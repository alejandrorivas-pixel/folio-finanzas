from backend import ledger
from backend import demo_data


def test_demo_dataset_is_invented_and_seed_is_idempotent(monkeypatch):
    monkeypatch.setenv("FOLIO_DEMO", "1")
    demo_data.seed()
    demo_data.seed()
    rows = ledger.query_movements()
    assert len(rows) == 18
    assert all("fictici" in r["description"] or "ficticio" in r["description"] for r in rows)
    assert all(r["property"].startswith("DEMO-") for r in rows)
    assert all(r["reference"].startswith("REF-DEMO-") for r in rows)
    p = demo_data.payload()
    assert p["stats"]["duplicates"] == 18
    assert p["stats"]["new"] == 6


def test_demo_preview_does_not_open_a_personal_workbook(client, monkeypatch):
    monkeypatch.setenv("FOLIO_DEMO", "1")
    def forbidden(*args, **kwargs):
        raise AssertionError("No se debe intentar leer un Excel en modo demo")
    monkeypatch.setattr("backend.main.parse_workbook", forbidden)
    r = client.post("/api/imports/local-preview")
    assert r.status_code == 200
    assert r.json()["payload"]["filename"].startswith("movimientos-demo.json")
    assert client.get("/api/meta").json()["company_name"] == "Empresa Demo"


def test_demo_upload_is_blocked_before_parsing_the_file(client, monkeypatch):
    monkeypatch.setenv("FOLIO_DEMO", "1")
    result = client.post("/api/imports/preview", files={"file": ("file.xlsx", b"not-read")})
    assert result.status_code == 400
    assert "ficticios" in result.json()["detail"]
    assert ledger.metadata()["count"] == 0
