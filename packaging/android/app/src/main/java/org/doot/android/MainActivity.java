package org.doot.android;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Starts the crypt, says whether overlays are allowed, and offers a test doot. */
public final class MainActivity extends Activity {
    private TextView status;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setGravity(Gravity.CENTER);
        column.setBackgroundColor(Color.rgb(13, 16, 23));

        ImageView logo = new ImageView(this);
        logo.setImageResource(R.drawable.logo);
        column.addView(logo, new LinearLayout.LayoutParams(320, 320));

        status = new TextView(this);
        status.setTextColor(Color.WHITE);
        status.setTextSize(22);
        status.setGravity(Gravity.CENTER);
        status.setPadding(0, 32, 0, 32);
        column.addView(status);

        Button doot = new Button(this);
        doot.setText("Doot !");
        doot.setOnClickListener(v -> DootService.start(this, DootService.ACTION_DOOT));
        column.addView(doot);

        Button allow = new Button(this);
        allow.setText("Autoriser l'affichage par-dessus les applis");
        allow.setOnClickListener(v -> {
            Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName()));
            if (intent.resolveActivity(getPackageManager()) != null) startActivity(intent);
        });
        column.addView(allow);

        setContentView(column);
        DootService.start(this, null);
        doot.requestFocus();
    }

    @Override
    protected void onResume() {
        super.onResume();
        status.setText(OverlayWindow.canDraw(this)
                ? "La crypte veille : le squelette surgira au hasard."
                : "Le squelette n'a pas le droit de s'afficher par-dessus les applis.\n"
                + "adb shell appops set org.doot.android SYSTEM_ALERT_WINDOW allow");
    }
}
