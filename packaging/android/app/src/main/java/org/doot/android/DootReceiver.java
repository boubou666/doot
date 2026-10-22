package org.doot.android;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Starts the daemon at boot, and fires a doot on `org.doot.android.DOOT`. */
public final class DootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        DootService.start(context, intent.getAction());
    }
}
