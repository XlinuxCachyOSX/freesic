package com.freesic.player;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import fi.iki.elonen.NanoHTTPD;
import fi.iki.elonen.NanoHTTPD.ResponseException;

/**
 * Server locale dell'app: serve l'interfaccia web e risponde alle stesse API
 * che sul computer fornisce Python, ma tutto dentro il telefono.
 */
public final class Server extends NanoHTTPD {

    public interface Asset {
        byte[] leggi(String nome) throws IOException;
    }

    public interface Archivio {
        String leggi();

        void scrivi(String testo);
    }

    private static final String UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            + "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

    private final Asset asset;
    private final Archivio archivio;

    public Server(final Asset asset, final Archivio archivio) {
        super("127.0.0.1", 0);
        this.asset = asset;
        this.archivio = archivio;
    }

    @Override
    public Response serve(final IHTTPSession sessione) {
        final String uri = sessione.getUri();
        try {
            if (!uri.startsWith("/api/")) return statico(uri);
            return api(uri, sessione);
        } catch (Exception e) {
            try {
                return json(Response.Status.INTERNAL_ERROR,
                        new JSONObject().put("detail", messaggio(e)));
            } catch (Exception ex) {
                return newFixedLengthResponse(Response.Status.INTERNAL_ERROR,
                        "text/plain; charset=utf-8", messaggio(e));
            }
        }
    }

    private static String messaggio(final Exception e) {
        final String m = e.getMessage();
        return m == null || m.isEmpty() ? e.getClass().getSimpleName() : m;
    }

    // ------------------------------------------------------------------
    // File statici
    // ------------------------------------------------------------------
    private Response statico(final String uri) {
        String nome = uri.equals("/") ? "index.html" : uri.substring(1);
        if (nome.contains("..")) return testo(Response.Status.FORBIDDEN, "no");
        byte[] dati;
        try {
            dati = asset.leggi(nome);
        } catch (IOException e) {
            dati = null;
        }
        if (dati == null) return testo(Response.Status.NOT_FOUND, "Non trovato");
        final Response risposta = NanoHTTPD.newFixedLengthResponse(
                Response.Status.OK, tipo(nome), new ByteArrayInputStream(dati), dati.length);
        risposta.addHeader("Cache-Control", "no-cache");
        return risposta;
    }

    private static String tipo(final String nome) {
        if (nome.endsWith(".html")) return "text/html; charset=utf-8";
        if (nome.endsWith(".js")) return "application/javascript; charset=utf-8";
        if (nome.endsWith(".css")) return "text/css; charset=utf-8";
        if (nome.endsWith(".svg")) return "image/svg+xml";
        if (nome.endsWith(".png")) return "image/png";
        if (nome.endsWith(".ico")) return "image/x-icon";
        return "application/octet-stream";
    }

    // ------------------------------------------------------------------
    // API
    // ------------------------------------------------------------------
    private Response api(final String uri, final IHTTPSession sessione) throws Exception {
        final String metodo = sessione.getMethod().name();
        if (uri.equals("/api/health")) {
            return json(Response.Status.OK, new JSONObject()
                    .put("ok", true)
                    .put("servizio", "FreeSic Android")
                    .put("versione", "1.2.0"));
        }
        if (uri.equals("/api/home")) {
            return json(Response.Status.OK, Api.home());
        }
        if (uri.equals("/api/search")) {
            final Map<String, List<String>> p = sessione.getParameters();
            return json(Response.Status.OK, Api.search(param(p, "q"), param(p, "params")));
        }
        if (uri.startsWith("/api/browse/")) {
            return json(Response.Status.OK, Api.browse(uri.substring("/api/browse/".length())));
        }
        if (uri.startsWith("/api/track/")) {
            return json(Response.Status.OK, Api.track(uri.substring("/api/track/".length())));
        }
        if (uri.startsWith("/api/stream/")) {
            return audio(uri.substring("/api/stream/".length()), sessione);
        }
        if (uri.equals("/api/image")) {
            final Map<String, List<String>> p = sessione.getParameters();
            return immagine(param(p, "u"));
        }
        if (uri.equals("/api/auth/me")) {
            return json(Response.Status.OK, new JSONObject()
                    .put("autenticato", true).put("utente", "Locale"));
        }
        if (uri.startsWith("/api/auth/")) {
            final String azione = uri.substring("/api/auth/".length());
            if (azione.equals("logout")) {
                return json(Response.Status.OK, new JSONObject()
                        .put("autenticato", false).put("utente", ""));
            }
            return json(Response.Status.OK, new JSONObject()
                    .put("autenticato", true).put("utente", "Locale"));
        }
        if (uri.equals("/api/mipiace")) {
            if (metodo.equals("POST")) {
                final JSONObject corpo = corpo(sessione);
                final JSONObject brano = new JSONObject();
                for (final String chiave : new String[]{"videoId", "title", "artist", "album",
                        "thumbnail", "duration"}) {
                    if (corpo.has(chiave)) brano.put(chiave, corpo.get(chiave));
                }
                return json(Response.Status.OK, new JSONObject().put("items", piaciuti(brano)));
            }
            return json(Response.Status.OK, new JSONObject().put("items", listaPiaciuti()));
        }
        if (uri.startsWith("/api/mipiace/")) {
            return json(Response.Status.OK, new JSONObject()
                    .put("items", togliPiaciuto(uri.substring("/api/mipiace/".length()))));
        }
        if (uri.equals("/api/playlist/piaciuta")) {
            final JSONArray brani = listaPiaciuti();
            String copertina = "";
            if (brani.length() > 0) copertina = brani.getJSONObject(0).optString("thumbnail", "");
            return json(Response.Status.OK, new JSONObject()
                    .put("browseId", "freesic-piaciuta")
                    .put("title", "Piaciuta")
                    .put("subtitle", brani.length() == 1
                            ? "1 brano" : brani.length() + " brani")
                    .put("type", "playlist")
                    .put("thumbnail", copertina)
                    .put("items", brani));
        }
        return json(Response.Status.NOT_FOUND, new JSONObject().put("detail", "Percorso sconosciuto"));
    }

