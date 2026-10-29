"""Canonical, integer-only ledger. No agent can call the commit functions."""
from __future__ import annotations

import calendar
import hashlib
import json
import os
import sqlite3
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCOUNTS = [
    {"id": "efectivo", "name": "Efectivo", "kind": "cash"},
    {"id": "banco", "name": "Cuenta bancaria", "kind": "bank"},
    {"id": "tarjeta_bbva", "name": "Tarjeta BBVA", "kind": "credit"},
]


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize(value):
    return "".join(c for c in unicodedata.normalize("NFKD", str(value or "").lower()) if not unicodedata.combining(c)).strip()


def money(value):
    try:
        raw = str(value).replace("$", "").replace(",", "").strip()
        d = Decimal(raw)
        if not d.is_finite():
            raise ValueError("Importe no finito")
        cents = int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if abs(cents) > 10**14:
            raise ValueError("Importe fuera de rango")
        return cents
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Importe inválido") from exc


def treatment(category, kind):
    c = normalize(category)
    if kind == "pago" or c == "pago de tarjeta":
        return "card_payment"
    if "transferencia" in c or "traspaso" in c:
        return "transfer"
    if "deposito en garantia" in c:
        return "custody"
    if any(word in c for word in ["prestamo", "aportacion de socios", "retiro de socios"]):
        return "financing"
    if not c or c == "por revisar":
        return "por_revisar"
    return "operational"


