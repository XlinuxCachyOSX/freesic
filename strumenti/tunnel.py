"""Rende FreeSic raggiungibile da qualsiasi rete con un tunnel Cloudflare.

Avvia `cloudflared` in modalita' "quick tunnel": non serve account ne'
configurare il router, e l'indirizzo pubblico e' in HTTPS. Il programma
viene scaricato al primo uso nella cartella `.cloudflared` del progetto.

L'indirizzo cambia a ogni avvio: per averne uno fisso serve un account
Cloudflare con un dominio (vedi README).
"""

import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CARTELLA = BASE / ".cloudflared"
SCARICA = "https://github.com/cloudflare/cloudflared/releases/latest/download/"
INDIRIZZO = re.compile(r"https://[a-z0-9][a-z0-9-]*\.trycloudflare\.com", re.I)
ATTESA = 45


def _architettura() -> str:
    arch = platform.machine().lower()
    if arch in ("x86_64", "amd64", "x64"):
        return "amd64"
    if arch in ("aarch64", "arm64"):
        return "arm64"
    if arch.startswith("arm"):
        return "arm"
    return "amd64"


def _asset() -> tuple[str, str | None]:
    """(nome del file da scaricare, estensione da estrarre oppure None)."""
    sistema = platform.system().lower()
    arch = _architettura()
    if sistema == "windows":
        return "cloudflared-windows-amd64.exe", None
    if sistema == "darwin":
        return f"cloudflared-darwin-{arch}.tgz", ".tgz"
    return f"cloudflared-linux-{arch}", None


def _scarica(destinazione: Path) -> None:
    nome, archivio = _asset()
    CARTELLA.mkdir(parents=True, exist_ok=True)
    print(f"  Scarico cloudflared (una volta sola, ~40 MB)...", flush=True)
    temporaneo = CARTELLA / nome
    with urllib.request.urlopen(SCARICA + nome, timeout=120) as risposta:
        with open(temporaneo, "wb") as f:
            shutil.copyfileobj(risposta, f)
    if archivio == ".tgz":
        with tarfile.open(temporaneo, "r:gz") as pacchetto:
            pacchetto.extractall(CARTELLA)
        temporaneo.unlink(missing_ok=True)
        estratto = CARTELLA / "cloudflared"
        if estratto.exists():
            estratto.replace(destinazione)
    else:
        temporaneo.replace(destinazione)
    try:
        destinazione.chmod(0o755)
    except OSError:
        pass


def percorso_cloudflared() -> Path:
    """Usa cloudflared se e' gia' installato, altrimenti lo scarica."""
    trovato = shutil.which("cloudflared")
    if trovato:
        return Path(trovato)
    eseguibile = CARTELLA / ("cloudflared.exe" if os.name == "nt" else "cloudflared")
    if not eseguibile.exists():
        _scarica(eseguibile)
    return eseguibile


class Tunnel:
    """Avvia cloudflared e legge l'indirizzo pubblico dal suo output."""

    def __init__(self, porta: int):
        self.porta = porta
        self.url: str | None = None
        self.processo: subprocess.Popen | None = None

    def avvia(self) -> None:
        eseguibile = percorso_cloudflared()
        comando = [
            str(eseguibile),
            "tunnel",
            "--url", f"http://127.0.0.1:{self.porta}",
            "--no-autoupdate",
            "--protocol", "http2",
        ]
        self.processo = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self._leggi, daemon=True).start()

    def _leggi(self) -> None:
        if not self.processo or not self.processo.stdout:
            return
        for riga in self.processo.stdout:
            if self.url:
                continue
            trovato = INDIRIZZO.search(riga)
            if trovato:
                self.url = trovato.group(0)
                print()
                print(f"  Da qualsiasi rete: {self.url}/", flush=True)
                print(f"  (indirizzo valido finche' FreeSic resta acceso)", flush=True)
                print(flush=True)

    def aspetta(self, secondi: float = ATTESA) -> str | None:
        fine = time.time() + secondi
        while time.time() < fine and not self.url:
            if self.processo and self.processo.poll() is not None:
                return None
            time.sleep(0.3)
        return self.url

    def chiudi(self) -> None:
        if self.processo and self.processo.poll() is None:
            try:
                self.processo.terminate()
                self.processo.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    self.processo.kill()
                except OSError:
                    pass


def attivo() -> bool:
    return os.environ.get("TUNNEL", "").strip().lower() in ("1", "si", "sì", "true", "yes")


def main() -> int:
    porta = int((sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PORT", "8000")) or 8000)
    tunnel = Tunnel(porta)
    try:
        tunnel.avvia()
    except Exception as e:
        print(f"\n  Non riesco ad avviare il tunnel: {e}\n"
              "  Installa cloudflared a mano: sudo apt install cloudflared\n"
              "  (oppure brew install cloudflared).\n")
        return 1
    print("  Attendo l'indirizzo pubblico da Cloudflare...", flush=True)
    url = tunnel.aspetta()
    if not url:
        print("\n  Cloudflare non ha risposto. Controlla la connessione e riprova.\n")
        tunnel.chiudi()
        return 1
    print("  Apri questo indirizzo dal telefono (menu -> Indirizzo server):")
    print(f"  {url}/")
    print("\n  Ctrl+C per chiudere il tunnel.")
    try:
        while tunnel.processo and tunnel.processo.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        tunnel.chiudi()
    return 0


if __name__ == "__main__":
    sys.exit(main())
