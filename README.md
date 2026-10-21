# FreeSic — player musicale senza pubblicità

Applicazione web per ascoltare musica da YouTube Music **senza pubblicità, senza
login e senza account**: il backend risolve i brani e serve l'audio direttamente
al browser, il frontend è una web app in stile YouTube Music.

**Cosa c'è dentro**

- Ricerca, album, playlist e stream audio diretti da YouTube Music, senza
  pubblicità, senza login e senza account.
- La musica parte da sola appena apri il sito.
- Tema chiaro o scuro (predefinito: quello del sistema), salvato nel browser.
- Account facoltativo, salvato **solo su questo computer**: serve per mettere
  "mi piace" ai brani e ritrovarli nella playlist **Piaciuta**.
- Versione Android (APK) che mostra la stessa interfaccia.

## Scarica

| Versione | Dispositivo | File |
|---|---|---|
| 1.0.0 (release) | Android 5.0+ | [FreeSic-1.0.0.apk](https://github.com/XlinuxCachyOSX/freesic/raw/main/FreeSic-1.0.0.apk) |
| 1.0.0 (debug) | Android 5.0+ | [FreeSic-debug.apk](https://github.com/XlinuxCachyOSX/freesic/raw/main/FreeSic-debug.apk) |

Su computer: Linux/macOS con `./start.sh`, Windows con `start.bat`.
L'APK è il guscio: per ascoltare serve il server acceso sul computer
(`./start.sh` con `HOST=0.0.0.0`) e l'indirizzo del PC da inserire nel menu
dell'app. Tutte le impostazioni (ricerca, tema, "mi piace") sono le stesse
del sito.

```
freesic/
├── server/            backend Python (FastAPI)
│   ├── innertube.py   client dell'API interna di YouTube Music
│   ├── parse.py       normalizzazione delle risposte in JSON semplici
│   ├── audio.py       risoluzione dello stream audio (yt-dlp) + cache
│   ├── cache.py       cache TTL in memoria
│   └── main.py        endpoint REST + file statici
├── web/               frontend (HTML/CSS/JS puro, nessun build)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── android/           app Android (WebView verso il backend)
│   ├── app/           progetto Gradle
│   └── build-apk.sh   compila l'APK (usa JDK/SDK/Gradle in toolchain/)
├── strumenti/         avvio condiviso da Linux, macOS e Windows
│   ├── prepara.py     virtualenv, pip, dipendenze, porta libera
│   ├── avvia.py      entry point di start.sh / start.bat
│   └── servizio.py    uvicorn + apertura automatica del browser
├── toolchain/         JDK 17, Android SDK e Gradle (non tracciato da git)
├── FreeSic-1.0.0.apk  APK release pronto (stessa cartella del progetto)
├── FreeSic-debug.apk  APK debug
├── tests/             test automatici (unittest)
├── requirements.txt
├── start.sh / start.bat
└── README.md
```

## Avvio rapido

Linux/macOS:

```bash
cd freesic
./start.sh
```

Windows (PowerShell o cmd):

```bat
cd freesic
start.bat
```

Il comando e' lo stesso su tutte le piattaforme: crea l'ambiente virtuale
`.venv`, installa le dipendenze se mancano, avvia il server e **apre da solo
il browser** su <http://127.0.0.1:8000>. Per fermarlo basta `Ctrl+C`.

Dietro le quinte `start.sh` e `start.bat` chiamano `strumenti/avvia.py`, che
prepara l'ambiente (`strumenti/prepara.py`) e avvia il server
(`strumenti/servizio.py`): la logica e' quindi identica su Linux, macOS e
Windows.

Per raggiungere il player dal telefono o da un altro computer della rete:

```bash
HOST=0.0.0.0 ./start.sh
```

Il server stampa l'indirizzo da usare (es. `http://192.168.1.78:8000/`).

## Comandi manuali

```bash
./.venv/bin/python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Variabili d'ambiente supportate:

| variabile | default | descrizione |
|---|---|---|
| `PORT` | `8000` | porta del server |
| `HOST` | `127.0.0.1` | interfaccia di ascolto |

## API

| metodo | percorso | cosa fa |
|---|---|---|
| `GET` | `/api/health` | stato del servizio |
| `GET` | `/api/search?q=…&params=…` | ricerca; `params` è il filtro opaco (Canzoni, Album, Artisti…) |
| `GET` | `/api/home` | scaffali consigliati |
| `GET` | `/api/browse/{browse_id}` | album (`MPREb…`), playlist (`VLPL…`), artisti (`UC…`) |
| `GET` | `/api/track/{video_id}` | metadati del brano (artista, album, durata, copertina) |
| `GET` | `/api/stream/{video_id}` | stream audio con supporto `Range` (seek) |
| `GET` | `/api/image?u=…` | proxy delle copertine |
| `POST` | `/api/auth/register` | crea un account locale (`username`, `password`) |
| `POST` | `/api/auth/login` | accesso (cookie di sessione) |
| `POST` | `/api/auth/logout` | uscita |
| `GET` | `/api/auth/me` | utente corrente |
| `GET` | `/api/mipiace` | brani con "mi piace" |
| `POST` | `/api/mipiace` | aggiunge un "mi piace" |
| `DELETE` | `/api/mipiace/{video_id}` | toglie un "mi piace" |
| `GET` | `/api/playlist/piaciuta` | playlist "Piaciuta" dell'utente |

Documentazione interattiva: <http://127.0.0.1:8000/api/docs>.

### Verifica dell'interfaccia

C'è uno script che apre il sito in un browser headless e controlla autoplay,
tema, registrazione, "mi piace" e playlist "Piaciuta":

```bash
./.venv/bin/pip install playwright
./.venv/bin/python -m playwright install chromium
./.venv/bin/python strumenti/verifica_ui.py http://127.0.0.1:8000
```

## Come funziona

1. **Ricerca e cataloghi** – `server/innertube.py` parla con l'API interna di
   YouTube Music (client `WEB_REMIX`). Le richieste sono distanziate nel tempo e
   ritentate con attese crescenti, perché il servizio applica un rate limit
   aggressivo; il `visitorData` ricevuto nelle risposte viene riusato.
2. **Parsing** – `server/parse.py` trasforma le risposte eterogenee in JSON
   uniforme (brani, album, playlist, artisti, podcast) con titolo, artista,
   album, durata, riproduzioni e copertina.
3. **Audio** – `server/audio.py` usa `yt-dlp` per ottenere l'URL diretto del
   flusso audio (`bestaudio[ext=m4a]`) e lo serve al browser via proxy.
   Nessun segmento pubblicitario viene riprodotto e nessun video viene
   scaricato su disco.
4. **Cache** – ricerche (3 min), album/playlist (15 min) e home (5 min) sono
   memorizzati in memoria per ridurre le chiamate e i limiti.

## Versione Android (APK)

L'app Android FreeSic è un contenitore WebView che mostra la stessa interfaccia: il
backend Python resta sul computer e l'app si collega a lui.

APK già compilati, nella stessa cartella del progetto:

| file | uso |
|---|---|
| `FreeSic-1.0.0.apk` | release (installabile, non debuggabile) |
| `FreeSic-debug.apk` | versione debug |

Installazione sul telefono: copia l'APK sul dispositivo, aprilo e autorizza
l'installazione da sorgenti sconosciute.

Configurazione:

1. Sul computer avvia il server in ascolto sulla rete locale:
   ```bash
   HOST=0.0.0.0 ./start.sh
   ```
2. Scopri l'indirizzo IP del computer (`ip addr` / `ipconfig`).
3. Nell'app scegli **menu → Indirizzo server** e inserisci
   `http://<ip-del-computer>:8000/`.

Su un emulatore Android l'indirizzo predefinito `http://10.0.2.2:8000/` punta
già alla macchina che esegue l'emulatore.

Per ricompilare l'APK (usa JDK 17, Android SDK e Gradle già presenti nella
cartella `toolchain/` del progetto; se mancano vengono scaricati, senza
installare nulla a livello di sistema):

```bash
cd android && ./build-apk.sh
```

L'APK risultante viene copiato nella cartella del progetto
(`FreeSic-1.0.0.apk`).

## Test

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

I test non contattano YouTube: il client Innertube e il risolutore audio sono
sostituiti con stub, e lo streaming è verificato contro un server locale che
supporta le richieste `Range`.

## Note e limiti

- Serve una connessione a internet: il backend interroga YouTube per
  catalogo e stream.
- I formati audio disponibili dipendono da ciò che YouTube espone per il singolo
  brano; in genere è sufficiente l'm4a.
- Il rate limit di YouTube Music può far fallire una richiesta se si fanno
  troppe interrogazioni in pochi secondi: il client attende e ritenta, ma a
  volume elevato conviene usare la cache.
- Il progetto è a scopo personale/educativo: rispetta i termini di servizio di
  YouTube e il diritto d'autore delle opere distribuite.
