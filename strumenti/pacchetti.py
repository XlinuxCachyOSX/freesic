"""Crea i pacchetti zip distribuibili per Linux, Windows e macOS.

Dentro ci finisce solo quello che serve per usare FreeSic: il server, la
web app, gli script di avvio e i requisiti. Non finiscono i test, gli
strumenti di sviluppo, l'APK o la cartella Android.

Uso:  python strumenti/pacchetti.py
"""
import os
import stat
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DEST = BASE / "dist"
VERSIONE = "1.0.0"

CONTENUTI = [
    "server",
    "web",
    "requirements.txt",
    "README.md",
    ".gitignore",
]
STRUMENTI = ["__init__.py", "avvia.py", "prepara.py", "servizio.py"]


def raccogli(piattaforma: str) -> list:
    """Elenco (percorso dentro lo zip, percorso sorgente, eseguibile)."""
    voci = []
    for cartella in CONTENUTI:
        sorgente = BASE / cartella
        if sorgente.is_dir():
            for file in sorted(sorgente.rglob("*")):
                if file.is_dir() or "__pycache__" in file.parts:
                    continue
                voci.append((file.relative_to(BASE).as_posix(), file, False))
        else:
            voci.append((cartella, sorgente, False))
    for nome in STRUMENTI:
        voci.append((f"strumenti/{nome}", BASE / "strumenti" / nome, False))
    if piattaforma == "windows":
        voci.append(("start.bat", BASE / "start.bat", False))
    else:
        voci.append(("start.sh", BASE / "start.sh", True))
    return voci


def crea_zip(piattaforma: str) -> Path:
    prefisso = f"FreeSic-{VERSIONE}-{piattaforma}"
    destinazione = DEST / f"{prefisso}.zip"
    DEST.mkdir(exist_ok=True)
    with zipfile.ZipFile(destinazione, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, sorgente, eseguibile in raccogli(piattaforma):
            if not sorgente.exists():
                continue
            dati = sorgente.read_bytes()
            if nome.endswith(".bat"):
                # cmd.exe vuole fine-riga CRLF
                dati = dati.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            info = zipfile.ZipInfo(f"{prefisso}/{nome}")
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            if eseguibile:
                info.external_attr = (stat.S_IFREG | 0o755) << 16
            else:
                info.external_attr = (stat.S_IFREG | 0o644) << 16
            z.writestr(info, dati)
    return destinazione


def main() -> int:
    for piattaforma in ("linux", "windows", "macos"):
        zip_ = crea_zip(piattaforma)
        print(f"  {zip_.name}  ({zip_.stat().st_size} byte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
