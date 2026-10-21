# Player musicale senza pubblicità

Applicazione web per ascoltare musica da YouTube Music **senza pubblicità, senza
login e senza account**: il backend risolve i brani e serve l'audio direttamente
al browser, il frontend è una web app in stile YouTube Music.

```
nuovo-progetto/
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
│   └── build-apk.sh   compila l'APK (scarica JDK/SDK/Gradle da solo)
├── dist/              APK già compilati
├── tests/             test automatici (unittest)
├── requirements.txt
├── start.sh / start.bat
├── pubblica.sh        pubblica su GitHub da riga di comando
└── README.md
```

## Avvio rapido

Linux/macOS:

```bash
cd nuovo-progetto
./start.sh
```

Windows (PowerShell o cmd):

```bat
cd nuovo-progetto
start.bat
```

Lo script crea l'ambiente virtuale `.venv`, installa le dipendenze se mancano,
avvia il server e **apre da solo il browser** su
<http://127.0.0.1:8000> (su Windows l'apertura avviene dopo 3 secondi).
Per fermarlo basta `Ctrl+C`.

Per aprire il sito da un altro dispositivo della stessa rete (telefono,
tablet) usa `HOST=0.0.0.0 ./start.sh` e raggiungi
`http://<ip-del-computer>:8000`.

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

| metodo | endpoint | descrizione |
|---|---|---|
| `GET` | `/api/health` | stato del servizio |
| `GET` | `/api/search?q=…&params=…` | ricerca; `params` è il filtro opaco (Canzoni, Album, Artisti…) |
| `GET` | `/api/home` | scaffali consigliati |
| `GET` | `/api/browse/{browse_id}` | album (`MPREb…`), playlist (`VLPL…`), artisti (`UC…`) |
| `GET` | `/api/track/{video_id}` | metadati del brano (artista, album, durata, copertina) |
| `GET` | `/api/stream/{video_id}` | stream audio con supporto `Range` (seek) |
| `GET` | `/api/image?u=…` | proxy delle copertine |

Documentazione interattiva: <http://127.0.0.1:8000/api/docs>.

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

L'app Android è un contenitore WebView che mostra la stessa interfaccia: il
backend Python resta sul computer e l'app si collega a lui.

APK già compilati in `dist/`:

| file | uso |
|---|---|
| `MusicaSenzaPubblicita-1.0.0.apk` | release (installabile, non debuggabile) |
| `MusicaSenzaPubblicita-debug.apk` | versione debug |

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

Per ricompilare l'APK (scarica da solo JDK 17, Android SDK e Gradle in
`~/android-toolchain`, senza installare nulla a livello di sistema):

```bash
cd android && ./build-apk.sh
```

## Pubblicare su GitHub

Il comando va eseguito **dentro** la cartella del progetto:

```bash
cd "Default Project/nuovo-progetto"
./pubblica.sh                 # crea il repository e fa il push
./pubblica.sh altro-nome     # sceglie un altro nome
```

Lo script usa GitHub CLI: se non è installato lo scarica in `./.gh`, poi chiede
il login (via browser: compare un codice da confermare) e infine crea il
repository e carica il codice. Se il repository esiste già lo riusa.
In alternativa, senza script:

```bash
git remote add origin https://github.com/<utente>/<repository>.git
git push -u origin main
```

Se preferisci usare un token personale invece del login:

```bash
export GH_TOKEN=ghp_xxxxxxxxxxxx
./pubblica.sh
```

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
