# -*- coding: utf-8 -*-
"""
make_run.py -- Prepare le dossier d'un calcul : runs/<case_id>/

Pour chaque calcul (une ligne de studies/<etude>/cases.csv), le script :
  1. copie model/templates/SHPB_UT_main.inp  -> runs/<case_id>/<case_id>.inp
     et  model/templates/SHPB_UT_paras.inp -> runs/<case_id>/<case_id>_paras.inp
     en remplacant les jetons __SPEC__, __CASE_ID__, __V_STRIKER_MS__ ;
  2. copie a cote les 7 maillages de l'eprouvette (model/geometry/<SPEC>/*.geo, ecrits par inp_to_geo.py)
     et les materiaux (model/materials/*.dat).
Le dossier est autonome : on peut le lancer tel quel, ou l'envoyer sur Euler.

Lancement (Python 3, depuis la racine du repo) :
    python shpb-ut-equilibrium/scripts/pre/make_run.py UT19_R0500_00   # un calcul
    python shpb-ut-equilibrium/scripts/pre/make_run.py                 # tous ceux de cases.csv
Si le dossier existe deja, il est ecrase (les resultats deja presents restent).
"""
import csv
import math
import os
import re
import shutil
import sys

# ============================================================
# PARAMETRES
# ============================================================
STUDY = 'taskI'                       # etude : studies/<STUDY>/cases.csv

# Vitesse du striker deduite de la vitesse de deformation visee (voir docs/results.md, section 4) :
#     vitesse d'allongement de l'eprouvette  ~  2 v_i - 2 F / Z_BARRE      (v_i = K_IMP x V_striker)
#     =>  V_striker = (vitesse de deformation x L_eff + 2 F / Z_BARRE) / (2 K_IMP)
# v_i : vitesse particulaire de l'onde incidente ; F : force moyenne dans l'eprouvette ;
# Z_BARRE = rho c A des barres : la force de l'eprouvette freine le pusher ET pousse la barre de sortie.
RHO_BARRE, C_BARRE = 8000.0, 4871.0           # barres et pusher (MARAGING)
RHO_STRIKER, C_STRIKER = 7850.0, 4720.0       # striker (STRIKER_STEEL)
A_BARRE_M2 = math.pi * 0.010 ** 2             # diametre 20 mm, le meme pour le striker
Z_BARRE = RHO_BARRE * C_BARRE * A_BARRE_M2    # 12 242 N.s/m
K_IMP = RHO_STRIKER * C_STRIKER / (RHO_STRIKER * C_STRIKER + RHO_BARRE * C_BARRE)   # 0,487

# Par eprouvette : L_eff = longueur efficace (mm) qui relie l'allongement a la deformation de
# l'extensometre ; F = force moyenne de l'eprouvette pendant l'essai (N) ; source = origine des valeurs
# (reprise dans le rapport).
SPECIMENS = {
    # Calees sur l'etude taskI_20261013-1127 (UT19 a 500 /s : 485 /s obtenus, F moyenne 6,4 a 6,8 kN)
    'UT19': {'L_eff_mm': 12.7, 'F_N': 7000.0,
             'source': 'calibrated on a first simulation at 500 s-1'},
    # Calees le 23/10/2026 sur l'etude taskI_20261023-1140 (premier calcul UT40, valeurs estimees 34 mm et
    # 15 kN) : 138 /s obtenus a 6,00 m/s et 590 /s a 19,95 m/s. Deux equations 2 K V = vit. L_eff + 2F/(rho c A)
    # -> L_eff = 30,1 mm, F = 10,4 kN (force efficace basse : la force chute fortement pendant la striction).
    # Le cas a 1000 /s n'est pas utilisable (striction hors de l'extensometre).
    'UT40': {'L_eff_mm': 30.1, 'F_N': 10400.0,
             'source': 'calibrated on the first UT40 simulations at 100 and 500 s-1 (study taskI_20261023-1140)'},
    # UT40 a partie droite parfaitement droite (cad/dxf/Xmas_UT40S.dxf, scripts/pre/straighten_gauge.py) :
    # memes valeurs que l'UT40 (meme section a 0,1 % pres)
    'UT40S': {'L_eff_mm': 30.1, 'F_N': 10400.0,
              'source': 'same as UT40 (UT40 with a perfectly straight parallel section)'},
}

