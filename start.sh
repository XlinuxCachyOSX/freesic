#!/bin/sh
# Avvio one-click del player musicale.
set -e
cd "$(dirname "$0")"

PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python

if [ ! -d .venv ]; then
  echo "Creo l'ambiente virtuale (una volta sola)..."
  "$PY" -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip >/dev/null
  ./.venv/bin/python -m pip install -r requirements.txt
fi

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
echo ""
echo "  Musica senza pubblicità - avvio del server..."
echo "  http://$HOST:$PORT/"
echo ""
exec ./.venv/bin/python -m uvicorn server.main:app --host "$HOST" --port "$PORT"
