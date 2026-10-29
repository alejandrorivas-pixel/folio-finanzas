"""Exercise the actual MCP stdio transport using only isolated, fictitious data."""

import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
from mcp import Client, StdioServerParameters
import pytest

from backend.agent_client import FolioClient, FolioClientError, validate_api_url


ROOT = Path(__file__).resolve().parents[2]
TOOLS = {
    "folio_status", "folio_catalog", "folio_summary", "folio_movements",
    "folio_movement", "folio_propose_movement", "folio_pending_proposals", "folio_proposal",
}


def tool_data(result):
    """Prefer protocol structured content; text is the SDK-compatible fallback."""
    assert not result.is_error, result.content
    if result.structured_content is not None:
        return result.structured_content
    text = "".join(block.text for block in result.content if block.type == "text")
    return json.loads(text)


@pytest.fixture
def isolated_api(tmp_path):
    # Inherit only ordinary runtime settings, never a provider key or a real DB path.
    env = {key: os.environ[key] for key in ("PATH", "HOME", "SYSTEMROOT", "TMPDIR") if key in os.environ}
    env.update({
        "FINANZAS_DB": str(tmp_path / "mcp-demo.sqlite"),
        "FOLIO_DEMO": "1",
        "OPENAI_API_KEY": "",
        "PYTHON_DOTENV_DISABLED": "1",
    })
    # Pass the bound socket directly to uvicorn, avoiding a port-allocation race.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    log_path = tmp_path / "api.log"
    process = None
    try:
        with log_path.open("w+") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.main:app", "--fd", str(listener.fileno()), "--log-level", "error"],
                cwd=ROOT,
                env=env,
                pass_fds=(listener.fileno(),),
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            listener.close()
            deadline = time.monotonic() + 12
            with httpx.Client(base_url=url, timeout=1, trust_env=False) as api:
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        log.seek(0)
                        pytest.fail(f"Isolated API exited before startup: {log.read()}")
                    try:
                        response = api.get("/health")
                    except httpx.TransportError:
                        response = None
                    if response is not None and response.status_code == 200:
                        assert response.json()["demo_mode"] is True
                        assert response.json()["ai_configured"] is False
                        yield url, api
                        return
                    time.sleep(0.05)
                pytest.fail("Isolated API did not become healthy within 12 seconds")
    finally:
        listener.close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_stdio_protocol_reads_and_proposes_without_confirming(isolated_api):
    url, api = isolated_api
    expected = api.get("/api/summary", params={"month": "2026-10"}).json()
    assert expected["count"] == 18
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.mcp_server"],
        cwd=ROOT,
        env={"FOLIO_API_URL": url, "OPENAI_API_KEY": "", "PYTHON_DOTENV_DISABLED": "1"},
    )

    async def exercise():
        async with Client(params, read_timeout_seconds=10) as mcp:
            listed = (await mcp.list_tools()).tools
            assert {tool.name for tool in listed} == TOOLS
            assert not any("confirm" in tool.name or "delete" in tool.name for tool in listed)
            for tool in listed:
                assert tool.annotations is not None
                assert tool.annotations.read_only_hint is (tool.name != "folio_propose_movement")
                assert tool.annotations.destructive_hint is False

            status = tool_data(await mcp.call_tool("folio_status"))
            assert status["application"] == "folio"
            assert status["demo_mode"] is True
            assert status["ai_configured"] is False

            catalog = tool_data(await mcp.call_tool("folio_catalog"))
            assert {a["id"] for a in catalog["accounts"]} == {"efectivo", "banco", "tarjeta_bbva"}
            assert "Nómina y sueldos" in catalog["categories"]

            summary = tool_data(await mcp.call_tool("folio_summary", {"month": "2026-10"}))
            for key in ("income_minor", "expense_minor", "operating_net_minor", "count"):
                assert summary[key] == expected[key]
            assert [(a["id"], a["balance_minor"]) for a in summary["accounts"]] == [
                (a["id"], a["balance_minor"]) for a in expected["accounts"]
            ]

            movements = tool_data(await mcp.call_tool("folio_movements", {"month": "2026-10", "size": 2}))
            assert movements["total"] == 18
            assert len(movements["items"]) == 2
            movement_id = movements["items"][0]["id"]
            single = tool_data(await mcp.call_tool("folio_movement", {"movement_id": movement_id}))
            assert single["id"] == movement_id
            assert single["source_file"] == "movimientos-demo.json"

            resources = await mcp.list_resources()
            assert "folio://guide" in {str(resource.uri) for resource in resources.resources}
            guide = await mcp.read_resource("folio://guide")
            assert guide.contents

            draft = {
                "request_id": "mcp-protocol-fixture-001",
                "date": "2026-10-28",
                "account": "efectivo",
                "kind": "egreso",
                "category": "Nómina y sueldos",
                "description": "Nómina ficticia desde agente de prueba",
                "amount_minor": 12345,
            }
            proposal = tool_data(await mcp.call_tool("folio_propose_movement", draft))
            assert proposal["status"] == "pending"
            repeated = tool_data(await mcp.call_tool("folio_propose_movement", draft))
            assert repeated["id"] == proposal["id"]

            conflict = await mcp.call_tool("folio_propose_movement", {**draft, "amount_minor": 54321})
            assert conflict.is_error
            invalid = await mcp.call_tool("folio_propose_movement", {**draft, "request_id": "mcp-invalid-float", "amount_minor": 1.5})
            assert invalid.is_error

            detail = tool_data(await mcp.call_tool("folio_proposal", {"proposal_id": proposal["id"]}))
            assert detail["id"] == proposal["id"]
            assert detail["status"] == "pending"
            pending = tool_data(await mcp.call_tool("folio_pending_proposals"))
            assert pending["total"] == 1
            assert pending["items"][0]["id"] == proposal["id"]

            after = tool_data(await mcp.call_tool("folio_summary", {"month": "2026-10"}))
            assert after == summary

    asyncio.run(exercise())
    # An independent direct API read also confirms that the agent posted nothing.
    assert api.get("/api/summary", params={"month": "2026-10"}).json() == expected
    assert len(api.get("/api/proposals").json()) == 1


