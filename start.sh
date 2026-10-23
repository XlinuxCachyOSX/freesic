#!/bin/sh
# Avvio one-click di FreeSic: prepara l'ambiente, avvia il server
# e apre automaticamente il sito nel browser.
# Stessa logica su Linux, macOS e Windows (vedi strumenti/avvia.py).
set -e
cd "$(dirname "$0")"

PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo ""
  echo "  Python 3 non trovato."
  echo "  Debian/Ubuntu: sudo apt install python3 python3-venv"
  echo "  Windows: installa Python 3 da https://www.python.org/downloads/"
  echo ""
  exit 1
fi

if [ "$1" = "--tunnel" ]; then export TUNNEL=1; fi
exec "$PY" strumenti/avvia.py
