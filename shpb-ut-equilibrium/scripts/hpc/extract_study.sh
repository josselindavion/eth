#!/bin/bash
# ============================================================================
# extract_study.sh -- Sur Euler : extrait les courbes de tous les calculs d'une
# etude (.odb -> CSV), nettoie les fichiers inutiles, et emballe les resultats
# legers dans une archive a rapatrier.
# ============================================================================
# Normalement appele par scripts/hpc/fetch_study.py (depuis ton PC) :
#     bash ~/eth/shpb-ut-equilibrium/scripts/hpc/extract_study.sh $SCRATCH/<etude> [--clean] [--force]
#
# Pour chaque calcul TERMINE (THE ANALYSIS HAS COMPLETED SUCCESSFULLY dans le .sta) :
#   - abaqus python extract_history.py  ->  <case>_history.csv + <case>_inventory.txt
#   - abaqus python extract_peeq.py     ->  <case>_peeq.csv (PEEQ max de l'eprouvette par image)
#   - avec --clean : supprime les fichiers de reprise / temporaires d'Abaqus
#     (.res .abq .pac .sel .stt .mdl .prt .com .par .pes .pmg .ipm .lck),
#     qui ne servent qu'a relancer un calcul interrompu. Le .odb est GARDE.
# Un calcul deja extrait (CSV plus recent que le .odb) n'est pas re-extrait, sauf avec --force
# (apres une modification de extract_history.py).
# Puis cree <etude>/<etude>_results.tgz : CSV, inventaires, parametres (_paras.inp), .sta, .msg.
# ============================================================================
STUDY_DIR=${1%/}
shift
CLEAN=""
FORCE=""
for a in "$@"; do
    [ "$a" == "--clean" ] && CLEAN="--clean"
    [ "$a" == "--force" ] && FORCE="--force"     # re-extraire meme si le CSV existe deja
done
HERE=$(cd "$(dirname "$0")" && pwd)
EXTRACT="$HERE/../post/extract_history.py"
PEEQ="$HERE/../post/extract_peeq.py"

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
    if [ -z "$FORCE" ] && [ "$c/${c}_history.csv" -nt "$c/$c.odb" ]; then
        echo "$c : deja extrait"
    else
        (cd "$c" && abaqus python "$EXTRACT" "$PWD" 2>&1 | grep -v -i "^abaqus license\|^<\|checked out")
    fi
    # PEEQ max de l'eprouvette par image (localisation dans la striction ; depuis le 27/10/2026)
    if [ -z "$FORCE" ] && [ "$c/${c}_peeq.csv" -nt "$c/$c.odb" ]; then
        echo "$c : PEEQ deja extraite"
    else
        (cd "$c" && abaqus python "$PEEQ" "$PWD" 2>&1 | grep -v -i "^abaqus license\|^<\|checked out")
    fi
    if [ "$CLEAN" == "--clean" ]; then
        rm -f "$c/$c".{res,abq,pac,sel,stt,mdl,prt,com,par,pes,pmg,ipm,lck}
    fi
done

NAME=$(basename "$STUDY_DIR")
tar czf "${NAME}_results.tgz" */*_history.csv */*_peeq.csv */*_inventory.txt */*_paras.inp */*.sta */*.msg 2>/dev/null
echo "Archive : $STUDY_DIR/${NAME}_results.tgz ($(du -h "${NAME}_results.tgz" | cut -f1))"
du -sh "$STUDY_DIR" | sed 's/^/Place occupee par l etude : /'
