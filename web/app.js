/* FreeSic - player musicale senza pubblicità - frontend vanilla */
const audio = document.getElementById("audio");
const vista = document.getElementById("vista");
const chips = document.getElementById("chips");
const libreriaEl = document.getElementById("libreria");
const codaEl = document.getElementById("coda");
const listaCoda = document.getElementById("lista-coda");
const avvioEl = document.getElementById("avvio");

const stato = {
  vista: "home",
  filtri: [],
  filtroAttivo: null,
  coda: [],
  indice: -1,
  libreria: [],
  scaffali: [],
  utente: "",
  piaciuti: new Set(),
  modalita: "login",
  loop: "nessuno",
};

/* ---------- tema chiaro / scuro ---------- */
function temaPreferito() {
  try {
    const salvato = localStorage.getItem("freesic.tema");
    if (salvato === "chiaro" || salvato === "scuro") return salvato;
  } catch (e) { /* storage non disponibile */ }
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) return "chiaro";
  return "scuro";
}

function applicaTema(tema) {
  document.documentElement.dataset.tema = tema;
  const bottone = document.getElementById("tema");
  if (bottone) bottone.textContent = tema === "chiaro" ? "☀" : "☾";
  try { localStorage.setItem("freesic.tema", tema); } catch (e) { /* storage non disponibile */ }
}

function cambiaTema() {
  applicaTema(document.documentElement.dataset.tema === "chiaro" ? "scuro" : "chiaro");
}

/* ---------- account e "mi piace" ---------- */
async function caricaSessione() {
  try {
    const d = await api("/api/auth/me");
    stato.utente = d.utente || "";
  } catch (e) {
    stato.utente = "";
  }
  disegnaAccount();
  if (stato.utente) await caricaPiaciuti();
}

function disegnaAccount() {
  const bottone = document.getElementById("btn-account");
  const voce = document.getElementById("voce-piaciuta");
  if (bottone) bottone.textContent = stato.utente ? `${stato.utente} · Esci` : "Accedi";
  if (voce) {
    voce.classList.toggle("attivo", stato.vista === "piaciuta");
    if (!stato.utente) voce.title = "Accedi per vedere i brani con mi piace";
  }
  if (!stato.utente) {
    stato.piaciuti = new Set();
    aggiornaCuori();
  }
}

async function caricaPiaciuti() {
  try {
    const d = await api("/api/mipiace");
    stato.piaciuti = new Set((d.items || []).map((x) => x.videoId));
  } catch (e) {
    stato.piaciuti = new Set();
  }
  aggiornaCuori();
}

function aggiornaCuori() {
  document.querySelectorAll("[data-piace]").forEach((b) => {
    const attivo = stato.piaciuti.has(b.dataset.piace);
    b.classList.toggle("attivo", attivo);
    b.textContent = attivo ? "♥" : "♡";
    b.title = attivo ? "Togli dai mi piace" : "Mi piace";
  });
}

async function alternaMiPiace(videoId, brano) {
  if (!stato.utente) { apriModale("login"); return; }
  const attivo = stato.piaciuti.has(videoId);
  try {
    if (attivo) {
      const d = await api(`/api/mipiace/${encodeURIComponent(videoId)}`, { metodo: "DELETE" });
      stato.piaciuti.delete(videoId);
      void d;
    } else {
      const d = await api("/api/mipiace", {
        metodo: "POST",
        corpo: {
          videoId,
          title: brano.title || "",
          artist: brano.artist || "",
          album: brano.album || "",
          thumbnail: brano.thumbnail || "",
          duration: brano.duration || 0,
        },
      });
      (d.items || []).forEach((x) => stato.piaciuti.add(x.videoId));
    }
    aggiornaCuori();
  } catch (e) {
    document.getElementById("acc-errore").textContent = e.message;
  }
}

