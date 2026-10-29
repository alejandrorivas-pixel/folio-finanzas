"""Read-only adapter for the user's Balance workbook. Preserve every valid posting."""
import hashlib
import io
import json
import warnings
from collections import Counter
from datetime import date, datetime
from zipfile import ZipFile, BadZipFile

import openpyxl

from . import ledger

SHEETS = {
    "Movimientos Efectivo": ("efectivo", "Balance Efectivo", "C5"),
    "Movimientos Banco": ("banco", "Balance Banco", "C5"),
    "Movimientos Tarjeta BBVA": ("tarjeta_bbva", "Balance Tarjeta BBVA", "C9"),
}


def parse_workbook(content, filename):
    if len(content) > 15 * 1024 * 1024:
        raise ValueError("El archivo excede 15 MB")
    try:
        with ZipFile(io.BytesIO(content)) as z:
            if sum(i.file_size for i in z.infolist()) > 80 * 1024 * 1024:
                raise ValueError("El contenido descomprimido excede el límite")
    except BadZipFile:
        raise ValueError("El archivo no es un Excel XLSX válido")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        w = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        if not set(SHEETS).intersection(w.sheetnames):
            raise ValueError("No se encontraron las hojas de movimientos del Balance. Usa tu archivo original .xlsx.")
        sha = hashlib.sha256(content).hexdigest()
        movements, errors, notes, openings, categories = [], [], [], [], set()
        occurrences = Counter()
        keys = ledger.existing_keys()
        for name, (account, balance_sheet, cell) in SHEETS.items():
            if name not in w.sheetnames:
                notes.append(f"No se encontró {name}; no se importará esa cuenta.")
                continue
            sheet = w[name]
            if sheet.max_row > 50000:
                raise ValueError("La hoja excede 50,000 filas")
            header = [c.value for c in next(sheet.iter_rows(min_row=3, max_row=3, max_col=9))]
            if header[1:5] != ["Fecha", "Tipo", "Categoría", "Concepto / Descripción"]:
                raise ValueError(f"Los encabezados de {name} cambiaron; revisa el formato.")
            if balance_sheet in w.sheetnames and w[balance_sheet][cell].value is not None:
                opening = ledger.money(w[balance_sheet][cell].value)
                openings.append({"account": account, "amount_minor": -opening if account == "tarjeta_bbva" else opening,
                    "source": f"{filename} · {balance_sheet}!{cell}"})
            else:
                notes.append(f"Falta el saldo inicial de {account}; su saldo quedará sin determinar.")
            for idx, row in enumerate(sheet.iter_rows(min_row=4, max_col=17, values_only=True), 4):
                _, dt, kind, cat, desc, ref, prop, incoming, outgoing, *_ = row
                if not any(v is not None for v in (dt, kind, desc, incoming, outgoing)):
                    continue
                if kind is None and incoming is None and outgoing is None:
                    continue  # Opening balance note, not a transaction.
                try:
                    if not isinstance(dt, (date, datetime)):
                        raise ValueError("Fecha vacía o inválida")
                    kind = ledger.normalize(kind)
                    card = account == "tarjeta_bbva"
                    allowed = {"cargo", "pago", "interes", "comision", "abono", "devolucion"} if card else {"ingreso", "egreso"}
                    if kind not in allowed:
                        raise ValueError("Tipo de movimiento desconocido")
                    a, b = ledger.money(incoming or 0), ledger.money(outgoing or 0)
                    if a < 0 or b < 0 or (a and b) or not (a or b):
                        raise ValueError("Se requiere exactamente un importe positivo en entrada/cargo o salida/abono")
                    negative = kind in {"egreso", "cargo", "interes", "comision"}
                    expected_first = negative if card else not negative
                    if bool(a) != expected_first:
                        raise ValueError("La columna del importe no corresponde al tipo de movimiento")
                    amount = -(a or b) if negative else (a or b)
                    if not str(desc or "").strip():
                        raise ValueError("Falta la descripción")
                    category = str(cat or "Por revisar").strip()
                    categories.add(category)
                    r = {"date": dt.date().isoformat() if isinstance(dt, datetime) else dt.isoformat(),
                        "account": account, "kind": kind, "category": category, "description": str(desc).strip(),
                        "amount_minor": amount, "currency": "MXN", "reference": str(ref).strip() if ref is not None else None,
                        "property": str(prop).strip() if prop is not None else None,
                        "treatment": ledger.treatment(category, kind), "source_file": filename,
                        "source_sheet": name, "source_row": idx, "source_hash": sha}
                    canonical = {k: r[k] for k in ["date", "account", "kind", "category", "description", "amount_minor", "reference", "property"]}
                    # Category is editable metadata, not transaction identity.
                    canonical.pop("category")
                    base = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                    occurrences[base] += 1
                    r["dedup_key"] = f"{base}:{occurrences[base]}"
                    r["duplicate"] = r["dedup_key"] in keys
                    movements.append(r)
                except (ValueError, TypeError) as exc:
                    errors.append({"sheet": name, "row": idx, "message": str(exc)})
        if "Catalogos" in w.sheetnames:
            for row in w["Catalogos"].iter_rows(min_row=2, max_col=3, values_only=True):
                for value in (row[0], row[2]):
                    if isinstance(value, str) and value.strip():
                        categories.add(value.strip())
        new = [r for r in movements if not r["duplicate"]]
        if not movements and not errors:
            errors.append({"sheet": "Archivo", "row": 0, "message": "No se encontraron movimientos"})
        return {"filename": filename, "file_hash": sha, "movements": movements, "openings": openings,
            "categories": sorted(categories), "errors": errors, "notes": notes,
            "stats": {**ledger.totals(new), "total": len(movements), "new": len(new),
                "duplicates": len(movements) - len(new), "errors": len(errors),
                "accounts": dict(Counter(r["account"] for r in new)),
                "review": sum(r["treatment"] == "por_revisar" for r in new)}}
    finally:
        w.close()
