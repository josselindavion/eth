# -*- coding: utf-8 -*-
"""
make_run.py -- Prepare le dossier d'un calcul : runs/<case_id>/

Pour chaque calcul (une ligne de studies/<etude>/cases.csv), le script :
  1. copie model/templates/SHPB_UT_main.inp  -> runs/<case_id>/<case_id>.inp
     et  model/templates/SHPB_UT_paras.inp -> runs/<case_id>/<case_id>_paras.inp
     en remplacant les jetons __SPEC__, __CASE_ID__, __V_STRIKER_MS__ ;
  2. copie a cote les 7 maillages (model/geometry/*.geo)
     et les materiaux (model/materials/*.dat).
Le dossier est autonome : on peut le lancer tel quel, ou l'envoyer sur Euler.

Lancement (Python 3, depuis la racine du repo) :
    python shpb-ut-equilibrium/scripts/pre/make_run.py UT19_R0500_00   # un calcul
    python shpb-ut-equilibrium/scripts/pre/make_run.py                 # tous ceux de cases.csv
Si le dossier existe deja, il est ecrase (les resultats deja presents restent).
"""
import csv
import os
import re
import shutil
import sys

# ============================================================
# PARAMETRES
# ============================================================
STUDY = 'taskI'                       # etude : studies/<STUDY>/cases.csv

# Vitesse du striker deduite de la vitesse de deformation visee :
#     V_striker ~ V_pusher ~ (vitesse de deformation) x (longueur de reference)
# ESTIMATION a verifier avec le premier calcul (extensometre).
# Longueur de reference = partie droite de la zone utile, en mm.
L_REF_MM = {
    'UT19': 15.0,                     # partie droite mesuree dans build_bench.py (15,000 mm)
    'UT40': None,                     # geometrie pas encore disponible
}

# Pieces communes a toutes les eprouvettes (+ la piece de l'eprouvette elle-meme)
BENCH_PIECES = ['STRIKER', 'INPUT_BAR', 'PUSHER_ROD', 'PUSHER_HEAD', 'OUTPUT_BAR', 'OUTPUT_HEAD']
MATERIALS = ['MARAGING', 'STRIKER_STEEL', 'DP1000']

# ============================================================
# CHEMINS
# ============================================================
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, 'model', 'templates')
GEO_DIR = os.path.join(PROJECT_ROOT, 'model', 'geometry')
MAT_DIR = os.path.join(PROJECT_ROOT, 'model', 'materials')
RUNS_DIR = os.path.join(PROJECT_ROOT, 'runs')
CASES_CSV = os.path.join(PROJECT_ROOT, 'studies', STUDY, 'cases.csv')

TOKEN = re.compile(r'__[A-Z][A-Z0-9_]*?__')


def fill(template_name, tokens):
    """Lit un gabarit et remplace les jetons ; erreur s'il en reste."""
    with open(os.path.join(TEMPLATE_DIR, template_name)) as f:
        text = f.read()
    for key, value in tokens.items():
        text = text.replace('__%s__' % key, str(value))
    left = TOKEN.findall(text)
    if left:
        sys.exit('Jetons non remplaces dans %s : %s' % (template_name, ', '.join(sorted(set(left)))))
    return text


def striker_velocity(spec, rate):
    """Vitesse du striker en m/s pour une vitesse de deformation 'rate' en 1/s."""
    L = L_REF_MM.get(spec)
    if L is None:
        return None
    return rate * L / 1000.0          # (1/s) x mm -> mm/s -> m/s


def make_run(case):
    case_id, spec, rate = case['case_id'], case['specimen'], float(case['strain_rate'])
    v = striker_velocity(spec, rate)
    if v is None:
        print('%-15s IGNORE : pas de longueur de reference pour %s' % (case_id, spec))
        return False
    needed_geo = BENCH_PIECES + [spec]
    missing = [p + '.geo' for p in needed_geo if not os.path.exists(os.path.join(GEO_DIR, p + '.geo'))]
    missing += [m + '.dat' for m in MATERIALS if not os.path.exists(os.path.join(MAT_DIR, m + '.dat'))]
    if missing:
        print('%-15s IGNORE : fichiers manquants : %s' % (case_id, ', '.join(missing)))
        return False

    run_dir = os.path.join(RUNS_DIR, case_id)
    os.makedirs(run_dir, exist_ok=True)
    tokens = {'SPEC': spec, 'CASE_ID': case_id, 'V_STRIKER_MS': '%.4g' % v}
    with open(os.path.join(run_dir, case_id + '.inp'), 'w') as f:
        f.write(fill('SHPB_UT_main.inp', tokens))
    with open(os.path.join(run_dir, case_id + '_paras.inp'), 'w') as f:
        f.write(fill('SHPB_UT_paras.inp', tokens))
    for p in needed_geo:
        shutil.copy(os.path.join(GEO_DIR, p + '.geo'), run_dir)
    for m in MATERIALS:
        shutil.copy(os.path.join(MAT_DIR, m + '.dat'), run_dir)
    print('%-15s %-5s %6.0f /s   V_striker = %6.2f m/s   -> %s'
          % (case_id, spec, rate, v, os.path.relpath(run_dir, os.getcwd())))
    return True


def main():
    with open(CASES_CSV) as f:
        cases = list(csv.DictReader(f))
    wanted = sys.argv[1:]
    if wanted:
        unknown = [w for w in wanted if w not in [c['case_id'] for c in cases]]
        if unknown:
            sys.exit('Inconnu dans %s : %s' % (os.path.relpath(CASES_CSV, os.getcwd()), ', '.join(unknown)))
        cases = [c for c in cases if c['case_id'] in wanted]
    n = sum(make_run(c) for c in cases)
    print('%d dossier(s) de calcul prepare(s) dans %s' % (n, RUNS_DIR))


if __name__ == '__main__':
    main()
