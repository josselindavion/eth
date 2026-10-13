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
   - vitesse du striker ≈ vitesse de déformation × 15 mm (estimation à vérifier) ;
   - durée simulée par cas : arrivée de l'onde (1,234 ms) + 0,30 / vitesse de déformation + 0,2 ms,
     plafonnée à la fin de l'impulsion (+ 2,119 ms) → 3,55 / 2,03 / 1,73 ms à 100 / 500 / 1 000 /s
     (colonne optionnelle `t_step_ms` dans `cases.csv` pour imposer une valeur)
3. `scripts/hpc/submit_study.py <étude>` (depuis le PC) : prépare tous les cas, les copie sur Euler dans
   `$SCRATCH/<étude>_<date>/` et lance un job array Slurm (`scripts/hpc/run_array.sh`, un calcul par cas)
4. `scripts/hpc/fetch_study.py <étude>_<date>` (depuis le PC) : sur Euler, `extract_study.sh` lance
   `scripts/post/extract_history.py` (Python d'Abaqus) sur chaque calcul terminé → `<case>_history.csv`
   (jauges, forces dans les sections, extensomètre, énergies), puis rapatrie ces fichiers légers dans
   `runs/_submit/<étude>_<date>/<case>/`. Options : `--clean` (supprime les fichiers de reprise sur Euler),
   `--odb <case>` (rapatrie aussi le `.odb` pour CAE)
5. `scripts/post/plot_case.py runs/_submit/<étude>_<date>` (PC, Python 3) : un graphe `<case>_overview.png`
   par calcul (jauges, forces, déséquilibre, extensomètre) et `<étude>_<date>_summary.csv`
   (vitesse de déformation obtenue, instant des 30 %, temps de mise en équilibre…) ; voir `docs/results.md`

## Lancer Abaqus à la main (PC du labo, Windows)

| Étape | Commande |
|---|---|
| Ouvrir l'invite Abaqus | menu Démarrer → taper **Abaqus Command** → Entrée |
| Aller dans le dossier du calcul | `cd /d C:\Users\jdavion\Documents\eth\shpb-ut-equilibrium\runs\<case_id>` |
| Vérifier le modèle sans calculer | `abq2023 job=<case_id> datacheck interactive` |
| Calculer | `abq2023 job=<case_id> cpus=4 double=both interactive` |

Utiliser **`abq2023`** et pas `abaqus` : sur les PC du labo, `abaqus.bat` charge le compilateur puis se place
d'office dans `C:\APPS\Abaqus2023_Work`, et ne trouve donc pas le `.inp`.

## Lancer une étude sur Euler

Prérequis (une fois) : repo cloné sur Euler dans `~/eth` (`module load eth_proxy` puis `git clone https://github.com/josselindavion/eth.git`).

| Étape | Où | Commande |
|---|---|---|
| Préparer, copier, lancer tous les cas | PC, racine du repo | `python shpb-ut-equilibrium/scripts/hpc/submit_study.py taskI` |
| Vérifier sans rien lancer | PC | ajouter `--dry-run` |
| Suivre | Euler | `squeue -u $USER` puis `tail -n 3 $SCRATCH/<étude>_<date>/*/*.sta` |
| Récupérer les courbes (calculs terminés) | PC, racine du repo | `python shpb-ut-equilibrium/scripts/hpc/fetch_study.py <étude>_<date>` |
| … et nettoyer Euler | PC | ajouter `--clean` (garde les `.odb`) |
| … et rapatrier un `.odb` pour CAE | PC | ajouter `--odb <case_id>` |
| Tracer et résumer | PC, racine du repo | `python shpb-ut-equilibrium/scripts/post/plot_case.py shpb-ut-equilibrium/runs/_submit/<étude>_<date>` |
| Lancer un seul cas à la main | Euler, dans le dossier du cas | `sbatch ~/eth/shpb-ut-equilibrium/scripts/hpc/run_abaqus.sh` |

Chaque lancement a son propre dossier daté : rien n'est écrasé. `$SCRATCH` est vidé après 15 jours.

## Nommage des calculs

`<éprouvette>_R<vitesse de déformation sur 4 chiffres>_<indice>`, par ex. `UT19_R0500_00`.

## Documentation

| Fichier | Contenu |
|---|---|
| `docs/assembly.md` | placement des pièces dans le repère global, demi-modèle, découpe des pièces |
| `docs/materials.md` | matériaux, sources des données, hypothèses |
| `docs/mesh.md` | maillage : pièces, éléments, techniques, vérifications, paramètres |
| `docs/results.md` | dépouillement : graphes, définitions des grandeurs, premiers résultats |

## Reste à faire

| Sujet | Détail |
|---|---|
| Vitesse du striker | V = vitesse × 15 mm donne 21 /s au lieu de 100 /s : ajouter la force de l'éprouvette, V ≈ vitesse × L + 2 F / (ρ c A) (voir `docs/results.md`) |
| 30 % à 100 /s | impossible avec l'impulsion de 2,12 ms (striker de 5 m) : il faut ≈ 3 ms de chargement |
| Étude `taskI_20261013-1127` | R0100 et R0500 dépouillés ; R1000 encore en cours (pas de temps 3,9e-9 s en fin de calcul) |

## Mesures de performance

| Date | Modèle | Machine | Résultat |
|---|---|---|---|
| 12/10/2026 | UT19_R0500_00, maillage initial, double précision | Euler, 8 cœurs | 1 789 incréments en 59 s (≈ 33 ms/incrément), pas ≈ 1,1e-8 s imposé par des tétraèdres déformés des têtes → ≈ 3,3 h pour 4 ms |
| 12/10/2026 | têtes remaillées (sans trous M4, virtual topology) | Euler, 8 cœurs | 767 incréments en 26 s (≈ 34 ms/incrément), pas ≈ 2,6e-8 s → ≈ 153 000 incréments, **≈ 1,4 h pour 4 ms** |
| 12/10/2026 | étude taskI (UT19, 4 ms simulées, double précision) | Euler, 8 cœurs par cas | R0100 : 4 182 s (1,2 h) ; R0500 : 6 473 s (1,8 h) ; R1000 : 11 329 s (**3,1 h**, proche de la limite de 4 h). Plus la vitesse est grande, plus l'éprouvette se déforme et plus le pas de temps baisse en cours de calcul |
