package org.doot.android;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.WindowManager;
import android.widget.ImageView;

import java.nio.ByteBuffer;
import java.util.concurrent.Callable;
import java.util.concurrent.FutureTask;

/**
 * A borderless window above every app, painted with doot's premultiplied BGRA frames.
 * Called from Python's thread; every view operation runs on the main thread.
 */
public final class OverlayWindow {
    private final Handler main = new Handler(Looper.getMainLooper());
    private final WindowManager windows;
    private final WindowManager.LayoutParams params;
    private final Bitmap bitmap;
    private final ImageView view;
    private boolean shown;

    public static boolean canDraw(Context context) {
        return Settings.canDrawOverlays(context);
    }

    public OverlayWindow(Context context, int width, int height, int x, int y) throws Exception {
        windows = context.getSystemService(WindowManager.class);
        params = new WindowManager.LayoutParams(
                width, height,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.TOP | Gravity.START;
        params.x = x;
        params.y = y;
        bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);
        view = onMain(() -> {
            ImageView image = new ImageView(context);
            image.setImageBitmap(bitmap);
            return image;
        });
    }

    /** Adds the window; throws if the system refuses it, so doot can fall back. */
    public void show() throws Exception {
        onMain(() -> {
            windows.addView(view, params);
            shown = true;
            return null;
        });
    }

    public void draw(byte[] bgra) {
        // doot's frames are B,G,R,A in memory; an ARGB_8888 bitmap is R,G,B,A.
        for (int i = 0; i + 3 < bgra.length; i += 4) {
            byte blue = bgra[i];
            bgra[i] = bgra[i + 2];
            bgra[i + 2] = blue;
        }
        main.post(() -> {
            bitmap.copyPixelsFromBuffer(ByteBuffer.wrap(bgra));
            view.invalidate();
        });
    }

    public void move(int x, int y) {
        main.post(() -> {
            params.x = x;
            params.y = y;
            if (shown) windows.updateViewLayout(view, params);
        });
    }

    public void close() {
        main.post(() -> {
            if (shown) windows.removeViewImmediate(view);
            shown = false;
        });
    }

    private <T> T onMain(Callable<T> work) throws Exception {
        if (Looper.myLooper() == Looper.getMainLooper()) return work.call();
        FutureTask<T> task = new FutureTask<>(work);
        main.post(task);
        return task.get();
    }
}
