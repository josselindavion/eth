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
PULSE_MS = 2.0 * 5000.0 / 4720.0      # duree de l'impulsion du striker de 5 m
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

    Fi, Fo, eps = lp(d.F_sec_in_N.values), lp(d.F_sec_out_N.values), lp(d.eps_ext.values)
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

    # Debut de l'equilibre : premier instant a partir duquel |R| < 5 % jusqu'a la fin de la fenetre
    i_eq = None
    i_start = max(k0, int(np.argmax(eps >= EPS_START)))
    bad = valid & (np.abs(np.nan_to_num(R)) >= EQ_TOL)
    last_bad = np.nonzero(bad[:i_end + 1])[0]
    cand = i_start if len(last_bad) == 0 else max(i_start, last_bad[-1] + 1)
    if cand < i_end:
        i_eq = cand
    plateau = win & (eps >= EPS_PLATEAU)
    hi = min(0.25, 0.8 * eps[i_end])
    rate_win = plateau & (eps <= hi)
    iF = k0 + int(np.argmax(Fi[k0:i_end + 1]))
    g = plateau & ~np.isnan(Fg)
    inc = d.eps_gauge_in.values
    res = {
        'case_id': case, 'specimen': spec, 'target_rate': rate, 'v_striker': v, 'v_source': v_src,
        'incident_strain': np.median(inc[inc < 0.5 * inc.min()]),
        'achieved_rate': rate_t[rate_win].mean() if rate_win.any() else np.nan,
        't_load_ms': 1e3 * t[k0],
        'time_to_30_ms': 1e3 * (t[i_end] - t[k0]) if reached else np.nan,
        'eps_max': eps[i_end], 'reached_30': reached,
        'F_max_kN': Fi[iF] / 1e3, 'eps_at_Fmax': eps[iF],
        'eps_eq': eps[i_eq] if i_eq is not None else np.nan,
        't_eq_ms': 1e3 * (t[i_eq] - t[k0]) if i_eq is not None else np.nan,
        'R_max_after5': np.nanmax(np.abs(R[plateau])) if plateau.any() else np.nan,
        'dF_max_after5_kN': np.abs(Fi - Fo)[plateau].max() / 1e3 if plateau.any() else np.nan,
        'gauge_err_after5': (np.abs(Fg - Fo)[g].max() / Fi[iF]) if g.any() else np.nan,
        'hourglass': d.ALLAE_mJ.iloc[-1] / max(d.ALLIE_mJ.iloc[-1], 1e-12),
    }
    curves = {'t_ms': 1e3 * (t - t[k0]), 'eps': eps, 'Fi': Fi, 'Fo': Fo, 'Fg': Fg, 'R': R,
              'rate': rate_t, 'win': win, 'valid': valid}
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
        ax.set_yscale('log')
        ax.set_ylim(30, 3000)
        ax.set_xlim(0, 32)
        ax.set_xlabel('engineering strain (%)')
        ax.set_ylabel('strain rate (s$^{-1}$)')
        ax.set_title('%s  (dotted: target)' % spec, loc='left')
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


def case_sentence(r):
    s = '- **%s, %d s⁻¹** (striker %.2f m/s): ' % (r['specimen'], r['target_rate'], r['v_striker'])
    if r['reached_30']:
        s += '30 %% strain reached %.2f ms after loading start, at %.0f s⁻¹. ' % (
            r['time_to_30_ms'], r['achieved_rate'])
    else:
        s += ('30 %% strain is **not reached**: the strain stops at %s when the %.2f ms pulse ends '
              '(%.0f s⁻¹). ' % (pct(r['eps_max'], 1), PULSE_MS, r['achieved_rate']))
    if not np.isnan(r['eps_eq']) and r['R_max_after5'] < EQ_TOL:
        s += ('Force equilibrium (|R| < %d %%) is established at %s strain (%.2f ms after loading start) '
              'and holds until the end of the useful window (max |R| after 5 %% strain: %s).' % (
                  round(100 * EQ_TOL), pct(r['eps_eq'], 1), r['t_eq_ms'], pct(r['R_max_after5'], 1)))
    else:
        s += ('Force equilibrium is **not maintained**: after 5 %% strain |R| reaches %s '
              '(|F_in - F_out| up to %.2f kN, i.e. %s of the maximum force)%s.' % (
                  pct(r['R_max_after5'], 1), r['dF_max_after5_kN'],
                  pct(r['dF_max_after5_kN'] / r['F_max_kN'], 1),
                  '' if np.isnan(r['eps_eq']) else
                  '; |R| stays below %d %% only from %s strain onwards' % (round(100 * EQ_TOL), pct(r['eps_eq'], 1))))
    return s


