"""Verifica della modalita' loop nel browser (Playwright).

Controlla che:
- il pulsante cicli tra nessuno / coda / brano singolo
- la scelta resti valida dopo il ricaricamento
- a fine brano la musica riparta (loop) o si fermi (nessuno)

Uso:  python strumenti/verifica_loop.py http://127.0.0.1:8303
"""
import sys
import time

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8303"


def icona(pagina):
    return pagina.inner_text("#btn-loop")


def main() -> int:
    errori = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        pagina = browser.new_page()
        pagina.goto(URL, wait_until="domcontentloaded", timeout=60000)
        pagina.wait_for_timeout(2500)

        # 1. il pulsante esiste e parte da "nessuno"
        iniziale = icona(pagina)
        print("loop iniziale:", iniziale)
        if iniziale != "↻":
            errori.append("il loop non parte da nessuno")

        # 2. clic -> coda, ancora -> brano singolo, ancora -> nessuno
        pagina.click("#btn-loop")
        pagina.wait_for_timeout(200)
        print("dopo 1 clic:", icona(pagina))
        if icona(pagina) != "∞":
            errori.append("il primo clic non attiva il loop della coda")

        pagina.click("#btn-loop")
        pagina.wait_for_timeout(200)
        print("dopo 2 clic:", icona(pagina))
        if icona(pagina) != "↺":
            errori.append("il secondo clic non attiva il loop del brano")

        pagina.click("#btn-loop")
        pagina.wait_for_timeout(200)
        if icona(pagina) != "↻":
            errori.append("il terzo clic non torna a nessuno")

        # 3. la scelta resta valida dopo il ricaricamento
        pagina.click("#btn-loop")
        pagina.wait_for_timeout(200)
        pagina.reload(wait_until="domcontentloaded", timeout=60000)
        pagina.wait_for_timeout(1500)
        print("dopo reload:", icona(pagina))
        if icona(pagina) != "∞":
            errori.append("la scelta del loop non e' stata salvata")
        pagina.evaluate("localStorage.removeItem('freesic.loop')")

        # 4. a fine brano il brano riparte da capo (loop brano)
        for _ in range(4):
            if icona(pagina) == "↺":
                break
            pagina.click("#btn-loop")
            pagina.wait_for_timeout(200)
        print("modalita' per il test:", icona(pagina))
        if icona(pagina) != "↺":
            errori.append("non sono riuscito a mettere il loop del brano")
        pagina.evaluate("""() => {
            const a = document.getElementById('audio');
            window.__fin = false;
            a.addEventListener('ended', () => { window.__fin = true; });
            a.currentTime = Math.max(0, (a.duration || 5) - 0.4);
        }""")
        pagina.wait_for_timeout(5000)
        riparte = pagina.evaluate("""() => {
            const a = document.getElementById('audio');
            return { fine: window.__fin, pausa: a.paused, tempo: a.currentTime };
        }""")
        print("dopo la fine del brano:", riparte)
        if not riparte["fine"]:
            errori.append("l'evento di fine brano non e' scattato")
        if riparte["pausa"] or riparte["tempo"] < 1:
            errori.append("il brano non e' ripartito")

        # 5. con loop disattivato il brano si ferma
        for _ in range(4):
            if icona(pagina) == "↻":
                break
            pagina.click("#btn-loop")
            pagina.wait_for_timeout(200)
        pagina.evaluate("""() => {
            const a = document.getElementById('audio');
            a.currentTime = Math.max(0, (a.duration || 5) - 0.4);
        }""")
        pagina.wait_for_timeout(5000)
        fermo = pagina.evaluate("""() => {
            const a = document.getElementById('audio');
            return { pausa: a.paused, tempo: a.currentTime };
        }""")
        print("con loop disattivato:", fermo)
        if not fermo["pausa"]:
            errori.append("con loop disattivato il brano dovrebbe fermarsi")

        # 6. con loop della coda, finite le tracce si torna alla prima
        pagina.evaluate("""() => {
            window.avvia([
                { videoId: 'FGBhQbmPwH8', title: 'Uno' },
                { videoId: 'i5efaeO-5Jo', title: 'Due' },
            ], 0);
        }""")
        pagina.wait_for_timeout(2500)
        for _ in range(4):
            if icona(pagina) == "∞":
                break
            pagina.click("#btn-loop")
            pagina.wait_for_timeout(200)
        print("modalita' per il test coda:", icona(pagina))
        # mette in coda l'ultima traccia e la porta a fine
        pagina.evaluate("""() => {
            const a = document.getElementById('audio');
            a.currentTime = Math.max(0, (a.duration || 5) - 0.4);
        }""")
        pagina.wait_for_timeout(5000)
        dopo = pagina.evaluate("""() => {
            const a = document.getElementById('audio');
            return { titolo: document.getElementById('titolo-brano').textContent,
                     pausa: a.paused, tempo: a.currentTime };
        }""")
        print("a fine coda:", dopo)
        if dopo["pausa"] or dopo["titolo"] != "Uno":
            errori.append("il loop della coda non e' ripartito dal primo brano")

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