# Duree simulee T_STEP, calculee pour chaque cas (on s'arrete juste apres les 30 %) :
#     T_STEP = T_ARRIVEE + DEFORMATION_CIBLE / vitesse de deformation + MARGE
# plafonnee a T_ARRIVEE + T_IMPULSION + MARGE (apres la fin de l'impulsion, plus rien
# ne tire sur l'eprouvette). Valeurs a la main, a verifier sur les jauges :
#   T_ARRIVEE   = barre d'entree / c = 6010 mm / 4871 m/s       = 1,234 ms
#   T_IMPULSION = 2 x striker / c    = 2 x 5000 mm / 4720 m/s   = 2,119 ms
# Une colonne optionnelle 't_step_ms' dans cases.csv impose la duree a la main.
DEFORMATION_CIBLE = 0.30              # deformation nominale visee (Task I : 30 %)
T_ARRIVEE_MS = 6010.0 / 4871.0        # ms
T_IMPULSION_MS = 2.0 * 5000.0 / 4720.0
MARGE_MS = 0.3                        # ms : montee de l'impulsion + retard de la mise en charge
                                      # (0,2 ms etait trop juste : 30 % a 1,995 ms pour 2,034 ms simulees)

# Sondes de force le long de la barre de sortie (colonne optionnelle 'probes' = 1 dans cases.csv) :
# tranches de 5 mm d'elements dont on sort S22 ; extract_history.py en deduit la force qui traverse
# chaque tranche (somme de S22 x volume / epaisseur). Sert a localiser l'origine des oscillations
# de la jauge de sortie. Positions en mm, comptees depuis le bout de la barre de sortie (cote eprouvette)
# ou depuis le plan de collage tete / barre (piece, reference, decalage) :
PROBE_THICKNESS = 5.0
PROBES = [
    ('HEAD_MID', 'OUTPUT_HEAD', 'tie', +14.0),     # dans la tete, entre le collage et le logement
    ('HEAD_TIE', 'OUTPUT_HEAD', 'tie', +4.0),      # dans la tete, juste au-dessus du collage
    ('BAR_TIE', 'OUTPUT_BAR', 'tie', -2.5),        # dans la barre, juste sous le collage (1 couche)
    ('BAR_100', 'OUTPUT_BAR', 'end', -100.0),      # dans la barre, a 100 mm du bout
    ('BAR_250', 'OUTPUT_BAR', 'end', -250.0),      # dans la barre, a 250 mm du bout
]

# Pieces communes a toutes les eprouvettes (+ la piece de l'eprouvette elle-meme)
BENCH_PIECES = ['STRIKER', 'INPUT_BAR', 'PUSHER_ROD', 'PUSHER_HEAD', 'OUTPUT_BAR', 'OUTPUT_HEAD']
MATERIALS = ['MARAGING', 'STRIKER_STEEL', 'DP1000']

# ============================================================
# CHEMINS
# ============================================================
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, 'model', 'templates')
GEO_ROOT = os.path.join(PROJECT_ROOT, 'model', 'geometry')     # un sous-dossier par eprouvette
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
    # Abaqus remplace les <parametres> meme dans les commentaires, et s'arrete
    # s'il ne connait pas le nom : on interdit donc les chevrons dans les commentaires.
    bad = [i + 1 for i, l in enumerate(text.splitlines()) if l.startswith('**') and ('<' in l or '>' in l)]
    if bad:
        sys.exit('Chevrons < ou > dans un commentaire de %s, lignes %s : a retirer'
                 % (template_name, ', '.join(str(i) for i in bad)))
    return text


def read_geo(path):
    """Noeuds {label: (x, y, z)} et elements [(label, [noeuds])] d'un fichier .geo."""
    nodes, elems, mode = {}, [], None
    with open(path) as f:
        for line in f:
            if line.startswith('**'):
                continue
            if line.startswith('*'):
                kw = line[1:].split(',')[0].strip().lower()
                mode = kw if kw in ('node', 'element') else None
                continue
            v = [x for x in line.replace(' ', '').strip().split(',') if x]
            if mode == 'node':
                nodes[int(v[0])] = (float(v[1]), float(v[2]), float(v[3]))
            elif mode == 'element':
                elems.append((int(v[0]), [int(x) for x in v[1:]]))
    return nodes, elems


def write_probes(geo_dir, run_dir, case_id):
    """Ecrit <case>_probe_sets.inp (groupes PROBE_*) et <case>_probe_out.inp (sorties S22)."""
    head_nodes, _ = read_geo(os.path.join(geo_dir, 'OUTPUT_HEAD.geo'))
    ys = [c[1] for c in head_nodes.values()]
    ref = {'end': max(ys), 'tie': min(ys)}         # bout de la barre de sortie, plan de collage
    meshes = {}
    sets, outs, info = ['** Sondes de force -- genere par make_run.py'], ['** Sorties des sondes'], []
    for name, piece, where, dy in PROBES:
        if piece not in meshes:
            meshes[piece] = read_geo(os.path.join(geo_dir, piece + '.geo'))
        nodes, elems = meshes[piece]
        yc = ref[where] + dy
        cent = []
        for lab, conn in elems:
            corners = conn[:8] if len(conn) in (8, 20) else conn[:4]
            cent.append((lab, len(corners), sum(nodes[n][1] for n in corners) / len(corners)))
        if all(k == 8 for _, k, _ in cent):
            # hexaedres balayes : exactement UNE couche d'elements, celle dont le centre est le plus proche
            y_best = min((abs(y - yc), y) for _, _, y in cent)[1]
            labels = [lab for lab, _, y in cent if abs(y - y_best) < 1.0e-3]
        else:
            # tetraedres : tous les elements dont le centre est dans une tranche de 5 mm
            labels = [lab for lab, _, y in cent if abs(y - yc) <= 0.5 * PROBE_THICKNESS]
        sets.append('*ELSET, ELSET=PROBE_%s' % name)
        sets += [', '.join(str(l) for l in labels[i:i + 16]) for i in range(0, len(labels), 16)]
        outs += ['*ELEMENT OUTPUT, ELSET=PROBE_%s' % name, 'S22']
        info.append('%s Y=%.2f (%d el.)' % (name, yc, len(labels)))
    with open(os.path.join(run_dir, case_id + '_probe_sets.inp'), 'w') as f:
        f.write('\n'.join(sets) + '\n')
    with open(os.path.join(run_dir, case_id + '_probe_out.inp'), 'w') as f:
        f.write('\n'.join(outs) + '\n')
    return ', '.join(info)


