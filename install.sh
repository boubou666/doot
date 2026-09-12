#!/usr/bin/env bash
# Installe doot pour l'utilisateur courant (Linux, y compris Arch, et macOS).
#
#   ./install.sh                 # installe + demarrage automatique a la session
#   ./install.sh --no-autostart  # installe seulement la commande `doot`
#   ./install.sh --min 300 --max 1800
#   ./install.sh --burst-min 2 --burst-max 5   # plusieurs doots d'affilee
#   ./install.sh --burst-min 2 --burst-max 5 --formation canon
#
# Aucun droit root, aucune dependance Python : tout est dans la stdlib.
set -euo pipefail

APP_NAME="doot"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$DATA_HOME/$APP_NAME/app"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Dossier de donnees de doot, qui n'est pas celui du code : sur macOS c'est
# Application Support quand le code va dans ~/.local/share.
if [ "$(uname -s)" = "Darwin" ]; then
    RECORD_DIR="$HOME/Library/Application Support/$APP_NAME"
else
    RECORD_DIR="$DATA_HOME/$APP_NAME"
fi

AUTOSTART=1
MIN_SECONDS=600
MAX_SECONDS=3600
BURST_MIN=1
BURST_MAX=1
BURST_DELAY=0.6
FORMATION=random

while [ $# -gt 0 ]; do
    case "$1" in
        --no-autostart) AUTOSTART=0; shift ;;
        --min) MIN_SECONDS="$2"; shift 2 ;;
        --max) MAX_SECONDS="$2"; shift 2 ;;
        --burst-min) BURST_MIN="$2"; shift 2 ;;
        --burst-max) BURST_MAX="$2"; shift 2 ;;
        --burst-delay) BURST_DELAY="$2"; shift 2 ;;
        --formation) FORMATION="$2"; shift 2 ;;
        -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
        *) echo "option inconnue : $1" >&2; exit 2 ;;
    esac
done

say()  { printf '  %s\n' "$*"; }
head_() { printf '\n\033[1m%s\033[0m\n' "$*"; }

# Les bornes de salve sont comparees puis recopiees telles quelles dans la
# fiche JSON : une valeur qui n'est pas un nombre casserait l'une ou l'autre
# loin d'ici, avec un message qui ne dirait pas d'ou elle vient.
for couple in "--burst-min:$BURST_MIN" "--burst-max:$BURST_MAX"; do
    case "${couple#*:}" in
        ''|*[!0-9]*) echo "${couple%%:*} attend un entier : ${couple#*:}" >&2; exit 2 ;;
    esac
done
case "$BURST_DELAY" in
    ''|*[!0-9.]*|*.*.*) echo "--burst-delay attend un nombre : $BURST_DELAY" >&2; exit 2 ;;
esac
case "$FORMATION" in
    random|canon) ;;
    *) echo "--formation attend random ou canon : $FORMATION" >&2; exit 2 ;;
esac

# Les drapeaux de salve ne sont ecrits que s'ils changent quelque chose : sans
# eux, la commande engendree reste exactement celle d'avant les salves.
SALVE_OPTS=""
if [ "$BURST_MAX" -gt 1 ]; then
    SALVE_OPTS="--burst-min $BURST_MIN --burst-max $BURST_MAX --burst-delay $BURST_DELAY "
fi
FORMATION_OPTS=""
if [ "$FORMATION" != "random" ]; then
    FORMATION_OPTS="--formation $FORMATION "
fi

head_ "doot - installation"

# ------------------------------------------------------------ python ---------
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)'; then
            PYTHON="$(command -v "$candidate")"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    say "Python 3.8+ est introuvable. Installe-le puis relance :"
    say "  Arch/Manjaro  : sudo pacman -S python tk"
    say "  Debian/Ubuntu : sudo apt install python3 python3-tk"
    say "  Fedora        : sudo dnf install python3 python3-tkinter"
    say "  macOS         : brew install python-tk"
    exit 1
fi
say "python      : $PYTHON ($("$PYTHON" -c 'import platform; print(platform.python_version())'))"

