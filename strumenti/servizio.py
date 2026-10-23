"""Server FreeSic: avvia uvicorn e apre il browser.

Viene eseguito con l'interprete del virtualenv, quindi ha a disposizione
tutte le dipendenze. E' lo stesso file su Linux, macOS e Windows.
"""

import os
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import uvicorn  # noqa: E402

from server.main import app  # noqa: E402
from strumenti import prepara  # noqa: E402


def apri_browser(sito: str) -> None:
    """Aspetta che il server risponda e poi apre il browser."""
    for _ in range(60):
        try:
            urllib.request.urlopen(sito, timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    try:
        webbrowser.open(sito)
    except Exception:
        pass


def indirizzi_rete() -> list:
    """Indirizzi IP della macchina (per aprire il sito dal telefono)."""
    import socket
    trovati = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        trovati.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in trovati and not ip.startswith("127."):
                trovati.append(ip)
    except OSError:
        pass
    return trovati


def main() -> int:
    porta = int(os.environ.get("PORT", "8000") or 8000)
    host = os.environ.get("HOST", "0.0.0.0") or "0.0.0.0"
    mostrato = "127.0.0.1" if host == "0.0.0.0" else host
    sito = f"http://{mostrato}:{porta}/"

    print()
    print("  FreeSic - avvio del server...", flush=True)
    print(f"  {sito}", flush=True)
    if host == "0.0.0.0":
        for ip in indirizzi_rete():
            print(f"  Dal telefono: http://{ip}:{porta}/", flush=True)
    print(flush=True)
    try:
        prepara.PID_FILE.write_text(str(os.getpid()))
    except OSError:
        pass

    threading.Thread(target=apri_browser, args=(sito,), daemon=True).start()
    try:
        uvicorn.run(app, host=host, port=porta, log_level="info")
    finally:
        prepara.PID_FILE.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
