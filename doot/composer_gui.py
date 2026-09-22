"""Page autonome d'edition RTTTL, avec import et apercu audio vivant."""

from __future__ import annotations

import os
import queue
import sys
import threading
from pathlib import Path

from . import composer, melodie, sound


class ComposerApp:
    BG = "#0e0b14"
    PANEL = "#171120"
    PANEL_2 = "#20172b"
    CARD = "#261b32"
    GOLD = "#d7a84a"
    GOLD_LIGHT = "#f3d486"
    BONE = "#f2e7cf"
    MUTED = "#aa9cb4"
    EMBER = "#e76f36"

    def __init__(self, root) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.root = root
        self.score = composer.empty_score()
        self.voice = 0
        self.pattern = self.score[0]
        self.clipboard: list | None = None
        self.cells: dict[tuple[int, str], object] = {}
        self.grid_mode = True
        self.current_path: Path | None = None
        self._updating_source = False
        self._loading = False
        self._preview_after = None
        self._preview_generation = 0
        self._preview_events: queue.Queue = queue.Queue()
        self._preview_files: set[Path] = set()
        self._closed = False

        root.title("doot — compositeur RTTTL")
        root.geometry("1180x820")
        root.minsize(940, 690)
        root.configure(bg=self.BG)
        root.protocol("WM_DELETE_WINDOW", self._close)
        self._style()
        self._build()
        self._refresh_grid()
        self.root.after(80, self._poll_preview)

    def _style(self) -> None:
        style = self.ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", background=self.BG, foreground=self.BONE,
                        font=("Segoe UI", 10))
        style.configure("TEntry", fieldbackground="#120e19", foreground=self.BONE,
                        insertcolor=self.BONE, bordercolor="#4a365a", padding=7)
        style.configure("TCombobox", fieldbackground="#120e19", foreground=self.BONE,
                        arrowcolor=self.GOLD, bordercolor="#4a365a", padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", "#120e19")],
                  foreground=[("readonly", self.BONE)])
        style.configure("TCheckbutton", background=self.PANEL, foreground=self.BONE,
                        indicatorcolor="#120e19")
        style.map("TCheckbutton", background=[("active", self.PANEL)],
                  indicatorcolor=[("selected", self.EMBER)])
        style.configure("Editor.TButton", background="#382745", foreground=self.BONE,
                        borderwidth=0, padding=(11, 8))
        style.map("Editor.TButton", background=[("active", "#4c3560")])
        style.configure("Listen.TButton", background=self.EMBER, foreground="#fff8e8",
                        borderwidth=0, padding=(15, 9), font=("Segoe UI", 10, "bold"))
        style.map("Listen.TButton", background=[("active", "#f28b51")])

    def _build(self) -> None:
        header = self.tk.Frame(self.root, bg=self.BG)
        header.pack(fill="x", padx=24, pady=(18, 9))
        self.tk.Label(
            header, text="COMPOSITEUR RTTTL", bg=self.BG, fg=self.GOLD,
            font=("Segoe UI", 10, "bold"), anchor="w",
        ).pack(fill="x")
        self.tk.Label(
            header, text="Écris, importe et écoute sans quitter la partition.",
            bg=self.BG, fg=self.BONE, font=("Georgia", 23, "bold"), anchor="w",
        ).pack(fill="x", pady=(4, 3))
        self.tk.Label(
            header,
            text="Jusqu’à 8 voix et des notes de 1, 2, 4 ou 8 pas ; clic droit pour changer la durée.",
            bg=self.BG, fg=self.MUTED, font=("Segoe UI", 10), anchor="w",
        ).pack(fill="x")

        toolbar = self.tk.Frame(self.root, bg=self.PANEL)
        toolbar.pack(fill="x", padx=24, pady=(0, 9), ipady=8)
        self.ttk.Button(toolbar, text="Nouveau", style="Editor.TButton",
                        command=self._new).pack(side="left", padx=(9, 5))
        self.ttk.Button(toolbar, text="Importer…", style="Editor.TButton",
                        command=self._import).pack(side="left", padx=5)
        self.ttk.Button(toolbar, text="Enregistrer", style="Editor.TButton",
                        command=self._save).pack(side="left", padx=5)
        self.ttk.Button(toolbar, text="Enregistrer sous…", style="Editor.TButton",
                        command=self._save_as).pack(side="left", padx=5)
        self.ttk.Button(toolbar, text="Charger la source dans la grille",
                        style="Editor.TButton", command=self._source_to_grid).pack(
                            side="left", padx=5,
                        )
        self.live = self.tk.BooleanVar(value=True)
        self.ttk.Checkbutton(
            toolbar, text="Aperçu automatique", variable=self.live,
            command=self._live_changed,
        ).pack(side="right", padx=(8, 10))
        self.ttk.Button(toolbar, text="ÉCOUTER", style="Listen.TButton",
                        command=self._listen_now).pack(side="right", padx=5)

        metadata = self.tk.Frame(self.root, bg=self.PANEL_2)
        metadata.pack(fill="x", padx=24, pady=(0, 9), ipady=8)
        self.title = self.tk.StringVar(value="ma-melodie")
        self.tempo = self.tk.StringVar(value="120")
        self.octave = self.tk.StringVar(value="5")
        for label, variable, width in (
            ("Nom", self.title, 24), ("BPM", self.tempo, 7),
        ):
            self.tk.Label(metadata, text=label, bg=self.PANEL_2, fg=self.GOLD_LIGHT,
                          font=("Segoe UI", 9, "bold")).pack(
                              side="left", padx=(12, 5),
                          )
            self.ttk.Entry(metadata, textvariable=variable, width=width).pack(side="left")
        self.tk.Label(metadata, text="Octave", bg=self.PANEL_2, fg=self.GOLD_LIGHT,
                      font=("Segoe UI", 9, "bold")).pack(side="left", padx=(12, 5))
        self.ttk.Combobox(
            metadata, textvariable=self.octave,
            values=tuple(str(value) for value in range(1, 9)),
            state="readonly", width=4,
        ).pack(side="left")
        self.voice_label = self.tk.StringVar(value="Voix 1/1")
        self.tk.Label(
            metadata, textvariable=self.voice_label, bg=self.PANEL_2,
            fg=self.GOLD_LIGHT, font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(16, 7))
        for text, command in (
            ("−", self._remove_voice), ("+", self._add_voice),
            ("Suivante", self._next_voice), ("Copier", self._copy_voice),
            ("Coller", self._paste_voice),
        ):
            self.ttk.Button(
                metadata, text=text, style="Editor.TButton", command=command,
            ).pack(side="left", padx=2)
        for variable in (self.title, self.tempo, self.octave):
            variable.trace_add("write", self._metadata_changed)

        panes = self.tk.PanedWindow(
            self.root, orient="vertical", bg=self.BG, bd=0,
            sashwidth=7, sashrelief="flat",
        )
        panes.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        grid_panel = self.tk.Frame(panes, bg=self.PANEL_2)
        source_panel = self.tk.Frame(panes, bg=self.PANEL)
        panes.add(grid_panel, minsize=300, height=390)
        panes.add(source_panel, minsize=150)
        self._build_grid(grid_panel)
        self._build_source(source_panel)

        self.status = self.tk.StringVar(
            value="Pose une note : l’aperçu démarre après une courte pause.",
        )
        self.tk.Label(
            self.root, textvariable=self.status, bg=self.BG, fg=self.MUTED,
            font=("Consolas", 9), anchor="w", justify="left",
        ).pack(fill="x", padx=27, pady=(0, 13))

    def _build_grid(self, parent) -> None:
        self.grid_title = self.tk.StringVar(value="GRILLE — MODE VISUEL")
        self.tk.Label(
            parent, textvariable=self.grid_title, bg=self.PANEL_2, fg=self.GOLD_LIGHT,
            font=("Segoe UI", 10, "bold"), anchor="w",
        ).grid(row=0, column=0, columnspan=composer.STEPS + 1,
               sticky="ew", padx=12, pady=(10, 7))
        self.tk.Label(parent, text="NOTE", bg=self.PANEL_2, fg=self.MUTED,
                      font=("Consolas", 8, "bold"), width=6).grid(row=1, column=0)
        for step in range(composer.STEPS):
            self.tk.Label(
                parent, text=str(step + 1), bg=self.PANEL_2,
                fg=self.GOLD if step % 4 == 0 else self.MUTED,
                font=("Consolas", 8, "bold"), width=2,
            ).grid(row=1, column=step + 1, padx=1)
        for row, (label, note) in enumerate(composer.PITCHES, 2):
            self.tk.Label(
                parent, text=label, bg=self.PANEL_2, fg=self.BONE,
                font=("Consolas", 8, "bold"), width=6, anchor="e",
            ).grid(row=row, column=0, padx=(8, 5), pady=1, sticky="e")
            for step in range(composer.STEPS):
                cell = self.tk.Button(
                    parent, text="", width=2, height=1, bd=0,
                    bg=self.CARD, activebackground=self.GOLD,
                    fg="#fff8e8", activeforeground="#fff8e8", cursor="hand2",
                    command=lambda s=step, n=note: self._toggle(s, n),
                )
                cell.grid(row=row, column=step + 1, padx=1, pady=1, sticky="nsew")
                cell.bind("<Button-3>", lambda _event, s=step, n=note:
                          self._cycle_duration(s, n))
                self.cells[(step, note)] = cell
        for column in range(1, composer.STEPS + 1):
            parent.grid_columnconfigure(column, weight=1)

    def _build_source(self, parent) -> None:
        self.tk.Label(
            parent, text="SOURCE RTTTL — ÉDITION LIBRE ET POLYPHONIQUE",
            bg=self.PANEL, fg=self.GOLD_LIGHT, font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(9, 5))
        self.source = self.tk.Text(
            parent, height=7, wrap="none", undo=True, bg="#0b0910", fg=self.BONE,
            insertbackground=self.GOLD_LIGHT, selectbackground="#4c3560",
            relief="flat", padx=10, pady=8, font=("Consolas", 10),
        )
        self.source.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.source.bind("<<Modified>>", self._source_modified)
        self.source.edit_modified(False)

    def _values(self) -> tuple[str, int, int]:
        try:
            return self.title.get(), int(self.tempo.get()), int(self.octave.get())
        except ValueError as exc:
            raise composer.ComposerError(
                "le tempo et l'octave doivent etre des nombres"
            ) from exc

    def _toggle(self, step: int, note: str) -> None:
        if not self.grid_mode:
            return
        composer.toggle(self.pattern, step, note)
        self._refresh_grid()

    def _select_voice(self, index: int) -> None:
        self.voice = max(0, min(index, len(self.score) - 1))
        self.pattern = self.score[self.voice]
        self.voice_label.set(f"Voix {self.voice + 1}/{len(self.score)}")
        self._refresh_grid()

    def _next_voice(self) -> None:
        self._select_voice((self.voice + 1) % len(self.score))

    def _add_voice(self) -> None:
        if len(self.score) >= 8:
            self.status.set("Huit voix maximum.")
            return
        self.score.append(composer.empty_pattern())
        self._select_voice(len(self.score) - 1)

    def _remove_voice(self) -> None:
        if len(self.score) == 1:
            self.status.set("La partition doit garder une voix.")
            return
        del self.score[self.voice]
        self._select_voice(min(self.voice, len(self.score) - 1))

    def _copy_voice(self) -> None:
        self.clipboard = composer.copy_voice(self.pattern)
        self.status.set(f"Voix {self.voice + 1} copiée.")

    def _paste_voice(self) -> None:
        if self.clipboard is None:
            self.status.set("Copie d’abord une voix.")
            return
        self.score[self.voice] = composer.copy_voice(self.clipboard)
        self.pattern = self.score[self.voice]
        self._refresh_grid()

    def _cycle_duration(self, step: int, note: str) -> None:
        if not self.grid_mode:
            return
        current = self.pattern[step]
        current_note, units = (current if isinstance(current, tuple) else (current, 1))
        if current_note != note:
            composer.toggle(self.pattern, step, note)
            units = 1
        composer.set_duration(self.pattern, step, {1: 2, 2: 4, 4: 8, 8: 1}[units])
        self._refresh_grid()

    def _refresh_grid(self) -> None:
        for (step, note), cell in self.cells.items():
            current = self.pattern[step]
            current_note, units = (current if isinstance(current, tuple) else (current, 1))
            selected = current_note == note
            cell.configure(text=("♪" if units == 1 else str(units)) if selected else "",
                           bg=self.EMBER if selected else self.CARD)
        if self._loading or not self.grid_mode:
            return
        try:
            title, tempo, octave = self._values()
            text = composer.rtttl_score(title, tempo, octave, self.score)
        except composer.ComposerError as exc:
            self._set_source("")
            self.status.set(str(exc))
            self._cancel_preview()
            return
        self._set_source(text)
        self.status.set("Grille synchronisée avec la source RTTTL.")
        self._schedule_preview()

    def _set_source(self, text: str) -> None:
        self._updating_source = True
        try:
            self.source.delete("1.0", "end")
            self.source.insert("1.0", text)
            self.source.edit_modified(False)
        finally:
            self._updating_source = False

    def _source_text(self) -> str:
        return self.source.get("1.0", "end-1c")

    def _source_modified(self, _event=None) -> None:
        if not self.source.edit_modified():
            return
        self.source.edit_modified(False)
        if self._updating_source:
            return
        self._set_grid_mode(False)
        try:
            morceau = composer.validate_source(self._source_text())
        except composer.ComposerError as exc:
            self.status.set(f"Source incomplète : {exc}")
            self._cancel_preview()
            return
        self.status.set(
            f"Source valide — {len(morceau.voices)} voix, {morceau.tempo:g} BPM."
        )
        self._schedule_preview()

    def _metadata_changed(self, *_args) -> None:
        if not self._loading and self.grid_mode:
            self._refresh_grid()

    def _set_grid_mode(self, enabled: bool) -> None:
        self.grid_mode = enabled
        state = "normal" if enabled else "disabled"
        for cell in self.cells.values():
            cell.configure(state=state, cursor="hand2" if enabled else "arrow")
        self.grid_title.set(
            "GRILLE — MODE VISUEL" if enabled
            else "GRILLE VERROUILLÉE — LA SOURCE EST CANONIQUE"
        )

    def _load_draft(self, draft: composer.Draft) -> None:
        self._load_score(draft.title, draft.tempo, draft.octave,
                         [list(draft.pattern)])

    def _load_score(self, title: str, tempo: int, octave: int,
                    score: list[list]) -> None:
        self._loading = True
        try:
            self.title.set(title)
            self.tempo.set(str(tempo))
            self.octave.set(str(octave))
            self.score = score
            self.voice = 0
            self.pattern = self.score[0]
            self.voice_label.set(f"Voix 1/{len(self.score)}")
            self._set_grid_mode(True)
        finally:
            self._loading = False
        self._refresh_grid()

    def _source_to_grid(self) -> None:
        try:
            title, tempo, octave, score = composer.parse_score(self._source_text())
        except composer.ComposerError as exc:
            self.status.set(f"Conversion impossible : {exc}")
            return
        self._load_score(title, tempo, octave, score)
        self.status.set("Source chargée dans la grille.")

    def _new(self) -> None:
        self.current_path = None
        self._loading = True
        try:
            self.title.set("ma-melodie")
            self.tempo.set("120")
            self.octave.set("5")
            self.score = composer.empty_score()
            self.voice = 0
            self.pattern = self.score[0]
            self.voice_label.set("Voix 1/1")
            self._set_grid_mode(True)
            self._set_source("")
        finally:
            self._loading = False
        self._refresh_grid()

    def _import(self) -> None:
        path = self.filedialog.askopenfilename(
            title="Importer une sonnerie RTTTL",
            filetypes=(("Sonneries RTTTL", "*.rtttl"), ("Tous les fichiers", "*.*")),
        )
        if not path:
            return
        source_path = Path(path)
        try:
            text = source_path.read_text(encoding="utf-8")
            morceau = composer.validate_source(text)
        except (OSError, UnicodeError, composer.ComposerError) as exc:
            self.status.set(f"Import impossible : {exc}")
            return
        self.current_path = source_path
        self._set_source(text)
        self._set_grid_mode(False)
        try:
            title, tempo, octave, score = composer.parse_score(text)
        except composer.ComposerError:
            detail = f"{len(morceau.voices)} voix — édition fidèle dans la source."
        else:
            self._load_score(title, tempo, octave, score)
            detail = "compatible avec la grille — conversion disponible."
        self.status.set(f"Importée : {source_path.name} · {detail}")
        self._schedule_preview()

    def _save(self) -> None:
        if self.current_path is None:
            self._save_as()
            return
        if not self.messagebox.askyesno(
                "Écraser la sonnerie ?",
                f"Remplacer {self.current_path.name} par la source actuelle ?"):
            return
        self._write(self.current_path)

    def _save_as(self) -> None:
        from . import cli

        try:
            morceau = composer.validate_source(self._source_text())
            initial = composer.safe_name(morceau.name or self.title.get()) + ".rtttl"
        except composer.ComposerError as exc:
            self.status.set(f"Sauvegarde impossible : {exc}")
            return
        directory = cli.paths()["melodies"]
        directory.mkdir(parents=True, exist_ok=True)
        path = self.filedialog.asksaveasfilename(
            title="Enregistrer la sonnerie RTTTL",
            initialdir=str(directory), initialfile=initial,
            defaultextension=".rtttl",
            filetypes=(("Sonneries RTTTL", "*.rtttl"),),
            confirmoverwrite=True,
        )
        if path:
            self._write(Path(path))

    def _write(self, path: Path) -> None:
        try:
            composer.write_source(path, self._source_text())
        except (OSError, composer.ComposerError) as exc:
            self.status.set(f"Sauvegarde impossible : {exc}")
            return
        self.current_path = path
        self.status.set(f"Enregistrée : {path}")

    def _live_changed(self) -> None:
        if self.live.get():
            self._schedule_preview()
        else:
            self._cancel_preview()
            sound.stop_all()
            self.status.set("Aperçu automatique coupé ; le bouton Écouter reste disponible.")

    def _cancel_preview(self) -> None:
        self._preview_generation += 1
        if self._preview_after is not None:
            try:
                self.root.after_cancel(self._preview_after)
            except Exception:
                pass
            self._preview_after = None

    def _schedule_preview(self) -> None:
        self._cancel_preview()
        if not self.live.get():
            return
        generation = self._preview_generation
        self._preview_after = self.root.after(
            500, lambda: self._start_preview(generation),
        )

    def _listen_now(self) -> None:
        self._cancel_preview()
        self._start_preview(self._preview_generation)

    def _start_preview(self, generation: int) -> None:
        from . import cli

        self._preview_after = None
        source = self._source_text()
        try:
            morceau = composer.validate_source(source)
        except composer.ComposerError as exc:
            self.status.set(f"Aperçu impossible : {exc}")
            return
        destination = (
            cli.paths()["data"] /
            f"composer-live-{os.getpid()}-{generation}.wav"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.status.set("Rendu de l’aperçu…")

        def render() -> None:
            try:
                melodie.render(destination, morceau)
            except Exception as exc:
                if not self._closed:
                    self._preview_events.put((generation, None, str(exc)))
            else:
                if self._closed:
                    try:
                        destination.unlink()
                    except OSError:
                        pass
                else:
                    self._preview_events.put((generation, destination, ""))

        threading.Thread(target=render, daemon=True).start()

    def _poll_preview(self) -> None:
        try:
            while True:
                generation, path, error = self._preview_events.get_nowait()
                if generation != self._preview_generation:
                    if path is not None:
                        try:
                            path.unlink()
                        except OSError:
                            pass
                    continue
                if error:
                    self.status.set(f"Aperçu impossible : {error}")
                    continue
                sound.stop_all()
                for old_path in self._preview_files:
                    try:
                        old_path.unlink()
                    except OSError:
                        pass
                self._preview_files.clear()
                self._preview_files.add(path)
                handle = sound.play_async(path)
                self.status.set(
                    "Aperçu en cours." if handle is not None
                    else "Aucun lecteur audio disponible pour l’aperçu."
                )
        except queue.Empty:
            pass
        self.root.after(80, self._poll_preview)

    def _close(self) -> None:
        self._closed = True
        self._cancel_preview()
        sound.stop_all()
        for path in self._preview_files:
            try:
                path.unlink()
            except OSError:
                pass
        self.root.destroy()


def main() -> int:
    """Ouvre la page autonome ; renvoie 4 si Tkinter est indisponible."""
    try:
        import tkinter as tk
    except ImportError:
        print("doot : le compositeur demande tkinter.", file=sys.stderr)
        return 4
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"doot : impossible d'ouvrir le compositeur : {exc}", file=sys.stderr)
        return 4
    ComposerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
