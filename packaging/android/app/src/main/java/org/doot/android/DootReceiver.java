package org.doot.android;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/** Fires a doot on `org.doot.android.DOOT`. */
public final class DootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        Intent service = new Intent(context, DootService.class)
                .setAction(intent.getAction())
                .putExtra(DootService.EXTRA_ARGS, intent.getStringArrayExtra(DootService.EXTRA_ARGS));
        try {
            context.startForegroundService(service);
        } catch (IllegalStateException refused) {
            Log.w("doot", "foreground service refused from the background", refused);
        }
    }
}
