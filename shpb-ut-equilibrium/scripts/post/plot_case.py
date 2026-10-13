# -*- coding: utf-8 -*-
"""
plot_case.py -- Trace les courbes d'un ou plusieurs calculs a partir de <case>_history.csv
(sortie de extract_history.py) et calcule les grandeurs de la Task I.

Lancement (Python 3 + numpy, pandas, matplotlib), depuis la racine du repo :
    python shpb-ut-equilibrium/scripts/post/plot_case.py shpb-ut-equilibrium/runs/_submit/taskI_20261013-1127
    python shpb-ut-equilibrium/scripts/post/plot_case.py chemin/vers/UT19_R0500_00_history.csv

Sorties, a cote de chaque CSV :
    <case>_overview.png   4 graphes : jauges des barres ; forces dans l'eprouvette ;
                          desequilibre des forces ; deformation de l'extensometre
Et, si on donne un dossier d'etude : <etude>_summary.csv (une ligne par calcul).

Grandeurs calculees (voir docs/results.md) :
    t_load_ms      debut du chargement de l'eprouvette (|F_sec_in| > 2 % du max)
    rate_mean      vitesse de deformation moyenne de l'extensometre (de 0,5 % a 25 %)
    t30_ms         instant ou la deformation de l'extensometre atteint 30 % (vide si jamais)
    eps_max        deformation maximale de l'extensometre dans la fenetre utile
                   (fenetre utile : du debut du chargement a 30 %, ou a la deformation max)
    t_eq_ms        premier instant a partir duquel |F_in - F_out| / F_moyen reste < 5 %
                   jusqu'a la fin de la fenetre utile ; dt_eq_ms = t_eq_ms - t_load_ms
    dF_rms_pct     ecart moyen (rms) |F_in - F_out| / F_moyen ensuite, en %
    F_max_kN       force maximale dans l'eprouvette (section SEC_IN)
    hourglass_pct  ALLAE / ALLIE a la fin (doit rester petit, < ~5 %)
"""
import glob
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                # noqa: E402
import pandas as pd               # noqa: E402

BAR_AREA_MM2 = np.pi * 10.0 ** 2      # barres de diametre 20 mm (section complete)
EQ_TOL = 0.05                         # seuil d'equilibre : 5 %
COL = {'in': '#2a78d6', 'out': '#eb6834', 'bar': '#1baf7a', 'ref': '#6b6b6b'}


def analyse(d):
    t = d.time_s.values * 1e3                                  # ms
    Fi, Fo = d.F_sec_in_N.values, d.F_sec_out_N.values
    ex = d.eps_ext.values
    res = {}
    k0 = np.argmax(np.abs(Fi) > 0.02 * np.abs(Fi).max())
    res['t_load_ms'] = t[k0]
    # fin de la fenetre utile : 30 % atteints, sinon deformation maximale (fin de l'impulsion)
    i30 = np.argmax(ex >= 0.30) if (ex >= 0.30).any() else None
    i_end = i30 if i30 is not None else int(np.argmax(ex))
    res['t30_ms'] = t[i30] if i30 is not None else np.nan
    res['eps_max'] = ex[:i_end + 1].max()
    # vitesse de deformation : de 0,5 % (sortie de l'elastique) a min(25 %, 80 % du max atteint)
    rate = np.gradient(ex, d.time_s.values)
    hi = min(0.25, 0.8 * res['eps_max'])
    m = (ex > 0.005) & (ex < hi)
    m[i_end + 1:] = False
    res['rate_mean'] = rate[m].mean() if m.any() else np.nan
    # equilibre : premier instant a partir duquel |F_in - F_out| / F_moyen < 5 % jusqu'a la fin
    # de la fenetre utile (on ignore les instants ou la force est < 10 % de son max)
    Fm = 0.5 * (Fi + Fo)
    big = np.abs(Fm) > 0.1 * np.abs(Fm[:i_end + 1]).max()
    dF = np.abs(Fi - Fo) / np.maximum(np.abs(Fm), 1e-9)
    ok = (dF < EQ_TOL) | ~big
    t_eq, i_eq = np.nan, None
    for i in range(k0, i_end + 1):
        if big[i] and ok[i:i_end + 1].all():
            t_eq, i_eq = t[i], i
            break
    res['t_eq_ms'] = t_eq
    res['dt_eq_ms'] = t_eq - res['t_load_ms']
    w = slice(i_eq, i_end + 1) if i_eq is not None else slice(0, 0)
    sel = big[w]
    res['dF_rms_pct'] = 100 * np.sqrt(np.mean(dF[w][sel] ** 2)) if sel.any() else np.nan
    res['F_max_kN'] = np.abs(Fi).max() / 1e3
    res['hourglass_pct'] = 100 * d.ALLAE_mJ.iloc[-1] / max(d.ALLIE_mJ.iloc[-1], 1e-12)
    res['t_end_ms'] = t[i_end]
    return res


