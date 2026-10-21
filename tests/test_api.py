"""Test dell'API del player musicale.

I test non contattano YouTube: il client Innertube e il risolutore audio
vengono sostituiti con stub, così la suite resta veloce e deterministica.
"""
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from server import audio, innertube, main, parse

# --------------------------------------------------------------------------
# Fixture: risposte grezze minimali ma realistiche di YouTube Music
# --------------------------------------------------------------------------

ITEM_CANZONE = {
    "thumbnail": {"musicThumbnailRenderer": {"thumbnail": {"thumbnails": [
        {"url": "https://lh3.example/1.jpg", "width": 60, "height": 60}]}}},
    "flexColumns": [
        {"musicResponsiveListItemFlexColumnRenderer": {"text": {"runs": [
            {"text": "One More Time"}]}}},
        {"musicResponsiveListItemFlexColumnRenderer": {"text": {"runs": [
            {"text": "Brano"}, {"text": " • "},
            {"text": "Daft Punk", "navigationEndpoint": {"browseEndpoint": {"browseId": "UCabc"}}}]}}},
        {"musicResponsiveListItemFlexColumnRenderer": {"text": {"runs": [
            {"text": "100 Mln riproduzioni"}]}}},
    ],
    "playlistItemData": {"videoId": "FGBhQbmPwH8"},
}

ITEM_ALBUM = {
    "thumbnail": {"musicThumbnailRenderer": {"thumbnail": {"thumbnails": [
        {"url": "https://lh3.example/alb.jpg", "width": 60, "height": 60}]}}},
    "flexColumns": [
        {"musicResponsiveListItemFlexColumnRenderer": {"text": {"runs": [
            {"text": "Discovery"}]}}},
        {"musicResponsiveListItemFlexColumnRenderer": {"text": {"runs": [
            {"text": "Album"}, {"text": " • "},
            {"text": "Daft Punk", "navigationEndpoint": {"browseEndpoint": {"browseId": "UCabc"}}},
            {"text": " • "}, {"text": "2001"}]}}},
    ],
    "navigationEndpoint": {"browseEndpoint": {"browseId": "MPREb_7ltM34kr0mH"}},
}

