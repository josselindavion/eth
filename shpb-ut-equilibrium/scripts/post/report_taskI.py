# -*- coding: utf-8 -*-
"""
report_taskI.py -- Livrables de la Task I (courbes + tableau + texte en anglais) pour une etude.

Lancement (PC, Python 3 + numpy, pandas, matplotlib, scipy), depuis la racine du repo :
    python shpb-ut-equilibrium/scripts/post/report_taskI.py shpb-ut-equilibrium/results/taskI_20261013-1554

Entrees, dans results/<etude>/<case>/ (rapatriees par scripts/hpc/fetch_study.py) :
    <case>_history.csv     courbes extraites du .odb (scripts/post/extract_history.py)
    <case>_paras.inp       parametres du calcul (vitesse du striker) ; sinon formule de make_run.py
Sorties, dans results/<etude>/report/ :
    T1_conditions.csv               une ligne par calcul (conditions d'essai, equilibre, qualite)
    F1_equilibrium.pdf / .png       R = (F_in - F_out) / F_moyen en fonction de la deformation
    F2_forces_<SPEC>.pdf / .png     forces SEC_IN, SEC_OUT et jauge de sortie ramenee a l'eprouvette
    F3_stress_strain.pdf / .png     contrainte nominale (jauge de sortie / A0) - deformation (extensometre)
    F4_strain_rate.pdf / .png       vitesse de deformation en fonction de la deformation
    F5_striker_velocity.pdf / .png  abaque vitesse du striker -> vitesse de deformation
    report.md                       texte (anglais) avec les chiffres, le tableau et les figures

Traitement des signaux (comme au labo, voir docs/results.md) :
  - filtre passe-bas Butterworth d'ordre 4 a 100 kHz, sans dephasage (filtfilt), applique aux forces
    et a la deformation AVANT de calculer R (le labo filtre la jauge de sortie a 100 kHz) ;
  - jauge de sortie ramenee a l'eprouvette par un simple decalage en temps de 400 mm / 4871 m/s
    (pas de correction de dispersion) ;
  - deformation nominale = extensometre virtuel de 12 mm (equivalent de la correlation d'images).
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
    'UT40': None,            # geometrie pas encore disponible
}
# Couleurs : une par vitesse visee, dans l'ordre (palette categorielle validee, 3 premieres places)
RATE_COLORS = ['#2a78d6', '#eb6834', '#1baf7a']
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
    best, run = (np.nan, np.nan), None
    for i in range(i_start, i_end + 1):
        if not bad[i]:
            run = i if run is None else run
            if np.isnan(best[0]) or eps[i] - eps[run] > best[1] - best[0]:
                best = (eps[run], eps[i])
        else:
            run = None
    return i_eq, best


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
    i_eq, eq_int = equilibrium(R, valid, eps, k0, i_end)
    # Meme chose sans filtre (pour montrer l'effet du filtre)
    Fm_raw = 0.5 * (Fi_raw + Fo_raw)
    valid_raw = win & (Fm_raw > 0.1 * Fm_raw[win].max())
    R_raw = np.where(valid_raw, (Fi_raw - Fo_raw) / np.where(valid_raw, Fm_raw, 1.0), np.nan)
    i_eq_raw, _ = equilibrium(R_raw, valid_raw, eps, k0, i_end)

    plateau = win & (eps >= EPS_PLATEAU)
    hi = min(0.25, 0.8 * eps[i_end])
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
        'incident_strain': np.median(inc[inc < 0.5 * inc.min()]),
        'incident_theory': -make_run.K_IMP * v / C_BAR,
        'achieved_rate': achieved,
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
              'rate': rate_t, 'win': win, 'valid': valid, 'iF': iF}
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
    fig, axs = new_axes(len(groups), w=5.6)
    for ax, (spec, items) in zip(axs, groups):
        A0 = A0_MM2.get(spec)
        if not A0:
            continue
        for col, (r, c) in items:
            m = c['win']
            ax.plot(100 * c['eps'][m], c['Fg'][m] / A0, color=col, lw=1.4, label=rate_label(r))
            ax.plot(100 * c['eps'][m], c['Fo'][m] / A0, color=col, lw=0.9, ls=':')
        ax.plot([], [], color=INK2, lw=1.4, label='from output bar gauge')
        ax.plot([], [], color=INK2, lw=0.9, ls=':', label='specimen section (exact)')
        ax.set_xlim(0, 32)
        ax.set_ylim(0, 1600)                  # le pic initial de la jauge (< 2 %) est coupe
        ax.set_xlabel('engineering strain (%)')
        ax.set_ylabel('engineering stress (MPa)')
        ax.set_title('%s  (A$_0$ = %.1f mm$^2$)' % (spec, A0), loc='left')
        ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1.0), fontsize=8)
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
    fig, axs = new_axes(1, w=4.6, h=3.2)
    ax = axs[0]
    rate_min = EPS_TARGET / (PULSE_MS * 1e-3)
    ax.axvspan(0, rate_min, color=BAND, zorder=0)
    ax.text(rate_min * 0.5, 17.5, '30 %\nnot\nreachable', ha='center', va='top', color=INK2, fontsize=8)
    rr = np.linspace(20, 1300, 200)
    for spec, items in groups:
        if make_run.SPECIMENS.get(spec):
            ax.plot(rr, [make_run.striker_velocity(spec, x) for x in rr], color=INK2, lw=1.0,
                    label='%s, estimate (make_run.py)' % spec)
        for col, (r, c) in items:
            ax.plot(r['achieved_rate'], r['v_striker'], 'o', ms=7, color=col, mec='white', mew=1.2,
                    label='%s, simulated, target %s' % (spec, rate_label(r)))
    ax.set_xlim(0, 1300)
    ax.set_ylim(0, 18)
    ax.set_xlabel('achieved strain rate (s$^{-1}$)')
    ax.set_ylabel('striker velocity (m/s)')
    ax.legend(loc='lower right', fontsize=8)
    save(fig, out, 'F5_striker_velocity')


# ============================================================
# TABLEAU ET TEXTE
# ============================================================
T1_COLS = [
    ('specimen', 'specimen', '%s'),
    ('target_rate', 'target rate (1/s)', '%.0f'),
    ('v_striker', 'striker velocity (m/s)', '%.2f'),
    ('incident_strain', 'incident strain (-)', '%.2e'),
    ('achieved_rate', 'achieved rate (1/s)', '%.0f'),
    ('time_to_30_ms', 'time to 30 % (ms)', '%.3f'),
    ('eps_max', 'max strain reached (-)', '%.3f'),
    ('F_max_kN', 'max force (kN)', '%.2f'),
    ('eps_at_Fmax', 'strain at max force (-)', '%.3f'),
    ('eps_eq', 'equilibrium from strain (-)', '%.3f'),
    ('t_eq_ms', 'equilibrium after (ms)', '%.3f'),
    ('R_max_after5', 'max |R| after 5 % (-)', '%.3f'),
    ('dF_max_after5_kN', 'max |dF| after 5 % (kN)', '%.2f'),
    ('gauge_err_after5', 'max gauge error after 5 % (-)', '%.3f'),
    ('hourglass', 'hourglass / internal energy (-)', '%.3f'),
]


def fmt(val, f):
    if isinstance(val, float) and np.isnan(val):
        return 'n/a'
    return f % val


def write_table(rows, out):
    df = pd.DataFrame([{label: r[k] for k, label, _ in T1_COLS} for r in rows])   # NaN -> case vide
    df.insert(0, 'case_id', [r['case_id'] for r in rows])
    df.to_csv(os.path.join(out, 'T1_conditions.csv'), index=False, float_format='%.4g')
    head = '| ' + ' | '.join(['case'] + [lab.replace('|', '\\|') for _, lab, _ in T1_COLS[1:]]) + ' |'
    sep = '|' + '---|' * len(T1_COLS)
    lines = [head, sep]
    for r in rows:
        lines.append('| ' + ' | '.join([r['case_id']] + [fmt(r[k], f) for k, _, f in T1_COLS[1:]]) + ' |')
    return '\n'.join(lines)


def pct(x, nd=0):
    return ('%.' + str(nd) + 'f %%') % (100 * x)


def md_table(header, lines):
    def esc(c):
        return c.replace('|', '\\|')                      # un | dans une case casse le tableau
    out = ['| ' + ' | '.join(esc(c) for c in header) + ' |', '|' + '---|' * len(header)]
    out += ['| ' + ' | '.join(esc(c) for c in l) + ' |' for l in lines]
    return '\n'.join(out)


def eq_ok(r):
    return (not np.isnan(r['eps_eq'])) and r['R_max_after5'] < EQ_TOL


def eq_verdict(r):
    if eq_ok(r):
        return 'yes, from %s strain' % pct(r['eps_eq'], 1)
    s = 'partial: |R| < %d %%' % round(100 * EQ_TOL)
    if not np.isnan(r['eq_from']):
        s += ' from %s to %s strain' % (pct(r['eq_from'], 0), pct(r['eq_to'], 0))
    return s + ', up to %s elsewhere after 5 %% strain' % pct(r['R_max_after5'], 0)


def needed_striker(r):
    """Longueur de striker necessaire pour 30 % a la vitesse obtenue (demarrage compris)."""
    t_ms = 1e3 * EPS_TARGET / r['achieved_rate'] + r['startup_ms']
    return t_ms, C_STRIKER * t_ms * 1e-3 / 2.0


def case_sentence(r):
    s = '- **%s, %d s⁻¹** (striker %.2f m/s): ' % (r['specimen'], r['target_rate'], r['v_striker'])
    if eq_ok(r):
        s += ('force equilibrium (|R| < %d %%) is established at %s strain (%.2f ms after loading start) '
              'and holds until the end of the loading (max |R| after 5 %% strain: %s).' % (
                  round(100 * EQ_TOL), pct(r['eps_eq'], 1), r['t_eq_ms'], pct(r['R_max_after5'], 1)))
    else:
        s += 'force equilibrium is **only partly reached**: '
        if not np.isnan(r['eq_from']):
            s += '|R| stays below %d %% from %s to %s strain, ' % (
                round(100 * EQ_TOL), pct(r['eq_from'], 1), pct(r['eq_to'], 1))
        s += ('but reaches %s at other instants after 5 %% strain (|F_in - F_out| up to %.2f kN, '
              'i.e. %s of the maximum force).' % (pct(r['R_max_after5'], 1), r['dF_max_after5_kN'],
                                                 pct(r['dF_max_after5_kN'] / r['F_max_kN'], 1)))
    return s


def write_report(study, rows, table, out):
    specs = sorted(set(r['specimen'] for r in rows))
    rate_min = EPS_TARGET / (PULSE_MS * 1e-3)
    v_note = sorted(set(r['v_source'] for r in rows))
    tol = round(100 * EQ_TOL)
    L = []
    L.append('# Task I - Force equilibrium and loading speeds in the SHPB with load inversion device\n')
    L.append('Study `%s`, specimens: %s. Generated by `scripts/post/report_taskI.py`; all numbers in the '
             'results sections are computed from the simulation outputs.\n' % (study, ', '.join(specs)))
    L.append('Questions of Task I: (1) can quasi-static force equilibrium be achieved in the specimen at '
             'nominal strain rates of 100, 500 and 1000 s⁻¹, and (2) which loading speeds are required to '
             'reach an engineering strain of 30 %?\n')

    # ---------------------------------------------------------------- 1
    L.append('## Model and assumptions\n')
    L.append(md_table(['Item', 'Model'], [
        ['Bench', 'Ø20 mm steel striker (5 m), maraging input bar (6.01 m), load inversion device (pusher), '
                  'specimen and output bar (≈ 6 m), as in Beerli et al. (2026); virtual strain gauges at '
                  '400 mm on the input and output bars'],
        ['Symmetry', 'half model (symmetry plane through the bar axes)'],
        ['Mesh', 'bars and pusher rod: swept C3D8R, 5 mm axially, 2 mm in the section; pusher head and '
                 'output bar head: C3D10M tetrahedra, 2 mm (M4 holes removed, small fillets merged by virtual '
                 'topology); specimen: C3D8R, 0.5 mm in plane, 4 elements through the 1.5 mm thickness; '
                 '≈ 214 000 elements'],
        ['Solver', 'Abaqus/Explicit, double precision, **no mass scaling** (inertia is the studied effect); '
                   'initial stable time increment ≈ 2e-8 s'],
        ['Bars and pusher', 'linear elastic maraging steel, E = ρc² with the measured wave speed c = 4871 m/s '
                            'and ρ = 8000 kg/m³ (assumed); striker c = 4720 m/s, ρ = 7850 kg/m³ (assumed)'],
        ['Specimen', 'DP1000 (Beerli et al. 2026, table 4): E = 195 GPa, ν = 0.33, ρ = 7850 kg/m³, '
                     'von Mises yield surface, isotropic Swift-Voce hardening, **rate independent**, no thermal '
                     'effects, no fracture (same simplified material as the numerical study of the bench in '
                     'Beerli et al. 2026, §2.5.1)'],
        ['Contacts', 'striker / input bar and input bar / pusher: hard, frictionless; specimen shoulders / '
                     'clamping pockets: hard, friction 0.2 (Roth et al. 2015). The specimen lies in the pockets '
                     'without pre-load or top clamp'],
        ['Ties', 'pusher rod / pusher head and output bar / output bar head (change of mesh type)'],
        ['Guides', 'vertical displacement blocked on the sliding face of the pusher and on the axes of the '
                   'bars (slide and bearings of the bench). Without them the pusher pitched under the '
                   'eccentric load (output bar axis 21.5 mm above the input bar axis)'],
        ['Loading', 'initial velocity of the striker (Table T1)'],
    ]) + '\n')

    # ---------------------------------------------------------------- 2
    L.append('## Signal processing and definitions\n')
    L.append(
        'The simulated signals are processed as in the experiments. Forces and strain are low-pass filtered '
        '(4th-order Butterworth, %d kHz cut-off, zero phase), the cut-off used for the output bar strain gauge '
        'signal in the laboratory (Roth et al. 2015): the simulation writes one point per microsecond and '
        'contains vibrations of a few microseconds that the experiment cannot resolve. The effect of the filter '
        'is shown in Table T2.\n' % (FC_HZ / 1e3))
    L.append(
        'The force in the specimen is taken in two cross-sections at both ends of the parallel section '
        '(F_in on the load inversion device side, F_out on the output bar side). These exact forces are used '
        'to answer the equilibrium question. In the experiment only the strain gauge of the output bar is '
        'available (F = A E ε); its simulated signal is shifted in time by %.0f mm / %.0f m/s = %.0f µs to the '
        'specimen (no dispersion correction) and used only in the section "What the experiment will measure". The engineering strain is measured '
        'by a 12 mm virtual extensometer on the parallel section, equivalent to the DIC extensometer.\n'
        % (GAUGE_TO_SPEC_MM, C_BAR, 1e3 * GAUGE_TO_SPEC_MM / C_BAR))
    L.append(
        'Force equilibrium is quantified by R = (F_in - F_out) / F_mean with F_mean = (F_in + F_out) / 2, '
        'and the specimen is considered in equilibrium when |R| < %d %%. The equilibrium strain is the strain '
        'from which |R| stays below this limit until 30 %% strain (or until the end of loading). The loading '
        'start is the first instant where F_in exceeds 2 %% of its maximum.\n' % tol)
    L.append(
        'The achieved strain rate is the slope of the extensometer strain between 5 % strain and '
        'min(25 %, 0.8 x maximum strain), i.e. the strain gained in this interval divided by the time taken. '
        'The interval excludes the start-up transient (rise of the incident pulse, settling of the specimen '
        'shoulders in the pockets, build-up of the specimen force up to its maximum at about 5 % strain) and the '
        'end of the loading, so that it covers the established regime described by the striker velocity '
        'estimate (section "Loading speeds"). The complete strain rate history is given in F4 and other definitions in '
        'Table T3.\n')

    # ---------------------------------------------------------------- 3
    L.append('## Task I answers\n')
    L.append('**Table T1** - Test conditions and indicators (`T1_conditions.csv`).\n')
    L.append(table + '\n')
    L.append('Striker velocities taken from: %s.\n' % ', '.join(v_note))
    L.append(
        'Columns of T1: *incident strain*: plateau of the strain measured by the virtual gauge on the input bar; '
        '*achieved rate*: strain rate between 5 and 25 % strain (see above); *time to 30 %*: from the loading start; '
        '*max strain reached*: at 30 % or at the end of the pulse; *max force* and *strain at max force*: exact '
        'force in the input section; *equilibrium from strain* and *equilibrium after*: strain and time (from the '
        'loading start) from which |R| < 5 % holds until the end of loading, empty if never; *max |R| after 5 %* '
        'and *max |dF| after 5 %*: largest relative and absolute force difference between both ends of the '
        'specimen after 5 % strain; *max gauge error after 5 %*: largest difference between the force given by '
        'the output bar gauge and the exact specimen force, divided by the maximum force; *hourglass / internal '
        'energy*: numerical check (section "Numerical quality").\n')

    L.append('### Force equilibrium\n')
    L.append('![F1](F1_equilibrium.png)\n')
    L.append(
        '**Figure F1 - Force equilibrium in the specimen.** '
        '*Plotted:* the equilibrium ratio R = (F_in - F_out) / F_mean (vertical axis) against the engineering '
        'strain of the specimen (horizontal axis), one curve per target rate. '
        '*Where it comes from:* F_in and F_out are the exact axial forces in two cross-sections of the simulated '
        'specimen, at both ends of its parallel section (F_in on the load inversion device side, F_out on the '
        'output bar side), filtered at %d kHz; they are not measured by a strain gauge. The strain is given by the '
        '12 mm virtual extensometer on the specimen. '
        '*How to read it:* when a curve is inside the shaded band (|R| < %d %%), both ends of the specimen carry '
        'the same force: the specimen is in equilibrium. The large values below about 2 %% strain come from the '
        'start of loading (specimen shoulders settling in the pockets) and are cut at ±20 %%.\n'
        % (FC_HZ / 1e3, tol))
    L.extend([case_sentence(r) for r in rows])
    L.append('')
    L.append(
        'In all cases the first few tens of microseconds show a short force pulse followed by a drop to zero '
        'before continuous loading starts (F2). This is most likely the impact of the specimen shoulders in the '
        'clamping pockets, the specimen being inserted without pre-load; it produces the large values of R '
        'below about 2 % strain in F1.\n')
    L.append(
        'The maximum force is reached at about 5 to 8 % strain; the force then decreases (necking). The same '
        'force difference therefore gives a larger ratio R late in the test, which is why the maximum absolute '
        'difference |F_in - F_out| after 5 % strain is also given in Table T1.\n')
    L.append('**Table T2** - Effect of the %d kHz filter on the equilibrium indicators (exact section forces).\n'
             % (FC_HZ / 1e3))
    L.append(md_table(
        ['case', 'equilibrium from strain, unfiltered', 'equilibrium from strain, filtered',
         'max |R| after 5 %, unfiltered', 'max |R| after 5 %, filtered'],
        [[r['case_id'], fmt(100 * r['eps_eq_raw'], '%.1f %%'), fmt(100 * r['eps_eq'], '%.1f %%'),
          pct(r['R_max_after5_raw'], 1), pct(r['R_max_after5'], 1)] for r in rows]) + '\n')

    L.append('### Loading speeds\n')
    L.append('![F4](F4_strain_rate.png)\n')
    L.append(
        '**Figure F4 - Strain rate in the specimen.** '
        '*Plotted:* the strain rate (vertical axis, logarithmic scale) against the engineering strain (horizontal '
        'axis), one curve per target rate; dotted horizontal lines: target rates; dots: force maximum (onset of '
        'necking). '
        '*Where it comes from:* time derivative of the strain of the 12 mm virtual extensometer on the specimen '
        '(strain filtered at %d kHz before derivation). It is a kinematic quantity, equivalent to what DIC gives in '
        'the experiment; it is not a force and has nothing to do with the output bar gauge. '
        '*How to read it:* the curve should stay close to its dotted target line. Being a derivative, it amplifies '
        'small vibrations of the specimen: the oscillations of about ±10 to 30 %% around the mean (period of about '
        '10 to 20 µs at 1000 s⁻¹) are such vibrations; on the logarithmic scale the 100 s⁻¹ curve looks noisier '
        'than it is. A curve that drops before 30 %% strain (100 s⁻¹, at about 18 %%) shows the end of the loading '
        'pulse. Mean values are given in Table T3.\n' % (FC_HZ / 1e3))
    L.append('**Table T3 - Strain rate of each simulation with different definitions (s⁻¹).** '
             '*achieved*: strain gained between 5 and 25 % strain divided by the time taken (value used in T1 and '
             'F5); *at force maximum*: value of the F4 curve at the dot; *nominal*: final strain divided by the '
             'whole loading time (start-up included); *before / after force maximum*: range of the F4 curve '
             'before and after the dot (10 % of the points are below the first value, 10 % above the second).\n')
    L.append(md_table(
        ['case', 'target', 'achieved (5-25 %)', 'at force maximum', 'nominal (ε_end / loading time)',
         'before force maximum (10th-90th percentile)', 'after force maximum (10th-90th percentile)'],
        [[r['case_id'], '%.0f' % r['target_rate'], '%.0f' % r['achieved_rate'], '%.0f' % r['rate_at_Fmax'],
          '%.0f' % r['rate_nominal'], '%.0f to %.0f' % (r['rate_pre_p10'], r['rate_pre_p90']),
          '%.0f to %.0f' % (r['rate_post_p10'], r['rate_post_p90'])] for r in rows]) + '\n')
    L.append(
        'After the force maximum the strain rate is established close to the target and increases slowly, '
        'because the specimen force decreases (necking) and brakes the bench less. Before the force maximum, '
        'i.e. during the uniform hardening phase, the strain rate is not yet stable at the higher rates '
        '(negative values: rebound of the specimen in the pockets).\n')
    L.append('![F5](F5_striker_velocity.png)\n')
    L.append(
        '**Figure F5 - Striker velocity required for a given strain rate.** '
        '*Plotted:* the striker velocity (vertical axis), i.e. the setting of the test, against the strain rate '
        'in the specimen (horizontal axis). Line: the estimate V_striker = (ε̇ × L_eff + 2F/ρcA) / (2 × %.3f) '
        'explained below, used to choose the velocities of the simulations. Dots: the simulations, placed at the '
        'striker velocity that was imposed and at the strain rate that was achieved (5-25 %% window, Table T3). '
        'Shaded region: strain rates for which 30 %% strain cannot be reached with the 5 m striker. '
        '*How to read it:* choose a strain rate on the horizontal axis and read the striker velocity on the line. '
        'Dots lying on the line confirm the estimate.\n' % make_run.K_IMP)
    sp = make_run.SPECIMENS
    eff = '; '.join('L_eff = %.1f mm and F = %.0f kN for the %s' % (sp[s]['L_eff_mm'], sp[s]['F_N'] / 1e3, s)
                    for s in specs if sp.get(s))
    L.append(
        'The striker velocity is estimated from the elongation rate of the load inversion device, '
        'v ≈ 2 v_i - 2 F / (ρ c A), where v_i = %.3f V_striker is the particle velocity of the incident wave '
        '(impedance ratio of striker and bar) and F the specimen force: the specimen force both slows the '
        'inverter down and pushes the output bar. Hence V_striker = (ε̇ × L_eff + 2F/ρcA) / (2 × %.3f), with %s. '
        'L_eff is an effective gauge length relating the elongation rate to the extensometer strain rate; it was '
        'calibrated on a first simulation at 500 s⁻¹, and F is the typical specimen force (6.4 to 7.6 kN in the '
        'simulations). A first estimate without the force term (V = ε̇ × 15 mm) gave only 21 s⁻¹ instead of '
        '100 s⁻¹, because the specimen force is then almost as large as the force carried by the incident '
        'wave.\n' % (make_run.K_IMP, make_run.K_IMP, eff))
    L.append(
        '**Limit for 30 %% strain.** The 5 m striker gives a %.2f ms loading pulse, so 30 %% strain requires at '
        'least 0.30 / %.2f ms ≈ %.0f s⁻¹ (shaded region in F5); the output bar (5.99 m) also limits the '
        'measurement window to %.2f ms (Beerli et al. 2026).' % (PULSE_MS, PULSE_MS, rate_min, OUTPUT_WINDOW_MS))
    for r in rows:
        if not r['reached_30']:
            t_ms, l_m = needed_striker(r)
            L[-1] += (
                ' At %d s⁻¹ (%s), the strain stops at %s; reaching 30 %% would need a loading of about %.1f ms '
                '(0.30 / %.0f s⁻¹ + %.2f ms start-up), i.e. a striker of about %.1f m, almost the length of the '
                '%.1f m launch tube (no room left to accelerate it), and a loading longer than the measurement '
                'window of the output bar.' % (
                    r['target_rate'], r['specimen'], pct(r['eps_max'], 1), t_ms, r['achieved_rate'],
                    r['startup_ms'], l_m, LAUNCH_TUBE_M))
    L[-1] += '\n'

    # ---------------------------------------------------------------- 4
    L.append('## What the experiment will measure\n')
    L.append('In the experiment the force is only known from the output bar gauge. Figures F2 and F3 compare '
             'this signal, as it would be recorded, with the exact force in the specimen.\n')
    for s in specs:
        L.append('![F2](F2_forces_%s.png)\n' % s)
        L.append(
            '**Figure F2 (%s) - Forces in the specimen and force measured by the output bar gauge.** '
            '*Plotted:* the axial force (vertical axis) against the time from the start of loading (horizontal '
            'axis), one panel per target rate. Coloured solid line: exact force in the input section of the '
            'specimen (F_in); coloured dashed line: exact force in the output section (F_out); black line: force '
            'given by the virtual strain gauge on the output bar, as recorded in the experiment. '
            '*Where it comes from:* the gauge force is the axial stress of the gauge elements times the bar '
            'cross-section, shifted in time by %.0f µs (travel time of the wave over the %.0f mm between the '
            'specimen and the gauge) so that it can be compared with the specimen forces; all signals are filtered '
            'at %d kHz. '
            '*How to read it:* when the two coloured lines overlap, the specimen is in equilibrium; the distance '
            'between the black line and the coloured lines is the measurement error of the gauge.\n'
            % (s, 1e3 * GAUGE_TO_SPEC_MM / C_BAR, GAUGE_TO_SPEC_MM, FC_HZ / 1e3))
    L.append('![F3](F3_stress_strain.png)\n')
    a0 = ', '.join('A0 = %.1f mm² for the %s' % (A0_MM2[s_], s_) for s_ in specs if A0_MM2.get(s_))
    L.append(
        '**Figure F3 - Engineering stress-strain curves.** '
        '*Plotted:* engineering stress = force / initial cross-section of the parallel section (%s) on the '
        'vertical axis, against the engineering strain of the 12 mm extensometer on the horizontal axis; one colour '
        'per target rate. Solid line: force from the output bar gauge, i.e. the curve that the experiment will '
        'give. Dotted line: exact force in the output section of the specimen. '
        '*How to read it:* the gap between the solid and the dotted line of the same colour is the error of the '
        'measured curve. As the simulated material is rate independent, the dotted curves of the three rates '
        'coincide. The vertical axis is cut at 1600 MPa (spike of the gauge signal below 2 %% strain).\n' % a0)
    for r in rows:
        L.append('- %s, %d s⁻¹: maximum force %.2f kN at %s strain; the output bar gauge deviates from the '
                 'specimen force by up to %s of the maximum force after 5 %% strain.' % (
                     r['specimen'], r['target_rate'], r['F_max_kN'], pct(r['eps_at_Fmax'], 1),
                     pct(r['gauge_err_after5'], 1)))
    L.append('')
    L.append(
        'The force in the specimen is smooth, whereas the output bar gauge signal oscillates around it, with an '
        'amplitude that grows with the loading speed. An oscillating measured curve therefore does not mean '
        'that the specimen is out of equilibrium. The origin of these oscillations has not been identified yet: '
        'they appear between the specimen and the gauge and may come from the clamping head of the output bar '
        'or from its modelling (tetrahedral mesh tied to the bar). This must be checked before comparing with '
        'the experiments.\n')

    # ---------------------------------------------------------------- 5
    L.append('## Numerical quality\n')
    L.append(md_table(
        ['case', 'incident strain, simulated / theory', 'initial kinetic energy / ½ m V²',
         'total energy drift / initial energy', 'hourglass / internal energy'],
        [[r['case_id'], '%.3f' % (r['incident_strain'] / r['incident_theory']), '%.3f' % r['ke0_ratio'],
          pct(r['energy_drift'], 2), pct(r['hourglass'], 1)] for r in rows]) + '\n')
    L.append('Theory: incident strain = %.3f V_striker / c; ½ m V² with the nominal striker mass. The small '
             'differences come from the faceted mesh of the cylinders. The hourglass energy stays well below the '
             'usual 5 %% limit.\n' % make_run.K_IMP)

    # ---------------------------------------------------------------- 6
    L.append('## Limitations\n')
    lim = [
        'Rate-independent specimen material: in the experiments the force level, and hence the required '
        'striker velocity (term 2F/ρcA), will increase with the strain rate.',
        'The striker velocity estimate relies on L_eff calibrated on one simulation and on a constant specimen '
        'force F.',
        'The output bar gauge signal is shifted, not corrected for dispersion; the exact reference of the '
        '400 mm gauge distance is to be confirmed (about 6 µs uncertainty).',
        'The origin of the oscillations of the output bar gauge (section "What the experiment will measure") '
        'is not identified yet.',
        'Assumed values: densities of the bars and of the striker, material of the pusher (maraging).',
    ]
    if 'UT40' not in specs:
        lim.append('The long-gauge specimen (UT40) is not simulated yet (geometry not available).')
    L.append('\n'.join('- ' + x for x in lim) + '\n')

    # ---------------------------------------------------------------- 7
    L.append('## Conclusions\n')
    concl = []
    for r in rows:
        if r['reached_30']:
            s30 = 'yes, in %.2f ms' % r['time_to_30_ms']
        else:
            s30 = 'no: %s max (pulse too short)' % pct(r['eps_max'], 1)
        concl.append([r['specimen'], '%d s⁻¹' % r['target_rate'], eq_verdict(r),
                      '%.2f m/s (%.0f s⁻¹ achieved)' % (r['v_striker'], r['achieved_rate']), s30,
                      pct(r['gauge_err_after5'], 0)])
    L.append(md_table(['specimen', 'target rate', 'force equilibrium (|R| < %d %%)' % tol,
                       'striker velocity', '30 % reached', 'max error of the output gauge'], concl) + '\n')
    L.append(
        '- Equilibrium is reached early and maintained at the lower rates; at the highest rate it is only '
        'partly reached, the largest differences occurring late in the test, when the force decreases.\n'
        '- The striker velocity must account for the specimen force (V_striker formula, F5); 30 %% strain cannot '
        'be reached below about %.0f s⁻¹ with the 5 m striker.\n'
        '- Even when the specimen is in equilibrium, the output bar gauge oscillates around the specimen force: '
        'this has to be considered when assessing the quality of the measured curves.\n' % rate_min)
    with open(os.path.join(out, 'report.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


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
        fig_forces(spec, items, out)
    fig_stress_strain(groups, out)
    fig_strain_rate(groups, out)
    fig_striker(groups, out)
    rows = [r for r, _ in data]
    write_report(study, rows, write_table(rows, out), out)

    for r in rows:
        print('%-15s %5.0f /s obtenus | %s | equilibre des %s | |R| max apres 5 %% : %4.1f %% | jauge : %4.1f %%'
              % (r['case_id'], r['achieved_rate'],
                 '30 %% en %.3f ms' % r['time_to_30_ms'] if r['reached_30'] else 'max %4.1f %%' % (100 * r['eps_max']),
                 fmt(100 * r['eps_eq'], '%4.1f %%'), 100 * r['R_max_after5'], 100 * r['gauge_err_after5']))
    print('Livrables : %s' % out)


if __name__ == '__main__':
    main()
