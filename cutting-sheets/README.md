# Plans de découpe EDM (Task II)

Outil qui fabrique les **plans de découpe par électroérosion à fil (EDM)** des éprouvettes : à partir d'une liste
d'éprouvettes, il produit le DXF pour l'atelier, la notice et le registre des éprouvettes.

## Lancer

**Installation, une seule fois sur le PC du labo :**

```bash
py -m pip install ezdxf shapely matplotlib scipy pyyaml
```

**Les deux commandes prêtes :**

```bash
cd ~/Documents/eth
git pull
py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/exemple.yaml
py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/feuille_CT.yaml
```

| Commande | Contenu |
|---|---|
| `orders/exemple.yaml` | petit exemple sur une tôle 300 × 300 mm : 5 UTUT 30°, 3 NT20 45°, 2 UTST 0°, 2 SHLD 135°, 2 MNAK_HOLE 90° |
| `orders/feuille_CT.yaml` | **la vraie feuille** : le programme CT du plan du labo `input/ETH_600x500mm_2_SHEET_v20260901_CT_bardcode.dxf` (63 éprouvettes, mêmes codes), sur une tôle 500 × 600 mm |

**Résultats** dans `cutting-sheets/runs/<nom>/` :
- `<nom>.dxf` : le plan pour l'atelier ;
- `notice.pdf` : une page par tôle (éprouvettes numérotées, qualités, sens de laminage) et la liste des éprouvettes ;
- `registry.csv` : une ligne par éprouvette (numéro, type, angle, code, position, identifiant) ;
- `README.md` : résumé et contrôles ;
- `check/` : rapport détaillé de vérification.

Le terminal affiche les 6 étapes (`[3/6] Placement`…), une barre de progression avec le temps restant pour les
phases longues (placement, recuit, vérification), puis les contrôles : tout doit être `OK`.

