# shpb-ut-equilibrium

Simulations Abaqus de l'équilibre des efforts dans les éprouvettes UT (UT19, UT40) sur barres de Hopkinson (SHPB).

## Arborescence

```
shpb-ut-equilibrium/
├── cad/
│   ├── native/        sources SolidWorks (.SLDPRT / .SLDASM)
│   └── step/          exports STEP importés par Abaqus
├── model/             modèle Abaqus « source », conventions du labo
│   ├── geometry/      UT19.geo, UT40.geo, LID.geo, BARS.geo (maillage + sets)
│   ├── materials/     A2_tool_steel.dat, A286.dat, specimen_*.dat
│   ├── templates/     SHPB_UT_main.inp (avec *INCLUDE et <PARAMÈTRES>)
│   └── subroutines/   VUMAT du labo, le cas échéant
├── scripts/
│   ├── cae/           Python 2.7 lancé par Abaqus : STEP → maillage → .geo
│   ├── pre/           Python 3 : plan de calcul → génère runs/
│   ├── hpc/           script sbatch (job array), synchro vers Euler
│   └── post/          extract_odb.py (abaqus python) + analyse (Python 3)
├── studies/
│   └── taskI/cases.csv   matrice : UT19/UT40 × 100/500/1000 s⁻¹
├── runs/              GÉNÉRÉ, non versionné : un dossier par calcul
├── results/           CSV légers extraits (force, extensomètre), versionnés
└── docs/              notes, schémas du banc
```

## Chaîne de calcul

0. `scripts/pre/make_materials.py` : paramètres matériaux → `model/materials/*.dat` (voir `docs/materials.md`)
1. `scripts/cae/build_bench.py` (Abaqus/CAE) : STEP (`cad/step/`) → maillage → `model/geometry/_raw/SHPB_UT19_mesh.inp`,
   puis `scripts/pre/inp_to_geo.py` (Python 3) → un `model/geometry/<PIÈCE>.geo` par pièce (voir `docs/mesh.md`, section 10)
2. `scripts/pre/make_run.py` : `studies/<étude>/cases.csv` + `model/templates/` → `runs/<case_id>/`
   (`<case_id>.inp` + `<case_id>_paras.inp` + copies des `.geo` et `.dat` : dossier autonome)
3. `scripts/hpc/` : soumission sur Euler (job array)
4. `scripts/post/` : `.odb` → CSV dans `results/`

## Lancer Abaqus à la main (PC du labo, Windows)

| Étape | Commande |
|---|---|
| Ouvrir l'invite Abaqus | menu Démarrer → taper **Abaqus Command** → Entrée |
| Aller dans le dossier du calcul | `cd /d C:\Users\jdavion\Documents\eth\shpb-ut-equilibrium\runs\<case_id>` |
| Vérifier le modèle sans calculer | `abq2023 job=<case_id> datacheck interactive` |
| Calculer | `abq2023 job=<case_id> cpus=4 double=both interactive` |

Utiliser **`abq2023`** et pas `abaqus` : sur les PC du labo, `abaqus.bat` charge le compilateur puis se place
d'office dans `C:\APPS\Abaqus2023_Work`, et ne trouve donc pas le `.inp`.

## Nommage des calculs

`<éprouvette>_R<vitesse de déformation sur 4 chiffres>_<indice>`, par ex. `UT19_R0500_00`.

## Documentation

| Fichier | Contenu |
|---|---|
| `docs/assembly.md` | placement des pièces dans le repère global, demi-modèle, découpe des pièces |
| `docs/materials.md` | matériaux, sources des données, hypothèses |
| `docs/mesh.md` | maillage : pièces, éléments, techniques, vérifications, paramètres |

## Idées en réserve

| Idée | Gain attendu | Détail |
|---|---|---|
| Durée simulée `T_STEP` calculée par cas dans `make_run.py` | ≈ 2× sur 500 et 1 000 /s | `T_STEP` = arrivée de l'onde au pusher (≈ 1,25 ms) + temps pour 30 % de déformation (0,30 / vitesse) + marge 0,2 ms, plafonné à la fin de l'impulsion (≈ 1,25 + 2,1 ms). Valeurs à vérifier sur les jauges du premier calcul. |

## Mesures de performance

| Date | Modèle | Machine | Résultat |
|---|---|---|---|
| 12/10/2026 | UT19_R0500_00, maillage initial, double précision | Euler, 8 cœurs | 1 789 incréments en 59 s (≈ 33 ms/incrément), pas ≈ 1,1e-8 s imposé par des tétraèdres déformés des têtes → ≈ 3,3 h pour 4 ms |
| 12/10/2026 | têtes remaillées (sans trous M4, virtual topology) | Euler, 8 cœurs | 767 incréments en 26 s (≈ 34 ms/incrément), pas ≈ 2,6e-8 s → ≈ 153 000 incréments, **≈ 1,4 h pour 4 ms** |
