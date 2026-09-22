"""Controle de doot depuis la zone de notification.

``pystray`` reste optionnel : les plateformes sans backend utilisable gardent
le panneau Tk compact, afin que la commande ne devienne jamais une impasse.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _spawn(*argv: str) -> None:
    kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([sys.executable, "-m", "doot", *argv], **kwargs)


def main() -> int:
    try:
        import pystray
        from PIL import Image
    except ImportError:
        from . import gui

        print("doot : backend de tray absent, ouverture du panneau compact.")
        return gui.main(compact=True)

    from . import cli, profiles

    icon_path = Path(__file__).with_name("assets") / "logo.png"
    try:
        picture = Image.open(icon_path).convert("RGBA")
    except OSError:
        from . import gui

        return gui.main(compact=True)

    def action(*argv):
        return lambda _icon, _item: _spawn(*argv)

    def quit_tray(icon, _item):
        icon.stop()

    profile_items = []
    for name in profiles.names(cli.profiles_path()):
        profile_items.append(pystray.MenuItem(
            name, action("--activate-profile", name),
        ))
    if not profile_items:
        profile_items.append(pystray.MenuItem("Aucun profil", None, enabled=False))

    menu = pystray.Menu(
        pystray.MenuItem("Doot maintenant", action("--once", "--ignore-season"), default=True),
        pystray.MenuItem("Pause 30 minutes", action("--snooze", "30m")),
        pystray.MenuItem("Pause 2 heures", action("--snooze", "2h")),
        pystray.MenuItem("Reveiller", action("--resume")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Profils", pystray.Menu(*profile_items)),
        pystray.MenuItem("Ouvrir le grimoire", action("--gui")),
        pystray.MenuItem("Arreter le daemon", action("--stop")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Fermer cette icone", quit_tray),
    )
    icon = pystray.Icon("doot", picture, "doot — controle de la crypte", menu)
    try:
        icon.run()
    except Exception as exc:
        from . import gui

        print(f"doot : zone de notification indisponible ({exc}), panneau compact.")
        return gui.main(compact=True)
    return 0
