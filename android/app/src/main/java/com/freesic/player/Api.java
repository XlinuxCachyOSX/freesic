package com.freesic.player;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import org.schabi.newpipe.extractor.InfoItem;
import org.schabi.newpipe.extractor.Image;
import org.schabi.newpipe.extractor.NewPipe;
import org.schabi.newpipe.extractor.ServiceList;
import org.schabi.newpipe.extractor.channel.ChannelExtractor;
import org.schabi.newpipe.extractor.channel.ChannelInfo;
import org.schabi.newpipe.extractor.channel.ChannelInfoItem;
import org.schabi.newpipe.extractor.channel.tabs.ChannelTabExtractor;
import org.schabi.newpipe.extractor.downloader.Downloader;
import org.schabi.newpipe.extractor.exceptions.ExtractionException;
import org.schabi.newpipe.extractor.linkhandler.ListLinkHandler;
import org.schabi.newpipe.extractor.localization.Localization;
import org.schabi.newpipe.extractor.playlist.PlaylistInfo;
import org.schabi.newpipe.extractor.playlist.PlaylistInfoItem;
import org.schabi.newpipe.extractor.search.SearchExtractor;
import org.schabi.newpipe.extractor.stream.AudioStream;
import org.schabi.newpipe.extractor.stream.StreamInfo;
import org.schabi.newpipe.extractor.stream.StreamInfoItem;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Motore dell'app: cerca e riproduce la musica direttamente dal telefono
 * usando NewPipe Extractor. Non serve nessun server sul computer.
 */
public final class Api {

    private Api() {
    }

    private static final long DURATA_CACHE = 15 * 60 * 1000L;
    private static final Map<String, Object[]> CACHE = new HashMap<>();

    private static final String[][] FILTRI = {
            {"Tutto", ""},
            {"Brani", "music_songs"},
            {"Playlist", "music_albums"},
            {"Artisti", "music_artists"},
    };

    public static void init(final Downloader downloader) {
        NewPipe.init(downloader, new Localization("it", "IT"));
    }

    // ------------------------------------------------------------------
    // Cache
    // ------------------------------------------------------------------
    @SuppressWarnings("unchecked")
    private static <T> T daCache(final String chiave) {
        synchronized (CACHE) {
            final Object[] voce = CACHE.get(chiave);
            if (voce == null) return null;
            if ((Long) voce[1] < System.currentTimeMillis()) {
                CACHE.remove(chiave);
                return null;
            }
            return (T) voce[0];
        }
    }

    private static void inCache(final String chiave, final Object valore) {
        synchronized (CACHE) {
            if (CACHE.size() > 60) CACHE.clear();
            CACHE.put(chiave, new Object[]{valore, System.currentTimeMillis() + DURATA_CACHE});
        }
    }

    // ------------------------------------------------------------------
    // Home
    // ------------------------------------------------------------------
    public static JSONObject home() throws IOException, ExtractionException, JSONException {
        final JSONObject cache = daCache("home");
        if (cache != null) return cache;

        final String[][] scaffali = {
                {"successi del momento", "Hit del momento"},
                {"nuove uscite musica", "Novità"},
                {"musica italiana", "Musica italiana"},
        };
        final JSONArray uscita = new JSONArray();
        for (final String[] s : scaffali) {
            final List<InfoItem> items = cerca(s[0], "");
            if (items.isEmpty()) continue;
            final JSONArray brani = new JSONArray();
            for (final InfoItem it : items) brani.put(daItem(it));
            uscita.put(new JSONObject().put("title", s[1]).put("items", brani));
        }
        final JSONObject risposta = new JSONObject().put("shelves", uscita);
        inCache("home", risposta);
        return risposta;
    }

