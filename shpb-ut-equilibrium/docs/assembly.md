# Assemblage du banc SHPB (repère global)
Y = axe des barres / traction, Z = vers le haut, X = largeur de l'éprouvette.
Unités : mm.

| Instance   | Rotation              | Translation              |
|------------|-----------------------|--------------------------|
| PUSHER     | +90° autour de X      | aucune                   |
| INPUT_BAR  | +90° autour de X      | (0, 0, 7.85)             |
| OUTPUT_BAR | +90° autour de X      | (0, 155.713, 29.35)      |
| UT19       | +90° autour de Z      | (356.2728, -1357.7622, 28.6) |
| STRIKER    | +90° autour de X      | (0, -6010, 7.85)         |

Repères :
- INPUT_BAR : Y de -6010 à 0, axe en Z = 7.85 (centre de la face du pusher, 20 x 15.7 mm)
- OUTPUT_BAR : axe en Z = 29.35 (soit 21.5 mm au-dessus de l'axe de la barre d'entrée, d'après Beerli et al. 2026, fig. 5a)
- Fond des logements du pusher et de la barre de sortie : Z = 28.6
- UT19 : Y de 124.013 à 201.700, centrée dans les deux logements
- STRIKER : Y de -11010 à -6010, en contact avec la barre d'entrée

## Placement automatique de l'éprouvette (UT19, UT40)

Depuis le 21/10/2026, `build_bench.py` calcule lui-même la position de l'éprouvette et celle de la barre de
sortie à partir des sommets du fichier STEP de l'éprouvette (paramètre `SPEC`, tableau `SPECIMENS`). Hypothèse :
toutes les éprouvettes ont les mêmes têtes (mêmes dents), donc s'emboîtent de la même façon dans les deux logements.

| Grandeur | Règle | UT19 | UT40 (si 102,6875 mm de long, comme la NT20) |
|---|---|---|---|
| Rotation | +90° autour de Z : (x, y, z) → (−y, x, z), la longueur du STEP devient Y | | |
| Translation X | centre de la largeur du STEP → X = 0 | 356.2728 | dépend du fichier |
| Bout côté pusher | toujours en **Y = 201,7005** (le pusher ne bouge pas) | 201,7005 | 201,7005 |
| Bout côté barre de sortie | 201,7005 − longueur | 124,013 | 99,013 |
| Bout de la barre de sortie `Y_OUTPUT_BAR` | bout de l'éprouvette côté sortie + **31,700** | 155,713 | 130,713 |
| Découpe tête / barre de sortie | `Y_OUTPUT_BAR` − 55,713 (tête de même longueur) | 100,000 | 75,000 |
| Translation Z | fond de l'éprouvette sur Z = 28,6 (fond des logements) | 28,6 | 28,6 |
| Jauge de sortie | `Y_OUTPUT_BAR` − 400 | −244,287 | −269,287 |

Une éprouvette plus longue **recule la barre de sortie** d'autant. Contrôle : pour l'UT19, le script vérifie
que le placement calculé est identique (à 0,001 mm près) au placement vérifié le 08/10/2026, et s'arrête sinon.
Règles vérifiées hors Abaqus (OpenCascade) sur `XMas_UT_t1p5.step` : translation (356,2728 ; −1357,7622 ; 28,6),
barre de sortie en 155,713, découpe en 100,000.

**À vérifier sur le vrai fichier de l'UT40** : mêmes têtes que l'UT19 (sinon les deux constantes 201,7005 et
31,700 ne s'appliquent pas), et absence de collision entre la tête de la barre de sortie reculée et le pusher.

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
