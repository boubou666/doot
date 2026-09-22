"""Petit editeur visuel de timeline pour les choregraphies Doot."""

from __future__ import annotations

from . import choreography, cli


def main() -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError:
        print("doot : Tkinter est requis pour le choregraphe")
        return 4

    root = tk.Tk()
    root.title("Doot — Choregraphe visuel")
    root.geometry("760x500")
    name = tk.StringVar(value="bal-des-os")
    at, count, formation = tk.DoubleVar(value=0), tk.IntVar(value=3), tk.StringVar(value="wave")
    cues: list[choreography.Cue] = []

    form = ttk.Frame(root, padding=16)
    form.pack(fill="both", expand=True)
    ttk.Label(form, text="Choregraphe visuel", font=("Segoe UI", 20, "bold")).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 16))
    ttk.Label(form, text="Nom").grid(row=1, column=0, sticky="w")
    ttk.Entry(form, textvariable=name, width=24).grid(row=1, column=1, sticky="ew")
    ttk.Label(form, text="Temps (s)").grid(row=2, column=0, sticky="w")
    ttk.Spinbox(form, from_=0, to=3600, increment=.5, textvariable=at, width=8).grid(row=2, column=1, sticky="w")
    ttk.Label(form, text="Doots").grid(row=2, column=2, sticky="w", padx=(12, 0))
    ttk.Spinbox(form, from_=1, to=12, textvariable=count, width=5).grid(row=2, column=3)
    ttk.Combobox(form, textvariable=formation, values=sorted(choreography.FORMATIONS), state="readonly", width=12).grid(row=2, column=4, padx=12)
    listing = tk.Listbox(form, height=14, font=("Consolas", 11))
    listing.grid(row=4, column=0, columnspan=6, sticky="nsew", pady=14)
    form.rowconfigure(4, weight=1)
    form.columnconfigure(1, weight=1)

    def refresh():
        listing.delete(0, "end")
        for cue in sorted(cues, key=lambda item: item.at):
            listing.insert("end", f"{cue.at:6.1f}s  {cue.count:2} doot(s)  {cue.formation}")

    def add():
        try:
            cues.append(choreography.validate([{"at": at.get(), "count": count.get(), "formation": formation.get()}])[0])
            refresh()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Repere impossible", str(exc), parent=root)

    def save():
        try:
            path = choreography.save(cli.data_path("choreographies", "choreographies"), name.get(), cues)
            messagebox.showinfo("Choregraphie sauvee", str(path), parent=root)
        except ValueError as exc:
            messagebox.showerror("Sauvegarde impossible", str(exc), parent=root)

    ttk.Button(form, text="Ajouter le repere", command=add).grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))
    ttk.Button(form, text="Sauvegarder", command=save).grid(row=5, column=5, sticky="e")
    root.mainloop()
    return 0
