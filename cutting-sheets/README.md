# Plans de découpe EDM (Task II)

Outils pour vérifier, puis générer, les **plans de découpe par électroérosion à fil (EDM)** des éprouvettes : un DXF
pour l'atelier, plus la notice qui l'accompagne.

## Utilisation rapide : « je veux 5 UT à 30° »

1. Copier `orders/exemple.yaml` sous un nouveau nom et écrire la commande :

   ```yaml
   nom: ETH_300x300mm_SHEET_v20261030_UT30
   tole: 300x300
   eprouvettes:
     - {type: UTUT, angle: 30, nombre: 5}
     - {type: NT20, angle: 45, nombre: 3}
   ```

2. Lancer :

   ```bash
   cd ~/Documents/eth
   py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/<ma_commande>.yaml
   ```

3. Résultat dans `runs/<nom>/` (voir « Où vont les fichiers » ci-dessous) :
   - `<nom>.dxf` : le plan pour l'atelier ;
   - `notice.pdf` : une page par tôle et la liste des éprouvettes ;
   - `registry.csv` : une ligne par éprouvette (numéro, type, angle, code, identifiant) ;
   - `README.md` : résumé et contrôles.

   Le terminal affiche les contrôles ; tout doit être `OK`.

| Champ de la commande | Sens | Défaut |
|---|---|---|
| `nom` | nom du plan, du dossier de sortie et du DXF | nom du fichier |
| `gabarits` | dossier des gabarits sans code | `templates/CTLG_261029` (catalogue du labo) |
| `tole` | largeur × hauteur en mm ; la hauteur est le sens de laminage | `500x600` |
| `ecart`, `marge` | écart entre pièces et marge au bord (mm) | 5, 5 |
| `recuit` | itérations de recuit simulé par cœur (0 = rapide ; 50–150 pour gagner de la place, environ 2 s chacune pour 63 éprouvettes) | 0 |
| `coeurs` | nombre de recuits en parallèle, chacun avec un tirage différent ; on garde le meilleur | `auto` = cœurs du PC − 1 |
| `identifiant` | facultatif : `lot`, `geometrie_echantillon`, `supplement`, `geometrie_essai` (par type), pour l'identifiant complet du registre | – |
| `eprouvettes` | une ligne par groupe : `type`, `angle`, `nombre`, et en option `premier_index` | – |

Types disponibles = familles du **catalogue du labo** (`input/specimen_templates_261029_barcoded.dxf`) :

| Type (nom du labo) | Raccourci | Éprouvette | Angles présents dans le catalogue |
|---|---|---|---|
| `UTUT` | `UT` | traction uniaxiale, 106 mm | 0–90° par 15° |
| `NT20` / `NT06` | `NT6.67` pour NT06 | traction entaillée, rayon 20 / 6,67 mm, 106 mm | 0, 45, 90° |
| `CHCH` | `CH` | trou central Ø 4,8 mm, 106 mm | 0, 45, 90° |
| `UTST` | – | traction uniaxiale **courte**, 81 mm | 0–90° par 15° |
| `SHLD` / `SHMD` / `SHHD` | – | cisaillement **court**, 81 mm ; même contour, seul le coin à côté du code change | 0, 45, 90, 135° |
| `MNAK_FULL` | `DISC0` | disque sans trou | 0, 45, 90° |
| `MNAK_HOLE` | `DISC2` | disque à 2 trous ; trous à **angle + 90°** (angle 90° = trous dans le sens de laminage) | 0, 45, 90° |
| `TENS_FULL` | `STRIP` | bande 140 × 30 mm sans code | – |

Un angle absent du catalogue (ex. NT20 à 30°) est quand même généré, avec un **avertissement**.

**L'angle** est celui de la tête qui porte le code, compté depuis le sens de laminage (+Y), dans le sens
trigonométrique. On peut demander 0° à 135° par pas de 15° ; c'est ce chiffre qui est écrit dans le code.
L'**index** vaut 0, 1, 2… pour chaque type et angle, comme dans le catalogue du labo (0 à 9, donc 10 éprouvettes au
maximum par type et par angle). `premier_index: 1` fait commencer à 1.

