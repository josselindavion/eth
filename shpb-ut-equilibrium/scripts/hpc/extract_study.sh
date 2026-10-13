#!/bin/bash
# ============================================================================
# extract_study.sh -- Sur Euler : extrait les courbes de tous les calculs d'une
# etude (.odb -> CSV), nettoie les fichiers inutiles, et emballe les resultats
# legers dans une archive a rapatrier.
# ============================================================================
# Normalement appele par scripts/hpc/fetch_study.py (depuis ton PC) :
#     bash ~/eth/shpb-ut-equilibrium/scripts/hpc/extract_study.sh $SCRATCH/taskI_20261013-1127 [--clean]
#
# Pour chaque calcul TERMINE (THE ANALYSIS HAS COMPLETED SUCCESSFULLY dans le .sta) :
#   - abaqus python extract_history.py  ->  <case>_history.csv + <case>_inventory.txt
#   - avec --clean : supprime les fichiers de reprise / temporaires d'Abaqus
#     (.res .abq .pac .sel .stt .mdl .prt .com .par .pes .pmg .ipm .lck),
#     qui ne servent qu'a relancer un calcul interrompu. Le .odb est GARDE.
# Puis cree <etude>/<etude>_results.tgz : CSV, inventaires, .sta, .msg, journaux Slurm.
# ============================================================================
STUDY_DIR=${1%/}
CLEAN=$2
HERE=$(cd "$(dirname "$0")" && pwd)
EXTRACT="$HERE/../post/extract_history.py"

if [ ! -d "$STUDY_DIR" ]; then
    echo "Dossier d'etude introuvable : $STUDY_DIR" >&2
    exit 1
fi
module load stack/2024-06 intel-oneapi-compilers/2023.2.0 abaqus/2023 libjpeg-turbo/3.0.0 >/dev/null 2>&1
cd "$STUDY_DIR"

for d in */; do
    c=${d%/}
    [ -f "$c/$c.odb" ] || continue
    if ! grep -q "COMPLETED SUCCESSFULLY" "$c/$c.sta" 2>/dev/null; then
        echo "$c : calcul pas termine (ou en echec), ignore"
        continue
    fi
    (cd "$c" && abaqus python "$EXTRACT" "$PWD" 2>&1 | grep -v -i "^abaqus license\|^<\|checked out")
    if [ "$CLEAN" == "--clean" ]; then
        rm -f "$c/$c".{res,abq,pac,sel,stt,mdl,prt,com,par,pes,pmg,ipm,lck}
    fi
done

NAME=$(basename "$STUDY_DIR")
tar czf "${NAME}_results.tgz" */*_history.csv */*_inventory.txt */*.sta */*.msg slurm_* cases.txt 2>/dev/null
echo "Archive : $STUDY_DIR/${NAME}_results.tgz ($(du -h "${NAME}_results.tgz" | cut -f1))"
du -sh "$STUDY_DIR" | sed 's/^/Place occupee par l etude : /'