    // ------------------------------------------------------------------
    // Ricerca
    // ------------------------------------------------------------------
    private static List<InfoItem> cerca(final String q, final String filtro)
            throws IOException, ExtractionException {
        final List<String> fl = filtro == null || filtro.isEmpty()
                ? Collections.<String>emptyList()
                : Collections.singletonList(filtro);
        final SearchExtractor estrattore = ServiceList.YouTube.getSearchExtractor(q, fl, "");
        estrattore.fetchPage();
        final java.util.ArrayList<InfoItem> tutti = new java.util.ArrayList<InfoItem>();
        org.schabi.newpipe.extractor.ListExtractor.InfoItemsPage<InfoItem> pag
                = estrattore.getInitialPage();
        if (pag.getItems() != null) tutti.addAll(pag.getItems());
        int giri = 0;
        while (tutti.size() < 50 && pag.getNextPage() != null && giri < 4) {
            try {
                pag = estrattore.getPage(pag.getNextPage());
                if (pag.getItems() == null || pag.getItems().isEmpty()) break;
                tutti.addAll(pag.getItems());
                giri++;
            } catch (Throwable t) {
                break;
            }
        }
        if (q == null || q.trim().isEmpty()) return tutti;
        final String qq = q.toLowerCase(java.util.Locale.ITALY);
        final java.util.HashSet<String> parole = new java.util.HashSet<String>();
        String[] pezzi = qq.split("[^a-z0-9]+");
        for (String x : pezzi) {
            if (x.length() >= 3) parole.add(x);
        }
        if (parole.isEmpty()) return tutti;
        final java.util.ArrayList<InfoItem> filtrati = new java.util.ArrayList<InfoItem>();
        for (InfoItem it : tutti) {
            if (it == null) continue;
            final String nome = (it.getName() == null ? "" : it.getName())
                    .toLowerCase(java.util.Locale.ITALY);
            String up = "";
            try {
                java.lang.reflect.Method m = it.getClass().getMethod("getUploaderName");
                Object o = m.invoke(it);
                if (o != null) up = o.toString().toLowerCase(java.util.Locale.ITALY);
            } catch (Throwable ignored) {
            }
            boolean ok = false;
            for (String p : parole) {
                if (nome.contains(p) || up.contains(p)) { ok = true; break; }
            }
            if (ok) filtrati.add(it);
        }
        return filtrati.isEmpty() ? java.util.Collections.<InfoItem>emptyList() : filtrati;
    }

    public static JSONObject search(final String q, final String filtro)
            throws IOException, ExtractionException, JSONException {
        final JSONObject risposta = new JSONObject();
        final JSONArray filtri = new JSONArray();
        for (final String[] f : FILTRI) {
            filtri.put(new JSONObject()
                    .put("label", f[0])
                    .put("params", f[1])
                    .put("selected", f[1].equals(filtro == null ? "" : filtro)));
        }
        risposta.put("filters", filtri);

        final List<InfoItem> items = cerca(q, filtro);
        final JSONArray sezioni = new JSONArray();
        if (!items.isEmpty()) {
            if (filtro != null && !filtro.isEmpty()) {
                sezioni.put(sezione(nomeTipo(filtro), filtro, items));
            } else {
                final JSONArray video = new JSONArray();
                final JSONArray playlist = new JSONArray();
                final JSONArray canali = new JSONArray();
                for (final InfoItem it : items) {
                    if (it instanceof StreamInfoItem) video.put(daItem(it));
                    else if (it instanceof PlaylistInfoItem) playlist.put(daItem(it));
                    else if (it instanceof ChannelInfoItem) canali.put(daItem(it));
                }
                if (video.length() > 0) {
                    sezioni.put(new JSONObject().put("title", "Brani")
                            .put("type", "song").put("items", video));
                }
                if (playlist.length() > 0) {
                    sezioni.put(new JSONObject().put("title", "Playlist")
                            .put("type", "playlist").put("items", playlist));
                }
                if (canali.length() > 0) {
                    sezioni.put(new JSONObject().put("title", "Artisti")
                            .put("type", "artist").put("items", canali));
                }
            }
        }
        risposta.put("sections", sezioni);
        return risposta;
    }

    private static String nomeTipo(final String filtro) {
        if ("music_songs".equals(filtro)) return "Brani";
        if ("music_albums".equals(filtro)) return "Playlist";
        if ("music_artists".equals(filtro)) return "Artisti";
        if ("videos".equals(filtro)) return "Video";
        if ("playlists".equals(filtro)) return "Playlist";
        if ("channels".equals(filtro)) return "Artisti";
        return "Risultati";
    }

    private static JSONObject sezione(final String titolo, final String tipo,
                                      final List<InfoItem> items) throws JSONException {
        final JSONArray array = new JSONArray();
        for (final InfoItem it : items) array.put(daItem(it));
        return new JSONObject().put("title", titolo).put("type", tipo).put("items", array);
    }