function apriModale(modalita) {
  stato.modalita = modalita || "login";
  const modale = document.getElementById("modale");
  modale.classList.remove("nascosto");
  aggiornaSchede();
  document.getElementById("acc-errore").textContent = "";
  document.getElementById("acc-utente").focus();
}

function chiudiModale() {
  document.getElementById("modale").classList.add("nascosto");
}

function aggiornaSchede() {
  const login = stato.modalita === "login";
  document.getElementById("scheda-accesso").classList.toggle("attivo", login);
  document.getElementById("scheda-registro").classList.toggle("attivo", !login);
  document.getElementById("titolo-modale").textContent = login ? "Accedi a FreeSic" : "Crea un account";
  document.getElementById("form-account").querySelector("button[type=submit]").textContent =
    login ? "Accedi" : "Registrati";
  document.getElementById("acc-password").autocomplete = login ? "current-password" : "new-password";
}

async function inviaAccount(e) {
  e.preventDefault();
  const errore = document.getElementById("acc-errore");
  const nome = document.getElementById("acc-utente").value.trim();
  const password = document.getElementById("acc-password").value;
  const percorso = stato.modalita === "login" ? "/api/auth/login" : "/api/auth/register";
  errore.textContent = "";
  try {
    const d = await api(percorso, { metodo: "POST", corpo: { username: nome, password } });
    stato.utente = d.utente || nome;
    document.getElementById("acc-password").value = "";
    chiudiModale();
    disegnaAccount();
    await caricaPiaciuti();
  } catch (err) {
    errore.textContent = err.message;
  }
}

async function esciAccount() {
  try { await api("/api/auth/logout", { metodo: "POST" }); } catch (e) { /* ignorato */ }
  stato.utente = "";
  stato.piaciuti = new Set();
  disegnaAccount();
  aggiornaCuori();
}

/* ---------- playlist "Piaciuta" ---------- */
async function vistaPiaciuta() {
  vista.innerHTML = `<p class="vuoto">Caricamento…</p>`;
  try {
    const d = await api("/api/playlist/piaciuta");
    stato.scaffali = [d.items];
    vista.innerHTML = `
      <div class="scaffale" data-sec="0">
      <div class="intestazione">
        ${img(d.thumbnail, d.title)}
        <div class="info">
          <h1>${esc(d.title)}</h1>
          <p>${esc(d.subtitle || "")}</p>
          <div class="azioni">
            ${d.items.length ? `<button class="btn-rosso" id="riproduci-tutto">▶ Riproduci</button>` : ""}
          </div>
        </div>
      </div>
      ${d.items.length ? tracce(d.items) : `<p class="vuoto">Nessun brano con "mi piace".</p>`}
      </div>`;
    const btnPlay = document.getElementById("riproduci-tutto");
    if (btnPlay) btnPlay.onclick = () => avvia(d.items, 0);
  } catch (e) {
    vista.innerHTML = segnale("Playlist non disponibile: " + e.message);
  }
}

/* ---------- utilità ---------- */
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));

const tempo = (sec) => {
  if (!sec && sec !== 0) return "--:--";
  sec = Math.floor(sec);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
           : `${m}:${String(s).padStart(2, "0")}`;
};

const img = (url, alt) => url
  ? `<img src="/api/image?u=${encodeURIComponent(url)}" alt="${esc(alt || "")}" loading="lazy" onerror="this.src='${esc(url)}'">`
  : `<img src="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg'/>" alt="">`;

async function api(percorso, opzioni) {
  const op = opzioni || {};
  const init = { method: op.metodo || "GET", credentials: "same-origin" };
  if (op.corpo !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(op.corpo);
  }
  const r = await fetch(percorso, init);
  if (!r.ok) {
    let det = `Errore ${r.status}`;
    try { det = (await r.json()).detail || det; } catch (e) { /* risposta non JSON */ }
    throw new Error(det);
  }
  if (r.status === 204) return {};
  return r.json();
}

const segnale = (messaggio) => `<div class="segnale">${esc(messaggio)}</div>`;

