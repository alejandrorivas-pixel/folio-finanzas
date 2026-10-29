from backend import ledger
from conftest import workbook_bytes


def manual_data(**kwargs):
    return {"date": "2026-10-28", "account": "efectivo", "kind": "egreso", "category": "Nómina y sueldos",
        "description": "Registro ficticio", "amount_minor": 150050, **kwargs}


def test_full_import_preview_confirm_and_evidence_flow(client):
    p = client.post("/api/imports/preview", files={"file": ("fixture.xlsx", workbook_bytes())}).json()
    assert p["payload"]["stats"]["new"] == 2
    assert client.get("/api/meta").json()["count"] == 0
    assert client.post(f"/api/proposals/{p['id']}/confirm", json={}).status_code == 422
    result = client.post(f"/api/proposals/{p['id']}/confirm", json={"confirm": True}).json()
    assert result["inserted"] == 2
    assert client.get("/api/summary?month=2026-10").json()["expense_minor"] == 12000
    rows = client.get("/api/movements?month=2026-10&category=Nómina y sueldos").json()
    assert rows["total"] == 1
    mid = rows["items"][0]["id"]
    assert client.get(f"/api/movements/{mid}").json()["source_row"] == 5
    assert client.get(f"/api/movements?ids={mid}").json()["total"] == 1
    assert client.get("/api/movements?ids=").json()["total"] == 0


def test_manual_proposal_does_not_change_figures_until_explicit_confirm(client):
    r = client.post("/api/proposals/manual", json=manual_data())
    assert r.status_code == 200
    p = r.json()
    assert client.get("/api/summary").json()["expense_minor"] == 0
    assert client.post(f"/api/proposals/{p['id']}/confirm", json={"confirm": False}).status_code == 422
    assert client.post(f"/api/proposals/{p['id']}/confirm", json={"confirm": True}).status_code == 200
    assert client.get("/api/summary").json()["expense_minor"] == 150050
    assert client.post("/api/proposals/manual", json=manual_data(amount_minor=1.5)).status_code == 422
    assert client.post("/api/proposals/manual", json=manual_data(kind="pago")).status_code == 400


def test_unknown_rows_files_and_periods_report_actionable_errors(client):
    assert client.get("/api/movements/no-such-id").status_code == 404
    assert client.get("/api/summary?month=2026-99").status_code == 400
    assert client.post("/api/imports/preview", files={"file": ("test.pdf", b"pdf")}).status_code == 400
    assert client.post("/api/imports/preview", files={"file": ("test.xlsx", b"invalid")}).status_code == 400


def test_unconfigured_ai_is_explicit_without_fake_financial_answer(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert client.get("/health").json()["ai_configured"] is False
    result = client.post("/api/chat", json={"message": "¿Cuánto gasté?"})
    assert result.status_code == 400
    assert "clave" in result.json()["detail"]


def test_csv_export_protects_formula_text(client):
    p = client.post("/api/proposals/manual", json=manual_data(description="=HYPERLINK(\"test\")")).json()
    client.post(f"/api/proposals/{p['id']}/confirm", json={"confirm": True})
    data = client.get("/api/export").text
    assert "'=HYPERLINK" in data
    assert "-1500.5" in data
