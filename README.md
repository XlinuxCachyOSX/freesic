# FreeSic — player musicale senza pubblicità

Applicazione web per ascoltare musica da YouTube Music **senza pubblicità, senza
login e senza account**: il backend risolve i brani e serve l'audio direttamente
al browser, il frontend è una web app in stile YouTube Music.

**Cosa c'è dentro**

- Ricerca, album, playlist e stream audio diretti da YouTube Music, senza
  pubblicità, senza login e senza account.
- La musica parte da sola appena apri il sito.
- Pulsante di loop nel player: si sceglie se far ripartire la coda, lo stesso
  brano, o niente. La scelta resta anche dopo aver chiuso il browser.
- Tema chiaro o scuro (predefinito: quello del sistema), salvato nel browser.
- Account facoltativo, salvato **solo su questo computer**: serve per mettere
  "mi piace" ai brani e ritrovarli nella playlist **Piaciuta**. L'accesso resta
  valido anche riavviando il server o il computer (la sessione è salvata in
  `dati/sessioni.json`, dove si tiene solo l'hash del token).
- Versione Android (APK) che mostra la stessa interfaccia.

## Scarica

| Versione | Sistema | File |
|---|---|---|
| 1.0.0 (release) | Linux (x64) | [FreeSic-linux.zip](https://github.com/XlinuxCachyOSX/freesic/releases/download/v1.0.0/FreeSic-linux.zip) |
| 1.0.0 (release) | Windows (x64) | [FreeSic-windows.zip](https://github.com/XlinuxCachyOSX/freesic/releases/download/v1.0.0/FreeSic-windows.zip) |
| 1.0.0 (release) | macOS (Intel/Apple silicon) | [FreeSic-macos.zip](https://github.com/XlinuxCachyOSX/freesic/releases/download/v1.0.0/FreeSic-macos.zip) |
| 1.3.1 (release) | Android 5.0+ | [FreeSic.apk](https://github.com/XlinuxCachyOSX/freesic/releases/download/v1.0.0/FreeSic.apk) |
| 1.3.1 (debug) | Android 5.0+ | [FreeSic-debug.apk](https://github.com/XlinuxCachyOSX/freesic/releases/download/v1.0.0/FreeSic-debug.apk) |

I file zip contengono il progetto pronto: si decomprime e si avvia.
(Per rigenerarli: `python strumenti/pacchetti.py`.)

- Linux e macOS: `./start.sh`
- Windows: `start.bat`

Serve Python 3.10 o successivo: al primo avvio lo script crea da solo
l'ambiente virtuale e installa le dipendenze (serve una connessione internet
solo per quella operazione). L'APK è il guscio: per ascoltare serve il server
acceso sul computer (`./start.sh`) e l'indirizzo del PC che compare nella riga
"Dal telefono" all'avvio, da inserire nel menu dell'app. Ricerca, tema e
"mi piace" sono le stesse cose del sito.

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
├── FreeSic.apk        APK release pronto (stessa cartella del progetto)
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

Il server ascolta già sulla rete locale, quindi lo puoi raggiungere dal
telefono o da un altro computer: all'avvio stampa una riga
`Dal telefono: http://192.168.1.78:8000/` con l'indirizzo da usare. Se il
computer ha più di una scheda di rete (Wi-Fi, cavo, VPN) prova gli altri
indirizzi stampati. Per ascoltare solo da questo computer usa
`HOST=127.0.0.1 ./start.sh`.

### Da qualsiasi rete (anche in 4G)

Per ascoltare fuori casa non serve aprire porte sul router: basta aggiungere
`--tunnel` all'avvio e FreeSic passa da un tunnel HTTPS di Cloudflare.

```bash
./start.sh --tunnel        # Windows: start.bat --tunnel
```

Al primo uso scarica `cloudflared` (~40 MB, una volta sola) e poi stampa:

```
Da qualsiasi rete: https://parole-casuali.trycloudflare.com/
```

Inserisci quell'indirizzo nel menu dell'app Android (o aprilo da qualunque
browser) e funziona in 4G, all'estero, da qualsiasi computer. L'indirizzo
cambia a ogni avvio e vale finché FreeSic resta acceso: per chiuderlo basta
`Ctrl+C`, e da quel momento il link non risponde più.

Chi ha il link può usare il player: gli account restano protetti da password
(dopo 6 tentativi sbagliati l'accesso viene bloccato per qualche minuto).
Per avere un indirizzo fisso serve un dominio su Cloudflare: crea il tunnel
con `cloudflared tunnel login`, `cloudflared tunnel create freesic`,
`cloudflared tunnel route dns freesic musica.tuodominio.it` e avvialo con
`cloudflared tunnel run --url http://127.0.0.1:8000 freesic`.

## Comandi manuali

```bash
./.venv/bin/python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Variabili d'ambiente supportate:

| variabile | default | descrizione |
|---|---|---|
| `PORT` | `8000` | porta del server |
| `HOST` | `0.0.0.0` | interfaccia di ascolto (`0.0.0.0` = tutta la rete locale, `127.0.0.1` = solo questo computer) |
| `TUNNEL` | `0` | `1` = espone FreeSic su internet con un tunnel Cloudflare (come `--tunnel`) |

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
| `FreeSic.apk` | release (installabile, non debuggabile) |
| `FreeSic-debug.apk` | versione debug |

Installazione sul telefono: copia l'APK sul dispositivo, aprilo e autorizza
l'installazione da sorgenti sconosciute.

Configurazione:

1. Sul computer avvia il server con `./start.sh` (o `start.bat` su Windows).
2. All'avvio leggi la riga `Dal telefono: http://…` che compare nel terminale.
   Se non c'è, il computer e il telefono non sono sulla stessa rete Wi-Fi.
3. Nell'app scegli **menu → Indirizzo server** e inserisci quell'indirizzo.
   Se il telefono non si collega, controlla che il firewall del computer
   permetta le connessioni in ingresso sulla porta 8000.
4. Fuori casa (4G) usa l'indirizzo del tunnel: avvia con `--tunnel` e copia
   la riga `Da qualsiasi rete` (vedi sopra).

Su un emulatore Android l'indirizzo predefinito `http://10.0.2.2:8000/` punta
già alla macchina che esegue l'emulatore.

Per ricompilare l'APK (usa JDK 17, Android SDK e Gradle già presenti nella
cartella `toolchain/` del progetto; se mancano vengono scaricati, senza
installare nulla a livello di sistema):

```bash
cd android && ./build-apk.sh
```

L'APK risultante viene copiato nella cartella del progetto
(`FreeSic.apk`).

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
