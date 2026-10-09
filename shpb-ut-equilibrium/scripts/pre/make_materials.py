# -*- coding: utf-8 -*-
"""
make_materials.py -- Genere les fichiers materiaux Abaqus (model/materials/*.dat).

Convention du labo : chaque fichier .dat ne contient que les mots-cles du
materiau (*Density, *Elastic, *Plastic...). Il est insere dans le .inp
principal par :

    *MATERIAL, NAME=DP1000
    *INCLUDE, INPUT=DP1000.dat

Unites : mm, N, s, MPa, t/mm^3   (1 kg/m^3 = 1e-12 t/mm^3)

Lancement (Python 3, pas besoin d'Abaqus), depuis la racine du repo :
    python shpb-ut-equilibrium/scripts/pre/make_materials.py
"""
import math
import os

# ============================================================
# PARAMETRES  (le seul endroit a modifier)
# ============================================================

# --- Materiaux elastiques (barres, pusher, striker) ---
# E est deduit de la vitesse des ondes mesuree sur le banc : E = rho * c^2
# (Beerli et al. 2026, section 2.5).
ELASTIC = {
    # Barres d'entree et de sortie + pusher : acier maraging traite thermiquement.
    # c mesuree sur la barre d'entree. Densite : valeur usuelle du maraging (HYPOTHESE).
    'MARAGING': {'rho_kg_m3': 8000.0, 'c_m_s': 4871.0, 'nu': 0.3},
    # Striker : acier, c mesuree. Densite : valeur usuelle de l'acier (HYPOTHESE).
    'STRIKER_STEEL': {'rho_kg_m3': 7850.0, 'c_m_s': 4720.0, 'nu': 0.3},
}

# --- Eprouvette : DP1000 (Beerli et al. 2026, tableau 4) ---
# Ecrouissage Swift-Voce, independant de la vitesse :
#   k(ep) = a_SV * A * (ep + e0)^n  +  (1 - a_SV) * (k0 + Q * (1 - exp(-beta * ep)))
SPECIMEN = {
    'name': 'DP1000',
    'E_MPa': 195000.0, 'nu': 0.33, 'rho_kg_m3': 7850.0,
    'A': 1395.0, 'e0': 1.0e-6, 'n': 0.0892,        # Swift
    'k0': 739.0, 'Q': 301.0, 'beta': 102.0,        # Voce
    'a_SV': 0.5,                                   # ponderation Swift / Voce
}

# Tabulation de la courbe d'ecrouissage pour *Plastic
EP_MAX = 2.0       # deformation plastique max tabulee (au-dela, Abaqus garde la derniere valeur)
N_POINTS = 80      # nombre de points (espaces de facon logarithmique)
EP_MIN = 1.0e-6    # premier point non nul (Swift avec e0 = 1e-6 monte tres vite au debut)

# ============================================================
# CHEMINS
# ============================================================
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
OUT_DIR = os.path.join(PROJECT_ROOT, 'model', 'materials')


# ============================================================
# FONCTIONS
# ============================================================
def rho_t_mm3(rho_kg_m3):
    """kg/m^3 -> t/mm^3."""
    return rho_kg_m3 * 1.0e-12


def young_from_wave_speed(rho_kg_m3, c_m_s):
    """E = rho * c^2, renvoye en MPa."""
    return rho_kg_m3 * c_m_s ** 2 / 1.0e6


def swift_voce(ep, p):
    """Contrainte d'ecoulement [MPa] pour une deformation plastique ep."""
    swift = p['A'] * (ep + p['e0']) ** p['n']
    voce = p['k0'] + p['Q'] * (1.0 - math.exp(-p['beta'] * ep))
    return p['a_SV'] * swift + (1.0 - p['a_SV']) * voce


def plastic_strains(ep_min, ep_max, n_points):
    """0, puis des points espaces logarithmiquement de ep_min a ep_max."""
    lo, hi = math.log10(ep_min), math.log10(ep_max)
    return [0.0] + [10 ** (lo + (hi - lo) * i / (n_points - 2)) for i in range(n_points - 1)]


def header(lines):
    return ['** ' + l for l in lines] + ['**']


def write(name, lines):
    path = os.path.join(OUT_DIR, name + '.dat')
    with open(path, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    print('ecrit : ' + os.path.relpath(path, PROJECT_ROOT))


# ============================================================
# GENERATION
# ============================================================
os.makedirs(OUT_DIR, exist_ok=True)

# --- Materiaux elastiques ---
for name, p in ELASTIC.items():
    E = young_from_wave_speed(p['rho_kg_m3'], p['c_m_s'])
    lines = header([
        'Materiau ' + name + ' -- genere par scripts/pre/make_materials.py, NE PAS EDITER A LA MAIN',
        'Elastique lineaire. E = rho * c^2 avec c = %.0f m/s (vitesse des ondes mesuree)' % p['c_m_s'],
        'rho = %.0f kg/m^3, E = %.0f MPa, nu = %.2f' % (p['rho_kg_m3'], E, p['nu']),
        'Unites : mm, N, s, MPa, t/mm^3',
    ])
    lines += ['*Density', '%.4e,' % rho_t_mm3(p['rho_kg_m3']),
              '*Elastic', '%.1f, %.3f' % (E, p['nu'])]
    write(name, lines)

# --- Eprouvette ---
p = SPECIMEN
eps = plastic_strains(EP_MIN, EP_MAX, N_POINTS)
lines = header([
    'Materiau ' + p['name'] + ' -- genere par scripts/pre/make_materials.py, NE PAS EDITER A LA MAIN',
    'Source : Beerli et al. (2026), Int. J. Impact Eng. 215, 105761, tableau 4',
    'J2 (von Mises), ecrouissage isotrope Swift-Voce, independant de la vitesse',
    'Swift : A = %g MPa, e0 = %g, n = %g' % (p['A'], p['e0'], p['n']),
    'Voce  : k0 = %g MPa, Q = %g MPa, beta = %g' % (p['k0'], p['Q'], p['beta']),
    'a_SV = %g' % p['a_SV'],
    'Colonnes *Plastic : contrainte vraie [MPa], deformation plastique vraie [-]',
    'Unites : mm, N, s, MPa, t/mm^3',
])
lines += ['*Density', '%.4e,' % rho_t_mm3(p['rho_kg_m3']),
          '*Elastic', '%.1f, %.3f' % (p['E_MPa'], p['nu']),
          '*Plastic']
lines += ['%10.3f, %.6e' % (swift_voce(ep, p), ep) for ep in eps]
write(p['name'], lines)

print('Controle %s : k(0) = %.1f MPa, k(0.002) = %.1f MPa, k(0.1) = %.1f MPa, k(1) = %.1f MPa'
      % (p['name'], swift_voce(0.0, p), swift_voce(0.002, p), swift_voce(0.1, p), swift_voce(1.0, p)))
