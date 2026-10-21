# shpb-ut-equilibrium

Simulations Abaqus de l'équilibre des efforts dans les éprouvettes UT (UT19, UT40) sur barres de Hopkinson (SHPB).

## Arborescence

```
shpb-ut-equilibrium/
├── cad/
│   ├── native/        sources SolidWorks (.SLDPRT / .SLDASM)
│   └── step/          exports STEP importés par Abaqus
├── model/             modèle Abaqus « source », conventions du labo
│   ├── geometry/      un dossier par éprouvette : UT19/*.geo, UT40/*.geo (7 pièces, générés, non versionnés)
│   ├── materials/     A2_tool_steel.dat, A286.dat, specimen_*.dat
│   ├── templates/     SHPB_UT_main.inp (avec *INCLUDE et <PARAMÈTRES>)
│   └── subroutines/   VUMAT du labo, le cas échéant
├── scripts/
│   ├── cae/           Python 2.7 lancé par Abaqus : STEP → maillage → .geo
│   ├── pre/           Python 3 : plan de calcul → génère runs/
│   ├── hpc/           envoi sur Euler (submit_study), job array, rapatriement (fetch_study)
│   └── post/          extraction du .odb (abaqus python) + graphes et livrables (Python 3)
├── studies/
│   └── taskI/cases.csv   matrice : UT19/UT40 × 100/500/1000 s⁻¹
├── runs/              GÉNÉRÉ, non versionné : fichiers d'entrée des calculs (à envoyer, ou lancés à la main)
│   └── _submit/       copies préparées pour Euler (submit_study.py) ; jetable
├── results/           RÉSULTATS, versionnés : un dossier par étude (voir ci-dessous)
└── docs/              notes, schémas du banc
```

### Où sont les résultats

```
results/<étude>_<date>/                    ex. results/taskI_20261013-1554/
├── <case>/                                un dossier par calcul, ex. UT19_R0500_00/
│   ├── <case>_history.csv                 courbes extraites du .odb (jauges, forces, extensomètre, énergies)
│   ├── <case>_paras.inp                   paramètres du calcul (vitesse du striker, durée)
│   ├── <case>.sta, <case>.msg             journaux Abaqus (déroulement, avertissements)
│   ├── <case>_inventory.txt               liste des sorties du .odb
│   ├── <case>_overview.png                graphe de contrôle (plot_case.py)
│   └── <case>.odb                         SUR LE PC SEULEMENT (≈ 700 Mo, pas sur GitHub), si --odb
├── <étude>_<date>_summary.csv             résumé de plot_case.py
└── report/                                livrables (report_taskI.py) : T1, F1…F5 (.pdf + .png), report.md
```

Tout est rangé automatiquement par `fetch_study.py` puis les deux scripts de tracé ; il reste à faire
`git add` + `git commit` + `git push`. Les fichiers d'entrée des calculs (`runs/`) ne sont pas versionnés :
on les regénère avec `make_run.py`. Les `.odb` non plus (GitHub refuse les fichiers de plus de 100 Mo) :
ils restent sur le PC dans `results/…/<case>/`, et sur Euler jusqu'à la purge de `$SCRATCH` (15 jours).

## Chaîne de calcul

0. `scripts/pre/make_materials.py` : paramètres matériaux → `model/materials/*.dat` (voir `docs/materials.md`)
1. `scripts/cae/build_bench.py` (Abaqus/CAE, `SPEC = 'UT19'` ou `'UT40'` en tête du script) : STEP (`cad/step/`) →
   placement automatique de l'éprouvette et de la barre de sortie (`docs/assembly.md`) → maillage →
   `model/geometry/_raw/SHPB_<SPEC>_mesh.inp`, puis `scripts/pre/inp_to_geo.py <SPEC>` (Python 3) →
   `model/geometry/<SPEC>/<PIÈCE>.geo` (voir `docs/mesh.md`, section 10)
2. `scripts/pre/make_run.py` : `studies/<étude>/cases.csv` + `model/templates/` → `runs/<case_id>/`
   (`<case_id>.inp` + `<case_id>_paras.inp` + copies des `.geo` et `.dat` : dossier autonome)
   - vitesse du striker = (vitesse de déformation × L_eff + 2 F / ρcA) / (2 × 0,487), qui tient compte
     de la force de l'éprouvette (voir `docs/results.md`, section 4) → 2,48 / 7,69 / 14,20 m/s à 100 / 500 / 1 000 /s ;
   - durée simulée par cas : arrivée de l'onde (1,234 ms) + 0,30 / vitesse de déformation + 0,3 ms,
     plafonnée à la fin de l'impulsion (+ 2,119 ms) → 3,65 / 2,13 / 1,83 ms à 100 / 500 / 1 000 /s
     (colonne optionnelle `t_step_ms` dans `cases.csv` pour imposer une valeur)
3. `scripts/hpc/submit_study.py <étude>` (depuis le PC) : prépare tous les cas, les copie sur Euler dans
   `$SCRATCH/<étude>_<date>/` et lance un job array Slurm (`scripts/hpc/run_array.sh`, un calcul par cas)
