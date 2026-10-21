package com.freesic.player;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.text.InputType;
import android.view.KeyEvent;
import android.view.Menu;
import android.view.MenuItem;
import android.view.ViewGroup;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.TextView;

/**
 * Contenitore WebView per il player musicale.
 *
 * L'app non contiene il motore di ricerca: usa il backend Python che gira
 * sul computer (o su un altro dispositivo della stessa rete). L'indirizzo
 * del server e' salvato nelle preferenze e puo' essere cambiato dal menu.
 */
public class MainActivity extends Activity {

    private static final String PREFS = "musica";
    private static final String CHIAVE_URL = "url";
    private static final String URL_PREDEFINITA = "http://10.0.2.2:8000/";

    private WebView web;
    private SharedPreferences prefs;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);           // la libreria usa localStorage
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowContentAccess(false);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setUserAgentString(s.getUserAgentString() + " MusicaApp/1.0");
        web.setBackgroundColor(Color.parseColor("#0F0F0F"));
        web.setOverScrollMode(ViewGroup.OVER_SCROLL_NEVER);
        web.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request == null || request.isForMainFrame()) {
                    mostraErrore();
                }
            }
        });

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#0F0F0F"));
        root.addView(web, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);

        String salvato = prefs.getString(CHIAVE_URL, null);
        if (salvato == null) {
            chiediIndirizzo();
        } else {
            carica(salvato);
        }
    }

    private void carica(String indirizzo) {
        String url = indirizzo.trim();
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            url = "http://" + url;
        }
        if (!url.endsWith("/")) {
            url = url + "/";
        }
        web.loadUrl(url);
    }

    private void mostraErrore() {
        TextView errore = new TextView(this);
        errore.setTextColor(Color.parseColor("#F1F1F1"));
        errore.setTextSize(16);
        errore.setPadding(48, 48, 48, 48);
        errore.setText("Server non raggiungibile.\n\nAvvia il player sul computer con ./start.sh e poi scegli l'indirizzo dal menu 'Indirizzo server'.\n\n"
                + "Esempio: http://192.168.1.10:8000/");
        FrameLayout root = (FrameLayout) web.getParent();
        if (root != null && root.getChildCount() < 2) {
            root.addView(errore, new FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        }
    }

    private void chiediIndirizzo() {
        final EditText campo = new EditText(this);
        campo.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        campo.setText(URL_PREDEFINITA);
        campo.setSingleLine(true);
        int margine = (int) (24 * getResources().getDisplayMetrics().density);
        FrameLayout contenitore = new FrameLayout(this);
        contenitore.setPadding(margine, margine / 2, margine, 0);
        contenitore.addView(campo, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT));

        new AlertDialog.Builder(this)
                .setTitle("Indirizzo del server")
                .setMessage("Inserisci l'indirizzo del player che gira sul computer (stessa rete Wi-Fi).")
                .setView(contenitore)
                .setCancelable(false)
                .setPositiveButton("Apri", (dialog, which) -> {
                    String valore = campo.getText().toString();
                    prefs.edit().putString(CHIAVE_URL, valore).apply();
                    carica(valore);
                })
                .show();
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        int id = item.getItemId();
        if (id == R.id.indirizzo) {
            chiediIndirizzo();
            return true;
        }
        if (id == R.id.ricarica) {
            web.reload();
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
    protected void onPause() {
        super.onPause();
        if (web != null) {
            web.onPause();
            web.pauseTimers();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) {
            web.resumeTimers();
            web.onResume();
        }
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.loadUrl("about:blank");
            web.destroy();
        }
        super.onDestroy();
    }
}