# ------------------------------------------------------------ tkinter --------
if ! "$PYTHON" -c 'import tkinter' >/dev/null 2>&1; then
    say "tkinter     : MANQUANT (l'overlay ne s'affichera pas)"
    if   command -v pacman  >/dev/null 2>&1; then say "  -> sudo pacman -S tk"
    elif command -v apt     >/dev/null 2>&1; then say "  -> sudo apt install python3-tk"
    elif command -v dnf     >/dev/null 2>&1; then say "  -> sudo dnf install python3-tkinter"
    elif command -v zypper  >/dev/null 2>&1; then say "  -> sudo zypper install python3-tk"
    elif command -v brew    >/dev/null 2>&1; then say "  -> brew install python-tk"
    fi
    say "  (l'installation continue, tu pourras l'ajouter apres)"
else
    say "tkinter     : OK"
fi

# ------------------------------------------------------------- audio ---------
if [ "$(uname -s)" = "Darwin" ]; then
    say "audio       : afplay (integre a macOS)"
else
    PLAYER=""
    for p in pw-play paplay aplay ffplay play mpv cvlc; do
        if command -v "$p" >/dev/null 2>&1; then PLAYER="$p"; break; fi
    done
    if [ -n "$PLAYER" ]; then
        say "audio       : $PLAYER"
    else
        say "audio       : aucun lecteur trouve (doot restera muet)"
        command -v pacman >/dev/null 2>&1 && say "  -> sudo pacman -S alsa-utils    (ou pipewire-audio / libpulse)"
    fi
fi

# ------------------------------------------------------------ fichiers -------
head_ "Copie des fichiers"

# Un daemon deja lance continuerait avec l'ancien code : on l'arrete, et on le
# relance en fin d'installation s'il tournait.
DAEMON_TOURNAIT=0
if [ -f "$RECORD_DIR/doot.pid" ]; then
    DAEMON_PID="$(cat "$RECORD_DIR/doot.pid" 2>/dev/null || true)"
    if [ -n "$DAEMON_PID" ] && kill -0 "$DAEMON_PID" 2>/dev/null; then
        kill "$DAEMON_PID" 2>/dev/null || true
        rm -f "$RECORD_DIR/doot.pid"
        DAEMON_TOURNAIT=1
        say "daemon      : arrete (pid $DAEMON_PID) le temps de la copie"
    fi
fi

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR" "$BIN_DIR"
cp -R "$SRC_DIR/doot" "$APP_DIR/doot"
say "code        : $APP_DIR/doot"

cat > "$BIN_DIR/doot" <<EOF
#!/usr/bin/env bash
# Lanceur genere par install.sh
export PYTHONPATH="$APP_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$PYTHON" -m doot "\$@"
EOF
chmod +x "$BIN_DIR/doot"
say "commande    : $BIN_DIR/doot"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) say "ATTENTION   : $BIN_DIR n'est pas dans ton PATH"
       say "  -> ajoute  export PATH=\"\$HOME/.local/bin:\$PATH\"  a ton ~/.bashrc / ~/.zshrc" ;;
esac

# Fiche d'installation, relue par `doot --update`.
COMMIT=""
if [ -d "$SRC_DIR/.git" ] && command -v git >/dev/null 2>&1; then
    COMMIT="$(git -C "$SRC_DIR" rev-parse HEAD 2>/dev/null || true)"
