# shpb-ut-equilibrium

Simulations Abaqus/Explicit du banc de Hopkinson automatisé avec inverseur de charge (LID) pour des éprouvettes de
traction UT19 et UT40 (Task I) : l'équilibre des forces est-il atteint à 100, 500 et 1 000 /s, et quelle vitesse de
chargement faut-il pour atteindre 30 % de déformation ?

**Résultats actuels (UT19)** : `results/taskI_20261013-1554/report/report.md`.

Toutes les commandes se tapent dans **Git Bash**, depuis la racine du repo (`C:\Users\jdavion\Documents\eth`),
**une commande à la fois**, sauf mention contraire.

---

## En bref : je veux…

| Je veux… | Je fais… | Section |
|---|---|---|
| lancer les calculs d'une étude | `py shpb-ut-equilibrium/scripts/hpc/submit_study.py taskI` | [4](#4-lancer-une-étude-sur-euler) |
| savoir où en sont les calculs | sur Euler : `squeue -u $USER` | [4](#4-lancer-une-étude-sur-euler) |
| récupérer les résultats | `py shpb-ut-equilibrium/scripts/hpc/fetch_study.py <étude> --clean` | [5](#5-récupérer-et-dépouiller) |
| faire les courbes et le rapport | `py shpb-ut-equilibrium/scripts/post/report_taskI.py shpb-ut-equilibrium/results/<étude>` | [5](#5-récupérer-et-dépouiller) |
| regarder un calcul dans Abaqus/Viewer | `fetch_study.py <étude> --odb <calcul>`, puis File → Open | [5](#5-récupérer-et-dépouiller) |
| refaire le maillage | Abaqus/CAE : `build_bench.py`, puis `inp_to_geo.py <éprouvette>` | [3](#3-construire-le-modèle) |
| ajouter l'UT40 | 7 étapes | [8](#8-ajouter-une-éprouvette-ut40) |

`<étude>` est le nom daté affiché au lancement, par ex. `taskI_20261013-1554`.

---

## 1. Ce qu'il y a dans le dossier

```
shpb-ut-equilibrium/
├── README.md              ce guide
├── cad/
│   ├── native/            pièces SolidWorks (.SLDPRT)
│   └── step/              exports STEP lus par Abaqus (pusher et barre de sortie : versions _noM4, sans trous M4)
├── model/
│   ├── materials/         MARAGING.dat, STRIKER_STEEL.dat, DP1000.dat (générés par make_materials.py)
│   ├── templates/         SHPB_UT_main.inp et SHPB_UT_paras.inp : le modèle complet, avec des jetons à remplir
│   └── geometry/          GÉNÉRÉ, non versionné : un dossier de maillages .geo par éprouvette (UT19/, UT40/)
├── scripts/
│   ├── pre/               préparation (Python 3) : matériaux, .geo, dossiers de calcul
│   ├── cae/               build_bench.py : construit et maille le banc dans Abaqus/CAE
│   ├── hpc/               Euler : lancer une étude, rapatrier les résultats
│   └── post/              extraction du .odb, rapport et figures
├── studies/taskI/cases.csv   liste des calculs de la Task I
├── runs/                  GÉNÉRÉ, non versionné : dossiers de calcul (fichiers d'entrée), jetables
├── results/               RÉSULTATS, versionnés : un dossier par étude
└── docs/                  explications détaillées (assemblage, matériaux, maillage, dépouillement)
```

| Script | Rôle | Quand |
|---|---|---|
| `scripts/pre/make_materials.py` | écrit les `.dat` des matériaux et la figure de la loi d'écrouissage | si un paramètre matériau change |
| `scripts/pre/defeature_step.py` | enlève les trous M4 des STEP du pusher et de la barre de sortie | déjà fait, seulement si la CAO change |
| `scripts/cae/build_bench.py` | Abaqus/CAE : importe, place, découpe et maille le banc ; écrit `model/geometry/_raw/SHPB_<éprouvette>_mesh.inp` | si la géométrie ou le maillage change |
| `scripts/pre/inp_to_geo.py` | convertit ce fichier en 7 `.geo` (convention du labo) | après `build_bench.py` |
| `scripts/pre/straighten_gauge.py` | copie d'un contour DXF avec la partie droite rendue parfaitement droite (UT40S) | test de l'effet du rétrécissement de la partie droite (fait le 23/10 : aucun effet ; seul l'UT40 est gardé dans les résultats) |
| `scripts/pre/dxf_to_step.py` | contour 2D de découpe (DXF) → solide STEP de la tôle (épaisseur au choix) | nouvelle éprouvette fournie en DXF |
| `scripts/pre/pocket_gaps.py` | mesure sur les STEP les jeux entre les dents de l'éprouvette et les logements (valeurs `gap_pusher`, `gap_output` de `build_bench.py`) ; demande `py -m pip install cadquery-ocp` | nouvelle éprouvette (UT40) ou nouveau logement |
| `scripts/pre/make_run.py` | remplit les gabarits pour chaque calcul (vitesse du striker, durée) → `runs/<calcul>/` | appelé par `submit_study.py` |
| `scripts/hpc/submit_study.py` | prépare les calculs, les copie sur Euler, lance un job array | à chaque étude |
| `scripts/hpc/run_array.sh` | script Slurm : un calcul Abaqus par tâche | lancé par `submit_study.py` |
| `scripts/hpc/fetch_study.py` | sur Euler : extraction (`extract_study.sh` → `extract_history.py`), puis copie sur le PC | après les calculs |
| `scripts/post/report_taskI.py` | rapport, tableau, figures, et une figure de contrôle par calcul | après `fetch_study.py` |
| `scripts/post/plot_probes.py` | diagnostic : force le long de la barre de sortie (calculs avec sondes) | étude `diag` |
| `scripts/post/extract_peeq.py` | Abaqus Python, lancé automatiquement par `extract_study.sh` (donc par `fetch_study.py`) : PEEQ max de l'éprouvette à chaque image → `<calcul>_peeq.csv` (localisation dans la striction, figure F6 et tableau T7 du rapport) | automatique |
| `scripts/post/compare_studies.py` | compare deux études calcul par calcul (même éprouvette, même vitesse) : jauge contre vraie force, équilibre, début du chargement ; sortie dans `results/<étude après>/compare_<étude avant>/` | après une modification du modèle |
| `scripts/post/diag_gauge.py` | diagnostic : lecture de la jauge de sortie (moyenne, flexion) sur un `.odb` | ponctuel |

---

## 2. Installation (une seule fois)

**PC** (Git Bash) :
```
py -m pip install --user numpy pandas matplotlib scipy
```
`defeature_step.py` demande en plus `cadquery-ocp`, seulement si la CAO change.

**Euler** : se connecter (`ssh jdavion@euler.ethz.ch`, réseau ETH ou VPN), puis
```
module load eth_proxy
git clone https://github.com/josselindavion/eth.git
```
Le repo doit être dans `~/eth` : les scripts lancés sur Euler s'y trouvent, et `submit_study.py` le met à jour
(`git pull`) à chaque lancement.

---

## 3. Construire le modèle

À faire **seulement** si la géométrie, le maillage ou une éprouvette change. Les maillages ne sont pas versionnés :
ils restent sur le PC qui les a construits (PC du labo).

| Étape | Où | Action |
|---|---|---|
| 1 | Git Bash | si un matériau change : `py shpb-ut-equilibrium/scripts/pre/make_materials.py` |
| 2 | Abaqus/CAE | **File → Run Script** → `scripts/cae/build_UT19.py` (ou `build_UT40.py`). Quelques minutes. (`build_bench.py` lancé directement construit l'UT19, valeur de `SPEC` en haut du fichier) |
| 3 | Abaqus/CAE | vérifier la sortie : placement de l'éprouvette (UT19 : « controle : placement centre identique… », puis « mise en contact (CLOSE_GAPS) : eprouvette reculee de 0.3567 mm, barre de sortie de 0.7130 mm »), nombre d'éléments (UT19 : ≈ 214 214 ; 214 214 avec l'ancien placement, la tête de sortie peut changer de quelques éléments), qualité des tétraèdres (hauteur min > 0,3 mm) |
| 4 | Git Bash | `py shpb-ut-equilibrium/scripts/pre/inp_to_geo.py UT19` (ou `UT40`) → `model/geometry/UT19/` |

Détails : `docs/assembly.md` (placement), `docs/mesh.md` (maillage), `docs/materials.md` (matériaux).

---

## 4. Lancer une étude sur Euler

**a) Choisir les calculs** : `studies/taskI/cases.csv`, une ligne par calcul.

| Colonne | Exemple | Rôle |
|---|---|---|
| `case_id` | `UT19_R0500_00` | nom : `<éprouvette>_R<vitesse sur 4 chiffres>_<indice>` |
| `specimen` | `UT19` | éprouvette (le dossier `model/geometry/<éprouvette>/` doit exister) |
| `strain_rate` | `500` | vitesse de déformation visée (/s) : `make_run.py` en déduit la vitesse du striker et la durée simulée |
| `t_step_ms` (optionnelle) | `2.5` | impose la durée simulée (ms) |
| `probes` (optionnelle) | `1` | ajoute des sondes de force le long de la barre de sortie (diagnostic, étude `studies/diag/`) |

Un calcul dont le maillage n'existe pas encore (UT40 aujourd'hui) est ignoré, avec un message.

**b) Vérifier sans rien lancer** :
```
py shpb-ut-equilibrium/scripts/hpc/submit_study.py taskI --dry-run
```
Chaque ligne affiche la vitesse du striker et la durée simulée.

**c) Lancer** (mot de passe ETH demandé deux fois) :
```
py shpb-ut-equilibrium/scripts/hpc/submit_study.py taskI
```
Pour quelques calculs seulement : `submit_study.py taskI UT19_R0500_00 UT19_R1000_00`.
La sortie donne le nom de l'étude (`taskI_<date>-<heure>`) : le noter.

**d) Suivre** (sur Euler) :
```
squeue -u $USER
tail -n 3 $SCRATCH/<étude>/*/*.sta
```
`squeue` vide = plus rien ne tourne. Un calcul fini se termine par « THE ANALYSIS HAS COMPLETED SUCCESSFULLY ».
Durée : 1 à 2 h par calcul. **`$SCRATCH` est vidé après 15 jours** : rapatrier avant.

---

## 5. Récupérer et dépouiller

**a) Rapatrier** (mot de passe ETH demandé plusieurs fois) :
```
py shpb-ut-equilibrium/scripts/hpc/fetch_study.py <étude> --clean
```
- extrait les courbes de chaque calcul terminé (`.odb` → `<calcul>_history.csv`) et les copie dans
  `results/<étude>/` ;
- `--clean` supprime sur Euler les fichiers de reprise d'Abaqus (les `.odb` restent) ;
- `--odb <calcul>` (ou `--odb all`) copie aussi les `.odb` (≈ 0,7 Go chacun) pour Abaqus/Viewer ;
- on peut relancer la commande autant de fois que voulu : les calculs déjà extraits ne sont pas refaits ;
- `--force` ré-extrait quand même (après une modification de `extract_history.py`).

**b) Rapport et figures** :
```
py shpb-ut-equilibrium/scripts/post/report_taskI.py shpb-ut-equilibrium/results/<étude>
```
→ `results/<étude>/report/report.md` (texte en anglais avec tableaux et figures) et une figure de contrôle par
calcul. Lisible directement sur GitHub.

**c) Versionner** :
```
git add shpb-ut-equilibrium/results
git commit -m "Resultats <étude>"
git push
```
Vérifier avec `git status` qu'aucun `.odb` n'apparaît (ils sont exclus par `.gitignore`).