/* ---------- libreria locale ---------- */
function caricaLibreria() {
  try { stato.libreria = JSON.parse(localStorage.getItem("musica.libreria")) || []; }
  catch (e) { stato.libreria = []; }
  disegnaLibreria();
}

function salvaLibreria() {
  localStorage.setItem("musica.libreria", JSON.stringify(stato.libreria));
  disegnaLibreria();
}

function disegnaLibreria() {
  if (!stato.libreria.length) {
    libreriaEl.innerHTML = `<p class="vuoto">Le playlist che ascolti vengono salvate qui.</p>`;
    return;
  }
  libreriaEl.innerHTML = stato.libreria.map((it) => `
    <a data-browse="${esc(it.browseId || "")}" data-tipo="${esc(it.type)}" data-titolo="${esc(it.title)}"
       data-thumb="${esc(it.thumbnail || "")}">
      ${img(it.thumbnail, it.title)}
      <span>${esc(it.title)}</span>
    </a>`).join("");
}

function aggiungiAllaLibreria(item) {
  if (!item || !item.browseId) return;
  if (stato.libreria.some((x) => x.browseId === item.browseId)) return;
  stato.libreria.unshift({
    browseId: item.browseId, title: item.title, type: item.type, thumbnail: item.thumbnail,
  });
  stato.libreria = stato.libreria.slice(0, 12);
  salvaLibreria();
}

/* ---------- rendering ---------- */
function griglia(items) {
  return `<div class="griglia">${items.map((it) => `
    <div class="card" data-browse="${esc(it.browseId || "")}" data-video="${esc(it.videoId || "")}">
      <div class="miniatura">${img(it.thumbnail, it.title)}
        ${it.videoId ? `<span class="play">▶</span>` : ""}
        ${it.videoId ? `<button class="btn-piace card-piace" data-piace="${esc(it.videoId)}" title="Mi piace">♡</button>` : ""}</div>
      <h3>${esc(it.title)}</h3>
      <p>${esc(it.subtitle || it.artist || "")}</p>
    </div>`).join("")}</div>`;
}

function tracce(items) {
  return `<table class="tracce">
    <thead><tr><th class="idx">#</th><th>Titolo</th><th>Album</th><th class="durata">Durata</th><th class="azioni"></th></tr></thead>
    <tbody>${items.map((it, i) => `
      <tr data-video="${esc(it.videoId || "")}" data-idx="${i}">
        <td class="idx">${i + 1}</td>
        <td><div class="titolo-cella">${img(it.thumbnail, it.title)}
          <div><div class="titolo-traccia">${esc(it.title)}</div>
          <div class="meta">${esc(it.artist || "")}</div></div></div></td>
        <td class="meta">${esc(it.album || "")}</td>
        <td class="durata">${esc(it.durationText || tempo(it.duration))}</td>
        <td class="azioni">
          <button class="btn-piace" data-piace="${esc(it.videoId || "")}" title="Mi piace">♡</button>
          <button class="btn-singolo" title="Riproduci">▶</button>
        </td>
      </tr>`).join("")}</tbody></table>`;
}

function sezione(titolo, contenuto, indice) {
  return `<div class="scaffale" data-sec="${indice}"><h2>${esc(titolo)}</h2>${contenuto}</div>`;
}

/* Restituisce gli elementi della sezione che contiene l'elemento passato. */
function elementiDi(el) {
  const box = el.closest("[data-sec]");
  if (!box) return [];
  return stato.scaffali[Number(box.dataset.sec)] || [];
}

async function vistaHome() {
  vista.innerHTML = `<p class="vuoto">Caricamento…</p>`;
  try {
    const dati = await api("/api/home");
    if (!dati.shelves || !dati.shelves.length) {
      vista.innerHTML = `<p class="vuoto">Nessuna raccomandazione disponibile. Prova la ricerca.</p>`;
      return;
    }
    stato.scaffali = dati.shelves.map((s) => s.items);
    vista.innerHTML = dati.shelves.map((s, i) => sezione(s.title, griglia(s.items), i)).join("");
    avviaAutomatico();
  } catch (e) {
    vista.innerHTML = segnale("Home non disponibile: " + e.message);
  }
}