def write_report(study, rows, table, out):
    specs = sorted(set(r['specimen'] for r in rows))
    rate_min = EPS_TARGET / (PULSE_MS * 1e-3)
    v_note = sorted(set(r['v_source'] for r in rows))
    L = []
    L.append('# Task I - Force equilibrium and loading speeds in the SHPB with load inversion device\n')
    L.append('Study `%s`, specimens: %s. Generated by `scripts/post/report_taskI.py`; '
             'all numbers below are computed from the simulation outputs.\n' % (study, ', '.join(specs)))
    L.append('## 1. Simulation and signal processing\n')
    L.append(
        'The complete bench (5 m striker, 6.01 m input bar, load inversion device, output bar and specimen) '
        'is modelled in Abaqus/Explicit using the symmetry plane (half model), without mass scaling. '
        'The specimen material is DP1000 with a rate-independent von Mises / isotropic hardening law: '
        'differences between strain rates therefore come from wave propagation and inertia only, '
        'not from material rate sensitivity.\n')
    L.append(
        'The simulated signals are processed as in the experiments. Forces and strain are low-pass filtered '
        '(4th-order Butterworth, %d kHz cut-off, zero phase), the cut-off used for the output bar strain gauge '
        'signal in the laboratory. The axial force is taken in two cross-sections at both ends of the specimen '
        'parallel section (F_in on the load inversion device side, F_out on the output bar side) and, as in '
        'the experiment, from the strain gauge on the output bar (F = A E ε). The gauge signal is shifted '
        'in time by %.0f mm / %.0f m/s = %.0f µs to the specimen (no dispersion correction). The engineering '
        'strain is measured by a %d mm virtual extensometer on the parallel section, equivalent to the DIC '
        'extensometer.\n' % (FC_HZ / 1e3, GAUGE_TO_SPEC_MM, C_BAR, 1e3 * GAUGE_TO_SPEC_MM / C_BAR, 12))
    L.append(
        'Force equilibrium is quantified by R = (F_in - F_out) / F_mean with F_mean = (F_in + F_out) / 2. '
        'The specimen is considered in equilibrium when |R| < %d %%. The reported equilibrium strain is the '
        'strain from which |R| stays below this limit until 30 %% strain (or until the end of loading). '
        'The achieved strain rate is the slope of the extensometer strain between 5 %% strain and '
        'min(25 %%, 0.8 x maximum strain), i.e. the strain gained in this interval divided by the time taken. '
        'The interval excludes the start-up transient (rise of the incident pulse, settling of the specimen '
        'shoulders in the pockets, build-up of the specimen force up to its maximum at about 5 %% strain) and the '
        'end of the loading, so that it covers the established regime described by the striker velocity '
        'estimate (section 2). The complete strain rate history is given in F4.\n'
        % round(100 * EQ_TOL))
    L.append('## 2. Results\n')
    L.append('**Table T1** - Test conditions and equilibrium indicators (`T1_conditions.csv`).\n')
    L.append(table + '\n')
    L.append('Striker velocities taken from: %s.\n' % ', '.join(v_note))
    L.append('### Force equilibrium\n')
    L.append('![F1](F1_equilibrium.png)\n')
    L.append('**Figure F1** - Equilibrium ratio R as a function of the engineering strain. '
             'Shaded band: |R| < %d %%.\n' % round(100 * EQ_TOL))
    for spec in specs:
        L.append('![F2](F2_forces_%s.png)\n' % spec)
        L.append('**Figure F2 (%s)** - Forces at the specimen input and output sections and force measured by '
                 'the output bar gauge, shifted to the specimen.\n' % spec)
    L.extend([case_sentence(r) for r in rows])
    L.append('')
    L.append(
        'In all cases the first few tens of microseconds show a short force pulse followed by a drop to zero '
        'before continuous loading starts (F2). This is most likely the impact of the specimen shoulders in the '
        'clamping pockets, the specimen being inserted without pre-load; it produces the large values of R '
        'below about 2 % strain in F1.\n')
    L.append(
        'Since the force decreases after the maximum (necking), the same force difference gives a larger '
        'ratio R late in the test. The maximum absolute difference |F_in - F_out| after 5 % strain is '
        'therefore also given in Table T1.\n')
    L.append('### Measured stress-strain response\n')
    L.append('![F3](F3_stress_strain.png)\n')
    L.append('**Figure F3** - Engineering stress-strain curves as they would be measured (output bar gauge / A0, '
             'extensometer strain), compared with the exact force in the specimen output section (dotted).\n')
    for r in rows:
        L.append('- %s, %d s⁻¹: maximum force %.2f kN at %s strain; the output bar gauge deviates from the '
                 'specimen force by up to %s of the maximum force after 5 %% strain.' % (
                     r['specimen'], r['target_rate'], r['F_max_kN'], pct(r['eps_at_Fmax'], 1),
                     pct(r['gauge_err_after5'], 1)))
    L.append('')
    L.append(
        'The force in the specimen itself is smooth, whereas the output bar gauge signal oscillates around it, '
        'with an amplitude that grows with the loading speed. These oscillations are generated between the '
        'specimen and the gauge (clamping head of the output bar) and would be present in the measured '
        'stress-strain curve.\n')
    L.append('### Loading speeds\n')
    L.append('![F4](F4_strain_rate.png)\n')
    L.append('**Figure F4** - Strain rate (extensometer) as a function of the engineering strain; '
             'dotted lines: target rates.\n')
    L.append('![F5](F5_striker_velocity.png)\n')
    L.append('**Figure F5** - Striker velocity (vertical axis, setting of the test) required for a given strain '
             'rate (horizontal axis). Line: estimate used to set up the simulations. Dots: simulations, placed at '
             'the striker velocity imposed and at the strain rate achieved (slope between 5 %% and 25 %% strain, '
             'see section 1).\n')
    L.append(
        'The striker velocity is estimated from the elongation rate of the load inversion device, '
        'v ≈ 2 v_i - 2 F / (ρ c A), where v_i = 0.487 V_striker is the particle velocity of the incident '
        'wave and F the specimen force: the specimen force both slows the inverter and pushes the output '
        'bar. With an effective length of 12.7 mm and F = 7 kN for the UT19 specimen this gives '
        'V_striker = (ε̇ × 12.7 mm + 2F/ρcA) / (2 × 0.487). '
        'With the 5 m striker the loading pulse lasts %.2f ms, so 30 %% strain requires at least '
        '0.30 / %.2f ms ≈ %.0f s⁻¹ (shaded region in F5).\n' % (PULSE_MS, PULSE_MS, rate_min))
    L.append('## 3. Limitations\n')
    L.append(
        '- Rate-independent specimen material: in the experiments the force level, and hence the required '
        'striker velocity, will increase with the strain rate.\n'
        '- The output bar gauge signal is shifted, not corrected for dispersion; the exact reference of the '
        '400 mm gauge distance is to be confirmed (about 6 µs uncertainty).\n'
        '- Numerical quality: the hourglass energy stays below %s of the internal energy in all cases.\n'
        % pct(max(r['hourglass'] for r in rows), 1))
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