**Voir un calcul dans Abaqus/Viewer** : après `--odb`, File → Open → *Output Database* →
`results/<étude>/<calcul>/<calcul>.odb`. Fermer l'odb ensuite (File → Close ODB), sinon Windows bloque le fichier.

---

## 6. Où sont les résultats

```
results/<étude>/                      ex. results/taskI_20261013-1554/
├── <calcul>/                         un dossier par calcul
│   ├── <calcul>_history.csv          courbes (jauges, forces, extensomètre, énergies), une ligne par µs
│   ├── <calcul>_paras.inp            paramètres du calcul (vitesse du striker, durée)
│   ├── <calcul>.sta, <calcul>.msg    journaux d'Abaqus
│   ├── <calcul>_inventory.txt        liste des sorties du .odb (diagnostic)
│   ├── <calcul>_overview.png         figure de contrôle
│   └── <calcul>.odb                  sur le PC seulement (trop gros pour GitHub), si --odb
└── report/                           report.md, T1_conditions.csv, figures F1… (.pdf pour le rapport, .png)
```

Versionné : tout sauf les `.odb`. Les fichiers d'entrée des calculs (`runs/`) ne sont pas gardés : `make_run.py`
les regénère à l'identique.

---

## 7. Tester un calcul sur le PC (avant de lancer sur Euler)