@contextmanager
def connection():
    path = Path(os.environ.get("FINANZAS_DB", str(ROOT / "data" / "finanzas.sqlite")))
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    with connection() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY, name TEXT, kind TEXT,
          opening_minor INTEGER, opening_source TEXT);
        CREATE TABLE IF NOT EXISTS categories(name TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY, kind TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending', payload TEXT NOT NULL, created_at TEXT NOT NULL,
          confirmed_at TEXT);
        CREATE TABLE IF NOT EXISTS movements(id TEXT PRIMARY KEY, date TEXT NOT NULL,
          account TEXT NOT NULL REFERENCES accounts(id), kind TEXT NOT NULL, category TEXT NOT NULL,
          description TEXT NOT NULL, amount_minor INTEGER NOT NULL CHECK(typeof(amount_minor)='integer'),
          currency TEXT NOT NULL CHECK(currency='MXN'), reference TEXT, property TEXT,
          treatment TEXT NOT NULL, source_file TEXT, source_sheet TEXT, source_row INTEGER,
          source_hash TEXT, dedup_key TEXT UNIQUE, proposal_id TEXT REFERENCES proposals(id),
          created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS movements_date ON movements(date);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
          proposal_id TEXT, details TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
        for a in ACCOUNTS:
            con.execute("INSERT OR IGNORE INTO accounts(id,name,kind) VALUES(:id,:name,:kind)", a)
        for c in ["Nómina y sueldos", "Comisiones a vendedores", "Renta de oficina", "Pago a proveedores", "Tecnología y software", "Comisión de Renta", "Investigaciones", "Administraciones", "Por revisar"]:
            con.execute("INSERT OR IGNORE INTO categories VALUES(?)", (c,))


def metadata():
    with connection() as con:
        return {"accounts": [dict(r) for r in con.execute("SELECT * FROM accounts")],
                "categories": [r[0] for r in con.execute("SELECT name FROM categories ORDER BY name")],
                "months": [r[0] for r in con.execute("SELECT DISTINCT substr(date,1,7) FROM movements ORDER BY 1 DESC")],
                "count": con.execute("SELECT COUNT(*) FROM movements").fetchone()[0],
                "pending": con.execute("SELECT COUNT(*) FROM proposals WHERE status='pending'").fetchone()[0]}


def bounds(month):
    if not month:
        return None, None
    try:
        start = date.fromisoformat(month + "-01")
        return start.isoformat(), start.replace(day=calendar.monthrange(start.year, start.month)[1]).isoformat()
    except (ValueError, TypeError):
        raise ValueError("Periodo inválido; usa AAAA-MM")


def query_movements(month=None, account=None, category=None, search=None, ids=None, operating_only=False):
    clauses, params = [], []
    start, end = bounds(month)
    if start:
        clauses.append("date BETWEEN ? AND ?")
        params += [start, end]
    if account:
        if account not in {a["id"] for a in ACCOUNTS}:
            raise ValueError("Cuenta desconocida")
        clauses.append("account=?")
        params.append(account)
    if category:
        clauses.append("category=?")
        params.append(category)
    if search:
        clauses.append("(description LIKE ? OR reference LIKE ? OR category LIKE ? OR property LIKE ?)")
        params += ["%" + search + "%"] * 4
    if operating_only:
        clauses.append("treatment='operational'")
    if ids is not None:
        if not ids:
            return []
        clauses.append("id IN (" + ",".join("?" for _ in ids) + ")")
        params += ids
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with connection() as con:
        return [dict(r) for r in con.execute("SELECT * FROM movements" + where + " ORDER BY date DESC,created_at DESC,id", params)]


def totals(rows):
    operating = [r for r in rows if r["treatment"] == "operational"]
    refunds = {"abono", "devolucion"}
    income = sum(r["amount_minor"] for r in operating if r["amount_minor"] > 0 and r["kind"] not in refunds)
    expense = -sum(r["amount_minor"] for r in operating if r["amount_minor"] < 0 or r["kind"] in refunds)
    return {"income_minor": income, "expense_minor": expense, "operating_net_minor": income - expense,
            "inflow_minor": sum(r["amount_minor"] for r in rows if r["amount_minor"] > 0),
            "outflow_minor": -sum(r["amount_minor"] for r in rows if r["amount_minor"] < 0),
            "count": len(rows), "excluded_count": len(rows) - len(operating)}


def summary(month=None, account=None):
    rows = query_movements(month, account)
    result = totals(rows)
    _, end = bounds(month)
    with connection() as con:
        accounts = []
        for a in con.execute("SELECT * FROM accounts"):
            if account and a["id"] != account:
                continue
            q = "SELECT COALESCE(SUM(amount_minor),0), COUNT(*) FROM movements WHERE account=?"
            p = [a["id"]]
            if end:
                q += " AND date<=?"
                p.append(end)
            delta, count = con.execute(q, p).fetchone()
            a = dict(a)
            a["balance_minor"] = a["opening_minor"] + delta if a["opening_minor"] is not None else None
            a["count"] = count
            accounts.append(a)
    grouped, daily = {}, {}
    for r in rows:
        if r["treatment"] != "operational":
            continue
        day = daily.setdefault(r["date"], {"date": r["date"], "income_minor": 0, "expense_minor": 0})
        if r["amount_minor"] < 0 or r["kind"] in {"abono", "devolucion"}:
            grouped[r["category"]] = grouped.get(r["category"], 0) - r["amount_minor"]
            day["expense_minor"] -= r["amount_minor"]
        else:
            day["income_minor"] += r["amount_minor"]
    result.update({"accounts": accounts,
        "net_position_minor": sum(a["balance_minor"] for a in accounts) if accounts and all(a["balance_minor"] is not None for a in accounts) else None,
        "categories": sorted([{"name": k, "amount_minor": v} for k, v in grouped.items()], key=lambda r: -r["amount_minor"]),
        "daily": sorted(daily.values(), key=lambda r: r["date"]),
        "recent": rows[:6], "month": month, "unreconciled_count": len(rows),
        "review_count": sum(r["treatment"] == "por_revisar" for r in rows)})
    return result


def add_proposal(kind, payload):
    pid = str(uuid.uuid4())
    with connection() as con:
        con.execute("INSERT INTO proposals(id,kind,payload,created_at) VALUES(?,?,?,?)", (pid, kind, json.dumps(payload, ensure_ascii=False), now()))
    return get_proposal(pid)


def get_proposal(pid):
    with connection() as con:
        row = con.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
        if not row:
            raise KeyError("Propuesta no encontrada")
        out = dict(row)
        out["payload"] = json.loads(out["payload"])
        return out


def pending_proposals():
    with connection() as con:
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in con.execute("SELECT * FROM proposals WHERE status='pending' ORDER BY created_at DESC")]