def striker_velocity(spec, rate):
    """Vitesse du striker en m/s pour une vitesse de deformation 'rate' en 1/s."""
    p = SPECIMENS.get(spec)
    if p is None:
        return None
    v_allongement = rate * p['L_eff_mm'] / 1000.0 + 2.0 * p['F_N'] / Z_BARRE    # m/s
    return v_allongement / (2.0 * K_IMP)


def step_time_ms(rate, case):
    """Duree simulee en ms (voir PARAMETRES) ; colonne t_step_ms de cases.csv si remplie."""
    forced = (case.get('t_step_ms') or '').strip()
    if forced:
        return float(forced), 'impose (cases.csv)'
    t = T_ARRIVEE_MS + 1000.0 * DEFORMATION_CIBLE / rate + MARGE_MS
    t_max = T_ARRIVEE_MS + T_IMPULSION_MS + MARGE_MS
    if t > t_max:
        return t_max, 'plafonne : fin de l\'impulsion avant %d %%' % round(100 * DEFORMATION_CIBLE)
    return t, ''


def make_run(case):
    case_id, spec, rate = case['case_id'], case['specimen'], float(case['strain_rate'])
    v = striker_velocity(spec, rate)
    if v is None:
        print('%-15s IGNORE : pas de parametres (SPECIMENS) pour %s' % (case_id, spec))
        return False
    needed_geo = BENCH_PIECES + [spec]
    geo_dir = os.path.join(GEO_ROOT, spec)
    if not os.path.isdir(geo_dir):
        print('%-15s IGNORE : pas de maillage model/geometry/%s/ (build_bench.py avec SPEC = %s, '
              'puis inp_to_geo.py %s)' % (case_id, spec, spec, spec))
        return False
    missing = [spec + '/' + p + '.geo' for p in needed_geo if not os.path.exists(os.path.join(geo_dir, p + '.geo'))]
    missing += [m + '.dat' for m in MATERIALS if not os.path.exists(os.path.join(MAT_DIR, m + '.dat'))]
    if missing:
        print('%-15s IGNORE : fichiers manquants : %s' % (case_id, ', '.join(missing)))
        return False

    run_dir = os.path.join(RUNS_DIR, case_id)
    os.makedirs(run_dir, exist_ok=True)
    t_ms, note = step_time_ms(rate, case)
    tokens = {'SPEC': spec, 'CASE_ID': case_id, 'V_STRIKER_MS': '%.4g' % v,
              'T_STEP': '%.4e' % (t_ms * 1.0e-3),
              'PROBE_SETS': '** (pas de sondes)', 'PROBE_OUT': '** (pas de sondes)'}
    probes = (case.get('probes') or '').strip() not in ('', '0')
    if probes:
        tokens['PROBE_SETS'] = '*INCLUDE, INPUT=%s_probe_sets.inp' % case_id
        tokens['PROBE_OUT'] = '*INCLUDE, INPUT=%s_probe_out.inp' % case_id
        note = (note + ' ; ' if note else '') + 'sondes : ' + write_probes(geo_dir, run_dir, case_id)
    with open(os.path.join(run_dir, case_id + '.inp'), 'w') as f:
        f.write(fill('SHPB_UT_main.inp', tokens))
    with open(os.path.join(run_dir, case_id + '_paras.inp'), 'w') as f:
        f.write(fill('SHPB_UT_paras.inp', tokens))
    for p in needed_geo:
        shutil.copy(os.path.join(geo_dir, p + '.geo'), run_dir)
    for m in MATERIALS:
        shutil.copy(os.path.join(MAT_DIR, m + '.dat'), run_dir)
    print('%-15s %-5s %6.0f /s   V_striker = %6.2f m/s   T_STEP = %5.3f ms  %-34s -> %s'
          % (case_id, spec, rate, v, t_ms, note, os.path.relpath(run_dir, os.getcwd())))
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
