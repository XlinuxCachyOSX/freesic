"""Avvia il server FreeSic e apre il browser.

Viene eseguito con il Python di sistema: prepara l'ambiente e poi riavvia
se stesso con l'interprete del virtualenv (dove vivono le dipendenze).
"""

import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import prepara  # noqa: E402


def main() -> int:
    porta = int(os.environ.get("PORT", "8000") or 8000)
    host = os.environ.get("HOST", "127.0.0.1") or "127.0.0.1"
    try:
        py, porta, host = prepara.prepara(porta, host)
    except SystemExit as e:
        print(f"\n  {e}\n")
        return 1
    servizio = Path(__file__).resolve().parent / "servizio.py"
    env = dict(os.environ, PORT=str(porta), HOST=host)
    if os.name == "nt":
        return subprocess.call([str(py), str(servizio)], env=env)
    os.execve(str(py), [str(py), str(servizio)], env)


if __name__ == "__main__":
    sys.exit(main())