Le programme refuse une commande fausse, avec un message, sans rien écrire :
- angle non codable (150°, 20°…) ;
- plus de 10 éprouvettes au même angle ;
- deux fois le même code sur le même type ;
- type inconnu.


### Où vont les fichiers (pas de conflit git)

Par défaut, tout ce que les scripts produisent va dans **`cutting-sheets/runs/`**, un dossier **ignoré par git**. On
peut relancer autant qu'on veut, au labo ou ailleurs : `git pull` ne crée plus de conflit.

Pour un plan à garder dans le repo (par exemple celui envoyé à l'atelier), on relance avec `--final` :

```bash
py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/<ta_commande>.yaml --final
git add cutting-sheets/output/<nom>
git commit -m "Plan <nom> envoye a l'atelier"
git push
```

| Script | Par défaut (ignoré par git) | Avec `--final` (suivi par git) |
|---|---|---|
| `make_plan.py`, `nest.py` | `runs/<nom>/` | `output/<nom>/` |
| `check_sheet.py` | `runs/reports/<plan>/` | `reports/<plan>/` |

`extract_library.py` et `make_templates.py` écrivent toujours dans `library/` et `templates/`. Ils ne se lancent
qu'une fois par nouvelle bibliothèque : les relancer réécrit des fichiers suivis par git.

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
| Code à encoches | « peigne » bleu de 12–13 × 3 mm dans le bord d'une tête | code-barres « 2 parmi 5 » : les 5 encoches donnent un **numéro** (0–9), les 4 pleins l'**angle au laminage** (chiffre × 15°, 0–135°). Voir ci-dessous |
| *Mikrosteg* | pas dans le DXF (confirmé par les encadrants), seulement sur la notice (carrés rouges) | micro-attache, « exactement au milieu » d'un côté sans importance |
| Textes | seulement pour information | « bitte nicht gravieren » : à ne pas graver |

### Le code à encoches (décodé le 30/10/2026, vérifié sur tous les plans, confirmé par le document du labo)

C'est un code-barres **« Interleaved 2 of 5 »** de 14 mm, qui porte deux chiffres :
- les pleins (« black bars ») donnent l'**angle** ;
- les encoches (« white bars ») donnent l'**index**.

La dernière barre noire est implicite : c'est le bord de la tête. On ne voit donc que 9 éléments, soit 12 ou 13 mm.
L'identifiant complet de l'éprouvette (lot, géométrie, angle, index…) n'est pas découpé ; il sert au QR code du
labo.

Lecture : code en haut, dessin vu de dessus, de gauche à droite. Le coin chanfreiné est alors à gauche ; s'il est à
droite, on regarde l'autre face.

| Élément | Largeur | Lecture |
|---|---|---|
| 5 encoches N1–N5, 3 mm de profondeur | 1 mm (étroite) ou 2 mm (large), toujours **2 larges** | **numéro** = somme des poids 1-2-4-7-0 des encoches larges (4 + 7 = 0) |
| 4 pleins L1–L4 entre les encoches | 1 ou 2 mm | **angle** = (somme des poids 1-2-4-7 des pleins larges, 4 + 7 = 0) × 15° |

Exemple : encoches larges N2 et N5 → 2 + 0 = n° 2 ; plein large L2 → 2 × 15° = 30°.

| Plan | Sens du numéro |
|---|---|
| Programmes UT / NT / CH / disques | 1, 2, 3 = répétition à cet angle (même code pour l'UT, la NT20, la NT6.67 et le CH de même angle) |
| Cisaillement 2025 | LD1 = 1, LD2 = 2, MD1 = 4, MD2 = 5, HD1 = 7, HD2 = 8 |

Angles codables : 0°, 15°, …, 135°. Les angles −15° et −30° (150°, 165°) ne le sont pas.

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
| `scripts/` | `sheetlib.py` (lecture commune), `check_sheet.py` (vérification), `extract_library.py` (bibliothèque), `notchcode.py` (code à encoches), `make_templates.py` (gabarits sans code), `nest.py` (moteur de placement), `make_plan.py` (commande → plan complet) |
| `orders/` | commandes : `exemple.yaml` (modèle à copier), `CT_v20260901.yaml` (programme CT complet, sert de test) |
| `templates/<nom>/` | gabarits sans code (`CTLG_261029` = catalogue du labo, par défaut ; `CT_v20260901` = tirés du plan CT) : `templates.dxf`, `templates.csv`, `validation.csv`, `templates.png`, `README.md` |
| `runs/` | **ignoré par git** : tout ce qu'on lance (plans, rapports) |
| `output/<plan>/` | plans gardés (`--final`) : `<plan>.dxf`, `notice.pdf`, `registry.csv`, `placement.csv`, `specimens.dxf`, `check/`, `README.md` |
| `reports/<plan>/` | rapports gardés (`--final`) de la vérification des plans reçus : `report.md`, `preview.png`, `issues.png`, `pieces.csv` |
| `library/<nom>/` | bibliothèque d'éprouvettes extraite d'un plan : `specimens.dxf`, `index.csv`, `types.png`, `README.md`, `repaired_source.dxf` |

## Installation (PC du labo, une fois)

```bash
py -m pip install ezdxf shapely matplotlib scipy pyyaml
```

## 1. Vérifier un plan

```bash
cd ~/Documents/eth
py cutting-sheets/scripts/check_sheet.py cutting-sheets/input/ETH_600x500mm_2_SHEET_v20260901_CT_bardcode.dxf
```

Le rapport va dans `runs/reports/<plan>/` (ou `reports/<plan>/` avec `--final`).

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

## 3. Placer automatiquement et produire le plan

```bash
py cutting-sheets/scripts/nest.py cutting-sheets/library/CT_600x500_v20260901 --sheet 500x600 --anneal 120 --name ETH_600x500mm_1_SHEET_v20261029_CT
```

| Option | Sens |
|---|---|
| `--sheet LxH` | taille de la tôle en mm, H selon le sens de laminage |
| `--gap` | écart entre pièces (5 mm par défaut) |
| `--margin` | marge au bord de la tôle (5 mm par défaut) |
| `--res` | pas de la grille de placement (0,5 mm) |
| `--anneal N` | N itérations de recuit simulé par cœur, environ 2 s chacune ; 0 = pas de recuit |
| `--procs N` | recuits en parallèle (défaut : cœurs du PC − 1) |
| `--types UT NT` | ne placer que certains types |

Ce que fait le script :
1. Chaque éprouvette garde **l'angle qu'elle a dans le plan d'origine, ou cet angle + 180°** : pas de miroir.
2. Les collisions sont testées sur une grille conservative : l'écart réel est toujours ≥ `--gap`.
3. Placement « en bas à gauche », tôle par tôle. Plusieurs ordres de départ sont essayés, puis le recuit simulé
   améliore l'ordre.
4. Accélérations (30/10/2026), qui donnent **le même placement** que la recherche complète (vérifié sur 20 ordres
   de placement, écart 0) :
   - on ne cherche que dans les lignes utiles : la position libre la plus basse d'une forme ne peut que monter quand
     la tôle se remplit, et au-dessus de la zone remplie il n'y a que la marge ;
   - une forme qui ne tient plus sur une tôle n'y est plus essayée ;
   - la zone interdite autour d'une pièce (pièce + écart) est calculée une fois par forme et par angle ;
   - les ordres de départ et les recuits tournent en parallèle sur les cœurs du PC.

   Résultat : une mise en place complète prend 2,1 s au lieu de 6,9 s pour 63 éprouvettes sur 500 × 600 mm.
5. Le plan est écrit en DXF : blocs de la bibliothèque, géométrie exacte, mm, calques `Q3_NORMAL` / `Q4_MEDIUM` /
   `Q5_HIGH`.
6. Il est vérifié par `check_sheet.py`, plus un contrôle du type et de l'angle au laminage de chaque éprouvette.

Sorties dans `runs/<nom>/` (ou `output/<nom>/` avec `--final`) : `<nom>.dxf`, `placement.csv`, `check/report.md`, `check/preview.png`.

Ce script place une bibliothèque telle quelle, codes compris. Pour une **nouvelle** commande, on utilise
`make_plan.py` (section « Utilisation rapide »), qui appelle le même moteur.

## 4. Créer les gabarits sans code (une fois par catalogue)

```bash
py cutting-sheets/scripts/make_templates.py cutting-sheets/input/specimen_templates_261029_barcoded.dxf CTLG_261029
```

**Source : le catalogue du labo.** Chaque éprouvette y est un bloc nommé `<famille>_<nn>` (ex. `CTLG_UTUT_21`). Le
type est le **nom de la famille**, lu dans le fichier. Le modèle de chaque type est son bloc `_00` (angle 0°, index 0).

Ancienne source, encore possible : une bibliothèque extraite d'un plan sans noms
(`make_templates.py cutting-sheets/library/CT_600x500_v20260901 CT_v20260901`). Le type y est reconnu d'après la
forme, ce qui ne marche pas pour les familles qui ont le même contour (SHLD / SHMD / SHHD).

Pour chaque type, on retire du modèle :
- les 19 traits du code ;
- le trait Q3 qui suit le code : sa longueur dépend du code, puisqu'un code fait 12 ou 13 mm.

Le gabarit garde la position de départ du code (−6,000 ; 52,944 mm sur les barreaux) et le point où finit ce trait.

**Validation automatique :** chaque éprouvette de la source est reconstruite à partir de son gabarit et du code lu
dessus, puis comparée à l'originale (`validation.csv`). Pour le catalogue, le code lu doit aussi être le numéro du
bloc (`_21` = angle 2 × 15° = 30°, index 1).

**Mikrosteg :** la position proposée est le milieu du plus long côté droit Q3, loin du code. Elle apparaît seulement
sur la notice, à faire confirmer.

## 5. Vérifications faites par `make_plan.py` sur le DXF final

1. Tous les contrôles de `check_sheet.py` (contours fermés, couleurs, écarts, marges, chevauchements).
2. **Contour** de chaque éprouvette du DXF = gabarit avec son code, tourné de l'angle de pose (écart ≤ 0,02 mm,
   même nombre de trous). Ce contrôle couvre aussi l'axe des trous des disques.
3. **Relecture du code** de chaque éprouvette dans le DXF : le chiffre d'angle et l'index lus doivent être ceux
   commandés, et la direction de la tête codée doit être l'angle commandé (ou + 180°).

## Résultats

Résultats du 29/10/2026 :

| Plan | Verdict |
|---|---|
| Modèles 2025 (`300x300`, `450x400`, `600x500`, `ShearEDM`) | contours fermés, pas de doublon ; écarts ≥ 4 / 2,7 / 3 / 10 mm |
| `…v20260901_CT_bardcode` (plan de travail) | **pas prêt** : 3 contours ouverts + 2 fragments isolés, unités non définies, écarts jusqu’à 1,7 mm (pointes de dents face à face) |
| Bibliothèque `CT_600x500_v20260901` | 63 éprouvettes, 9 types, toutes fermées après réparation, formes identiques par type |
| **Plan généré `ETH_600x500mm_1_SHEET_v20261029_CT`** | **63 éprouvettes sur 1 tôle de 500 × 600 mm** (au lieu de 2), écart mini 5,25 mm, marge mini 5,1 mm, tous les contrôles OK |

Résultats du 30/10/2026 :

| Test | Résultat |
|---|---|
| Gabarits `CT_v20260901` : les 63 éprouvettes reconstruites (gabarit + code lu) | traits du code à moins de 0,010 mm, contour à moins de 0,016 mm de l'original |
| Commande `CT_v20260901.yaml` (même programme) | 63 éprouvettes sur **1 tôle** : 571 mm utilisés sans recuit, 567 mm avec 2 × 15 itérations ; tous les contrôles OK |
| Codes générés vs plan du labo | les 60 codes sont **identiques** |
| Gabarits `CTLG_261029` (catalogue du labo) : les 410 éprouvettes codées reconstruites | code = numéro du bloc pour 410 / 410 ; traits du code à moins de 0,012 mm, contour à moins de 0,017 mm |
| Commande `exemple.yaml` (5 UTUT 30°, 3 NT20 45°, 2 UTST 0°, 2 SHLD 135°, 2 MNAK_HOLE 90°) | 1 tôle 300 × 300 mm, tous les contrôles OK ; chaque éprouvette = le bloc du labo de même code à moins de 0,013 mm |
