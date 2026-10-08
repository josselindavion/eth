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

## Demi-modèle (symétrie au plan X = 0)

`build_bench.py` (paramètre `HALF_MODEL = True`) ne garde que la moitié **X ≥ 0** de chaque pièce,
comme dans les modèles du labo (Beerli et al. 2026 ; Roth et al. 2015).

- Les pièces complètes sont d'abord placées sous les noms `*_FULL`, puis coupées par une boîte
  couvrant X < 0 (`InstanceFromBooleanCut`). Les demi-parts finales s'appellent `STRIKER`, `INPUT_BAR`,
  `PUSHER`, `UT19`, `OUTPUT_BAR` (instances `<nom>-1`) et sont définies dans le repère global.
- Conséquence pour la suite : une condition de symétrie **XSYMM** (U1 = UR2 = UR3 = 0) devra être
  appliquée sur toutes les faces situées en X = 0.
