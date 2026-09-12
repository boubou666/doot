# doot

[![CI](https://github.com/boubou666/doot/actions/workflows/ci.yml/badge.svg)](https://github.com/boubou666/doot/actions/workflows/ci.yml)

Un squelette trompettiste surgit au hasard sur ton écran, joue son petit air, puis disparaît.

**Uniquement du 1er septembre au 31 octobre inclus.** Le reste de l'année, le programme
tourne mais reste sagement endormi : le squelette range sa trompette.

```
                                        d    o    o    t   !
            .-"""""""-.
          .'           '.
         /   .-.   .-.   \
        |   ( o ) ( o )   |                  .-----.
        |       ___       |             ,--''       '.
        |      /   \      |            /             \
        |     |=====|     |   ,-------'               |
         \    |||||||========(                        |
          '.  |||||  .'       '------.                |
            '-._____.-'               \              /
             /|     |\                 '--.        ,'
            / |     | \                     '-----'
```

- **Multiplateforme** : Windows 10/11, macOS, Linux (Arch, Debian/Ubuntu, Fedora, openSUSE…)
- **Zéro dépendance** : uniquement la bibliothèque standard de Python 3.8+
- **Discret** : overlay sans bordure, qui ne vole jamais le focus et — sous Windows —
  laisse passer les clics de souris. Il ne bloque rien, il fait juste *doot*.
- **Multi-écrans** : les moniteurs sont énumérés pour de vrai (Win32, Wayland,
  RandR, CoreGraphics), le squelette surgit sur l'un d'eux au hasard, jamais à cheval
  entre deux dalles ni sous la barre des tâches.
- **Trois façons d'arriver**, tirées au sort : il surgit au milieu de l'écran,
  il y surgit en faisant un tour complet sur lui-même, ou il glisse depuis l'un
  des quatre bords en pivotant pour avoir les pieds sur le bord d'où il vient —
  entré par le haut, il arrive tête en bas.
- **Son spatialisé** : le doot sort du côté où le squelette est apparu, calculé
  sur l'ensemble du bureau — collé à droite de l'écran de droite, il sonne
  franchement à droite.
- **Prêt à l'emploi** : le squelette et son *doot* sont livrés avec ; dépose ton
  propre PNG/GIF ou mp3 pour les remplacer, sans toucher au code.
- **Saisonnier** : la fenêtre du 1er septembre au 31 octobre est appliquée par le
  programme lui-même, pas seulement par le planificateur.

---

## 🛑 Au secours, faites-le taire

Pas de panique, rien n'est installé en profondeur et aucun droit administrateur n'a
été demandé. Trois niveaux, du plus doux au plus définitif :

```bash
doot --stop        # arrête le programme qui tourne, tout de suite
```

```bash
./uninstall.sh     # Linux / macOS : désinstalle tout, y compris le démarrage auto
```

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1   # Windows
```

Ajoute `--purge` (Linux/macOS) ou `-Purge` (Windows) pour effacer aussi le dossier de
données. Tu n'as plus le dépôt sous la main ? Tout se retire à la main :

| Système | Ce qu'il faut supprimer |
| --- | --- |
| **Linux** | `systemctl --user disable --now doot.service` puis `rm -rf ~/.config/systemd/user/doot.service ~/.config/autostart/doot.desktop ~/.local/bin/doot ~/.local/share/doot` |
| **macOS** | `launchctl unload ~/Library/LaunchAgents/com.doot.skeleton.plist` puis `rm -rf ~/Library/LaunchAgents/com.doot.skeleton.plist ~/.local/bin/doot ~/Library/Application\ Support/doot` |
| **Windows** | supprime le raccourci `doot` dans `shell:startup` (Win+R → `shell:startup`), puis les dossiers `%LOCALAPPDATA%\Programs\doot` et `%LOCALAPPDATA%\doot` |

Envie de le garder mais en plus discret ? `doot --min 7200 --max 28800` espace les
apparitions de 2 à 8 heures, et `--no-sound` le rend muet.

---

## Installation

### Depuis GitHub, sur les trois systèmes

Les versions qui utilisent le moteur partagé sont distribuées par les
[releases GitHub](https://github.com/boubou666/doot/releases). Les scripts
ci-dessous installent l'application et le wheel vérifié du moteur, puis
configurent le démarrage automatique. Les anciennes versions déjà publiées sur
PyPI restent disponibles, mais ne reçoivent pas cette intégration.

### Linux (dont Arch) et macOS

```bash
git clone https://github.com/boubou666/doot.git
cd doot
./install.sh
```

Le script copie le code dans `~/.local/share/doot/app`, crée la commande
`~/.local/bin/doot`, puis configure le démarrage automatique :
`systemd --user` si disponible, sinon une entrée XDG autostart, et un
LaunchAgent sur macOS.

Options : `./install.sh --no-autostart`, `--min 300`, `--max 1800`,
`--burst-min 2 --burst-max 5 --formation canon` (voir [Les salves](#les-salves)).

**Prérequis système** (`install.sh` te le dira si quelque chose manque) :

| Distribution  | Affichage (tkinter)                | Son (au choix)                                   |
| ------------- | ---------------------------------- | ------------------------------------------------ |
| Arch/Manjaro  | `sudo pacman -S python tk`         | `libpulse` (ou `alsa-lib`), plus `mpv` pour les mp3 |
| Debian/Ubuntu | `sudo apt install python3-tk`      | déjà là (`paplay` / `aplay`)                      |
| Fedora        | `sudo dnf install python3-tkinter` | déjà là                                           |
| openSUSE      | `sudo zypper install python3-tk`   | déjà là                                           |
| macOS         | `brew install python-tk`           | `afplay`, intégré                                 |

Pour lire des **mp3** sous Linux il faut un lecteur qui gère le compressé :
`mpv`, `ffmpeg` (ffplay), `sox` ou `vlc`. Les `.wav`, eux, ne demandent rien :
doot les envoie lui-même à PulseAudio, à PipeWire qui en sert l'interface, ou à
ALSA, sans passer par un lecteur. `doot --status` dit laquelle est utilisée.

### Arch Linux, via un paquet

Installe d'abord [python-desktop-overlay](https://github.com/boubou666/desktop-overlay/tree/main/packaging), puis :

```bash
cd packaging
makepkg -si
systemctl --user enable --now doot.service
```

**Et sur l'AUR ?** Pas encore : le paquet n'y est pas publié, donc `yay -S` ne
trouvera rien pour l'instant. Le `PKGBUILD` prêt à l'être vit dans
`packaging/aur/`, sous le nom **`spooky-doot`** — `doot` y est déjà pris par un
gestionnaire de dotfiles, exactement comme sur PyPI par un lanceur de tâches. Il
déclare `conflicts=('doot')` : les deux paquets installent `/usr/bin/doot` et ne
peuvent donc pas cohabiter. En attendant la publication, le `makepkg -si`
ci-dessus reste la voie.

### Windows

```powershell
git clone https://github.com/boubou666/doot.git
cd doot
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Python 3.8+ est requis (`winget install -e --id Python.Python.3.12`, en cochant
« tcl/tk »). Le script installe dans `%LOCALAPPDATA%\Programs\doot`, ajoute la
commande `doot` au PATH utilisateur et place un raccourci dans le dossier
Démarrage. Aucun droit administrateur, aucun composant système modifié.

### Sans installer (test rapide)

```bash
uv run --no-project --with "desktop-overlay @ https://github.com/boubou666/desktop-overlay/releases/download/v0.2.0/desktop_overlay-0.2.0-py3-none-any.whl#sha256=9ac3676603f73f30bf2d756040cdc35faed9fd5977a6ebf53b5eafd0a5db4f34" python -m doot --once --ignore-season
```

## Versions

Les évolutions sont consignées dans le [CHANGELOG](CHANGELOG.md), au format
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Chaque étiquette `vX.Y.Z`
publie une [release](https://github.com/boubou666/doot/releases) automatiquement,
avec les notes tirées du changelog et les paquets Python construits.

## Mettre à jour

Une fois installé, doot se met à jour tout seul, sur les trois systèmes :

```bash
doot --check-update    # dit si une version plus récente existe
doot --update          # récupère, réinstalle, relance le daemon
```

`--update` relit la fiche déposée par l'installeur (`install.json`, dans le
dossier de données) pour retrouver d'où le code vient et avec quelles options
il avait été installé, puis rejoue l'installeur avec les mêmes réglages. Le
daemon est arrêté le temps de l'opération et redémarré derrière.

Deux façons de récupérer le code, dans cet ordre : si le dépôt cloné est
toujours là, un `git pull --ff-only` ; sinon l'archive de la branche
principale est téléchargée depuis GitHub. La seconde voie ne demande ni git ni
le clone d'origine, donc une installation dont tu as effacé le dossier depuis
se met à jour quand même.

Tes sons, tes images et ton journal ne sont pas touchés : ils vivent dans le
dossier de données, l'installeur ne remplace que le code.

Si doot a été installé par un gestionnaire de paquets (le `PKGBUILD` d'Arch,
par exemple), `--update` refuse et te renvoie vers `pacman -Syu` plutôt que
d'écraser des fichiers qui ne lui appartiennent pas.

## Utilisation

```bash
doot                         # lance le daemon (c'est ce que fait le démarrage auto)
doot --once                  # un doot tout de suite, puis on quitte
doot --once --ignore-season  # idem, même hors saison : pratique pour tester
doot --status                # saison, daemon, son et image utilisés
doot --stop                  # arrête le daemon
doot --paths                 # où sont les fichiers
doot --screens               # liste les écrans détectés
doot --check-update          # une version plus récente existe-t-elle ?
doot --update                # met à jour et réinstalle
doot --art                   # imprime le squelette dans le terminal
```

| Option | Défaut | Description |
| --- | --- | --- |
| `--min` / `--max` | `600` / `3600` | bornes du délai aléatoire entre deux doot, en secondes |
| `--burst-min` / `--burst-max` | `1` / `1` | bornes du nombre de doots enchaînés à chaque déclenchement |
| `--burst-delay` | `0.6` | pause entre deux doots d'une même salve, en secondes |
| `--formation` | `random` | formation d'une salve : `random` ou `canon` (bords et écrans en séquence) |
| `--duration` | durée du son | durée d'affichage, en secondes (au moins 2.8) |
| `--image` | — | un PNG/GIF précis à afficher |
| `--no-image` | — | force l'ASCII art même si une image est disponible |
| `--scale` | auto | échelle de l'image (par défaut ajustée à l'écran) |
| `--volume` | `0.55` | volume du jingle synthétisé, de `0.0` à `1.0` |
| `--opacity` | `1.0` | opacité maximale de l'overlay |
| `--font-size` | `15` | taille du squelette ASCII |
| `--center` | — | se pose au centre, au lieu d'une position aléatoire |
| `--slide-chance` | `0.5` | proportion de doots qui entrent par un bord ; le reste surgit au milieu |
| `--side` | au hasard | bord d'entrée : `left`, `right`, `top`, `bottom` (impose l'entrée) |
| `--slide-ms` | `420` | durée de l'entrée, en millisecondes |
| `--no-slide` | — | jamais d'entrée par un bord, tout surgit sur place |
| `--spin` | — | ce doot fait un tour complet sur lui-même (impose l'apparition sur place) |
| `--spin-chance` | `0.25` | proportion des apparitions sur place qui font un tour complet |
| `--spin-ms` | `700` | durée du tour complet, en millisecondes |
| `--no-spin` | — | jamais de tour complet, le squelette reste droit |
| `--screen` | `random` | écran d'apparition : `random`, `primary`, ou un index (`0`, `1`…) |
| `--no-sound` | — | mode muet |
| `--no-pan` | — | son au centre, au lieu de suivre la position du squelette |
| `--regen-sound` | — | régénère le jingle |
| `--ignore-season` | — | ignore la fenêtre saisonnière (tests) |
| `--quiet` | — | n'écrit que dans le journal |

## Les médias

doot est livré avec le squelette et le son qu'on attend : `doot/assets/doot.png`
et `doot/assets/doot.mp3`, installés d'office. C'est le mème *skull trumpet*
(« doot doot »), qui circule un peu partout depuis 2010 ; il est inclus pour que
ça marche du premier coup. Si tu es l'ayant droit et que ça te dérange, ouvre une
issue et je les retire.

Trois niveaux de repli, dans cet ordre : tes fichiers → les fichiers fournis →
l'ASCII art et le jingle synthétisé maison (harmoniques, vibrato, enveloppe ADSR),
utilisés notamment sur un Linux sans lecteur mp3 — le jingle étant un WAV, il
part par la sortie native et ne demande donc aucun lecteur.

### Mettre les tiens

```bash
doot --paths        # affiche les deux dossiers ci-dessous
```

- **Image** → dossier `image/` : un `.png` ou un `.gif` (les GIF animés sont joués
  en boucle). Prends une image détourée, à fond transparent : sous Windows le fond
  disparaît complètement et le squelette flotte sur le bureau. Plusieurs fichiers ?
  Un est tiré au hasard à chaque apparition.
- **Son** → dossier `sound/` : `.wav`, `.mp3`, `.ogg`, `.flac`, `.m4a`, `.opus`.
  L'affichage s'allonge automatiquement pour couvrir toute la durée du son.

Tes fichiers passent devant ceux fournis, et ils sont relus à chaque apparition :
tu peux les changer pendant que le daemon tourne. Pour revenir au dessin ASCII et
au jingle synthétisé : `doot --no-image --regen-sound` (ou vide les deux dossiers
et supprime `doot/assets/`).

## Les salves

Un déclenchement peut en amener plusieurs. `--burst-min` et `--burst-max`
donnent les bornes : le nombre est tiré au hasard entre les deux à **chaque**
déclenchement, et `--burst-delay` règle la pause entre deux doots de la salve.

```bash
doot --burst-min 2 --burst-max 5              # de 2 à 5 doots d'affilée
doot --burst-min 3 --burst-max 3              # toujours 3
doot --burst-min 2 --burst-max 4 --burst-delay 1.5   # plus espacés
doot --once --ignore-season --burst-min 4 --burst-max 4   # pour voir tout de suite
doot --once --ignore-season --burst-min 4 --burst-max 4 --formation canon
```

Par défaut, chaque doot de la salve est tiré indépendamment : son animation
(sur place, en tournant, ou par un bord — et lequel), sa position, son écran,
son image et son son. Une salve de quatre, ce sont quatre squelettes différents
qui arrivent chacun à leur façon, pas la même apparition répétée.

`--formation canon` transforme la salve en petite parade : les bords suivent
le cycle gauche → haut → droite → bas et les écrans disponibles sont parcourus
dans l'ordre. Les doots restent séquentiels et `--burst-delay` donne le tempo.
Avec un seul écran, le canon garde son tour des bords ; `--screen` ou `--side`
peut fixer respectivement l'écran ou le bord, et `--no-slide` garde uniquement
la chorégraphie des écrans.

### Les garder au démarrage

Les options ci-dessus valent pour la commande que tu tapes. Le doot lancé à
l'ouverture de session, lui, tient sa ligne de commande des installeurs — il
faut donc la leur demander :

```bash
./install.sh --burst-min 2 --burst-max 5 --formation canon    # Linux, macOS
```

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -BurstMin 2 -BurstMax 5 -Formation canon
```

Le réglage part dans `install.json`, la fiche que relit `doot --update` : il
survit donc aux mises à jour. Éditer l'unité systemd, le LaunchAgent ou le
raccourci à la main marche aussi, mais **la prochaine mise à jour les
réécrit** — les installeurs les regénèrent depuis la fiche.

Sans ces options, la ligne engendrée est exactement celle d'avant les salves :
mettre doot à jour ne fait donc apparaître aucune salve chez personne.

Une salve n'échappe pas à la saison : elle dure — la pause plus la durée
d'affichage, autant de fois qu'il y a de doots — et la fenêtre saisonnière peut
donc se fermer en plein milieu. Chaque doot revérifie avant de s'afficher, comme
le daemon revérifie après chaque attente.

Par défaut `--burst-min` et `--burst-max` valent `1` : un déclenchement, un
doot, comme avant.

## Les trois façons d'arriver

Il y en a trois, tirées au sort à chaque apparition :

- **au milieu**, comme depuis toujours : il surgit sur place, à un endroit
  quelconque de l'écran, droit, en fondu ;
- **en tournant**, au même endroit, mais en faisant un tour complet sur
  lui-même ;
- **par un bord**, en glissant depuis l'extérieur.

Une entrée par un bord une fois sur deux par défaut. `--slide-chance` règle la
proportion — `0` pour n'avoir que des apparitions sur place, `1` que des entrées
par un bord, `0.8` pour surtout des entrées :

```bash
doot --slide-chance 0.8
```

Le tour complet se partage le reste : un quart des apparitions sur place par
défaut, réglable par `--spin-chance`.

### L'entrée par un bord

Le squelette glisse depuis un bord de l'écran jusqu'à sa position de repos. Le
mouvement est vif au départ et se pose en douceur — une décélération cubique
sur 420 ms par défaut.

L'image **pivote** pour que son bas se pose contre le bord par lequel elle
entre : le squelette a toujours les pieds sur le bord d'où il vient.

| Bord d'entrée | Rotation | Résultat |
| --- | --- | --- |
| gauche | un quart horaire | pieds à gauche, tête vers la droite |
| droite | un quart antihoraire | pieds à droite, tête vers la gauche |
| haut | demi-tour | pieds en haut, tête vers le bas |
| bas | aucune | image droite |

Il s'arrête **contre ce bord**, à quelques pixels près. Il ne s'enfonce pas
dans l'écran : ce serait une traversée, pas une entrée.

```bash
doot --once --side left      # entre par la gauche
doot --once --side top       # tombe du haut, tête en bas
doot --once --slide-ms 900   # entrée plus lente
doot --once --no-slide       # apparaît sur place, comme avant
```

Le squelette ASCII, lui, ne pivote pas : des glyphes à chasse fixe tournés d'un
quart de tour ne veulent plus rien dire. Il est simplement retourné quand il
entre par la droite — les obliques et les parenthèses basculent, et les lettres
du *doot* changent de côté sans cesser d'être lisibles.

Pendant le glissement il n'y a pas de fondu d'apparition : le bord de l'écran
révèle déjà le squelette, et les deux ensemble font bouillie.

### Le tour complet

Le squelette apparaît sur place, comme d'habitude, et fait **un tour complet sur
lui-même** avant de s'immobiliser — 700 ms par défaut, dans le sens horaire. Il
finit droit : le tour se referme exactement là où il a commencé.

C'est la même rotation que celle de l'entrée par un bord, mais étalée dans le
temps : les quatre quarts de tour défilent l'un après l'autre.

| Avancement | Rotation | Résultat |
| --- | --- | --- |
| 0 – ¼ | aucune | image droite |
| ¼ – ½ | un quart horaire | tête à droite |
| ½ – ¾ | demi-tour | tête en bas |
| ¾ – 1 | trois quarts | tête à gauche |

L'image est centrée dans le carré qui la contient : les quatre orientations ont
alors la même taille, et la fenêtre ne change ni de dimensions ni de place au
milieu du tour.

```bash
doot --once --spin           # un tour complet, tout de suite
doot --once --spin-ms 1500   # un tour bien plus lent
doot --spin-chance 1         # toutes les apparitions sur place tournent
doot --no-spin               # jamais de tour, comme avant
```

Il ne se cumule pas avec l'entrée par un bord : l'image y est déjà pivotée pour
poser les pieds contre le bord, et la faire tourner en plus lui ferait perdre le
seul repère de l'arrivée. `--spin` impose donc l'apparition sur place, et
demander `--side` en même temps est refusé.

Il demande une **image PNG** : les GIF animés et le squelette ASCII restent
droits, faute de pouvoir être pivotés (`doot/png.py` ne décode pas les GIF, et
des glyphes à chasse fixe tournés d'un quart de tour ne veulent plus rien dire).

## Le son spatialisé

Le doot sort du côté où le squelette est apparu. La position est calculée sur
**tout le bureau virtuel**, pas sur un écran isolé : avec deux dalles côte à
côte, un squelette collé au bord droit de celle de droite sonne franchement à
droite, et pas au centre comme s'il était seul au monde.

Le canal dominant reste à plein volume, seul le canal opposé est atténué. Un
doot centré rend donc exactement le son d'origine, sans les 3 dB qu'un
panoramique à puissance constante lui aurait coûtés.

Comment c'est appliqué, selon ce que la plateforme sait faire :

| Format | Windows | macOS | Linux |
| --- | --- | --- | --- |
| `.wav` | panoramisé dans les échantillons | idem | idem |
| `.mp3` et compressés | volume par canal via MCI | non spatialisé | `mpv` ou `ffplay` si présent, sinon non spatialisé |

Les WAV sont traités par doot lui-même. Sous Linux il les envoie aussi
lui-même à PulseAudio, à PipeWire qui en sert l'interface, ou à ALSA : aucun
lecteur n'intervient, donc rien ne peut diverger entre le calcul et la
restitution. Pour les formats compressés il faut un intermédiaire capable de
panoramiser : MCI sous Windows, un filtre `pan` sous Linux. Quand rien ne sait,
le son est joué au centre plutôt que pas du tout.

`--no-pan` désactive tout ça.

## Où sont les fichiers

`doot --paths` affiche tout. Par défaut :

| Système | Dossier de données |
| --- | --- |
| Linux   | `~/.local/share/doot` |
| macOS   | `~/Library/Application Support/doot` |
| Windows | `%LOCALAPPDATA%\doot` |

Il contient `image/` et `sound/` (tes médias), `doot.wav` (le jingle en cache),
`doot.log` (le journal) et `doot.pid`.

## Dépannage

**Rien ne s'affiche** → `doot --status`. Si tkinter manque, installe le paquet
du tableau ci-dessus. Sous Wayland, l'overlay passe par XWayland ; si ton
compositeur le refuse, lance la session en X11 ou utilise `--center`.

**Pas de son** → `doot --status` donne les deux lignes qui comptent, la sortie
native et le lecteur. Les `.wav` ne demandent que `libpulse` ou `alsa-lib`, qui
sont là dès qu'une pile audio l'est. Les mp3 et autres formats compressés
demandent en plus un lecteur capable de les décoder : `mpv`, `ffplay`, `play`
ou `cvlc`. Sans rien du tout, doot s'affiche en silence plutôt que de planter.

**Mon image ne s'affiche pas** → tkinter ne lit que le PNG et le GIF. Convertis
ton jpg/webp, par exemple avec `ffmpeg -i image.webp image.png`. Une image
illisible fait simplement revenir l'ASCII art.

**Il n'apparaît que sur un seul écran** → `doot --screens` liste ce que doot
détecte. Sous Wayland, doot parle à ton compositeur et pose le squelette sur la
sortie voulue, à condition qu'il gère `wlr-layer-shell`. Vérifié sur Hyprland ;
Sway et river l'implémentent aussi, KDE également même si son comportement sur
les marges négatives du glissement n'a pas été vérifié. GNOME ne l'implémente
pas. Sinon doot repasse par X11, où il interroge RandR directement sur la
socket, sans rien à installer. Sous GNOME Wayland, XWayland impose sa propre
disposition et la cible n'est pas garantie ; fixe-la avec `doot --screen 0`.
Avec des écrans à facteurs d'échelle différents sous Windows, la position peut
se décaler un peu : `--screen primary` évite le problème.

**Le fond n'est pas transparent** (Linux) → il faut un compositeur actif
(`picom`, KWin, Mutter…). Sinon le squelette s'affiche sur un fond sombre.

**Ça ne se déclenche jamais** → on est peut-être hors saison. `doot --status`
te dit la date de réouverture. Pour vérifier que tout marche :
`doot --once --ignore-season`.

**Le daemon ne redémarre pas à la session** →
`systemctl --user status doot` (Linux), `launchctl list | grep doot` (macOS),
ou vérifie le raccourci dans `shell:startup` (Windows).

## Tests

La suite est en `unittest`, donc elle tourne sans rien installer :

```bash
python -m unittest discover -s tests -v
```

Elle couvre les bornes de la saison, le placement multi-écrans, la synthèse du
jingle et le choix du son. Les tests du décodeur PNG comparent sa sortie à celle
de Pillow, octet pour octet, sur neuf variantes de fichier (RGBA, RGB, gris,
gris+alpha, palette 1/2/4/8 bits, avec et sans `tRNS`) ; ils se mettent en pause
si Pillow ou `doot/png.py` est absent :

```bash
python -m pip install pillow    # pour activer les tests PNG
```

La CI rejoue tout ça sur Linux, Windows et macOS à chaque push et chaque pull
request, vérifie qu'aucun doot ne s'affiche hors saison, et contrôle la syntaxe
des quatre installeurs.

## Comment ça marche

| Fichier | Rôle |
| --- | --- |
| `doot/season.py` | la fenêtre 1er septembre → 31 octobre |
| `doot/art.py` | l'ASCII art et les images de l'animation |
| `doot/image.py` | le choix du PNG/GIF déposé par l'utilisateur |
| `doot/screens.py` | l'énumération des écrans (Win32 / RandR / CoreGraphics) |
| `doot/wayland.py` | l'overlay natif Wayland, en layer-shell |
| `doot/overlay.py` | la boucle d'animation, partagée par les deux overlays |
| `doot/sound.py` | synthèse du jingle, durée et lecture selon l'OS |
| `doot/audio.py` | la sortie audio native (PulseAudio/PipeWire, ALSA) |
| `doot/window.py` | l'overlay tkinter, la transparence, le fondu |
| `doot/cli.py` | la CLI, la boucle aléatoire, l'instance unique |

Le daemon tire un délai au hasard entre `--min` et `--max`, dort, vérifie que la
saison est toujours ouverte, affiche la salve du déclenchement (un seul doot par
défaut, sinon un nombre tiré entre `--burst-min` et `--burst-max`), recommence. Hors saison, il
se contente de revérifier la date toutes les heures.

## Licence

Le **code** est sous licence MIT, ainsi que l'ASCII art et le jingle synthétisé,
qui sont originaux.

Les fichiers de `doot/assets/` sont l'exception : le mème *skull trumpet* n'est
pas de moi et n'est pas couvert par la licence MIT du projet. Il est inclus par
commodité ; retire-le si ton usage l'exige, et les médias que tu ajoutes toi-même
restent soumis à leurs propres droits.
