"""Verifica end-to-end del frontend con un browser headless (Playwright).

Non usa il test runner unittest: si esegue a mano con un server gia' attivo.
    python strumenti/verifica_ui.py http://127.0.0.1:8295
"""
import sys
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Serve Playwright:\n"
          "    ./.venv/bin/pip install playwright\n"
          "    ./.venv/bin/python -m playwright install chromium")
    sys.exit(2)

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8295"


def main() -> int:
    errori = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        pagina = browser.new_page()
        pagina.on("console", lambda m: errori.append(m.text) if m.type == "error" else None)
        pagina.on("pageerror", lambda e: errori.append(str(e)))

        pagina.goto(URL, wait_until="domcontentloaded", timeout=60000)
        pagina.wait_for_timeout(2500)

        # 1. la musica parte da sola
        in_riproduzione = pagina.evaluate("document.getElementById('audio').paused === false")
        print("riproduzione automatica:", "OK" if in_riproduzione else "FALLITA")
        if not in_riproduzione:
            errori.append("la musica non e' partita da sola")

        # 2. tema chiaro/scuro
        tema_iniziale = pagina.evaluate("document.documentElement.dataset.tema")
        pagina.click("#tema")
        pagina.wait_for_timeout(300)
        tema_finale = pagina.evaluate("document.documentElement.dataset.tema")
        print(f"tema: {tema_iniziale} -> {tema_finale}",
              "OK" if tema_iniziale != tema_finale else "FALLITO")
        if tema_iniziale == tema_finale:
            errori.append("il tema non cambia")
        pagina.click("#tema")

        # 3. registrazione
        pagina.evaluate("window.scrollTo(0, 0)")
        pagina.click("#btn-account")
        pagina.wait_for_timeout(500)
        pagina.click("#scheda-registro", force=True)
        utente = f"test{int(time.time())}"
        pagina.fill("#acc-utente", utente)
        pagina.fill("#acc-password", "ciao123")
        pagina.click("#form-account button[type=submit]")
        pagina.wait_for_timeout(900)
        testo_bottone = pagina.inner_text("#btn-account")
        print("account:", testo_bottone, "OK" if utente in testo_bottone else "FALLITO")
        if utente not in testo_bottone:
            errori.append("registrazione fallita: " + pagina.inner_text("#acc-errore"))

        # 4. mi piace sul primo brano
        pagina.wait_for_timeout(500)
        cuore = pagina.query_selector("[data-piace]")
        if cuore is None:
            errori.append("nessun pulsante mi piace")
        else:
            cuore.click(force=True)
            pagina.wait_for_timeout(800)
            attivo = "attivo" in (cuore.get_attribute("class") or "")
            print("mi piace:", "OK" if attivo else "FALLITO")
            if not attivo:
                errori.append("il cuore non si attiva")

        # 5. playlist Piaciuta
        pagina.click("#voce-piaciuta")
        pagina.wait_for_timeout(1200)
        titoli = pagina.eval_on_selector_all("#vista h1", "els => els.map(e => e.textContent)")
        print("playlist:", titoli, "OK" if titoli and "Piaciuta" in titoli[0] else "FALLITA")
        if not titoli or "Piaciuta" not in titoli[0]:
            errori.append("playlist Piaciuta non raggiungibile")
        righe = pagina.eval_on_selector_all("#vista tr[data-video]", "els => els.length")
        print("brani in Piaciuta:", righe, "OK" if righe >= 1 else "FALLITO")
        if righe < 1:
            errori.append("il brano con mi piace non compare in Piaciuta")

        # 6. sessione ripristinata dopo il ricaricamento
        pagina.reload(wait_until="domcontentloaded", timeout=60000)
        pagina.wait_for_timeout(1200)
        print("sessione dopo reload:", pagina.inner_text("#btn-account"))
        browser.close()

    if errori:
        print("\nERRORI:")
        for e in errori:
            print(" -", e)
        return 1
    print("\nTutto OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