    // ------------------------------------------------------------------
    // Album / playlist / artista
    // ------------------------------------------------------------------
    public static JSONObject browse(final String id)
            throws IOException, ExtractionException, JSONException {
        String url = decodifica(id);
        if (url == null) throw new ExtractionException("Indirizzo non valido");
        // gli indirizzi di YouTube Music vanno letti dal sito normale
        url = url.replace("music.youtube.com", "www.youtube.com");
        final JSONObject cache = daCache("browse:" + url);
        if (cache != null) return cache;

        final JSONObject risposta = new JSONObject();
        final JSONArray items = new JSONArray();

        if (url.contains("list=") || url.contains("/playlist")) {
            final PlaylistInfo info = PlaylistInfo.getInfo(ServiceList.YouTube, url);
            for (final InfoItem it : info.getRelatedItems()) {
                if (it instanceof StreamInfoItem) items.put(daItem(it));
            }
            risposta.put("browseId", id)
                    .put("title", senzaPrefisso(info.getName()))
                    .put("subtitle", testoBrani(items.length()))
                    .put("type", "playlist")
                    .put("thumbnail", miniatura(info.getThumbnails()))
                    .put("description", "")
                    .put("items", items);
        } else {
            final ChannelInfo info = ChannelInfo.getInfo(ServiceList.YouTube, url);
            try {
                final ChannelExtractor estrattore = ServiceList.YouTube.getChannelExtractor(url);
                estrattore.fetchPage();
                for (final ListLinkHandler tab : estrattore.getTabs()) {
                    if (!tab.getUrl().contains("/videos")) continue;
                    final ChannelTabExtractor video =
                            ServiceList.YouTube.getChannelTabExtractor(tab);
                    video.fetchPage();
                    for (final InfoItem it : video.getInitialPage().getItems()) {
                        if (it instanceof StreamInfoItem) items.put(daItem(it));
                    }
                    break;
                }
            } catch (ExtractionException e) {
                // artista senza elenco video: mostro comunque la scheda
            }
            risposta.put("browseId", id)
                    .put("title", senzaPrefisso(info.getName()))
                    .put("subtitle", "Artista")
                    .put("type", "artist")
                    .put("thumbnail", miniatura(info.getAvatars()))
                    .put("description", "")
                    .put("items", items);
        }
        inCache("browse:" + url, risposta);
        return risposta;
    }

    // ------------------------------------------------------------------
    // Brano e stream audio
    // ------------------------------------------------------------------
    public static JSONObject track(final String videoId)
            throws IOException, ExtractionException, JSONException {
        final StreamInfo info = StreamInfo.getInfo(ServiceList.YouTube, indirizzoVideo(videoId));
        return new JSONObject()
                .put("videoId", videoId)
                .put("title", info.getName())
                .put("artist", info.getUploaderName())
                .put("album", "")
                .put("duration", info.getDuration())
                .put("thumbnail", miniatura(info.getThumbnails()));
    }

    /** Restituisce {url, mime} dello stream audio migliore. */
    public static String[] stream(final String videoId) throws IOException, ExtractionException {
        final String cache = daCache("stream:" + videoId);
        if (cache != null) return cache.split("\n", 2);
        final StreamInfo info = StreamInfo.getInfo(ServiceList.YouTube, indirizzoVideo(videoId));
        AudioStream scelta = null;
        long punteggio = Long.MIN_VALUE;
        for (final AudioStream s : info.getAudioStreams()) {
            if (s.getUrl() == null || s.getUrl().isEmpty()) continue;
            final String mime = s.getFormat() == null ? "" : s.getFormat().getMimeType();
            long p = s.getAverageBitrate();
            if (mime != null && mime.contains("mp4")) p += 1_000_000; // preferito da Android
            if (p > punteggio) {
                punteggio = p;
                scelta = s;
            }
        }
        if (scelta == null) throw new ExtractionException("Nessuno stream audio disponibile");
        final String mime = scelta.getFormat() == null ? "audio/mp4" : scelta.getFormat().getMimeType();
        final String valore = scelta.getUrl() + "\n" + mime;
        inCache("stream:" + videoId, valore);
        return new String[]{scelta.getUrl(), mime};
    }