`runs/` est **ignoré par git** : on peut relancer autant qu'on veut sans créer de conflit. Pour garder un plan dans
le repo (par exemple celui envoyé à l'atelier), on ajoute `--final` : il va alors dans `output/<nom>/`, puis
`git add cutting-sheets/output/<nom>`, `git commit`, `git push`.

## Écrire une commande

Copier `orders/exemple.yaml` sous un nouveau nom et modifier les lignes :

```yaml
nom: ETH_300x300mm_SHEET_v20261030_UT30
tole: 300x300
eprouvettes:
  - {type: UTUT, angle: 30, nombre: 5}
  - {type: NT20, angle: 45, nombre: 3}
```

| Champ | Sens | Défaut |
|---|---|---|
| `nom` | nom du plan, du dossier de sortie et du DXF | nom du fichier |
| `gabarits` | dossier des gabarits sans code | `templates/CTLG_261029` (catalogue du labo) |
| `tole` | largeur × hauteur en mm ; la hauteur est le sens de laminage | `500x600` |
| `ecart`, `marge` | écart entre pièces et marge au bord (mm) | 5, 5 |
| `recuit` | itérations de recuit simulé par cœur pour gagner de la place (environ 2 s chacune pour 63 éprouvettes) ; 0 = rapide | 0 |
| `coeurs` | nombre de recuits en parallèle, chacun avec un tirage différent ; on garde le meilleur | `auto` = cœurs du PC − 1 |
| `identifiant` | facultatif : `lot`, `geometrie_echantillon`, `supplement`, `geometrie_essai` (par type), pour l'identifiant complet dans le registre | – |
| `eprouvettes` | une ligne par groupe : `type`, `angle`, `nombre`, et en option `premier_index` | – |

**Types** = familles du catalogue du labo (`input/specimen_templates_261029_barcoded.dxf`) :

| Type | Raccourci | Éprouvette |
|---|---|---|
| `UTUT` | `UT` | traction uniaxiale, 106 mm |
| `NT20` / `NT06` | `NT6.67` pour NT06 | traction entaillée, rayon 20 / 6,67 mm, 106 mm |
| `CHCH` | `CH` | trou central Ø 4,8 mm, 106 mm |
| `UTST` | – | traction uniaxiale courte, 81 mm |
| `SHLD` / `SHMD` / `SHHD` | – | cisaillement court, 81 mm ; même contour, seul le coin à côté du code change |
| `MNAK_FULL` | `DISC0` | disque sans trou |
| `MNAK_HOLE` | `DISC2` | disque à 2 trous ; trous à **angle + 90°** (angle 90° = trous dans le sens de laminage) |
| `TENS_FULL` | `STRIP` | bande 140 × 30 mm sans code |

- **Angle** : direction de la tête qui porte le code, comptée depuis le sens de laminage (+Y), dans le sens
  trigonométrique. De 0° à 135° par pas de 15°, pour tous les types.
- **Index** : 0, 1, 2… pour chaque type et angle, comme dans le catalogue (0 à 9, donc 10 éprouvettes au maximum par
  type et par angle). `premier_index: 1` fait commencer à 1.
- Le programme refuse une commande fausse, avec un message, sans rien écrire :
  - angle non codable (150°, 20°…) ;
  - plus de 10 éprouvettes au même angle ;
  - deux fois le même code sur le même type ;
  - type inconnu.

## Ce que fait le programme

1. **Lit la commande** et la contrôle.
2. **Prend le gabarit** de chaque type (sans code), le tourne de l'angle demandé et **grave le code**.
3. **Place** toutes les éprouvettes :
   - angle commandé ou demi-tour (+180°), jamais de miroir ;
   - 5 mm entre pièces, 5 mm au bord ;
   - placement « en bas à gauche » sur une grille de 0,5 mm qui garantit l'écart ;
   - plusieurs ordres de départ, puis recuit simulé en parallèle sur les cœurs du PC.
4. **Écrit le DXF** : mm, calques `Q3_NORMAL` / `Q4_MEDIUM` / `Q5_HIGH`.
5. **Vérifie le DXF final** sans rien supposer :
   - contours fermés, couleurs, écarts, marges, chevauchements (`check_sheet.py`) ;
   - **contour** de chaque éprouvette = gabarit avec son code, tourné de l'angle de pose (≤ 0,02 mm) ;
   - **code relu** = code commandé, et direction de la tête codée = angle commandé.
6. Écrit la **notice** et le **registre**.

## Contenu du dossier

| Dossier | Contenu |
|---|---|
| `orders/` | les commandes : `exemple.yaml`, `feuille_CT.yaml` |
| `templates/CTLG_261029/` | gabarits sans code tirés du catalogue du labo : `templates.dxf`, `templates.csv`, `validation.csv`, `templates.png`, `README.md` |
| `scripts/` | `make_plan.py` (commande → plan), `nest.py` (moteur de placement), `notchcode.py` (code à encoches), `make_templates.py` (gabarits depuis le catalogue), `check_sheet.py` (vérification d'un DXF), `sheetlib.py` (lecture des DXF) |
| `input/` | fichiers reçus du labo : catalogue `specimen_templates_261029_barcoded.dxf`, plan CT `…v20260901_CT_bardcode.dxf`, modèles de 2025 (`.dxf` + notices `.pptx` / `.pdf`) |
| `runs/` | **ignoré par git** : tout ce qu'on lance |

## Autres outils

**Vérifier n'importe quel DXF** (par exemple un plan reçu) :

```bash
py cutting-sheets/scripts/check_sheet.py cutting-sheets/input/ETH_600x500mm_2_SHEET_v20260901_CT_bardcode.dxf
```

- Le rapport va dans `runs/reports/<plan>/`.
- Options : `--min-gap 5` (écart minimal, ERREUR en dessous), `--warn-gap 5`, `--min-margin 5`.
- Contrôles : unités, cadre de tôle, contours fermés, traits en double, couleurs, pièces hors tôle ou qui se
  chevauchent, écarts, marges, codes.

**Refaire les gabarits** (seulement si le labo envoie un nouveau catalogue) :

```bash
py cutting-sheets/scripts/make_templates.py cutting-sheets/input/<catalogue>.dxf <nom>
```

- Le type de chaque éprouvette est le nom de sa famille de blocs (`CTLG_UTUT_21` → `CTLG_UTUT`).
- Le bloc `_00` sert de modèle. On lui retire les 19 traits du code et le trait Q3 qui le suit : sa longueur dépend
  du code, qui fait 12 ou 13 mm.
- **Validation :** chaque bloc du catalogue est reconstruit à partir du gabarit et du code lu dessus, puis comparé
  à l'original. Le code lu doit être le numéro du bloc (`_21` = angle 2 × 15° = 30°, index 1).
- Pour `CTLG_261029` :
  - 410 / 410 blocs corrects ;
  - traits du code à moins de 0,012 mm ;
  - contour à moins de 0,017 mm.

## Conventions des plans du labo

| Élément | Dans le DXF | Sens |
|---|---|---|
| Unités | millimètres (`$INSUNITS = 4`) | – |
| Cadre noir (couleur 7) | rectangle | la tôle brute (dimensions minimales) |
| Vert (couleur 3) | contour général : têtes, côtés | qualité **Q3** (normale) |
| Cyan (couleur 4) | congés de raccordement | qualité **Q4** (moyenne) |
| Bleu (couleur 5) | zone utile, entailles, trous, code | qualité **Q5** (maximale) |
| Sens de laminage | axe +Y | l'angle de chaque éprouvette est compté depuis +Y |
| Coin chanfreiné | un coin à 45° | repère d'orientation et de face |
| *Mikrosteg* | ni dans le DXF, ni sur la notice | gérés par l'atelier |

C'est la **couleur** qui donne la qualité, pas le nom du calque.

**Règles des encadrants (29/10/2026) :**
- 5 mm entre pièces ;
- 5 mm au bord (valeur provisoire) ;
- pas de miroir ;
- pas de Mikrosteg.

## Le code à encoches

Code-barres **« Interleaved 2 of 5 »** gravé dans le bord d'une tête (document « Specimen ID » du labo) :

| Élément | Largeur | Lecture |
|---|---|---|
| 5 encoches (blanches à contre-jour), 3 mm de profondeur | 1 mm ou 2 mm, toujours **2 larges** | **index** = somme des poids 1-2-4-7-0 des 2 encoches larges (4 + 7 → 0) |
| 4 pleins (noirs) entre les encoches, + 1 implicite (bord de la tête) | 1 mm ou 2 mm, **2 larges** en comptant l'implicite | **angle** = (somme des poids 1-2-4-7-0 des 2 pleins larges) × 15° |

- On lit le code en haut, de gauche à droite, le coin chanfreiné à gauche.
- Exemple : encoches larges n° 2 et 5 → 2 + 0 = index 2 ; un seul plein large visible, le n° 2 (l'autre est
  l'implicite) → 2 × 15° = 30°.
- Le code mesure 12 ou 13 mm de visible, 14 mm avec la barre implicite.
- Angles codables : 0° à 135° par pas de 15° (150° et 165° ne le sont pas).
- L'identifiant complet (lot, géométries, angle, index…) n'est pas gravé : il sert au QR code du labo.
