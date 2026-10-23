"""API del player musicale: ricerca, album, playlist e stream audio senza pubblicità."""
import asyncio
import os
import threading
import time

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import audio, innertube, parse, utenti
from .cache import TTLCache

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(BASE, "web")

app = FastAPI(title="FreeSic", version="1.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

_cache_ricerca = TTLCache(ttl=180.0, maxsize=128)
_cache_browse = TTLCache(ttl=900.0, maxsize=256)
_cache_home = TTLCache(ttl=300.0, maxsize=8)

UA = innertube.UA


@app.get("/api/health")
async def health():
    return {"ok": True, "servizio": "player musicale", "versione": app.version}


@app.get("/api/search")
async def ricerca(q: str = Query(..., min_length=1), params: str | None = None):
    chiave = f"{q.strip().lower()}|{params or ''}"
    in_cache = _cache_ricerca.get(chiave)
    if in_cache:
        return in_cache
    try:
        raw = await asyncio.to_thread(innertube.search, q, params)
    except innertube.InnertubeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    dati = parse.parse_search(raw)
    dati["query"] = q
    _cache_ricerca.set(chiave, dati)
    return dati


@app.get("/api/home")
async def home():
    in_cache = _cache_home.get("home")
    if in_cache:
        return in_cache
    try:
        raw = await asyncio.to_thread(innertube.home)
    except innertube.InnertubeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    dati = parse.parse_home(raw)
    _cache_home.set("home", dati)
    return dati


@app.get("/api/browse/{browse_id}")
async def browse(browse_id: str):
    browse_id = browse_id.strip()
    if not browse_id:
        raise HTTPException(status_code=400, detail="browse_id mancante")
    in_cache = _cache_browse.get(browse_id)
    if in_cache:
        return in_cache
    try:
        raw = await asyncio.to_thread(innertube.browse, browse_id)
    except innertube.InnertubeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    dati = parse.parse_browse(raw)
    dati["browseId"] = browse_id
    _cache_browse.set(browse_id, dati)
    return dati


@app.get("/api/track/{video_id}")
async def track(video_id: str):
    try:
        return await asyncio.to_thread(audio.metadati, video_id)
    except audio.AudioError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/stream/{video_id}")
async def stream(video_id: str, request: Request):
    """Invia l'audio al browser; supporta Range per la ricerca (seek)."""
    try:
        info = await asyncio.to_thread(audio.resolve, video_id)
    except audio.AudioError as e:
        raise HTTPException(status_code=502, detail=str(e))

    headers = {"User-Agent": UA, "Accept": "*/*"}
    richiesta = request.headers.get("range")
    if richiesta:
        headers["Range"] = richiesta

    client = httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(30.0, read=60.0))
    try:
        risposta = await client.send(client.build_request("GET", info["url"], headers=headers), stream=True)
    except httpx.HTTPError as e:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"stream non raggiungibile: {e}")

    async def genera():
        try:
            async for blocco in risposta.aiter_bytes(65536):
                yield blocco
        finally:
            await risposta.aclose()
            await client.aclose()

    uscita = {
        "Content-Type": info["mime"],
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=600",
    }
    for chiave in ("content-range", "content-length"):
        valore = risposta.headers.get(chiave)
        if valore:
            uscita[chiave.title()] = valore
    return StreamingResponse(genera(), status_code=risposta.status_code, headers=uscita)


@app.get("/api/image")
async def immagine(u: str = Query(...)):
    """Proxy delle copertine (evita problemi di hotlink e mixed content)."""
    if not u.startswith("https://"):
        raise HTTPException(status_code=400, detail="url non valido")
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            r = await client.get(u, headers={"User-Agent": UA})
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"immagine non raggiungibile: {e}")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="immagine non disponibile")
    return Response(content=r.content, media_type=r.headers.get("content-type", "image/jpeg"),
                    headers={"Cache-Control": "public, max-age=86400"})