    // ------------------------------------------------------------------
    // Conversione in JSON per l'interfaccia
    // ------------------------------------------------------------------
    private static JSONObject daItem(final InfoItem it) throws JSONException {
        final JSONObject o = new JSONObject();
        if (it instanceof StreamInfoItem) {
            final StreamInfoItem s = (StreamInfoItem) it;
            final String id = idVideo(s.getUrl());
            final long durata = s.getDuration();
            o.put("id", id);
            o.put("type", "song");
            o.put("videoId", id);
            o.put("browseId", JSONObject.NULL);
            o.put("title", s.getName());
            o.put("artists", new JSONArray().put(s.getUploaderName()));
            o.put("artist", s.getUploaderName());
            o.put("album", "");
            o.put("year", "");
            o.put("subtitle", s.getUploaderName());
            o.put("duration", durata > 0 ? durata : JSONObject.NULL);
            o.put("durationText", durata > 0 ? tempo(durata) : "");
            o.put("plays", s.getViewCount());
            o.put("playsText", s.getViewCount() > 0 ? conta(s.getViewCount()) : "");
            o.put("listeners", JSONObject.NULL);
            o.put("views", JSONObject.NULL);
            o.put("thumbnail", miniatura(s.getThumbnails()));
            o.put("section", JSONObject.NULL);
        } else if (it instanceof PlaylistInfoItem) {
            final PlaylistInfoItem p = (PlaylistInfoItem) it;
            o.put("id", p.getUrl());
            o.put("type", "playlist");
            o.put("videoId", JSONObject.NULL);
            o.put("browseId", codifica(p.getUrl()));
            o.put("title", p.getName());
            o.put("artists", new JSONArray().put(p.getUploaderName()));
            o.put("artist", p.getUploaderName());
            o.put("album", "");
            o.put("year", "");
            o.put("subtitle", p.getUploaderName());
            o.put("duration", JSONObject.NULL);
            o.put("durationText", "");
            o.put("plays", JSONObject.NULL);
            o.put("playsText", "");
            o.put("listeners", JSONObject.NULL);
            o.put("views", testoBrani((int) p.getStreamCount()));
            o.put("thumbnail", miniatura(p.getThumbnails()));
            o.put("section", JSONObject.NULL);
        } else if (it instanceof ChannelInfoItem) {
            final ChannelInfoItem c = (ChannelInfoItem) it;
            o.put("id", c.getUrl());
            o.put("type", "artist");
            o.put("videoId", JSONObject.NULL);
            o.put("browseId", codifica(c.getUrl()));
            o.put("title", c.getName());
            o.put("artists", new JSONArray().put(c.getName()));
            o.put("artist", c.getName());
            o.put("album", "");
            o.put("year", "");
            o.put("subtitle", c.getDescription());
            o.put("duration", JSONObject.NULL);
            o.put("durationText", "");
            o.put("plays", JSONObject.NULL);
            o.put("playsText", "");
            o.put("listeners", JSONObject.NULL);
            o.put("views", JSONObject.NULL);
            o.put("thumbnail", miniatura(c.getThumbnails()));
            o.put("section", JSONObject.NULL);
        }
        return o;
    }

    // ------------------------------------------------------------------
    // Utilità
    // ------------------------------------------------------------------
    private static String indirizzoVideo(final String videoId) {
        return "https://www.youtube.com/watch?v=" + videoId;
    }

    private static String idVideo(final String url) {
        if (url == null) return "";
        final int v = url.indexOf("v=");
        if (v >= 0) {
            final String resto = url.substring(v + 2);
            final int e = resto.indexOf('&');
            return e >= 0 ? resto.substring(0, e) : resto;
        }
        final int barra = url.lastIndexOf('/');
        return barra >= 0 ? url.substring(barra + 1) : url;
    }

    private static String codifica(final String url) {
        return "u:" + Base64.getUrlEncoder().withoutPadding()
                .encodeToString(url.getBytes(StandardCharsets.UTF_8));
    }

    private static String decodifica(final String id) {
        if (id == null || !id.startsWith("u:")) return null;
        try {
            return new String(Base64.getUrlDecoder().decode(id.substring(2)), StandardCharsets.UTF_8);
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    private static String miniatura(final List<Image> immagini) {
        if (immagini == null || immagini.isEmpty()) return "";
        Image scelta = immagini.get(0);
        int migliore = Integer.MAX_VALUE;
        for (final Image i : immagini) {
            final int distanza = Math.abs(i.getWidth() - 320);
            if (distanza < migliore) {
                migliore = distanza;
                scelta = i;
            }
        }
        return scelta.getUrl();
    }

    private static String senzaPrefisso(final String nome) {
        if (nome == null) return "";
        for (final String p : new String[]{"Album – ", "Album - ", "Playlist – ", "Playlist - "}) {
            if (nome.startsWith(p)) return nome.substring(p.length());
        }
        return nome;
    }

    private static String testoBrani(final int n) {
        return n == 1 ? "1 brano" : n + " brani";
    }

    static String tempo(final long secondi) {
        if (secondi <= 0) return "";
        final long m = secondi / 60;
        final long s = secondi % 60;
        return String.format(Locale.ITALY, "%d:%02d", m, s);
    }

    static String conta(final long n) {
        if (n >= 1_000_000_000L) {
            return String.format(Locale.ITALY, "%.1f Mld di visualizzazioni", n / 1_000_000_000.0);
        }
        if (n >= 1_000_000L) {
            return String.format(Locale.ITALY, "%.1f Mln di visualizzazioni", n / 1_000_000.0);
        }
        if (n >= 1_000L) {
            return String.format(Locale.ITALY, "%.0f mila visualizzazioni", n / 1_000.0);
        }
        return n + " visualizzazioni";
    }
}
