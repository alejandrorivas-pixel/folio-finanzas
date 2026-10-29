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
