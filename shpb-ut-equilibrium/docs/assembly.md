# Assemblage du banc SHPB (repère global)
Y = axe des barres / traction, Z = vers le haut, X = largeur de l'éprouvette.
Unités : mm.

| Instance   | Rotation              | Translation              |
|------------|-----------------------|--------------------------|
| PUSHER     | +90° autour de X      | aucune                   |
| INPUT_BAR  | +90° autour de X      | (0, 0, 7.85)             |
| OUTPUT_BAR | +90° autour de X      | (0, 155.000, 29.35) ; 155.713 avant le 22/10 (éprouvette centrée) |
| UT19       | +90° autour de Z      | (356.2728, -1358.1189, 28.6) ; Y = −1357.7622 avant le 22/10 |
| STRIKER    | +90° autour de X      | (0, -6010, 7.85)         |

Repères :
- INPUT_BAR : Y de -6010 à 0, axe en Z = 7.85 (centre de la face du pusher, 20 x 15.7 mm)
- OUTPUT_BAR : axe en Z = 29.35 (soit 21.5 mm au-dessus de l'axe de la barre d'entrée, d'après Beerli et al. 2026, fig. 5a)
- Fond des logements du pusher et de la barre de sortie : Z = 28.6
- UT19 : Y de 123.656 à 201.344, dents au contact des deux logements (avant le 22/10 : 124.013 à 201.700, centrée)
- STRIKER : Y de -11010 à -6010, en contact avec la barre d'entrée

## Placement automatique de l'éprouvette (UT19, UT40)

Depuis le 21/10/2026, `build_bench.py` calcule lui-même la position de l'éprouvette et celle de la barre de
sortie à partir des sommets du fichier STEP de l'éprouvette (paramètre `SPEC`, tableau `SPECIMENS`). Hypothèse :
toutes les éprouvettes ont les mêmes têtes (mêmes dents), donc s'emboîtent de la même façon dans les deux logements.

| Grandeur | Règle | UT19 | UT40 (103,181 mm, fichier du 23/10) |
|---|---|---|---|
| Rotation | +90° autour de Z : (x, y, z) → (−y, x, z), la longueur du STEP devient Y | | |
| Translation X | centre de la largeur du STEP → X = 0 | 356.2728 | 0.0000 |
| Bout côté pusher | toujours en **Y = 201,7005** (le pusher ne bouge pas) | 201,7005 | 201,7005 |
| Bout côté barre de sortie | 201,7005 − longueur | 124,013 | 98,520 |
| Bout de la barre de sortie `Y_OUTPUT_BAR` | bout de l'éprouvette côté sortie + **31,700** | 155,713 | 130,220 |
| Découpe tête / barre de sortie | `Y_OUTPUT_BAR` − 55,713 (tête de même longueur) | 100,000 | 74,507 |
| Translation Z | fond de l'éprouvette sur Z = 28,6 (fond des logements) | 28,6 | 28,6 |
| Jauge de sortie | `Y_OUTPUT_BAR` − 400 | −244,287 | −269,780 |

Une éprouvette plus longue **recule la barre de sortie** d'autant. Contrôle : pour l'UT19, le script vérifie
que le placement calculé est identique (à 0,001 mm près) au placement vérifié le 08/10/2026, et s'arrête sinon.
Règles vérifiées hors Abaqus (OpenCascade) sur `XMas_UT_t1p5.step` : translation (356,2728 ; −1357,7622 ; 28,6),
barre de sortie en 155,713, découpe en 100,000.

Ce tableau est le placement **centré** (avant mise en contact). Le placement final ajoute la mise en contact
(section suivante) : UT19 éprouvette −0,3567 mm, barre de sortie en 155,000 ; UT40 éprouvette **+0,0365 mm**,
barre de sortie en **130,000** (découpe 74,287, jauge −270,000).

**UT40 (vérifié le 23/10/2026 sur le fichier issu du DXF)** : les têtes ne sont **pas exactement** celles de
l'UT19. Même pas des dents, mais les flancs chargés sont 0,10 mm plus loin du bout (dents 0,10 mm plus épaisses
dans le sens de la traction) et le bout côté pusher est 0,29 mm plus court. Conséquence : calée sur ce bout comme
l'UT19, l'éprouvette centrée **recouvre déjà de 0,04 mm** le logement du pusher (`gap_pusher` négatif). La mise
en contact règle ce cas (elle part des jeux mesurés, positifs ou négatifs), et `pocket_gaps.py` vérifie qu'à la
fin il n'y a aucune interpénétration. Pas de collision entre la barre de sortie reculée et le pusher : 3,65 mm
au plus près (corps du pusher Z = 15,7 / dessous de la barre de sortie Z = 19,35).

## Mise en contact initiale (depuis le 22/10/2026)

