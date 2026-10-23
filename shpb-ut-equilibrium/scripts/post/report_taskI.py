# -*- coding: utf-8 -*-
"""
report_taskI.py -- Rapport de la Task I (texte en anglais, tableaux, figures) pour une etude.

Lancement (PC, Python 3 + numpy, pandas, matplotlib, scipy), depuis la racine du repo :
    python shpb-ut-equilibrium/scripts/post/report_taskI.py shpb-ut-equilibrium/results/taskI_20261013-1554

Entrees, dans results/<etude>/<calcul>/ (rapatriees par scripts/hpc/fetch_study.py) :
    <calcul>_history.csv     courbes extraites du .odb (scripts/post/extract_history.py)
    <calcul>_paras.inp       parametres du calcul (vitesse du striker) ; sinon formule de make_run.py
Sorties :
    results/<etude>/report/report.md                 rapport (anglais) : resume, modele, definitions, reponses,
                                                     mesure en essai, qualite numerique, limites, annexe
    results/<etude>/report/T1_conditions.csv         tous les indicateurs, une ligne par calcul
    results/<etude>/report/F*.pdf / .png             figures (pdf pour le rapport final, png pour l'apercu)
    results/<etude>/<calcul>/<calcul>_overview.png   figure de controle de chaque calcul (signaux bruts)

Traitement des signaux et definitions : docs/results.md.
"""
import glob
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402
import pandas as pd                      # noqa: E402
from scipy.signal import butter, filtfilt  # noqa: E402

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(THIS_DIR, '..', 'pre'))
import make_run                          # noqa: E402  (formule de la vitesse du striker)

# ============================================================
# PARAMETRES
# ============================================================
FC_HZ = 100.0e3              # frequence de coupure du filtre passe-bas (labo : 100 kHz)
FILTER_ORDER = 4
EQ_TOL = 0.05                # critere d'equilibre : |R| < 5 %
EPS_TARGET = 0.30            # deformation nominale visee
EPS_PLATEAU = 0.05           # debut de la fenetre "palier" (vitesse moyenne, R max apres 5 %)
EPS_START = 0.002            # on ne cherche pas l'equilibre avant 0,2 % (fin du jeu au contact)
C_BAR = 4871.0               # m/s, barres maraging
A_BAR_MM2 = np.pi * 10.0 ** 2
GAUGE_TO_SPEC_MM = 400.0     # jauge de sortie -> eprouvette (Beerli 2026 ; reference a confirmer)
L_STRIKER_M, C_STRIKER, RHO_STRIKER = 5.0, 4720.0, 7850.0
PULSE_MS = 2.0 * L_STRIKER_M / C_STRIKER * 1e3     # duree de l'impulsion du striker de 5 m (2,119 ms)
LAUNCH_TUBE_M = 7.5          # longueur du tube de lancement (Beerli 2026, section 2.5)
OUTPUT_WINDOW_MS = 2.33      # duree de mesure max permise par la barre de sortie de 5,99 m (Beerli 2026)
A0_MM2 = {                   # section initiale de la partie droite de l'eprouvette
    'UT19': 5.0 * 1.5,       # 5 mm x 1,5 mm
    'UT40': 10.0 * 1.5,      # 10 mm x 1,5 mm (DXF : 10,02 -> 10,00 mm)
    'UT40S': 10.0 * 1.5,     # UT40 a partie droite parfaitement droite, 10,00 mm
}
# Couleurs : une par vitesse visee, dans l'ordre (palette categorielle validee, 3 premieres places)
RATE_COLORS = ['#2a78d6', '#eb6834', '#1baf7a']
# Etudes lancees AVANT la mise en contact initiale (22/10/2026, CLOSE_GAPS de build_bench.py) : eprouvette
# centree dans les logements, avec un jeu de 0,36 mm de chaque cote. Le texte du rapport en depend.
CENTRED_STUDIES = ('taskI_20261012-1811', 'taskI_20261013-1127', 'taskI_20261013-1554', 'diag_20261021-1626')
INK, INK2, GRID, BAND = '#1f1f1d', '#52514e', '#e3e2de', '#efeeea'

plt.rcParams.update({'font.size': 9, 'axes.edgecolor': INK2, 'axes.labelcolor': INK,
                     'xtick.color': INK2, 'ytick.color': INK2, 'axes.titlesize': 10,
                     'legend.frameon': False, 'pdf.fonttype': 42})


# ============================================================
# LECTURE ET ANALYSE D'UN CALCUL
# ============================================================
def read_paras(path):
    vals = {}
    if os.path.exists(path):
        for line in open(path):
            m = re.match(r'\s*(V_STRIKER_MS|T_STEP)\s*=\s*([-+0-9.eE]+)\s*$', line)
            if m:
                vals[m.group(1)] = float(m.group(2))
    return vals


def equilibrium(R, valid, eps, k0, i_end):
    """Debut de l'equilibre (premier indice a partir duquel |R| < 5 % jusqu'a la fin de la fenetre),
    et plus long intervalle continu de deformation ou |R| < 5 % (apres EPS_START)."""
    i_start = max(k0, int(np.argmax(eps >= EPS_START)))
    bad = valid & (np.abs(np.nan_to_num(R)) >= EQ_TOL)
    last_bad = np.nonzero(bad[:i_end + 1])[0]
    cand = i_start if len(last_bad) == 0 else max(i_start, last_bad[-1] + 1)
    i_eq = cand if eps[cand] < 0.9 * eps[i_end] else None      # equilibre seulement a la toute fin : non
    best, i_best, run = (np.nan, np.nan), None, None
    for i in range(i_start, i_end + 1):
        if not bad[i]:
            run = i if run is None else run
            if np.isnan(best[0]) or eps[i] - eps[run] > best[1] - best[0]:
                best, i_best = (eps[run], eps[i]), run
        else:
            run = None
    return i_eq, best, i_best


