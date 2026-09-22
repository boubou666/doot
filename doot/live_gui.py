"""Studio Live : jouer au clavier, quantifier, puis sauvegarder en RTTTL."""

from __future__ import annotations

import time

from . import cli, composer, live


def main() -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError:
        print("doot : Tkinter est requis pour Studio Live")
        return 4

    root = tk.Tk()
    root.title("Doot — Studio Live")
    root.geometry("700x430")
    tempo, title = tk.IntVar(value=120), tk.StringVar(value="jam-macabre")
    hits: list[live.Hit] = []
    started = [time.monotonic()]
    status = tk.StringVar(value="A Z E R T Y U = notes · Espace = nouveau take")
    preview = tk.StringVar(value="· " * 16)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Studio Live", font=("Segoe UI", 24, "bold")).pack(anchor="w")
    ttk.Label(frame, textvariable=status).pack(anchor="w", pady=(4, 20))
    ttk.Label(frame, textvariable=preview, font=("Consolas", 18)).pack(fill="x", pady=24)
    controls = ttk.Frame(frame)
    controls.pack(fill="x")
    ttk.Label(controls, text="Titre").grid(row=0, column=0)
    ttk.Entry(controls, textvariable=title).grid(row=0, column=1, padx=8)
    ttk.Label(controls, text="BPM").grid(row=0, column=2)
    ttk.Spinbox(controls, from_=40, to=300, textvariable=tempo, width=6).grid(row=0, column=3, padx=8)

    def pattern():
        return live.quantize(hits, tempo.get())

    def refresh():
        preview.set(" ".join((note or "·").upper().ljust(2) for note in pattern()))
        status.set(f"{len(hits)} frappe(s) capturee(s) · quantification au 1/16")

    def key(event):
        key_name = event.keysym.casefold()
        if key_name == "space":
            hits.clear()
            started[0] = time.monotonic()
            refresh()
        elif key_name in live.KEY_NOTES:
            hits.append(live.Hit(time.monotonic() - started[0], live.KEY_NOTES[key_name]))
            refresh()

    def save():
        try:
            source = composer.rtttl(title.get(), tempo.get(), 5, pattern())
            path = cli.paths()["melodies"] / f"{composer.safe_name(title.get())}.rtttl"
            composer.write_source(path, source)
            cli.note_succes(cli.parse_args(["--quiet"]), "studio_live", name=title.get())
            messagebox.showinfo("Take sauvegarde", str(path), parent=root)
        except (ValueError, composer.ComposerError) as exc:
            messagebox.showerror("Take impossible", str(exc), parent=root)

    ttk.Button(frame, text="Sauvegarder le take", command=save).pack(anchor="e", pady=30)
    root.bind("<KeyPress>", key)
    root.focus_force()
    root.mainloop()
    return 0
