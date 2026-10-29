#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,11), "Necesitas Python 3.11 o superior; puedes indicar PYTHON_BIN=python3.12"'
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
(cd frontend && npm ci && npm run build)
echo 'Listo. Inicia con ./start.sh'
