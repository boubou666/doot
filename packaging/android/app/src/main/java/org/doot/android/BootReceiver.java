package org.doot.android;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Starts the daemon at boot. */
public final class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            DootService.start(context, null);
        }
    }
}