function disegnaChips(filtri, attivo) {
  stato.filtri = filtri || [];
  stato.filtroAttivo = attivo || null;
  chips.innerHTML = "";
  const senza = { label: "Tutto", params: null };
  const tutti = [senza].concat(stato.filtri.filter((f) => f.params !== (attivo || "")));
  const visti = new Set();
  for (const f of tutti) {
    if (visti.has(f.params)) continue;
    visti.add(f.params);
    const b = document.createElement("button");
    b.className = "chip" + ((f.params || null) === (attivo || null) ? " attivo" : "");
    b.textContent = f.label;
    b.dataset.params = f.params || "";
    chips.appendChild(b);
  }
}

async function vistaRicerca(q, params) {
  vista.innerHTML = `<p class="vuoto">Ricerca in corso…</p>`;
  try {
    const url = `/api/search?q=${encodeURIComponent(q)}${params ? `&params=${encodeURIComponent(params)}` : ""}`;
    const dati = await api(url);
    disegnaChips(dati.filters, params || null);
    if (!dati.sections.length) {
      vista.innerHTML = `<p class="vuoto">Nessun risultato per «${esc(q)}».</p>`;
      return;
    }
    stato.scaffali = dati.sections.map((s) => s.items);
    vista.innerHTML = dati.sections.map((s, i) => {
      if (s.type === "message") return `<p class="vuoto">${esc(s.message || "Nessun risultato.")}</p>`;
      if (s.type === "song") return sezione(s.title || "Canzoni", tracce(s.items), i);
      if (s.items.length && s.items[0].browseId) return sezione(s.title, griglia(s.items), i);
      if (s.items.length) return sezione(s.title, tracce(s.items), i);
      return "";
    }).join("");
  } catch (e) {
    vista.innerHTML = segnale("Ricerca non riuscita: " + e.message);
  }
}

async function vistaDettaglio(browseId) {
  vista.innerHTML = `<p class="vuoto">Caricamento…</p>`;
  try {
    const d = await api(`/api/browse/${encodeURIComponent(browseId)}`);
    const copertina = d.thumbnail || (d.items[0] && d.items[0].thumbnail) || "";
    const tracceHtml = d.items.length ? tracce(d.items) : `<p class="vuoto">Nessuna traccia.</p>`;
    stato.scaffali = [d.items];
    vista.innerHTML = `
      <div class="scaffale" data-sec="0">
      <div class="intestazione">
        ${img(copertina, d.title)}
        <div class="info">
          <h1>${esc(d.title)}</h1>
          ${d.subtitle ? `<p>${esc(d.subtitle)}</p>` : ""}
          ${d.description ? `<p>${esc(d.description)}</p>` : ""}
          <div class="azioni">
            ${d.items.some((i) => i.videoId) ? `<button class="btn-rosso" id="riproduci-tutto">▶ Riproduci</button>` : ""}
            <button class="btn-grigio" id="salva-libreria">+ Salva in libreria</button>
          </div>
        </div>
      </div>
      ${tracceHtml}</div>`;
    const btnSalva = document.getElementById("salva-libreria");
    if (btnSalva) btnSalva.onclick = () => {
      aggiungiAllaLibreria({ browseId, title: d.title, type: d.type, thumbnail: copertina });
      btnSalva.textContent = "✓ Salvato";
    };
    const btnPlay = document.getElementById("riproduci-tutto");
    if (btnPlay) btnPlay.onclick = () => avvia(d.items, 0);
  } catch (e) {
    vista.innerHTML = segnale("Contenuto non disponibile: " + e.message);
  }
}

