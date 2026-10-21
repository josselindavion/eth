# -*- coding: utf-8 -*-
"""
submit_study.py -- Prepare et lance sur Euler tous les calculs d'une etude, en une commande.

Depuis ton PC (Python 3, racine du repo) :
    python shpb-ut-equilibrium/scripts/hpc/submit_study.py taskI
    python shpb-ut-equilibrium/scripts/hpc/submit_study.py taskI --dry-run   (montre sans rien faire)
    python shpb-ut-equilibrium/scripts/hpc/submit_study.py taskI UT19_R0500_00 UT40_R0500_00   (quelques cas)

Etapes :
  1. make_run.py pour chaque ligne de studies/<etude>/cases.csv  -> runs/<case_id>/
     (les cas sans geometrie, ex. UT40 pour l'instant, sont ignores)
  2. regroupe ces dossiers dans runs/_submit/<etude>_<date>/ avec la liste cases.txt
  3. copie ce dossier sur Euler : $SCRATCH/<etude>_<date>/                (scp : mot de passe)
  4. sur Euler : met a jour le repo (git pull) puis lance un job array Slurm,
     un calcul par ligne de cases.txt                                       (ssh : mot de passe)

Chaque lancement a son propre dossier date : rien n'est ecrase sur Euler.
Rappel : $SCRATCH est efface apres 15 jours -> recuperer les resultats avant.
"""
import argparse
import csv
import datetime
import os
import shutil
import subprocess
import sys

# ============================================================
# PARAMETRES
# ============================================================
EULER_USER = 'jdavion'
EULER_HOST = 'euler.ethz.ch'
REMOTE_SCRATCH = '/cluster/scratch/' + EULER_USER          # = $SCRATCH sur Euler
REMOTE_REPO = '~/eth'                                       # clone du repo sur Euler
ARRAY_SCRIPT = REMOTE_REPO + '/shpb-ut-equilibrium/scripts/hpc/run_array.sh'

# ============================================================
# CHEMINS
# ============================================================
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts', 'pre'))
import make_run                                             # noqa: E402  (scripts/pre/make_run.py)


def run(cmd, dry):
    """Affiche puis execute une commande ; arrete tout si elle echoue."""
    print('  > ' + ' '.join(cmd))
    if dry:
        return ''
    res = subprocess.run(cmd, stdout=subprocess.PIPE, universal_newlines=True)
    if res.stdout:
        print(res.stdout.rstrip())
    if res.returncode != 0:
        sys.exit('Echec de la commande ci-dessus (code %d)' % res.returncode)
    return res.stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1])
    ap.add_argument('study', help='nom de l etude (dossier studies/<etude>/)')
    ap.add_argument('cases', nargs='*', help='seulement ces calculs (par defaut : tous ceux de cases.csv)')
    ap.add_argument('--dry-run', action='store_true', help='prepare tout en local, sans copier ni lancer')
    args = ap.parse_args()

    cases_csv = os.path.join(PROJECT_ROOT, 'studies', args.study, 'cases.csv')
    with open(cases_csv) as f:
        cases = list(csv.DictReader(f))
    if args.cases:
        unknown = [c for c in args.cases if c not in [x['case_id'] for x in cases]]
        if unknown:
            sys.exit('Inconnu dans %s : %s' % (cases_csv, ', '.join(unknown)))
        cases = [c for c in cases if c['case_id'] in args.cases]

    # 1. Dossiers de calcul
    print('1. Preparation des calculs (%s)' % os.path.relpath(cases_csv, os.getcwd()))
    ready = [c['case_id'] for c in cases if make_run.make_run(c)]
    if not ready:
        sys.exit('Aucun calcul pret.')

    # 2. Regroupement dans un dossier date
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M')
    name = '%s_%s' % (args.study, stamp)
    local = os.path.join(make_run.RUNS_DIR, '_submit', name)
    os.makedirs(local)
    for cid in ready:
        shutil.copytree(os.path.join(make_run.RUNS_DIR, cid), os.path.join(local, cid))
    with open(os.path.join(local, 'cases.txt'), 'w', newline='\n') as f:
        f.write('\n'.join(ready) + '\n')
    print('2. %d calcul(s) regroupe(s) dans %s' % (len(ready), os.path.relpath(local, os.getcwd())))

    # 3. Copie sur Euler
    print('3. Copie sur Euler (mot de passe ETH demande)')
    run(['scp', '-r', '-q', local, '%s@%s:%s/' % (EULER_USER, EULER_HOST, REMOTE_SCRATCH)], args.dry_run)

    # 4. Lancement du job array
    print('4. Lancement sur Euler (mot de passe ETH demande)')
    remote = ("bash -lc 'module load eth_proxy >/dev/null 2>&1; git -C %s pull -q; "
              "cd %s/%s && sbatch --array=1-%d %s'" % (REMOTE_REPO, REMOTE_SCRATCH, name, len(ready), ARRAY_SCRIPT))
    out = run(['ssh', '%s@%s' % (EULER_USER, EULER_HOST), remote], args.dry_run)

    print('')
    if args.dry_run:
        print('(--dry-run : rien n\'a ete copie ni lance ; dossier prepare en local : %s)'
              % os.path.relpath(local, os.getcwd()))
        return
    print('Etude lancee : %s' % name)
    print('Calculs      : %s' % ', '.join(ready))
    if out:
        print('Slurm        : %s' % out.strip())
    print('Suivi sur Euler :  squeue -u $USER')
    print('                   tail -n 3 $SCRATCH/%s/*/*.sta' % name)


if __name__ == '__main__':
    main()
