"""Risoluzione dello stream audio tramite yt-dlp (solo audio, nessun advertising)."""
import re
import threading

from .cache import TTLCache
from .innertube import UA


class AudioError(RuntimeError):
    """Errore durante la risoluzione di uno stream audio."""


_cache = TTLCache(ttl=240.0, maxsize=256)
_lock = threading.Lock()

_OPZIONI = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "skip_download": True,
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "http_headers": {"User-Agent": UA},
}


def _estrai(info):
    url = info.get("url")
    if not url:
        raise AudioError("nessuno stream audio disponibile")
    return {
        "videoId": info.get("id"),
        "url": url,
        "ext": info.get("ext", "m4a"),
        "mime": "audio/mp4" if info.get("ext") in ("m4a", "mp4") else "audio/webm",
        "duration": info.get("duration"),
        "title": info.get("title") or "",
        "artist": info.get("artist") or info.get("uploader") or "",
        "album": info.get("album") or "",
        "thumbnail": info.get("thumbnail") or f"https://i.ytimg.com/vi/{info.get('id')}/mqdefault.jpg",
        "headers": dict(info.get("http_headers") or {}),
    }


def resolve(video_id, force=False):
    """Restituisce {url, mime, ...} per lo stream audio di un video.

    Il risultato viene messo in cache: gli URL di googlevideo valgono per ore,
    la cache serve a non risolvere lo stesso brano a ogni richiesta.
    """
    video_id = video_id.strip()
    if not video_id:
        raise AudioError("id mancante")
    if not force:
        in_cache = _cache.get(video_id)
        if in_cache:
            return in_cache

    try:
        import yt_dlp
    except ImportError as e:
        raise AudioError("yt-dlp non installato: pip install -r requirements.txt") from e

    with _lock:
        with yt_dlp.YoutubeDL(_OPZIONI) as ydl:
            try:
                info = ydl.extract_info(f"https://music.youtube.com/watch?v={video_id}",
                                        download=False)
            except Exception as e:
                raise AudioError(f"risoluzione fallita: {e}") from e
    if info.get("_type") == "playlist":
        voci = [e for e in (info.get("entries") or []) if e]
        if not voci:
            raise AudioError("playlist vuota")
        info = voci[0]

    dato = _estrai(info)
    _cache.set(video_id, dato)
    return dato


_SUFFISSI = (
    "official video", "official music video", "official audio", "official lyric video",
    "official visualizer", "music video", "lyric video", "lyrics", "audio", "visualizer",
    "hd", "hq", "4k", "mv", "m/v", "full album", "explicit", "remastered",
)

_TITOLO_SEP = re.compile(r"\s+[-–—]\s+")


def _split_artista(testo):
    """Divide 'Artista - Brano' solo se il separatore è fuori dalle parentesi."""
    profondita = 0
    for i in range(len(testo) - 2):
        ch = testo[i]
        if ch in "([":
            profondita += 1
        elif ch in ")]":
            profondita -= 1
        elif profondita == 0 and testo[i:i + 3] in (" - ", " – ", " — "):
            return testo[:i].strip(), testo[i + 3:].strip()
    return "", ""


def _titolo_pulito(titolo, artista=""):
    """Ripulisce il titolo del video: 'Artista - Brano (Official Video)' -> ('Brano', 'Artista')."""
    testo = (titolo or "").strip()

    def _gruppo(m):
        interno = m.group(2).strip().lower()
        if any(interno == s or interno.startswith(s + " ") for s in _SUFFISSI):
            return " "
        return m.group(0)

    testo = re.sub(r"([\(\[])([^()\[\]]+)([\)\]])", _gruppo, testo)
    testo = re.sub(r"\s*[-–—]?\s*(" + "|".join(re.escape(s) for s in _SUFFISSI) + r")\s*$", "",
                   testo, flags=re.IGNORECASE)
    testo = re.sub(r"\s{2,}", " ", testo).strip(" -–—([|")

    sinistra, destra = _split_artista(testo)
    if artista:
        if sinistra and sinistra.lower() == artista.lower():
            testo = destra
    elif sinistra and destra and len(sinistra) <= 60:
        artista, testo = sinistra, destra
    return testo, artista


def metadati(video_id):
    """Solo i metadati del brano (titolo, artista, copertina, durata)."""
    info = resolve(video_id)
    titolo, artista = _titolo_pulito(info["title"], info.get("artist") or "")
    return {
        "videoId": info["videoId"],
        "title": titolo or info["title"],
        "artist": artista or info["artist"],
        "album": info["album"],
        "thumbnail": info["thumbnail"],
        "duration": info["duration"],
        "rawTitle": info["title"],
    }
