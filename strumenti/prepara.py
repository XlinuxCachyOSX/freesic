"""Prepara l'ambiente di FreeSic: virtualenv, pip, dipendenze, porta libera.

Viene eseguito con il Python di sistema e restituisce l'interprete del
virtualenv cosi' che il server possa essere avviato con le dipendenze
installate. Il codice e' identico su Linux, macOS e Windows.
"""

import os
import shutil
import subprocess
import sys
import urllib.request
import venv
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
VENV = BASE / ".venv"
REQUISITES = BASE / "requirements.txt"
PID_FILE = BASE / ".freesic.pid"
TENTATIVI_PORTA = 20
MODULI = ("uvicorn", "fastapi", "yt_dlp")
VERSIONE_MINIMA = (3, 10)


def messaggio(testo: str) -> None:
    print(testo, flush=True)


def percorso_python_venv(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def esiste_pip(py: Path) -> bool:
    try:
        subprocess.run([str(py), "-m", "pip", "--version"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def ci_sono_moduli(py: Path) -> bool:
    codice = "import " + ", ".join(MODULI)
    try:
        subprocess.run([str(py), "-c", codice],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def crea_venv(py: Path) -> None:
    messaggio("  Creo l'ambiente virtuale (una volta sola)...")
    try:
        venv.EnvBuilder(with_pip=True, clear=True).create(str(VENV))
    except Exception:
        # ensurepip manca (Debian senza python3-venv): si crea senza pip
        shutil.rmtree(VENV, ignore_errors=True)
        venv.EnvBuilder(with_pip=False, clear=True).create(str(VENV))


def assicura_pip(py: Path) -> None:
    if esiste_pip(py):
        return
    messaggio("  Preparo pip nell'ambiente virtuale...")
    subprocess.run([str(py), "-m", "ensurepip", "--upgrade"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if esiste_pip(py):
        return
    # ultimo tentativo: pip di sistema installato dentro il venv
    try:
        site = subprocess.run(
            [str(py), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
            capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        site = ""
    if site:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "--target", site, "pip"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if esiste_pip(py):
            return
    # pip scaricato dal bootstrap ufficiale
    messaggio("  pip non presente: lo scarico (get-pip.py)...")
    script = BASE / ".get-pip.py"
    try:
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", script)
        subprocess.run([str(py), str(script)], check=False)
    except Exception:
        pass
    finally:
        script.unlink(missing_ok=True)


def assicura_dipendenze(py: Path) -> None:
    if ci_sono_moduli(py):
        return
    messaggio("  Installo le dipendenze necessarie...")
    subprocess.run([str(py), "-m", "pip", "install", "--upgrade", "pip"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    try:
        subprocess.run([str(py), "-m", "pip", "install", "-r", str(REQUISITES)], check=True)
    except subprocess.CalledProcessError:
        raise SystemExit(
            "Installazione delle dipendenze fallita. Controlla la connessione e riprova:\n"
            f"  {py} -m pip install -r {REQUISITES}"
        )


def processo_vivo(pid: int) -> bool:
    if os.name == "nt":
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                 capture_output=True, text=True, check=False).stdout
            return str(pid) in out
        except OSError:
            return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def termina(pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            os.kill(pid, 15)
    except OSError:
        pass


def chiudi_istanza_precedente() -> None:
    """Chiude una nostra precedente istancora attiva (stesso progetto)."""
    if not PID_FILE.exists():
        return
    try:
        pid = int(PID_FILE.read_text().strip())
    except (OSError, ValueError):
        PID_FILE.unlink(missing_ok=True)
        return
    PID_FILE.unlink(missing_ok=True)
    if pid and pid != os.getpid() and processo_vivo(pid):
        messaggio(f"  Chiudo l'istanza precedente (pid {pid}).")
        termina(pid)


def porta_libera(porta: int, host: str) -> bool:
    """True se la porta e' davvero libera.

    Su Windows SO_REUSEADDR permette a due socket di usare la stessa porta,
    quindi si usa SO_EXCLUSIVEADDRUSE per un controllo affidabile.
    """
    import socket
    s = socket.socket()
    try:
        if os.name == "nt":
            esclusivo = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
            if esclusivo is not None:
                s.setsockopt(socket.SOL_SOCKET, esclusivo, 1)
        else:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, porta))
        return True
    except OSError:
        return False
    finally:
        s.close()


def scegli_porta(porta: int, host: str) -> int:
    for candidata in range(porta, porta + TENTATIVI_PORTA):
        if porta_libera(candidata, host):
            return candidata
    raise SystemExit(
        f"Nessuna porta libera da {porta} a {porta + TENTATIVI_PORTA - 1}. "
        "Chiudi le altre istanze e riprova."
    )


def prepara(porta: int = 8000, host: str = "0.0.0.0") -> tuple[Path, int, str]:
    """Prepara tutto e restituisce (interprete venv, porta, host)."""
    if sys.version_info < VERSIONE_MINIMA:
        raise SystemExit(
            f"Servono Python {VERSIONE_MINIMA[0]}.{VERSIONE_MINIMA[1]} o successivo "
            f"(questo e' Python {sys.version_info.major}.{sys.version_info.minor})."
        )
    py = percorso_python_venv(VENV)
    if not py.exists():
        crea_venv(py)
    if not py.exists():
        raise SystemExit("Non riesco a creare l'ambiente virtuale. Installa python3-venv.")
    assicura_pip(py)
    if not esiste_pip(py):
        raise SystemExit(
            "pip non e' disponibile. Installa le dipendenze con:\n"
            f"  {py} -m pip install -r {REQUISITES}"
        )
    assicura_dipendenze(py)
    if not ci_sono_moduli(py):
        raise SystemExit(f"Dipendenze mancanti. Esegui: {py} -m pip install -r {REQUISITES}")

    # chiude una nostra istanza precedente, cosi' la porta torna libera
    chiudi_istanza_precedente()
    scelta = scegli_porta(porta, host)
    if scelta != porta:
        messaggio(f"  La porta {porta} e' occupata: uso la porta {scelta}.")
    return py, scelta, host