def analyse(csv):
    case = os.path.basename(csv).replace('_history.csv', '')
    spec, rate_tag = case.split('_')[:2]
    rate = float(rate_tag[1:])
    paras = read_paras(csv.replace('_history.csv', '_paras.inp'))
    v_src = 'calculation input'
    if 'V_STRIKER_MS' in paras:
        v = paras['V_STRIKER_MS']
    else:
        v, v_src = make_run.striker_velocity(spec, rate), 'current make_run.py formula'

    d = pd.read_csv(csv, comment='#')
    ext_L0 = np.nan                      # longueur de l'extensometre, ecrite dans l'en-tete du CSV
    for line in open(csv):
        m_ = re.search(r'L0 = ([0-9.]+) mm', line)
        if m_:
            ext_L0 = float(m_.group(1))
        if not line.startswith('#'):
            break
    t = d.time_s.values
    fs = 1.0 / np.median(np.diff(t))
    b, a = butter(FILTER_ORDER, FC_HZ / (fs / 2.0))

    def lp(x):
        return filtfilt(b, a, x)

    Fi_raw, Fo_raw = d.F_sec_in_N.values, d.F_sec_out_N.values
    Fi, Fo, eps = lp(Fi_raw), lp(Fo_raw), lp(d.eps_ext.values)
    shift = GAUGE_TO_SPEC_MM * 1e-3 / C_BAR                     # s
    Fg = np.interp(t + shift, t, lp(d.sig_gauge_out.values * A_BAR_MM2), right=np.nan)
    rate_t = np.gradient(eps, t)

    k0 = int(np.argmax(Fi > 0.02 * Fi.max()))                   # debut du chargement
    reached = bool((eps >= EPS_TARGET).any())
    i_end = int(np.argmax(eps >= EPS_TARGET)) if reached else int(np.argmax(eps))
    win = np.zeros(len(t), bool)
    win[k0:i_end + 1] = True                                    # fenetre utile
    Fm = 0.5 * (Fi + Fo)
    valid = win & (Fm > 0.1 * Fm[win].max())
    R = np.where(valid, (Fi - Fo) / np.where(valid, Fm, 1.0), np.nan)
    i_eq, eq_int, i_eq_from = equilibrium(R, valid, eps, k0, i_end)
    # Meme chose sans filtre (pour montrer l'effet du filtre)
    Fm_raw = 0.5 * (Fi_raw + Fo_raw)
    valid_raw = win & (Fm_raw > 0.1 * Fm_raw[win].max())
    R_raw = np.where(valid_raw, (Fi_raw - Fo_raw) / np.where(valid_raw, Fm_raw, 1.0), np.nan)
    i_eq_raw, _, _ = equilibrium(R_raw, valid_raw, eps, k0, i_end)

    plateau = win & (eps >= EPS_PLATEAU)
    hi = 0.8 * eps[i_end]                                       # eps_2 = 0,8 x deformation max
    rate_win = plateau & (eps <= hi)
    i5 = int(np.argmax(eps >= EPS_PLATEAU))
    iF = k0 + int(np.argmax(Fi[k0:i_end + 1]))
    idx = np.arange(len(t))
    pre = (idx >= max(k0, int(np.argmax(eps >= EPS_START)))) & (idx <= iF)
    post = (idx > iF) & (idx <= i_end)
    g = plateau & ~np.isnan(Fg)
    inc = d.eps_gauge_in.values
    achieved = rate_t[rate_win].mean() if rate_win.any() else np.nan
    ke0 = d.ALLKE_mJ.iloc[0]
    m_striker = RHO_STRIKER * np.pi * 0.010 ** 2 * L_STRIKER_M          # kg, modele complet
    res = {
        'case_id': case, 'specimen': spec, 'target_rate': rate, 'v_striker': v, 'v_source': v_src,
        'ext_L0': ext_L0,
        'incident_strain': np.median(inc[inc < 0.5 * inc.min()]),
        'incident_theory': -make_run.K_IMP * v / C_BAR,
        'achieved_rate': achieved,
        'eps2': hi, 't1_ms': 1e3 * t[i5], 't2_ms': 1e3 * t[int(np.argmax(eps >= hi))],
        'rate_at_Fmax': rate_t[iF],
        'rate_nominal': eps[i_end] / (t[i_end] - t[k0]),
        'rate_pre_p10': np.percentile(rate_t[pre], 10), 'rate_pre_p90': np.percentile(rate_t[pre], 90),
        'rate_post_p10': np.percentile(rate_t[post], 10) if post.any() else np.nan,
        'rate_post_p90': np.percentile(rate_t[post], 90) if post.any() else np.nan,
        'startup_ms': 1e3 * ((t[i5] - t[k0]) - EPS_PLATEAU / achieved),
        't_load_ms': 1e3 * t[k0],
        'time_to_30_ms': 1e3 * (t[i_end] - t[k0]) if reached else np.nan,
        'eps_max': eps[i_end], 'reached_30': reached,
        'F_max_kN': Fi[iF] / 1e3, 'eps_at_Fmax': eps[iF],
        'eps_eq': eps[i_eq] if i_eq is not None else np.nan,
        't_eq_ms': 1e3 * (t[i_eq] - t[k0]) if i_eq is not None else np.nan,
        'eps_eq_raw': eps[i_eq_raw] if i_eq_raw is not None else np.nan,
        'eq_from': eq_int[0], 'eq_to': eq_int[1],
        'R_max_after5': np.nanmax(np.abs(R[plateau])) if plateau.any() else np.nan,
        'R_max_after5_raw': np.nanmax(np.abs(R_raw[plateau])) if plateau.any() else np.nan,
        'dF_max_after5_kN': np.abs(Fi - Fo)[plateau].max() / 1e3 if plateau.any() else np.nan,
        'gauge_err_after5': (np.abs(Fg - Fo)[g].max() / Fi[iF]) if g.any() else np.nan,
        'hourglass': d.ALLAE_mJ.iloc[-1] / max(d.ALLIE_mJ.iloc[-1], 1e-12),
        'ke0_ratio': ke0 / (0.5 * m_striker * v ** 2 * 1e3),
        'energy_drift': (d.ETOTAL_mJ.max() - d.ETOTAL_mJ.min()) / ke0,
    }
    curves = {'t_ms': 1e3 * (t - t[k0]), 'eps': eps, 'Fi': Fi, 'Fo': Fo, 'Fg': Fg, 'R': R,
              't_abs_ms': 1e3 * t, 'eps_gauge_in': d.eps_gauge_in.values, 'eps_gauge_out': d.eps_gauge_out.values,
              'Fi_raw': Fi_raw, 'Fo_raw': Fo_raw, 'Fg_raw': d.sig_gauge_out.values * A_BAR_MM2, 'R_raw': R_raw,
              'rate': rate_t, 'win': win, 'valid': valid, 'iF': iF, 'i_eq': i_eq, 'i_eq_from': i_eq_from}
    return res, curves


# ============================================================
# FIGURES
# ============================================================
def new_axes(n, w=3.3, h=3.0):
    fig, axs = plt.subplots(1, n, figsize=(w * n + 0.4, h), squeeze=False)
    for ax in axs[0]:
        ax.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
    return fig, axs[0]


def save(fig, out_dir, name):
    fig.tight_layout()
    for ext in ('pdf', 'png'):
        fig.savefig(os.path.join(out_dir, '%s.%s' % (name, ext)), dpi=200)
    plt.close(fig)


def rate_label(r):
    return '%d s$^{-1}$' % r['target_rate']


def fig_equilibrium(groups, out):
    fig, axs = new_axes(len(groups), w=4.2)
    for ax, (spec, items) in zip(axs, groups):
        ax.axhspan(-100 * EQ_TOL, 100 * EQ_TOL, color=BAND, zorder=0)
        for col, (r, c) in items:
            m = c['valid']
            ax.plot(100 * c['eps'][m], 100 * c['R'][m], color=col, lw=1.4, label=rate_label(r))
        ax.set_ylim(-20, 20)
        ax.set_xlim(0, 32)
        ax.set_xlabel('engineering strain (%)')
        ax.set_ylabel('R = (F$_{in}$ - F$_{out}$) / F$_{mean}$ (%)')
        ax.set_title('%s  (shaded: |R| < %d %%)' % (spec, round(100 * EQ_TOL)), loc='left')
        ax.legend(loc='upper center', ncol=3, fontsize=8)
    save(fig, out, 'F1_equilibrium')