```
py shpb-ut-equilibrium/scripts/pre/make_run.py UT19_R0500_00
```
crée `runs/UT19_R0500_00/`. Puis dans l'invite **Abaqus Command** (menu Démarrer) :
```
cd /d C:\Users\jdavion\Documents\eth\shpb-ut-equilibrium\runs\UT19_R0500_00
abq2023 job=UT19_R0500_00 datacheck interactive
```
`datacheck` vérifie le modèle sans calculer (une minute). Utiliser **`abq2023`** et pas `abaqus` : sur les PC du
labo, `abaqus.bat` se place d'office dans `C:\APPS\Abaqus2023_Work` et ne trouve pas le fichier.

---

## 8. Ajouter une éprouvette (UT40)

| Étape | Où | Action |
|---|---|---|
| 1 | Git Bash ou SolidWorks | **fait le 23/10** : contour de découpe `cad/dxf/Xmas_UT40.dxf` converti par `py shpb-ut-equilibrium/scripts/pre/dxf_to_step.py <dxf> <step> 1.5` (demande `ezdxf` et `cadquery-ocp`) en `cad/step/XMas_UT40_t1p5.step`. Autre voie : SolidWorks, tôle de 1,5 mm extrudée selon +Z depuis z = 0, exportée en STEP AP214 |
| 2 | `build_bench.py` | ligne `UT40` de `SPECIMENS` : demi-largeur de la partie droite (5,0 mm si elle fait 10 mm), longueur de l'extensomètre (30 mm), jeux `gap_pusher` / `gap_output` donnés par `py shpb-ut-equilibrium/scripts/pre/pocket_gaps.py UT40` |
| 3 | Abaqus/CAE | File → Run Script → `scripts/cae/build_UT40.py`. Lire la longueur de l'éprouvette et la position de la barre de sortie (recalculées automatiquement) |
| 4 | Git Bash | `py shpb-ut-equilibrium/scripts/pre/inp_to_geo.py UT40` |
| 5 | `make_run.py` | `SPECIMENS['UT40']` : L_eff et F sont des estimations (34 mm, 15 kN), à recaler après le premier calcul |
| 6 | `report_taskI.py` | `A0_MM2['UT40']` = largeur × 1,5 mm |
| 7 | | `datacheck` (section 7), puis `submit_study.py taskI UT40_R0100_00 UT40_R0500_00 UT40_R1000_00` |