    private static String param(final Map<String, List<String>> p, final String nome) {
        final List<String> valori = p.get(nome);
        return valori == null || valori.isEmpty() ? "" : valori.get(0);
    }

    private static JSONObject corpo(final IHTTPSession sessione) throws IOException,
            ResponseException, JSONException {
        final Map<String, String> mappa = new HashMap<>();
        sessione.parseBody(mappa);
        final String testo = mappa.get("postData");
        return testo == null || testo.isEmpty() ? new JSONObject() : new JSONObject(testo);
    }

    // ------------------------------------------------------------------
    // Audio con supporto Range (per andare avanti e indietro nel brano)
    // ------------------------------------------------------------------
    private Response audio(final String videoId, final IHTTPSession sessione) throws Exception {
        final String[] stream = Api.stream(videoId);
        final HttpURLConnection conn = (HttpURLConnection) new URL(stream[0]).openConnection();
        conn.setRequestProperty("User-Agent", UA);
        final String range = sessione.getHeaders().get("range");
        if (range != null) conn.setRequestProperty("Range", range);
        final int codice = conn.getResponseCode();
        final InputStream flusso = codice >= 400 ? conn.getErrorStream() : conn.getInputStream();
        final String lunghezza = conn.getHeaderField("Content-Length");
        final long dimensione = lunghezza == null ? -1 : Long.parseLong(lunghezza);
        final String mime = conn.getContentType() != null ? conn.getContentType() : stream[1];

        Response.Status stato = codice == 206
                ? Response.Status.PARTIAL_CONTENT : Response.Status.OK;
        final Response risposta = NanoHTTPD.newFixedLengthResponse(
                stato, mime, flusso, dimensione);
        risposta.addHeader("Accept-Ranges", "bytes");
        final String contentRange = conn.getHeaderField("Content-Range");
        if (contentRange != null) risposta.addHeader("Content-Range", contentRange);
        risposta.addHeader("Cache-Control", "no-store");
        return risposta;
    }

    // ------------------------------------------------------------------
    // Copertine (evita problemi di referer)
    // ------------------------------------------------------------------
    private Response immagine(final String indirizzo) throws IOException {
        if (!indirizzo.startsWith("https://") && !indirizzo.startsWith("http://")) {
            return testo(Response.Status.BAD_REQUEST, "indirizzo non valido");
        }
        final HttpURLConnection conn = (HttpURLConnection) new URL(indirizzo).openConnection();
        conn.setRequestProperty("User-Agent", UA);
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(20000);
        final int codice = conn.getResponseCode();
        if (codice >= 400) return testo(Response.Status.NOT_FOUND, "immagine non disponibile");
        final InputStream in = conn.getInputStream();
        final ByteArrayOutputStream out = new ByteArrayOutputStream();
        final byte[] buffer = new byte[8192];
        int letti;
        while ((letti = in.read(buffer)) != -1) out.write(buffer, 0, letti);
        final byte[] dati = out.toByteArray();
        final Response risposta = NanoHTTPD.newFixedLengthResponse(
                Response.Status.OK, conn.getContentType() == null ? "image/jpeg" : conn.getContentType(),
                new ByteArrayInputStream(dati), dati.length);
        risposta.addHeader("Cache-Control", "max-age=86400");
        return risposta;
    }

    // ------------------------------------------------------------------
    // Piaciuti (salvati sul telefono)
    // ------------------------------------------------------------------
    private JSONArray listaPiaciuti() {
        try {
            return new JSONArray(archivio.leggi());
        } catch (JSONException | NullPointerException e) {
            return new JSONArray();
        }
    }

    private void salva(final JSONArray lista) {
        archivio.scrivi(lista.toString());
    }

    private JSONArray piaciuti(final JSONObject brano) {
        final JSONArray lista = listaPiaciuti();
        final String videoId = brano.optString("videoId", "");
        for (int i = 0; i < lista.length(); i++) {
            if (videoId.equals(lista.optJSONObject(i).optString("videoId", ""))) return lista;
        }
        final JSONArray nuova = new JSONArray();
        nuova.put(brano);
        for (int i = 0; i < lista.length(); i++) { try { nuova.put(lista.get(i)); } catch (Exception ignored) {} }
        salva(nuova);
        return nuova;
    }

    private JSONArray togliPiaciuto(final String videoId) {
        final JSONArray lista = listaPiaciuti();
        final JSONArray nuova = new JSONArray();
        for (int i = 0; i < lista.length(); i++) {
            final JSONObject o = lista.optJSONObject(i);
            if (!videoId.equals(o.optString("videoId", ""))) nuova.put(o);
        }
        salva(nuova);
        return nuova;
    }

    // ------------------------------------------------------------------
    // Risposte
    // ------------------------------------------------------------------
    private static Response json(final Response.Status stato, final JSONObject corpo) {
        final byte[] dati = corpo.toString().getBytes(StandardCharsets.UTF_8);
        final Response risposta = NanoHTTPD.newFixedLengthResponse(
                stato, "application/json; charset=utf-8", new ByteArrayInputStream(dati), dati.length);
        risposta.addHeader("Cache-Control", "no-store");
        return risposta;
    }

    private static Response testo(final Response.Status stato, final String testo) {
        return NanoHTTPD.newFixedLengthResponse(stato, "text/plain; charset=utf-8", testo);
    }
}
