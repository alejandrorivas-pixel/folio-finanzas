"""Read-only MCP handshake check. Prints no movements, balances, or secrets."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters


ROOT = Path(__file__).resolve().parents[1]


def data(result):
    if result.is_error:
        raise RuntimeError("Una herramienta MCP devolvió un error; revisa que Folio esté ejecutándose.")
    if result.structured_content is not None:
        return result.structured_content
    return json.loads("".join(block.text for block in result.content if block.type == "text"))


async def check(url):
    params = StdioServerParameters(
        command=str(ROOT / "start-mcp.sh"),
        args=[],
        cwd=ROOT,
        env={"FOLIO_API_URL": url, "OPENAI_API_KEY": "", "PYTHON_DOTENV_DISABLED": "1"},
    )
    async with Client(params, read_timeout_seconds=10) as client:
        tools = (await client.list_tools()).tools
        status = data(await client.call_tool("folio_status"))
        summary = data(await client.call_tool("folio_summary"))
        resources = (await client.list_resources()).resources
        if status.get("application") != "folio":
            raise RuntimeError("La API no se identificó como Folio.")
        return {
            "mcp": "ok",
            "transport": "stdio",
            "application": status["application"],
            "demo_mode": status.get("demo_mode"),
            "confirmed_count": summary["count"],
            "tools": sorted(tool.name for tool in tools),
            "resources": [str(resource.uri) for resource in resources],
            "writes_performed": False,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("FOLIO_API_URL", "http://127.0.0.1:8000"), help="URL local de la API Folio")
    args = parser.parse_args()
    try:
        result = asyncio.run(check(args.url))
    except Exception:
        # Tool/protocol errors may carry remote payloads: do not echo them here.
        print("No se pudo verificar MCP. Comprueba la URL local y que la API Folio esté activa y actualizada.", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
