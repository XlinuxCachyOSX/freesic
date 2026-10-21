"""Client minimale dell'API interna di YouTube Music (client WEB_REMIX).

Nessun pacchetto esterno oltre httpx: si parla direttamente con
https://music.youtube.com/youtubei/v1/ (search, browse).

YouTube risponde a raffica con 400 "Precondition check failed": qui il client
limita la frequenza delle chiamate, riusa il visitorData e ritenta con attesa.
"""
import threading
import time

import httpx

API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
BASE = "https://music.youtube.com/youtubei/v1"
CLIENT_VERSION = "1.20241010.01.00"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Content-Type": "application/json",
    "Origin": "https://music.youtube.com",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "X-YouTube-Client-Name": "67",
    "X-YouTube-Client-Version": CLIENT_VERSION,
}

INTERVALLO = 1.1          # secondi minimi fra due chiamate
TENTATIVI = 5
PAUSE = (2.0, 4.0, 8.0, 12.0)

_lock = threading.Lock()
_ultima = 0.0
_visitor = None


class InnertubeError(RuntimeError):
    """Errore restituito dall'API interna di YouTube Music."""


def _throttled():
    """Attende per non superare la frequenza consentita."""
    global _ultima
    with _lock:
        attesa = INTERVALLO - (time.monotonic() - _ultima)
        if attesa > 0:
            time.sleep(attesa)
        _ultima = time.monotonic()


def context(hl="it", gl="IT"):
    ctx = {
        "client": {
            "clientName": "WEB_REMIX",
            "clientVersion": CLIENT_VERSION,
            "hl": hl,
            "gl": gl,
        },
        "user": {"lockedSafetyMode": False},
        "request": {"useSsl": True},
    }
    if _visitor:
        ctx["visitorData"] = _visitor
    return {"context": ctx}


def _memorizza_visitor(dati):
    global _visitor
    try:
        visit = ((dati or {}).get("responseContext") or {}).get("visitorData")
    except AttributeError:
        visit = None
    if visit:
        _visitor = visit


def post(endpoint, payload, timeout=25.0):
    """Esegue una chiamata POST a /youtubei/v1/<endpoint> e restituisce il JSON."""
    url = f"{BASE}/{endpoint}?key={API_KEY}&prettyPrint=false"
    errore = None
    for tentativo in range(TENTATIVI):
        _throttled()
        headers = dict(HEADERS)
        if _visitor:
            headers["X-Goog-Visitor-Id"] = _visitor
        try:
            r = httpx.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 200:
                dati = r.json()
                _memorizza_visitor(dati)
                return dati
            errore = f"HTTP {r.status_code}"
            if r.status_code not in (400, 429, 500, 502, 503):
                break
        except (httpx.HTTPError, ValueError) as e:
            errore = f"{type(e).__name__}: {e}"
        if tentativo < TENTATIVI - 1:
            time.sleep(PAUSE[min(tentativo, len(PAUSE) - 1)])
    raise InnertubeError(f"chiamata a {endpoint} fallita ({errore})")


def search(query, params=None, hl="it"):
    """Ricerca testuale. `params` è il filtro opaco restituito dall'API."""
    payload = context(hl)
    payload["query"] = query
    if params:
        payload["params"] = params
    return post("search", payload)


def browse(browse_id, params=None, hl="it"):
    """Apre album (MPREb_...), playlist (VLPL/PL...) o artisti (UC...)."""
    payload = context(hl)
    payload["browseId"] = browse_id
    if params:
        payload["params"] = params
    return post("browse", payload)


def home(hl="it"):
    """Restituisce la home di YouTube Music (shelves di album e playlist)."""
    payload = context(hl)
    payload["browseId"] = "FEmusic_home"
    return post("browse", payload)
