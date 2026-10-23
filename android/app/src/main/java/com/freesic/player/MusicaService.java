package com.freesic.player;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

public class MusicaService extends Service {
    public static final String CANALE = "freesic_media";
    public static final int ID = 1;

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        creaCanale();
        Intent apri = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, apri, PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder nb = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(this, CANALE)
                : new Notification.Builder(this);
        nb.setContentTitle("FreeSic")
           .setContentText("Riproduzione in corso")
           .setSmallIcon(R.mipmap.ic_launcher)
           .setContentIntent(pi)
           .setOngoing(true)
           .setVisibility(Notification.VISIBILITY_PUBLIC);
        Notification n = nb.build();
        startForeground(ID, n);
        return START_NOT_STICKY;
    }

    private void creaCanale() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel c = new NotificationChannel(CANALE, "Musica FreeSic", NotificationManager.IMPORTANCE_LOW);
            c.setDescription("Controlli riproduzione");
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(c);
        }
    }

    @Override
    public void onDestroy() {
        stopForeground(true);
        super.onDestroy();
    }
}