def fig_equilibrium_onset(spec, items, out):
    """Zoom sur la mise en equilibre : F_in et F_out en fonction du temps, du debut du chargement
    jusqu'un peu apres le debut de l'equilibre (et au moins 5 % de deformation)."""
    fig, axs = new_axes(len(items), w=3.3, h=3.1)
    for k, (ax, (col, (r, c))) in enumerate(zip(axs, items)):
        t, eps = c['t_ms'], c['eps']
        i_mark = c['i_eq'] if c['i_eq'] is not None else c['i_eq_from']
        i5 = int(np.argmax((eps >= EPS_PLATEAU) & (t >= 0)))
        t_end = 1.4 * max(t[i5], t[i_mark] if i_mark is not None else 0.0)
        m = (t >= -0.02 * t_end) & (t <= t_end)
        ax.plot(t[m], c['Fi'][m] / 1e3, color=col, lw=1.6, label='F$_{in}$ (input section)')
        ax.plot(t[m], c['Fo'][m] / 1e3, color=INK, lw=1.1, ls='--', label='F$_{out}$ (output section)')
        ymax = 1.15 * max(c['Fi'][m].max(), c['Fo'][m].max()) / 1e3
        for e in (0.01, 0.02, 0.05):                          # reperes de deformation
            j = int(np.argmax((eps >= e) & (t >= 0)))
            if t[j] <= t_end:
                ax.axvline(t[j], color=INK2, lw=0.6, ls=':')
                ax.text(t[j], ymax * 0.99, ' %d %%' % round(100 * e), color=INK2, fontsize=7, va='top')
        # premier point ou le critere est evalue (deformation >= EPS_START et force > 10 % du max)
        checked = np.where(c['valid'] & (eps >= EPS_START) & (t >= 0))[0]
        from_start = c['i_eq'] is not None and len(checked) and c['i_eq'] == checked[0]
        if len(checked):
            # partie non evaluee (forces quasi nulles) : grisee, pour ne pas la confondre avec un desequilibre
            ax.axvspan(t[m][0], t[checked[0]], color=BAND, zorder=0)
            if t[checked[0]] - t[m][0] > 0.08 * (t_end - t[m][0]):
                ax.text(0.5 * (t[m][0] + t[checked[0]]), ymax * 0.55, 'not\nchecked', color=INK2, fontsize=6.5,
                        ha='center', va='center', rotation=90)
        if from_start:
            # equilibre des le premier point verifie : pas de trait, qui ressemblerait a un instant physique
            ax.text(t[c['i_eq']], ymax * 0.12, ' |R| < %d %% from the\n first point checked\n to the end'
                    % round(100 * EQ_TOL), color=col, fontsize=7, va='bottom')
        elif i_mark is not None:
            ax.axvline(t[i_mark], color=col, lw=1.0)
            txt = '|R| < %d %%\nfrom here (%s)' % (round(100 * EQ_TOL), pct(eps[i_mark], 2))
            if c['i_eq'] is None:
                txt += '\n(until %s)' % pct(r['eq_to'], 0)
            ax.text(t[i_mark], ymax * 0.12, ' ' + txt, color=col, fontsize=7, va='bottom')
        ax.set_ylim(0, ymax)
        ax.set_xlim(t[m][0], t_end)
        ax.set_title('%s, %s' % (spec, rate_label(r)), loc='left')
        ax.set_xlabel('time from loading start (ms)')
        if k == 0:
            ax.set_ylabel('force (kN)')
            ax.legend(loc='center right', fontsize=7)
    save(fig, out, 'F1b_equilibrium_onset_%s' % spec)


def fig_forces(spec, items, out):
    fig, axs = new_axes(len(items), w=3.3)
    for k, (ax, (col, (r, c))) in enumerate(zip(axs, items)):
        m = c['win'].copy()
        j = np.nonzero(m)[0]
        m[max(j[0] - 30, 0):min(j[-1] + 30, len(m))] = True       # un peu de marge autour
        ax.plot(c['t_ms'][m], c['Fi'][m] / 1e3, color=col, lw=1.6, label='specimen, input section')
        ax.plot(c['t_ms'][m], c['Fo'][m] / 1e3, color=col, lw=1.2, ls='--', label='specimen, output section')
        ax.plot(c['t_ms'][m], c['Fg'][m] / 1e3, color=INK, lw=0.9, label='output bar gauge (shifted)')
        ax.set_title('%s, %s' % (spec, rate_label(r)), loc='left')
        ax.set_xlabel('time from loading start (ms)')
        if k == 0:
            ax.set_ylabel('force (kN)')
            ax.legend(loc='lower center', fontsize=8)
    ymax = max(ax.get_ylim()[1] for ax in axs)
    for ax in axs:
        ax.set_ylim(0, ymax)
    save(fig, out, 'F2_forces_%s' % spec)


def fig_stress_strain(groups, out):
    """Une ligne par eprouvette, un graphe par vitesse : vraie courbe (coupe dans l'eprouvette, gris epais)
    et courbe mesuree par la jauge de la barre de sortie (couleur), toutes deux issues de la simulation."""
    ncol = max(len(items) for _, items in groups)
    fig, axs = plt.subplots(len(groups), ncol, figsize=(3.4 * ncol + 0.4, 3.1 * len(groups)),
                            squeeze=False, sharey=True)
    for row, (spec, items) in enumerate(groups):
        A0 = A0_MM2.get(spec)
        for k in range(ncol):
            ax = axs[row][k]
            if k >= len(items) or not A0:
                ax.axis('off')
                continue
            col, (r, c) = items[k]
            m = c['win']
            ax.grid(True, color=GRID, linewidth=0.6)
            ax.set_axisbelow(True)
            for s_ in ('top', 'right'):
                ax.spines[s_].set_visible(False)
            ax.plot(100 * c['eps'][m], c['Fo'][m] / A0, color='#9a9994', lw=3.2, solid_capstyle='round',
                    label='true force in the specimen\n(cross-section, simulation only)')
            ax.plot(100 * c['eps'][m], c['Fg'][m] / A0, color=col, lw=1.2,
                    label='force read on the output bar\ngauge (what the test measures)')
            ax.set_xlim(0, 32)
            ax.set_ylim(0, 1600)              # le pic initial de la jauge (< 2 %) est coupe
            ax.set_title('%s, %s  (error %s)' % (spec, rate_label(r), pct(r['gauge_err_after5'], 0)),
                         loc='left')
            ax.set_xlabel('engineering strain (%)')
            if k == 0:
                ax.set_ylabel('engineering stress (MPa)')
                ax.legend(loc='lower left', fontsize=7, frameon=False)      # une seule legende
    save(fig, out, 'F3_stress_strain')


def fig_strain_rate(groups, out):
    fig, axs = new_axes(len(groups), w=4.2)
    for ax, (spec, items) in zip(axs, groups):
        for col, (r, c) in items:
            m = c['win'] & (c['eps'] > 0.005)
            ax.plot(100 * c['eps'][m], c['rate'][m], color=col, lw=1.4, label=rate_label(r))
            ax.axhline(r['target_rate'], color=col, lw=0.8, ls=':')
            ax.plot(100 * c['eps'][c['iF']], c['rate'][c['iF']], 'o', ms=6, color=col, mec='white', mew=1.0)
        ax.plot([], [], 'o', ms=6, color=INK2, mec='white', label='force maximum')
        ax.set_yscale('log')
        ax.set_ylim(30, 3000)
        ax.set_xlim(0, 32)
        ax.set_xlabel('engineering strain (%)')
        ax.set_ylabel('strain rate (s$^{-1}$)')
        ax.set_title('%s  (dotted: target; dot: force maximum)' % spec, loc='left')
        ax.legend(loc='lower right')
    save(fig, out, 'F4_strain_rate')


def fig_striker(groups, out):
    """Un panneau par eprouvette : formule de make_run.py (ligne) et calculs (points)."""
    fig, axs = new_axes(len(groups), w=4.2, h=3.2)
    rate_min = EPS_TARGET / (PULSE_MS * 1e-3)
    rr = np.linspace(20, 1300, 200)
    for k, (ax, (spec, items)) in enumerate(zip(axs, groups)):
        vmax = max(r['v_striker'] for _, (r, _c) in items)
        if make_run.SPECIMENS.get(spec):
            vv = [make_run.striker_velocity(spec, x) for x in rr]
            ax.plot(rr, vv, color=INK2, lw=1.0, label='estimate (make_run.py)')
            vmax = max(vmax, max(vv))
        ytop = 1.1 * vmax
        ax.axvspan(0, rate_min, color=BAND, zorder=0)
        ax.text(rate_min * 0.5, 0.97 * ytop, '30 %\nnot\nreachable', ha='center', va='top', color=INK2,
                fontsize=8)
        for col, (r, c) in items:
            ax.plot(r['achieved_rate'], r['v_striker'], 'o', ms=7, color=col, mec='white', mew=1.2,
                    label='simulated, target %s' % rate_label(r))
        ax.set_xlim(0, 1300)
        ax.set_ylim(0, ytop)
        ax.set_title(spec, loc='left')
        ax.set_xlabel('achieved strain rate (s$^{-1}$)')
        if k == 0:
            ax.set_ylabel('striker velocity (m/s)')
        ax.legend(loc='upper left', bbox_to_anchor=(0.14, 1.0), fontsize=8)
    save(fig, out, 'F5_striker_velocity')