@pytest.mark.parametrize("url", [
    "https://example.com:8000", "http://192.168.1.10:8000", "http://169.254.169.254:8000",
    "http://127.0.0.1:80", "http://user:secret@127.0.0.1:8000", "http://127.0.0.1:8000/api",
    "http://127.0.0.1:8000?token=secret", "http://127.0.0.1:8000#fragment",
    "http://localhost.evil.example:8000", " http://127.0.0.1:8000",
])
def test_agent_bridge_rejects_nonlocal_or_ambiguous_urls(url):
    with pytest.raises(FolioClientError):
        validate_api_url(url)


def test_agent_bridge_accepts_explicit_local_port():
    assert validate_api_url("http://127.0.0.1:8000/") == "http://127.0.0.1:8000"
    assert validate_api_url("http://localhost:8001") == "http://localhost:8001"


def test_agent_bridge_checks_folio_identity_before_posting():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(200, json={"application": "another-service"})

    client = FolioClient(transport=httpx.MockTransport(handler))
    with pytest.raises(FolioClientError, match="no corresponde a Folio"):
        asyncio.run(client.post("/api/agent/proposals/manual", {"request_id": "test-id"}))
    assert calls == [("GET", "/health")]


def test_agent_bridge_does_not_follow_redirects_or_echo_payloads():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/health":
            return httpx.Response(200, json={"application": "folio"})
        return httpx.Response(307, headers={"Location": "https://external.example/private"}, text="private-account-details")

    client = FolioClient(transport=httpx.MockTransport(handler))
    with pytest.raises(FolioClientError) as error:
        asyncio.run(client.get("/api/summary"))
    assert "private-account-details" not in str(error.value)
    assert "external.example" not in str(error.value)
    assert calls == ["/health", "/api/summary"]


def test_agent_bridge_cannot_confirm_or_proxy_arbitrary_requests():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"application": "folio"})

    client = FolioClient(transport=httpx.MockTransport(handler))
    for path in ("/api/proposals/anything/confirm", "/api/proposals/anything/reject", "/api/chat"):
        with pytest.raises(FolioClientError, match="no está disponible"):
            asyncio.run(client.post(path, {"confirm": True}))
    assert not calls


def test_smoke_command_is_read_only_and_omits_financial_details(isolated_api):
    url, api = isolated_api
    before = api.get("/api/summary").json()
    result = subprocess.run(
        [sys.executable, "scripts/smoke_mcp.py", "--url", url],
        cwd=ROOT, capture_output=True, text=True, timeout=15, check=True,
    )
    output = json.loads(result.stdout)
    assert output["mcp"] == "ok"
    assert output["confirmed_count"] == 18
    assert output["writes_performed"] is False
    assert set(output["tools"]) == TOOLS
    assert "folio://guide" in output["resources"]
    assert not {"accounts", "movements", "amount_minor", "income_minor", "expense_minor"} & output.keys()
    assert api.get("/api/summary").json() == before
    assert api.get("/api/proposals").json() == []
