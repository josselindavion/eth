# Plans de découpe EDM (Task II)

Outils pour vérifier, puis générer, les **plans de découpe par électroérosion à fil (EDM)** des éprouvettes : un DXF
pour l'atelier, plus la notice qui l'accompagne.

## Les conventions des plans du labo

Relevées sur les plans reçus le 29/10/2026 (`input/`).

| Élément | Dans le DXF | Sens |
|---|---|---|
| Unités | millimètres (`$INSUNITS = 4`), DXF R2000 | – |
| Cadre noir (couleur 7) | rectangle | la tôle brute (dimensions minimales) |
| Vert (couleur 3) | contour général : têtes, côtés | qualité **Q3** (normale), coupe rapide |
| Cyan (couleur 4) | congés de raccordement | qualité **Q4** (moyenne) |
| Bleu (couleur 5) | bords de la zone utile, entailles, trous, code d'identification | qualité **Q5** (maximale) |
| Sens de laminage | axe +Y du dessin | l'angle de chaque éprouvette est compté depuis +Y |
| Coin chanfreiné | un coin à 45° sur chaque pièce | repère d'orientation et de face |
| Code à encoches | « peigne » bleu ≈ 13 × 3 mm dans le bord d'une tête | **un code par orientation et par répétition** (ex. « 45°, n° 2 »), partagé par l'UT, la NT20, la NT6.67 et le trou central de même orientation, qu'on distingue par leur forme |
| *Mikrosteg* | pas dans le DXF (confirmé par les encadrants), seulement sur la notice (carrés rouges) | micro-attache, « exactement au milieu » d'un côté sans importance |
| Textes | seulement pour information | « bitte nicht gravieren » : à ne pas graver |

**C'est la couleur qui fait foi, pas le calque** : selon les fichiers, les calques s'appellent `3` / `4` / `5` ou
`Normal_Quality` / `Medium_Quality` / `High_Quality`, et beaucoup de traits sont sur le calque `0` avec une couleur
forcée.

## Règles des encadrants (29/10/2026)

| Règle | Valeur |
|---|---|
| Écart minimal entre pièces | **5 mm** |
| Marge au bord de la tôle | 5 mm (valeur provisoire, non précisée) |
| *Mikrosteg* | pas dans le DXF |
| Miroir d'une éprouvette | **interdit** : seuls l'angle d'origine et son demi-tour (+180°) sont permis |

## Contenu du dossier

| Dossier | Contenu |
|---|---|
| `input/` | plans reçus : 4 modèles de 2025 (`.dxf` + notice `.pptx` / `.pdf`) et le plan de travail `ETH_600x500mm_2_SHEET_v20260901_CT_bardcode.dxf` |
| `scripts/` | `sheetlib.py` (lecture commune), `check_sheet.py` (vérification), `extract_library.py` (bibliothèque), `nest.py` (placement automatique et plan DXF) |
| `output/<plan>/` | plans générés : `<plan>.dxf`, `placement.csv`, `check/` (rapport de vérification du plan généré) |
| `reports/<plan>/` | rapport de vérification de chaque plan : `report.md`, `preview.png`, `issues.png`, `pieces.csv` |
| `library/<nom>/` | bibliothèque d'éprouvettes extraite d'un plan : `specimens.dxf`, `index.csv`, `types.png`, `README.md`, `repaired_source.dxf` |

## Installation (PC du labo, une fois)

```bash
py -m pip install ezdxf shapely matplotlib scipy
```

## 1. Vérifier un plan

```bash
cd ~/Documents/eth
py cutting-sheets/scripts/check_sheet.py cutting-sheets/input/ETH_600x500mm_2_SHEET_v20260901_CT_bardcode.dxf
```

Options :
- `--min-gap 5` : écart minimal entre pièces, ERREUR en dessous (règle des encadrants) ;
- `--warn-gap 5` : écart en dessous duquel on signale ;
- `--min-margin 5` : marge au bord de la tôle (provisoire).

Pour comparaison, les modèles de 2025 ont en général 5 mm entre pièces, mais descendent jusqu'à 2,7 mm.

| Contrôle | ERREUR si | AVERTISSEMENT si |
|---|---|---|
| Unités | autre chose que mm | non définies (`$INSUNITS = 0`) |
| Tôles | aucun cadre de couleur 7 | – |
| Contours fermés | une extrémité de trait ne rejoint rien (le fil ne peut pas suivre) | – |
| Traits en double | – | un trait dessiné deux fois |
| Couleurs | un trait de coupe hors des couleurs 3 / 4 / 5 | calque de qualité et couleur incohérents |
| Pièces | hors tôle ou à cheval sur le bord ; chevauchement | – |
| Écart entre pièces | < `--min-gap` | < `--warn-gap` |
| Marge au bord | < `--min-margin` | – |
| Codes | – | éprouvette sans code ; deux éprouvettes **du même type** avec le même code |

Les types d'éprouvettes sont reconnus d'après la géométrie, avec des noms provisoires :

| Nom | Sens |
|---|---|
| `UT` | traction uniaxiale |
| `NT_R<r>` | traction entaillée, rayon d'entaille r |
| `CH_D<d>` | trou central de diamètre d |
| `DISC_<n>H` | disque à n trous (`2H_xx` : axe des trous à xx° du laminage) |
| `STRIP` / `BLANK` | rectangle sans zone utile, avec ou sans code |
| `_L<l>` | longueur hors tout (mm) |

## 2. Extraire une bibliothèque d'éprouvettes

```bash
py cutting-sheets/scripts/extract_library.py cutting-sheets/input/<plan>.dxf <nom>
```

1. **Réparation des contours ouverts** à partir d'une éprouvette jumelle intacte (même type). La jumelle est
   superposée à la pièce cassée, les traits manquants sont recopiés avec leur géométrie exacte (un arc reste un arc),
   et les fragments isolés sont retirés. Le code à encoches de la pièce n'est jamais touché.
2. Chaque éprouvette est ramenée dans un repère canonique (centre à l'origine, axe vers la tête qui porte le code =
   +Y ; les disques gardent leur orientation) et écrite comme un bloc DXF.
3. **Contrôle de forme** : toutes les éprouvettes d'un même type doivent être identiques, au code près.

## Résultats

Résultats du 29/10/2026 :

| Plan | Verdict |
|---|---|
| Modèles 2025 (`300x300`, `450x400`, `600x500`, `ShearEDM`) | contours fermés, pas de doublon ; écarts ≥ 4 / 2,7 / 3 / 10 mm |
| `…v20260901_CT_bardcode` (plan de travail) | **pas prêt** : 3 contours ouverts + 2 fragments isolés, unités non définies, écarts jusqu’à 1,7 mm (pointes de dents face à face) |
| Bibliothèque `CT_600x500_v20260901` | 63 éprouvettes, 9 types, toutes fermées après réparation, formes identiques par type |
