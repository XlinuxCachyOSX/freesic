package com.freesic.player;

import org.schabi.newpipe.extractor.downloader.Downloader;
import org.schabi.newpipe.extractor.downloader.Request;
import org.schabi.newpipe.extractor.downloader.Response;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** Downloader per NewPipe basato su HttpURLConnection (nessuna dipendenza esterna). */
public final class DownloaderImpl extends Downloader {

    private static final String UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            + "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

    @Override
    public Response execute(final Request request) throws IOException {
        final HttpURLConnection conn = (HttpURLConnection) new URL(request.url()).openConnection();
        conn.setRequestMethod(request.httpMethod());
        conn.setConnectTimeout(20000);
        conn.setReadTimeout(30000);
        conn.setInstanceFollowRedirects(true);

        final Map<String, List<String>> intestazioni = request.headers();
        boolean agente = false;
        for (final Map.Entry<String, List<String>> voce : intestazioni.entrySet()) {
            if (voce.getKey() == null) continue;
            if ("User-Agent".equalsIgnoreCase(voce.getKey())) agente = true;
            // HttpURLConnection decomprime da solo: non va richiesto il gzip
            if ("Accept-Encoding".equalsIgnoreCase(voce.getKey())) continue;
            if ("Host".equalsIgnoreCase(voce.getKey())
                    || "Connection".equalsIgnoreCase(voce.getKey())
                    || "Content-Length".equalsIgnoreCase(voce.getKey())) continue;
            for (final String valore : voce.getValue()) {
                conn.setRequestProperty(voce.getKey(), valore);
            }
        }
        if (!agente) conn.setRequestProperty("User-Agent", UA);

        final byte[] corpo = request.dataToSend();
        if (corpo != null && corpo.length > 0 && !"GET".equals(request.httpMethod())) {
            conn.setDoOutput(true);
            conn.setFixedLengthStreamingMode(corpo.length);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(corpo);
            }
        }

        final int codice = conn.getResponseCode();
        final InputStream flusso = codice >= 400 ? conn.getErrorStream() : conn.getInputStream();
        final String testo = flusso == null ? "" : new String(leggi(flusso), StandardCharsets.UTF_8);

        final Map<String, List<String>> risposta = new HashMap<>();
        for (final Map.Entry<String, List<String>> voce : conn.getHeaderFields().entrySet()) {
            if (voce.getKey() != null) risposta.put(voce.getKey(), voce.getValue());
        }
        if (true) {
            System.out.println("[debug] " + request.httpMethod() + " " + request.url()
                    + " -> " + codice + " len=" + testo.length());
            System.out.println("[debug] inizio: "
                    + testo.substring(0, Math.min(300, testo.length())).replace("\n", " "));
        }
        return new Response(codice, conn.getResponseMessage(), risposta, testo, conn.getURL().toString());
    }

    private static byte[] leggi(final InputStream in) throws IOException {
        final ByteArrayOutputStream out = new ByteArrayOutputStream();
        final byte[] buffer = new byte[8192];
        int letti;
        while ((letti = in.read(buffer)) != -1) out.write(buffer, 0, letti);
        return out.toByteArray();
    }
}
