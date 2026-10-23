package org.doot.android;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Starts the daemon at boot, and fires a doot on `org.doot.android.DOOT`. */
public final class DootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        Intent service = new Intent(context, DootService.class)
                .setAction(intent.getAction())
                .putExtra(DootService.EXTRA_ARGS, intent.getStringArrayExtra(DootService.EXTRA_ARGS));
        context.startForegroundService(service);
    }
}