fi
mkdir -p "$RECORD_DIR"
cat > "$RECORD_DIR/install.json" <<EOF
{
  "source": "$SRC_DIR",
  "commit": "$COMMIT",
  "min": $MIN_SECONDS,
  "max": $MAX_SECONDS,
  "burst_min": $BURST_MIN,
  "burst_max": $BURST_MAX,
  "burst_delay": $BURST_DELAY,
  "formation": "$FORMATION",
  "autostart": $([ "$AUTOSTART" -eq 1 ] && echo true || echo false),
  "app_dir": "$APP_DIR",
  "bin_dir": "$BIN_DIR",
  "python": "$PYTHON",
  "platform": "$(uname -s)",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
say "fiche       : $RECORD_DIR/install.json"

# --------------------------------------------------------- demarrage ---------
if [ "$AUTOSTART" -eq 1 ]; then
    head_ "Demarrage automatique"
    # Le plist veut un <string> par mot, la ou systemd et .desktop prennent la
    # ligne entiere : la meme salve s'ecrit donc deux fois, pas une.
    SALVE_PLIST=""
    if [ -n "$SALVE_OPTS" ]; then
        SALVE_PLIST="
        <string>--burst-min</string><string>$BURST_MIN</string>
        <string>--burst-max</string><string>$BURST_MAX</string>
        <string>--burst-delay</string><string>$BURST_DELAY</string>"
    fi
    if [ "$FORMATION" != "random" ]; then
        SALVE_PLIST="$SALVE_PLIST
        <string>--formation</string><string>$FORMATION</string>"
    fi

    if [ "$(uname -s)" = "Darwin" ]; then
        PLIST="$HOME/Library/LaunchAgents/com.doot.skeleton.plist"
        mkdir -p "$(dirname "$PLIST")"
        cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.doot.skeleton</string>
    <key>ProgramArguments</key>
    <array>
        <string>$BIN_DIR/doot</string>
        <string>--min</string><string>$MIN_SECONDS</string>
        <string>--max</string><string>$MAX_SECONDS</string>$SALVE_PLIST
        <string>--quiet</string>
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ProcessType</key><string>Interactive</string>
</dict>
</plist>
EOF
        launchctl unload "$PLIST" >/dev/null 2>&1 || true
        launchctl load "$PLIST"
        say "LaunchAgent : $PLIST (charge)"
    elif command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
        UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
        mkdir -p "$UNIT_DIR"

        # default.target demarre avec le gestionnaire utilisateur, avant que la
        # session ne publie DISPLAY et WAYLAND_DISPLAY : doot n'avait alors
        # aucun ecran ou dessiner. Plasma publie ces variables en meme temps que
        # plasma-workspace.target, sans les ordonner face a
        # graphical-session.target, d'ou l'accroche specifique quand elle
        # existe.
        # is-active et pas list-unit-files : jusqu'a systemd 245 inclus,
        # list-unit-files renvoie 0 meme sans correspondance, donc le test
        # serait toujours vrai et on ecrirait une cible inexistante. is-active
        # repond en plus a la bonne question : non pas si la cible est sur le
        # disque, mais si elle a demarre cette session.
        CIBLE="graphical-session.target"
        if systemctl --user is-active --quiet plasma-workspace.target; then
            CIBLE="plasma-workspace.target"
        fi

        cat > "$UNIT_DIR/doot.service" <<EOF
[Unit]
Description=doot - squelette trompettiste saisonnier
After=$CIBLE
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$BIN_DIR/doot --min $MIN_SECONDS --max $MAX_SECONDS $SALVE_OPTS$FORMATION_OPTS--quiet
Restart=on-failure
RestartSec=30

[Install]
WantedBy=$CIBLE
EOF
        systemctl --user daemon-reload
        # reenable et pas enable : sur une mise a jour depuis une version
        # accrochee a default.target, enable ajouterait le nouveau lien sans
        # retirer l'ancien, et l'unite continuerait de demarrer trop tot.
        systemctl --user reenable doot.service >/dev/null 2>&1 || true
        # restart et pas `enable --now` : sur une reinstallation l'unite tourne
        # deja, et --now ne relancerait pas le code fraichement copie.
        systemctl --user restart doot.service
        DAEMON_TOURNAIT=0
        say "systemd     : doot.service actif, accroche a $CIBLE"
    else
        DESKTOP_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
        mkdir -p "$DESKTOP_DIR"
        cat > "$DESKTOP_DIR/doot.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=doot
Comment=Squelette trompettiste saisonnier
Exec=$BIN_DIR/doot --min $MIN_SECONDS --max $MAX_SECONDS $SALVE_OPTS$FORMATION_OPTS--quiet
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
        say "autostart   : $DESKTOP_DIR/doot.desktop"
    fi
else
    say "demarrage automatique ignore (--no-autostart)"
fi

# Hors systemd, on relance nous-memes le daemon qui tournait avant la copie.
if [ "$DAEMON_TOURNAIT" -eq 1 ]; then
    # Les options composees ne sont volontairement pas entre guillemets :
    # elles portent plusieurs mots, ou rien du tout.
    # shellcheck disable=SC2086
    "$BIN_DIR/doot" --min "$MIN_SECONDS" --max "$MAX_SECONDS" $SALVE_OPTS$FORMATION_OPTS --quiet \
        >/dev/null 2>&1 &
    say "daemon      : redemarre avec le nouveau code"
fi

head_ "Termine"
say "Teste tout de suite : doot --once --ignore-season"
say "Etat                : doot --status"
say "Desinstaller        : ./uninstall.sh"
printf '\n'
"$BIN_DIR/doot" --art || true