/* ---------- riproduzione ---------- */
/* La musica parte da sola appena il sito si apre: se il browser blocca
   l'avvio automatico (serve un gesto dell'utente) compare la schermata
   "Clicca per far partire la musica". */
function mostraAvvio() {
  if (avvioEl) avvioEl.classList.remove("nascosto");
}

function nascondiAvvio() {
  if (avvioEl) avvioEl.classList.add("nascosto");
}

function avviaAutomatico() {
  const primo = stato.scaffali.flat().find((x) => x && x.videoId);
  if (!primo) return;
  avvia([primo], 0);
}

if (avvioEl) {
  avvioEl.addEventListener("click", () => {
    if (!audio.src) return;
    audio.play().then(nascondiAvvio).catch(() => { /* resta la schermata */ });
  });
}

function avvia(brano, indice) {
  const brani = brano.filter((b) => b.videoId);
  if (!brani.length) return;
  stato.coda = brani;
  stato.indice = -1;
  suona(indice);
}

function suona(indice) {
  if (indice < 0 || indice >= stato.coda.length) return;
  const b = stato.coda[indice];
  stato.indice = indice;
  audio.src = `/api/stream/${encodeURIComponent(b.videoId)}`;
  audio.play().catch((e) => {
    if (e && e.name === "NotAllowedError") { mostraAvvio(); return; }
    document.getElementById("artista-brano").textContent = "Errore: " + e.message;
  });
  aggiornaPlayer(b);
  arricchisci(b);
  disegnaCoda();
  segnaInRiproduzione();
}

async function arricchisci(b) {
  /* Completa artista/album/copertina con i metadati risolti dal backend. */
  if (!b.videoId) return;
  try {
    const d = await api(`/api/track/${encodeURIComponent(b.videoId)}`);
    const corrente = stato.coda[stato.indice];
    if (!corrente || corrente.videoId !== b.videoId) return;
    const aggiornato = {
      ...corrente,
      artist: corrente.artist || d.artist || "",
      album: corrente.album || d.album || "",
      thumbnail: corrente.thumbnail || d.thumbnail,
      duration: corrente.duration || d.duration,
    };
    stato.coda[stato.indice] = aggiornato;
    aggiornaPlayer(aggiornato);
    disegnaCoda();
  } catch (e) {
    /* metadati non disponibili: la riproduzione continua */
  }
}

function successivo() {
  if (stato.indice + 1 < stato.coda.length) suona(stato.indice + 1);
  else { audio.pause(); audio.currentTime = 0; aggiornaBarra(); }
}

/* ---------- loop: la musica ricomincia da sola quando finisce ---------- */
const MODI_LOOP = ["nessuno", "coda", "uno"];
const TESTI_LOOP = {
  nessuno: "Loop disattivato: clicca per far ripartire la coda",
  coda: "Loop della coda: a fine lista ricomincia dal primo brano",
  uno: "Loop del brano: a fine brano riparte da capo",
};

function loopSalvato() {
  try {
    const salvato = localStorage.getItem("freesic.loop");
    if (MODI_LOOP.includes(salvato)) return salvato;
  } catch (e) { /* storage non disponibile */ }
  return "nessuno";
}

function salvaLoop(modo) {
  try { localStorage.setItem("freesic.loop", modo); } catch (e) { /* storage non disponibile */ }
}

function disegnaLoop() {
  const bottone = document.getElementById("btn-loop");
  if (!bottone) return;
  const icone = { nessuno: "↻", coda: "∞", uno: "↺" };
  bottone.textContent = icone[stato.loop];
  bottone.classList.toggle("attivo", stato.loop !== "nessuno");
  bottone.title = TESTI_LOOP[stato.loop];
  bottone.setAttribute("aria-label", TESTI_LOOP[stato.loop]);
}

