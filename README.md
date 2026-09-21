<p align="center">
  <img src="doot/assets/logo.png" width="220" alt="Logo de doot : un squelette joue de la trompette dans un croissant de lune" />
</p>

<h1 align="center">☠️ doot 🎺</h1>

<p align="center">
  <strong>Un squelette trompettiste surgit au hasard sur ton écran,<br />
  joue son petit air, puis retourne dans sa crypte.</strong>
</p>

<p align="center">
  <a href="https://github.com/boubou666/doot/actions/workflows/ci.yml"><img src="https://github.com/boubou666/doot/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
</p>

> [!IMPORTANT]
> **La crypte ne s'ouvre que du 1er septembre au 31 octobre inclus.** Le reste
> de l'année, le programme tourne mais reste sagement endormi : le squelette
> range sa trompette.

<details>
<summary>🦴 Invoquer le trompettiste du terminal</summary>

```text
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

</details>

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
- **Orchestre polyphonique** : une ligne RTTTL donne une voix et un squelette ;
  chacun hoche sur ses propres notes, sans plafond artificiel de musiciens.
- **Chorégraphies** : les salves peuvent défiler en canon, onduler entre les
  écrans, tomber du haut, tournoyer sur place ou se répondre en duel.
- **Rencontres rares** : parade, pluie d'os, vortex, duel, Mimic et faux bug
  interrompent parfois la routine ; le Codex garde la trace des découvertes.
- **Doot contagieux** : les machines d'une même flotte chiffrée se transmettent
  une apparition éphémère — et ce qu'elle portait, mélodie ou rencontre rare —
  sans serveur ni dépendance au réseau.
- **Profils persistants** : sauvegarde plusieurs ambiances et active celle que
  le daemon doit reprendre automatiquement, y compris après une mise à jour.
- **Registre de la crypte** : les soirs de la saison en grille, les totaux, les
  records et la part de chaque machine de la flotte — tout ce que `state.json`
  gardait déjà sans que rien ne le montre.
- **Prêt à l'emploi** : le squelette et son *doot* sont livrés avec ; dépose ton
  propre PNG/GIF ou mp3 pour les remplacer, sans toucher au code.
- **Saisonnier** : la fenêtre du 1er septembre au 31 octobre est appliquée par le
  programme lui-même, pas seulement par le planificateur.
- **Le rite du dernier soir** : le 31 octobre au soir, douze trompettistes
  saluent la fermeture et doot laisse derrière lui la carte de la saison — un
  PNG qu'il compose seul, sans fonte installée ni bibliothèque d'images.

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
| **Linux** | `systemctl --user disable --now doot.service` puis `rm -rf ~/.config/systemd/user/doot.service ~/.config/autostart/doot.desktop ~/.local/bin/doot ~/.local/bin/doot-gui ~/.local/share/doot` |
| **macOS** | `launchctl unload ~/Library/LaunchAgents/com.doot.skeleton.plist` puis `rm -rf ~/Library/LaunchAgents/com.doot.skeleton.plist ~/.local/bin/doot ~/.local/bin/doot-gui ~/Library/Application\ Support/doot` |
| **Windows** | supprime le raccourci `doot` dans `shell:startup` (Win+R → `shell:startup`), puis les dossiers `%LOCALAPPDATA%\Programs\doot` et `%LOCALAPPDATA%\doot` |

Envie de le garder mais en plus discret ? `doot --min 7200 --max 28800` espace les
apparitions de 2 à 8 heures, et `--no-sound` le rend muet.

---

## 🕯️ Installation

### Depuis GitHub, sur les trois systèmes

Les versions sont distribuées uniquement par les
[releases GitHub](https://github.com/boubou666/doot/releases). Les canaux PyPI
et AUR ne sont plus maintenus. Les scripts ci-dessous installent l'application
et le wheel vérifié du moteur, puis configurent le démarrage automatique.

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

Le projet n'est plus publié sur l'AUR. Le `PKGBUILD` de `packaging/` reste une
commodité pour construire localement depuis une release GitHub ; il n'est pas
synchronisé vers un dépôt de paquets. Pour les mises à jour automatiques, utilise
plutôt `install.sh` puis `doot --update`.

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
uv run --no-project --with "desktop-overlay @ https://github.com/boubou666/desktop-overlay/releases/download/v0.2.1/desktop_overlay-0.2.1-py3-none-any.whl#sha256=c752c46c077390a1f6cc6569dae09df302a2d0810b6a555122366be38928c972" python -m doot --once --ignore-season
```

## 📜 Versions