---

## 9. Problèmes déjà rencontrés

| Symptôme | Cause | Solution |
|---|---|---|
| Abaqus demande « Input file: » ou ne trouve pas le `.inp` | `abaqus.bat` du labo change de dossier | utiliser `abq2023` |
| `Remove-Item: command not found` | commande PowerShell tapée dans Git Bash | `rm -rf …` |
| « Device or resource busy » en supprimant | `.odb` encore ouvert dans Abaqus/Viewer | File → Close ODB |
| `ModuleNotFoundError: No module named 'matplotlib'` | bibliothèques absentes sur ce PC | section 2 |
| « Operation cancelled by user » pendant `pip` | deux commandes collées d'un coup | une commande à la fois |
| `IGNORE : pas de maillage model/geometry/UT40/` | maillage pas encore construit | section 3 |
| « PARAMETER … APPEARS IN A COMMENT LINE » | chevrons dans un commentaire d'un gabarit | les retirer (`make_run.py` le signale) |
| `tail -3` ne marche pas sur plusieurs fichiers | syntaxe | `tail -n 3` |
| `scp` ou `ssh` refusés | commande tapée dans la fenêtre Euler | les lancer depuis le PC |

---

## 10. Documentation

| Fichier | Contenu |
|---|---|
| `docs/assembly.md` | repère global, placement des pièces (automatique pour l'éprouvette), demi-modèle, découpe des pièces |
| `docs/materials.md` | matériaux, loi d'écrouissage Swift-Voce expliquée, hypothèses |
| `docs/mesh.md` | maillage, pas de temps, trous M4, virtual topology, guidages, performances |
| `docs/results.md` | dépouillement : filtre, indicateurs, formule de la vitesse du striker, historique des études |

**Reste à faire** : calculs de l'UT40 (géométrie prête le 23/10) et recalage de L_eff / F pour l'UT40 ; référence exacte des
400 mm de la jauge ; vitesse maximale du lanceur (37 m/s nécessaires pour l'UT40 à 1 000 /s ?) ; densités et
matériau du pusher à confirmer.
