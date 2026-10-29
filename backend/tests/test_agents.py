import asyncio
import json
from types import SimpleNamespace

from agents.tool_context import ToolContext

from backend import ai, ledger
from backend.importer import parse_workbook
from conftest import workbook_bytes


def test_capture_agent_requires_review_before_posting(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-real-key")

    async def run(agent, text, **kwargs):
        assert agent.name == "Agente de captura"
        return SimpleNamespace(final_output=ai.CaptureDraft(date="2026-10-28", account="efectivo", kind="egreso",
            category="Nómina y sueldos", description="Pago ficticio", amount_pesos="1500.50", reference=None, property=None, question=None))

    monkeypatch.setattr(ai.Runner, "run", run)
    result = asyncio.run(ai.capture("Hoy pagué 1500.50 de nómina en efectivo"))
    assert result["proposal"]["status"] == "pending"
    assert ledger.metadata()["count"] == 0
    assert result["proposal"]["payload"]["movements"][0]["amount_minor"] == -150050


def test_capture_agent_asks_for_missing_amount_without_inventing(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-real-key")

    async def run(*args, **kwargs):
        return SimpleNamespace(final_output=ai.CaptureDraft(date="2026-10-28", account="efectivo", kind="egreso",
            category="Nómina y sueldos", description="Pago ficticio", amount_pesos=None, reference=None, property=None, question="¿Qué importe pagaste?"))

    monkeypatch.setattr(ai.Runner, "run", run)
    result = asyncio.run(ai.capture("Pagué nómina"))
    assert result["proposal"] is None
    assert "importe" in result["message"]
    assert ledger.pending_proposals() == []


def test_analyst_returns_actual_tool_totals_instead_of_model_invented_numbers(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-a-real-key")
    p = ledger.add_proposal("import", parse_workbook(workbook_bytes(), "fixture.xlsx"))
    ledger.confirm_proposal(p["id"])

    async def run(agent, text, **kwargs):
        assert len(agent.tools) == 1
        tool = agent.tools[0]
        arguments = json.dumps({"periodo": "2026-10", "cuenta": None, "categoria": "Nómina y sueldos", "texto": None, "solo_operativos": True})
        ctx = ToolContext(context=None, tool_name=tool.name, tool_call_id="test-call", tool_arguments=arguments)
        result = json.loads(await tool.on_invoke_tool(ctx, arguments))
        assert result["totals"]["expense_minor"] == 12000
        return SimpleNamespace(final_output="Inventado: $999,999.99")

    monkeypatch.setattr(ai.Runner, "run", run)
    result = asyncio.run(ai.analyze("¿Cuánto pagué de nómina?", "2026-10"))
    assert "$120.00" in result["message"]
    assert "999,999" not in result["message"]
    assert len(result["evidence"][0]["movement_ids"]) == 1
    assert ledger.metadata()["count"] == 2
