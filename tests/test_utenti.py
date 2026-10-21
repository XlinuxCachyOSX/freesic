"""Test di account e "mi piace".

Gli utenti e i "mi piace" vengono salvati in file temporanei, quindi i
test non toccano i dati reali del giocatore.
"""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from server import main, utenti


class TestAccount(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="freesic-test-")
        self.vecchio = (utenti.DATI, utenti.FILE_UTENTI, utenti.FILE_PIACI, utenti.FILE_SESSIONI)
        utenti.DATI = self.dir
        utenti.FILE_UTENTI = os.path.join(self.dir, "utenti.json")
        utenti.FILE_PIACI = os.path.join(self.dir, "mi_piace.json")
        utenti.FILE_SESSIONI = os.path.join(self.dir, "sessioni.json")
        utenti._sessioni.clear()
        self.client = TestClient(main.app)

    def tearDown(self):
        (utenti.DATI, utenti.FILE_UTENTI, utenti.FILE_PIACI,
         utenti.FILE_SESSIONI) = self.vecchio
        utenti._sessioni.clear()

    # -- registrazione e accesso -------------------------------------------
    def test_registrazione_e_sessione(self):
        r = self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["autenticato"])
        self.assertIn("freesic_session", r.cookies)

        r = self.client.get("/api/auth/me")
        self.assertEqual(r.json()["utente"], "alessio")

    def test_password_non_cifrata_su_disco(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        with open(utenti.FILE_UTENTI, encoding="utf-8") as f:
            contenuto = f.read()
        self.assertNotIn("ciao123", contenuto)
        self.assertIn("hash", contenuto)

    def test_nome_utente_duplicato(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        r = self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        self.assertEqual(r.status_code, 400)

    def test_password_troppo_corta(self):
        r = self.client.post("/api/auth/register", json={"username": "alessio", "password": "x"})
        self.assertEqual(r.status_code, 400)

    def test_login_errato(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        r = self.client.post("/api/auth/login", json={"username": "alessio", "password": "sbagliata"})
        self.assertEqual(r.status_code, 401)

    def test_logout(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        self.client.post("/api/auth/logout")
        r = self.client.get("/api/auth/me")
        self.assertFalse(r.json()["autenticato"])

    # -- mi piace -----------------------------------------------------------
    def test_mi_piace_richiede_account(self):
        r = self.client.get("/api/mipiace")
        self.assertEqual(r.status_code, 401)

    def test_aggiungi_e_togli_mi_piace(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        brano = {"videoId": "FGBhQbmPwH8", "title": "One More Time", "artist": "Daft Punk"}
        r = self.client.post("/api/mipiace", json=brano)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["items"]), 1)

        r = self.client.get("/api/mipiace")
        self.assertEqual(r.json()["items"][0]["title"], "One More Time")

        r = self.client.delete("/api/mipiace/FGBhQbmPwH8")
        self.assertEqual(r.json()["items"], [])

    def test_mi_piace_duplicato_non_doppia(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        brano = {"videoId": "FGBhQbmPwH8", "title": "One More Time"}
        self.client.post("/api/mipiace", json=brano)
        r = self.client.post("/api/mipiace", json=brano)
        self.assertEqual(len(r.json()["items"]), 1)

    def test_playlist_piaciuta(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        self.client.post("/api/mipiace", json={"videoId": "FGBhQbmPwH8", "title": "One More Time"})
        r = self.client.get("/api/playlist/piaciuta")
        dati = r.json()
        self.assertEqual(dati["title"], "Piaciuta")
        self.assertEqual(len(dati["items"]), 1)
        self.assertIn("brani", dati["subtitle"])

    def test_piace_di_un_utente_restano_privati(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        self.client.post("/api/mipiace", json={"videoId": "FGBhQbmPwH8", "title": "One More Time"})
        self.client.post("/api/auth/logout")
        self.client.post("/api/auth/register", json={"username": "marco", "password": "ciao123"})
        r = self.client.get("/api/mipiace")
        self.assertEqual(r.json()["items"], [])

    def test_dati_su_disco(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        self.client.post("/api/mipiace", json={"videoId": "FGBhQbmPwH8", "title": "One More Time"})
        with open(utenti.FILE_PIACI, encoding="utf-8") as f:
            dati = json.load(f)
        self.assertEqual(len(dati["alessio"]), 1)

    # -- la sessione sopravvive al riavvio ---------------------------------
    def test_sessione_salvata_su_disco(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        with open(utenti.FILE_SESSIONI, encoding="utf-8") as f:
            dati = json.load(f)
        self.assertEqual(len(dati), 1)
        # nel file non deve comparire il token, solo il suo hash
        token = self.client.cookies.get(utenti.COOKIE)
        self.assertNotIn(token, json.dumps(dati))

    def test_sessione_valida_dopo_ricarica_in_memoria(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        token = self.client.cookies.get(utenti.COOKIE)
        # simula il riavvio del server: la memoria si svuota e si rilegge il file
        utenti._sessioni.clear()
        utenti._carica_sessioni()
        self.assertEqual(utenti.utente_da_token(token), "alessio")
        r = self.client.get("/api/auth/me")
        self.assertEqual(r.json()["utente"], "alessio")

    def test_sessione_scaduta_non_valida(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        token = self.client.cookies.get(utenti.COOKIE)
        chiave = utenti._chiave_token(token)
        utenti._sessioni[chiave] = ("alessio", time.time() - 10)
        utenti._salva_sessioni()
        utenti._sessioni.clear()
        utenti._carica_sessioni()
        self.assertIsNone(utenti.utente_da_token(token))

    def test_logout_rimuove_anche_dal_disco(self):
        self.client.post("/api/auth/register", json={"username": "alessio", "password": "ciao123"})
        self.client.post("/api/auth/logout")
        with open(utenti.FILE_SESSIONI, encoding="utf-8") as f:
            dati = json.load(f)
        self.assertEqual(dati, {})


if __name__ == "__main__":
    unittest.main()