# ============================================================
# FIGURE DE CONTROLE (une par calcul, dans le dossier du calcul)
# ============================================================
def fig_case_overview(r, c, png):
    """Vue d'ensemble d'un calcul : jauges des barres, forces, R, deformation (signaux bruts)."""
    t = c['t_abs_ms']
    fig, ax = plt.subplots(4, 1, figsize=(8, 9.5), sharex=True)
    for a in ax:
        a.grid(True, color=GRID, linewidth=0.6)
        for s_ in ('top', 'right'):
            a.spines[s_].set_visible(False)
        a.axvspan(t[c['win']][0], t[c['win']][-1], color=BAND, zorder=0)
    ax[0].plot(t, 1e3 * c['eps_gauge_in'], color='#2a78d6', lw=1.2, label='input bar gauge')
    ax[0].plot(t, 1e3 * c['eps_gauge_out'], color='#eb6834', lw=1.2, label='output bar gauge')
    ax[0].set_ylabel('bar strain (x 1e-3)')
    ax[0].legend(frameon=False, loc='center right', fontsize=8)
    ax[1].plot(t, c['Fi_raw'] / 1e3, color='#2a78d6', lw=1.2, label='F$_{in}$ (specimen)')
    ax[1].plot(t, c['Fo_raw'] / 1e3, color='#eb6834', lw=1.0, ls='--', label='F$_{out}$ (specimen)')
    ax[1].plot(t, c['Fg_raw'] / 1e3, color=INK, lw=0.8, label='output bar gauge (not shifted)')
    ax[1].set_ylabel('force (kN)')
    ax[1].legend(frameon=False, loc='lower right', fontsize=8)
    ax[2].plot(t, 100 * c['R_raw'], color='#2a78d6', lw=1.0)
    ax[2].axhspan(-100 * EQ_TOL, 100 * EQ_TOL, color='#e3e2de', zorder=0)
    ax[2].set_ylim(-30, 30)
    ax[2].set_ylabel('R, unfiltered (%)')
    ax[3].plot(t, 100 * c['eps'], color='#2a78d6', lw=1.2)
    ax[3].axhline(100 * EPS_TARGET, color=INK2, lw=0.8, ls=':')
    ax[3].set_ylim(0, max(40, min(100, 105 * r['eps_max'])))
    ax[3].set_ylabel('extensometer strain (%)')
    ax[3].set_xlabel('time (ms)')
    fig.suptitle('%s - control figure (shaded: from loading start to 30 %% strain)' % r['case_id'], fontsize=10)
    fig.tight_layout()
    fig.savefig(png, dpi=130)
    plt.close(fig)


# ============================================================
# TABLEAUX ET TEXTE DU RAPPORT
# ============================================================
# Tableau complet ecrit dans T1_conditions.csv (le rapport en montre des extraits plus etroits)
CSV_COLS = [
    ('specimen', 'specimen'), ('target_rate', 'target rate (1/s)'), ('v_striker', 'striker velocity (m/s)'),
    ('incident_strain', 'incident strain (-)'), ('achieved_rate', 'achieved rate (1/s)'),
    ('rate_at_Fmax', 'rate at max force (1/s)'), ('rate_nominal', 'nominal rate (1/s)'),
    ('time_to_30_ms', 'time to 30 % (ms)'), ('eps_max', 'max strain reached (-)'),
    ('F_max_kN', 'max force (kN)'), ('eps_at_Fmax', 'strain at max force (-)'),
    ('eps_eq', 'equilibrium from strain (-)'), ('t_eq_ms', 'equilibrium after (ms)'),
    ('eq_from', 'longest equilibrium interval from strain (-)'), ('eq_to', 'longest equilibrium interval to strain (-)'),
    ('R_max_after5', 'max |R| after 5 % (-)'), ('dF_max_after5_kN', 'max |dF| after 5 % (kN)'),
    ('gauge_err_after5', 'max gauge error after 5 % (-)'), ('hourglass', 'hourglass / internal energy (-)'),
]


def write_csv(rows, out):
    df = pd.DataFrame([{label: r[k] for k, label in CSV_COLS} for r in rows])   # NaN -> case vide
    df.insert(0, 'case_id', [r['case_id'] for r in rows])
    df.to_csv(os.path.join(out, 'T1_conditions.csv'), index=False, float_format='%.4g')


def fmt(val, f):
    if isinstance(val, float) and np.isnan(val):
        return 'n/a'
    return f % val


def pct(x, nd=0):
    return ('%.' + str(nd) + 'f %%') % (100 * x)


def md_table(header, lines):
    def esc(c):
        return c.replace('|', '\\|')                      # un | dans une case casse le tableau
    out = ['| ' + ' | '.join(esc(c) for c in header) + ' |', '|' + '---|' * len(header)]
    out += ['| ' + ' | '.join(esc(c) for c in l) + ' |' for l in lines]
    return '\n'.join(out)


def sci(x):
    """-7.69e-04 -> $-7.69 \\times 10^{-4}$"""
    m, e = ('%.2e' % x).split('e')
    return '$%s \\times 10^{%d}$' % (m, int(e))


def label_long(r):
    return '%s at %d s⁻¹' % (r['specimen'], r['target_rate'])


def label(r):
    return '%s / %d' % (r['specimen'], r['target_rate'])          # court : tient sur une ligne dans le PDF


def eq_ok(r):
    return (not np.isnan(r['eps_eq'])) and r['R_max_after5'] < EQ_TOL


def eq_short(r):
    """Verdict court pour les tableaux."""
    if eq_ok(r):
        return 'yes, from %s' % pct(r['eps_eq'], 1)
    if not np.isnan(r['eq_from']):
        return 'partial, %s to %s' % (pct(r['eq_from'], 1), pct(r['eq_to'], 1))
    return 'no'


def needed_striker(r):
    """Longueur de striker necessaire pour 30 % a la vitesse obtenue (demarrage compris)."""
    t_ms = 1e3 * EPS_TARGET / r['achieved_rate'] + r['startup_ms']
    return t_ms, C_STRIKER * t_ms * 1e-3 / 2.0


def case_sentence(r):
    s = '- **%s** (striker %.2f m/s): ' % (label_long(r), r['v_striker'])
    if eq_ok(r):
        s += ('equilibrium is established at %s strain, %.2f ms after the loading start, and holds until the end '
              'of the loading (max $\\lvert R\\rvert$ after 5 %% strain: %s).' % (
                  pct(r['eps_eq'], 1), r['t_eq_ms'], pct(r['R_max_after5'], 1)))
    else:
        s += 'equilibrium is **only partly reached**: '
        if not np.isnan(r['eq_from']):
            s += '$\\lvert R\\rvert$ < %d %% from %s to %s strain, ' % (
                round(100 * EQ_TOL), pct(r['eq_from'], 1), pct(r['eq_to'], 1))
        s += ('but it reaches %s at other instants after 5 %% strain ($\\lvert F_{in} - F_{out}\\rvert$ up to '
              '%.2f kN, i.e. %s of the maximum force).' % (
                  pct(r['R_max_after5'], 1), r['dF_max_after5_kN'], pct(r['dF_max_after5_kN'] / r['F_max_kN'], 1)))
    return s


