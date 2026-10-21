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

Trace aussi la courbe d'ecrouissage de l'eprouvette dans docs/figures/DP1000_hardening.png
(si matplotlib est installe). Explications : docs/materials.md.
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
# Points EQUIDISTANTS : Abaqus/Explicit "regularise" les tables (il les re-echantillonne
# a pas constant, egal au plus petit intervalle donne). Avec des points en echelle log
# (plus petit intervalle 1e-6 sur une plage de 2), il faudrait 2 millions d'intervalles :
# erreur "Failed to regularize material data". Pas constant de 0,005 -> 400 intervalles.
EP_MAX = 2.0       # deformation plastique max tabulee (au-dela, Abaqus garde la derniere valeur)
EP_STEP = 0.005    # pas de la table

# ============================================================
# CHEMINS
# ============================================================
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
OUT_DIR = os.path.join(PROJECT_ROOT, 'model', 'materials')
FIG_DIR = os.path.join(PROJECT_ROOT, 'docs', 'figures')


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


def plastic_strains(ep_step, ep_max):
    """0, ep_step, 2*ep_step, ... jusqu'a ep_max (pas constant)."""
    n = int(round(ep_max / ep_step))
    return [i * ep_step for i in range(n + 1)]


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
eps = plastic_strains(EP_STEP, EP_MAX)
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


# ============================================================
# FIGURE : courbe d'ecrouissage (docs/materials.md)
# ============================================================
def considere(p):
    """Debut de la striction en traction (critere de Considere : dk/dep = k), par dichotomie."""
    lo, hi, h = 1.0e-4, 1.0, 1.0e-7
    f = lambda e: (swift_voce(e + h, p) - swift_voce(e - h, p)) / (2 * h) - swift_voce(e, p)
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
    return lo


def plot_hardening(p, eps_table):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('matplotlib absent : pas de figure')
        return
    os.makedirs(FIG_DIR, exist_ok=True)
    e_c = considere(p)
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.6))
    for k, (ax, emax) in enumerate(zip(axs, (1.0, 0.03))):
        e = [emax * i / 2000.0 for i in range(2001)]
        sw = [p['A'] * (x + p['e0']) ** p['n'] for x in e]
        vo = [p['k0'] + p['Q'] * (1.0 - math.exp(-p['beta'] * x)) for x in e]
        ax.plot(e, sw, color='#2a78d6', lw=1.0, ls='--', label='Swift  $A(\\varepsilon_p+\\varepsilon_0)^n$')
        ax.plot(e, vo, color='#eb6834', lw=1.0, ls='--', label='Voce  $k_0+Q(1-e^{-\\beta\\varepsilon_p})$')
        ax.plot(e, [swift_voce(x, p) for x in e], color='#1f1f1d', lw=1.6,
                label='Swift-Voce, $\\alpha_{SV}$ = %g' % p['a_SV'])
        tab = [x for x in eps_table if x <= emax]
        if k == 0:                              # vue d'ensemble : un point sur 10 de la table
            tab = tab[::10]
            ax.axvline(e_c, color='#6b6b6b', lw=0.8, ls=':')
            ax.text(e_c, 420, ' necking (Considere)\n $\\varepsilon_p$ = %.3f' % e_c, fontsize=7, color='#52514e')
        else:                                   # zoom : premier intervalle de la table, rectiligne
            ax.annotate('first interval of the table:\nstraight line %.0f -> %.0f MPa' %
                        (swift_voce(0.0, p), swift_voce(EP_STEP, p)),
                        xy=(0.0025, 0.5 * (swift_voce(0.0, p) + swift_voce(EP_STEP, p))), xytext=(0.008, 620),
                        fontsize=7, color='#52514e', arrowprops=dict(arrowstyle='->', color='#6b6b6b', lw=0.7))
        ax.plot(tab, [swift_voce(x, p) for x in tab], 'o', color='#1baf7a', ms=3, zorder=3,
                label='points of the *Plastic table' + (' (1 in 10)' if k == 0 else ''))
        ax.set_xlim(0, emax)
        ax.set_ylim(400, 1450)
        ax.set_xlabel('true plastic strain $\\varepsilon_p$ (-)')
        ax.set_ylabel('flow stress $k$ (MPa)')
        ax.set_title('%s, %s' % (p['name'], 'whole table' if k == 0 else 'zoom on the start'), loc='left', fontsize=10)
        ax.grid(True, color='#e3e2de', lw=0.6)
        for side in ('top', 'right'):
            ax.spines[side].set_visible(False)
    axs[0].legend(loc='lower right', fontsize=7, frameon=False)
    axs[1].plot([0.0, EP_STEP], [swift_voce(0.0, p), swift_voce(EP_STEP, p)], color='#1baf7a', lw=0.8)
    fig.tight_layout()
    path = os.path.join(FIG_DIR, p['name'] + '_hardening.png')
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print('figure : ' + os.path.relpath(path, PROJECT_ROOT))
    print('Striction (Considere) : ep = %.4f, k = %.0f MPa -> deformation nominale %.1f %%, contrainte nominale %.0f MPa'
          % (e_c, swift_voce(e_c, p), 100 * (math.exp(e_c) - 1), swift_voce(e_c, p) / math.exp(e_c)))


plot_hardening(p, eps)