def plot(d, res, case, png):
    t = d.time_s.values * 1e3
    fig, ax = plt.subplots(4, 1, figsize=(9, 11), sharex=True)
    for a in ax:
        a.grid(True, color='#e3e2de', linewidth=0.6)
        for s in ('top', 'right'):
            a.spines[s].set_visible(False)

    ax[0].plot(t, 1e3 * d.eps_gauge_in, color=COL['in'], lw=1.5, label='jauge entree (400 mm)')
    ax[0].plot(t, 1e3 * d.eps_gauge_out, color=COL['out'], lw=1.5, label='jauge sortie')
    ax[0].set_ylabel('deformation barre (x1e-3)')
    ax[0].legend(frameon=False, loc='lower right')

    ax[1].plot(t, d.F_sec_in_N / 1e3, color=COL['in'], lw=1.5, label='section SEC_IN (cote pusher)')
    ax[1].plot(t, d.F_sec_out_N / 1e3, color=COL['out'], lw=1.5, ls='--', label='section SEC_OUT (cote sortie)')
    ax[1].plot(t, d.sig_gauge_out * BAR_AREA_MM2 / 1e3, color=COL['bar'], lw=1.2,
               label='barre de sortie (S22 x aire)')
    ax[1].set_ylabel('force (kN)')
    ax[1].legend(frameon=False, loc='lower right')

    Fi, Fo = d.F_sec_in_N.values, d.F_sec_out_N.values
    Fm = 0.5 * (Fi + Fo)
    valid = np.abs(Fi) > 0.1 * np.abs(Fi).max()
    dF = np.where(valid, 100 * (Fi - Fo) / np.where(valid, Fm, 1.0), np.nan)
    ax[2].plot(t, dF, color=COL['in'], lw=1.2)
    for y in (-100 * EQ_TOL, 100 * EQ_TOL):
        ax[2].axhline(y, color=COL['ref'], lw=0.8, ls=':')
    ax[2].set_ylim(-30, 30)
    ax[2].set_ylabel('(F_in - F_out) / F moyen (%)')
    ax[2].text(0.01, 0.9, 'pointilles : +/- %d %%' % round(100 * EQ_TOL), transform=ax[2].transAxes,
               color='#4a4a48', fontsize=9)

    ax[3].plot(t, 100 * d.eps_ext, color=COL['in'], lw=1.5)
    ax[3].axhline(30, color=COL['ref'], lw=0.8, ls=':')
    if not np.isnan(res['t30_ms']):
        ax[3].axvline(res['t30_ms'], color=COL['ref'], lw=0.8, ls=':')
    ax[3].set_ylim(0, max(40, min(100, 100 * res['eps_max'] * 1.05)))
    ax[3].set_ylabel('deformation extensometre (%)')
    ax[3].set_xlabel('temps (ms)')

    fig.suptitle('%s : %.0f /s ; 30 %% a %s ms ; equilibre (< 5 %%) %s ms apres le debut de charge'
                 % (case, res['rate_mean'],
                    '%.3f' % res['t30_ms'] if not np.isnan(res['t30_ms']) else 'jamais',
                    '%.3f' % res['dt_eq_ms'] if not np.isnan(res['dt_eq_ms']) else '-'), fontsize=11)
    for a in ax:
        a.axvspan(res['t_load_ms'], res['t_end_ms'], color='#f2f1ed', zorder=0)
    fig.tight_layout()
    fig.savefig(png, dpi=130)
    plt.close(fig)


def main():
    target = sys.argv[1]
    if os.path.isdir(target):
        csvs = sorted(glob.glob(os.path.join(target, '*', '*_history.csv')))
    else:
        csvs = [target]
    rows = []
    for c in csvs:
        case = os.path.basename(c).replace('_history.csv', '')
        d = pd.read_csv(c, comment='#')
        res = analyse(d)
        plot(d, res, case, c.replace('_history.csv', '_overview.png'))
        res['case_id'] = case
        rows.append(res)
        print('%-15s charge a %.3f ms | %4.0f /s | 30 %% a %s ms | eps max %.3f | equilibre (< 5 %%) '
              '%s ms apres la charge, ecart rms ensuite %.1f %% | F max %.2f kN | hourglass %.1f %%'
              % (case, res['t_load_ms'], res['rate_mean'],
                 '%.3f' % res['t30_ms'] if not np.isnan(res['t30_ms']) else 'jamais',
                 res['eps_max'], '%.3f' % res['dt_eq_ms'] if not np.isnan(res['dt_eq_ms']) else '-',
                 res['dF_rms_pct'], res['F_max_kN'], res['hourglass_pct']))
    if os.path.isdir(target) and rows:
        out = os.path.join(target, os.path.basename(os.path.normpath(target)) + '_summary.csv')
        cols = ['case_id', 't_load_ms', 'rate_mean', 't30_ms', 'eps_max', 't_eq_ms', 'dt_eq_ms',
                'dF_rms_pct', 'F_max_kN', 'hourglass_pct']
        pd.DataFrame(rows)[cols].to_csv(out, index=False, float_format='%.4g')
        print('Resume : ' + out)


if __name__ == '__main__':
    main()
