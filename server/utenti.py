"""Account opzionali di FreeSic: registrazione, accesso e "mi piace".

Gli utenti sono salvati in locale (dati/utenti.json) con password hashed:
non serve alcun account YouTube e nulla lascia il computer. Le sessioni
sono token casuali tenuti su disco (dati/sessioni.json), cosi' l'accesso
resta valido anche riavviando il server; nel file viene salvato solo
l'hash del token, mai il token stesso.
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATI = os.path.join(BASE, "dati")
FILE_UTENTI = os.path.join(DATI, "utenti.json")
FILE_PIACI = os.path.join(DATI, "mi_piace.json")
FILE_SESSIONI = os.path.join(DATI, "sessioni.json")
COOKIE = "freesic_session"
DURATA_SESSIONE = 60 * 60 * 24 * 30  # 30 giorni
ITERAZIONI = 120_000


class ErroreUtente(Exception):
    """Errore di autenticazione o di dati non validi."""


# --------------------------------------------------------------------------
# Persistenza
# --------------------------------------------------------------------------
_lock = threading.RLock()
_sessioni: dict[str, tuple[str, float]] = {}


def _chiave_token(token: str) -> str:
    """Nel file viene salvato solo l'hash del token, non il token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _leggi(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _scrivi(path: str, dati: dict) -> None:
    os.makedirs(DATI, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _salva_sessioni() -> None:
    _scrivi(FILE_SESSIONI, {k: [v[0], v[1]] for k, v in _sessioni.items()})


def _carica_sessioni() -> None:
    """Rilegge le sessioni salvate: l'accesso resta valido dopo un riavvio."""
    with _lock:
        _sessioni.clear()
        ora = time.time()
        for chiave, voce in _leggi(FILE_SESSIONI).items():
            try:
                utente, scadenza = voce[0], float(voce[1])
            except (TypeError, ValueError, IndexError):
                continue
            if utente and scadenza > ora:
                _sessioni[chiave] = (str(utente), scadenza)


def _hash(password: str, sale: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sale, ITERAZIONI).hex()


# --------------------------------------------------------------------------
# Utenti
# --------------------------------------------------------------------------
def _utenti() -> dict:
    return _leggi(FILE_UTENTI)


def registra(nome: str, password: str) -> str:
    nome = (nome or "").strip()
    if len(nome) < 3:
        raise ErroreUtente("Il nome utente deve avere almeno 3 caratteri.")
    if len(password) < 4:
        raise ErroreUtente("La password deve avere almeno 4 caratteri.")
    with _lock:
        utenti = _utenti()
        if nome.lower() in utenti:
            raise ErroreUtente("Nome utente già in uso.")
        sale = secrets.token_bytes(16)
        utenti[nome.lower()] = {
            "nome": nome,
            "sale": sale.hex(),
            "hash": _hash(password, sale),
            "creato": time.time(),
        }
        _scrivi(FILE_UTENTI, utenti)
        _scrivi(FILE_PIACI, {**_leggi(FILE_PIACI), nome.lower(): []})
    return nome


def accedi(nome: str, password: str) -> str:
    nome = (nome or "").strip().lower()
    with _lock:
        utente = _utenti().get(nome)
        if not utente:
            raise ErroreUtente("Nome utente o password errati.")
        sale = bytes.fromhex(utente["sale"])
        if not hmac.compare_digest(_hash(password, sale), utente["hash"]):
            raise ErroreUtente("Nome utente o password errati.")
    return utente["nome"]


def token_sessione(utente: str) -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessioni[_chiave_token(token)] = (utente, time.time() + DURATA_SESSIONE)
        _salva_sessioni()
    return token


def utente_da_token(token: str | None) -> str | None:
    if not token:
        return None
    chiave = _chiave_token(token)
    with _lock:
        ora = time.time()
        scadute = [k for k, (_, scadenza) in _sessioni.items() if scadenza < ora]
        for k in scadute:
            _sessioni.pop(k, None)
        voce = _sessioni.get(chiave)
        if voce is None:
            if scadute:
                _salva_sessioni()
            return None
        # la scadenza scorre: chi usa l'app ogni giorno non viene sloggato
        if voce[1] - ora < DURATA_SESSIONE / 2:
            _sessioni[chiave] = (voce[0], ora + DURATA_SESSIONE)
            _salva_sessioni()
        return voce[0]


def chiudi_sessione(token: str | None) -> None:
    if not token:
        return
    with _lock:
        if _sessioni.pop(_chiave_token(token), None) is not None:
            _salva_sessioni()


# --------------------------------------------------------------------------
# Mi piace
# --------------------------------------------------------------------------
def _chiave(nome: str) -> str:
    return nome.strip().lower()


def piaciuti(nome: str) -> list:
    with _lock:
        return list(_leggi(FILE_PIACI).get(_chiave(nome), []))


def aggiungi_mi_piace(nome: str, brano: dict) -> list:
    video_id = (brano.get("videoId") or "").strip()
    if not video_id:
        raise ErroreUtente("Brano non valido.")
    with _lock:
        dati = _leggi(FILE_PIACI)
        lista = dati.get(_chiave(nome), [])
        if not any(x.get("videoId") == video_id for x in lista):
            lista.insert(0, {
                "videoId": video_id,
                "title": brano.get("title") or "",
                "artist": brano.get("artist") or "",
                "album": brano.get("album") or "",
                "thumbnail": brano.get("thumbnail") or "",
                "duration": brano.get("duration") or 0,
            })
        dati[_chiave(nome)] = lista
        _scrivi(FILE_PIACI, dati)
        return list(lista)


def rimuovi_mi_piace(nome: str, video_id: str) -> list:
    with _lock:
        dati = _leggi(FILE_PIACI)
        lista = [x for x in dati.get(_chiave(nome), []) if x.get("videoId") != video_id]
        dati[_chiave(nome)] = lista
        _scrivi(FILE_PIACI, dati)
        return list(lista)


def playlist_piaciuta(nome: str) -> dict:
    """Restituisce la playlist 'Piaciuta' nel formato usato dal frontend."""
    brani = piaciuti(nome)
    return {
        "browseId": f"freesic-piaciuta-{_chiave(nome)}",
        "title": "Piaciuta",
        "subtitle": f"{len(brani)} brani",
        "type": "playlist",
        "thumbnail": brani[0]["thumbnail"] if brani else "",
        "items": brani,
    }


# le sessioni vengono rilette all'avvio del server
_carica_sessioni()
