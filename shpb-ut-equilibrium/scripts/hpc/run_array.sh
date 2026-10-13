#!/bin/bash
# ============================================================================
# run_array.sh -- Lance TOUS les calculs d'une etude sur Euler (job array Slurm)
# ============================================================================
# Normalement appele par scripts/hpc/submit_study.py (depuis ton PC).
# A soumettre depuis le dossier de l'etude sur Euler, qui contient :
#     cases.txt          un nom de calcul par ligne (ex. UT19_R0500_00)
#     UT19_R0100_00/     un dossier par calcul (sortie de make_run.py)
#     UT19_R0500_00/ ...
#
#     sbatch --array=1-3 $HOME/eth/shpb-ut-equilibrium/scripts/hpc/run_array.sh
#
# Slurm lance alors 3 jobs independants (en parallele si des noeuds sont libres).
# Chacun recoit un numero SLURM_ARRAY_TASK_ID (1, 2, 3...) et prend la ligne
# correspondante de cases.txt.
# ============================================================================
#SBATCH --job-name=shpb
#SBATCH --time=08:00:00            # par calcul ; mesure 12/10/2026 (4 ms simulees) : 1,2 h a 100/s, 3,1 h a 1000/s
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem-per-cpu=2G
#SBATCH --tmp=20G
#SBATCH --output=slurm_%A_%a.out   # %A = numero du job array, %a = numero du calcul
#SBATCH --error=slurm_%A_%a.err

module load stack/2024-06 intel-oneapi-compilers/2023.2.0 abaqus/2023 libjpeg-turbo/3.0.0

CASE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" cases.txt)
if [ -z "$CASE" ] || [ ! -d "$CASE" ]; then
    echo "Ligne $SLURM_ARRAY_TASK_ID de cases.txt vide ou dossier '$CASE' introuvable" >&2
    exit 1
fi
cd "$CASE"
echo "Calcul $CASE (tache $SLURM_ARRAY_TASK_ID) sur $(hostname), $SLURM_CPUS_PER_TASK coeurs, debut $(date)"

# Memes options que run_abaqus.sh ; ask_delete=OFF : ne jamais attendre de reponse (y/n)
abaqus job=$CASE input=$CASE.inp cpus=$SLURM_CPUS_PER_TASK mp_mode=threads \
       double=both scratch=$TMPDIR ask_delete=OFF interactive

echo "Fin $CASE $(date)"
