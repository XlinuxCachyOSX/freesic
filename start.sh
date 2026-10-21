#!/bin/sh
# Avvio one-click del player musicale: prepara l'ambiente, avvia il server
# e apre automaticamente il sito nel browser.
set -e
cd "$(dirname "$0")"

PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Python non trovato. Installa Python 3 (Debian/Ubuntu: sudo apt install python3 python3-venv)."
  exit 1
fi

VENV_PY=".venv/bin/python"
MODULO_SISTEMA=0

# ---------------------------------------------------------------------------
# 1. Ambiente virtuale (con pip garantito)
# ---------------------------------------------------------------------------
if [ ! -x "$VENV_PY" ]; then
  echo "Creo l'ambiente virtuale (una volta sola)..."
  rm -rf .venv
  if ! "$PY" -m venv .venv >/dev/null 2>&1; then
    echo "  Il venv non e' stato creato: usero il Python di sistema."
    MODULO_SISTEMA=1
  fi
fi

if [ "$MODULO_SISTEMA" = "0" ] && [ -x "$VENV_PY" ]; then
  # pip a volte manca (venv creato a mano, ensurepip assente, ...)
  if ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    echo "Preparo pip nell'ambiente virtuale..."
    "$VENV_PY" -m ensurepip --upgrade >/dev/null 2>&1 || true
  fi

  if ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    echo "Ricreo l'ambiente virtuale con pip..."
    rm -rf .venv
    "$PY" -m venv .venv >/dev/null 2>&1 || true
    if [ -x "$VENV_PY" ]; then
      "$VENV_PY" -m ensurepip --upgrade >/dev/null 2>&1 || true
    fi
  fi

  if ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    echo "pip mancante: lo scarico (get-pip.py)..."
    if command -v curl >/dev/null 2>&1; then
      curl -sSL https://bootstrap.pypa.io/get-pip.py -o .get-pip.py || true
    elif command -v wget >/dev/null 2>&1; then
      wget -qO .get-pip.py https://bootstrap.pypa.io/get-pip.py || true
    fi
    if [ -s .get-pip.py ] && [ -x "$VENV_PY" ]; then
      "$VENV_PY" .get-pip.py >/dev/null 2>&1 || true
      rm -f .get-pip.py
    fi
  fi

  if ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    # ultimo tentativo: pip di sistema installato dentro il venv
    SITE=$("$VENV_PY" -c "import sysconfig; print(sysconfig.get_paths()['purelib'])" 2>/dev/null || echo "")
    if [ -n "$SITE" ] && "$PY" -m pip --version >/dev/null 2>&1; then
      echo "Uso il pip di sistema per l'ambiente virtuale..."
      "$PY" -m pip install --upgrade --target "$SITE" pip >/dev/null 2>&1 || true
    fi
  fi

  if ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    echo "  pip non e' installabile: passo al Python di sistema."
    MODULO_SISTEMA=1
  fi
fi

# ---------------------------------------------------------------------------
# 2. Dipendenze
# ---------------------------------------------------------------------------
if [ "$MODULO_SISTEMA" = "1" ]; then
  RUNPY="$PY"
  if ! "$PY" -m pip --version >/dev/null 2>&1; then
    echo ""
    echo "  pip non disponibile. Installa le dipendenze con:"
    echo "    sudo apt install python3-pip python3-venv"
    echo "    python3 -m pip install -r requirements.txt"
    echo ""
    exit 1
  fi
else
  RUNPY="$VENV_PY"
fi

if ! "$RUNPY" -c "import uvicorn, fastapi, yt_dlp" >/dev/null 2>&1; then
  echo "Installo le dipendenze necessarie..."
  "$RUNPY" -m pip install --upgrade pip >/dev/null 2>&1 || true
  "$RUNPY" -m pip install -r requirements.txt || {
    echo "Installazione delle dipendenze fallita. Riprova con:"
    echo "  $RUNPY -m pip install -r requirements.txt"
    exit 1
  }
fi

if ! "$RUNPY" -c "import uvicorn, fastapi, yt_dlp" >/dev/null 2>&1; then
  echo "Dipendenze ancora mancanti. Controlla l'output del pip qui sopra."
  exit 1
fi

# ---------------------------------------------------------------------------
# 3. Server + browser
# ---------------------------------------------------------------------------
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

porta_libera() {
  # stampa la prima porta libera a partire da $1 (vedi strumenti/porta.py)
  "$RUNPY" strumenti/porta.py "$1" "$HOST"
}
# Chiude una nostra precedente istanza (stessa cartella) che occupa la porta.
chiudi_precedenti() {
  for pid in $(pgrep -f "server.main:app" 2>/dev/null); do
    [ "$pid" = "$$" ] && continue
    exe=$(readlink "/proc/$pid/exe" 2>/dev/null || echo "")
    case "$exe" in *python*) ;; *) continue ;; esac
    cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || echo "")
    [ "$cwd" = "$PWD" ] || continue
    echo "  Chiudo l'istanza precedente (pid $pid)."
    kill "$pid" 2>/dev/null || true
  done
  sleep 1
}

PORT_TROVATA=$(porta_libera "$PORT")
if [ "$PORT_TROVATA" != "$PORT" ]; then
  # la porta richiesta e' occupata: chiudo la nostra istanza precedente e riprovo
  chiudi_precedenti
  PORT_TROVATA=$(porta_libera "$PORT")
  if [ "$PORT_TROVATA" != "$PORT" ]; then
    echo "  La porta $PORT e' occupata: uso la porta $PORT_TROVATA."
    PORT="$PORT_TROVATA"
  fi
fi
SITO="http://$HOST:$PORT/"
[ "$HOST" = "0.0.0.0" ] && SITO="http://127.0.0.1:$PORT/"

apri_browser() {
  tentativi=0
  while [ "$tentativi" -lt 60 ]; do
    if "$RUNPY" - "$SITO" <<'PY' >/dev/null 2>&1
import sys, urllib.request
urllib.request.urlopen(sys.argv[1], timeout=1)
PY
    then
      "$RUNPY" -c "import webbrowser, sys; webbrowser.open(sys.argv[1])" "$SITO" >/dev/null 2>&1 || true
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
exec "$RUNPY" -m uvicorn server.main:app --host "$HOST" --port "$PORT"
