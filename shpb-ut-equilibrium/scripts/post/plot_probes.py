# -*- coding: utf-8 -*-
"""
plot_probes.py -- Ou naissent les oscillations de la jauge de sortie ?

Pour un calcul avec sondes (probes = 1 dans cases.csv), trace la force a chaque endroit du chemin
eprouvette -> tete de la barre de sortie -> collage -> barre -> jauge, chaque courbe comparee a la
vraie force dans l'eprouvette (section SEC_OUT). Les signaux sont filtres a 100 kHz et decales du temps
de trajet de l'onde jusqu'a la sonde la plus proche de l'eprouvette (HEAD_MID).

Lancement (PC, Python 3), racine du repo :
    python shpb-ut-equilibrium/scripts/post/plot_probes.py shpb-ut-equilibrium/results/<etude>/<calcul>
Sortie : <calcul>_probes.png dans le dossier du calcul (+ resume a l'ecran)
"""
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                # noqa: E402
import pandas as pd               # noqa: E402
from scipy.signal import butter, filtfilt  # noqa: E402

C_BAR = 4871.0e3                  # mm/s
A_BAR = np.pi * 10.0 ** 2         # mm2
ORDER = ['HEAD_MID', 'HEAD_TIE', 'BAR_TIE', 'BAR_100', 'BAR_250', 'GAUGE_OUT']
TITLES = {'HEAD_MID': 'output head, between pocket and tie', 'HEAD_TIE': 'output head, just above the tie',
          'BAR_TIE': 'output bar, just below the tie', 'BAR_100': 'output bar, 100 mm from its end',
          'BAR_250': 'output bar, 250 mm from its end', 'GAUGE_OUT': 'output bar gauge (400 mm)'}


def main():
    case_dir = os.path.abspath(sys.argv[1])
    case = os.path.basename(case_dir.rstrip(os.sep))
    csv = os.path.join(case_dir, case + '_history.csv')
    ys = {}
    for line in open(csv):
        if not line.startswith('#'):
            break
        if 'sondes' in line:
            ys = dict((k, float(v)) for k, v in re.findall(r'([A-Z0-9_]+)=([-0-9.]+)', line))
    if not ys:
        sys.exit('Pas de sondes dans %s (calcul lance sans probes = 1 ?)' % csv)
    d = pd.read_csv(csv, comment='#')
    t = d.time_s.values
    b, a = butter(4, 100e3 / (0.5 / np.median(np.diff(t))))
    lp = lambda x: filtfilt(b, a, x)
    ref = lp(d.F_sec_out_N.values)
    sig = {k: lp(d['F_probe_%s_N' % k].values) for k in ORDER if 'F_probe_%s_N' % k in d}
    sig['GAUGE_OUT'] = lp(d.sig_gauge_out.values * A_BAR)
    y0 = ys['HEAD_MID']
    k0 = int(np.argmax(ref > 0.02 * ref.max()))
    ex = lp(d.eps_ext.values)
    i_end = int(np.argmax(ex >= 0.30)) if (ex >= 0.30).any() else int(np.argmax(ex))
    tt = 1e3 * (t - t[k0])
    m = (tt > -0.03) & (tt <= tt[i_end])
    win = (np.arange(len(t)) >= k0) & (np.arange(len(t)) <= i_end) & (ex >= 0.05)
    fmax = ref[win].max()
    keys = [k for k in ORDER if k in sig]
    fig, axs = plt.subplots(len(keys), 1, figsize=(8, 1.9 * len(keys) + 0.6), sharex=True, sharey=True)
    print('%s : ecart max a la vraie force (apres 5 %% de deformation), en %% de la force max' % case)
    for ax, k in zip(axs, keys):
        shifted = np.interp(t + (y0 - ys[k]) / C_BAR, t, sig[k], right=np.nan)
        err = np.nanmax(np.abs(shifted[win] - ref[win])) / fmax
        ax.plot(tt[m], ref[m] / 1e3, color='#9a9994', lw=3.0, label='true force in the specimen')
        ax.plot(tt[m], shifted[m] / 1e3, color='#2a78d6', lw=1.2, label='force at this position')
        ax.set_title('%s (Y = %.0f mm) - error %.0f %%' % (TITLES[k], ys[k], 100 * err), loc='left', fontsize=9)
        ax.grid(True, color='#e3e2de', lw=0.6)
        for s_ in ('top', 'right'):
            ax.spines[s_].set_visible(False)
        print('  %-10s Y = %8.1f mm   %5.1f %%' % (k, ys[k], 100 * err))
    axs[0].legend(fontsize=7, frameon=False, loc='upper right')
    axs[-1].set_xlabel('time from loading start (ms), each signal shifted by its wave travel time')
    for ax in axs:
        ax.set_ylabel('force (kN)', fontsize=8)
    fig.suptitle('%s - force along the output side' % case, fontsize=10)
    fig.tight_layout()
    out = os.path.join(case_dir, case + '_probes.png')
    fig.savefig(out, dpi=140)
    print('Figure : ' + out)


if __name__ == '__main__':
    main()