SEARCH_RAW = {
    "contents": {
        "tabbedSearchResultsRenderer": {
            "tabs": [
                {
                    "tabRenderer": {
                        "content": {
                            "sectionListRenderer": {
                                "contents": [
                                    {
                                        "itemSectionRenderer": {
                                            "contents": [
                                                {
                                                    "musicShelfRenderer": {
                                                        "title": {"runs": [{"text": "Canzoni"}]},
                                                        "contents": [{"musicResponsiveListItemRenderer": ITEM_CANZONE}],
                                                    }
                                                },
                                                {"musicResponsiveListItemRenderer": ITEM_ALBUM},
                                            ]
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            ]
        }
    },
    "chipCloudRenderer": {"chips": [
        {"chipCloudChipRenderer": {
            "text": {"runs": [{"text": "Canzoni"}]},
            "navigationEndpoint": {"searchEndpoint": {"params": "EgWKAQIYAWoKEAkQBRAKEAMQBA%3D%3D"}}}},
        {"chipCloudChipRenderer": {
            "text": {"runs": [{"text": "Album"}]},
            "navigationEndpoint": {"searchEndpoint": {"params": "EgWKAQIYAWoKEAkQBRAQ"}}}},
    ]},
}

BROWSE_RAW = {
    "header": {"musicResponsiveHeaderRenderer": {
        "title": {"runs": [{"text": "Discovery"}]},
        "subtitle": {"runs": [{"text": "Album"}, {"text": " • "}, {"text": "2001"}]},
        "thumbnail": {"musicThumbnailRenderer": {"thumbnail": {"thumbnails": [
            {"url": "https://lh3.example/alb.jpg", "width": 60, "height": 60}]}}},
    }},
    "contents": {"musicShelfRenderer": {"contents": [
        {"musicResponsiveListItemRenderer": ITEM_CANZONE}]}},
}

HOME_RAW = {
    "contents": {
        "singleColumnBrowseResultsRenderer": {
            "tabs": [
                {
                    "tabRenderer": {
                        "content": {
                            "sectionListRenderer": {
                                "contents": [
                                    {
                                        "musicCarouselShelfRenderer": {
                                            "header": {"musicCarouselShelfBasicHeaderRenderer": {
                                                "title": {"runs": [{"text": "Scelte rapide"}]}}},
                                            "contents": [{"musicResponsiveListItemRenderer": ITEM_CANZONE}],
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            ]
        }
    }
}

# --------------------------------------------------------------------------
# Server locale che supporta Range, usato per testare lo streaming
# --------------------------------------------------------------------------

PAYLOAD = bytes(range(256)) * 40  # 10 KB circa


class RangeHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            inizio, _, fine = rng[6:].partition("-")
            inizio = int(inizio or 0)
            fine = int(fine) if fine else len(PAYLOAD) - 1
            fine = min(fine, len(PAYLOAD) - 1)
            corpo = PAYLOAD[inizio:fine + 1]
            self.send_response(206)
            self.send_header("Content-Type", "audio/mp4")
            self.send_header("Content-Range", f"bytes {inizio}-{fine}/{len(PAYLOAD)}")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "audio/mp4")
            self.send_header("Content-Length", str(len(PAYLOAD)))
            self.end_headers()
            self.wfile.write(PAYLOAD)


class TestParsing(unittest.TestCase):
    def test_titolo_pulito_rimuove_etichette(self):
        casi = [
            ("Daft Punk - One More Time (Official Video)", "", ("One More Time", "Daft Punk")),
            ("Instant Crush (feat. Julian Casablancas)", "", ("Instant Crush (feat. Julian Casablancas)", "")),
            ("Discovery (Remastered 2011)", "", ("Discovery", "")),
            ("Firenze (feat. Maya Jane Coles) [4K]", "", ("Firenze (feat. Maya Jane Coles)", "")),
            ("Daft Punk - One More Time (Official Video)", "Daft Punk", ("One More Time", "Daft Punk")),
        ]
        for titolo, artista, atteso in casi:
            with self.subTest(titolo=titolo):
                self.assertEqual(audio._titolo_pulito(titolo, artista), atteso)

    def test_parse_search_estrae_scaffali_e_filtri(self):
        dati = parse.parse_search(SEARCH_RAW)
        titoli = [s["title"] for s in dati["sections"]]
        self.assertIn("Canzoni", titoli)
        self.assertIn("Album", titoli)
        canzoni = next(s for s in dati["sections"] if s["title"] == "Canzoni")
        brano = canzoni["items"][0]
        self.assertEqual(brano["videoId"], "FGBhQbmPwH8")
        self.assertEqual(brano["title"], "One More Time")
        self.assertEqual(brano["artist"], "Daft Punk")
        self.assertEqual(brano["plays"], 100_000_000)
        album = next(s for s in dati["sections"] if s["title"] == "Album")
        self.assertEqual(album["items"][0]["browseId"], "MPREb_7ltM34kr0mH")
        self.assertEqual(album["items"][0]["type"], "album")
        self.assertEqual(len(dati["filters"]), 2)
        self.assertEqual(dati["filters"][0]["label"], "Canzoni")

    def test_parse_browse_estrae_titolo_e_tracce(self):
        dati = parse.parse_browse(BROWSE_RAW)
        self.assertEqual(dati["title"], "Discovery")
        self.assertIn("Album", dati["subtitle"])
        self.assertEqual(dati["thumbnail"], "https://lh3.example/alb.jpg")
        self.assertEqual(len(dati["items"]), 1)
        self.assertEqual(dati["items"][0]["videoId"], "FGBhQbmPwH8")

    def test_parse_home_estrae_titolo_dello_scaffale(self):
        dati = parse.parse_home(HOME_RAW)
        self.assertEqual(len(dati["shelves"]), 1)
        self.assertEqual(dati["shelves"][0]["title"], "Scelte rapide")
        self.assertEqual(dati["shelves"][0]["items"][0]["title"], "One More Time")

    def test_parse_item_tipi_e_durata(self):
        item = parse.parse_item(ITEM_ALBUM)
        self.assertEqual(item["type"], "album")
        self.assertEqual(item["artist"], "Daft Punk")
        self.assertEqual(item["year"], "2001")


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def setUp(self):
        main._cache_ricerca.clear()
        main._cache_browse.clear()
        main._cache_home.clear()

    def test_health(self):
        r = self.client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_search(self):
        with mock.patch.object(innertube, "search", return_value=SEARCH_RAW) as m:
            r = self.client.get("/api/search", params={"q": "daft punk"})
        self.assertEqual(r.status_code, 200)
        dati = r.json()
        self.assertEqual(dati["query"], "daft punk")
        self.assertTrue(dati["sections"])
        self.assertTrue(dati["filters"])
        m.assert_called_once_with("daft punk", None)

    def test_search_con_filtro(self):
        with mock.patch.object(innertube, "search", return_value=SEARCH_RAW) as m:
            r = self.client.get("/api/search", params={"q": "daft punk", "params": "abc"})
        self.assertEqual(r.status_code, 200)
        m.assert_called_once_with("daft punk", "abc")

    def test_search_vuoto_rifiutato(self):
        r = self.client.get("/api/search", params={"q": ""})
        self.assertEqual(r.status_code, 422)

    def test_search_errore_upstream(self):
        with mock.patch.object(innertube, "search", side_effect=innertube.InnertubeError("rate limit")):
            r = self.client.get("/api/search", params={"q": "daft punk"})
        self.assertEqual(r.status_code, 502)
        self.assertIn("rate limit", r.json()["detail"])

    def test_home(self):
        with mock.patch.object(innertube, "home", return_value=HOME_RAW):
            r = self.client.get("/api/home")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["shelves"][0]["title"], "Scelte rapide")

    def test_browse(self):
        with mock.patch.object(innertube, "browse", return_value=BROWSE_RAW) as m:
            r = self.client.get("/api/browse/MPREb_7ltM34kr0mH")
        self.assertEqual(r.status_code, 200)
        dati = r.json()
        self.assertEqual(dati["title"], "Discovery")
        self.assertEqual(dati["browseId"], "MPREb_7ltM34kr0mH")
        self.assertEqual(len(dati["items"]), 1)
        m.assert_called_once_with("MPREb_7ltM34kr0mH")

    def test_track(self):
        meta = {"videoId": "FGBhQbmPwH8", "title": "One More Time", "artist": "Daft Punk",
                "album": "Discovery", "thumbnail": "https://img/x.jpg", "duration": 321}
        with mock.patch.object(audio, "metadati", return_value=meta):
            r = self.client.get("/api/track/FGBhQbmPwH8")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["artist"], "Daft Punk")
        self.assertEqual(r.json()["duration"], 321)

    def test_immagine_url_non_valido(self):
        r = self.client.get("/api/image", params={"u": "http://esempio/x.jpg"})
        self.assertEqual(r.status_code, 400)

    def test_pagina_principale(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers["content-type"])


class TestStream(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), RangeHandler)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/audio.m4a"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.client = TestClient(main.app)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_stream_completo(self):
        with mock.patch.object(audio, "resolve", return_value={"url": self.url, "mime": "audio/mp4"}):
            r = self.client.get("/api/stream/FGBhQbmPwH8")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "audio/mp4")
        self.assertEqual(len(r.content), len(PAYLOAD))

    def test_stream_con_range(self):
        with mock.patch.object(audio, "resolve", return_value={"url": self.url, "mime": "audio/mp4"}):
            r = self.client.get("/api/stream/FGBhQbmPwH8", headers={"Range": "bytes=0-1023"})
        self.assertEqual(r.status_code, 206)
        self.assertEqual(r.headers["content-range"], f"bytes 0-1023/{len(PAYLOAD)}")
        self.assertEqual(len(r.content), 1024)

    def test_stream_errore_risoluzione(self):
        with mock.patch.object(audio, "resolve", side_effect=audio.AudioError("video inesistente")):
            r = self.client.get("/api/stream/inesistente")
        self.assertEqual(r.status_code, 502)
        self.assertIn("inesistente", r.json()["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