function cambiaLoop() {
  const prossimo = MODI_LOOP[(MODI_LOOP.indexOf(stato.loop) + 1) % MODI_LOOP.length];
  stato.loop = prossimo;
  salvaLoop(prossimo);
  disegnaLoop();
}

function aFineBrano() {
  /* Fine brano: applica la modalita' scelta. */
  if (stato.loop === "uno") {
    audio.currentTime = 0;
    audio.play().catch(() => { /* il browser blocca: riprova al prossimo click */ });
    return;
  }
  if (stato.loop === "coda" && stato.coda.length) {
    if (stato.indice + 1 < stato.coda.length) suona(stato.indice + 1);
    else suona(0);
    return;
  }
  successivo();
}

function precedente() {
  if (audio.currentTime > 4) { audio.currentTime = 0; return; }
  if (stato.indice > 0) suona(stato.indice - 1);
}

function aggiornaPlayer(b) {
  document.getElementById("titolo-brano").textContent = b.title || "";
  document.getElementById("artista-brano").textContent = b.artist || b.album || "";
  const cop = document.getElementById("copertina");
  if (b.thumbnail) cop.src = `/api/image?u=${encodeURIComponent(b.thumbnail)}`;
  document.getElementById("tempo-totale").textContent = tempo(b.duration || 0);
}

function aggiornaBarra() {
  const d = audio.duration || 0;
  const seek = document.getElementById("seek");
  seek.value = d ? Math.round((audio.currentTime / d) * 1000) : 0;
  document.getElementById("tempo-attuale").textContent = tempo(audio.currentTime);
}

function segnaInRiproduzione() {
  const b = stato.coda[stato.indice];
  document.querySelectorAll("tr.in-riproduzione").forEach((tr) => tr.classList.remove("in-riproduzione"));
  if (!b) return;
  document.querySelectorAll("tr[data-video]").forEach((tr) => {
    if (tr.dataset.video === b.videoId) tr.classList.add("in-riproduzione");
  });
}

function disegnaCoda() {
  listaCoda.innerHTML = stato.coda.map((b, i) => `
    <li data-idx="${i}">
      ${img(b.thumbnail, b.title)}
      <div class="testo"><div class="t">${esc(b.title)}</div><div class="a">${esc(b.artist || "")}</div></div>
    </li>`).join("");
  if (stato.indice >= 0) {
    const el = listaCoda.querySelector(`li[data-idx="${stato.indice}"]`);
    if (el) el.scrollIntoView({ block: "nearest" });
  }
}

/* ---------- eventi ---------- */
document.addEventListener("click", (e) => {
  const nav = e.target.closest(".nav-item");
  if (nav) {
    document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("attivo"));
    nav.classList.add("attivo");
    stato.vista = nav.dataset.view;
    if (stato.vista === "home") vistaHome();
    else if (stato.vista === "piaciuta") {
      if (!stato.utente) { apriModale("login"); return; }
      vistaPiaciuta();
    }
    else { document.getElementById("q").focus(); vista.innerHTML = `<p class="vuoto">Scrivi per cercare.</p>`; }
    return;
  }

  const cuore = e.target.closest("[data-piace]");
  if (cuore) {
    e.stopPropagation();
    const videoId = cuore.dataset.piace;
    const brano = elementiDi(cuore).find((x) => x.videoId === videoId) || { videoId };
    alternaMiPiace(videoId, brano);
    return;
  }

  const chip = e.target.closest(".chip");
  if (chip) {
    const q = document.getElementById("q").value.trim();
    const params = chip.dataset.params || null;
    vistaRicerca(q, params);
    return;
  }

  const card = e.target.closest(".card");
  if (card) {
    if (card.dataset.video) {
      const elementi = elementiDi(card).filter((x) => x.videoId);
      const idx = elementi.findIndex((x) => x.videoId === card.dataset.video);
      if (idx >= 0) avvia(elementi, idx);
      else avvia([{ videoId: card.dataset.video, title: (card.querySelector("h3") || {}).textContent || "" }], 0);
      return;
    }
    if (card.dataset.browse) {
      vistaDettaglio(card.dataset.browse);
    }
    return;
  }

  const lib = e.target.closest(".libreria a");
  if (lib && lib.dataset.browse) {
    vistaDettaglio(lib.dataset.browse);
    return;
  }

  const riga = e.target.closest("tr[data-video]");
  if (riga) {
    const brani = elementiDi(riga).filter((b) => b.videoId);
    const posizione = brani.findIndex((b) => b.videoId === riga.dataset.video);
    if (posizione >= 0) avvia(brani, posizione);
    else avvia([{ videoId: riga.dataset.video }], 0);
    return;
  }

  const codaItem = e.target.closest("#lista-coda li");
  if (codaItem) {
    suona(Number(codaItem.dataset.idx));
    return;
  }

  if (e.target.id === "btn-account") {
    if (stato.utente) esciAccount();
    else apriModale("login");
    return;
  }

  if (e.target.closest && e.target.closest("#modale") === e.target) chiudiModale();

  if (e.target.id === "chiudi-coda") codaEl.classList.add("nascosto");
  if (e.target.id === "btn-coda") codaEl.classList.toggle("nascosto");
});

