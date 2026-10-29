#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'Primero ejecuta ./scripts/setup.sh (Python 3.10+ y Node 20+).'
  exit 1
fi
if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm run build)
fi
echo 'Folio → http://127.0.0.1:8000'
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "${PORT:-8000}"