4. `scripts/hpc/fetch_study.py <étude>_<date>` (depuis le PC) : sur Euler, `extract_study.sh` lance
   `scripts/post/extract_history.py` (Python d'Abaqus) sur chaque calcul terminé → `<case>_history.csv`
   (jauges, forces dans les sections, extensomètre, énergies), puis rapatrie ces fichiers légers dans
   `results/<étude>_<date>/<case>/`. Options : `--clean` (supprime les fichiers de reprise sur Euler),
   `--odb <case>` ou `--odb all` (rapatrie aussi les `.odb`, pour CAE)
5. `scripts/post/plot_case.py results/<étude>_<date>` (PC, Python 3) : un graphe de contrôle `<case>_overview.png`
   par calcul et `<étude>_<date>_summary.csv` ; voir `docs/results.md`
6. `scripts/post/report_taskI.py results/<étude>_<date>` (PC, Python 3 + scipy) : livrables de la Task I
   dans `results/<étude>_<date>/report/` (tableau T1, figures F1 à F5, texte en anglais) ; voir `docs/results.md`

## Ajouter l'éprouvette UT40 (ou une autre)

| Étape | Où | Action |
|---|---|---|
| 1 | SolidWorks | exporter la tôle de 1,5 mm (extrudée selon +Z depuis z = 0) en STEP AP214 : `cad/step/XMas_UT40_t1p5.step` |
| 2 | `scripts/cae/build_bench.py` | vérifier la ligne `UT40` de `SPECIMENS` : fichier, demi-largeur de la partie droite (5,0 mm si 10 mm de large), longueur de l'extensomètre (30 mm, zone DIC de Beerli) |
| 3 | Abaqus/CAE | `SPEC = 'UT40'`, puis File → Run Script → `build_bench.py`. Lire dans la sortie : longueur de l'éprouvette, position de la barre de sortie, qualité des tétraèdres |
| 4 | PC, racine du repo | `python shpb-ut-equilibrium/scripts/pre/inp_to_geo.py UT40` → `model/geometry/UT40/` |
| 5 | `scripts/pre/make_run.py` | `SPECIMENS['UT40']` : L_eff et F sont des **estimations** (34 mm, 15 kN), à recaler après le premier calcul |
| 6 | `scripts/post/report_taskI.py` | `A0_MM2['UT40']` = largeur × 1,5 mm (15 mm² si 10 mm de large) |
| 7 | PC | `datacheck` d'un cas à la main, puis `submit_study.py taskI` (les cas UT40 de `cases.csv` sont pris automatiquement) |

**Après la mise à jour du 21/10/2026** : les `.geo` de l'UT19 doivent être dans `model/geometry/UT19/`.
Une fois : `python shpb-ut-equilibrium/scripts/pre/inp_to_geo.py UT19` (relit `_raw/SHPB_UT19_mesh.inp`).

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
| … et rapatrier un `.odb` (ou tous) pour CAE | PC | ajouter `--odb <case_id>` (ou `--odb all`) |
| Graphes de contrôle | PC, racine du repo | `python shpb-ut-equilibrium/scripts/post/plot_case.py shpb-ut-equilibrium/results/<étude>_<date>` |
| Livrables Task I | PC, racine du repo | `python shpb-ut-equilibrium/scripts/post/report_taskI.py shpb-ut-equilibrium/results/<étude>_<date>` |
| Versionner les résultats | PC, racine du repo | `git add shpb-ut-equilibrium/results` puis `git commit` et `git push` |
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
| UT40 | chaîne prête (section « Ajouter l'éprouvette UT40 ») ; il manque le fichier STEP (le fichier reçu le 21/10 était la NT20 entaillée, renommé `cad/step/Xmas_NT20_t1p5.step`). Vitesses du striker estimées : 6,0 / 19,9 / 37,4 m/s → 37 m/s est-il possible avec le lanceur ? |
| Jauge de sortie | référence exacte des 400 mm à confirmer ; oscillations fortes à 500 et 1 000 /s (tête de la barre de sortie ?) |
| Matériau | DP1000 indépendant de la vitesse : en essai la force, donc la vitesse du striker nécessaire, augmentera |
| 30 % à 100 /s | impossible avec l'impulsion de 2,12 ms (striker de 5 m) : écrit comme un résultat (18,5 % max) |

## Mesures de performance

| Date | Modèle | Machine | Résultat |
|---|---|---|---|
| 12/10/2026 | UT19_R0500_00, maillage initial, double précision | Euler, 8 cœurs | 1 789 incréments en 59 s (≈ 33 ms/incrément), pas ≈ 1,1e-8 s imposé par des tétraèdres déformés des têtes → ≈ 3,3 h pour 4 ms |
| 12/10/2026 | têtes remaillées (sans trous M4, virtual topology) | Euler, 8 cœurs | 767 incréments en 26 s (≈ 34 ms/incrément), pas ≈ 2,6e-8 s → ≈ 153 000 incréments, **≈ 1,4 h pour 4 ms** |
| 12/10/2026 | étude taskI (UT19, 4 ms simulées, double précision) | Euler, 8 cœurs par cas | R0100 : 4 182 s (1,2 h) ; R0500 : 6 473 s (1,8 h) ; R1000 : 11 329 s (**3,1 h**, proche de la limite de 4 h). Plus la vitesse est grande, plus l'éprouvette se déforme et plus le pas de temps baisse en cours de calcul |
