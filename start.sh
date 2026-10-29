#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'Primero ejecuta ./scripts/setup.sh (Python 3.11+ y Node 20+).'
  exit 1
fi
# Always build the real app: a previous UI/UX demo build must not replace real data.
(cd frontend && npm run build)
echo "Folio → http://127.0.0.1:${PORT:-8000}"
exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "${PORT:-8000}"
