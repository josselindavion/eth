# -*- coding: utf-8 -*-
"""
compare_studies.py -- Compare deux etudes calcul par calcul (meme eprouvette, meme vitesse visee).
Cree pour comparer l'ancien placement (eprouvette centree, jeux de 0,36 mm) et le nouveau
(dents au contact des deux logements, CLOSE_GAPS de build_bench.py, 22/10/2026).

Lancement (PC, Python 3), depuis la racine du repo :
    py shpb-ut-equilibrium/scripts/post/compare_studies.py <etude_avant> <etude_apres> [nom_avant] [nom_apres]
Exemple :
    py shpb-ut-equilibrium/scripts/post/compare_studies.py shpb-ut-equilibrium/results/taskI_20261013-1554 ^
       shpb-ut-equilibrium/results/taskI_20261022-1138 "centred (gaps)" "in contact"

Les calculs sont apparies par (eprouvette, vitesse visee) : UT19_R1000_00 et UT19_R1000_P1 sont compares.
Traitement : exactement celui du rapport (fonction analyse de report_taskI.py : filtre 100 kHz,
jauge decalee de 82 us, R, indicateurs). Voir docs/results.md.

Sorties dans <etude_apres>/compare_<etude_avant>/ :
    compare.md                 texte (anglais) : tableau avant / apres et explication des figures
    C1_gauge_vs_true.png/pdf   force lue par la jauge contre vraie force de l'eprouvette, avant et apres
    C2_equilibrium.png/pdf     R = (F_in - F_out) / F_moy contre la deformation, avant et apres
    C3_start.png/pdf           debut du chargement (signaux bruts) : force dans l'eprouvette, avant et apres
"""
import glob
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_taskI as rep               # noqa: E402

GREY = '#9a9994'
INK2 = '#52514e'
START_US = 150.0                         # duree montree sur C3 (us apres le debut du chargement)


def load(study_dir):
    out = {}
    for csv in sorted(glob.glob(os.path.join(study_dir, '*', '*_history.csv'))):
        r, c = rep.analyse(csv)
        out[(r['specimen'], int(r['target_rate']))] = (r, c)
    return out


def axes(nrow, ncol, w=3.6, h=2.7):
    fig, axs = plt.subplots(nrow, ncol, figsize=(w * ncol + 0.3, h * nrow + 0.5), squeeze=False)
    for ax in axs.flat:
        ax.grid(True, color=rep.GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
    return fig, axs


def save(fig, out, name, rect=(0, 0, 1, 1)):
    fig.tight_layout(rect=rect)
    for ext in ('pdf', 'png'):
        fig.savefig(os.path.join(out, '%s.%s' % (name, ext)), dpi=200)
    plt.close(fig)


def fig_gauge(pairs, names, out):
    """Ligne 1 : avant, ligne 2 : apres. Gris epais = vraie force, couleur = jauge."""
    fig, axs = axes(2, len(pairs))
    for j, (key, col, (ra, ca), (rb, cb)) in enumerate(pairs):
        for i, (r, c, nm) in enumerate(((ra, ca, names[0]), (rb, cb, names[1]))):
            ax = axs[i, j]
            m = c['win']
            ax.plot(100 * c['eps'][m], c['Fo'][m] / 1e3, color=GREY, lw=3.0,
                    label='true force in the specimen (simulation only)')
            ax.plot(100 * c['eps'][m], c['Fg'][m] / 1e3, color=col, lw=1.2,
                    label='force read by the output gauge (measured in the test; one colour per rate)')
            ax.set_xlim(0, 32)
            ax.set_title('%s, %d s$^{-1}$, %s\nmax gauge error after 5 %%: %.0f %%'
                         % (key[0], key[1], nm, 100 * r['gauge_err_after5']), loc='left', fontsize=8.5)
            ax.set_xlabel('engineering strain (%)', fontsize=8)
            ax.set_ylabel('force (kN)', fontsize=8)
    top = max(np.nanmax(c['Fg'][c['win']]) for _, _, (_, ca), (_, cb) in pairs for c in (ca, cb)) / 1e3
    for ax in axs.flat:
        ax.set_ylim(-1.0, 1.05 * max(top, 8.0))       # meme echelle partout : on compare les amplitudes
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc='upper center', ncol=2, frameon=False, fontsize=8)
    save(fig, out, 'C1_gauge_vs_true', rect=(0, 0, 1, 0.94))


def fig_eq(pairs, names, out):
    fig, axs = axes(1, len(pairs))
    for ax, (key, col, (ra, ca), (rb, cb)) in zip(axs[0], pairs):
        ax.axhspan(-100 * rep.EQ_TOL, 100 * rep.EQ_TOL, color=rep.BAND, zorder=0)
        for r, c, cl, lw, nm in ((ra, ca, GREY, 2.4, names[0]), (rb, cb, col, 1.3, names[1])):
            m = c['valid']
            ax.plot(100 * c['eps'][m], 100 * c['R'][m], color=cl, lw=lw, label=nm)
        ax.set_ylim(-20, 20)
        ax.set_xlim(0, 32)
        ax.set_title('%s, %d s$^{-1}$' % key, loc='left', fontsize=9)
        ax.set_xlabel('engineering strain (%)', fontsize=8)
        ax.set_ylabel('R = (F$_{in}$ - F$_{out}$) / F$_{mean}$ (%)', fontsize=8)
        ax.legend(fontsize=7.5, frameon=False, loc='upper right')
    save(fig, out, 'C2_equilibrium')


