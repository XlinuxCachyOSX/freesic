package com.freesic.player;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.Menu;
import android.view.MenuItem;
import android.view.ViewGroup;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.FrameLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

import fi.iki.elonen.NanoHTTPD;

/**
 * FreeSic autonoma: l'app contiene tutto (interfaccia + motore di ricerca e
 * riproduzione). Non serve nessun server sul computer.
 */
public class MainActivity extends Activity {

    private WebView web;
    private Server server;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        try {
            android.content.Intent svc = new android.content.Intent(this, MusicaService.class);
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                startForegroundService(svc);
            } else {
                startService(svc);
            }
        } catch (Throwable ignored) {}

        Api.init(new DownloaderImpl());

        controllaAggiornamenti(false);

        final SharedPreferences prefs = getSharedPreferences("freesic", MODE_PRIVATE);
        server = new Server(new Server.Asset() {
            @Override
            public byte[] leggi(String nome) throws IOException {
                try (InputStream in = getAssets().open(nome)) {
                    final ByteArrayOutputStream out = new ByteArrayOutputStream();
                    final byte[] buffer = new byte[8192];
                    int letti;
                    while ((letti = in.read(buffer)) != -1) out.write(buffer, 0, letti);
                    return out.toByteArray();
                }
            }
        }, new Server.Archivio() {
            @Override
            public String leggi() {
                return prefs.getString("piaciuta", "[]");
            }

            @Override
            public void scrivi(String testo) {
                prefs.edit().putString("piaciuta", testo).apply();
            }
        });

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowContentAccess(false);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setUserAgentString(s.getUserAgentString() + " FreeSic/1.2");
        web.setBackgroundColor(Color.parseColor("#0F0F0F"));
        web.setOverScrollMode(ViewGroup.OVER_SCROLL_NEVER);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#0F0F0F"));
        root.addView(web, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);

        try {
            server.start(NanoHTTPD.SOCKET_READ_TIMEOUT, false);
            int porta = server.getListeningPort();
            int tentativi = 0;
            while (porta <= 0 && tentativi < 150) {
                try {
                    Thread.sleep(10);
                } catch (InterruptedException ignored) {
                }
                porta = server.getListeningPort();
                tentativi++;
            }
            if (porta <= 0) {
                porta = 0;
            }
            web.loadUrl("http://127.0.0.1:" + porta + "/");
        } catch (IOException e) {
            TextView errore = new TextView(this);
            errore.setTextColor(Color.parseColor("#F1F1F1"));
            errore.setTextSize(16);
            errore.setPadding(48, 48, 48, 48);
            errore.setText("Non riesco ad avviare il motore musicale interno.\n\n" + e.getMessage());
            root.addView(errore, new FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        }
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.ricarica) {
            web.reload();
            return true;
        }
        if (item.getItemId() == R.id.aggiorna) {
            controllaAggiornamenti(true);
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && web != null && web.canGoBack()) {
            web.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.loadUrl("about:blank");
            web.destroy();
        }
        if (server != null) server.stop();
        super.onDestroy();
    }

    private void controllaAggiornamenti(final boolean manuale) {
        final SharedPreferences prefs = getSharedPreferences("freesic", MODE_PRIVATE);
        if (!manuale) {
            long ultimo = prefs.getLong("ultimoControllo", 0);
            if (System.currentTimeMillis() - ultimo < 12L * 60 * 60 * 1000) return;
        }
        new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    URL u = new URL("https://raw.githubusercontent.com/XlinuxCachyOSX/freesic/main/update.json");
                    HttpURLConnection c = (HttpURLConnection) u.openConnection();
                    c.setConnectTimeout(6000);
                    c.setReadTimeout(6000);
                    c.setRequestProperty("User-Agent", "FreeSic");
                    if (c.getResponseCode() != 200) return;
                    InputStream in = c.getInputStream();
                    ByteArrayOutputStream fuori = new ByteArrayOutputStream();
                    byte[] buf = new byte[4096];
                    int letti;
                    while ((letti = in.read(buf)) != -1) fuori.write(buf, 0, letti);
                    in.close();
                    prefs.edit().putLong("ultimoControllo", System.currentTimeMillis()).apply();
                    JSONObject j = new JSONObject(new String(fuori.toByteArray(), "UTF-8"));
                    final int nuova = j.optInt("versionCode", 0);
                    PackageInfo pi = getPackageManager().getPackageInfo(getPackageName(), 0);
                    if (nuova <= pi.versionCode) {
                        if (manuale) {
                            runOnUiThread(new Runnable() {
                                @Override
                                public void run() {
                                    new AlertDialog.Builder(MainActivity.this)
                                            .setTitle("FreeSic aggiornato")
                                            .setMessage("Hai già l'ultima versione (" + versione() + ").")
                                            .setPositiveButton("OK", null)
                                            .show();
                                }
                            });
                        }
                        return;
                    }
                    final String link = j.optString("url");
                    final String note = j.optString("note", "");
                    final String nome = j.optString("versionName", "");
                    runOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            new AlertDialog.Builder(MainActivity.this)
                                    .setTitle("Aggiornamento disponibile: " + nome)
                                    .setMessage(note + "\n\nVuoi aggiornare ora?")
                                    .setPositiveButton("Aggiorna", new android.content.DialogInterface.OnClickListener() {
                                        @Override
                                        public void onClick(android.content.DialogInterface d, int w) {
                                            try {
                                                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(link)));
                                            } catch (Exception ignored) {
                                            }
                                        }
                                    })
                                    .setNegativeButton("Resta senza aggiornare", null)
                                    .show();
                        }
                    });
                } catch (Exception ignored) {
                    if (manuale) {
                        runOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                new AlertDialog.Builder(MainActivity.this)
                                        .setTitle("Controllo non riuscito")
                                        .setMessage("Nessuna connessione o server non raggiungibile.")
                                        .setPositiveButton("OK", null)
                                        .show();
                            }
                        });
                    }
                }
            }
        }).start();
    }

    private String versione() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception e) {
            return "";
        }
    }
}
