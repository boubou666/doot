# Changelog

Toutes les évolutions notables de doot sont consignées ici.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le
projet applique le [versionnage sémantique](https://semver.org/lang/fr/).

> Les versions antérieures à la 1.0.0 ont été étiquetées après coup : doot a été
> écrit d'une traite, sans numérotation au fil de l'eau. Les étiquettes marquent
> les étapes réelles du dépôt, mais `doot --version` répond `1.0.0` dans ces
> commits-là, la chaîne n'ayant jamais été incrémentée à l'époque.

## [Non publié]

### Ajouté
- **Le rite du dernier soir.** Le 31 octobre à partir de 20 h, douze
  trompettistes saluent la fermeture de la crypte, et doot laisse derrière lui
  la **carte de la saison** : un PNG composé par ses soins, avec les chiffres du
  registre, la grille des soirs et les médailles gagnées. `doot --carte` l'écrit
  quand on veut. La finale ne sort jamais du tirage ordinaire, et le rite n'a
  lieu qu'une fois par saison.
- `doot/police.py`, une fonte matricielle de 5×7 points dessinée à la main :
  celles du système ne sont lisibles que par Tkinter, qui ne sait pas rendre
  dans un fichier, et en installer une ajouterait un binaire et une licence.
- `doot --stats` ouvre le **registre de la crypte** : les totaux, les records,
  la part de chaque machine de la flotte, les collections, et la saison en
  grille — une colonne par semaine, une case par soir. Le grimoire graphique en
  a son onglet. Rien n'est collecté de neuf : tout cela dormait déjà dans
  `state.json`, sans autre visage que le score.

### Modifié
- Le **Doot contagieux** transporte désormais ce qui a été joué : une rencontre
  rare traverse avec sa chorégraphie, une mélodie avec son nom. Les deux clés
  restent facultatives des deux côtés, donc une flotte se met à jour machine par
  machine. `--no-melody` et `--no-event` l'emportent sur ce que le signal
  demande, une mélodie inconnue du poste retombe en doot, et le nom reçu est
  cherché par égalité dans le catalogue local — jamais comme un chemin.

## [1.21.0] - 2026-09-20

### Ajouté
- La GUI possède désormais un cabinet des trophées illustré : les succès
  débloqués remontent en tête avec leur badge, leurs points et leur date, tandis
  que les autres montrent leur progression. La galerie s'adapte sur une ou deux
  colonnes et s'actualise après chaque commande.

## [1.20.0] - 2026-09-20

### Ajouté
- Le **Doot contagieux** fait voyager une apparition éphémère entre les
  machines d'une flotte chiffrée. Les signaux expirent après cinq minutes,
  ne se jouent qu'une fois par poste et ne rebondissent jamais.
- `doot --codex` ouvre le Codex des apparitions : les rencontres vues y sont
  révélées, les autres ne montrent qu'un indice.
- Trois rencontres rares : le duel de trompettes entre les bords, le Mimic
  déguisé en notification et le faux bug qui se coince avant de tomber.
- La formation `duel` alterne gauche et droite pour les salves ordinaires.

## [1.19.0] - 2026-09-17

### Ajouté
- `--sync-key-id` et `--sync-secret` posent les identifiants du seau dans la
  fiche du poste, et `DOOT_S3_KEY_ID` / `DOOT_S3_SECRET` les nomment dans
  l'environnement sans marcher sur les `AWS_*` d'un autre outil. `--sync-secret -`
  lit le secret sur l'entrée standard plutôt que de le laisser dans `ps`.

### Corrigé
- Les installeurs posent `cryptography`, que le partage chiffré réclame depuis
  la 1.18.0. Sans elle, `--sync-init` échouait sur toute machine dont le Python
  ne l'avait pas déjà par ailleurs - y compris après un `doot --update`, qui
  rejoue `install.sh`.
- `replica.json` naît en `0600` et le reste. Il porte la clé qui ouvre toute la
  flotte, et l'écriture atomique reposait les droits à `0644` à chaque cycle.

## [1.18.1] - 2026-09-17

### Corrigé
- `doot --update` tire maintenant explicitement `origin/main` au lieu de la
  branche laissée checkoutée dans le dépôt source, afin de ne plus annoncer une
  mise à jour réussie tout en réinstallant une ancienne version.

## [1.18.0] - 2026-09-17

### Ajouté
- Le partage des succès traverse désormais un stockage qu'on ne contrôle pas :
  chaque poste publie un objet **chiffré** (ChaCha20-Poly1305), nommé par un
  `HMAC(clé, identité)` pour que l'hébergeur ne puisse pas le relier à une
  machine. Une seule clé symétrique, recopiée d'un poste à l'autre par
  `doot --sync-join`, sans révocation et en le disant.
- Un **seau compatible S3** comme dépôt, R2, MinIO et B2 compris, signé en
  SigV4 sans SDK : `doot --sync-init s3://seau/prefixe --sync-endpoint URL`.
- `--sync-force` frappe une clé neuve, `--sync-endpoint` et `--sync-region`
  décrivent le seau.

### Modifié
- Les objets sont écrits **atomiquement** et nommés strictement, ce qui écarte
  les copies de conflit qu'un outil de synchronisation laisse derrière lui et
  évite qu'un pair lise un fichier à moitié écrit.
- Les réglages du partage, clé comprise, vivent dans `replica.json` et non dans
  `state.json`, que la documentation invite à sauvegarder et à copier.
- Changer de clé ne peut plus abandonner d'objet dans le dépôt : le poste
  retient la liste des clés quittées jusqu'à ce que leurs objets soient retirés,
  une rotation ratée puis rejouée comprise.

## [1.17.1] - 2026-09-17

### Corrigé
- La molette et les trackpads font maintenant défiler la galerie des commandes
  et les réglages, même lorsque le pointeur survole un bouton, un libellé ou un
  champ enfant.

## [1.17.0] - 2026-09-17

### Ajouté
- `doot --gui` et `doot-gui` ouvrent un grimoire graphique qui rassemble toutes
  les commandes et tous leurs réglages, prévisualise la ligne de commande et
  montre sa sortie sans dupliquer la logique de la CLI. Chaque action reprend
  les illustrations des succès, autour d'une nouvelle scène de squelette-maestro
  et de barres de défilement en forme d'os.
- `doot --sync-init CHEMIN` : le démon publie ses succès et relit ceux des
  autres machines à chaque doot, par un dossier partagé. Une panne du dossier
  n'interrompt jamais un doot, elle se lit dans `doot --succes`.
- `doot --export` et `doot --merge` font converger les succès de plusieurs
  machines sans serveur : chaque poste dépose son fichier dans un dossier
  partagé et lit ceux des autres. Refaire la fusion ne change rien, et réunir
  deux machines peut débloquer un succès qu'aucune n'avait atteint seule.

### Modifié
- L'identité de chaque poste vit dans `replica.json` et non plus dans
  `state.json`, que la documentation invite à sauvegarder et à copier. Deux
  installations qui la partageaient voyaient leurs progressions fusionnées par
  maximum : dix doots communs, puis cinq ici et sept là-bas, donnaient dix-sept
  au lieu de vingt-deux.
- Plusieurs succès gagnés d'un coup tiennent désormais sur une seule carte, au
  lieu d'une par succès. Cinq succès peuvent tomber sur le même doot, ce qui
  faisait cinq cartes bloquantes à la suite et dix-sept secondes sans rien
  d'autre. Un succès gagné en fusionnant deux machines a lui aussi sa médaille,
  là où il se contentait d'une ligne de texte.
- Chaque statistique déclare comment elle se fusionne, et les totaux sont
  rangés en parts par machine dans `state.json`. Sans cette distinction,
  copier le fichier d'une machine à l'autre faussait déjà les chiffres en
  silence, un total et un maximum étant indiscernables une fois écrits. Les
  fichiers existants sont repris sans perte : leurs totaux reviennent à la
  machine qui les a accumulés.

## [1.16.0] - 2026-09-17

### Ajouté

- Trois nouvelles formations de salve : `wave` alterne les bords et fait
  l'aller-retour sur les écrans, `rain` tombe du haut, et `vortex` impose les
  tours sur place. Les choix explicites d'écran, de bord et de mouvement restent
  prioritaires.
- Des profils persistants enregistrent les réglages dans `profiles.json`.
  `--save-profile`, `--profile`, `--activate-profile`, `--deactivate-profile`,
  `--delete-profile`, `--profiles` et `--no-profile` couvrent leur cycle de vie ;
  le profil actif est repris automatiquement par le daemon existant.
- Trois événements rares — parade, pluie d'os et vortex — ont une chance de 2 %
  par déclenchement et un compteur de pitié de 100, tous deux réglables. Ils se
  listent avec `--events`, se testent avec `--event`, et se coupent avec
  `--no-event`.
- Quatre succès illustrés récompensent les quatre formations, la première
  rencontre rare, la collection des trois événements et l'activation d'un
  profil. Le catalogue compte désormais 18 succès et 475 points.

## [1.15.0] - 2026-09-17

### Ajouté

- Quatorze succès locaux suivent les doots, salves, mélodies, formations et jours
  actifs sans télémétrie. `doot --achievements` (ou `--succes`) affiche les succès,
  leur progression et un score sur 375 points, conservés dans `state.json`. Chaque
  déblocage affiche son badge illustré et joue une micro-fanfare RTTTL à deux voix ;
  `--no-sound` conserve le toast sans le son.

### Modifié

- Le README prend des airs de grimoire d'Halloween et accueille un logo original
  assorti aux badges de succès.

## [1.14.0] - 2026-09-16

### Ajouté
- Le démon joue parfois une mélodie à la place du doot du moment, une fois sur
  vingt, tirée au hasard parmi les tiennes et celles fournies. `--melody-chance`
  règle la proportion, `--no-melody` coupe tout.
- Un compteur de pitié borne les séries sans mélodie : le quarantième
  déclenchement qui n'en a pas joué en joue une à coup sûr, `--melody-pity` le
  règle. Il est gardé dans `state.json` plutôt qu'en mémoire, le démon repartant
  à chaque ouverture de session.

## [1.13.1] - 2026-09-14

### Corrigé

- Le tour complet ne bloque plus le callback tkinter : le squelette finit son
  animation et disparaît au lieu de rester affiché indéfiniment sous Windows.

## [1.13.0] - 2026-09-13

### Modifié

- `careless-whisper`, `rickroll` et `spooky-scary-skeletons` gagnent une
  basse en seconde voix et affichent désormais deux squelettes. Les trois
  accompagnements finissent exactement avec leur mélodie et conservent son
  accordage.

## [1.12.0] - 2026-09-13

### Ajouté

- Une mélodie peut avoir autant de voix parallèles que de lignes RTTTL. Elles
  partagent le tempo et sont mixées sans saturation. `doot --melodies` annonce
  le nombre de voix.
- `doot --play` affiche un squelette par voix, sans plafond : le groupe est
  rangé en grille dans un seul overlay et chacun hoche uniquement sur ses
  propres notes, pendant que la piste mixée ne démarre qu'une fois.
- `megalovania` gagne la basse de son arrangement en seconde voix.
- `megalovania` (le riff quatre fois puis les deux thèmes) et
  `this-is-halloween` (ostinato, couplet et refrain), relevés sur des
  arrangements Online Sequencer.

### Modifié

- Le recentrage automatique d'une mélodie vise le milieu de son ambitus, plus
  la médiane : un riff de basse répété sous un thème aigu n'envoie plus le
  thème dans les aigus. Les mélodies déjà fournies ne bougent pas.
- Le lecteur RTTTL accepte les octaves 1 à 8 (la norme s'arrête à 4–7), pour
  les notes de basse d'un riff.

### Supprimé

- Les canaux de distribution PyPI et AUR sont abandonnés. GitHub Releases devient
  l'unique source publiée ; la recette AUR et son `.SRCINFO` quittent le dépôt.
  Le `PKGBUILD` local reste disponible pour une construction manuelle sous Arch.

## [1.11.0] - 2026-09-13

### Ajouté

- `careless-whisper` : le riff de sax de George Michael en doots, relevé sur
  le canal sax d'un MIDI, en sol mineur (une quarte au-dessus du disque).
- Les notes plus longues que le coup de trompette sont tenues : la partie
  stable du doot est bouclée en fondu enchaîné, puis sa finale jouée. Une
  blanche n'est plus un toot suivi d'un silence.

### Modifié

- La copie de la recette AUR et son `.SRCINFO` ciblent désormais l'archive
  vérifiée de la version 1.10.0.

## [1.10.0] - 2026-09-13

### Ajouté

- `doot --play MELODIE` joue n'importe quelle mélodie en doots, depuis un
  fichier **RTTTL** (le format des sonneries Nokia) : un nom parmi les
  mélodies fournies ou déposées dans `<data>/melodies/`, ou un chemin.
  `doot --melodies` les liste, `--transpose N` décale de N demi-tons. Chaque
  mélodie est ramenée par octaves entières au plus près du ré5 du doot.
- `spooky-scary-skeletons` : le riff d'intro, les couplets et le pont d'Andrew
  Gold en doots, relevés sur un arrangement piano, à 135 BPM.

### Modifié

- `--rickroll` est désormais un raccourci de `--play rickroll` : la partition
  sort du code pour `doot/assets/melodies/rickroll.rtttl`, à l'identique. Le
  module `rickroll.py` devient `melodie.py`, et le WAV rendu s'appelle
  `melodie.wav`.
- La copie de la recette AUR et son `.SRCINFO` ciblent désormais l'archive
  vérifiée de la version 1.9.0.

## [1.9.0] - 2026-09-13

### Ajouté

- `doot --rickroll` : le squelette joue le refrain de *Never Gonna Give You Up*
  en doots. Le coup de trompette du `doot.mp3` est isolé dans
  `doot/assets/doot-note.wav` et relu plus ou moins vite pour chaque note, en
  la♭ majeur à 113 BPM ; rien n'est synthétisé. À chaque coup le squelette
  hoche la tête (7°, 6 % plus grand, autour du poing), sur les trois overlays.

### Corrigé

- `install.ps1` échouait sous Windows PowerShell 5.1 sur `SyntaxError: '('
  was never closed` : le script Python qui installe desktop-overlay était
  passé à `python -c` en un argument, et PowerShell 5.1 n'échappe pas les
  guillemets qu'il contient. Il passe maintenant par un fichier temporaire.
  pwsh 7 n'avait pas ce défaut, ce qui l'a caché à la CI depuis la 1.8.0.

### Modifié

- La copie de la recette AUR et son `.SRCINFO` ciblent désormais l'archive
  vérifiée de la version 1.8.0 et desktop-overlay 0.2.1.

## [1.8.0] - 2026-09-12

### Modifié
- L'énumération des écrans, la géométrie partagée et la préparation des
  fenêtres tkinter viennent désormais de desktop-overlay 0.2.1. Doot garde
  son choix aléatoire d'écran, ses textes français et ses méthodes historiques
  derrière un adaptateur mince.
- Les installeurs autonomes vérifient le wheel 0.2.1 par SHA-256 ; la recette
  Arch dépend du paquet partagé python-desktop-overlay.
- Les nouvelles versions sont distribuées par GitHub Releases : le paquet
  référence le wheel 0.2.1 du moteur et son SHA-256, sans compte PyPI pour le
  moteur.

### Corrigé
- Sous Windows, les styles click-through et sans activation sont posés avant
  le premier affichage de la fenêtre.
- Les coordonnées tkinter négatives utilisent maintenant une géométrie signée
  valide pour les écrans placés à gauche ou au-dessus de l'écran principal.

## [1.7.2] - 2026-09-12

### Corrigé
- L'attente des sons natifs à la sortie du programme ne court plus contre
  les fils de lecture. `_laisse_finir` parcourait `_en_cours` sans le verrou
  pendant qu'un fil qui finit s'en retire : un fil s'achevant juste à ce
  moment-là levait un `RuntimeError` au moment même où doot s'arrêtait. La
  copie de l'ensemble se prend désormais sous le verrou, et les `join` se
  font sans lui, sans quoi la lecture attendue ne pourrait plus se retirer et
  chaque sortie durerait le délai entier. Signalé par la revue du même code
  porté dans butbutbut.

## [1.7.1] - 2026-09-12

### Corrigé
- Le daemon ne tourne plus aveugle toute la session. L'unité s'installait
  `WantedBy=default.target`, donc elle démarrait avec le gestionnaire
  utilisateur, avant que la session ne publie `DISPLAY` et `WAYLAND_DISPLAY`.
  Comme l'environnement d'un processus ne change plus une fois qu'il tourne,
  chaque doot échouait ensuite sur `no display name and no $DISPLAY` sans que
  l'unité cesse d'afficher `active`. Elle s'accroche désormais à la session
  graphique, et à `plasma-workspace.target` quand celle-ci a démarré, Plasma
  publiant ces variables au même moment. L'installeur emploie `reenable` pour
  que la mise à jour retire le lien périmé vers `default.target`, et le daemon
  refuse de démarrer sans affichage plutôt que de boucler, ce qui laisse
  systemd le relancer avec l'environnement complet.

## [1.7.0] - 2026-09-10

### Ajouté
- `--formation canon` chorégraphie les salves : les apparitions alternent les
  bords dans le sens gauche, haut, droite, bas et parcourent les écrans
  disponibles dans l'ordre. `random` conserve le tirage indépendant par défaut.
  La formation est enregistrée par les installeurs et restaurée lors des mises
  à jour.

### Corrigé
- **Sous Windows, un PID périmé condamnait doot au silence.** Quand la machine
  s'arrête, le daemon est tué sans pouvoir effacer son `doot.pid`. Le test de
  vie se contentait d'un `OpenProcess` réussi — or l'objet noyau d'un processus
  survit à sa mort tant qu'un handle traîne quelque part, et l'appel réussit
  donc encore. doot se croyait déjà lancé et se retirait à chaque ouverture de
  session, définitivement, pendant que `--status` annonçait un daemon « actif »
  qui n'existait plus. Le handle est désormais interrogé avec
  `WaitForSingleObject` : signalé, le processus est mort et la place est libre.
  Les handles sont au passage déclarés sur 64 bits, pour ne plus être rendus
  tronqués à `CloseHandle`.

## [1.6.0] - 2026-09-07

### Ajouté
- Une troisième façon d'arriver : le **tour complet**. Le squelette surgit sur
  place et fait un tour sur lui-même avant de s'immobiliser, droit — 700 ms par
  défaut, sur un quart des apparitions sur place. `--spin` l'impose (et impose
  l'apparition sur place), `--no-spin` le coupe, `--spin-chance` et `--spin-ms`
  en règlent la fréquence et la durée. C'est la rotation par quarts de l'entrée
  par un bord, étalée dans le temps ; l'image est centrée dans le carré qui la
  contient pour que les quatre orientations aient la même taille, et que la
  fenêtre ne change ni de dimensions ni de place au milieu du tour. Réservé aux
  PNG, comme la rotation d'entrée : les GIF animés et l'ASCII art restent
  droits.

- Les installeurs prennent `--burst-min` / `--burst-max` / `--burst-delay`
  (`-BurstMin` / `-BurstMax` / `-BurstDelay` sous Windows) et les inscrivent
  dans `install.json`, que `doot --update` relit. Les salves n'étaient
  atteignables qu'en tapant la commande soi-même : le doot lancé à l'ouverture
  de session tient sa ligne des installeurs, et la modifier à la main ne
  tenait pas — l'unité systemd, le LaunchAgent et le raccourci sont regénérés
  à chaque mise à jour. Les drapeaux ne sont écrits que s'ils changent quelque
  chose, donc une installation existante retrouve mot pour mot la commande
  qu'elle avait déjà.

## [1.5.0] - 2026-09-07

### Ajouté
- Les salves : `--burst-min` / `--burst-max` enchaînent plusieurs doots sur un
  seul déclenchement, le nombre étant retiré à chaque fois entre les deux
  bornes, et `--burst-delay` règle la pause entre deux doots de la salve. Chaque
  doot repasse par le tirage complet — animation, bord d'entrée, position,
  écran, image, son — parce qu'une salve qui rejouerait la même apparition
  n fois n'aurait aucun intérêt. La saison est revérifiée avant chaque doot de
  la salve : une salve dure, et la fenêtre saisonnière peut se fermer en plein
  milieu comme elle peut se fermer pendant l'attente du daemon. Par défaut
  `1` / `1` : le comportement d'avant, un déclenchement pour un doot.

- Une sortie audio native (`doot/audio.py`) : les WAV partent directement vers
  PulseAudio par `libpulse-simple`, ou vers ALSA par `libasound`, appelées en
  ctypes comme `x11.py` appelle libX11. PipeWire n'a pas besoin d'un chemin à
  lui, il sert l'interface PulseAudio. Plus de sous-processus, plus de fichier
  temporaire panoramisé, et le panoramique appliqué sur les échantillons comme
  `pan_wav` le fait déjà, donc les deux chemins ne peuvent plus diverger.
  Toujours sans dépendance.
- `doot --status` indique la sortie audio utilisée et rappelle que le lecteur
  externe ne sert plus qu'aux formats compressés.

- Un overlay Wayland natif (`doot/wayland.py`), qui parle `wlr-layer-shell`
  directement sur la socket du compositeur. C'est le seul protocole qui laisse
  un client choisir sa sortie et s'y positionner : ni le cœur de Wayland ni
  xdg-shell ne le permettent, et XWayland divise les coordonnées par le facteur
  d'échelle global avant de poser la fenêtre sur une dalle qui ne suit pas la
  géométrie annoncée. Le multi-écrans devient donc exact, vérifié sur Hyprland ;
  Sway, river et KDE implémentent aussi layer-shell, mais le comportement de
  KWin sur les marges négatives du glissement n'a pas été regardé. GNOME ne
  l'implémente pas du tout : `available()` y renvoie faux et le chemin X11
  reprend la main. Toujours sans dépendance : le descripteur du tampon partagé
  passe par `SCM_RIGHTS`, tout est dans la bibliothèque standard.
- `--screens` et `--status` décrivent les écrans tels que les verra le backend
  qui affichera vraiment, et non un autre espace de coordonnées.

### Modifié
- Les formats compressés gardent le lecteur externe : aucun décodeur audio
  n'existe dans la bibliothèque standard. `sound.stop_all()` coupe désormais
  aussi les lectures natives en cours.

### Corrigé
- L'overlay Wayland lit la géométrie logique des écrans par
  `zxdg_output_manager_v1` au lieu de la déduire de `mode / scale`.
  `wl_output.scale` est un entier : sous échelle fractionnaire les compositeurs
  laissent `mode` en pixels physiques et arrondissent `scale` au supérieur, si
  bien qu'une dalle 2560 à l'échelle 1.5 était annoncée à 1280 unités logiques
  au lieu de 1707. Le squelette se cantonnait alors au quart supérieur gauche,
  et une entrée par la droite démarrait au milieu de la dalle au lieu de son
  bord. Le calcul précédent sert de repli si l'interface manque.
- Le son revient quand le doot est spatialisé. mpv n'atteint le filtre `pan` de
  libavfilter que par `--af=lavfi=[...]` ; écrit `--af=pan=...`, son analyseur
  d'options bute sur les barres verticales, refuse de démarrer et le doot est
  muet. Comme le panoramique s'applique dès que le squelette n'est pas au centre
  du bureau, presque tous les doots l'étaient sur une configuration multi-écrans.
- Un lecteur qui refuse la syntaxe du filtre est rejoué sans panoramique, au
  lieu de laisser un silence. Le module promettait déjà « non panoramisé plutôt
  que muet », mais rien ne tenait la promesse quand le refus venait du lecteur.
- Un son stéréo garde ses deux canaux quand le doot est spatialisé. Le filtre
  tirait les deux sorties du canal d'entrée gauche, ce qui jetait le droit,
  alors que `pan_wav` fait le même travail sur les WAV en gardant chacun le
  sien. Le même fichier changeait donc de rendu au franchissement de
  `SEUIL_PAN` — la marche exacte que `stereo_gains` s'applique à éviter par
  ailleurs. Un `aformat` monte d'abord le mono en stéréo, ce qui laisse une
  seule expression valable pour les deux sources.
- Le lecteur rendu par `play_async` est toujours celui qui joue. Quand le
  repli sans panoramique relançait le son, le processus rendu restait le mort :
  sans effet tant que `release` laisse volontairement la note finir, mais le
  lecteur de repli aurait été injoignable le jour où il coupera vraiment.

## [1.4.2] - 2026-09-07

### Corrigé
- L'énumération des écrans sous Linux ne dépend plus du binaire `xrandr`, qui
  vit dans un paquet à part (`xorg-xrandr`, `x11-xserver-utils`) que rien
  n'installe pour un bureau. Sans lui, la détection échouait en silence et doot
  se rabattait sur un unique écran 1920x1080 à l'origine, sans rapport avec la
  machine. doot interroge maintenant RandR 1.5 sur la socket X, avec la même
  requête que celle envoyée par `xrandr --listmonitors` ; le binaire reste en
  second recours.

## [1.4.1] - 2026-09-07

### Ajouté
- Le `PKGBUILD` joue la suite de tests pendant la construction du paquet Arch,
  avec `python-pillow` en `checkdepends` pour que les tests de conformité PNG
  ne se contentent pas de sauter — sans lui, ils sauteraient en silence et la
  construction resterait verte.
- `optdepends` mentionne `mpv` et `ffmpeg` pour les sons compressés et la
  spatialisation, et `xorg-xrandr` pour la détection des écrans multiples.
- La CI vérifie la syntaxe du `PKGBUILD`, qui n'était couvert par rien.

### Corrigé
- La réécriture du chemin dans l'unité systemd est contrôlée : un `sed` qui ne
  trouvait plus son motif laissait sans un mot une unité pointant dans le vide.
  La construction échoue désormais.
- Le README annonçait « Depuis PyPI » puis expliquait d'abord comment installer
  uv. Les commandes doot passent devant, le prérequis derrière.

### Note
- `sha256sums` reste à `SKIP`, et c'est contraint et non négligent : ce fichier
  vit **dans** l'archive qu'il décrit, donc y inscrire la somme de cette archive
  la modifierait, et modifierait sa somme. Le point fixe est inatteignable. Un
  `PKGBUILD` de l'AUR n'a pas ce problème, vivant à côté des sources. La raison
  est écrite dans le fichier pour que la question ne se rouvre pas.

## [1.4.0] - 2026-09-06

L'outillage passe à uv, et Python 3.8 redevient une promesse tenue plutôt
qu'une case cochée.

### Ajouté
- La CI installe l'interpréteur par uv au lieu de dépendre de ce que l'image du
  runner embarque, ce qui remet `ubuntu / 3.8` dans la matrice — les images
  GitHub ne la fournissent plus ([#6](https://github.com/boubou666/doot/pull/6)).
- Le workflow de release construit par `uv build --no-sources` et vérifie les
  métadonnées par `uvx twine check`, sans rien installer à côté des paquets
  ([#8](https://github.com/boubou666/doot/pull/8)).
- `uv publish --trusted-publishing always` remplace l'action tierce
  ([#9](https://github.com/boubou666/doot/pull/9)). Le mode `always` donne un
  échec net si le jeton OIDC manque, au lieu d'une bascule silencieuse vers une
  recherche d'identifiants. uv invalide en plus le jeton de courte durée après
  l'envoi, y compris quand celui-ci échoue.

### Modifié
- Le README propose `uv` pour installer depuis PyPI, et `uvx` pour lancer doot
  sans l'installer. Il dit aussi où prendre uv, sur les trois systèmes. pipx
  reste indiqué pour qui l'a déjà. La ligne `uvx` porte `--ignore-season`, sans
  quoi une première visite hors saison lit un message et ne voit aucun
  squelette.
- `requires-python` remonte de `>=3.9` à `>=3.8`, avec le classifier
  correspondant. Cette borne avait été descendue faute de pouvoir éprouver 3.8,
  les images GitHub ne la fournissant plus. Depuis que uv télécharge
  l'interpréteur, la CI la couvre à nouveau : l'annoncer n'est plus une promesse
  en l'air. À savoir tout de même : 3.8 est en fin de vie depuis octobre 2024,
  doot y tourne mais l'interpréteur ne reçoit plus de correctifs.

## [1.3.0] - 2026-09-06

doot s'installe désormais en une commande, sur les trois systèmes, sans cloner
quoi que ce soit.

### Ajouté
- Publication sur PyPI : `pipx install spooky-doot`. Le nom `doot` était déjà
  pris par un lanceur de tâches, seul le nom de distribution change — le module
  et la commande restent `doot`.
- Le workflow de release envoie les paquets à PyPI après avoir publié la
  release GitHub, dans un job séparé pour qu'un refus de PyPI n'emporte pas une
  release déjà faite. L'authentification passe par le jeton OIDC de GitHub :
  aucun secret n'est stocké dans le dépôt.
- `twine check` valide les métadonnées avant publication.
- Métadonnées enrichies pour PyPI : classifiers par version de Python et par
  système, liens vers le changelog et le dépôt.

### Modifié
- `requires-python` passe de `>=3.8` à `>=3.9`, ce que la CI éprouve
  réellement. Annoncer 3.8 laissait `pip` installer le paquet sur une version
  que personne ne teste.

## [1.2.1] - 2026-09-06

### Corrigé
- Les PNG en couleur 3 que la norme interdit lèvent désormais `PngError` au
  lieu de se décoder en pixels entièrement transparents
  ([#4](https://github.com/boubou666/doot/pull/4), ferme
  [#3](https://github.com/boubou666/doot/issues/3)). Quatre cas : bloc `PLTE`
  absent, index qu'aucune entrée ne couvre, `tRNS` plus long que la palette, et
  `PLTE` dont la longueur n'est pas un multiple de trois.
- L'enjeu n'est pas cosmétique : `PngError` est ce qui fait basculer
  `window.py` sur le chemin tkinter. Une image refusée proprement s'affiche
  donc quand même par l'autre voie, là où une image acceptée puis rendue vide
  laissait un doot muet et invisible, sans indice sur la cause.
- Le contrôle se fait une fois avant la boucle, et lui retire au passage son
  test par pixel : une image saine n'y perd rien.

## [1.2.0] - 2026-09-06

Le squelette ne se contente plus d'apparaître : il peut entrer par n'importe
lequel des quatre bords de l'écran, en glissant, et pivote pour avoir les pieds
sur celui d'où il vient. Les deux façons d'arriver se côtoient, tirées au sort.

### Ajouté
- Deux façons d'arriver, tirées au sort à chaque apparition : surgir au milieu
  de l'écran comme depuis toujours, ou entrer en glissant depuis un bord. Une
  fois sur deux par défaut, réglable par `--slide-chance`. Demander un bord
  précis avec `--side` impose l'entrée, sinon la demande n'aurait d'effet
  qu'une fois sur deux.
- L'entrée se fait avec une décélération cubique sur 420 ms par défaut. Le
  squelette s'arrête contre le bord, à quelques pixels près, et ne s'enfonce
  pas dans l'écran : ce serait une traversée, pas une entrée.
- Les quatre bords sont possibles, et l'image **pivote** pour poser son bas
  contre celui par lequel elle entre : un quart de tour horaire pour la gauche,
  un antihoraire pour la droite, un demi-tour pour le haut, rien pour le bas.
  Le squelette a donc toujours les pieds sur le bord d'où il vient.
- Le squelette ASCII, lui, ne pivote pas — des glyphes à chasse fixe tournés
  d'un quart de tour ne veulent plus rien dire. Il est retourné quand il entre
  par la droite : les obliques et les parenthèses basculent, et les lettres du
  *doot* changent de côté sans cesser d'être lisibles, les renverser telles
  quelles aurait donné « ! t o o d ».
- `png.write_png()`, un encodeur PNG minimal. tkinter ne sait pas pivoter et
  n'accepte des pixels avec leur transparence que par un fichier : l'image est
  donc décodée, pivotée, puis réécrite à côté.
- Options `--slide-chance`, `--side` (`left`, `right`, `top`, `bottom`),
  `--slide-ms` et `--no-slide`.

### Modifié
- Plus de fondu d'apparition pendant le glissement : le bord de l'écran révèle
  déjà le squelette, et les deux ensemble font bouillie. Le fondu de sortie est
  conservé.

## [1.1.0] - 2026-09-06

Première version où la mise à jour tient debout pour tout le monde, y compris
pour qui a installé depuis une release et n'a aucun dépôt sous la main. Elle
embarque évidemment la spatialisation du son et la mise à jour intégrée,
arrivées respectivement en [0.7.0](#070---2026-09-06) et
[1.0.0](#100---2026-09-06), l'historique étant linéaire.

### Ajouté
- `doot --check-update` se rabat sur le numéro de version, comparé à celui de
  la dernière release, quand l'installation n'a pas de dépôt git derrière elle.
  Il répondait jusqu'ici « commit installé inconnu » indéfiniment, à ceux-là
  mêmes qui ne peuvent pas aller vérifier par leurs propres moyens.
- Le workflow de release vérifie que l'étiquette correspond à la version
  déclarée dans les trois fichiers qui la portent — `doot/__init__.py`,
  `pyproject.toml` et le `PKGBUILD` — et non plus dans le seul premier, les
  deux autres pouvant dériver sans que rien ne le signale.

### Corrigé
- Après une mise à jour par archive, la fiche d'installation gardait comme
  source le dossier temporaire effacé dans la foulée. Elle reçoit désormais le
  commit résolu, et plus de chemin mort : les vérifications suivantes
  redeviennent précises au lieu de rester muettes.

## [1.0.0] - 2026-09-06

Première version numérotée pour de bon, et la seule où l'étiquette correspond à
ce que le code annonce.

### Ajouté
- `doot --update` met à jour une installation existante sur les trois systèmes :
  il relit la fiche laissée par l'installeur, rafraîchit la source et rejoue
  l'installeur avec les mêmes options, en arrêtant puis relançant le daemon.
- `doot --check-update` dit si une version plus récente existe, sans rien
  installer.
- Deux voies pour récupérer le code : `git pull --ff-only` si le dépôt cloné est
  toujours là, sinon l'archive de la branche principale téléchargée depuis
  GitHub. La seconde ne demande ni git ni le clone d'origine.
- Fiche `install.json` déposée par les installeurs dans le dossier de données :
  origine du code, commit, options d'installation.
- Refus explicite de se mettre à jour quand doot vient d'un gestionnaire de
  paquets, avec renvoi vers celui-ci.
- Ce changelog, et un workflow qui publie une release à chaque étiquette.

### Corrigé
- La fiche d'installation était illisible sous Windows : PowerShell 5.1 écrit
  l'UTF-8 avec un BOM, que `json.loads` refuse. `--check-update` annonçait un
  commit inconnu sur une installation pourtant enregistrée. Lecture en
  `utf-8-sig`.
- Les installeurs ne pouvaient plus être rejoués pendant que doot tournait : le
  daemon garde le dossier du code ouvert et Windows refuse de remplacer des
  fichiers verrouillés. Ils arrêtent désormais le daemon avant la copie et le
  relancent ensuite. Sous systemd, `enable --now` ne relançait pas une unité
  déjà active, c'est maintenant `restart`.
- `update.py` appelle `cli.paths()` au moment de s'en servir au lieu de
  l'importer une fois pour toutes, sans quoi la fonction n'était plus
  remplaçable et les tests écrivaient dans le vrai dossier de données.

## [0.7.0] - 2026-09-06

### Ajouté
- Spatialisation du son : le doot sort du côté où le squelette apparaît, calculé
  sur l'ensemble du bureau virtuel et non sur un écran isolé.
- Les WAV sont panoramisés dans leurs échantillons, ce qui fonctionne partout ;
  les formats compressés passent par MCI sous Windows et par un filtre `pan`
  pour `mpv` ou `ffplay` sous Linux.
- Option `--no-pan`.

### Corrigé
- Au centre exact, le canal droit sortait une unité en dessous du gauche sous
  Linux : `cos(π/4)` et `sin(π/4)` ne donnent pas le même dernier bit d'une libm
  à l'autre, et la troncature amplifiait l'écart. Gains arrondis, canaux
  strictement symétriques.
- Les échantillons sont arrondis au lieu d'être tronqués, `int()` ajoutant un
  biais à chaque valeur.

### Modifié
- Le canal dominant reste à plein volume, seul l'opposé est atténué. Un
  panoramique à puissance constante aurait rendu le doot 3 dB plus discret
  qu'avant, avec un saut audible au franchissement du seuil.

## [0.6.0] - 2026-09-06

### Ajouté
- Suite de tests qui fabrique les PNG octet par octet à partir de pixels connus,
  au lieu de comparer à Pillow : elle couvre le gris 2 et 4 bits, `tRNS` hors
  palette et sous 8 bits, le 16 bits, les cinq filtres de ligne et les entrées
  refusées ([#2](https://github.com/boubou666/doot/pull/2)).

### Corrigé
- Un IDAT illisible laissait remonter `zlib.error` au lieu de `PngError`,
  faisant mentir le contrat du module.

## [0.5.0] - 2026-09-06

### Ajouté
- Vraie transparence par pixel sous X11 et XWayland : fenêtre ARGB de profondeur
  32 ouverte via libX11 en ctypes, composée avec le bureau
  ([#1](https://github.com/boubou666/doot/pull/1)).
- Décodeur PNG maison en pur stdlib, sortie en BGRA à alpha prémultiplié.
- Click-through sous X11, que seul Windows avait jusque-là.

### Corrigé
- Les index de palette étaient étirés comme des intensités, ce qui faisait lire
  la mauvaise entrée de PLTE sur les PNG palette sous 8 bits.
- Le gestionnaire d'erreurs X était posé une seule fois alors qu'il est global
  au processus : un seul repli vers tkinter et la protection disparaissait. Il
  est désormais installé et restauré autour de chaque overlay.

## [0.4.0] - 2026-09-06

### Ajouté
- CI GitHub Actions sur Linux, Windows et macOS, de Python 3.9 à 3.13.
- Suite de tests couvrant les bornes de la saison, le placement multi-écrans, la
  synthèse du jingle et le refus hors saison.
- Vérification de la syntaxe des quatre installeurs.

## [0.3.0] - 2026-09-06

### Ajouté
- Image et son fournis d'office, pour que ça marche dès la première
  installation.
- Gestion multi-écrans : énumération réelle des moniteurs via Win32, `xrandr` et
  CoreGraphics, avec repli sur un écran unique.
- Options `--screen` et `--screens`.

### Corrigé
- L'installeur Windows ne trouvait jamais Python : le tableau d'arguments était
  passé comme un seul argument faute de splatting, et PowerShell mangeait les
  guillemets de la sonde.

## [0.2.0] - 2026-09-06

### Ajouté
- Mode image : un PNG ou un GIF animé remplace l'ASCII art.
- Sons compressés en plus du WAV : mp3, ogg, opus, flac, m4a.
- Section « Au secours, faites-le taire » en tête du README, avec le retrait
  manuel système par système.

### Modifié
- La durée d'affichage suit la durée du son, pour ne plus couper la note.
- Son et image sont relus à chaque apparition, donc modifiables sans redémarrer
  le daemon.

## [0.1.0] - 2026-09-06

### Ajouté
- Première version : un squelette trompettiste en ASCII surgit au hasard sur
  l'écran, avec un jingle deux notes synthétisé localement.
- Fenêtre saisonnière du 1er septembre au 31 octobre inclus, appliquée par le
  programme lui-même et pas seulement par le planificateur.
- Overlay sans bordure, sans vol de focus, click-through sous Windows.
- Installeurs sans droits administrateur pour Windows, macOS et Linux, avec
  démarrage automatique, et un PKGBUILD pour Arch.

[Non publié]: https://github.com/boubou666/doot/compare/v1.20.0...HEAD
[1.20.0]: https://github.com/boubou666/doot/compare/v1.19.0...v1.20.0
[1.19.0]: https://github.com/boubou666/doot/compare/v1.18.1...v1.19.0
[1.18.1]: https://github.com/boubou666/doot/compare/v1.18.0...v1.18.1
[1.18.0]: https://github.com/boubou666/doot/compare/v1.17.1...v1.18.0
[1.17.1]: https://github.com/boubou666/doot/compare/v1.17.0...v1.17.1
[1.17.0]: https://github.com/boubou666/doot/compare/v1.16.0...v1.17.0
[1.16.0]: https://github.com/boubou666/doot/compare/v1.15.0...v1.16.0
[1.15.0]: https://github.com/boubou666/doot/compare/v1.14.0...v1.15.0
[1.14.0]: https://github.com/boubou666/doot/compare/v1.13.1...v1.14.0
[1.13.1]: https://github.com/boubou666/doot/compare/v1.13.0...v1.13.1
[1.13.0]: https://github.com/boubou666/doot/compare/v1.12.0...v1.13.0
[1.12.0]: https://github.com/boubou666/doot/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/boubou666/doot/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/boubou666/doot/compare/v1.9.0...v1.10.0
[1.9.0]: https://github.com/boubou666/doot/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/boubou666/doot/compare/v1.7.2...v1.8.0
[1.7.2]: https://github.com/boubou666/doot/compare/v1.7.1...v1.7.2
[1.7.1]: https://github.com/boubou666/doot/compare/v1.7.0...v1.7.1
[1.7.0]: https://github.com/boubou666/doot/compare/v1.6.0...v1.7.0
[1.6.0]: https://github.com/boubou666/doot/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/boubou666/doot/compare/v1.4.2...v1.5.0
[1.4.2]: https://github.com/boubou666/doot/compare/v1.4.1...v1.4.2
[1.4.1]: https://github.com/boubou666/doot/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/boubou666/doot/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/boubou666/doot/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/boubou666/doot/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/boubou666/doot/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/boubou666/doot/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/boubou666/doot/compare/v0.7.0...v1.0.0
[0.7.0]: https://github.com/boubou666/doot/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/boubou666/doot/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/boubou666/doot/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/boubou666/doot/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/boubou666/doot/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/boubou666/doot/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/boubou666/doot/releases/tag/v0.1.0
