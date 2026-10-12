#!/bin/bash
# ============================================================================
# run_abaqus.sh -- Lance UN calcul Abaqus/Explicit sur Euler (Slurm)
# ============================================================================
# A soumettre DEPUIS le dossier du calcul (celui qui contient <case_id>.inp) :
#
#     cd $SCRATCH/UT19_R0500_00
#     sbatch $HOME/eth/shpb-ut-equilibrium/scripts/hpc/run_abaqus.sh
#
# Le nom du calcul est pris automatiquement : c'est le nom du dossier.
# Les ressources ci-dessous (#SBATCH) peuvent etre changees a la soumission,
# sans modifier ce fichier :   sbatch --time=12:00:00 --cpus-per-task=16 run_abaqus.sh
# ============================================================================
#SBATCH --job-name=abaqus
#SBATCH --time=01:00:00            # duree max (hh:mm:ss) ; le job est tue au-dela
#SBATCH --ntasks=1                 # un seul processus Abaqus...
#SBATCH --cpus-per-task=8          # ... qui utilise 8 coeurs (threads)
#SBATCH --mem-per-cpu=2G           # memoire par coeur (8 x 2 Go = 16 Go)
#SBATCH --tmp=20G                  # disque local du noeud ($TMPDIR) pour les fichiers temporaires
#SBATCH --output=slurm_%j.out      # ce qu'Abaqus affiche (%j = numero du job)
#SBATCH --error=slurm_%j.err       # messages d'erreur

# Logiciels : meme ligne que dans la doc du labo / d'Euler
module load stack/2024-06 intel-oneapi-compilers/2023.2.0 abaqus/2023 libjpeg-turbo/3.0.0

JOB=$(basename "$PWD")             # ex. UT19_R0500_00
echo "Calcul $JOB sur $(hostname), $SLURM_CPUS_PER_TASK coeurs, debut $(date)"

# job=/input=   : nom du calcul et fichier .inp
# cpus=         : nombre de coeurs donnes par Slurm
# mp_mode=threads : parallelisme par threads sur un seul noeud (recommande sur Euler)
# double=both   : double precision (calcul long : on evite l'accumulation d'arrondis)
# scratch=      : fichiers temporaires sur le disque local du noeud (rapide)
# interactive   : Abaqus reste au premier plan, sinon le job Slurm se terminerait tout de suite
abaqus job=$JOB input=$JOB.inp cpus=$SLURM_CPUS_PER_TASK mp_mode=threads \
       double=both scratch=$TMPDIR interactive

echo "Fin $(date)"
