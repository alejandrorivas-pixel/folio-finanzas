#!/bin/sh
set -eu

# stdout is reserved for the MCP stdio protocol.
CDPATH= cd -P "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  printf '%s\n' 'Primero ejecuta ./scripts/setup.sh (Python 3.11+ y Node 20+).' >&2
  exit 1
fi

# This bridge calls the local API; it never needs an OpenAI secret.
# This affects this child process only, not the launching shell or web backend.
unset OPENAI_API_KEY
exec .venv/bin/python -m backend.mcp_server