document.getElementById("tema").addEventListener("click", cambiaTema);
document.getElementById("chiudi-modale").addEventListener("click", chiudiModale);
document.getElementById("scheda-accesso").addEventListener("click", () => {
  stato.modalita = "login"; aggiornaSchede();
});
document.getElementById("scheda-registro").addEventListener("click", () => {
  stato.modalita = "registro"; aggiornaSchede();
});
document.getElementById("form-account").addEventListener("submit", inviaAccount);

document.getElementById("form-ricerca").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = document.getElementById("q").value.trim();
  if (q) vistaRicerca(q, null);
});

document.getElementById("play").addEventListener("click", () => {
  if (!audio.src) return;
  audio.paused ? audio.play() : audio.pause();
});

document.getElementById("succ").addEventListener("click", successivo);
document.getElementById("btn-loop").addEventListener("click", cambiaLoop);
document.getElementById("prec").addEventListener("click", precedente);

document.getElementById("seek").addEventListener("input", (e) => {
  if (audio.duration) audio.currentTime = (e.target.value / 1000) * audio.duration;
});

document.getElementById("volume").addEventListener("input", (e) => {
  audio.volume = e.target.value / 100;
});

audio.addEventListener("timeupdate", aggiornaBarra);
audio.addEventListener("loadedmetadata", () => {
  if (isFinite(audio.duration)) document.getElementById("tempo-totale").textContent = tempo(audio.duration);
});
audio.addEventListener("play", () => { document.getElementById("play").textContent = "⏸"; nascondiAvvio(); });
audio.addEventListener("pause", () => { document.getElementById("play").textContent = "▶"; });
audio.addEventListener("ended", aFineBrano);
audio.addEventListener("error", () => {
  nascondiAvvio();
  if (audio.src) document.getElementById("artista-brano").textContent = "Stream non disponibile";
});

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" && e.target.type === "search") return;
  if (e.code === "Space") { e.preventDefault(); document.getElementById("play").click(); }
  if (e.code === "ArrowRight" && audio.duration) audio.currentTime = Math.min(audio.duration, audio.currentTime + 5);
  if (e.code === "ArrowLeft" && audio.duration) audio.currentTime = Math.max(0, audio.currentTime - 5);
});

/* Un qualsiasi clic sblocca l'avvio automatico bloccato dal browser. */
document.addEventListener("click", () => {
  if (audio.src && audio.paused) audio.play().then(nascondiAvvio).catch(() => { /* ignorato */ });
}, { once: true });

/* ---------- avvio ---------- */
applicaTema(temaPreferito());
stato.loop = loopSalvato();
disegnaLoop();
caricaLibreria();
vistaHome();
caricaSessione();
