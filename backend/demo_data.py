"""Entirely invented business data. Never derived from a user's workbook."""
import hashlib
import json
from pathlib import Path

from . import ledger
from .importer import refresh_preview


def payload():
    path = Path(__file__).resolve().parents[1] / "fixtures" / "movimientos-demo.json"
    raw = path.read_bytes()
    data = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    rows = []
    for i, item in enumerate(data["movements"], 1):
        rows.append({**item, "currency": "MXN", "treatment": ledger.treatment(item["category"], item["kind"]),
            "reference": f"REF-DEMO-{i:03}", "property": f"DEMO-{(i % 4) + 1:03}",
            "source_file": "movimientos-demo.json", "source_sheet": "Dataset ficticio", "source_row": i,
            "source_hash": digest})
    return refresh_preview({"filename": "movimientos-demo.json · datos ficticios", "file_hash": digest,
        "movements": rows, "categories": sorted({r["category"] for r in rows} | {"Por revisar"}),
        "openings": [{"account": a, "amount_minor": n, "source": "Saldo ficticio de demostración"}
            for a, n in data["opening_minor"].items()], "errors": [], "corrections": [],
        "notes": ["Todos los nombres, conceptos, referencias, folios e importes de este ejemplo son ficticios."]})


def seed():
    if ledger.metadata()["count"]:
        return
    data = payload()
    data["movements"] = data["movements"][:18]
    refresh_preview(data)
    p = ledger.add_proposal("demo_seed", data)
    ledger.confirm_proposal(p["id"])


def document_payload(format: str, account: str):
    """A labeled UI example, not a claim of having parsed an uploaded document."""
    if format not in {"pdf", "image"} or account not in {a["id"] for a in ledger.ACCOUNTS}:
        raise ValueError("Ejemplo o cuenta inválidos")
    filename = "estado-demo-ficticio.pdf" if format == "pdf" else "recibo-demo-ficticio.png"
    source = f"ejemplo-documento-v1:{format}:{account}".encode()
    digest = hashlib.sha256(source).hexdigest()
    examples = [
        ("Materiales ficticios de Proveedor Demo", 35000, "Pago a proveedores", "DOC-DEMO-001"),
        ("Nómina ficticia de Equipo Demo", 420000, "Nómina y sueldos", "DOC-DEMO-002"),
    ][:2 if format == "pdf" else 1]
    movements = []
    for i, (description, amount, category, reference) in enumerate(examples, 4):
        movement = ledger.validate_manual({"date": "2026-10-28", "account": account,
            "kind": "cargo" if account == "tarjeta_bbva" else "egreso",
            "category": category, "description": description, "amount_minor": amount,
            "reference": reference, "property": "DEMO-001"})
        movement.update(source_file=filename, source_sheet="Página 1", source_row=i, source_hash=digest)
        movements.append(movement)
    return refresh_preview({"filename": filename, "file_hash": digest, "movements": movements,
        "categories": ledger.metadata()["categories"], "openings": [], "errors": [], "corrections": [],
        "document": {"mime": "application/pdf" if format == "pdf" else "image/png", "pages": 1,
            "account": account, "model": "ejemplo-simulado", "warnings": [], "extracted_rows": [], "simulated": True},
        "notes": ["Ejemplo ficticio y simulado: no se leyó ningún PDF o imagen ni se llamó a OpenAI.",
                  "Todos los conceptos, importes y referencias fueron inventados para la demo.",
                  "Revisa o edita los movimientos antes de confirmar. Importado no significa conciliado."]})
