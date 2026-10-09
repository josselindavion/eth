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
2. `scripts/pre/` : `studies/<étude>/cases.csv` + `model/templates/` → `runs/<case_id>/`
   (`<case_id>.inp` + `<case_id>_paras.inp`)
3. `scripts/hpc/` : soumission sur Euler (job array)
4. `scripts/post/` : `.odb` → CSV dans `results/`

## Nommage des calculs

`<éprouvette>_R<vitesse de déformation sur 4 chiffres>_<indice>`, par ex. `UT19_R0500_00`.

## Documentation

| Fichier | Contenu |
|---|---|
| `docs/assembly.md` | placement des pièces dans le repère global, demi-modèle, découpe des pièces |
| `docs/materials.md` | matériaux, sources des données, hypothèses |
| `docs/mesh.md` | maillage : pièces, éléments, techniques, vérifications, paramètres |
