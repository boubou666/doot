package org.doot.android;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

/** Runs doot's daemon in Python, and one doot on demand. */
public final class DootService extends Service {
    static final String ACTION_DOOT = "org.doot.android.DOOT";
    private static final String CHANNEL = "doot";
    private static final String TAG = "doot";
    private Thread daemon;

    static void start(Context context, String action) {
        Intent intent = new Intent(context, DootService.class).setAction(action);
        context.startForegroundService(intent);
    }

    @Override
    public void onCreate() {
        super.onCreate();
        NotificationManager notifications = getSystemService(NotificationManager.class);
        notifications.createNotificationChannel(
                new NotificationChannel(CHANNEL, "doot", NotificationManager.IMPORTANCE_MIN));
        Notification notification = new Notification.Builder(this, CHANNEL)
                .setSmallIcon(R.drawable.logo)
                .setContentTitle("doot")
                .setContentText("La crypte veille.")
                .build();
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else {
            startForeground(1, notification);
        }
        if (!Python.isStarted()) Python.start(new AndroidPlatform(this));
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (daemon == null) {
            daemon = run("daemon");
        }
        if (intent != null && ACTION_DOOT.equals(intent.getAction())) {
            run("once");
        }
        return START_STICKY;
    }

    private Thread run(String entry) {
        Thread thread = new Thread(() -> {
            try {
                int code = Python.getInstance().getModule("doot_android").callAttr(entry).toInt();
                Log.i(TAG, entry + " exited with " + code);
            } catch (Throwable error) {
                Log.e(TAG, entry + " failed", error);
            }
        }, "doot-" + entry);
        thread.start();
        return thread;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