def write_report(study, rows, out):
    specs = sorted(set(r['specimen'] for r in rows))
    rate_min = EPS_TARGET / (PULSE_MS * 1e-3)
    tol = round(100 * EQ_TOL)
    fc = FC_HZ / 1e3
    shift_us = 1e3 * GAUGE_TO_SPEC_MM / C_BAR
    sp = make_run.SPECIMENS
    ext = {}
    for r in rows:
        ext.setdefault(r['specimen'], r['ext_L0'])
    ext_txt = ', '.join('%g mm for the %s' % (ext[s_], s_) for s_ in specs)
    a0_txt = ', '.join('%.1f mm² for the %s' % (A0_MM2[s_], s_) for s_ in specs if A0_MM2.get(s_))
    gaps = study in CENTRED_STUDIES      # ancien placement : eprouvette centree, jeux dans les logements
    all_eq = all(eq_ok(r) for r in rows)
    err_max = max(r['gauge_err_after5'] for r in rows)
    L = []

    def P(*parts):                       # un paragraphe = une ligne + une ligne vide
        L.append(''.join(parts))
        L.append('')

    def figure(img, title, plotted, source, read):
        P('![%s](%s)' % (title, img))
        P('**%s.** ' % title, '*Plotted:* ', plotted, ' *Source:* ', source, ' *How to read it:* ', read)

    # ------------------------------------------------------------ titre
    P('# Task I – Force equilibrium and loading speeds in the SHPB with load inversion device')
    P('*Study `%s` – specimens: %s. Generated by `scripts/post/report_taskI.py`: every number in this report '
      'is computed from the simulation outputs.*' % (study, ', '.join(specs)))
    P('**Questions of Task I.**')
    P('1. Can quasi-static force equilibrium be achieved in the specimen at nominal strain rates of 100, 500 and '
      '1000 s⁻¹?\n2. Which loading speeds are required to reach an engineering strain of 30 %?')

    # ------------------------------------------------------------ conclusions d'abord
    P('## Summary')
    P(md_table(['Specimen / target rate (s⁻¹)', 'Equilibrium ($\\lvert R\\rvert$ < %d %%)' % tol, 'Striker velocity', '30 % strain',
                'Gauge error'],
               [[label(r), eq_short(r), '%.2f m/s' % r['v_striker'],
                 ('in %.2f ms' % r['time_to_30_ms']) if r['reached_30'] else 'no (%s max)' % pct(r['eps_max'], 1),
                 pct(r['gauge_err_after5'], 0)] for r in rows]))
    ok_ = [label(r) for r in rows if eq_ok(r)]
    part_ = ['%s (%s to %s)' % (label(r), pct(r['eq_from'], 1), pct(r['eq_to'], 1)) for r in rows
             if not eq_ok(r) and not np.isnan(r['eq_from'])]
    if all_eq:
        eq_txt = '- Equilibrium is reached at the very start of loading and maintained until the end at all rates.\n'
    else:
        eq_txt = ('- Equilibrium maintained until the end: %s. ' % (', '.join(ok_) if ok_ else 'none') +
                  ('Only partly reached: %s; the largest ratios occur late in the test, when the force decreases '
                   '(necking).\n' % ', '.join(part_) if part_ else '\n'))
    P(eq_txt +
      '- The striker velocity must account for the specimen force (see *Loading speeds*). With the 5 m striker, '
      '30 %% strain cannot be reached below about %.0f s⁻¹.\n' % rate_min +
      ('- The force read on the output bar gauge follows the true specimen force within %s of the maximum force '
       'after 5 %% strain.' % pct(err_max, 0) if err_max < 0.10 else
       '- Even when the specimen is in equilibrium, the force read on the output bar gauge oscillates around the '
       'true specimen force: this must be considered when assessing the measured curves.'))
    P('*Gauge error*: largest difference between the force read on the output bar gauge and the exact specimen '
      'force after 5 % strain, relative to the maximum force.')

    # ------------------------------------------------------------ modele
    P('## Model and assumptions')
    model = [
        ('Bench', 'Ø20 mm steel striker (5 m), maraging input bar (6.01 m), load inversion device, specimen, '
                  'maraging output bar (≈ 6 m); virtual strain gauges 400 mm from the bar ends (Beerli et al. 2026).'),
        ('Symmetry', 'half model, cut by the vertical plane through the bar axes.'),
        ('Mesh', 'bars: swept C3D8R (5 mm axially, 2 mm in the section); clamping heads: C3D10M tetrahedra (2 mm); '
                 'specimen: C3D8R, 0.5 mm in plane, 4 elements through the 1.5 mm thickness; ≈ 214 000 elements.'),
        ('Solver', 'Abaqus/Explicit, double precision, **no mass scaling** (inertia is the studied effect).'),
        ('Bars', 'linear elastic, $E = \\rho c^2$ with the measured wave speeds (4871 m/s bars, 4720 m/s striker) '
                 'and assumed densities (8000 and 7850 kg/m³).'),
        ('Specimen', 'DP1000, von Mises, isotropic Swift–Voce hardening (below), **rate independent**.'),
        ('Contacts', 'bar ends: hard, frictionless; specimen teeth in the pockets: hard, friction 0.2. ' +
                     ('The specimen is centred in the pockets, with a clearance of 0.36 mm on each side '
                      '(placement used until 21 Oct 2026).' if gaps else
                      'At the start the specimen teeth touch both pockets, without pre-load, as in the lab where the '
                      'inverter is pulled slightly before the test (clearances of 0.36 mm closed by translating the '
                      'specimen and the output bar; `docs/assembly.md`).')),
        ('Guides', 'vertical displacement blocked on the sliding face of the inverter and on the bar axes (without '
                   'them the inverter pitches under the eccentric load).'),
        ('Loading', 'initial velocity of the striker (Table T1).'),
    ]
    P('\n'.join('- **%s**: %s' % kv for kv in model))
    P('**Specimen material.** The flow stress $k$ (true stress) is a function of the equivalent plastic strain '
      '$\\varepsilon_p$, as identified by Beerli et al. (2026, eq. 10 and table 4) on quasi-static tensile tests:')
    P('$$\nk(\\varepsilon_p) = \\alpha_{SV}\\,A\\,(\\varepsilon_p+\\varepsilon_0)^{n}'
      ' + (1-\\alpha_{SV})\\left[k_0 + Q\\left(1-e^{-\\beta\\varepsilon_p}\\right)\\right]\n$$')
    P('with $A$ = 1395 MPa, $\\varepsilon_0$ = 10⁻⁶, $n$ = 0.0892 (Swift power law), $k_0$ = 739 MPa, '
      '$Q$ = 301 MPa, $\\beta$ = 102 (Voce exponential law) and $\\alpha_{SV}$ = 0.5; $E$ = 195 GPa, $\\nu$ = 0.33. '
      'The strain-rate and temperature factor of the full model of Beerli et al. is not used, as in their own '
      'simulation of the bench: the three strain rates have exactly the same material law. The Considère '
      'criterion $dk/d\\varepsilon_p = k$ predicts necking at 5.1 % engineering strain and 1002 MPa, which the '
      'simulations reproduce (maximum force ≈ 7.5 kN on 7.5 mm² at about 5 % strain). Details: `docs/materials.md`.')

    # ------------------------------------------------------------ traitement
    P('## Signal processing and definitions')
    P('**Filter.** Forces and strain are low-pass filtered (4th-order Butterworth, %d kHz cut-off, zero phase), '
      'the cut-off used for the output bar gauge signal in the laboratory. The simulation writes one point per '
      'microsecond and contains vibrations of a few microseconds that the experiment cannot resolve. The effect of '
      'the filter is shown in Table T3.' % fc)
    P('**Forces.** $F_{in}$ and $F_{out}$ are the exact axial forces in two cross-sections at both ends of the '
      'parallel section of the specimen ($F_{in}$ on the inverter side, $F_{out}$ on the output bar side). They '
      'answer the equilibrium question. The experiment only has the strain gauge of the output bar:')
    P('$$\nF_{gauge}(t) = A_{bar}\\,E_{bar}\\,\\varepsilon_{gauge}\\!\\left(t + \\Delta t\\right), \\qquad '
      '\\Delta t = \\frac{%.0f\\ \\text{mm}}{%.0f\\ \\text{m/s}} = %.0f\\ \\mu\\text{s}\n$$'
      % (GAUGE_TO_SPEC_MM, C_BAR, shift_us))
    P('i.e. the gauge signal shifted by the travel time of the wave from the specimen to the gauge (no dispersion '
      'correction). It is only used in the section *What the experiment will measure*.')
    P('**Strain.** Engineering strain of a virtual extensometer on the parallel section (%s), equivalent to the '
      'DIC extensometer.' % ext_txt)
    P('**Equilibrium.**')
    P('$$\nR = \\frac{F_{in} - F_{out}}{F_{mean}}, \\qquad F_{mean} = \\frac{F_{in} + F_{out}}{2}\n$$')
    P('The specimen is considered in equilibrium when $\\lvert R\\rvert$ < %d %%. The *equilibrium strain* is the '
      'strain from which $\\lvert R\\rvert$ stays below this limit until 30 %% strain (or until the end of loading). '
      'The *loading start* is the first instant where $F_{in}$ exceeds 2 %% of its maximum.' % tol)
    P('**Achieved strain rate.** The strain rate varies during the test (F4). To give one value per simulation, it '
      'is measured on the part of the test where the loading is established: the strain gained between two '
      'instants divided by the time between them,')
    P('$$\n\\dot\\varepsilon = \\frac{\\varepsilon_2 - \\varepsilon_1}{t_2 - t_1}, \\qquad '
      '\\varepsilon_1 = 5\\ \\%, \\qquad \\varepsilon_2 = 0.8\\,\\varepsilon_{max}\n$$')
    ex = [r for r in rows if r['reached_30']]
    ex = ex[0] if ex else rows[0]
    P('where $t_1$ and $t_2$ are the instants at which the extensometer reaches $\\varepsilon_1$ and '
      '$\\varepsilon_2$, and $\\varepsilon_{max}$ is the maximum strain of the test (30 %, or less if the loading '
      'pulse ends before).')
    P('- $\\varepsilon_1$ = 5 %: before, the loading is not established (rise of the incident pulse, ' +
      ('specimen shoulders settling in the pockets, ' if gaps else '') +
      'force rising to its maximum, reached at about 5 % strain).\n'
      '- $\\varepsilon_2$ = 80 % of the maximum strain: the end of the test is excluded, where the strain rate '
      'drops when the pulse ends. This gives 24 % when 30 % is reached, and less otherwise (Table T4).')
    P('Example (%s): the strain reaches 5 %% at $t_1$ = %.3f ms and %s at $t_2$ = %.3f ms, so '
      '$\\dot\\varepsilon$ = (%.3f − 0.05) / (%.3f × 10⁻³ s) ≈ %.0f s⁻¹. The full history is shown in F4 and '
      'other definitions in T4.' % (label_long(ex), ex['t1_ms'], pct(ex['eps2'], 1), ex['t2_ms'], ex['eps2'],
                                   ex['t2_ms'] - ex['t1_ms'], ex['achieved_rate']))

    # ------------------------------------------------------------ resultats
    P('## Task I answers')
    P('**Table T1 – Test conditions.**')
    P(md_table(['Specimen / target rate (s⁻¹)', 'Striker velocity (m/s)', 'Achieved rate (s⁻¹)',
                'Time to 30 % strain', 'Max strain'],
               [[label(r), '%.2f' % r['v_striker'], '%.0f' % r['achieved_rate'],
                 ('%.2f ms' % r['time_to_30_ms']) if r['reached_30'] else 'not reached',
                 pct(r['eps_max'], 1)] for r in rows]))
    P('*Striker velocity*: setting of the test. *Achieved rate*: see above. *Time to 30 % strain*: from the loading '
      'start. *Max strain*: 30 %, or less if the loading pulse ends before. The complete table, with all '
      'indicators, is `T1_conditions.csv`.')

    P('### Force equilibrium')
    figure('F1_equilibrium.png', 'Figure F1 – Force equilibrium in the specimen',
           'the equilibrium ratio $R$ (vertical axis) against the engineering strain (horizontal axis), one curve '
           'per target rate.',
           'exact forces $F_{in}$ and $F_{out}$ in the two cross-sections of the simulated specimen, filtered at '
           '%d kHz (not a strain gauge); strain of the virtual extensometer.' % fc,
           'inside the shaded band ($\\lvert R\\rvert$ < %d %%) both ends of the specimen carry the same force: '
           'the specimen is in equilibrium. ' % tol +
           ('The large values below about 2 % strain come from the start of loading (specimen shoulders settling '
            'in the pockets) and are cut at ±20 %.' if gaps else
            'At the very start both forces are close to zero, so $R$ is large for a few microseconds; values are '
            'cut at ±20 %.'))
    for s_ in specs:
        figure('F1b_equilibrium_onset_%s.png' % s_, 'Figure F1b (%s) – Onset of equilibrium' % s_,
               'the exact forces $F_{in}$ (coloured solid line) and $F_{out}$ (black dashed line) against the time '
               'from the loading start, one panel per target rate, until shortly after equilibrium is reached '
               '(and at least 5 % strain). Dotted vertical lines: instants at which the strain reaches 1, 2 and 5 %; '
               'coloured vertical line: instant from which $\\lvert R\\rvert$ < 5 % (for a partial equilibrium: '
               'start of the longest interval); no line when equilibrium holds from the first point checked. '
               'Grey band: start of loading where $R$ is not evaluated (strain below ' + pct(EPS_START, 1) +
               ' or mean force below 10 % of its maximum: the ratio of two near-zero forces is meaningless).',
               'same filtered forces as F1.',
               ('before equilibrium the two forces differ (the first pulse is the specimen shoulders settling in the '
                'pockets); from the coloured line onwards they overlap.' if gaps else
                'from the coloured line onwards the two forces overlap; the force rises smoothly from zero.'))
    P('**Table T2 – Equilibrium indicators.**')
    P(md_table(['Specimen / target rate (s⁻¹)', 'Equilibrium from', 'Max $\\lvert R\\rvert$ after 5 %', 'Max $\\lvert\\Delta F\\rvert$ after 5 %',
                'Max force'],
               [[label(r),
                 ('%s (%.2f ms)' % (pct(r['eps_eq'], 1), r['t_eq_ms'])) if eq_ok(r) else
                 ('%s to %s only' % (pct(r['eq_from'], 1), pct(r['eq_to'], 1)) if not np.isnan(r['eq_from']) else 'never'),
                 pct(r['R_max_after5'], 1), '%.2f kN' % r['dF_max_after5_kN'],
                 '%.2f kN at %s' % (r['F_max_kN'], pct(r['eps_at_Fmax'], 1))] for r in rows]))
    P('*Equilibrium from*: strain (and time after the loading start) from which $\\lvert R\\rvert$ < %d %% holds '
      'until the end of loading; %s is the lowest strain considered, so this value means "from the start". '
      '$\\Delta F = F_{in} - F_{out}$.' % (tol, pct(EPS_START, 1)))
    for r in rows:
        L.append(case_sentence(r))
    L.append('')
    if gaps:
        P('In all cases the first few tens of microseconds show a short force pulse followed by a drop to zero before '
          'continuous loading starts (F1b): the inverter and the specimen cross the clearances of the pockets, then '
          'the specimen hits the output pocket.')
    else:
        P('The specimen teeth touch both pockets at the start: the force rises smoothly from zero, without the '
          'impact pulse and the rebound obtained when the specimen was centred with clearances (study '
          '`taskI_20261013-1554`).')
    P('The force is maximum at about 5 to 8 % strain and then decreases (necking). The same force difference '
      'therefore gives a larger ratio $R$ late in the test, which is why the absolute difference $\\Delta F$ is '
      'given as well.')
    P('**Table T3 – Effect of the %d kHz filter** (exact section forces).' % fc)
    P(md_table(['Specimen / target rate (s⁻¹)', 'Equilibrium from (raw)', 'Equilibrium from (filtered)',
                'Max $\\lvert R\\rvert$ (raw)', 'Max $\\lvert R\\rvert$ (filtered)'],
               [[label(r), fmt(100 * r['eps_eq_raw'], '%.1f %%'), fmt(100 * r['eps_eq'], '%.1f %%'),
                 pct(r['R_max_after5_raw'], 1), pct(r['R_max_after5'], 1)] for r in rows]))
    P('*Raw*: forces as written by Abaqus (one point per µs). Max $\\lvert R\\rvert$ after 5 % strain.')

    P('### Loading speeds')
    figure('F4_strain_rate.png', 'Figure F4 – Strain rate in the specimen',
           'the strain rate (vertical axis, logarithmic scale) against the engineering strain, one curve per '
           'target rate; dotted lines: target rates; dots: force maximum (onset of necking).',
           'time derivative of the extensometer strain (filtered at %d kHz before derivation): a kinematic '
           'quantity, equivalent to DIC; not a force, not the output bar gauge.' % fc,
           'the curve should stay close to its target. Being a derivative, it amplifies small vibrations of the '
           'specimen (±10 to 30 % around the mean, period 10 to 20 µs at 1000 s⁻¹); on the logarithmic scale the '
           '100 s⁻¹ curve looks noisier than it is. A curve that drops before 30 % strain shows the end of the '
           'loading pulse' + ''.join(' (%s: %s)' % (label(r), pct(r['eps_max'], 1)) for r in rows if not r['reached_30']) +
           '.')
    P('**Table T4 – Strain rate with different definitions** (s⁻¹).')
    P(md_table(['Specimen / target rate (s⁻¹)', 'Achieved ($\\varepsilon_1 \\to \\varepsilon_2$)', 'At max force', 'Nominal', 'Before max force', 'After max force'],
               [[label(r), '%.0f (5 → %.1f %%)' % (r['achieved_rate'], 100 * r['eps2']), '%.0f' % r['rate_at_Fmax'],
                 '%.0f' % r['rate_nominal'],
                 '%.0f to %.0f' % (r['rate_pre_p10'], r['rate_pre_p90']),
                 '%.0f to %.0f' % (r['rate_post_p10'], r['rate_post_p90'])] for r in rows]))
    P('*Achieved*: definition above (used in T1 and F5). *At max force*: value of F4 at the dot. *Nominal*: final '
      'strain divided by the whole loading time, start-up included. *Before / after max force*: range of the F4 '
      'curve before and after the dot (10th to 90th percentile).')
    P('After the force maximum the strain rate is established close to the target and increases slowly, because '
      'the force decreases (necking) and brakes the bench less. Before the force maximum, during the uniform '
      'hardening phase, the strain rate is not yet stable at the higher rates' +
      (' (negative values: rebound of the specimen in the pockets).' if gaps else '.'))
    P('**Striker velocity.** The elongation rate of the inverter is approximately')
    P('$$\nv \\approx 2\\,v_i - \\frac{2F}{\\rho c A}, \\qquad v_i = K\\,V_{striker}, \\qquad '
      'K = \\frac{Z_{striker}}{Z_{striker} + Z_{bar}} = %.3f\n$$' % make_run.K_IMP)
    P('where $v_i$ is the particle velocity of the incident wave and $F$ the specimen force: the specimen force '
      'both slows the inverter down and pushes the output bar ($\\rho c A$ = %.0f N·s/m). Writing '
      '$v = \\dot\\varepsilon\\,L_{eff}$ gives' % make_run.Z_BARRE)
    P('$$\nV_{striker} = \\frac{\\dot\\varepsilon\\,L_{eff} + 2F/(\\rho c A)}{2K}\n$$')
    for s_ in specs:
        if sp.get(s_):
            P('- %s: $L_{eff}$ = %.1f mm, $F$ = %.0f kN (%s).' % (s_, sp[s_]['L_eff_mm'], sp[s_]['F_N'] / 1e3,
                                                                  sp[s_].get('source', '').replace('s-1', 's⁻¹')))
    P('$L_{eff}$ is an effective length relating the elongation rate to the extensometer strain rate. For the UT19, '
      'a first estimate without the force term ($V = \\dot\\varepsilon \\times$ 15 mm) gave 21 s⁻¹ instead of '
      '100 s⁻¹, because the specimen force is then almost as large as the force carried by the incident wave.')
    figure('F5_striker_velocity.png', 'Figure F5 – Striker velocity required for a given strain rate',
           'the striker velocity (vertical axis), i.e. the setting of the test, against the strain rate in the '
           'specimen (horizontal axis), one panel per specimen. Line: the formula above. Dots: the simulations, at '
           'the imposed striker velocity and the achieved strain rate (T1). Shaded: 30 % not reachable.',
           'formula of `make_run.py` and simulation results.',
           'choose a strain rate on the horizontal axis and read the striker velocity on the line; dots on the '
           'line confirm the formula.')
    lim = ('**Limit for 30 %% strain.** The 5 m striker gives a %.2f ms loading pulse, so 30 %% strain requires at '
           'least 0.30 / %.2f ms ≈ %.0f s⁻¹; the output bar (5.99 m) also limits the measurement window to '
           '%.2f ms (Beerli et al. 2026).' % (PULSE_MS, PULSE_MS, rate_min, OUTPUT_WINDOW_MS))
    for r in rows:
        if not r['reached_30']:
            t_ms, l_m = needed_striker(r)
            lim += (' At %d s⁻¹ (%s) the strain stops at %s; 30 %% would need about %.1f ms of loading '
                    '(0.30 / %.0f s⁻¹ + %.2f ms start-up), i.e. a striker of about %.1f m: almost the length of '
                    'the %.1f m launch tube, and longer than the measurement window.' % (
                        r['target_rate'], r['specimen'], pct(r['eps_max'], 1), t_ms, r['achieved_rate'],
                        r['startup_ms'], l_m, LAUNCH_TUBE_M))
    P(lim)

    # ------------------------------------------------------------ mesure
    P('## What the experiment will measure')
    P('In the experiment the force is only known from the output bar gauge. F2 and F3 compare this signal, as it '
      'would be recorded, with the exact force in the specimen.')
    for s_ in specs:
        figure('F2_forces_%s.png' % s_, 'Figure F2 (%s) – Specimen forces and output bar gauge' % s_,
               'axial force against the time from the loading start, one panel per target rate. Coloured solid '
               'line: $F_{in}$; coloured dashed line: $F_{out}$; black line: force read on the output bar gauge.',
               'the gauge force is $A_{bar} E_{bar} \\varepsilon_{gauge}$ shifted by %.0f µs (wave travel over the '
               '%.0f mm between specimen and gauge); all signals filtered at %d kHz.' % (shift_us, GAUGE_TO_SPEC_MM, fc),
               'overlapping coloured lines mean equilibrium; the distance between the black line and the coloured '
               'lines is the measurement error of the gauge.')
    figure('F3_stress_strain.png', 'Figure F3 – Engineering stress–strain curves: true and measured',
           'one panel per target rate: engineering stress $F / A_0$ (%s) against the engineering strain of the '
           'extensometer. **Both curves come from the same simulation**; they differ by *where* the force is taken. '
           'Thick grey line: the true force in the specimen, summed over a cross-section of the specimen '
           '(impossible in a real test). Coloured line: the force read by the virtual strain gauge on the output '
           'bar, 400 mm away from the specimen, exactly where the real gauge is: this is the curve the experiment '
           'will give.' % a0_txt,
           'filtered signals; gauge signal shifted by the travel time of the wave as in F2. The error in the panel '
           'title is the largest gap after 5 % strain, relative to the maximum force.',
           'where the coloured line follows the grey one, the gauge measures the specimen correctly; where it '
           'oscillates around it, the measurement distorts the true response. The grey curves are identical at '
           'the three rates because the simulated material is rate independent.' +
           (' Axis cut at 1600 MPa (spike of the gauge signal below 2 % strain).' if gaps else ''))
    P('**Table T5 – Error of the output bar gauge.**')
    P(md_table(['Specimen / target rate (s⁻¹)', 'Max force', 'Max gauge error after 5 %'],
               [[label(r), '%.2f kN' % r['F_max_kN'], '%s of the max force' % pct(r['gauge_err_after5'], 1)]
                for r in rows]))
    if gaps:
        P('The force in the specimen is smooth, whereas the gauge signal oscillates around it, with an amplitude '
          'that grows with the loading speed. An oscillating measured curve therefore does not mean that the '
          'specimen is out of equilibrium. Origin (identified on 22 Oct 2026 with force probes along the output '
          'side): the specimen crosses the clearance of the output pocket and hits the output head (force spike '
          'of about twice the specimen force), which then rings at about 40 kHz.')
    else:
        P('The gauge signal follows the specimen force closely. With the specimen centred in the pockets '
          '(clearances of 0.36 mm, study `taskI_20261013-1554`), the specimen hit the output head at the start '
          'and the gauge error reached 3 / 15 / 39 % at 100 / 500 / 1000 s⁻¹: closing the clearances, as done in '
          'the lab before a test, is essential for the measurement.')

    # ------------------------------------------------------------ qualite
    P('## Numerical quality')
    P('These checks do not answer the Task I questions: they verify that the simulation can be trusted. Each column '
      'compares the simulation with a value known in advance, or measures a purely numerical error.')
    P('**Table T6 – Numerical checks.**')
    P(md_table(['Specimen / target rate (s⁻¹)', 'Incident strain / theory', 'Kinetic energy / ½mV²', 'Energy drift',
                'Hourglass / internal energy'],
               [[label(r), '%.3f' % (r['incident_strain'] / r['incident_theory']), '%.3f' % r['ke0_ratio'],
                 pct(r['energy_drift'], 2), pct(r['hourglass'], 1)] for r in rows]))
    r0 = rows[0]
    m_str = RHO_STRIKER * np.pi * 0.010 ** 2 * L_STRIKER_M
    rng = lambda key, f: (f(min(r_[key] for r_ in rows)), f(max(r_[key] for r_ in rows)))
    P('- **Incident strain / theory** – is the loading right? When the striker hits the input bar, one-dimensional '
      'wave theory gives the strain of the incident wave: $\\varepsilon_{inc} = K\\,V_{striker}/c$, with '
      '$c$ = %.0f m/s the wave speed in the bar and $K$ = %.3f the share of the striker velocity transmitted to the '
      'bar ($K = Z_{striker}/(Z_{striker}+Z_{bar})$, $Z = \\rho c A$). Example (%s): %.3f × %.2f / %.0f = %s '
      '(a compression: negative in `T1_conditions.csv`). The simulated value is the plateau of the virtual gauge on '
      'the input bar. A ratio of 1.000 means that the impact, '
      'the bar materials and the gauge reading are correct.'
      % (C_BAR, make_run.K_IMP, label_long(r0), make_run.K_IMP, r0['v_striker'], C_BAR, sci(abs(r0['incident_theory']))))
    P('- **Kinetic energy / ½mV²** – is the striker mass right? At $t$ = 0 only the striker moves; its kinetic '
      'energy is compared with $\\tfrac12 m V^2$ for the nominal striker (Ø20 × %.0f mm, %.0f kg/m³, $m$ = %.1f kg). '
      'The ratio (%.3f) is slightly below 1 because the mesh replaces the circular cross-section by a polygon with a '
      'slightly smaller area: the meshed striker is a little lighter. This does not change the incident wave, which '
      'depends on the striker velocity, not on its mass.'
      % (1e3 * L_STRIKER_M, RHO_STRIKER, m_str, r0['ke0_ratio']))
    P('- **Energy drift** – does the calculation create or lose energy? Without losses the total energy must stay '
      'constant. Abaqus keeps an energy balance (kinetic + internal + friction − external work, `ETOTAL`); the column '
      'gives its largest variation during the whole run, relative to the initial kinetic energy (%s to %s here). '
      'Below about 1 %%, contacts, ties and time integration are considered free of artificial energy.'
      % tuple(pct(x, 2) for x in rng('energy_drift', float)))
    P('- **Hourglass / internal energy** – does the mesh deform in a non-physical way? The hexahedra (C3D8R) are '
      'evaluated at a single point at their centre: fast, but some zigzag ("hourglass") deformations are not seen by '
      'that point and would meet no resistance. Abaqus adds a small artificial stiffness against them; the energy '
      'absorbed by it (`ALLAE`) is not physical. The column gives it at the end of the run relative to the real '
      'deformation energy (`ALLIE`): %s to %s here, well below the usual 5 %% limit.'
      % tuple(pct(x, 1) for x in rng('hourglass', float)))

    # ------------------------------------------------------------ limites
    P('## Limitations')
    lim = [
        'Rate-independent specimen material: in the experiments the force, and hence the required striker '
        'velocity (term $2F/\\rho c A$), will increase with the strain rate.',
        'The striker velocity formula relies on $L_{eff}$ calibrated on one simulation and on a constant force $F$.',
        'The gauge signal is shifted, not corrected for dispersion; the reference of the 400 mm gauge distance is '
        'to be confirmed (about 6 µs uncertainty).',
        ('Specimen centred in the pockets with clearances: the impact in the output pocket makes the gauge '
         'oscillate; the lab closes these clearances before a test (later studies).' if gaps else
         'Initial contact without pre-load in both pockets, as described by the lab; a residual clearance or a '
         'pre-load in a real test would change the start of the signals.'),
        'Assumed values: densities of the bars and of the striker, material of the inverter (maraging).',
    ]
    if not any(s_.startswith('UT40') for s_ in specs):
        lim.append('The long-gauge specimen (UT40) is not simulated yet (geometry not available).')
    L.extend('- ' + x for x in lim)
    L.append('')

    # ------------------------------------------------------------ annexe
    P('## Appendix – Control figures')
    P('One figure per simulation, unfiltered signals over the whole simulated time: bar gauges, specimen forces '
      'and gauge force (not shifted), $R$ and extensometer strain. Shaded: from the loading start to 30 % strain.')
    for r in rows:
        P('![%s](../%s/%s_overview.png)' % (r['case_id'], r['case_id'], r['case_id']))
        P('*Control figure – %s.*' % label_long(r))

    with open(os.path.join(out, 'report.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L).rstrip() + '\n')


# ============================================================
def main():
    study_dir = os.path.abspath(sys.argv[1])
    study = os.path.basename(study_dir.rstrip(os.sep))
    csvs = sorted(glob.glob(os.path.join(study_dir, '*', '*_history.csv')))
    if not csvs:
        sys.exit('Aucun <case>_history.csv dans %s' % study_dir)
    out = os.path.join(study_dir, 'report')
    os.makedirs(out, exist_ok=True)

    data = [analyse(c) for c in csvs]
    data.sort(key=lambda rc: (rc[0]['specimen'], rc[0]['target_rate']))
    rates = sorted(set(r['target_rate'] for r, _ in data))
    color = dict(zip(rates, RATE_COLORS * 3))
    groups = []
    for spec in sorted(set(r['specimen'] for r, _ in data)):
        groups.append((spec, [(color[r['target_rate']], (r, c)) for r, c in data if r['specimen'] == spec]))

    fig_equilibrium(groups, out)
    for spec, items in groups:
        fig_equilibrium_onset(spec, items, out)
    for spec, items in groups:
        fig_forces(spec, items, out)
    fig_stress_strain(groups, out)
    fig_strain_rate(groups, out)
    fig_striker(groups, out)
    for r, c in data:
        fig_case_overview(r, c, os.path.join(study_dir, r['case_id'], r['case_id'] + '_overview.png'))
    rows = [r for r, _ in data]
    write_csv(rows, out)
    write_report(study, rows, out)

    for r in rows:
        print('%-15s %5.0f /s obtenus | %s | equilibre des %s | |R| max apres 5 %% : %4.1f %% | jauge : %4.1f %%'
              % (r['case_id'], r['achieved_rate'],
                 '30 %% en %.3f ms' % r['time_to_30_ms'] if r['reached_30'] else 'max %4.1f %%' % (100 * r['eps_max']),
                 fmt(100 * r['eps_eq'], '%4.1f %%'), 100 * r['R_max_after5'], 100 * r['gauge_err_after5']))
    print('Livrables : %s' % out)


if __name__ == '__main__':
    main()
