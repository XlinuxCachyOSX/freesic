"""Normalizzazione delle risposte di YouTube Music in dizionari semplici."""
import re

_ETICHETTE_TIPO = {
    "brano", "canzone", "song", "songs", "brani", "episodio", "puntata",
    "video", "album", "singolo", "single", "ep", "artista", "profilo",
    "playlist", "podcast", "audiolibro",
}

_TIPI_TITOLO = {
    "canzoni": "song", "brani": "song", "song": "song", "songs": "song",
    "video": "video", "videos": "video",
    "album": "album", "albums": "album",
    "singoli": "album", "single": "album", "singles": "album",
    "ep": "album", "eps": "album",
    "artisti": "artist", "artist": "artist", "artists": "artist",
    "profili": "profile", "profilo": "profile",
    "playlist": "playlist", "playlists": "playlist",
    "playlist della community": "playlist",
    "playlist in primo piano": "playlist",
    "podcast": "podcast", "podcasts": "podcast",
    "puntate": "episode", "episodi": "episode",
}

_TIPI_BROWSE = (
    ("MPREb", "album"),
    ("MPRE", "album"),
    ("MPED", "episode"),
    ("VLPL", "playlist"),
    ("VLRD", "playlist"),
    ("PL", "playlist"),
    ("MPSP", "podcast"),
    ("UC", "artist"),
)

_TITOLI_TIPO = {
    "song": "Canzoni",
    "video": "Video",
    "album": "Album",
    "artist": "Artisti",
    "profile": "Profili",
    "playlist": "Playlist",
    "podcast": "Podcast",
    "episode": "Puntate",
}


def _runs(node):
    """Estrae [{text, browseId, videoId}] da un nodo con .runs."""
    out = []
    if not isinstance(node, dict):
        return out
    for r in node.get("runs", []) or []:
        if not isinstance(r, dict):
            continue
        nav = r.get("navigationEndpoint", {}) or {}
        out.append({
            "text": r.get("text", ""),
            "browseId": (nav.get("browseEndpoint", {}) or {}).get("browseId"),
            "videoId": (nav.get("watchEndpoint", {}) or {}).get("videoId"),
        })
    return out


def _testo(node):
    return "".join(r["text"] for r in _runs(node)).strip()


def _campi(node):
    """Divide una colonna nei campi separati da ' • '."""
    campi = []
    for r in _runs(node):
        testo = r["text"].replace(" ", " ").strip()
        if not testo:
            continue
        if set(testo) <= {"•", "·", "-", " "} and len(testo) <= 3:
            continue
        campi.append({"testo": testo, "browseId": r["browseId"], "videoId": r["videoId"]})
    return campi


def _tipo_da_titolo(titolo):
    return _TIPI_TITOLO.get((titolo or "").strip().lower())


def _tipo_da_browse(browse_id):
    if not browse_id:
        return None
    for prefisso, tipo in _TIPI_BROWSE:
        if browse_id.startswith(prefisso):
            return tipo
    return None


def _durata_secondi(testo):
    if not testo:
        return None
    parti = testo.strip().split(":")
    if len(parti) < 2 or not all(p.isdigit() for p in parti):
        return None
    secondi = 0
    for p in parti:
        secondi = secondi * 60 + int(p)
    return secondi