def confirm_proposal(pid):
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
        if not row:
            raise KeyError("Propuesta no encontrada")
        if row["status"] == "confirmed":
            return {"inserted": 0, "duplicates": 0, "already_confirmed": True}
        if row["status"] != "pending":
            raise ValueError("Esta propuesta ya fue descartada")
        payload = json.loads(row["payload"])
        if payload.get("errors"):
            raise ValueError("Resuelve los errores del archivo antes de confirmar")
        inserted = duplicates = 0
        for r in payload["movements"]:
            cursor = con.execute("""INSERT OR IGNORE INTO movements(id,date,account,kind,category,description,
             amount_minor,currency,reference,property,treatment,source_file,source_sheet,source_row,source_hash,dedup_key,proposal_id,created_at)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                str(uuid.uuid4()), r["date"], r["account"], r["kind"], r["category"], r["description"],
                r["amount_minor"], "MXN", r.get("reference"), r.get("property"), r["treatment"],
                r.get("source_file"), r.get("source_sheet"), r.get("source_row"), r.get("source_hash"),
                r.get("dedup_key"), pid, now()))
            inserted += cursor.rowcount
            duplicates += 1 - cursor.rowcount
        for a in payload.get("openings", []):
            existing = con.execute("SELECT opening_minor FROM accounts WHERE id=?", (a["account"],)).fetchone()[0]
            if existing is not None and existing != a["amount_minor"]:
                raise ValueError("El saldo inicial cambió. Revisa el archivo; no se sobrescribirá el saldo existente.")
            con.execute("UPDATE accounts SET opening_minor=?,opening_source=? WHERE id=?", (a["amount_minor"], a["source"], a["account"]))
        for c in payload.get("categories", []):
            con.execute("INSERT OR IGNORE INTO categories VALUES(?)", (c,))
        con.execute("UPDATE proposals SET status='confirmed',confirmed_at=? WHERE id=?", (now(), pid))
        con.execute("INSERT INTO audit(action,proposal_id,details,created_at) VALUES('confirm',?,?,?)", (pid, json.dumps({"inserted": inserted, "duplicates": duplicates}), now()))
        return {"inserted": inserted, "duplicates": duplicates, "already_confirmed": False}


def reject_proposal(pid):
    with connection() as con:
        c = con.execute("UPDATE proposals SET status='rejected' WHERE id=? AND status='pending'", (pid,))
        if not c.rowcount:
            raise ValueError("Solo se pueden descartar propuestas pendientes")
        con.execute("INSERT INTO audit(action,proposal_id,details,created_at) VALUES('reject',?,'{}',?)", (pid, now()))


def existing_keys():
    with connection() as con:
        return {r[0] for r in con.execute("SELECT dedup_key FROM movements WHERE dedup_key IS NOT NULL")}


def validate_manual(data):
    d = date.fromisoformat(data["date"])
    if data["account"] not in {a["id"] for a in ACCOUNTS}:
        raise ValueError("Elige una cuenta válida")
    amount = data["amount_minor"]
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0 or amount > 10**14:
        raise ValueError("El importe debe ser positivo y estar expresado en centavos enteros")
    kind = data["kind"]
    card = data["account"] == "tarjeta_bbva"
    allowed = {"cargo", "pago", "interes", "comision", "abono", "devolucion"} if card else {"ingreso", "egreso"}
    if kind not in allowed:
        raise ValueError("Tipo de movimiento incompatible con la cuenta")
    if not data["description"].strip() or not data["category"].strip():
        raise ValueError("Descripción y categoría son obligatorias")
    category = data["category"].strip()
    if category not in metadata()["categories"]:
        raise ValueError("Selecciona una categoría del catálogo")
    negative = kind in {"egreso", "cargo", "interes", "comision"}
    return {"date": d.isoformat(), "account": data["account"], "kind": kind,
        "category": category, "description": data["description"].strip(),
        "amount_minor": -amount if negative else amount, "currency": "MXN",
        "reference": data.get("reference"), "property": data.get("property"),
        "treatment": treatment(category, kind), "source_file": "Registro manual", "source_sheet": None,
        "source_row": None, "source_hash": None, "dedup_key": None}