def fig_start(pairs, names, out):
    fig, axs = axes(1, len(pairs))
    for ax, (key, col, (ra, ca), (rb, cb)) in zip(axs[0], pairs):
        for r, c, cl, lw, nm in ((ra, ca, GREY, 2.4, names[0]), (rb, cb, col, 1.3, names[1])):
            t_us = 1e3 * c['t_ms']
            m = (t_us > -10) & (t_us < START_US)
            ax.plot(t_us[m], c['Fo_raw'][m] / 1e3, color=cl, lw=lw, label=nm)
        ax.set_title('%s, %d s$^{-1}$' % key, loc='left', fontsize=9)
        ax.set_xlabel('time from the start of loading (µs)', fontsize=8)
        ax.set_ylabel('force in the specimen, F$_{out}$ (kN, unfiltered)', fontsize=8)
        ax.legend(fontsize=7.5, frameon=False, loc='lower right')
    save(fig, out, 'C3_start')


def pct(x):
    return '–' if x is None or not np.isfinite(x) else '%.1f %%' % (100 * x)


def num(x, f):
    return '–' if x is None or not np.isfinite(x) else f % x


def write_md(pairs, names, studies, out):
    L = ['# Comparison: %s vs %s' % (studies[0], studies[1]), '',
         '- **%s**: study `%s`' % (names[0], studies[0]),
         '- **%s**: study `%s`' % (names[1], studies[1]), '',
         'Runs are paired by specimen and target strain rate. Both are processed exactly like the Task I report '
         '(100 kHz low-pass filter, output gauge shifted by 82 µs, equilibrium criterion |R| < 5 %; see '
         '`docs/results.md`).', '']
    rows = [('equilibrium from strain', lambda r: pct(r['eps_eq'])),
            ('max \\|R\\| after 5 % strain', lambda r: pct(r['R_max_after5'])),
            ('max \\|ΔF\\| after 5 % strain', lambda r: num(r['dF_max_after5_kN'], '%.2f kN')),
            ('max gauge error after 5 % strain', lambda r: pct(r['gauge_err_after5'])),
            ('achieved strain rate', lambda r: num(r['achieved_rate'], '%.0f s⁻¹')),
            ('max force', lambda r: num(r['F_max_kN'], '%.2f kN')),
            ('time to 30 % strain', lambda r: num(r['time_to_30_ms'], '%.3f ms')),
            ('max strain', lambda r: pct(r['eps_max']))]
    for key, col, (ra, ca), (rb, cb) in pairs:
        L += ['## %s at %d s⁻¹' % key, '', '| Indicator | %s | %s |' % names, '|---|---|---|']
        for lab, f in rows:
            L.append('| %s | %s | %s |' % (lab, f(ra), f(rb)))
        L.append('')
    L += ['## Figures', '',
          '![C1](C1_gauge_vs_true.png)', '',
          '*C1 – Force against strain. Grey thick line: true force in the specimen (cross-section of the gauge '
          'section, available only in the simulation). Coloured line: force read on the output-bar gauge, i.e. '
          'what the test measures. Top row: %s; bottom row: %s. The closer the two lines, the more reliable the '
          'measured curve.*' % names, '',
          '![C2](C2_equilibrium.png)', '',
          '*C2 – Force equilibrium of the specimen: R = (F_in − F_out) / F_mean against strain. Shaded band: '
          '|R| < 5 %%. Grey thick line: %s; coloured line: %s.*' % names, '',
          '![C3](C3_start.png)', '',
          '*C3 – First %.0f µs of loading, unfiltered: force in the specimen at the output side. Grey thick '
          'line: %s; coloured line: %s. Time 0 = the input-side force F_in reaches 2 %% of its maximum, in each run.*'
          % ((START_US,) + names), '']
    open(os.path.join(out, 'compare.md'), 'w', encoding='utf-8').write('\n'.join(L))


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    da, db = [os.path.abspath(p.rstrip('/\\')) for p in sys.argv[1:3]]
    names = (sys.argv[3] if len(sys.argv) > 3 else 'before', sys.argv[4] if len(sys.argv) > 4 else 'after')
    sa, sb = os.path.basename(da), os.path.basename(db)
    A, B = load(da), load(db)
    keys = sorted(set(A) & set(B))
    if not keys:
        sys.exit('Aucun calcul commun (meme eprouvette et meme vitesse) entre %s et %s' % (sa, sb))
    out = os.path.join(db, 'compare_' + sa)
    os.makedirs(out, exist_ok=True)
    pairs = [(k, rep.RATE_COLORS[i % len(rep.RATE_COLORS)], A[k], B[k]) for i, k in enumerate(keys)]
    fig_gauge(pairs, names, out)
    fig_eq(pairs, names, out)
    fig_start(pairs, names, out)
    write_md(pairs, names, (sa, sb), out)
    print('%-12s %-16s %10s %10s %10s %10s' % ('calcul', '', 'equilibre', '|R| max', 'jauge', 'vitesse'))
    for key, col, (ra, ca), (rb, cb) in pairs:
        for r, nm in ((ra, names[0]), (rb, names[1])):
            print('%-12s %-16s %10s %10s %10s %8.0f/s' % ('%s_%d' % key, nm[:16], pct(r['eps_eq']),
                  pct(r['R_max_after5']), pct(r['gauge_err_after5']), r['achieved_rate']))
    print('Comparaison : ' + out)


if __name__ == '__main__':
    main()