Les évolutions sont consignées dans le [CHANGELOG](CHANGELOG.md), au format
[Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Chaque étiquette `vX.Y.Z`
publie une [release](https://github.com/boubou666/doot/releases) automatiquement,
avec les notes tirées du changelog et les paquets Python construits.

## 🧪 Mettre à jour

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
toujours là, un `git pull --ff-only origin main` ; sinon l'archive de la branche
principale est téléchargée depuis GitHub. La seconde voie ne demande ni git ni
le clone d'origine, donc une installation dont tu as effacé le dossier depuis
se met à jour quand même.

Tes sons, tes images et ton journal ne sont pas touchés : ils vivent dans le
dossier de données, l'installeur ne remplace que le code.

Si doot a été installé par un gestionnaire de paquets (le `PKGBUILD` d'Arch,
par exemple), `--update` refuse et te renvoie vers `pacman -Syu` plutôt que
d'écraser des fichiers qui ne lui appartiennent pas.

## 🎺 Utilisation

### Interface graphique

```bash
doot --gui       # ouvre le grimoire graphique
doot-gui         # raccourci equivalent apres installation
```

Le grimoire rassemble toutes les actions et tous les réglages de la CLI. Chaque
action possède sa vignette, la commande exacte reste visible avant son lancement
et sa sortie s'affiche dans un journal intégré, jusque dans des barres de
défilement en forme d'os. Le daemon peut être lancé en arrière-plan : fermer le
grimoire ne l'arrête pas. La GUI utilise Tkinter, déjà requis par l'overlay, et
n'ajoute donc aucune dépendance.

```bash
doot                         # lance le daemon (c'est ce que fait le démarrage auto)
doot --gui                   # ouvre le lanceur graphique de toutes les commandes
doot --once                  # un doot tout de suite, puis on quitte
doot --once --ignore-season  # idem, même hors saison : pratique pour tester
doot --play spooky-scary-skeletons   # une mélodie en doots (voir --melodies)
doot --rickroll              # raccourci de --play rickroll
doot --melodies              # les mélodies jouables, les tiennes et les fournies
doot --events                # les rencontres rares disponibles
doot --event pluie           # force une rencontre rare, pour la découvrir
doot --codex                 # le livre des apparitions déjà découvertes
doot --achievements          # les succès locaux, leur progression et le score
doot --stats                 # le registre : totaux, machines, saison en grille
doot --carte                 # la carte de la saison, en PNG, quand on veut
doot --profiles              # les profils enregistrés et celui qui est actif
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
| `--formation` | `random` | formation : `random`, `canon`, `wave`, `rain`, `vortex` ou `duel` |
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
| `--melody-chance` | `0.05` | proportion de déclenchements qui jouent une mélodie au lieu d'un doot |
| `--melody-pity` | `40` | le N-ième déclenchement sans mélodie en joue une à coup sûr (`0` : aucune garantie) |
| `--no-melody` | — | jamais de mélodie à la place d'un doot |
| `--event-chance` | `0.02` | proportion de déclenchements transformés en rencontre rare |
| `--event-pity` | `100` | le N-ième déclenchement sans événement en force un (`0` : aucune garantie) |
| `--no-event` | — | coupe les événements rares automatiques |
| `--contagion-chance` | `0.12` | chance qu'un doot local traverse le partage chiffré |
| `--no-contagion` | — | coupe l'émission et la réception des doots contagieux |
| `--no-spin` | — | jamais de tour complet, le squelette reste droit |
| `--screen` | `random` | écran d'apparition : `random`, `primary`, ou un index (`0`, `1`…) |
| `--no-sound` | — | mode muet |
| `--no-pan` | — | son au centre, au lieu de suivre la position du squelette |
| `--regen-sound` | — | régénère le jingle |
| `--ignore-season` | — | ignore la fenêtre saisonnière (tests) |
| `--quiet` | — | n'écrit que dans le journal |

## 🏆 Les succès

Doot garde sa progression **uniquement en local**, dans le même `state.json` que
le compteur de mélodies (`doot --paths` montre son emplacement). Aucun compte,
aucune connexion et aucune télémétrie : les apparitions, les salves, les mélodies,
les bords imposés, les formations, les événements et les profils débloquent
18 succès pour un total de 475 points.

```bash
doot --achievements     # alias français : doot --succes
```

Un succès est annoncé une seule fois dans le terminal et dans le journal. Il fait
aussi apparaître une médaille illustrée en haut à droite, accompagnée d'une courte
fanfare originale à deux voix jouée par le moteur RTTTL. `--no-sound` garde la
médaille mais coupe la fanfare. La commande affiche ensuite les succès acquis, les
objectifs encore verrouillés et leur progression. Le fichier reste du JSON lisible
et peut être sauvegardé avec le reste du dossier de données.

### Le registre de la crypte

```bash
doot --stats
```

Le score dit combien de points ont été gagnés, jamais ce qui s'est passé.
`state.json` en garde pourtant beaucoup plus depuis toujours : les doots machine
par machine, les soirs où la crypte a servi, la plus grande salve, les formations
menées, les bords imposés, les mélodies fournies déjà jouées. Le registre les
montre, sans rien collecter de neuf.

La saison s'affiche en grille, une colonne par semaine et une case par soir :

```text
       sep     oct
  lun    . . . . # . . .
  mar  # # . . . . . . .
  mer  # # . . # . . . .
  jeu  # . . . # . . . .
  ven  . . . . . . . . #
  sam  # # # # . . # . #
  dim  . # # . # # # #
```

Une case est pleine dès qu'un soir a eu son doot. Elle ne dit pas combien :
l'état range les jours actifs en ensemble de dates, pas en compteurs, et une
case plus sombre pour « trois doots » prétendrait à une intensité que le fichier
ne garde pas. Compter par jour demanderait une troisième façon de fusionner deux
machines, et ferait grossir le fichier sans fin.

Le registre lit et n'écrit pas. C'est ce qui lui permet de rouvrir une saison
fermée depuis des mois — les saisons précédentes tiennent en une ligne chacune —
et de détailler une flotte déjà fusionnée sans la resynchroniser d'abord.

Le grimoire graphique en a son onglet, avec la même grille dessinée en cases
dorées ; il se rafraîchit à la fin de chaque commande lancée depuis la fenêtre.

### Faire converger ses machines

Sur le premier poste :

```bash
doot --sync-init ~/Sync/doot
```

Il frappe une clé et l'affiche. Sur les autres, on dit où publier puis on
recopie la clé, comme on recopie un identifiant Syncthing :

```bash
doot --sync-init ~/Sync/doot
doot --sync-join dootsync1ykriszfb4t5hqt3a5tu7zhs5pgaym7xwvwsb6w6dt75pchdiyrra
```

Le démon publie sa part et relit celle des autres à chaque doot. Il écoute aussi
doucement le dépôt entre deux déclenchements : avec 12 % de chance, un doot
local y laisse pendant cinq minutes un signal qu'une autre machine fera surgir
chez elle. Chaque signal n'est joué qu'une fois par poste et ne rebondit pas,
donc deux machines ne peuvent pas s'enfermer dans une épidémie infinie.

Le signal dit **ce qui a été joué** là-bas. Une pluie d'os traverse avec sa
chorégraphie, un rickroll avec son nom : le portable qui joue une mélodie la
fait jouer sur le fixe, et ce n'est plus seulement « un doot a eu lieu quelque
part ». Quatre garde-fous :

- les deux clés sont **facultatives des deux côtés**. Un poste plus ancien
  n'écrit rien de plus et reçoit le doot ordinaire ; un poste plus ancien qui
  reçoit une charge l'ignore et joue le doot. Une flotte se met à jour machine
  par machine sans se casser ;
- **tes refus gagnent**. `--no-melody` et `--no-event` rendent le doot bref :
  un poste qu'on a fait taire sur un point ne se le voit pas rouvrir par un pair ;
- une mélodie **que ce poste ne connaît pas** retombe en doot. Deux machines ne
  portent pas forcément les mêmes fichiers dans `melodies/` ;
- ce qui traverse reste **une contagion** au Codex, même quand c'est une parade.
  La rencontre a été vue là-bas et son poste l'a comptée ; la compter ici aussi
  ferait d'une flotte un moyen de collectionner les rencontres rares.

Le nom porté par un signal vient d'une autre machine, et il sert à chercher une
mélodie. Il est donc réduit à un jeton — ni séparateur, ni point de tête, 48
caractères au plus — et cherché **par égalité** dans le catalogue local. Jamais
comme un chemin : `doot --play` accepte un fichier, et ce chemin-là ne doit pas
pouvoir être choisi depuis le dépôt partagé.

Rien d'autre à lancer : un dépôt injoignable ou un disque plein laissent la
progression locale intacte et l'ennui dans `doot --succes`, parce qu'un doot ne
doit jamais dépendre du partage. `--no-contagion` coupe ces apparitions sans
couper la convergence des succès ; `--contagion-chance` règle leur fréquence.

Un seau compatible S3 marche aussi, R2, MinIO ou B2 compris :

```bash
doot --sync-init s3://mon-seau/doot --sync-endpoint https://….r2.cloudflarestorage.com
```

Les identifiants viennent du premier de ces trois endroits qui en porte :

1. la fiche du poste, posée par `--sync-key-id` et `--sync-secret` ;
2. `DOOT_S3_KEY_ID` et `DOOT_S3_SECRET` ;
3. `AWS_ACCESS_KEY_ID` et `AWS_SECRET_ACCESS_KEY`.

Les noms propres à doot existent pour une machine qui garde déjà des `AWS_*`
pour autre chose : elle n'a ni à les partager, ni à jouer avec l'ordre de
chargement de `environment.d` pour les séparer.

```bash
doot --sync-init s3://mon-seau/doot --sync-endpoint https://… \
     --sync-key-id ID --sync-secret -
```

`--sync-secret -` lit le secret sur l'entrée standard : saisie invisible s'il y
a un terminal, une ligne lue sinon, pour qu'il ne traîne ni dans `ps` ni dans
l'historique du shell. Ce qui est posé ainsi vit dans `replica.json`, en `0600`
comme la clé de chiffrement qui l'accompagne.

#### Ce que voit celui qui héberge

Rien de lisible. Chaque poste publie un objet chiffré, nommé par un
`HMAC(clé, identité)` :

```
80aa18677ffe2d5aa978e241cd12abaf.dootsync
b5f5c1a6f0f04b6861d9b4f9638f07da.dootsync
```

L'hébergeur ne peut donc pas relier un objet à une machine. La **taille** de la
flotte n'est pas cachée pour autant, un objet par machine se compte quel que
soit son nom, et l'heure des écritures laisse deviner des horaires.

**Il n'y a pas de révocation.** Une machine perdue ou volée lit la progression
de la flotte tant que toutes les autres n'ont pas été rechiffrées à la main :
`--sync-init --sync-force` ici, `--sync-join` sur chacune, et les anciens objets
supprimés. Mieux vaut le dire que laisser croire que « chiffré » veut dire
« révocable ».

Changer de clé se fait en deux temps : le poste retient celle qu'il quitte,
publie sa part sous la neuve, et ne retire l'objet de l'ancienne qu'ensuite. Si
le dépôt est injoignable pendant l'opération, la clé quittée survit dans
`replica.json` et le premier cycle qui aboutit fait le ménage. Sans elle l'objet
resterait là pour toujours : son nom ne se calcule que depuis la clé qui l'a
fermé.

`replica.json` en garde une **liste**, parce que deux objets peuvent attendre à
la fois : une rotation dont le retrait a échoué laisse le sien derrière elle, et
la rotation suivante ajoute le sien. Rejouer la commande qui vient d'échouer
passe par le même chemin, la clé qui n'a jamais rien publié s'ajoutant sans
chasser celle qui la précède.

La possession de la clé est la seule authentification. Une machine ne peut pas
prouver laquelle elle est au-delà de détenir la clé, ce qui est le bon niveau
pour les machines d'une personne et le mauvais pour une équipe.

#### À la main, sans clé

Pour un transfert ponctuel, une clé USB ou un courriel, les deux commandes
d'origine restent, en clair puisque c'est toi qui manipules le fichier :

```bash
doot --export ~/ma-cle-usb
doot --merge  ~/ma-cle-usb
```

#### Ce qui voyage, et ce qui reste

L'export ne porte que l'identité, les statistiques et les succès. Les compteurs
de pitié restent au poste : ils décrivent son rythme, pas ce qui y a été
accompli.

L'identité de chaque poste et les réglages du partage, clé comprise, vivent dans
`replica.json`, à côté de `state.json` mais pas dedans, parce que `state.json` se
sauvegarde et se copie. Deux installations qui partageraient une identité
verraient leurs progressions fusionnées par maximum au lieu d'être additionnées,
et un secret n'a rien à faire dans un fichier qu'on recopie.

Refaire la fusion ne change rien, et le sens n'importe pas. Chaque total est
rangé en parts, une par machine, et fusionner prend le maximum part par part au
lieu d'additionner ; les maxima se comparent, les ensembles s'unissent, et les
dates de déblocage gardent la plus ancienne. Réunir deux machines peut franchir
un objectif qu'aucune n'avait atteint seule.

Ce qu'un poste publie porte aussi ce qu'il a appris des autres, donc deux
machines jamais allumées en même temps se rejoignent par l'intermédiaire d'une
troisième.

C'est de la convergence entre tes machines, pas un classement : la progression
reste falsifiable en local, et rien ici ne prétend le contraire.

### Et un classement en ligne ?

Le score local prépare le terrain, mais l'envoi doit rester explicitement activé
par la personne. Une petite API suffit : le client envoie des **événements** munis
d'un identifiant unique (`doot`, `melodie`, succès débloqué), et le serveur calcule
lui-même le score au lieu d'accepter un total fourni par le client. Trois routes
couvrent le besoin : inscription pseudonyme, envoi d'un lot d'événements et lecture
du top de la saison.

Une implémentation légère peut tenir dans un
[Cloudflare Worker avec D1](https://developers.cloudflare.com/d1/get-started/), ou
dans [Supabase avec des règles d'accès par ligne](https://supabase.com/docs/guides/database/postgres/row-level-security).
Dans les deux cas il faut prévoir :

- un pseudo public et un jeton secret local, sans adresse e-mail obligatoire ;
- l'idempotence des événements, des limites de fréquence et un score recalculé
  côté serveur ;
- une saison dans la clé du classement, par exemple `2026`, afin de repartir
  proprement chaque septembre ;
- `--online` désactivé par défaut, une commande de suppression, et aucun envoi de
  chemins de fichiers, noms de machines ou autres données privées ;
- un classement présenté comme amical : un client open source exécuté en local ne
  peut pas empêcher totalement la triche, même avec une validation serveur.

Le stockage local reste utilisable hors ligne ; la synchronisation peut reprendre
en envoyant les événements non encore accusés par le serveur.

## 🖼️ Les médias

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

## 💀 Les salves

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

`--formation` transforme la salve en petite parade. Les doots restent
séquentiels et `--burst-delay` donne le tempo :

| Formation | Chorégraphie |
| --- | --- |
| `random` | chaque écran, bord et animation est tiré indépendamment, comme avant |
| `canon` | gauche → haut → droite → bas, avec les écrans parcourus dans l'ordre |
| `wave` | gauche ↔ droite, avec un aller-retour sur la rangée d'écrans |
| `rain` | tous les squelettes tombent du haut, écran après écran |
| `vortex` | apparitions sur place, chacune avec un tour complet |
| `duel` | gauche ↔ droite, comme deux pupitres qui se répondent |

```bash
doot --once --ignore-season --burst-min 6 --burst-max 6 --formation wave
doot --once --ignore-season --burst-min 7 --burst-max 7 --formation rain
doot --once --ignore-season --burst-min 5 --burst-max 5 --formation vortex
doot --once --ignore-season --burst-min 6 --burst-max 6 --formation duel
```

Avec un seul écran, la chorégraphie des bords reste visible. `--screen` ou
`--side` peut fixer respectivement l'écran ou le bord ; `--no-slide` et
`--no-spin` restent prioritaires. Un vortex sans rotation reste donc sur place,
mais droit.

### Les garder au démarrage

Le moyen le plus simple est d'enregistrer puis d'activer un profil. Le daemon
lancé à l'ouverture de session le charge tout seul, sans réinstallation :

```bash
doot --save-profile parade --burst-min 2 --burst-max 5 --formation wave
doot --activate-profile parade
```

Les installeurs savent aussi inscrire directement les salves dans la commande
de démarrage :

```bash
./install.sh --burst-min 2 --burst-max 5 --formation canon    # Linux, macOS
```

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -BurstMin 2 -BurstMax 5 -Formation canon
```

Dans ce second cas, le réglage part dans `install.json`, la fiche que relit
`doot --update` : il survit donc aux mises à jour. Éditer l'unité systemd, le
LaunchAgent ou le raccourci à la main marche aussi, mais **la prochaine mise à
jour les réécrit** — les installeurs les regénèrent depuis la fiche.

Sans ces options, la ligne engendrée est exactement celle d'avant les salves :
mettre doot à jour ne fait donc apparaître aucune salve chez personne.

Une salve n'échappe pas à la saison : elle dure — la pause plus la durée
d'affichage, autant de fois qu'il y a de doots — et la fenêtre saisonnière peut
donc se fermer en plein milieu. Chaque doot revérifie avant de s'afficher, comme
le daemon revérifie après chaque attente.

Par défaut `--burst-min` et `--burst-max` valent `1` : un déclenchement, un
doot, comme avant.

## 🕯️ Le rite du dernier soir

Une saison qui ferme sans rien dire ferme pour rien. Le **31 octobre à partir de
20 h**, le prochain déclenchement n'est plus tiré au sort : douze trompettistes
tournoient pour saluer la fermeture, et doot dépose la **carte de la saison**
dans le dossier de données.

```bash
doot --carte                    # sans attendre octobre
doot --carte ~/Images/          # ailleurs qu'au dossier de données
doot --event finale             # voir la finale tout de suite
```

La carte réunit les chiffres du registre, la grille des soirs et les médailles
gagnées. C'est un PNG que doot **compose lui-même** : `doot/png.py` sait déjà
décoder et écrire, `doot/police.py` apporte une fonte matricielle de 5×7 points
dessinée à la main, et les badges sont ceux livrés avec les succès. Aucune fonte
installée, aucune bibliothèque d'images : celles du système ne sont lisibles que
par Tkinter, qui ne sait pas rendre dans un fichier.

La finale ne peut pas sortir du tirage ordinaire — elle salue une fermeture, un
12 septembre lui ôterait tout son sens — et le rite n'a lieu **qu'une fois par
saison** : un démon relancé dans la soirée ne le rejoue pas. Si la carte échoue
à s'écrire, la crypte a quand même fermé ; seule l'image manque.

## 🎲 Les événements rares

Avant le tirage d'une mélodie, le daemon a 2 % de chances de lancer une
rencontre précomposée : les classiques `parade`, `pluie` et `vortex`, le
`duel` qui se répond entre les deux bords, le `mimic` déguisé en notification,
ou le `faux-bug` qui se coince, tremble et tombe hors de l'écran. Elles durent
quelques secondes et réutilisent tes images, tes sons et ton volume.

```bash
doot --events                         # noms et descriptions
doot --event parade --ignore-season   # essai immédiat
doot --event pluie --ignore-season
doot --event vortex --ignore-season
doot --event duel --ignore-season
doot --event mimic --ignore-season
doot --event faux-bug --ignore-season
```

Le **Codex des apparitions** révèle le nom et la description de chaque rencontre
déjà vue. Les autres gardent leur silhouette mais donnent un indice :

```bash
doot --codex
```

La contagion y possède sa propre entrée et ne se révèle qu'après avoir reçu un
signal d'une autre machine.

Une chance seule pourrait ne rien donner pendant très longtemps. Le compteur
de pitié force donc le centième déclenchement sans événement. Comme celui des
mélodies, il vit dans `state.json` et survit aux redémarrages :

```bash
doot --event-chance 0.05     # un déclenchement sur vingt en moyenne
doot --event-pity 50         # jamais plus de cinquante sans rencontre
doot --no-event              # aucune rencontre automatique
```

Les événements passent avant les mélodies pour un déclenchement donné. Ils ne
contournent jamais la saison et respectent `--no-sound`, `--no-image`,
`--no-slide` et `--no-spin`.

## 🎛️ Les profils persistants

Un profil mémorise les options de comportement — fréquence, salves, formation,
médias, animation, son, mélodies et événements — mais jamais une commande
ponctuelle comme `--stop`, `--update` ou `--once`.

```bash
# Crée deux ambiances sans lancer le daemon
doot --save-profile calme --min 3600 --max 10800 --no-sound --no-event
doot --save-profile chaos --min 120 --max 600 --burst-min 3 --burst-max 6 \
     --formation wave --event-chance 0.08

doot --profiles                 # liste ; * marque le profil actif
doot --profile chaos --once     # l'utilise seulement pour cette commande
doot --activate-profile chaos   # devient le défaut des prochains lancements
doot --deactivate-profile       # revient aux réglages historiques
doot --delete-profile calme
```

Le profil actif est chargé par un simple `doot`, donc aussi par le daemon déjà
installé au démarrage : inutile de rejouer l'installeur. Les options écrites sur
la commande remplacent celles du profil. `--no-profile` permet de l'ignorer
entièrement pour un lancement. Le fichier `profiles.json` reste lisible,
modifiable et local ; `doot --paths` donne son emplacement.

## 🦴 Les trois façons d'arriver

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

## 🎼 Les mélodies

```bash
doot --melodies                        # ce qui est jouable
doot --play spooky-scary-skeletons     # une mélodie fournie, tout de suite, puis on quitte
doot --rickroll                        # raccourci de --play rickroll
doot --play ~/sonneries/tetris.rtttl   # n'importe quel fichier RTTTL
doot --play rickroll --transpose -3    # trois demi-tons plus bas
```

Le démon en joue aussi de lui-même, sans qu'on demande rien : une fois sur
vingt, la mélodie remplace le doot du moment. Elle est tirée au hasard parmi
les tiennes et celles fournies.

Une chance seule laisse de longues séries sans rien. Un compteur de pitié les
borne, comme dans les jeux qui tirent au sort : le quarantième déclenchement
sans mélodie en joue une à coup sûr, ce qui porte le taux réel de 5,0 % à
5,7 %. Le compteur est gardé dans `state.json` (`doot
--paths`), donc il survit à la fermeture de session ; sinon quarante
déclenchements, soit plusieurs jours, ne seraient jamais atteints.

```bash
doot --melody-chance 0.2               # une fois sur cinq
doot --melody-chance 0 --melody-pity 40  # exactement tous les quarante, jamais avant
doot --no-melody                       # rien que des doots
```

Le squelette surgit et joue une mélodie **en doots**. Un seul son, celui du
`doot.mp3` fourni : le coup de trompette est isolé (`doot/assets/doot-note.wav`,
265 ms, un ré5) puis relu plus ou moins vite pour chaque note, comme une bande
qu'on accélère — un demi-ton, c'est 2^(1/12) fois plus vite. Rien n'est
synthétisé, tout le timbre vient de ce seul doot.

Une note plus longue que le coup de trompette est **tenue** comme le ferait un
sampleur : l'attaque telle quelle, puis la partie stable du son bouclée en
fondu enchaîné autant qu'il faut, puis la finale — le « t » du doot. Sans ça,
une blanche serait un toot suivi d'un silence, et un riff de sax deviendrait
du morse.

Cinq mélodies sont fournies :

- `rickroll`, le refrain de *Never Gonna Give You Up* en la♭ majeur comme le
  disque, avec sa synthé-basse syncopée en seconde voix ;
- `spooky-scary-skeletons` — le riff d'intro, les couplets et le pont d'Andrew
  Gold, en si mineur, relevés sur un arrangement piano
  ([Online Sequencer #32991](https://onlinesequencer.net/32991)) : la voix du
  dessus de la main droite et les fondamentales des accords en seconde voix,
  ralenties à 135 BPM parce qu'à la vitesse du disque les doots se marchent
  dessus ;
- `careless-whisper`, le riff de sax de George Michael et la basse électrique
  du même MIDI (quantifiés à la double-croche, 76 BPM), une quarte plus haut
  que le disque : le si♭3 du riff n'existe pas en RTTTL, et sol mineur tombe
  pile dans la fenêtre où le doot sonne bien. `--transpose -5` pour la
  tonalité d'origine ;
- `megalovania` (Undertale — un squelette, forcément) : le riff quatre fois,
  puis les deux thèmes **avec leur basse en seconde voix**, relevés sur
  [Online Sequencer #973167](https://onlinesequencer.net/973167) ;
- `this-is-halloween` (L'Étrange Noël de Monsieur Jack) : l'ostinato d'intro,
  le couplet et « This is Halloween » deux fois, relevés sur
  [Online Sequencer #3005280](https://onlinesequencer.net/3005280).

### Le format : RTTTL

Les mélodies sont des fichiers **RTTTL**, le format des sonneries Nokia. Rien à
inventer : des milliers de morceaux existent déjà sous cette forme, ils se
collent tels quels dans un fichier `.rtttl` du dossier `melodies/` (`doot
--paths`), et `doot --play nom-du-fichier` les joue. Un fichier à toi qui porte
le nom d'une mélodie fournie la remplace, comme un son ou une image.

Une ligne est une voix. Pour jouer plusieurs notes en parallèle, mets autant
de sonneries RTTTL complètes que tu veux, une par ligne, toutes au même tempo.
Les voix sont additionnées et chacune est ramenée à `1 / nombre_de_voix` : le
mix ne sature pas, quel que soit le nombre de voix. Chaque ligne affiche aussi
son propre squelette, qui hoche uniquement sur ses notes. Ils partagent un seul
overlay transparent, se rangent automatiquement en grille et se réduisent si
nécessaire : il n'y a pas de plafond artificiel. Les lignes vides et celles qui
commencent par `#` sont ignorées.

```
# Melodie et basse, ensemble a 120 BPM
Melodie:d=8,o=5,b=120:c,d,e,g
Basse:d=4,o=4,b=120:c,g
```

- `d` : durée par défaut (`1` ronde, `2` blanche, `4` noire, `8` croche, `16`, `32`)
- `o` : octave par défaut (`a4` = 440 Hz ; la norme dit 4 à 7, doot accepte 1 à 8,
  les basses d'un riff descendant volontiers sous le do4)
- `b` : tempo, en noires par minute
- puis chaque note : `[durée]nom[#][octave][.]` — `4e6.` est une noire pointée de
  mi6, `8p` une croche de silence, le point allonge de moitié et se lit aux trois
  places où on le rencontre (`8.f`, `8f.`, `8f5.`)

Une mélodie écrite trop haut ou trop bas ferait un écureuil ou un tuba : elle est
**ramenée par octaves entières** au plus près du ré5 du doot (le milieu de son
ambitus), ce qui ne change pas sa tonalité. `--transpose N` décale ensuite de N
demi-tons. Les mélodies fournies restent dans une plage où le squelette garde
sa voix de squelette.

### Le hochement

À chaque coup le squelette de la voix concernée **hoche la tête** : l'image se
penche de 7° vers la gauche en grossissant de 6 %, autour du poing qui tient la
trompette, puis se redresse en 180 ms. Les trois étapes sont dessinées une fois
pour toutes sur une toile commune, assez grande pour la plus penchée, et
aucune fenêtre ne bouge.

Le concert se donne sur place et debout : ni entrée par un bord, ni tour complet.
Les musiciens sont regroupés dans un seul overlay, en grille adaptée à l'écran.
Les images PNG se penchent indépendamment ; l'ASCII art fait voler les lettres
du bon squelette à chaque coup ; un GIF animé garde sa propre animation. La
mélodie est rendue en un seul WAV, puis jouée une seule fois par le lecteur
habituel, donc spatialisée comme le reste. Même règle de saison que `--once`.

## 🔊 Le son spatialisé

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

## 🗝️ Où sont les fichiers

`doot --paths` affiche tout. Par défaut :

| Système | Dossier de données |
| --- | --- |
| Linux   | `~/.local/share/doot` |
| macOS   | `~/Library/Application Support/doot` |
| Windows | `%LOCALAPPDATA%\doot` |

Il contient `image/` et `sound/` (tes médias), `doot.wav` (le jingle en cache),
`profiles.json` (tes profils), `state.json` (pitié et succès), `doot.log` (le
journal) et `doot.pid`.

## 🕸️ Dépannage

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

## ⚗️ Tests

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

## ⚙️ Comment ça marche

| Fichier | Rôle |
| --- | --- |
| `doot/season.py` | la fenêtre 1er septembre → 31 octobre |
| `doot/art.py` | l'ASCII art et les images de l'animation |
| `doot/image.py` | le choix du PNG/GIF déposé par l'utilisateur |
| `doot/screens.py` | l'énumération des écrans (Win32 / RandR / CoreGraphics) |
| `doot/wayland.py` | l'overlay natif Wayland, en layer-shell |
| `doot/overlay.py` | la boucle d'animation, partagée par les deux overlays |
| `doot/sound.py` | synthèse du jingle, durée et lecture selon l'OS |
| `doot/melodie.py` | les mélodies en doots : lecture RTTTL, accordage et rendu |
| `doot/evenements.py` | les trois rencontres rares précomposées |
| `doot/profiles.py` | le stockage et l'activation des profils persistants |
| `doot/succes.py` | les succès, les parts par machine et leur fusion |
| `doot/registre.py` | le registre : totaux, records, machines et grille de saison |
| `doot/contagion.py` | les signaux du doot contagieux et ce qu'ils portent |
| `doot/police.py` | la fonte matricielle 5x7, dessinée à la main |
| `doot/carte.py` | la carte de fin de saison, composée en PNG |
| `doot/audio.py` | la sortie audio native (PulseAudio/PipeWire, ALSA) |
| `doot/window.py` | l'overlay tkinter, la transparence, le fondu |
| `doot/cli.py` | la CLI, la boucle aléatoire, l'instance unique |

Le daemon tire un délai au hasard entre `--min` et `--max`, dort, vérifie que la
saison est toujours ouverte, tire d'abord une rencontre rare, sinon une mélodie,
sinon la salve ordinaire (un seul doot par défaut), puis recommence. Hors saison,
il se contente de revérifier la date toutes les heures.

## 📜 Licence

Le **code** est sous licence MIT, ainsi que l'ASCII art, le jingle synthétisé,
la fanfare de succès, le logo et les badges illustrés, qui sont originaux.

Les médias historiques dérivés du mème *skull trumpet* (`doot.png`, `doot.mp3`
et `doot-note.wav`) sont l'exception : ils ne sont pas couverts par la licence
MIT du projet. Ils sont inclus par commodité ; retire-les si ton usage l'exige,
et les médias que tu ajoutes toi-même restent soumis à leurs propres droits.