# --------------------------------------------------------------------------
# Account opzionale e "mi piace"
# --------------------------------------------------------------------------
def _utente(request: Request) -> str:
    utente = utenti.utente_da_token(request.cookies.get(utenti.COOKIE))
    if not utente:
        raise HTTPException(status_code=401, detail="Devi accedere con un account.")
    return utente


def _cookie_sessione(token: str) -> str:
    return (f"{utenti.COOKIE}={token}; Path=/; Max-Age={utenti.DURATA_SESSIONE}; "
            "HttpOnly; SameSite=Lax")


@app.get("/api/auth/me")
async def chi_sono(request: Request):
    utente = utenti.utente_da_token(request.cookies.get(utenti.COOKIE))
    return {"autenticato": bool(utente), "utente": utente or ""}


@app.post("/api/auth/register")
async def registra(request: Request, response: Response):
    dati = await _corpo(request)
    try:
        nome = utenti.registra(dati.get("username", ""), dati.get("password", ""))
    except utenti.ErroreUtente as e:
        raise HTTPException(status_code=400, detail=str(e))
    token = utenti.token_sessione(nome)
    response.set_cookie(utenti.COOKIE, token, httponly=True, samesite="lax", max_age=utenti.DURATA_SESSIONE)
    return {"autenticato": True, "utente": nome}


_blocco_tentativi = threading.Lock()
_tentativi: dict[str, list[float]] = {}
_MAX_TENTATIVI = 6
_FINESTRA = 300


def _blocca_troppi_tentativi(chiave: str) -> None:
    """Freno ai tentativi ripetuti di accesso (utile se il server e' pubblico)."""
    ora = time.time()
    with _blocco_tentativi:
        recenti = [t for t in _tentativi.get(chiave, []) if ora - t < _FINESTRA]
        _tentativi[chiave] = recenti
        if len(recenti) >= _MAX_TENTATIVI:
            raise HTTPException(
                status_code=429,
                detail="Troppi tentativi falliti: riprova tra qualche minuto.",
            )


@app.post("/api/auth/login")
async def accedi(request: Request, response: Response):
    dati = await _corpo(request)
    chiave = f"{request.client.host if request.client else '?'}|{str(dati.get('username', '')).strip().lower()}"
    _blocca_troppi_tentativi(chiave)
    try:
        nome = utenti.accedi(dati.get("username", ""), dati.get("password", ""))
    except utenti.ErroreUtente as e:
        with _blocco_tentativi:
            _tentativi.setdefault(chiave, []).append(time.time())
        raise HTTPException(status_code=401, detail=str(e))
    with _blocco_tentativi:
        _tentativi.pop(chiave, None)
    token = utenti.token_sessione(nome)
    response.set_cookie(utenti.COOKIE, token, httponly=True, samesite="lax", max_age=utenti.DURATA_SESSIONE)
    return {"autenticato": True, "utente": nome}


@app.post("/api/auth/logout")
async def esci(request: Request, response: Response):
    utenti.chiudi_sessione(request.cookies.get(utenti.COOKIE))
    response.delete_cookie(utenti.COOKIE)
    return {"autenticato": False, "utente": ""}


@app.get("/api/mipiace")
async def lista_mi_piace(request: Request):
    utente = _utente(request)
    return {"items": utenti.piaciuti(utente)}


@app.post("/api/mipiace")
async def aggiungi_mi_piace(request: Request):
    utente = _utente(request)
    dati = await _corpo(request)
    try:
        lista = utenti.aggiungi_mi_piace(utente, dati)
    except utenti.ErroreUtente as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"items": lista}


@app.delete("/api/mipiace/{video_id}")
async def rimuovi_mi_piace(video_id: str, request: Request):
    utente = _utente(request)
    return {"items": utenti.rimuovi_mi_piace(utente, video_id)}


@app.get("/api/playlist/piaciuta")
async def playlist_piaciuta(request: Request):
    utente = _utente(request)
    return utenti.playlist_piaciuta(utente)


async def _corpo(request: Request) -> dict:
    try:
        dati = await request.json()
    except Exception:
        return {}
    return dati if isinstance(dati, dict) else {}


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
