# -*- coding: utf-8 -*-
"""
fetch_study.py -- Recupere sur ton PC les resultats d'une etude calculee sur Euler.

Depuis ton PC (Python 3, racine du repo) :
    python shpb-ut-equilibrium/scripts/hpc/fetch_study.py taskI_20261013-1554
    python shpb-ut-equilibrium/scripts/hpc/fetch_study.py taskI_20261013-1554 --clean
    python shpb-ut-equilibrium/scripts/hpc/fetch_study.py taskI_20261013-1554 --odb UT19_R0500_00
    python shpb-ut-equilibrium/scripts/hpc/fetch_study.py taskI_20261013-1554 --odb all
    python shpb-ut-equilibrium/scripts/hpc/fetch_study.py taskI_20261013-1554 --force   (re-extraire)

Etapes :
  1. sur Euler (ssh, mot de passe) : git pull, puis scripts/hpc/extract_study.sh :
     extraction des courbes de chaque calcul termine (.odb -> <case>_history.csv),
     nettoyage optionnel (--clean : fichiers de reprise d'Abaqus ; le .odb est garde),
     archive <etude>_results.tgz avec les fichiers legers (CSV, parametres, .sta, .msg) ;
  2. copie de l'archive sur le PC (scp, mot de passe) et deballage dans results/<etude>/<case>/
     (dossier suivi par git : c'est LA que sont les resultats) ;
  3. avec --odb CASE (ou --odb all) : copie aussi le(s) .odb (~700 Mo chacun) dans results/<etude>/<case>/.
     Les .odb ne sont pas envoyes sur GitHub (trop gros, voir .gitignore) : ils restent sur le PC.

On peut relancer ce script autant de fois que voulu (ex. quand un calcul de plus est termine).
"""
import argparse
import os
import subprocess
import sys
import tarfile

# ============================================================
# PARAMETRES
# ============================================================
EULER_USER = 'jdavion'
EULER_HOST = 'euler.ethz.ch'
REMOTE_SCRATCH = '/cluster/scratch/' + EULER_USER
REMOTE_REPO = '~/eth'
EXTRACT_SCRIPT = REMOTE_REPO + '/shpb-ut-equilibrium/scripts/hpc/extract_study.sh'

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')


def run(cmd):
    print('  > ' + ' '.join(cmd))
    res = subprocess.run(cmd)
    if res.returncode != 0:
        sys.exit('Echec de la commande ci-dessus (code %d)' % res.returncode)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('study', help='dossier de l etude sur Euler, ex. taskI_20261013-1127')
    ap.add_argument('--clean', action='store_true', help='supprime aussi les fichiers de reprise sur Euler')
    ap.add_argument('--force', action='store_true',
                    help='re-extrait les courbes meme si elles existent (apres une modif de extract_history.py)')
    ap.add_argument('--odb', metavar='CASE', help='copie aussi le .odb de ce calcul (all : tous)')
    args = ap.parse_args()

    remote_dir = '%s/%s' % (REMOTE_SCRATCH, args.study)
    host = '%s@%s' % (EULER_USER, EULER_HOST)
    local = os.path.join(RESULTS_DIR, args.study)
    os.makedirs(local, exist_ok=True)

    print('1. Extraction sur Euler (mot de passe ETH demande)')
    remote = ("bash -lc 'module load eth_proxy >/dev/null 2>&1; git -C %s pull -q; bash %s %s %s %s'"
              % (REMOTE_REPO, EXTRACT_SCRIPT, remote_dir, '--clean' if args.clean else '',
                 '--force' if args.force else ''))
    run(['ssh', host, remote])

    print('2. Copie des resultats sur le PC (mot de passe ETH demande)')
    tgz = '%s_results.tgz' % args.study
    run(['scp', '-q', '%s:%s/%s' % (host, remote_dir, tgz), local])
    with tarfile.open(os.path.join(local, tgz)) as t:
        names = t.getnames()
        t.extractall(local)
    os.remove(os.path.join(local, tgz))
    csvs = sorted(n for n in names if n.endswith('_history.csv'))
    print('   %d fichier(s) recupere(s) dans %s' % (len(names), os.path.relpath(local, os.getcwd())))
    for n in csvs:
        print('     ' + n)

    if args.odb:
        cases = sorted(set(n.split('/')[0] for n in csvs)) if args.odb == 'all' else [args.odb]
        print('3. Copie des .odb : %s (mot de passe ETH demande)' % ', '.join(cases))
        for c in cases:
            dest = os.path.join(local, c)
            os.makedirs(dest, exist_ok=True)
            run(['scp', '%s:%s/%s/%s.odb' % (host, remote_dir, c, c), dest])
    print('Resultats : %s' % os.path.relpath(local, os.getcwd()))


if __name__ == '__main__':
    main()
