# Maillage du banc SHPB

Tout le maillage est fait par **`scripts/cae/build_bench.py`** (à lancer dans Abaqus/CAE : *File → Run Script*).
Ce document explique **ce qui est maillé, comment, et pourquoi**.

Repère global : **Y** = axe des barres (traction), **Z** = vers le haut, **X** = largeur de l'éprouvette. Unités : mm.

---

## 1. Vue d'ensemble

Le banc est un **demi-modèle** (on ne garde que X ≥ 0, symétrie au plan X = 0) découpé en **7 pièces** :

```
STRIKER → INPUT_BAR → PUSHER_ROD ┃ PUSHER_HEAD ─┐
                                 tie            UT19 (éprouvette)
            OUTPUT_BAR ┃ OUTPUT_HEAD ────────────┘
                      tie
```

| Pièce | Rôle | Origine de la géométrie | Zone (Y, mm) | Maillage | Élément | Tailles | Éléments | Nœuds |
|---|---|---|---|---|---|---|---|---|
| `STRIKER` | projectile | cylindre créé par le script, Ø20 × 5000 | −11010 → −6010 | balayé (*sweep*) | C3D8R | 5 mm axial, 2 mm section | 47 000 | 61 061 |
| `INPUT_BAR` | barre d'entrée | cylindre créé par le script, Ø20 × 6010 | −6010 → 0 | balayé | C3D8R | 5 mm axial, 2 mm section | 58 898 | 75 789 |
| `PUSHER_ROD` | corps de l'inverseur | STEP `Inverter_new.step` | 0 → 125 | balayé | C3D8R | 5 mm axial, 2 mm section | 1 000 | 1 404 |
| `PUSHER_HEAD` | tête de l'inverseur (logement de l'éprouvette) | STEP `Inverter_new.step` | 125 → 206 | libre (*free*) | C3D10M | 2 mm | 30 886 | 45 811 |
| `UT19` | éprouvette (tôle 1,5 mm) | STEP `XMas_UT_t1p5.step` | 124 → 201,7 | découpée en 3 volumes : partie droite en grille régulière (*structured*), têtes balayées dans l'épaisseur | C3D8R | 0,5 mm dans le plan, 4 éléments dans l'épaisseur | ~12 400 | ~16 700 |
| `OUTPUT_BAR` | barre de sortie (partie ronde) | cylindre créé par le script, Ø20 × 6000 | −5844 → 100 | balayé | C3D8R | 5 mm axial, 2 mm section | 61 828 | 78 540 |
| `OUTPUT_HEAD` | tête de la barre de sortie (logement de l'éprouvette) | STEP `Stange30mm_Step2.step` | 100 → 155,7 | libre | C3D10M | 2 mm | 11 755 | 18 052 |
| **Total** | | | | | | | **223 747** | ~297 000 |

Sources des tailles d'éléments : Roth et al. (2015) et Beerli et al. (2026) — barres 5 mm, pusher et barre de sortie 2 mm,
éprouvette 0,5 mm avec 4 éléments dans l'épaisseur.

---

## 2. Les deux types d'éléments

| | **C3D8R** | **C3D10M** |
|---|---|---|
| Forme | hexaèdre (brique) | tétraèdre |
| Nœuds | 8 (sommets) | 10 (4 sommets + 6 milieux d'arêtes) |
| Ordre | linéaire | quadratique (« modifié », adapté au contact et à l'explicite) |
| Intégration | réduite (1 point) → nécessite un contrôle de l'*hourglass* | — |
| Utilisé pour | tout ce qui peut être maillé en briques | les formes trop complexes pour des briques |
| Pourquoi | précis, peu coûteux, standard du labo | maille n'importe quelle forme ; le C3D4 (tétra linéaire) est trop raide |

Bibliothèque **Explicit** pour tous les éléments (calcul en dynamique explicite).

---

## 3. Les deux techniques de maillage

| Technique | Principe | Condition | Pièces |
|---|---|---|---|
| **Balayé (*sweep*)** | on maille une section en quadrangles, puis on « pousse » ce maillage le long d'une direction (comme une extrusion) | la section doit être **identique** sur toute la longueur | barres, `PUSHER_ROD`, `UT19` (balayée dans l'épaisseur) |
| **Libre (*free*)** | Abaqus remplit le volume de tétraèdres, sans contrainte de forme | aucune | `PUSHER_HEAD`, `OUTPUT_HEAD` |

Graines (*seeds*) : une taille globale pour la pièce, puis des tailles locales sur certaines arêtes
(faces d'extrémité des barres pour la section, arêtes verticales de l'éprouvette pour imposer **exactement 4** éléments dans l'épaisseur).

---

## 4. Choix de modélisation (et leurs conséquences)

| Choix | Raison | Conséquence à gérer |
|---|---|---|
| **Demi-modèle** (X ≥ 0) | le banc est symétrique ; ÷2 sur le nombre d'éléments ; pratique du labo | condition **XSYMM** sur toutes les faces en X = 0 |
| **Têtes séparées et en tétraèdres** (option A) | les têtes (dents, évasement) ne sont pas balayables ; rapide et robuste | interfaces **Y = 125** (pusher) et **Y = 100** (barre de sortie) à coller par des contraintes **TIE** ; vérifier dans les résultats qu'il n'y a **pas de réflexion parasite** de l'onde à ces interfaces |
| Coupes placées **dans** les parties simples (5 mm avant leur fin) | l'interface collée est une section plane et régulière | — |
| **Barre de sortie ronde recréée** en cylindre plein | le STEP a au bout éloigné un trou taraudé Ø8,5 × 27,5 mm qui empêche le balayage | détail supprimé (0,08 % du volume, à 6 m de l'éprouvette, hors fenêtre de mesure de 2,33 ms) |
| Striker et barre d'entrée **créés par le script** | ce sont de simples cylindres (dimensions : Beerli 2026) | — |

Option B (pour plus tard, si la réflexion aux *ties* est gênante) : tout en hexaèdres en découpant les têtes en volumes balayables.

---

### Découpe de l'éprouvette

La partie droite de la zone utile (15 mm × 5 mm) est isolée par deux plans perpendiculaires à Y,
dont la position est **lue sur la géométrie** (sommets en |X| = 2,5 mm) :

| Plan | Y (mm) | Nom de la section | Côté |
|---|---|---|---|
| début de la partie droite | ≈ 155,357 | `SEC_OUT` | barre de sortie |
| fin de la partie droite | ≈ 170,357 | `SEC_IN` | pusher (entrée de l'effort) |

Intérêts : (1) maillage **parfaitement aligné** dans la partie droite (meilleur pour la striction) ;
(2) deux **faces internes** où mesurer la force qui traverse l'éprouvette — comparer `SEC_IN` et `SEC_OUT`
est le critère d'équilibre de la Task I (comme Beerli et al. 2026, fig. 5c).

## 5. Vérifier le maillage

Le script affiche deux bilans dans la zone de messages de CAE.

| Contrôle | Valeur attendue | Ce qu'un écart signifierait |
|---|---|---|
| « Etendue des pièces » : X min | 0.000 pour toutes les pièces | la coupe du demi-modèle a raté |
| « Etendue des pièces » : Y | les zones du tableau §1 | une coupe au mauvais endroit |
| Type d'élément | C3D8R, sauf C3D10M pour les deux têtes | mauvais type affecté |
| Nœuds / éléments, C3D8R | ≈ 1,3 | — |
| Nœuds / éléments, C3D10M | ≈ 1,4 à 1,6 | **≈ 0,2 → ce sont des C3D4** (tétras linéaires), le type n'a pas été pris en compte |
| Éléments par tranche de barre | ≈ 47 à 49 (Ø20, demi-section, 2 mm) | graines de section mal appliquées |
| `UT19` | 4 couches d'éléments dans l'épaisseur | graine d'épaisseur mal appliquée |

Pour voir le maillage : module **Mesh**, *Object : Part*, choisir la pièce.

---

## 6. Modifier le maillage

Tout se règle dans le bloc `PARAMETRES` en haut de `build_bench.py` :

| Paramètre | Valeur | Effet |
|---|---|---|
| `HALF_MODEL` | `True` | `False` = banc complet (2× plus d'éléments) |
| `Y_SPLIT_PUSHER` | 125.0 | position de la coupe pusher (corps / tête) |
| `Y_SPLIT_OUTPUT` | 100.0 | position de la coupe barre de sortie (ronde / tête) |
| `BAR_SEED_AXIAL` | 5.0 mm | taille des éléments dans l'axe des barres |
| `BAR_SEED_SECTION` | 2.0 mm | taille des éléments dans la section des barres |
| `SPEC_SEED_INPLANE` | 0.5 mm | taille des éléments de l'éprouvette dans son plan |
| `SPEC_N_THICKNESS` | 4 | nombre d'éléments dans l'épaisseur de l'éprouvette |
| `HEAD_SEED` | 2.0 mm | taille des tétraèdres des têtes |

Après modification : relancer le script dans une base vierge (*File → New Model Database*) et revérifier les bilans (§5).

---

## 7. Ce qu'on a appris en chemin

| Problème rencontré | Cause | Solution |
|---|---|---|
| *Some regions cannot be Swept* sur la barre de sortie | trou taraudé au bout éloigné : la section change | partie ronde recréée en cylindre plein |
| Têtes en C3D4 au lieu de C3D10M, **sans message d'erreur** | `setElementType` reçu avec un seul type au lieu du triplet (hexa, prisme, tétra) | toujours fournir le triplet |
| *Default args are not fully supported* | triplet mélangeant un hexa **linéaire** (C3D8R) et un tétra **quadratique** (C3D10M) | syntaxe reprise du journal : `UNKNOWN_HEX`, `UNKNOWN_WEDGE`, `C3D10M` |

**Méthode générale** : quand on ne connaît pas la syntaxe Python d'une opération, la faire une fois à la main dans CAE
et la lire dans `abaqus.rpy` (le journal de la session en cours, sans numéro, dans le dossier de travail).

---

## 8. Reste à faire

- [x] Groupes nommés : `<PIÈCE>_ALL`, `XSYMM`, surfaces de *tie* et de contact, jauges (`GAUGE_IN`, `GAUGE_OUT`), extensomètre
- [x] Export du maillage en `.geo` (convention du labo) — voir section 10
- [ ] Après le premier calcul : vérifier l'absence de réflexion aux interfaces Y = 125 et Y = 100
- [ ] (optionnel) maillage aligné dans la zone utile de l'éprouvette, pour la striction

---

## 9. Groupes nommés (créés par `build_bench.py`)

Les groupes sont définis **sur la géométrie** (par coordonnées), donc ils restent valables si le maillage change.

| Groupe | Type | Pièces | Contenu | Usage prévu |
|---|---|---|---|---|
| `<PIÈCE>_ALL` | set d'éléments | toutes | tous les éléments de la pièce | `*SOLID SECTION` (matériau) |
| `XSYMM` | set (faces → nœuds) | toutes | faces en X = 0 | condition de symétrie XSYMM |
| `SEC_IN` | surface | `UT19` | section en Y ≈ 170,357 | force traversant l'éprouvette, côté pusher |
| `SEC_OUT` | surface | `UT19` | section en Y ≈ 155,357 | force traversant l'éprouvette, côté barre de sortie |
| `GAUGE_ZONE` | set d'éléments | `UT19` | partie droite de la zone utile | contraintes / déformations moyennes |
| `GUIDE` | set de nœuds | `PUSHER_ROD`, `PUSHER_HEAD`, `STRIKER`, `INPUT_BAR`, `OUTPUT_BAR` | face inférieure du pusher (Z = 0) ; axe des barres | guidage vertical U3 = 0 (section 12) |

### Surfaces d'interface

Même nom des deux côtés d'une interface ; dans le `.inp`, elles sont qualifiées par l'instance
(ex. `PUSHER_ROD-1.S_TIE`).

| Surface | Pièces | Position | Interaction prévue |
|---|---|---|---|
| `S_TIE` | `PUSHER_ROD` + `PUSHER_HEAD` | Y = 125 | *tie* (collage) |
| `S_TIE` | `OUTPUT_BAR` + `OUTPUT_HEAD` | Y = 100 | *tie* (collage) |
| `S_IMPACT` | `STRIKER` + `INPUT_BAR` | Y = −6010 | contact : impact du striker |
| `S_PUSH` | `INPUT_BAR` + `PUSHER_ROD` | Y = 0 | contact : la barre d'entrée pousse le pusher |
| `S_SKIN` | `UT19`, `PUSHER_HEAD`, `OUTPUT_HEAD` | peau extérieure (sans faces internes ni faces en X = 0) | contact général : dents de l'éprouvette ↔ logements |

### Mesures virtuelles

Réglables dans le bloc `PARAMETRES` (`GAUGE_IN_DIST`, `GAUGE_OUT_DIST`, `GAUGE_LENGTH`, `EXT_LENGTH`).

| Groupe | Type | Pièce | Position | Source / remarque |
|---|---|---|---|---|
| `GAUGE_IN` | set d'éléments | `INPUT_BAR` | Y = −6010 + 400 = −5610 | jauge à 400 mm de l'interface striker / barre (Beerli 2026) |
| `GAUGE_OUT` | set d'éléments | `OUTPUT_BAR` | Y = 155,713 − 400 = −244,3 | « Gauge out: 400 » (Beerli 2026, fig. 5a). **Référence exacte à confirmer** (bout de barre ou interface éprouvette, ≈ 30 mm d'écart ≈ 6 µs de décalage) |
| `EXT_OUT` | set d'un nœud | `UT19` | dessus (Z = 30,1), X = 0, Y = centre de la partie droite − 6 | extensomètre virtuel de 12 mm (zone DIC de la sUT, Beerli 2026) |
| `EXT_IN` | set d'un nœud | `UT19` | idem, Y = centre + 6 | |

Une jauge virtuelle = les éléments dont le centre est à moins de `GAUGE_LENGTH / 2` = 5 mm de la position
(≈ 2 tranches d'éléments) : comme une vraie jauge, elle moyenne la déformation sur quelques millimètres.

---

## 10. Export en fichiers `.geo` (convention du labo)

Le `.inp` principal ne contient pas le maillage : il l'inclut par `*INCLUDE`, un fichier `.geo` par pièce
(comme `NT20.geo` dans le tuto du labo).

### Chaîne

| Étape | Outil | Entrée | Sortie |
|---|---|---|---|
| 1 | `scripts/cae/build_bench.py` (Abaqus/CAE, *File → Run Script*, après avoir réglé `SPEC = 'UT19'` ou `'UT40'` ; ou `abaqus cae noGUI=build_bench.py -- UT40`) | STEP de `cad/step/` | `SHPB_<SPEC>.cae` (dossier de travail) **et** `model/geometry/_raw/SHPB_<SPEC>_mesh.inp` |
| 2 | `scripts/pre/inp_to_geo.py <SPEC>` (Python 3, sans Abaqus) | `model/geometry/_raw/SHPB_<SPEC>_mesh.inp` | `model/geometry/<SPEC>/<PIÈCE>.geo` (7 fichiers) |

**Un dossier de `.geo` par éprouvette** (`model/geometry/UT19/`, `model/geometry/UT40/`) : la barre de sortie et sa tête ne sont pas au même endroit selon la longueur de l'éprouvette (voir `docs/assembly.md`), donc `OUTPUT_BAR.geo` et `OUTPUT_HEAD.geo` diffèrent. `make_run.py` copie les 7 `.geo` du dossier de l'éprouvette du calcul.

```bash
# depuis la racine du repo
python shpb-ut-equilibrium/scripts/pre/inp_to_geo.py
```

Les `.geo` et le dossier `_raw/` **ne sont pas versionnés** (`.gitignore`) : ils sont regénérés par ces deux scripts.

### Ce que fait la conversion

| Dans le `.inp` brut de CAE | Dans le `.geo` |
|---|---|
| maillage dans `*Part`, placé par `*Instance` (translation + rotation) | nœuds directement en **coordonnées globales** (la transformation est appliquée) |
| labels qui recommencent à 1 dans chaque part | labels **décalés** : pièce n → à partir de n × 1 000 000 (voir tableau ci-dessous) |
| noms locaux (`XSYMM`, `S_TIE`…) qualifiés par l'instance (`UT19-1.XSYMM`) | noms **préfixés par la pièce** : `UT19_XSYMM`, `PUSHER_ROD_S_TIE` ; `UT19_ALL` reste `UT19_ALL` |
| `*Solid Section` dans la part | **retiré** : les sections sont dans le `.inp` principal |
| — | en plus : `*Node, nset=<PIÈCE>_NALL` (tous les nœuds de la pièce) |
| elsets internes des surfaces (`_S_TIE_S3, internal`) | renommés `<PIÈCE>_I_S_TIE_S3`, **sans** l'option `internal` : hors `*Part` / `*Assembly`, Abaqus la refuse (`UNKNOWN PARAMETER INTERNAL`) |

Les labels dépendent de l'ordre des instances dans le `.inp` brut ; le script affiche la plage de chaque pièce.
Un groupe d'assemblage qui porterait le même nom qu'un groupe de part serait renommé `<nom>_ASM` (message `ATTENTION`).

### Noms disponibles dans le `.inp` principal

| Pièce (`<PIÈCE>.geo`) | Groupes | Surfaces |
|---|---|---|
| `STRIKER` | `STRIKER_ALL`, `STRIKER_NALL`, `STRIKER_XSYMM` | `STRIKER_S_IMPACT` |
| `INPUT_BAR` | `INPUT_BAR_ALL`, `INPUT_BAR_NALL`, `INPUT_BAR_XSYMM`, `INPUT_BAR_GAUGE_IN` | `INPUT_BAR_S_IMPACT`, `INPUT_BAR_S_PUSH` |
| `PUSHER_ROD` | `PUSHER_ROD_ALL`, `PUSHER_ROD_NALL`, `PUSHER_ROD_XSYMM` | `PUSHER_ROD_S_PUSH`, `PUSHER_ROD_S_TIE` |
| `PUSHER_HEAD` | `PUSHER_HEAD_ALL`, `PUSHER_HEAD_NALL`, `PUSHER_HEAD_XSYMM` | `PUSHER_HEAD_S_TIE`, `PUSHER_HEAD_S_SKIN` |
| `UT19` | `UT19_ALL`, `UT19_NALL`, `UT19_XSYMM`, `UT19_GAUGE_ZONE`, `UT19_EXT_OUT`, `UT19_EXT_IN` | `UT19_SEC_OUT`, `UT19_SEC_IN`, `UT19_S_SKIN` |
| `OUTPUT_BAR` | `OUTPUT_BAR_ALL`, `OUTPUT_BAR_NALL`, `OUTPUT_BAR_XSYMM`, `OUTPUT_BAR_GAUGE_OUT` | `OUTPUT_BAR_S_TIE` |
| `OUTPUT_HEAD` | `OUTPUT_HEAD_ALL`, `OUTPUT_HEAD_NALL`, `OUTPUT_HEAD_XSYMM` | `OUTPUT_HEAD_S_TIE`, `OUTPUT_HEAD_S_SKIN` |

Tableau vérifié au premier lancement (9 oct. 2026). Plages de labels obtenues :

| Pièce | Nœuds | Éléments | Labels |
|---|---|---|---|
| `STRIKER` | 61 061 | 47 000 | 1 000 001 … |
| `INPUT_BAR` | 75 789 | 58 898 | 2 000 001 … |
| `PUSHER_ROD` | 1 404 | 1 000 | 3 000 001 … |
| `PUSHER_HEAD` | 45 811 | 30 886 | 4 000 001 … |
| `UT19` | 16 765 | 12 428 | 5 000 001 … |
| `OUTPUT_BAR` | 78 540 | 61 828 | 6 000 001 … |
| `OUTPUT_HEAD` | 18 052 | 11 755 | 7 000 001 … |
| **Total** | **297 422** | **223 795** | |

Le premier chiffre d'un label donne donc la pièce : utile pour lire un message d'erreur Abaqus
(« élément 5004321 trop distordu » → `UT19`).

---

## 11. Qualité des tétraèdres des têtes (pas de temps)

Premier datacheck (12/10/2026) : pas de temps stable **5,5e-9 s**, imposé par des tétraèdres écrasés
dans les têtes (204 éléments signalés). Localisation des éléments signalés :

| Cause | Éléments | Pire épaisseur | Traitement |
|---|---|---|---|
| Trou M4 au fond du logement du **pusher** (Y = 186,35 ; borgne, pointe de foret ; coupé par X = 0) | 89 | 0,54 mm | **supprimé dans le STEP** |
| Trou M4 au fond du logement de la **barre de sortie** (Y = 139,21 ; débouchant ; coupé par X = 0) | 45 | 0,68 mm | **supprimé dans le STEP** |
| Congés R0,5 / R1 / R1,5 des dents des logements | 64 | 0,13 mm | virtual topology |
| Lanières de la surface cylindrique à la jonction tige / tête du pusher (Y ≈ 130, 0,05 à 0,14 mm de large) | 2 | **0,10 mm** (impose le pas) | virtual topology |

Épaisseur médiane des tétraèdres : ≈ 1,2 mm.

### Suppression des trous M4

Les trous sont inutiles pendant l'essai. Ils sont supprimés **avant Abaqus**, dans la géométrie :

| Fichier d'origine | Fichier utilisé | Volume ajouté |
|---|---|---|
| `cad/step/Inverter_new.step` | `cad/step/Inverter_new_noM4.step` | 101,2 mm³ (Ø3,3 × 11,5 mm + pointe) |
| `cad/step/Stange30mm_Step2.step` | `cad/step/Stange30mm_Step2_noM4.step` | 62,0 mm³ (Ø3,3 × 7,25 mm) |

- Outil : `scripts/pre/defeature_step.py` (Python 3 + OpenCascade, `pip install cadquery-ocp`).
  Il retire les faces de rayon 1,65 mm et prolonge les faces voisines. Contrôles : un seul solide,
  géométrie valide, volume ajouté = volume du trou.
- Pourquoi pas dans Abaqus/CAE : *Geometry Edit → Face → Remove* sur la demi-tête a fait **perdre le volume**
  de la pièce (il ne restait qu'une peau), et la conversion *Shell → Solid* a échoué.

### Virtual topology des têtes

Dans `build_bench.py` (`apply_virtual_topology`, appelée par `mesh_tet`) : le mailleur ignore les faces et arêtes
plus petites qu'un élément. La géométrie réelle ne change pas ; les nœuds restent sur la vraie surface, mais les
congés de 0,5 à 1 mm ne sont plus suivis exactement (écart ~0,1–0,2 mm aux coins des dents).

| Réglage (`PARAMETRES`) | Valeur | Ce qu'il fusionne |
|---|---|---|
| `VT_SHORT_EDGE` | 1,0 mm | arêtes courtes (arcs des congés R0,5 : 0,5–0,8 mm ; arêtes de 0,14 mm à la jonction) |
| `VT_SMALL_FACE` | 5,0 mm² | petites faces (bandes de congés 1,8–4,6 mm², petites faces planes des dents) |
| `VT_ASPECT` | 10 | faces très élancées (lanières de 0,05 × 20 mm à la jonction) |
| `applyBlendControls` | `False` | sinon les congés de rayon < 2,1 mm sont **protégés** (réglage par défaut de CAE) |
| `HEAD_MIN_SIZE_FACTOR` | 0,5 | taille mini des tétraèdres = 1 mm (sinon CAE raffine jusqu'à 0,2 mm sur les petits rayons) |

Réglages testés à la main dans CAE (*Mesh → Tools → Virtual Topology → Automatic Create*, aperçu avec *Preview*).
`build_bench.py` affiche ensuite, pour chaque tête, la plus petite hauteur de tétraèdre (indicateur du pas de temps).

### Résultat (datacheck du 12/10/2026)

| | Avant | Après (STEP sans trous M4 + virtual topology + taille mini 1 mm) |
|---|---|---|
| Éléments des têtes | 30 886 + 11 755 | 24 307 + 8 753 |
| Plus petite hauteur de tétraèdre | 0,102 mm (pusher), 0,174 mm (sortie) | 0,431 mm, 0,388 mm |
| Pas de temps stable initial | **5,5e-9 s** | **2,0e-8 s** (× 3,7) |
| Éléments les plus critiques | 9 sur 10 dans la tête du pusher | tête de sortie (7005583) **et éprouvette** (5002066, 5003540…), à égalité |
| Pénétrations initiales de contact | max 0,0070 mm | max 0,0076 mm (la virtual topology ne dégrade pas le contact) |
| Masse du demi-modèle | 21,4882 kg | 21,4889 kg (+0,7 g = matière des deux demi-trous bouchés) |

Les têtes ne sont plus seules à imposer le pas de temps : **l'éprouvette** a maintenant des éléments aussi
critiques (≈ 2,0e-8 s, alors qu'une couche de 0,375 mm laisserait attendre ≈ 6e-8 s). Pour gagner encore,
il faudrait regarder où sont ces petits éléments de l'éprouvette (à faire).

---

## 12. Guidages (glissière du pusher, paliers des barres)

**Constat** (calcul `taskI_20261012-1811`, UT19 à 500 /s) : entre t = 0 et t = 4 ms, le pusher a **basculé** par rapport
au reste du banc. Les efforts sont excentrés : la barre d'entrée pousse le pusher à Z = 7,85 (son axe), l'éprouvette le
retient à Z ≈ 29 (fond du logement) ; ce couple le fait tourner autour de X. Dans le modèle, rien ne s'y opposait
(seule condition : la symétrie X = 0).

**Sur le banc** : le pusher coulisse dans une **glissière** et les barres dans des **paliers**, qui les tiennent dans les
deux sens (haut et bas).

**Dans le modèle** : U3 = 0 (déplacement vertical) sur les groupes `GUIDE` créés par `build_bench.py` :

| Pièce | Nœuds bloqués en U3 | Pourquoi ces nœuds |
|---|---|---|
| `PUSHER_ROD`, `PUSHER_HEAD` | face inférieure, Z = 0 (une seule face plane sur toute la longueur, Y = 0 à 206) | c'est la face qui glisse dans la glissière. Sur la tête, les nœuds du plan de tie (Y = 125) sont exclus : ceux de la tige les bloquent déjà |
| `STRIKER`, `INPUT_BAR`, `OUTPUT_BAR` | axe de la barre (X = 0, Z = axe), sur toute la longueur | bloquer l'axe empêche la barre de monter, descendre ou basculer, sans gêner l'onde axiale ni le gonflement radial (effet Poisson), qui laissent l'axe en place |

Tout reste libre selon Y. Hypothèses : guidages **sans frottement** et **sans jeu** ; guidage des barres **continu**
(les positions réelles des paliers ne sont pas modélisées). `build_bench.py` affiche le nombre de nœuds de chaque groupe
et s'arrête si un groupe est vide.