**Pourquoi.** Avec l'éprouvette centrée dans les deux logements, il restait un jeu de 0,36 mm de chaque côté.
Au début du calcul, le pusher parcourait ce jeu avant de tirer sur l'éprouvette, puis l'éprouvette parcourait
l'autre jeu et **frappait** la tête de la barre de sortie : pic de 15 kN (deux fois la force de l'éprouvette),
puis vibrations à ≈ 40 kHz que la jauge de sortie mesurait (journal du 22/10). Au labo, on tire très légèrement
sur le pusher avant l'essai : tout est au contact, sans effort (confirmé par les encadrants le 22/10).

**Ce que fait `build_bench.py`** (paramètre `CLOSE_GAPS = True`) :

| Pièce | Déplacement selon Y | Résultat |
|---|---|---|
| pusher | aucun | reste au contact de la barre d'entrée (Y = 0) |
| éprouvette | − `gap_pusher` = − 0,3567 mm | ses dents touchent les dents du logement du pusher |
| barre de sortie | − (`gap_pusher` + `gap_output`) = − 0,7130 mm | les dents de son logement touchent celles de l'éprouvette |

Le reste suit la barre de sortie (découpe tête / barre en Y = 99,287, jauge de sortie en Y = −245,000), car tout
est calculé à partir de `Y_OUTPUT_BAR`. `CLOSE_GAPS = False` redonne l'ancien placement centré.

**Mesure des jeux** (`scripts/pre/pocket_gaps.py`, OpenCascade, sur les fichiers STEP) : plus petite translation
selon Y qui met les deux solides en contact, l'éprouvette étant levée de 0,5 mm pendant la mesure pour ne pas
compter le contact sur le fond du logement.

| Éprouvette, logement | Jeu dans le sens de la traction (placement centré) | Jeu restant de l'autre côté des dents, une fois au contact | Faces au contact une fois le jeu fermé |
|---|---|---|---|
| UT19, pusher | 0,3567 mm | 0,6385 mm | les flancs inclinés des **trois** dents (et les congés voisins) |
| UT19, barre de sortie | 0,3563 mm | 0,5222 mm | idem |
| UT40, pusher | **−0,0365 mm** (recouvrement au départ) | 0,5321 mm | idem |
| UT40, barre de sortie | 0,2562 mm | 0,4222 mm | idem |

Interpénétration une fois au contact (volume commun) : ≤ 0,0014 mm³ (arrondi des translations à 1e-4 mm).

Les trois dents touchent en même temps : le pas des dents est le même sur l'éprouvette et dans les logements.
Le contact est exact sur la géométrie ; après maillage, les facettes des tétraèdres peuvent laisser des écarts
ou des interpénétrations de l'ordre du micromètre, qu'Abaqus/Explicit corrige au début du calcul (ajustement sans
déformation du contact général) : à vérifier dans le `.msg`.

## Demi-modèle (symétrie au plan X = 0)

`build_bench.py` (paramètre `HALF_MODEL = True`) ne garde que la moitié **X ≥ 0** de chaque pièce,
comme dans les modèles du labo (Beerli et al. 2026 ; Roth et al. 2015).

- Les pièces complètes sont d'abord placées sous les noms `*_FULL`, puis coupées par une boîte
  couvrant X < 0 (`InstanceFromBooleanCut`). Les demi-parts finales s'appellent `STRIKER`, `INPUT_BAR`,
  `PUSHER`, `UT19`, `OUTPUT_BAR` (instances `<nom>-1`) et sont définies dans le repère global.
- Conséquence pour la suite : une condition de symétrie **XSYMM** (U1 = UR2 = UR3 = 0) devra être
  appliquée sur toutes les faces situées en X = 0.

## Découpe des pièces complexes (maillage, option A)

Le pusher et la barre de sortie ont une partie simple (balayable en hexaèdres) et une tête de forme
complexe (dents, évasement). Chacun est séparé en deux parts par un plan perpendiculaire à Y :

| Part | Zone | Maillage |
|---|---|---|
| `PUSHER_ROD` | Y ≤ 125 (corps rectangulaire, qui va jusqu'à Y = 130) | C3D8R balayés, 5 mm / 2 mm |
| `PUSHER_HEAD` | Y ≥ 125 | C3D10M libres, 2 mm |
| `OUTPUT_BAR` | Y ≤ 100 (partie ronde, qui commence à Y = 105.05), **recréée en cylindre plein Ø 20 × 6000 mm** | C3D8R balayés, 5 mm / 2 mm |
| `OUTPUT_HEAD` | Y ≥ 100 | C3D10M libres, 2 mm |

Les interfaces **Y = 125** (pusher) et **Y = 100** (barre de sortie) devront être collées par des
contraintes **TIE**. À vérifier dans les résultats : pas de réflexion parasite de l'onde à ces interfaces.

**Défeaturing de la barre de sortie :** le STEP comporte au bout éloigné (Y ≈ −5844) un trou taraudé
Ø 8,5 × 27,5 mm avec cône de perçage, qui empêche le maillage balayé. La partie ronde est donc recréée
en cylindre plein sur le même axe (Y de −5844.287 à 100). Le trou représente 0,08 % du volume et n'agit que
sur la réflexion au bout éloigné, après la fenêtre de mesure (2,33 ms).
