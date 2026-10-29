from concurrent.futures import ThreadPoolExecutor

import pytest

from backend import ledger
from test_api import manual_data


def test_agent_proposal_retries_do_not_change_ledger_or_duplicate_proposals(client):
    body = {**manual_data(), "request_id": "agent-demo-123"}
    first = client.post("/api/agent/proposals/manual", json=body)
    retry = client.post("/api/agent/proposals/manual", json=body)
    assert first.status_code == retry.status_code == 200
    assert first.json()["id"] == retry.json()["id"]
    assert first.json()["status"] == "pending"
    assert ledger.metadata()["pending"] == 1
    assert ledger.metadata()["count"] == 0
    assert ledger.summary()["expense_minor"] == 0
    assert first.json()["payload"]["movements"][0]["source_file"] == "Propuesta de agente externo"


def test_agent_request_cannot_silently_change_payload_on_retry(client):
    body = {**manual_data(), "request_id": "agent-demo-123"}
    proposal = client.post("/api/agent/proposals/manual", json=body).json()
    response = client.post("/api/agent/proposals/manual", json={**body, "amount_minor": 999})
    assert response.status_code == 409
    assert ledger.get_proposal(proposal["id"])["payload"]["movements"][0]["amount_minor"] == -150050
    assert ledger.metadata()["pending"] == 1


def test_parallel_agent_retries_are_atomic():
    with ThreadPoolExecutor(max_workers=4) as pool:
        proposals = list(pool.map(lambda _: ledger.propose_agent_movement("agent-concurrent", manual_data()), range(8)))
    assert len({p["id"] for p in proposals}) == 1
    assert ledger.metadata()["pending"] == 1
    with ledger.connection() as con:
        assert con.execute("SELECT count(*) FROM audit WHERE action='agent_proposal'").fetchone()[0] == 1


@pytest.mark.parametrize("status", ["confirmed", "rejected"])
def test_retry_after_human_decision_returns_original_status(client, status):
    body = {**manual_data(), "request_id": "agent-demo-123"}
    proposal = client.post("/api/agent/proposals/manual", json=body).json()
    if status == "confirmed":
        ledger.confirm_proposal(proposal["id"])
    else:
        ledger.reject_proposal(proposal["id"])
    retry = client.post("/api/agent/proposals/manual", json=body)
    assert retry.json()["id"] == proposal["id"]
    assert retry.json()["status"] == status
    assert ledger.metadata()["pending"] == 0
    assert ledger.metadata()["count"] == (1 if status == "confirmed" else 0)


@pytest.mark.parametrize("change", [{"request_id": ""}, {"request_id": "bad key /"}, {"request_id": "x"*101}, {"amount_minor": 100.5}, {"amount_minor": True}, {"amount_minor": -100}, {"account": "unknown"}])
def test_invalid_agent_inputs_cannot_create_proposals(client, change):
    response = client.post("/api/agent/proposals/manual", json={**manual_data(), "request_id": "agent-demo-123", **change})
    assert response.status_code in (400, 422)
    assert ledger.metadata()["pending"] == ledger.metadata()["count"] == 0