def _conta(testo):
    """'1,8 Mln riproduzioni' -> 1800000."""
    m = re.search(r"([\d.,]+)\s*([KkMmBb])", (testo or "").replace(" ", " "))
    if not m:
        return None
    numero = float(m.group(1).replace(".", "").replace(",", "."))
    return int(numero * {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[m.group(2).lower()])


def _thumb(node):
    """Sceglie la miniatura più grande disponibile in un nodo thumbnail."""
    if not isinstance(node, dict):
        return None
    renderer = node.get("musicThumbnailRenderer") or node.get("thumbnailRenderer") or node
    thumbs = (renderer.get("thumbnail", {}) or {}).get("thumbnails", []) or []
    if not thumbs:
        return None
    return max(thumbs, key=lambda t: t.get("width", 0)).get("url")


def _video_id(item):
    pid = item.get("playlistItemData") or {}
    if pid.get("videoId"):
        return pid["videoId"]
    overlay = item.get("overlay", {}) or {}
    play = (overlay.get("musicItemThumbnailOverlayRenderer", {}) or {}).get("content", {}) or {}
    button = play.get("musicPlayButtonRenderer", {}) or {}
    nav = button.get("playNavigationEndpoint", {}) or {}
    if (nav.get("watchEndpoint", {}) or {}).get("videoId"):
        return nav["watchEndpoint"]["videoId"]
    nav = item.get("navigationEndpoint", {}) or {}
    if (nav.get("watchEndpoint", {}) or {}).get("videoId"):
        return nav["watchEndpoint"]["videoId"]
    for colonna in item.get("flexColumns", []) or []:
        for r in _runs((colonna.get("musicResponsiveListItemFlexColumnRenderer", {}) or {}).get("text")):
            if r["videoId"]:
                return r["videoId"]
    return None


def _browse_id(item):
    nav = item.get("navigationEndpoint", {}) or {}
    bid = (nav.get("browseEndpoint", {}) or {}).get("browseId")
    if bid:
        return bid
    for colonna in item.get("flexColumns", []) or []:
        for r in _runs((colonna.get("musicResponsiveListItemFlexColumnRenderer", {}) or {}).get("text")):
            if r["browseId"]:
                return r["browseId"]
    return None


def _fixed(item, indice):
    colonne = item.get("fixedColumns", []) or []
    if len(colonne) <= indice:
        return None
    r = colonne[indice].get("musicResponsiveListItemFixedColumnRenderer", {}) or {}
    return _testo(r.get("text")) or None


def parse_item(item, tipo=None, sezione=None):
    """Converte un musicResponsiveListItemRenderer in un dizionario uniforme."""
    if not isinstance(item, dict):
        return None
    colonne = item.get("flexColumns", []) or []
    titolo = ""
    secondari = []
    if colonne:
        titolo = _testo((colonne[0].get("musicResponsiveListItemFlexColumnRenderer", {}) or {}).get("text"))
    if len(colonne) > 1:
        secondari = _campi((colonne[1].get("musicResponsiveListItemFlexColumnRenderer", {}) or {}).get("text"))
    terzi = []
    if len(colonne) > 2:
        terzi = _campi((colonne[2].get("musicResponsiveListItemFlexColumnRenderer", {}) or {}).get("text"))

    video_id = _video_id(item)
    browse_id = (item.get("navigationEndpoint", {}) or {}).get("browseEndpoint", {}).get("browseId")
    if not browse_id and not video_id:
        browse_id = _browse_id(item)
    durata_testo = _fixed(item, 0)
    riproduzioni = _fixed(item, 1)

    if not tipo:
        tipo = "song" if video_id else (_tipo_da_browse(browse_id) or None)
    if tipo is None:
        etichetta = secondari[0]["testo"].lower() if secondari else ""
        tipo = "song" if etichetta in ("brano", "canzone", "song") else (
            "album" if etichetta in ("album", "singolo", "single", "ep") else (
                "artist" if etichetta in ("artista", "profilo") else (
                    "playlist" if etichetta == "playlist" else "album")))
    if tipo == "profile":
        tipo = "artist"

    def testo(campo):
        return campi[campo]["testo"] if len(campi) > campo else ""

    campi = secondari
    etichetta = None
    if campi and campi[0]["testo"].lower() in _ETICHETTE_TIPO:
        etichetta = campi[0]["testo"]
        campi = campi[1:]

    durata = durata_testo
    for c in campi:
        if _durata_secondi(c["testo"]):
            durata = c["testo"]
            break

    artisti = [c["testo"] for c in campi if (c["browseId"] or "").startswith("UC")]
    album = ""
    anno = ""
    ascoltatori = ""
    visualizzazioni = ""

    if tipo == "song":
        restanti = [c["testo"] for c in campi if not _durata_secondi(c["testo"])]
        if not artisti and restanti:
            artisti = [restanti[0]]
        for t in restanti:
            if not artisti or t != artisti[0]:
                album = t
                break
    elif tipo == "album":
        if not artisti:
            restanti = [c["testo"] for c in campi if not _durata_secondi(c["testo"])]
            if restanti:
                artisti = [restanti[0]]
        if len(campi) > 1:
            anno = campi[-1]["testo"]
    elif tipo == "artist":
        ascoltatori = testo(0)
    elif tipo in ("playlist", "episode", "podcast"):
        if len(campi) > 1 and campi[1]["testo"].lower().startswith(("visualizzazioni", "views", "ascolti")):
            visualizzazioni = campi[1]["testo"]

    if not durata and durata_testo is None:
        durata = None

    plays_testo = riproduzioni or (terzi[0]["testo"] if terzi else "")

    return {
        "id": video_id or browse_id,
        "type": tipo,
        "videoId": video_id,
        "browseId": browse_id,
        "title": titolo,
        "artists": [a for a in artisti if a],
        "artist": artisti[0] if artisti else "",
        "album": album,
        "year": anno,
        "subtitle": " • ".join(c["testo"] for c in campi),
        "duration": _durata_secondi(durata) if isinstance(durata, str) else durata,
        "durationText": durata if isinstance(durata, str) else None,
        "plays": _conta(plays_testo),
        "playsText": plays_testo or None,
        "listeners": ascoltatori or None,
        "views": visualizzazioni or None,
        "thumbnail": _thumb(item.get("thumbnail")),
        "section": sezione,
    }


def _items_shelf(shelf, tipo=None, sezione=None):
    out = []
    for entry in shelf.get("contents", []) or []:
        if not isinstance(entry, dict):
            continue
        r = entry.get("musicResponsiveListItemRenderer")
        if r:
            item = parse_item(r, tipo=tipo, sezione=sezione)
            if item and item["title"]:
                out.append(item)
    return out


def _titolo_shelf(shelf):
    """Titolo di uno scaffale: può stare in 'title' oppure in 'header'."""
    titolo = _testo(shelf.get("title"))
    if titolo:
        return titolo
    header = shelf.get("header", {}) or {}
    for chiave in ("musicCarouselShelfBasicHeaderRenderer", "musicShelfBasicHeaderRenderer"):
        if chiave in header:
            return _testo(header[chiave].get("title"))
    return ""


def _shelf_typed(shelf, sezione=None):
    titolo = _titolo_shelf(shelf)
    tipo = _tipo_da_titolo(titolo)
    return titolo, tipo, _items_shelf(shelf, tipo=tipo, sezione=sezione or titolo)


def parse_search(raw):
    """Estrae filtri e sezioni da una risposta di ricerca."""
    filtri = []
    sezioni = []
    piatti = []
    try:
        tabs = raw["contents"]["tabbedSearchResultsRenderer"]["tabs"]
    except (KeyError, TypeError):
        return {"filters": filtri, "sections": sezioni}

    for tab in tabs:
        contenuto = ((tab.get("tabRenderer", {}) or {}).get("content", {}) or {})
        lista = contenuto.get("sectionListRenderer", {}) or {}
        for sezione in lista.get("contents", []) or []:
            if not isinstance(sezione, dict):
                continue
            if "itemSectionRenderer" in sezione:
                for inner in sezione["itemSectionRenderer"].get("contents", []) or []:
                    if not isinstance(inner, dict):
                        continue
                    if "musicShelfRenderer" in inner:
                        titolo, tipo, items = _shelf_typed(inner["musicShelfRenderer"])
                        if items:
                            sezioni.append({"title": titolo, "type": tipo or "mixed", "items": items})
                    elif "musicResponsiveListItemRenderer" in inner:
                        item = parse_item(inner["musicResponsiveListItemRenderer"])
                        if item and item["title"]:
                            piatti.append(item)
                    elif "messageRenderer" in inner:
                        messaggio = _testo(inner["messageRenderer"].get("text"))
                        if messaggio:
                            sezioni.append({"title": "", "type": "message", "items": [], "message": messaggio})
            elif "musicCardShelfRenderer" in sezione:
                shelf = sezione["musicCardShelfRenderer"]
                titolo = _testo(shelf.get("title"))
                items = _items_shelf(shelf, sezione=titolo)
                if items:
                    sezioni.append({"title": titolo, "type": "mixed", "items": items})
            elif "musicShelfRenderer" in sezione:
                titolo, tipo, items = _shelf_typed(sezione["musicShelfRenderer"])
                if items:
                    sezioni.append({"title": titolo, "type": tipo or "mixed", "items": items})
            elif "musicPlaylistShelfRenderer" in sezione:
                shelf = sezione["musicPlaylistShelfRenderer"]
                titolo = _testo(shelf.get("title"))
                items = _items_shelf(shelf, sezione=titolo)
                if items:
                    sezioni.append({"title": titolo, "type": "playlist", "items": items})

    if piatti:
        gruppi = {}
        ordine = []
        for item in piatti:
            if item["type"] not in gruppi:
                gruppi[item["type"]] = []
                ordine.append(item["type"])
            gruppi[item["type"]].append(item)
        for tipo in ordine:
            sezioni.append({
                "title": _TITOLI_TIPO.get(tipo, "Risultati"),
                "type": tipo,
                "items": gruppi[tipo],
            })

    return {"filters": _chips(raw), "sections": sezioni}


def _chips(raw):
    """Filtri di ricerca (Tutto, Canzoni, Album...) con i loro parametri opachi."""
    trovati = []

    def walk(x):
        if isinstance(x, dict):
            if "chipCloudRenderer" in x:
                for chip in x["chipCloudRenderer"].get("chips", []) or []:
                    r = chip.get("chipCloudChipRenderer") or chip.get("searchFilterChipRenderer") or {}
                    testo = _testo(r.get("text"))
                    nav = r.get("navigationEndpoint", {}) or {}
                    params = (nav.get("searchEndpoint", {}) or {}).get("params")
                    if not params:
                        continue
                    trovati.append({"label": testo, "params": params, "selected": bool(r.get("isSelected"))})
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(raw)
    return trovati


def parse_browse(raw):
    """Estrae intestazione e tracce da album, playlist o artisti."""
    info = {"title": "", "subtitle": "", "thumbnail": None, "description": "",
            "items": [], "type": None, "shelves": []}
    visti = set()

    def walk(x):
        if isinstance(x, dict):
            if "musicResponsiveHeaderRenderer" in x and not info["title"]:
                h = x["musicResponsiveHeaderRenderer"]
                info["title"] = _testo(h.get("title"))
                info["subtitle"] = _testo(h.get("subtitle"))
                info["thumbnail"] = _thumb(h.get("thumbnail"))
                desc = h.get("description", {}) or {}
                info["description"] = _testo(desc.get("text")) if isinstance(desc, dict) else str(desc)
            if "musicDetailHeaderRenderer" in x and not info["title"]:
                h = x["musicDetailHeaderRenderer"]
                info["title"] = _testo(h.get("title"))
                info["subtitle"] = _testo(h.get("subtitle"))
                info["thumbnail"] = _thumb(h.get("thumbnail"))
            if "musicResponsiveListItemRenderer" in x:
                item = parse_item(x["musicResponsiveListItemRenderer"])
                if item and item["title"] and item["id"] not in visti:
                    visti.add(item["id"])
                    info["items"].append(item)
            if "musicShelfRenderer" in x:
                titolo, tipo, items = _shelf_typed(x["musicShelfRenderer"])
                if items:
                    info["shelves"].append({"title": titolo, "type": tipo or "mixed", "items": items})
            if "musicCarouselShelfRenderer" in x:
                titolo, tipo, items = _shelf_typed(x["musicCarouselShelfRenderer"])
                if items:
                    info["shelves"].append({"title": titolo, "type": tipo or "mixed", "items": items})
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(raw)
    if not info["type"]:
        info["type"] = "album"
    return info


def parse_home(raw):
    """Estrae le scaffali (shelves) della home."""
    shelves = []
    visti = set()

    def walk(x):
        if isinstance(x, dict):
            for chiave in ("musicShelfRenderer", "musicCarouselShelfRenderer"):
                if chiave in x:
                    titolo, tipo, items = _shelf_typed(x[chiave])
                    if items and titolo not in visti:
                        visti.add(titolo)
                        shelves.append({"title": titolo, "items": items})
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(raw)
    return {"shelves": shelves}
