"""API del player musicale: ricerca, album, playlist e stream audio senza pubblicità."""
import asyncio
import os

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import audio, innertube, parse
from .cache import TTLCache

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(BASE, "web")

app = FastAPI(title="Player musicale", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

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


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
