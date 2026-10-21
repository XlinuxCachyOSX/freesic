#!/bin/sh
# Avvio one-click del player musicale: crea l'ambiente, avvia il server
# e apre automaticamente il sito nel browser.
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
SITO="http://$HOST:$PORT/"
[ "$HOST" = "0.0.0.0" ] && SITO="http://127.0.0.1:$PORT/"

# Apre il browser appena il server risponde (non blocca l'avvio).
apri_browser() {
  tentativi=0
  while [ "$tentativi" -lt 60 ]; do
    if ./.venv/bin/python - "$SITO" <<'PY' >/dev/null 2>&1
import sys, urllib.request
urllib.request.urlopen(sys.argv[1], timeout=1)
PY
    then
      ./.venv/bin/python -c "import webbrowser, sys; webbrowser.open(sys.argv[1])" "$SITO" >/dev/null 2>&1 || true
      return 0
    fi
    tentativi=$((tentativi + 1))
    sleep 0.5
  done
}

echo ""
echo "  Musica senza pubblicità - avvio del server..."
echo "  $SITO"
echo ""
apri_browser &
exec ./.venv/bin/python -m uvicorn server.main:app --host "$HOST" --port "$PORT"
