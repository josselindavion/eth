# -*- coding: utf-8 -*-
"""
report_taskI_final.py -- Rapport FINAL de la Task I (anglais) : UT19 + UT40 reunis, pour les encadrants.

Reprend l'analyse de report_taskI.py (memes definitions, meme filtre, memes figures) sur les deux etudes de
reference, et y ajoute tout ce qui a ete appris pendant la Task I :
    - comparaison UT19 / UT40 ;
    - effet de la mise en contact initiale (UT19 centree avec jeux, etude taskI_20261013-1554) ;
    - premier calcul UT40 (vitesses estimees, etude taskI_20261023-1140) et recalage de la formule du striker ;
    - sondes de force le long de la sortie ;
    - diagnostic de la localisation brutale (images Abaqus/Viewer du journal du 27/10) ;
    - rupture du DP1000, validite des resultats ; historique des etudes ; statistiques de calcul.

Lancement (PC, Python 3), racine du repo :
    python shpb-ut-equilibrium/scripts/post/report_taskI_final.py
Sortie : shpb-ut-equilibrium/results/taskI_final/ (report.md, figures .png/.pdf, img/ = images copiees,
         T_all_runs.csv = tous les indicateurs de tous les calculs)
Les numeros de figures et de tableaux sont attribues automatiquement dans l'ordre d'apparition.
"""
import glob
import os
import re
import shutil
import sys

import numpy as np
import pandas as pd

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, THIS_DIR)
import report_taskI as rt                 # noqa: E402  (analyse, figures et helpers communs)
from report_taskI import pct, fmt, md_table, label, label_long, eq_ok, eq_short   # noqa: E402

plt = rt.plt
make_run = rt.make_run

PROJECT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
REPO = os.path.abspath(os.path.join(PROJECT, '..'))
RESULTS = os.path.join(PROJECT, 'results')
OUT = os.path.join(RESULTS, 'taskI_final')

# Etudes de reference (une par eprouvette) et etudes d'historique
REF = {'UT19': 'taskI_20261022-1138', 'UT40': 'taskI_20261023-1518'}
CENTRED_UT19 = 'taskI_20261013-1554'     # UT19 centree dans les logements (jeux de 0,36 mm)
FIRST_UT40 = 'taskI_20261023-1140'       # UT40, vitesses du striker estimees (L_eff 34 mm, F 15 kN)
PROBE_RUNS = [                           # (etude, calcul, legende)
    ('diag_20261021-1626', 'UT19_R1000_P1', 'UT19 / 1000, centred (gaps)'),
    ('taskI_20261022-1138', 'UT19_R1000_00', 'UT19 / 1000, in contact'),
    ('taskI_20261023-1140', 'UT40_R1000_00', 'UT40 / 1000, first run (37.4 m/s)'),
    ('taskI_20261023-1518', 'UT40_R1000_00', 'UT40 / 1000, recalibrated (32.6 m/s)'),
]
# Images copiees du journal (captures Abaqus, geometrie) : (source relative au repo, nom dans img/)
JOURNAL_IMG = [
    'journal/figures/2026-10-22/pocket_contact_UT19.png',
    'journal/figures/2026-10-22/cae_assembly_contact_UT19.png',
    'journal/figures/2026-10-22/gap_impact_UT19_R1000.png',
    'journal/figures/2026-10-23/UT40_vs_UT19_outline.png',
    'journal/figures/2026-10-23/UT40_head_vs_UT19_tip_aligned.png',
    'journal/figures/2026-10-23/UT40_pocket_contact.png',
    'journal/figures/2026-10-23/UT40_R1000_PEEQ_last_frame.png',
    'journal/figures/2026-10-27/ecart_dents_UT40_R0500.png',
    'journal/figures/2026-10-27/U3_frame79.png',
    'journal/figures/2026-10-27/U3_frame81.png',
    'journal/figures/2026-10-27/U3_frame83.png',
    'journal/figures/2026-10-27/PEEQ_frame79.png',
    'journal/figures/2026-10-27/PEEQ_frame81.png',
    'journal/figures/2026-10-27/PEEQ_frame83.png',
]
# Geometrie et maillage (sorties de build_bench.py imprimees dans Abaqus/CAE, journal 22/10 et 23/10)
SPEC_INFO = {
    'UT19': {'source': 'STEP file of the lab (`cad/step/XMas_UT_t1p5.step`)', 'length': '77.688',
             'gauge': '15.0 × 5.0', 'elem_spec': '12 360', 'elem_gauge': '600 (30 × 5 × 4)',
             'elem_total': '213 977', 'gap_pusher': 0.3567, 'gap_output': 0.3563, 'bar_end': '155.000',
             'gauge_y': '−245.000', 'clear_p': 0.6385, 'clear_o': 0.5222},
    'UT40': {'source': 'cutting drawing `cad/dxf/Xmas_UT40.dxf`, extruded to 1.5 mm '
                       '(`scripts/pre/dxf_to_step.py`)', 'length': '103.181',
             'gauge': '40.077 × (10.020 → 10.001)', 'elem_spec': '15 324', 'elem_gauge': '3 200 (80 × 10 × 4)',
             'elem_total': '216 951', 'gap_pusher': -0.0365, 'gap_output': 0.2562, 'bar_end': '130.000',
             'gauge_y': '−270.000', 'clear_p': 0.5321, 'clear_o': 0.4222},
}
# DP1000 : loi de Swift-Voce (Beerli et al. 2026, table 4) -- pour la vitesse des ondes plastiques
SV = dict(A=1395.0, e0=1e-6, n=0.0892, k0=739.0, Q=301.0, beta=102.0, alpha=0.5, E=195000.0, rho=7850.0)
Z_BAR = make_run.Z_BARRE
K = make_run.K_IMP
RHO_C_BAR = make_run.RHO_BARRE * make_run.C_BARRE


# ============================================================
# DONNEES
# ============================================================
def load(study):
    csvs = sorted(glob.glob(os.path.join(RESULTS, study, '*', '*_history.csv')))
    data = [rt.analyse(c) for c in csvs]
    for r, c in data:
        r['study'] = study
        r.update(run_stats(os.path.join(RESULTS, study, r['case_id'], r['case_id'] + '.sta')))
        c['csv'] = os.path.join(RESULTS, study, r['case_id'], r['case_id'] + '_history.csv')
    data.sort(key=lambda rc: (rc[0]['specimen'], rc[0]['target_rate']))
    return data


def run_stats(sta):
    """Derniere ligne d'increment du .sta : nombre d'increments, temps de calcul, pas de temps stable final."""
    out = {'increments': np.nan, 'wall_min': np.nan, 'dt_final': np.nan, 't_step_ms': np.nan}
    if not os.path.exists(sta):
        return out
    last = None
    for line in open(sta, errors='replace'):
        m = re.match(r'\s+(\d+)\s+([0-9.E+-]+)\s+([0-9.E+-]+)\s+(\d+):(\d+):(\d+)\s+([0-9.E+-]+)', line)
        if m:
            last = m
    if last:
        out['increments'] = int(last.group(1))
        out['t_step_ms'] = 1e3 * float(last.group(2))
        out['wall_min'] = int(last.group(4)) * 60 + int(last.group(5)) + int(last.group(6)) / 60.0
        out['dt_final'] = float(last.group(7))
    return out


def groups_of(data):
    rates = sorted(set(r['target_rate'] for r, _ in data))
    color = dict(zip(rates, rt.RATE_COLORS * 3))
    return [(spec, [(color[r['target_rate']], (r, c)) for r, c in data if r['specimen'] == spec])
            for spec in sorted(set(r['specimen'] for r, _ in data))]


def probe_errors(study, case):
    """Meme calcul que plot_probes.py : erreur max (apres 5 %) de la force a chaque sonde, ramenee au bout de la
    barre de sortie, en fraction de la force max de l'eprouvette."""
    csv = os.path.join(RESULTS, study, case, case + '_history.csv')
    ys = {}
    for line in open(csv):
        if not line.startswith('#'):
            break
        if 'sondes' in line:
            ys = dict((k, float(v)) for k, v in re.findall(r'([A-Z0-9_]+)=([-0-9.]+)', line))
    d = pd.read_csv(csv, comment='#')
    t = d.time_s.values
    b, a = rt.butter(4, 100e3 / (0.5 / np.median(np.diff(t))))
    lp = lambda x: rt.filtfilt(b, a, x)                       # noqa: E731
    ref = lp(d.F_sec_out_N.values)
    ex = lp(d.eps_ext.values)
    k0 = int(np.argmax(ref > 0.02 * ref.max()))
    i_end = int(np.argmax(ex >= 0.30)) if (ex >= 0.30).any() else int(np.argmax(ex))
    win = (np.arange(len(t)) >= k0) & (np.arange(len(t)) <= i_end) & (ex >= 0.05)
    fmax = ref[win].max()
    y0 = ys['GAUGE_OUT'] + 400.0
    res = {}
    for k in ['HEAD_MID', 'HEAD_TIE', 'BAR_TIE', 'BAR_100', 'BAR_250', 'GAUGE_OUT']:
        col = 'F_probe_%s_N' % k
        if k == 'GAUGE_OUT':
            sig = lp(d.sig_gauge_out.values * rt.A_BAR_MM2)
        elif col in d:
            sig = lp(d[col].values)
        else:
            continue
        sh = np.interp(t + (y0 - ys[k]) / 4871.0e3, t, sig, right=np.nan)
        res[k] = (y0 - ys[k], np.nanmax(np.abs(sh[win] - ref[win])) / fmax)
    return res


def plastic_wave_speed(eps_p):
    """c_p = sqrt(h / rho), h = dk/deps_p (pente de la loi d'ecrouissage, vraie contrainte)."""
    s = SV
    h = s['alpha'] * s['A'] * s['n'] * (eps_p + s['e0']) ** (s['n'] - 1) + \
        (1 - s['alpha']) * s['Q'] * s['beta'] * np.exp(-s['beta'] * eps_p)
    return np.sqrt(h * 1e6 / s['rho']), h


def refit(points):
    """Moindres carres sur 2 K V = vit. x L_eff + 2 F / Z : points = [(vitesse obtenue, V striker)]."""
    x = np.array([p[0] for p in points])
    y = np.array([2 * K * p[1] for p in points])
    A = np.vstack([x, np.ones_like(x)]).T
    (L, c), *_ = np.linalg.lstsq(A, y, rcond=None)
    return L * 1e3, c * Z_BAR / 2.0          # mm, N


def v_formula(rate, L_mm, F_N):
    return (rate * L_mm * 1e-3 + 2 * F_N / Z_BAR) / (2 * K)


# ============================================================
# FIGURES SUPPLEMENTAIRES
# ============================================================
def fig_test_window(groups, out):
    """Deformation de l'extensometre en fonction du temps : 30 % vise, rupture DP1000, localisations."""
    fig, axs = rt.new_axes(len(groups), w=4.2, h=3.2)
    for ax, (spec, items) in zip(axs, groups):
        for col, (r, c) in items:
            m = (c['t_ms'] >= -0.05)
            ax.plot(c['t_ms'][m], 100 * c['eps'][m], color=col, lw=1.5, label=rt.rate_label(r))
            if not np.isnan(r['drop_eps']):
                ax.plot(r['drop_t_ms'], 100 * r['drop_eps'], 'o', ms=8, mfc='none', mec=col, mew=1.5)
        ax.axhline(30, color=rt.INK2, lw=0.8, ls=':')
        ax.text(0.02, 30.5, '30 % (target)', color=rt.INK2, fontsize=7, va='bottom')
        if spec == 'UT40':
            ax.axhline(100 * rt.DP1000_UT_FRACTURE_EPS, color=rt.INK, lw=1.0, ls='--')
            ax.text(0.02, 11.5, 'DP1000 fracture, quasi-static UT40 (Beerli 2026)', color=rt.INK, fontsize=7,
                    va='bottom')
        ax.axvline(rt.PULSE_MS, color=rt.INK2, lw=0.6, ls='-.')
        ax.text(rt.PULSE_MS, 2, ' end of the\n incident pulse\n (2.12 ms)', color=rt.INK2, fontsize=7)
        ax.set_xlim(-0.05, 2.6)
        ax.set_ylim(0, 40)
        ax.set_xlabel('time from loading start (ms)')
        ax.set_ylabel('engineering strain, extensometer (%)')
        ax.set_title('%s  (circle: sudden localisation)' % spec, loc='left')
        ax.legend(loc='upper right', fontsize=8)
    rt.save(fig, out, 'G1_strain_time')


def fig_compare_specimens(ref, out):
    """UT19 et UT40 a la meme vitesse visee : contrainte nominale (vraie force) et R_mod."""
    rates = sorted(set(r['target_rate'] for r, _ in ref))
    fig, axs = plt.subplots(2, len(rates), figsize=(3.5 * len(rates) + 0.4, 6.0), squeeze=False)
    sty = {'UT19': dict(color='#2a78d6', lw=1.5), 'UT40': dict(color='#eb6834', lw=1.5)}
    for k, rate in enumerate(rates):
        for r, c in ref:
            if r['target_rate'] != rate:
                continue
            m = c['win']
            a0 = rt.A0_MM2[r['specimen']]
            axs[0][k].plot(100 * c['eps'][m], 0.5 * (c['Fi'][m] + c['Fo'][m]) / a0, label=r['specimen'],
                           **sty[r['specimen']])
            axs[1][k].plot(100 * c['eps'][m], 100 * c['R_mod'][m], label=r['specimen'], **sty[r['specimen']])
        axs[1][k].axhspan(-5, 5, color=rt.BAND, zorder=0)
        axs[0][k].set_ylim(0, 1200)
        axs[1][k].set_ylim(-20, 20)
        axs[0][k].set_title('%d s$^{-1}$ (target)' % rate, loc='left')
        for row in (0, 1):
            ax = axs[row][k]
            ax.set_xlim(0, 32)
            ax.grid(True, color=rt.GRID, linewidth=0.6)
            ax.set_axisbelow(True)
            for s_ in ('top', 'right'):
                ax.spines[s_].set_visible(False)
            ax.set_xlabel('engineering strain (%)')
        if k == 0:
            axs[0][k].set_ylabel('engineering stress, mean of\nF$_{in}$ and F$_{out}$ / A$_0$ (MPa)')
            axs[1][k].set_ylabel('R$_{mod}$ (%)')
            axs[0][k].legend(loc='lower left', fontsize=8)
    rt.save(fig, out, 'G2_UT19_vs_UT40')


def fig_contact_effect(centred, contact, out):
    """UT19 : eprouvette centree (jeux) / au contact. Ligne 1 : jauge contre vraie force ; ligne 2 : debut."""
    rates = sorted(set(r['target_rate'] for r, _ in contact))
    fig, axs = plt.subplots(3, len(rates), figsize=(3.5 * len(rates) + 0.4, 8.6), squeeze=False)
    a0 = rt.A0_MM2['UT19']
    for k, rate in enumerate(rates):
        for row, (data, name) in enumerate(((centred, 'centred, gaps'), (contact, 'in contact'))):
            r, c = [rc for rc in data if rc[0]['target_rate'] == rate][0]
            m = c['win']
            ax = axs[row][k]
            ax.plot(100 * c['eps'][m], c['Fo'][m] / a0, color='#9a9994', lw=3.2, label='true force')
            ax.plot(100 * c['eps'][m], c['Fg'][m] / a0, color=rt.RATE_COLORS[k], lw=1.1, label='output bar gauge')
            ax.set_ylim(0, 1600)
            ax.set_xlim(0, 32)
            ax.set_title('%s: %d s$^{-1}$ (error %s)' % (name, rate, pct(r['gauge_err_after5'], 0)), loc='left',
                         fontsize=9)
            ax.set_xlabel('engineering strain (%)')
            if k == 0:
                ax.set_ylabel('engineering stress (MPa)')
                if row == 0:
                    ax.legend(loc='lower left', fontsize=7)
        ax = axs[2][k]
        for data, colr, name, lw in ((centred, '#9a9994', 'centred, gaps', 2.4), (contact, rt.RATE_COLORS[k],
                                                                                  'in contact', 1.3)):
            r, c = [rc for rc in data if rc[0]['target_rate'] == rate][0]
            t = c['t_ms']
            mm = (t >= -0.02) & (t <= 0.15)
            ax.plot(1e3 * t[mm], c['Fo_raw'][mm] / 1e3, color=colr, lw=lw, label=name)
        ax.set_title('start of loading, %d s$^{-1}$' % rate, loc='left', fontsize=9)
        ax.set_xlabel('time from loading start (µs)')
        if k == 0:
            ax.set_ylabel('F$_{out}$, unfiltered (kN)')
            ax.legend(loc='upper left', fontsize=7)
    for row in axs:
        for ax in row:
            ax.grid(True, color=rt.GRID, linewidth=0.6)
            ax.set_axisbelow(True)
            for s_ in ('top', 'right'):
                ax.spines[s_].set_visible(False)
    rt.save(fig, out, 'G3_contact_effect_UT19')


def fig_first_ut40(first, recal, out):
    """UT40 a 1000 /s : premier calcul (37,4 m/s) et calcul recale (32,6 m/s)."""
    r1, c1 = [rc for rc in first if rc[0]['target_rate'] == 1000 and rc[0]['specimen'] == 'UT40'][0]
    r2, c2 = [rc for rc in recal if rc[0]['target_rate'] == 1000 and rc[0]['specimen'] == 'UT40'][0]
    fig, axs = rt.new_axes(3, w=3.4, h=3.1)
    for r, c, col, name in ((r1, c1, '#9a9994', 'first run, %.1f m/s' % r1['v_striker']),
                            (r2, c2, '#1baf7a', 'recalibrated, %.1f m/s' % r2['v_striker'])):
        t = c['t_ms']
        m = (t >= -0.02) & (t <= 0.6)
        axs[0].plot(t[m], 100 * c['eps'][m], color=col, lw=1.6, label=name)
        axs[1].plot(t[m], c['Fi'][m] / 1e3, color=col, lw=1.6, label=name)
        # vitesse des deux noeuds de l'extensometre (filtree)
        d = pd.read_csv(c['csv'], comment='#')
        tt = d.time_s.values
        b, a = rt.butter(4, 100e3 / (0.5 / np.median(np.diff(tt))))
        vin = np.gradient(rt.filtfilt(b, a, d.u2_ext_in_mm.values), tt) * 1e-3
        vout = np.gradient(rt.filtfilt(b, a, d.u2_ext_out_mm.values), tt) * 1e-3
        axs[2].plot(t[m], vin[m], color=col, lw=1.6, label=name + ', pusher side')
        axs[2].plot(t[m], vout[m], color=col, lw=1.0, ls='--', label=name + ', output side')
        if not np.isnan(r['drop_eps']):
            for ax in axs:
                ax.axvline(r['drop_t_ms'], color='#d03b3b', lw=0.8)
    axs[0].axhline(30, color=rt.INK2, lw=0.8, ls=':')
    axs[0].set_ylabel('extensometer strain (%)')
    axs[1].set_ylabel('F$_{in}$ (kN)')
    axs[2].set_ylabel('velocity of the extensometer nodes (m/s)')
    axs[2].axhline(0, color=rt.INK2, lw=0.6)
    for ax, ttl in zip(axs, ('strain', 'force, input section', 'extensometer nodes')):
        ax.set_xlabel('time from loading start (ms)')
        ax.set_title('UT40 / 1000: ' + ttl, loc='left', fontsize=9)
    axs[0].legend(loc='lower right', fontsize=7)
    axs[2].legend(loc='lower left', fontsize=6)
    rt.save(fig, out, 'G4_first_UT40_R1000')


def fig_probes(prb, out):
    """Erreur max (apres 5 %) a chaque sonde, en fonction de la distance au bout de la barre de sortie."""
    fig, axs = rt.new_axes(1, w=6.4, h=3.3)
    ax = axs[0]
    cols = ['#9a9994', '#2a78d6', '#d03b3b', '#1baf7a']
    for (name, res), col in zip(prb, cols):
        keys = sorted(res, key=lambda k: res[k][0])
        ax.plot([res[k][0] for k in keys], [100 * res[k][1] for k in keys], '-o', color=col, ms=5, lw=1.2,
                label=name)
    ax.axvline(400, color=rt.INK2, lw=0.6, ls=':')
    ax.text(400, 1.2, 'gauge ', fontsize=7, color=rt.INK2, va='bottom', ha='right')
    ax.axvspan(0, 55.7, color=rt.BAND, zorder=0)
    ax.text(28, 1.2, 'output\nhead', fontsize=7, color=rt.INK2, va='bottom', ha='center')
    ax.set_yscale('log')
    ax.set_ylim(1, 100)
    ax.set_xlabel('distance from the pocket end of the output bar (mm)')
    ax.set_xlim(0, 420)
    ax.set_ylabel('max error after 5 % strain\n(% of the max force)')
    ax.legend(fontsize=7, loc='lower center', ncol=2)
    rt.save(fig, out, 'G5_probes_error')


# ============================================================
# RAPPORT
# ============================================================
class Doc:
    """Sections ecrites dans l'ordre ; figures et tableaux references par une cle, numerotes a la fin."""

    def __init__(self):
        self.lines = []

    def P(self, *parts):
        self.lines.extend([''.join(parts), ''])

    def H(self, level, text):
        self.P('#' * level + ' ' + text)

    def bullets(self, items):
        self.P('\n'.join('- ' + x for x in items))

    def fig(self, key, img, title, plotted, source, read):
        self.P('![%s](%s)' % (title, img))
        self.P('> **Figure [[fig:%s]] – %s.**\n>\n> *Plotted* – %s\n>\n> *Source* – %s\n>\n> *How to read it* – %s'
               % (key, title, plotted, source, read))

    def img(self, key, img, title, what, source):
        """Capture d'ecran ou image du journal (pas de courbe a lire)."""
        self.P('![%s](%s)' % (title, img))
        self.P('> **Figure [[fig:%s]] – %s.**\n>\n> *Shown* – %s\n>\n> *Source* – %s' % (key, title, what, source))

    def tab(self, key, title, header, rows, note=None):
        self.P('**Table [[tab:%s]] – %s.**' % (key, title))
        self.P(md_table(header, rows))
        if note:
            self.P(note)

    def text(self):
        txt = '\n'.join(self.lines)
        num = {}
        for kind in ('fig', 'tab'):
            word = 'Figure' if kind == 'fig' else 'Table'
            order = []
            for m in re.finditer(r'\*\*%s \[\[%s:(\w+)\]\]' % (word, kind), txt):
                if m.group(1) not in order:
                    order.append(m.group(1))
            for i, k in enumerate(order):
                num[(kind, k)] = str(i + 1)
        missing = set(re.findall(r'\[\[(fig|tab):(\w+)\]\]', txt)) - set(num)
        if missing:
            sys.exit('References sans legende : %s' % sorted(missing))
        return re.sub(r'\[\[(fig|tab):(\w+)\]\]', lambda m: num[(m.group(1), m.group(2))], txt)


def F(key):
    return 'Figure [[fig:%s]]' % key


def T(key):
    return 'Table [[tab:%s]]' % key


def kn(x):
    return '%.2f kN' % x


def write(ref, centred, first, prb, out):
    rows = [r for r, _ in ref]
    by = {(r['specimen'], int(r['target_rate'])): (r, c) for r, c in ref}
    by_c = {int(r['target_rate']): r for r, _ in centred}
    by_f = {int(r['target_rate']): r for r, _ in first}
    rate_min = rt.EPS_TARGET / (rt.PULSE_MS * 1e-3)
    tol = round(100 * rt.EQ_TOL)
    shift_us = 1e3 * rt.GAUGE_TO_SPEC_MM / rt.C_BAR
    sp = make_run.SPECIMENS
    L0 = {r['specimen']: r['ext_L0'] for r in rows}
    drops = [r for r in rows if not np.isnan(r['drop_eps'])]
    no_drop = [r for r in rows if np.isnan(r['drop_eps'])]
    u19 = [by[('UT19', k)][0] for k in (100, 500, 1000)]
    u40 = [by[('UT40', k)][0] for k in (100, 500, 1000)]
    D = Doc()
    P = D.P

    # ------------------------------------------------------------------ titre
    D.H(1, 'Task I – Force equilibrium and loading speeds in the SHPB with load inversion device: final report')
    P('*Specimens UT19 (15 mm parallel section) and UT40 (40 mm parallel section), DP1000, target strain rates '
      '100, 500 and 1000 s⁻¹. Reference studies: `%s` (UT19) and `%s` (UT40). Generated by '
      '`scripts/post/report_taskI_final.py`: every number in this report is computed from the simulation '
      'outputs, except the observations made in Abaqus/Viewer and Abaqus/CAE, which are marked as such and come '
      'from the lab journal.*' % (REF['UT19'], REF['UT40']))
    P('**Questions of Task I.**')
    P('1. Can quasi-static force equilibrium be achieved in the specimen at nominal strain rates of 100, 500 and '
      '1000 s⁻¹?\n2. Which loading speeds are required to reach an engineering strain of 30 %?')
    P('**Contents.** Summary · Background: the bench and the questions · Numerical model · Definitions and '
      'signal processing · Simulation campaign · Answer 1: force equilibrium · Answer 2: loading speeds · UT19 '
      'and UT40 compared · What the experiment will measure · Necking, localisation and fracture: how far the '
      'results are valid · Numerical quality and computing cost · Limitations · Conclusions and recommendations · '
      'Open questions for the supervisors · Appendices A to E.')

    # ------------------------------------------------------------------ resume
    D.H(2, 'Summary')
    P('The two questions were answered with an Abaqus/Explicit model of the complete bench (striker, input bar, '
      'load inversion device, specimen, output bar), for the two specimen geometries and the three target '
      'rates: six reference simulations. The tables below give the answer for each case; the sections that '
      'follow give the evidence.')
    D.tab('sum_eq', 'Answer 1 at a glance: force equilibrium',
          ['Specimen / target rate (s⁻¹)', 'Equilibrium, $R$', 'Equilibrium, $R_{mod}$', 'Max $\\lvert\\Delta F\\rvert$ after 5 %'],
          [[label(r), eq_short(r),
            rmod_from(r, 'yes, ') if not np.isnan(r['eps_eq_mod']) else 'no (max %s)' % pct(r['Rmod_max_after5'], 0),
            '%s (%s of $F_{max}$)' % (kn(r['dF_max_after5_kN']), pct(r['dF_max_after5_kN'] / r['F_max_kN'], 1))]
           for r in rows],
          '*Equilibrium*: from which engineering strain the force difference between the two ends of the parallel '
          'section stays below %d %% until the end of the test, relative to the current mean force ($R$) or to the '
          'maximum force ($R_{mod}$); "partial": longest interval where it holds. $\\Delta F = F_{in} - F_{out}$.'
          % tol)
    D.tab('sum_v', 'Answer 2 at a glance: loading speed and 30 % strain',
          ['Specimen / target rate (s⁻¹)', 'Striker velocity', 'Achieved rate', '30 % strain', 'Gauge error'],
          [[label(r), '%.2f m/s' % r['v_striker'], '%.0f s⁻¹' % r['achieved_rate'],
            ('in %.2f ms' % r['time_to_30_ms']) if r['reached_30'] else 'no (max %s)' % pct(r['eps_max'], 1),
            pct(r['gauge_err_after5'], 1) + (' (%s before localisation)' % pct(r['gauge_err_before_drop'], 1)
                                             if not np.isnan(r['drop_eps']) else '')] for r in rows],
          '*Striker velocity*: the setting of the test (5 m striker). *Achieved rate*: mean strain rate of the '
          'extensometer between 5 % and 80 % of the maximum strain. *Gauge error*: largest difference between the '
          'force that the output bar gauge will measure and the true specimen force, after 5 % strain, relative '
          'to the maximum force.')
    P('**Key findings.**')
    eq_ok40 = [label(r) for r in u40 if eq_ok(r)]
    P('1. **UT19: equilibrium at every rate.** With the specimen in contact with both pockets, as in the lab, '
      '$\\lvert R\\rvert$ stays below 5 %% from the very start of loading to 30 %% strain (or to the end of the '
      'pulse at 100 s⁻¹); the largest force difference after 5 %% strain is %s at 1000 s⁻¹ (%s of the maximum '
      'force).\n'
      '2. **UT40: equilibrium only at 100 s⁻¹.** At 500 and 1000 s⁻¹ the two ends of the longer parallel section '
      'carry the same force only between about %s and %s strain (500 s⁻¹) and %s and %s (1000 s⁻¹). Likely '
      'reason: the 40 mm parallel section is too long for the plastic waves to even out the force before the '
      'maximum force is reached (interpretation, section *UT19 and UT40 compared*).\n'
      '3. **Loading speed.** The striker velocity must include the force of the specimen, which brakes the '
      'inverter and pushes the output bar: $V = (\\dot\\varepsilon\\,L_{eff} + 2F/\\rho c A)/(2K)$. With the '
      'calibrated constants the achieved rates are within %s of the targets (UT19) and within %s (UT40). 30 %% '
      'strain is reached at 500 and 1000 s⁻¹ with both specimens; it cannot be reached below ≈ %.0f s⁻¹ with '
      'the 5 m striker, so not at 100 s⁻¹.\n'
      '4. **Measurement.** Once the specimen sits against both pockets at the start, the output bar gauge '
      'measures the specimen force within %s of the maximum force, except after a sudden localisation of the '
      'neck. With the specimen centred in the pockets (clearances of 0.36 mm) the error was up to %s at '
      '1000 s⁻¹: the initial contact is essential.\n'
      '5. **Validity limit.** The model has no fracture criterion. DP1000 breaks at about %s engineering strain '
      'on the UT40 geometry in a quasi-static test (Beerli et al. 2026). The UT40 simulations reach 30 %% only '
      'because the simulated material cannot break; at 500 s⁻¹ the neck finally collapses numerically at %s '
      'strain. For DP1000, 30 %% engineering strain is very probably not reachable with the UT40.'
      % (kn(by[('UT19', 1000)][0]['dF_max_after5_kN']),
         pct(by[('UT19', 1000)][0]['dF_max_after5_kN'] / by[('UT19', 1000)][0]['F_max_kN'], 1),
         pct(by[('UT40', 500)][0]['eq_from'], 1), pct(by[('UT40', 500)][0]['eq_to'], 1),
         pct(by[('UT40', 1000)][0]['eq_from'], 1), pct(by[('UT40', 1000)][0]['eq_to'], 1),
         pct(max(abs(r['achieved_rate'] / r['target_rate'] - 1) for r in u19), 0),
         pct(max(abs(r['achieved_rate'] / r['target_rate'] - 1) for r in u40), 0), rate_min,
         pct(max([r['gauge_err_after5'] for r in no_drop] + [r['gauge_err_before_drop'] for r in drops]), 0),
         pct(by_c[1000]['gauge_err_after5'], 0), pct(rt.DP1000_UT_FRACTURE_EPS, 0),
         pct(by[('UT40', 500)][0]['drop_eps'], 1)))
    del eq_ok40

    # ------------------------------------------------------------------ contexte
    D.H(2, 'Background: the bench and the questions')
    P('**The bench.** The split Hopkinson pressure bar (SHPB) of the lab is used here in tension through a load '
      'inversion device (LID; Beerli et al. 2026). The striker hits the input bar and creates a compression '
      'wave. At the end of the input bar this wave pushes the *pusher* (inverter), whose head holds one end of '
      'the specimen in a toothed pocket; the other end of the specimen sits in the toothed pocket of the head '
      'of the output bar, which lies above the pusher and points the other way. Pushing the pusher therefore '
      '**pulls** the specimen. The force transmitted by the specimen travels into the output bar and is '
      'measured by a strain gauge 400 mm from the bar end; the strain of the specimen is measured optically '
      '(DIC), here by a virtual extensometer.')
    P('**Why equilibrium matters.** The stress–strain curve of a test is computed from the force measured on '
      'the output side only. It represents the material only if the force is the same at both ends of the '
      'parallel section (quasi-static force equilibrium); otherwise the specimen is not uniformly loaded and '
      'the measured curve depends on the inertia of the specimen. Equilibrium requires the stress waves to '
      'travel back and forth several times along the specimen before the stress changes much, which becomes '
      'harder at higher strain rates and for longer specimens.')
    P('**Why the loading speed matters.** The strain rate in the specimen is set by the striker velocity, but '
      'not proportionally: the specimen force brakes the pusher. The strain the test can reach is limited by '
      'the duration of the loading pulse (twice the travel time of the wave in the striker: %.2f ms for the '
      '5 m striker) and by the length of the output bar (measurement window ≈ %.2f ms before the reflected wave '
      'comes back to the gauge; Beerli et al. 2026).' % (rt.PULSE_MS, rt.OUTPUT_WINDOW_MS))
    P('**Interpretation of the questions.** "Loading speed" is interpreted as the **striker velocity**, the '
      'only setting of the test; the velocity of the pusher follows from it and can be extracted from the same '
      'simulations. "Quasi-static force equilibrium" is judged on the exact forces at both ends of the parallel '
      'section, with the 5 % criterion usual in Hopkinson bar testing (definitions below). "30 %" is the '
      'engineering strain over the extensometer.')

    # ------------------------------------------------------------------ modele
    D.H(2, 'Numerical model')
    D.H(3, 'Bench, mesh and solver')
    D.tab('bench', 'Parts of the model',
          ['Part', 'Geometry', 'Material', 'Mesh'],
          [['Striker', 'cylinder Ø20 × 5000 mm (created by the script)', 'steel, elastic', 'swept C3D8R, 5 mm axially, 2 mm in the section'],
           ['Input bar', 'cylinder Ø20 × 6010 mm', 'maraging, elastic', 'swept C3D8R, 5 / 2 mm'],
           ['Pusher (inverter)', 'lab CAD file `Inverter_new.step`; rod + toothed head', 'maraging, elastic', 'rod: swept C3D8R; head: C3D10M tetrahedra, 2 mm'],
           ['Specimen', 'see %s' % T('spec'), 'DP1000, elastic–plastic', 'C3D8R, 0.5 mm in plane, 4 elements through the 1.5 mm thickness; regular grid in the parallel section'],
           ['Output bar', 'cylinder Ø20, ≈ 6 m, + toothed head (`Stange30mm_Step2.step`)', 'maraging, elastic', 'bar: swept C3D8R, 5 / 2 mm; head: C3D10M, 2 mm']],
          'Element sizes as in Roth et al. (2015) and Beerli et al. (2026). Heads and bars are joined by ties; '
          'details in `docs/mesh.md`.')
    D.bullets([
        '**Solver**: Abaqus/Explicit 2023, double precision, **no mass scaling** (inertia is the studied effect); '
        'Euler cluster (ETH), 8 cores per simulation.',
        '**Half model**: only the half X ≥ 0 is modelled (vertical plane of symmetry through the bar axes). '
        'Every piece has the symmetry condition `XSYMM` (U1 = 0 on its nodes of the plane X = 0; '
        '`model/templates/SHPB_UT_main.inp`, section 6a); forces and energies of the half model are multiplied '
        'by 2 when they are extracted.',
        '**Guides**: the vertical displacement U3 is blocked on the sliding face of the pusher and on the bar '
        'axes. Without them the pusher pitched under the eccentric load (the input bar pushes on its axis, the '
        'specimen pulls 21 mm higher; first study `taskI_20261012-1811`). Guides are frictionless and without '
        'clearance.',
        '**Contacts**: bar ends hard and frictionless; specimen teeth in the pockets hard with a friction '
        'coefficient of 0.2 (general contact).',
        '**Loading**: initial velocity of the striker, in contact with the input bar at $t = 0$.',
        '**Simulated time**: arrival of the wave at the pusher (1.234 ms) + time to 30 % strain at the target '
        'rate + 0.3 ms, capped at the end of the pulse: 3.65 / 2.13 / 1.83 ms at 100 / 500 / 1000 s⁻¹.',
    ])
    D.H(3, 'Specimens and placement in the pockets')
    D.tab('spec', 'Specimen geometries',
          ['', 'UT19', 'UT40'],
          [['Geometry file', SPEC_INFO['UT19']['source'], SPEC_INFO['UT40']['source']],
           ['Overall length × width × thickness (mm)', '%s × 30 × 1.5' % SPEC_INFO['UT19']['length'],
            '%s × 30 × 1.5' % SPEC_INFO['UT40']['length']],
           ['Parallel section, length × width (mm)', SPEC_INFO['UT19']['gauge'], SPEC_INFO['UT40']['gauge']],
           ['Initial section $A_0$', '%.1f mm²' % rt.A0_MM2['UT19'], '%.1f mm²' % rt.A0_MM2['UT40']],
           ['Extensometer length $L_0$', '%.3f mm' % L0['UT19'], '%.3f mm' % L0['UT40']],
           ['Elements: specimen / parallel section', '%s / %s' % (SPEC_INFO['UT19']['elem_spec'], SPEC_INFO['UT19']['elem_gauge']),
            '%s / %s' % (SPEC_INFO['UT40']['elem_spec'], SPEC_INFO['UT40']['elem_gauge'])],
           ['Elements, whole model', SPEC_INFO['UT19']['elem_total'], SPEC_INFO['UT40']['elem_total']]],
          'Both specimens have the same toothed heads (three teeth on each side). On the UT40 drawing the loaded '
          'tooth flanks are 0.10 mm further from the tip and the pusher-side tip is 0.29 mm shorter than on the '
          'UT19; its parallel section is very slightly tapered (10.020 mm at the output end, 10.001 mm at the '
          'pusher end). The extensometer nodes are the surface nodes on the symmetry plane closest to ±15 mm '
          '(UT40) or ±6 mm (UT19) from the middle of the parallel section.')
    D.img('outline', 'img/UT40_vs_UT19_outline.png', 'UT19 and UT40 in their final placement',
          'outline of the UT19 (grey) and of the UT40 (orange) in the bench, pusher side at the top. The '
          'pusher-side heads coincide; the UT40 is 25 mm longer, so its output-side head, and with it the whole '
          'output bar, is placed 25 mm further down.',
          'geometry files, placement of `build_bench.py`; lab journal, 23 Oct 2026.')
    P('**Initial contact.** In the lab, the pusher is pulled very slightly before the shot so that the teeth of '
      'the specimen sit against the teeth of both pockets, without pre-load (confirmed by the supervisors on '
      '22 Oct 2026). The model reproduces this: the clearances between the specimen teeth and the pockets were '
      'measured on the CAD files (OpenCascade, `scripts/pre/pocket_gaps.py`) and closed by translating the '
      'specimen and the output bar along the bar axis (`build_bench.py`, `CLOSE_GAPS = True`).')
    D.tab('gaps', 'Clearances closed at the start',
          ['Specimen', 'Pusher pocket', 'Output pocket', 'Clearance left behind the teeth', 'Output bar end (Y)'],
          [[s, ('%.4f mm' % SPEC_INFO[s]['gap_pusher']).replace('-', '−'), '%.4f mm' % SPEC_INFO[s]['gap_output'],
            '%.2f / %.2f mm' % (SPEC_INFO[s]['clear_p'], SPEC_INFO[s]['clear_o']), SPEC_INFO[s]['bar_end'] + ' mm']
           for s in ('UT19', 'UT40')],
          '*Pusher / output pocket*: translation along the bar axis needed to bring the loaded tooth flanks into '
          'contact, starting from the specimen centred in the pockets (negative: the centred UT40 already '
          'overlaps the pusher pocket by 0.04 mm and is moved back). *Clearance left behind the teeth*: free '
          'space on the unloaded side of the teeth, pusher / output pocket. In both pockets the inclined flanks '
          'of the **three** teeth touch at the same time; the overlap volume once in contact is below 0.002 mm³.')
    D.img('pocket19', 'img/pocket_contact_UT19.png', 'UT19 teeth in the pockets, centred and in contact',
          'cut at mid-thickness of the specimen (half X > 0). Left: whole pocket with the final placement. '
          'Middle: one tooth with the old centred placement, a 0.36 mm gap between the inclined flanks. Right: '
          'the same tooth in the final placement, flanks in contact. Top: pusher; bottom: output bar.',
          'CAD files and `pocket_gaps.py` (OpenCascade); lab journal, 22 Oct 2026.')
    D.img('pocket40', 'img/UT40_pocket_contact.png', 'UT40 teeth in contact in both pockets',
          'UT40 in its final placement, cut at mid-thickness. Left: pusher pocket and zoom on one tooth; right: '
          'output pocket and zoom. The loaded flanks touch; the other flanks keep a clearance of 0.4–0.5 mm.',
          '`pocket_gaps.py`; lab journal, 23 Oct 2026.')
    D.H(3, 'Materials')
    D.tab('mat', 'Elastic parts',
          ['Material', 'Wave speed $c$', 'Density $\\rho$', '$E = \\rho c^2$', 'Used for'],
          [['Maraging steel', '4871 m/s (measured)', '8000 kg/m³ (assumed)', '189.8 GPa', 'bars, pusher'],
           ['Striker steel', '4720 m/s (measured)', '7850 kg/m³ (assumed)', '174.9 GPa', 'striker']],
          'Wave speeds measured on the bench (Beerli et al. 2026, section 2.5); Poisson ratio 0.3. What matters '
          'for the waves is $c$ and the impedance $Z = \\rho c A$: an error on the assumed density changes $Z$ '
          'in the same proportion.')
    P('**Specimen: DP1000.** Von Mises yield surface, isotropic hardening, rate independent. The flow stress $k$ '
      '(true stress) is a function of the equivalent plastic strain $\\varepsilon_p$, as identified by Beerli et '
      'al. (2026, eq. 10 and table 4) on quasi-static tensile tests:')
    P('$$\nk(\\varepsilon_p) = \\alpha_{SV}\\,A\\,(\\varepsilon_p+\\varepsilon_0)^{n}'
      ' + (1-\\alpha_{SV})\\left[k_0 + Q\\left(1-e^{-\\beta\\varepsilon_p}\\right)\\right]\n$$')
    P('with $A$ = 1395 MPa, $\\varepsilon_0$ = 10⁻⁶, $n$ = 0.0892 (Swift power law), $k_0$ = 739 MPa, '
      '$Q$ = 301 MPa, $\\beta$ = 102 (Voce exponential law) and $\\alpha_{SV}$ = 0.5; $E$ = 195 GPa, '
      '$\\nu$ = 0.33, $\\rho$ = 7850 kg/m³. Not used from the paper: the anisotropic yield surface, the strain-rate '
      'and temperature dependence, the thermal properties and the fracture model, as in the authors\' own '
      'simulation of the bench. The three strain rates therefore have exactly the same material law. The '
      'Considère criterion $dk/d\\varepsilon_p = k$ predicts necking at 5.1 % engineering strain and 1002 MPa '
      '(`docs/materials.md`).')
    D.H(3, 'Outputs')
    D.bullets([
        '**Specimen forces** $F_{in}$, $F_{out}$: exact axial forces through two cross-sections at both ends of '
        'the parallel section (pusher side, output side). They are only available in a simulation.',
        '**Virtual extensometer**: displacement of two surface nodes of the parallel section (equivalent to the '
        'DIC extensometer of the tests).',
        '**Virtual strain gauges** 400 mm from the end of each bar, read as in the lab: mean of a gauge on top '
        'and one at the bottom of the bar, which cancels the bending of the output bar.',
        '**Force probes** (1000 s⁻¹ runs only): force through five slices along the output side, from the output '
        'head to the bar, to see where a measurement error comes from.',
        '**Energies** of the whole model; field outputs (stress, strain, PEEQ) every ≈ 21 µs for Abaqus/Viewer.',
    ])

    # ------------------------------------------------------------------ definitions
    D.H(2, 'Definitions and signal processing')
    P('**Filter.** Forces and strain are low-pass filtered (4th-order Butterworth, 100 kHz cut-off, zero phase), '
      'the cut-off used for the output bar gauge in the lab. The simulation writes one point per microsecond '
      'and contains vibrations of a few microseconds that the experiment cannot resolve. The effect of the '
      'filter on the conclusions is shown in %s.' % T('filter'))
    P('**Force measured by the experiment.** The experiment only has the output bar gauge:')
    P('$$\nF_{gauge}(t) = A_{bar}\\,E_{bar}\\,\\varepsilon_{gauge}\\!\\left(t + \\Delta t\\right), \\qquad '
      '\\Delta t = \\frac{400\\ \\text{mm}}{4871\\ \\text{m/s}} = %.0f\\ \\mu\\text{s}\n$$' % shift_us)
    P('i.e. the gauge signal moved back by the travel time of the wave from the bar end to the gauge (no '
      'dispersion correction), as in Beerli et al. (2026, fig. 5c). It is used only in the section *What the '
      'experiment will measure*; the equilibrium question is answered with the exact forces.')
    P('**Engineering strain** $\\varepsilon$: elongation of the virtual extensometer divided by its initial '
      'length $L_0$ (%.3f mm for the UT19, %.3f mm for the UT40).' % (L0['UT19'], L0['UT40']))
    P('**Equilibrium: two indicators.** The same force difference is divided either by the current mean force '
      '($R$, the usual definition) or by the maximum force of the test ($R_{mod}$):')
    P('$$\nR = \\frac{F_{in} - F_{out}}{F_{mean}}, \\quad F_{mean} = \\frac{F_{in} + F_{out}}{2}'
      '\\qquad\\qquad R_{mod} = \\frac{F_{in} - F_{out}}{F_{max}}, \\quad F_{max} = \\max(F_{in})\n$$')
    D.bullets([
        'The specimen is considered in equilibrium when $\\lvert R\\rvert$ < 5 %.',
        '*Loading start*: first instant where $F_{in}$ exceeds 2 % of its maximum. *Useful window*: from the '
        'loading start to 30 % strain, or to the maximum strain if 30 % is not reached.',
        '*Equilibrium strain*: strain from which $\\lvert R\\rvert$ stays below 5 % until the end of the useful '
        'window. $R$ is not evaluated below 0.2 % strain or while the mean force is below 10 % of its maximum '
        '(the ratio of two near-zero forces is meaningless): "from 0.2 %" means "from the start".',
        '*Partial equilibrium*: when there is no such strain, the longest strain interval with '
        '$\\lvert R\\rvert$ < 5 % is given.',
        '$R_{mod}$ always divides by the same force, so it is defined over the **whole** useful window, '
        'including the start of loading and the end of necking, where the force is small and $R$ is large or '
        'not evaluated. Its 5 %% threshold is a fixed force: ≈ %.2f kN for the UT19 and ≈ %.2f kN for the UT40.'
        % (0.05 * by[('UT19', 500)][0]['F_max_kN'], 0.05 * by[('UT40', 500)][0]['F_max_kN']),
    ])
    P('**Achieved strain rate.** The strain rate varies during a test. To give one value per simulation, it is '
      'measured where the loading is established:')
    P('$$\n\\dot\\varepsilon = \\frac{\\varepsilon_2 - \\varepsilon_1}{t_2 - t_1}, \\qquad \\varepsilon_1 = 5\\ \\%, '
      '\\qquad \\varepsilon_2 = 0.8\\,\\varepsilon_{max}\n$$')
    P('where $t_1$, $t_2$ are the instants at which the extensometer reaches $\\varepsilon_1$ and '
      '$\\varepsilon_2$. Below 5 %% the loading is not established (rise of the pulse, force rising to its '
      'maximum); above 80 %% of the maximum strain the rate drops at the end of the pulse. Other definitions are '
      'compared in %s.' % T('rates'))
    P('**Sudden localisation.** First drop of the mean specimen force (unfiltered) by more than %d %% of the '
      'maximum force within %.0f µs, after the force maximum. It marks the moment when a few elements at the '
      'centre of the neck collapse (section *Necking, localisation and fracture*).'
      % (round(100 * rt.DROP_FRAC), rt.DROP_US))

    # ------------------------------------------------------------------ campagne
    D.H(2, 'Simulation campaign')
    P('Seven studies were run during Task I. Each changed one thing with respect to the previous one; the '
      'two reference studies used for the answers are in bold.')
    D.tab('studies', 'Studies of Task I',
          ['Study', 'What changed', 'What it showed'],
          [['`taskI_20261012-1811`', 'first UT19 runs, 4 ms simulated', 'the pusher pitches under the eccentric load → vertical guides added'],
           ['`taskI_20261013-1127`', 'guides; striker velocity $V = \\dot\\varepsilon \\times 15$ mm', '100 s⁻¹ gives only 21 s⁻¹ → striker formula with the specimen force'],
           ['`%s`' % CENTRED_UT19, 'new formula; simulated time per case; specimen centred in the pockets',
            '%.0f / %.0f / %.0f s⁻¹; gauge error %s / %s / %s (Appendix B)' % (by_c[100]['achieved_rate'], by_c[500]['achieved_rate'], by_c[1000]['achieved_rate'],
                                                                       pct(by_c[100]['gauge_err_after5'], 0), pct(by_c[500]['gauge_err_after5'], 0), pct(by_c[1000]['gauge_err_after5'], 0))],
           ['`diag_20261021-1626`', 'UT19 at 1000 s⁻¹ with force probes', 'the gauge error comes from the specimen hitting the output pocket after crossing the clearance'],
           ['**`%s`**' % REF['UT19'], '**initial contact** of the teeth in both pockets', 'UT19 reference: equilibrium from the start at all rates; gauge error ≤ %s' % pct(max(r['gauge_err_after5'] for r in u19), 0)],
           ['`%s`' % FIRST_UT40, 'UT40 (geometry from the cutting drawing), estimated striker velocities',
            '%.0f / %.0f / %.0f s⁻¹; at 1000 s⁻¹ the strain localises outside the extensometer; formula recalibrated (Appendix C)'
            % (by_f[100]['achieved_rate'], by_f[500]['achieved_rate'], by_f[1000]['achieved_rate'])],
           ['**`%s`**' % REF['UT40'], 'UT40 with the recalibrated striker formula',
            'UT40 reference: %.0f / %.0f / %.0f s⁻¹; sudden localisation at 500 s⁻¹' % tuple(r['achieved_rate'] for r in u40)]],
          'Every study is in `results/<study>/` with its own report (`report/report.md`).')

    # ------------------------------------------------------------------ reponse 1
    D.H(2, 'Answer 1 – Force equilibrium')
    D.H(3, 'Overview')
    D.fig('eq', 'F1_equilibrium.png', 'Force equilibrium in the specimen, $R$',
          'the equilibrium ratio $R$ against the engineering strain, one panel per specimen, one curve per target '
          'rate.',
          'exact forces $F_{in}$, $F_{out}$ in the two cross-sections of the specimen, filtered at 100 kHz; strain '
          'of the virtual extensometer.',
          'inside the shaded band ($\\lvert R\\rvert$ < 5 %) both ends of the specimen carry the same force. '
          'Values are cut at ±20 %. $R$ is not plotted where it is not evaluated (very start of loading).')
    D.fig('eqmod', 'F1c_equilibrium_Rmod.png', 'Force equilibrium relative to the maximum force, $R_{mod}$',
          '$R_{mod} = (F_{in} - F_{out}) / F_{max}$ against the engineering strain over the whole useful window, '
          'one panel per specimen; dotted vertical line: sudden localisation, if any.',
          'same filtered section forces.',
          'inside the shaded band the force difference is below 5 % of the maximum force. Unlike $R$, the curve '
          'is not amplified at the start and at the end of the test, where the force is small.')
    D.tab('eq', 'Equilibrium indicators',
          ['Specimen / target rate (s⁻¹)', 'Equilibrium from', 'Max $\\lvert R\\rvert$ after 5 %', 'Max $\\lvert\\Delta F\\rvert$ after 5 %', 'Max force'],
          [[label(r), ('%s (%.2f ms)' % (pct(r['eps_eq'], 1), r['t_eq_ms'])) if eq_ok(r) else
            ('%s to %s only' % (pct(r['eq_from'], 1), pct(r['eq_to'], 1)) if not np.isnan(r['eq_from']) else 'never'),
            pct(r['R_max_after5'], 1), kn(r['dF_max_after5_kN']),
            '%.2f kN at %s' % (r['F_max_kN'], pct(r['eps_at_Fmax'], 1))] for r in rows],
          '*Equilibrium from*: strain (and time after the loading start) from which $\\lvert R\\rvert$ < 5 % holds '
          'until the end of the useful window; 0.2 % is the lowest strain considered.')
    D.tab('eqmod', 'Equilibrium with $R_{mod}$',
          ['Specimen / target rate (s⁻¹)', '$\\lvert R_{mod}\\rvert$ < 5 % from', 'Max $\\lvert R_{mod}\\rvert$ after 5 %', 'Max $\\lvert R_{mod}\\rvert$, whole window'],
          [[label(r), rmod_from(r, '', True) if not np.isnan(r['eps_eq_mod']) else 'not maintained', pct(r['Rmod_max_after5'], 1), pct(r['Rmod_max_all'], 1)] for r in rows],
          '*From*: strain (and time) from which $\\lvert R_{mod}\\rvert$ < 5 % holds until the end of the useful '
          'window, the search starting at the loading start.')
    D.H(3, 'UT19')
    P('\n'.join(rt.case_sentence(r) for r in u19))
    P('With $R_{mod}$ the conclusion is the same, and it extends to the start of loading, where $R$ is not '
      'evaluated: $\\lvert R_{mod}\\rvert$ stays below %s over the whole useful window at the three rates. The '
      'force rises smoothly from zero at both ends (%s): there is no transient to wait for.'
      % (pct(max(r['Rmod_max_all'] for r in u19), 1), F('onset19')))
    D.fig('onset19', 'F1b_equilibrium_onset_UT19.png', 'UT19: start of loading',
          'the exact forces $F_{in}$ (coloured solid line) and $F_{out}$ (black dashed line) against the time from '
          'the loading start, one panel per target rate, until shortly after 5 % strain. Dotted vertical lines: '
          '1, 2 and 5 % strain. Grey band: start of loading where $R$ is not evaluated.',
          'filtered section forces.',
          'the two forces overlap from the beginning; no line is drawn when equilibrium holds from the first '
          'point checked.')
    D.H(3, 'UT40')
    P('\n'.join(rt.case_sentence(r) for r in u40))
    r5, r10 = by[('UT40', 500)][0], by[('UT40', 1000)][0]
    pre5, pre10 = rmod_range_before(by[('UT40', 500)]), rmod_range_before(by[('UT40', 1000)])
    post10 = rmod_peak_after(by[('UT40', 1000)])
    P('At 500 and 1000 s⁻¹ the UT40 is in equilibrium during the hardening phase and the beginning of necking, '
      'but not before and not after:')
    D.bullets([
        '**Before** (start of loading up to %s and %s strain): the force rises within ≈ 0.1–0.2 ms, during '
        'which the plastic waves cross the 40 mm parallel section only a few times (section *UT19 and UT40 '
        'compared*). The force difference oscillates: $R_{mod}$ between %s and %s at 500 s⁻¹, between %s and %s '
        'at 1000 s⁻¹, mostly with more force on the input side, which is pulled (%s).'
        % (pct(r5['eq_from'], 1), pct(r10['eq_from'], 1), sgn(pre5[0]), sgn(pre5[1]), sgn(pre10[0]),
           sgn(pre10[1]), F('onset40')),
        '**After** (from %s and %s strain): the neck forms. At 1000 s⁻¹, $R_{mod}$ reaches %s at %s strain: '
        'the input-side force has already dropped to %.1f kN while the output side still carries %.1f kN '
        '(maximum force %.1f kN; %s, Appendix A). At 500 s⁻¹ the force difference stays moderate (%s of $F_{max}$ before 18 %% strain) '
        'until the sudden localisation at %s strain, after which the forces at both ends oscillate in opposition '
        '(%s of $F_{max}$).'
        % (pct(r5['eq_to'], 1), pct(r10['eq_to'], 1), sgn(post10['rmod']), pct(post10['eps'], 1),
           post10['fi'], post10['fo'], r10['F_max_kN'], F('eqmod'),
           pct(rmod_before(by[('UT40', 500)]), 1), pct(r5['drop_eps'], 1), pct(r5['Rmod_max_after5'], 0)),
    ])
    P('At 100 s⁻¹ the UT40 is in equilibrium from %s strain to the end of the pulse (max $\\lvert R_{mod}\\rvert$ '
      'after 5 %%: %s).' % (pct(by[('UT40', 100)][0]['eps_eq'], 1), pct(by[('UT40', 100)][0]['Rmod_max_after5'], 1)))
    D.fig('onset40', 'F1b_equilibrium_onset_UT40.png', 'UT40: start of loading',
          'as %s, for the UT40. Coloured vertical line: instant from which $\\lvert R\\rvert$ < 5 %% (for a partial '
          'equilibrium: start of the longest interval).' % F('onset19'),
          'filtered section forces.',
          'at 500 and 1000 s⁻¹ the solid line (input side) rises before the dashed one (output side): the force '
          'needs time to cross the long parallel section.')
    D.H(3, 'Effect of the filter')
    P('All indicators above use forces filtered at 100 kHz. %s shows the same indicators on the raw forces '
      'written by Abaqus.' % T('filter'))
    D.tab('filter', 'Effect of the 100 kHz filter (exact section forces)',
          ['Specimen / target rate (s⁻¹)', 'Equilibrium from, raw / filtered', 'Max $\\lvert R\\rvert$ after 5 %, raw / filtered'],
          [[label(r), '%s / %s' % (fmt(100 * r['eps_eq_raw'], '%.1f %%'), fmt(100 * r['eps_eq'], '%.1f %%')),
            '%s / %s' % (pct(r['R_max_after5_raw'], 1), pct(r['R_max_after5'], 1))] for r in rows],
          '"n/a": no equilibrium until the end of the window. *Raw*: one point per µs, as written by Abaqus.')
    diff = [r for r in rows if np.isnan(r['eps_eq_raw']) != np.isnan(r['eps_eq'])]
    P('The filter removes vibrations of a few microseconds that the experiment cannot resolve; it does not '
      'change the verdict of the UT40 cases (partial equilibrium with and without filter).' +
      (' Without filter, %s: the raw forces carry vibrations of a few µs that slightly exceed the 5 %% limit; '
       'the filtered force difference stays small (%s).'
       % ('; '.join('%s reaches %s after 5 %% strain instead of %s' % (label(r), pct(r['R_max_after5_raw'], 1),
                                                                        pct(r['R_max_after5'], 1)) for r in diff),
          ', '.join('%s: %s' % (label(r), kn(r['dF_max_after5_kN'])) for r in diff)) if diff else
       ' The verdict is the same with and without filter in every case.'))

    # ------------------------------------------------------------------ reponse 2
    D.H(2, 'Answer 2 – Loading speeds for 30 % strain')
    D.H(3, 'Results')
    D.tab('cond', 'Test conditions and strain reached',
          ['Specimen / target rate (s⁻¹)', 'Striker velocity', 'Incident stress', 'Achieved rate', 'Time to 30 %', 'Max strain'],
          [[label(r), '%.2f m/s' % r['v_striker'], '%.0f MPa' % (RHO_C_BAR * K * r['v_striker'] / 1e6),
            '%.0f s⁻¹ (%s)' % (r['achieved_rate'], sgn(r['achieved_rate'] / r['target_rate'] - 1)),
            ('%.2f ms' % r['time_to_30_ms']) if r['reached_30'] else 'not reached', pct(r['eps_max'], 1)]
           for r in rows],
          '*Incident stress*: stress of the incident wave in the input bar, $\\rho c\\,K V$ (elastic for '
          'maraging steel). *Achieved rate*: definition above, in brackets the deviation from the target. *Time '
          'to 30 %*: from the loading start. *Max strain*: 30 %, or less if the loading pulse ends before.')
    D.fig('rate', 'F4_strain_rate.png', 'Strain rate during the test',
          'the strain rate (logarithmic scale) against the engineering strain, one panel per specimen; dotted '
          'lines: targets; dots: force maximum (onset of necking).',
          'time derivative of the filtered extensometer strain.',
          'the curve should stay close to its target. Being a derivative, it amplifies the small vibrations of '
          'the specimen (±10 to 30 % at 1000 s⁻¹). A curve that drops before 30 % shows the end of the loading '
          'pulse.')
    D.tab('rates', 'Strain rate with different definitions (s⁻¹)',
          ['Specimen / target rate (s⁻¹)', 'Achieved ($\\varepsilon_1 \\to \\varepsilon_2$)', 'At max force', 'Nominal', 'Before / after max force'],
          [[label(r), '%.0f (5 → %.1f %%)' % (r['achieved_rate'], 100 * r['eps2']), '%.0f' % r['rate_at_Fmax'],
            '%.0f' % r['rate_nominal'], '%.0f–%.0f / %s' % (r['rate_pre_p10'], r['rate_pre_p90'],
                                                           fmt(r['rate_post_p10'], '%.0f') + '–' + fmt(r['rate_post_p90'], '%.0f'))]
           for r in rows],
          '*At max force*: value of %s at the dot. *Nominal*: final strain divided by the whole loading time, '
          'start-up included. *Before / after max force*: range of the curve of %s before and after the dot '
          '(10th to 90th percentile).' % (F('rate'), F('rate')))
    P('After the force maximum the strain rate settles close to the target and increases slowly, because the '
      'force decreases (necking) and brakes the bench less. Before the force maximum, during uniform '
      'hardening, the rate is still building up at 500 and 1000 s⁻¹ (the "at max force" values are below the '
      'achieved rate).')
    D.fig('window', 'G1_strain_time.png', 'Strain against time: the test window',
          'the extensometer strain against the time from the loading start, one panel per specimen. Dotted line: '
          '30 % target; dash-dotted line: end of the incident pulse of the 5 m striker; dashed line (UT40): '
          'fracture strain of DP1000 in a quasi-static test on the same geometry; circle: sudden localisation.',
          'filtered extensometer strain.',
          'the slope is the strain rate. At 100 s⁻¹ the strain stops growing at the end of the pulse, before '
          '30 %; at 500 and 1000 s⁻¹ 30 % is reached well within the pulse.')
    D.H(3, 'Striker velocity formula')
    P('The elongation rate of the inverter (pusher pocket moving away from the output pocket) is approximately')
    P('$$\nv \\approx 2\\,v_i - \\frac{2F}{\\rho c A}, \\qquad v_i = K\\,V, \\qquad K = '
      '\\frac{Z_{striker}}{Z_{striker} + Z_{bar}} = %.3f\n$$' % K)
    P('where $V$ is the striker velocity, $v_i$ the particle velocity of the incident wave, $F$ the specimen '
      'force and $\\rho c A$ = %.0f N·s/m the impedance of the bars: the specimen force both slows the pusher '
      'down and pushes the output bar. Writing $v = \\dot\\varepsilon\\,L_{eff}$ gives' % Z_BAR)
    P('$$\nV = \\frac{\\dot\\varepsilon\\,L_{eff} + 2F/(\\rho c A)}{2K}\n$$')
    P('$L_{eff}$ is an effective length relating the elongation rate of the pockets to the strain rate of the '
      'extensometer, and $F$ an effective specimen force. Both are calibrated on simulations:')
    D.tab('calib', 'Constants of the striker formula',
          ['Specimen', '$L_{eff}$', '$F$', 'Calibration', 'Velocities for 100 / 500 / 1000 s⁻¹'],
          [['UT19', '%.1f mm' % sp['UT19']['L_eff_mm'], '%.1f kN' % (sp['UT19']['F_N'] / 1e3),
            'first UT19 simulation at 500 s⁻¹ (study `taskI_20261013-1127`: 485 s⁻¹ achieved, mean force 6.4–6.8 kN)',
            ' / '.join('%.2f' % make_run.striker_velocity('UT19', x) for x in (100, 500, 1000)) + ' m/s'],
           ['UT40', '%.1f mm' % sp['UT40']['L_eff_mm'], '%.1f kN' % (sp['UT40']['F_N'] / 1e3),
            'first UT40 study (`%s`) at 100 and 500 s⁻¹: two runs, two unknowns (Appendix C)' % FIRST_UT40,
            ' / '.join('%.2f' % make_run.striker_velocity('UT40', x) for x in (100, 500, 1000)) + ' m/s']])
    P('$L_{eff}$ is shorter than the parallel section (12.7 instead of 15 mm for the UT19; 30.1 instead of '
      '40 mm for the UT40), because the extensometer sees the most strained part of it. The effective force is '
      'lower than the maximum force (7.0 against ≈ 7.5 kN, 10.4 against ≈ 15 kN) because the force decreases '
      'during necking, much more for the UT40. The force term matters: at 100 s⁻¹, $2F/\\rho c A$ is as large '
      'as the useful term $\\dot\\varepsilon L_{eff}$ (UT19: %.2f against %.2f m/s; UT40: %.2f against %.2f m/s), '
      'so a 10 %% error on $F$ gives about 10 %% error on the strain rate. A first estimate without it '
      '($V = \\dot\\varepsilon \\times$ 15 mm) gave 21 s⁻¹ instead of 100 s⁻¹ for the UT19.'
      % (2 * sp['UT19']['F_N'] / Z_BAR, 100 * sp['UT19']['L_eff_mm'] * 1e-3, 2 * sp['UT40']['F_N'] / Z_BAR,
         100 * sp['UT40']['L_eff_mm'] * 1e-3))
    D.fig('striker', 'F5_striker_velocity.png', 'Striker velocity required for a given strain rate',
          'the striker velocity against the achieved strain rate, one panel per specimen. Line: the formula with '
          'the constants of %s. Dots: the reference simulations. Shaded: 30 %% strain not reachable with the 5 m '
          'striker.' % T('calib'),
          'formula of `make_run.py`; simulation results.',
          'choose a strain rate on the horizontal axis and read the striker velocity on the line; a dot on the '
          'line means that the formula predicted the simulation exactly.')
    # recalage par moindres carres (propose, non simule)
    pts19 = [(r['achieved_rate'], r['v_striker']) for r in u19]
    pts40 = [(r['achieved_rate'], r['v_striker']) for r in u40] + \
            [(by_f[k]['achieved_rate'], by_f[k]['v_striker']) for k in (100, 500)]
    L19, F19 = refit(pts19)
    L40, F40 = refit(pts40)
    P('**Accuracy and possible refinement.** With these constants the achieved rates deviate from the targets '
      'by %s (UT19) and %s (UT40) (%s). The constants can be refined by a least-squares fit of the formula on '
      'all the simulations of each specimen (three UT19 runs; five UT40 runs: the reference study and the two '
      'usable runs of the first one):'
      % (' / '.join(sgn(r['achieved_rate'] / r['target_rate'] - 1) for r in u19),
         ' / '.join(sgn(r['achieved_rate'] / r['target_rate'] - 1) for r in u40), T('cond')))
    D.tab('refit', 'Refined striker velocities (least-squares fit, not yet simulated)',
          ['Specimen', 'Fitted $L_{eff}$', 'Fitted $F$', 'Velocity for 100 / 500 / 1000 s⁻¹', 'Change'],
          [[s, '%.1f mm' % L, '%.1f kN' % (Fv / 1e3),
            ' / '.join('%.2f' % v_formula(x, L, Fv) for x in (100, 500, 1000)) + ' m/s',
            ' / '.join(sgn(v_formula(x, L, Fv) / make_run.striker_velocity(s, x) - 1) for x in (100, 500, 1000))]
           for s, L, Fv in (('UT19', L19, F19), ('UT40', L40, F40))],
          '*Change*: relative to the velocities used in the reference simulations. These values are a better '
          'fit of the simulations, but they have not been checked by a simulation; they remain subject to the '
          'rate dependence of the real material (section *Limitations*).')
    D.H(3, 'Limit for 30 % strain')
    r100 = by[('UT40', 100)][0]
    t40, l40 = rt.needed_striker(r100)
    t19, l19 = rt.needed_striker(by[('UT19', 100)][0])
    P('The 5 m striker gives a %.2f ms loading pulse, so 30 %% strain requires at least 0.30 / %.2f ms ≈ %.0f '
      's⁻¹; the output bar (5.99 m) also limits the measurement window to %.2f ms (Beerli et al. 2026). At '
      '100 s⁻¹ the strain stops at %s (UT19, %.0f s⁻¹) and %s (UT40, %.0f s⁻¹). Reaching 30 %% at these rates '
      'would need a loading of about %.1f ms (UT19) and %.1f ms (UT40), i.e. a striker of about %.1f m and '
      '%.1f m: longer than the measurement window, and for the UT40 longer than the 7.5 m launch tube.'
      % (rt.PULSE_MS, rt.PULSE_MS, rate_min, rt.OUTPUT_WINDOW_MS, pct(by[('UT19', 100)][0]['eps_max'], 1),
         by[('UT19', 100)][0]['achieved_rate'], pct(r100['eps_max'], 1), r100['achieved_rate'], t19, t40, l19, l40))
    P('**Answer.** To reach 30 %% engineering strain: about %.1f m/s (500 s⁻¹) and %.1f m/s (1000 s⁻¹) for the '
      'UT19; %.1f m/s (500 s⁻¹) and %.1f m/s (1000 s⁻¹) for the UT40. At 100 s⁻¹, 30 %% is not reachable with the '
      '5 m striker (above ≈ %.0f s⁻¹ only). The maximum velocity of the launcher has to be checked for the UT40 '
      'at 1000 s⁻¹ (%.1f m/s; incident stress ≈ %.0f MPa in the bars).'
      % (by[('UT19', 500)][0]['v_striker'], by[('UT19', 1000)][0]['v_striker'], by[('UT40', 500)][0]['v_striker'],
         by[('UT40', 1000)][0]['v_striker'], rate_min, by[('UT40', 1000)][0]['v_striker'],
         RHO_C_BAR * K * by[('UT40', 1000)][0]['v_striker'] / 1e6))

    # ------------------------------------------------------------------ comparaison
    D.H(2, 'UT19 and UT40 compared')
    P('The two specimens have the same heads and the same section-to-width ratio; they differ by the length of '
      'the parallel section (15 against 40 mm) and its width (5 against 10 mm).')
    D.fig('cmp', 'G2_UT19_vs_UT40.png', 'UT19 and UT40 at the same target rate',
          'top row: engineering stress (mean of $F_{in}$ and $F_{out}$ divided by $A_0$) against the engineering '
          'strain; bottom row: $R_{mod}$; one column per target rate; blue UT19, orange UT40.',
          'filtered section forces of the reference simulations.',
          'the stress curves coincide up to the force maximum (same material); after it, the longer UT40 loses '
          'its force much faster, because the same neck is averaged over a longer extensometer. In the bottom '
          'row, the UT40 leaves the ±5 % band at 500 and 1000 s⁻¹.')
    rows_cmp = []
    for k in (100, 500, 1000):
        a, b = by[('UT19', k)][0], by[('UT40', k)][0]
        rows_cmp.append(['%d s⁻¹' % k, '%s / %s' % (pct(a['eps_at_Fmax'], 1), pct(b['eps_at_Fmax'], 1)),
                         '%.0f / %.0f µs' % (1e6 * t_fmax(by[('UT19', k)]), 1e6 * t_fmax(by[('UT40', k)])),
                         '%s / %s' % (pct(a['Rmod_max_after5'], 1), pct(b['Rmod_max_after5'], 1)),
                         '%s / %s' % (pct(force_at(by[('UT19', k)], 0.3), 0), pct(force_at(by[('UT40', k)], 0.3), 0))
                         if a['reached_30'] and b['reached_30'] else 'not reached'])
    D.tab('cmp', 'UT19 / UT40 side by side',
          ['Target rate', 'Strain at max force', 'Time to max force', 'Max $\\lvert R_{mod}\\rvert$ after 5 %', 'Force at 30 % / max force'],
          rows_cmp,
          'Each cell: UT19 / UT40. *Time to max force*: from the loading start. *Force at 30 %*: mean of '
          '$F_{in}$ and $F_{out}$; for the UT40 at 500 s⁻¹ it is read after the sudden localisation and only '
          'indicative.')
    cp5, h5 = plastic_wave_speed(0.05)
    cp1, h1 = plastic_wave_speed(0.01)
    c0 = np.sqrt(SV['E'] * 1e6 / SV['rho'])
    P('**Why the UT40 is harder to equilibrate (interpretation).** Equilibrium needs the stress waves to cross '
      'the specimen several times while the force changes. In the elastic range the waves travel at '
      '$c_0 = \\sqrt{E/\\rho}$ = %.0f m/s and cross the parallel section in %.0f µs (UT19) or %.0f µs (UT40). '
      'Once the specimen yields, the changes of force travel at the plastic wave speed $c_p = \\sqrt{h/\\rho}$, '
      'with $h = dk/d\\varepsilon_p$ the slope of the hardening law: $h$ = %.0f MPa and $c_p$ = %.0f m/s at '
      '1 %% plastic strain, %.0f MPa and %.0f m/s at 5 %%. One crossing of the parallel section then takes '
      '≈ %.0f–%.0f µs for the UT19 and ≈ %.0f–%.0f µs for the UT40. The force maximum is reached ≈ %.0f µs '
      'after the loading start at 1000 s⁻¹ (%s): about %.0f to %.0f plastic crossings for the UT19, but only '
      '%.1f to %.1f for the UT40. After the maximum force (Considère) the slope of the engineering stress–strain '
      'curve is negative, the neck concentrates the deformation, and the remaining force differences are no '
      'longer evened out. This is consistent with the simulations: the UT40 is in equilibrium at 100 s⁻¹ '
      '(%.0f µs to the force maximum) and only during an intermediate interval at 500 and 1000 s⁻¹.'
      % (c0, 15e-3 / c0 * 1e6, 40e-3 / c0 * 1e6, h1, cp1, h5, cp5, 15e-3 / cp1 * 1e6, 15e-3 / cp5 * 1e6,
         40e-3 / cp1 * 1e6, 40e-3 / cp5 * 1e6, 1e6 * t_fmax(by[('UT40', 1000)]), T('cmp'),
         t_fmax(by[('UT19', 1000)]) / (15e-3 / cp5), t_fmax(by[('UT19', 1000)]) / (15e-3 / cp1),
         t_fmax(by[('UT40', 1000)]) / (40e-3 / cp5), t_fmax(by[('UT40', 1000)]) / (40e-3 / cp1),
         1e6 * t_fmax(by[('UT40', 100)])))
    P('**Consequence for the tests.** The neck needs about the same elongation in both specimens, but it is '
      'averaged over a 30 mm extensometer instead of 12 mm: to reach 30 %% engineering strain the neck of the '
      'UT40 must provide ≈ %.1f mm of elongation against ≈ %.1f mm for the UT19, and the force falls to '
      '≈ %s of its maximum instead of ≈ %s (1000 s⁻¹, %s). The UT40 is therefore much closer to fracture at 30 %% strain.'
      % (0.3 * L0['UT40'], 0.3 * L0['UT19'], pct(force_at(by[('UT40', 1000)], 0.3), 0),
         pct(force_at(by[('UT19', 1000)], 0.3), 0), T('cmp')))

    # ------------------------------------------------------------------ mesure
    D.H(2, 'What the experiment will measure')
    P('In the experiment the specimen force is only known from the output bar gauge. %s, %s and %s compare this '
      'signal, as it would be recorded, with the exact specimen force.' % (F('f19'), F('f40'), F('ss')))
    D.fig('f19', 'F2_forces_UT19.png', 'UT19: specimen forces and output bar gauge',
          'axial force against the time from the loading start, one panel per target rate. Coloured solid line: '
          '$F_{in}$; coloured dashed line: $F_{out}$; black line: force read on the output bar gauge.',
          'gauge force $A_{bar} E_{bar} \\varepsilon_{gauge}$ shifted by %.0f µs; all signals filtered at 100 kHz.'
          % shift_us,
          'overlapping coloured lines mean equilibrium; the distance between the black line and the coloured '
          'lines is the measurement error of the gauge.')
    D.fig('f40', 'F2_forces_UT40.png', 'UT40: specimen forces and output bar gauge',
          'as %s, for the UT40.' % F('f19'), 'as %s.' % F('f19'),
          'at 500 s⁻¹, after the sudden localisation, the forces at both ends and the gauge oscillate.')
    D.fig('ss', 'F3_stress_strain.png', 'Engineering stress–strain curves: true and measured',
          'one panel per specimen (rows) and target rate (columns): engineering stress $F / A_0$ against the '
          'engineering strain. **Both curves come from the same simulation** and differ by where the force is '
          'taken. Thick grey line: true force in the specimen (cross-section, simulation only). Coloured line: '
          'force read by the virtual gauge on the output bar, 400 mm from the specimen, where the real gauge '
          'is: the curve the experiment will give.',
          'filtered signals; gauge signal shifted as above. Error in the panel title: largest gap after 5 % '
          'strain, relative to the maximum force.',
          'where the coloured line follows the grey one, the gauge measures the specimen correctly. The grey '
          'curves are the same at the three rates because the simulated material is rate independent.')
    D.tab('gauge', 'Error of the output bar gauge',
          ['Specimen / target rate (s⁻¹)', 'Max error after 5 %', 'Before a sudden localisation', 'Fastest force drop (10 µs)'],
          [[label(r), pct(r['gauge_err_after5'], 1),
            pct(r['gauge_err_before_drop'], 1) if not np.isnan(r['drop_eps']) else 'no localisation',
            '%.2f kN' % r['fastest_drop_kN']] for r in rows],
          '*Error*: largest difference between the gauge force and the true specimen force, relative to the '
          'maximum force. *Fastest force drop*: largest decrease of the mean specimen force (unfiltered) within '
          '10 µs after the force maximum.')
    P('Except after the sudden localisation of the UT40 at 500 s⁻¹, the gauge follows the specimen force within '
      '%s of the maximum force.' % pct(max([r['gauge_err_after5'] for r in no_drop] + [r['gauge_err_before_drop'] for r in drops]), 1))
    D.H(3, 'The initial contact is essential')
    P('Before 22 Oct 2026 the specimen was centred in the pockets, with a clearance of 0.36 mm on each side. The '
      'same UT19 simulations (same striker velocities) gave a very different measurement:')
    D.tab('contact', 'UT19: specimen centred with clearances (study `%s`) and in contact (`%s`)' % (CENTRED_UT19, REF['UT19']),
          ['Indicator', '100 s⁻¹', '500 s⁻¹', '1000 s⁻¹'],
          [['Equilibrium from'] + ['%s → %s' % (eq_from_txt(by_c[k]), eq_from_txt(by[('UT19', k)][0])) for k in (100, 500, 1000)],
           ['Max $\\lvert R\\rvert$ after 5 %'] + ['%s → %s' % (pct(by_c[k]['R_max_after5'], 1), pct(by[('UT19', k)][0]['R_max_after5'], 1)) for k in (100, 500, 1000)],
           ['**Gauge error after 5 %**'] + ['%s → **%s**' % (pct(by_c[k]['gauge_err_after5'], 1), pct(by[('UT19', k)][0]['gauge_err_after5'], 1)) for k in (100, 500, 1000)],
           ['Achieved rate (s⁻¹)'] + ['%.0f → %.0f' % (by_c[k]['achieved_rate'], by[('UT19', k)][0]['achieved_rate']) for k in (100, 500, 1000)],
           ['Max strain'] + ['%s → %s' % (pct(by_c[k]['eps_max'], 1), pct(by[('UT19', k)][0]['eps_max'], 1)) for k in (100, 500, 1000)]],
          'Each cell: centred → in contact. Same processing for both studies.')
    D.fig('contact', 'G3_contact_effect_UT19.png', 'UT19: effect of the initial contact',
          'top row: centred specimen with clearances; middle row: specimen in contact; engineering stress from '
          'the true force (grey) and from the output gauge (colour) against strain. Bottom row: first 150 µs of '
          'loading, output-side specimen force, unfiltered, centred (grey) and in contact (colour).',
          'studies `%s` and `%s`, same processing.' % (CENTRED_UT19, REF['UT19']),
          'with clearances the measured curve oscillates around the true one, up to 1000 s⁻¹ where the error '
          'reaches %s; in contact the two curves coincide. Bottom: with clearances the force jumps, drops to '
          'zero and rebounds; in contact it rises smoothly.' % pct(by_c[1000]['gauge_err_after5'], 0))
    P('**What happened with the clearances** (probe study `diag_20261021-1626`, UT19 at 1000 s⁻¹): the specimen, '
      'pulled by the pusher, travelled ≈ 0.3 mm across the clearance of the output pocket before pulling on the '
      'output head, and **hit** it: a force spike of ≈ 15 kN, twice the force the specimen can carry, after which '
      'the output head rang at ≈ 40 kHz for ≈ 0.25 ms. The gauge recorded this ringing on top of the specimen '
      'force (%s). At 1000 s⁻¹, 30 %% strain is reached in 0.33 ms, before the ringing has died out.' % F('gap'))
    D.img('gap', 'img/gap_impact_UT19_R1000.png', 'UT19 centred at 1000 s⁻¹: the specimen crosses the clearance and hits the output head',
          'top: force in the specimen (grey) and in the output head (blue, moved back by its 8.5 µs of wave '
          'travel), first 120 µs, unfiltered; bottom: displacement of the output end of the specimen. Shaded: the '
          'specimen is pulled but the head does not feel anything yet.',
          'probe study `diag_20261021-1626`; lab journal, 22 Oct 2026.')
    D.H(3, 'Where a measurement error comes from: force probes')
    P('In the four simulations with force probes, the force through five slices of the output side (output '
      'head, tie, bar) was compared with the true specimen force, each signal moved back by its own wave travel '
      'time to the bar end (%s, %s).' % (F('probes'), T('probes')))
    keys = ['HEAD_MID', 'HEAD_TIE', 'BAR_TIE', 'BAR_100', 'BAR_250', 'GAUGE_OUT']
    names = {'HEAD_MID': 'output head, 14 mm above the tie', 'HEAD_TIE': 'output head, 4 mm above the tie',
             'BAR_TIE': 'bar, just below the tie', 'BAR_100': 'bar, 100 mm from its end',
             'BAR_250': 'bar, 250 mm from its end', 'GAUGE_OUT': 'gauge, 400 mm from the bar end'}
    D.tab('probes', 'Max error after 5 % strain at each probe (% of the max force)',
          ['Position'] + [n for n, _ in prb],
          [[names[k]] + [pct(res[k][1], 1) if k in res else '–' for _, res in prb] for k in keys],
          'Same computation as `scripts/post/plot_probes.py`.')
    D.fig('probes', 'G5_probes_error.png', 'Error of the force along the output side',
          'the largest error after 5 % strain (logarithmic scale) at each probe, against its distance from the '
          'pocket end of the output bar, one line per simulation. Shaded: the output head (55.7 mm, tied to the '
          'bar).',
          'probe forces and gauge, filtered at 100 kHz, each moved back by its wave travel time.',
          'a flat line means that the error is already there in the head and is only carried along the bar: it '
          'is created between the specimen and the head. Error ≈ 5 % everywhere: the measurement is good.')
    P('In every case the error is the same at every position: it is created at the specimen–head interface, '
      'not by the tie or by the travel along the bar. The two large errors have the same mechanism, a force '
      '**step** that sets the head ringing: the impact after the clearance (UT19 centred) and the collapse of '
      'the neck (first UT40 run at 1000 s⁻¹, below). With the specimen in contact and no localisation, the '
      'error is %s (UT19) and %s (UT40) at every position.'
      % (pct(prb[1][1]['GAUGE_OUT'][1], 1), pct(prb[3][1]['GAUGE_OUT'][1], 1)))
    D.H(3, 'Why a sudden localisation makes the gauge wrong')
    P('The gauge does not measure the specimen: it measures the wave in the output bar, 400 mm away, after the '
      'force has gone through the specimen head, the pocket and the output head, and it is moved back in time '
      'by %.0f µs. This works as long as the specimen force changes **slowly** compared with the time the waves '
      'need to cross these parts (a few tens of µs): they then simply pass the force on. All specimens neck, '
      'but in a normal neck the force decreases gradually: at most %.1f kN in 10 µs in the runs without '
      'localisation. When a few elements collapse in the neck, the force drops by %s in 10 µs, a step instead of '
      'a slope; the heads and the output bar are set ringing, and the gauge records the ringing on top of the '
      'specimen force. Before the localisation the gauge error of the UT40 at 500 s⁻¹ is only %s.'
      % (shift_us, max(r['fastest_drop_kN'] for r in no_drop),
         ' / '.join('%.1f kN (%s)' % (r['fastest_drop_kN'], label(r)) for r in drops),
         ' / '.join(pct(r['gauge_err_before_drop'], 1) for r in drops)))

    # ------------------------------------------------------------------ validite
    D.H(2, 'Necking, localisation and fracture: how far the results are valid')
    D.H(3, 'What happens in the specimen')
    P('After the force maximum (%s strain) the specimen necks: the deformation concentrates in a short zone of '
      'the parallel section, which thins in width and thickness while the rest of the specimen stops deforming. '
      'The force decreases. To reach 30 %% strain over the extensometer, the neck alone has to provide almost all '
      'the elongation (≈ %.1f mm for the UT19, ≈ %.1f mm for the UT40).'
      % ('%.0f to %s' % (100 * min(r['eps_at_Fmax'] for r in rows), pct(max(r['eps_at_Fmax'] for r in rows), 0)),
         0.3 * L0['UT19'], 0.3 * L0['UT40']))
    P('**What the model cannot do: fracture.** The DP1000 model has **no fracture criterion**. A real sheet '
      'breaks in the neck; the simulated one keeps stretching until the elements at the centre of the neck '
      'collapse. The results after that are a numerical consequence of the missing fracture model, not an '
      'effect of the test.')
    D.H(3, 'The sudden localisation of the UT40 at 500 s⁻¹')
    rr5, cc5 = by[('UT40', 500)]
    drop = drop_detail(by[('UT40', 500)])
    P('At %.2f ms after the loading start (%s strain) both specimen forces drop within 10 µs (input side %.1f → '
      '%.1f kN, output side %.1f → %.1f kN, unfiltered), then reload with strong oscillations, while the '
      'extensometer keeps stretching to 30 %%. Three explanations were checked in Abaqus/Viewer on the field '
      'outputs around this instant (frames 79, 81 and 83: 1.686, 1.728 and 1.771 ms of simulated time; lab '
      'journal, 27 Oct 2026):'
      % (rr5['drop_t_ms'], pct(rr5['drop_eps'], 1), drop['fi0'], drop['fi1'], drop['fo0'], drop['fo1']))
    D.tab('hyp', 'Three explanations of the force drop, and their check',
          ['Explanation', 'Check in Abaqus/Viewer', 'Result'],
          [['the teeth slip or lose contact in the pusher pocket', 'axial displacement of a specimen node and of the facing pusher node across a loaded tooth flank',
            'rejected: the relative displacement changes by ≈ 10 µm (relaxation of the contact compression when the force drops); a slip would be tenths of a mm'],
           ['the specimen lifts out of the pockets', 'out-of-plane displacement U3, frames 79 / 81 / 83',
            'rejected: heads and pusher stay at U3 ≈ 0; only the neck moves (±0.5 mm, thinning through the thickness)'],
           ['something sudden happens in the neck', 'equivalent plastic strain PEEQ, frames 79 / 81 / 83',
            '**confirmed**: max PEEQ 1.15 → 9.19 → 11.7 in ≈ 40 µs, at one spot at the centre of the neck']])
    D.img('teeth', 'img/ecart_dents_UT40_R0500.png', 'Relative displacement across a loaded tooth flank',
          'axial displacement U2 of a specimen node minus that of the facing pusher node, against time, UT40 at '
          '500 s⁻¹ (one point per field frame). Shaded: the force drop. While loaded the specimen node lags by '
          '8–9 µm (elastic compression of the teeth); during the drop the difference changes by ≈ 10 µm only.',
          'Abaqus/Viewer, XY report of `UT40_R0500_00.odb`; lab journal, 27 Oct 2026.')
    P('U3 (out of the sheet plane) at the three frames:')
    for k, tt in ((79, '1.686'), (81, '1.728'), (83, '1.771')):
        D.img('u3_%d' % k, 'img/U3_frame%d.png' % k, 'UT40 / 500: out-of-plane displacement U3, frame %d (%s ms)' % (k, tt),
              'contour of U3 on the specimen and the pusher head, side view. Heads and pusher at U3 ≈ 0 (green); '
              'non-zero values only in the neck.',
              'Abaqus/Viewer, `UT40_R0500_00.odb`; lab journal, 27 Oct 2026.')
    P('PEEQ at the three frames (the colour scale changes from one frame to the next):')
    for k, tt, txt in ((79, '1.686', 'max 1.15, spread over a few mm of the parallel section'),
                       (81, '1.728', 'max 9.19 at one spot at the centre of the neck, on the symmetry plane'),
                       (83, '1.771', 'max 11.7, same spot')):
        D.img('pq_%d' % k, 'img/PEEQ_frame%d.png' % k, 'UT40 / 500: equivalent plastic strain, frame %d (%s ms)' % (k, tt),
              'contour of PEEQ, view from the top (half model, symmetry plane on the left): %s.' % txt,
              'Abaqus/Viewer, `UT40_R0500_00.odb`; lab journal, 27 Oct 2026.')
    P('**Conclusion.** In ≈ 40 µs the deformation concentrates in a few elements at the centre of the neck, which '
      'thin out almost completely (PEEQ ≈ 9, a true strain of 900 %). The section loses its load-carrying '
      'capacity at that point, the specimen unloads elastically on both sides, then reloads and oscillates. '
      'A real DP1000 sheet would have broken long before.')
    D.H(3, 'The first UT40 run at 1000 s⁻¹: localisation outside the extensometer')
    rf = by_f[1000]
    P('In the first UT40 study the striker velocity for 1000 s⁻¹ was estimated too high (%.2f m/s instead of '
      '%.2f m/s after recalibration). The extensometer strain rose to ≈ 11 %% in ≈ 0.2 ms and then stopped (%s '
      'at the end), while the forces collapsed (sudden localisation at %s strain). The extensometer node on the '
      'pusher side stopped and even moved back (%s, right): the material inside the extensometer was unloading, '
      'so the deformation continued **between the extensometer and the pusher head**. Abaqus/Viewer confirmed '
      'that the neck formed at the pusher-side end of the parallel section (%s). With the recalibrated velocity '
      'and the same (slightly tapered) geometry, the strain stays inside the extensometer and reaches 30 %%. Up to '
      '≈ 0.2 ms both runs are almost identical (%s); the localisation at the pulled end is therefore attributed '
      'to the higher pulling speed of the first run (pusher-side node up to ≈ 30 m/s), not to the 0.02 mm taper, '
      'which is the same in both runs.'
      % (rf['v_striker'], by[('UT40', 1000)][0]['v_striker'], pct(rf['eps_max'], 1), pct(rf['drop_eps'], 1),
         F('first'), F('peeq1000'), F('first')))
    D.fig('first', 'G4_first_UT40_R1000.png', 'UT40 at 1000 s⁻¹: first run and recalibrated run',
          'against the time from the loading start: extensometer strain (left), input-side specimen force '
          '(middle), velocity of the two extensometer nodes (right; solid: pusher side, dashed: output side). '
          'Grey: first run; green: recalibrated run; red line: sudden localisation of the first run.',
          'studies `%s` and `%s`, filtered at 100 kHz.' % (FIRST_UT40, REF['UT40']),
          'in the first run the pusher-side node stops and moves back at the localisation, and the strain '
          'stops at ≈ 12 %; in the recalibrated run both nodes keep moving apart.')
    D.img('peeq1000', 'img/UT40_R1000_PEEQ_last_frame.png', 'First UT40 run at 1000 s⁻¹: plastic strain at the end',
          'PEEQ at the last frame (1.834 ms), side view, pusher head at the top. The neck (red) is at the '
          'pusher-side end of the parallel section, just below the pusher head, outside the extensometer.',
          'Abaqus/Viewer, `%s/UT40_R1000_00.odb`; lab journal, 23 Oct 2026.' % FIRST_UT40)
    D.H(3, 'When does a real DP1000 specimen break?')
    P('Beerli et al. (2026, section 4.1.1, fig. 7a) report an engineering strain to fracture of **%s** for DP1000 '
      'in quasi-static uniaxial tension (0.001 s⁻¹) on the 40 × 10 mm UT specimen, i.e. the UT40 geometry, the '
      'lowest of the five DP steels of the paper. At high strain rates the elongation to fracture of DP1000 does '
      'not decrease (section 4.2.1), but no value is given. The paper\'s fracture model (Hosford–Coulomb with a '
      'neural-network rate dependence) has no published parameters. For the UT19 the engineering strain to '
      'fracture is larger, since the neck is a larger part of a shorter extensometer; no value is available.'
      % pct(rt.DP1000_UT_FRACTURE_EPS, 0))
    D.tab('valid', 'Validity of each reference simulation',
          ['Specimen / target rate (s⁻¹)', 'Max strain', 'Sudden localisation', 'Beyond 11 % (DP1000 fracture, UT40)?'],
          [[label(r), pct(r['eps_max'], 1),
            ('at %s (%.2f ms)' % (pct(r['drop_eps'], 1), r['drop_t_ms'])) if not np.isnan(r['drop_eps']) else 'none',
            ('yes, from %.2f ms' % t_at(by[(r['specimen'], int(r['target_rate']))], rt.DP1000_UT_FRACTURE_EPS))
            if r['specimen'] == 'UT40' and r['eps_max'] > rt.DP1000_UT_FRACTURE_EPS else
            ('no value for this geometry' if r['specimen'] == 'UT19' else 'no')] for r in rows],
          '*Sudden localisation*: definition above; time from the loading start.')
    P('**Consequences for Task I.**')
    D.bullets([
        'The equilibrium and gauge indicators are meaningful only before fracture. After a sudden localisation '
        'they describe a numerical artefact.',
        'For a DP1000 UT40, the question "which loading speed reaches 30 % strain?" has to be put together with '
        'fracture: with a quasi-static elongation to fracture of 11 %, 30 % engineering strain is very likely '
        'not reachable, whatever the loading speed. The speeds of Answer 2 remain valid for a more ductile '
        'material with similar strength.',
        'Even if the results are cut at 11 %%, the conclusion of Answer 1 does not change: the UT40 is in '
        'equilibrium at 100 s⁻¹, but at 500 and 1000 s⁻¹ only from %s to %s and from %s to %s strain, i.e. '
        'not until fracture.' % (pct(r5['eq_from'], 1), pct(r5['eq_to'], 1), pct(r10['eq_from'], 1),
                                 pct(r10['eq_to'], 1)),
    ])

    # ------------------------------------------------------------------ qualite numerique
    D.H(2, 'Numerical quality and computing cost')
    P('These checks do not answer the Task I questions: they verify that the simulations can be trusted.')
    D.tab('num', 'Numerical checks',
          ['Specimen / target rate (s⁻¹)', 'Incident strain / theory', 'Kinetic energy / ½mV²', 'Energy drift', 'Hourglass / internal'],
          [[label(r), '%.3f' % (r['incident_strain'] / r['incident_theory']), '%.3f' % r['ke0_ratio'],
            pct(r['energy_drift'], 2), pct(r['hourglass'], 1)] for r in rows])
    D.bullets([
        '**Incident strain / theory** – is the loading right? One-dimensional wave theory gives the incident '
        'strain $\\varepsilon_{inc} = K\\,V/c$. The simulated value is the plateau of the virtual gauge on the '
        'input bar. 1.000 means that the impact, the bar materials and the gauge reading are correct.',
        '**Kinetic energy / ½mV²** – is the striker mass right? At $t = 0$ only the striker moves. The ratio is '
        'slightly below 1 because the meshed circular section is a polygon of slightly smaller area; this does '
        'not change the incident wave, which depends on the velocity.',
        '**Energy drift** – does the calculation create or lose energy? Largest variation of the total energy '
        'balance of Abaqus (`ETOTAL`) during the run, relative to the initial kinetic energy; below ≈ 1 %, '
        'contacts, ties and time integration create no artificial energy.',
        '**Hourglass / internal** – does the mesh deform in a non-physical way? Energy absorbed by the '
        'artificial stiffness against the zero-energy modes of the reduced-integration hexahedra (`ALLAE`), '
        'relative to the deformation energy (`ALLIE`) at the end; usual limit 5 %.',
    ])
    D.tab('cpu', 'Computing cost (Euler, 8 cores per simulation)',
          ['Specimen / target rate (s⁻¹)', 'Simulated time', 'Increments', 'Final stable time increment', 'Wall time'],
          [[label(r), '%.3f ms' % r['t_step_ms'], '%d' % r['increments'], '%.1e s' % r['dt_final'],
            '%.0f min' % r['wall_min']] for r in rows],
          'From the `.sta` file of each run. The stable time increment falls when the neck elements become very '
          'thin (UT40 at 500 and 1000 s⁻¹).')

    # ------------------------------------------------------------------ limites
    D.H(2, 'Limitations')
    D.bullets([
        '**No fracture model** for the specimen: results after fracture are not representative (DP1000 UT40: '
        '≈ 11 % engineering strain in a quasi-static test).',
        '**Rate-independent material**: in the tests the force, hence the braking term $2F/\\rho c A$ and the '
        'required striker velocity, will increase with the strain rate.',
        '**Striker formula**: $L_{eff}$ and $F$ are effective constants calibrated on the simulations; the formula '
        'is least accurate at low rate, where the force term dominates.',
        '**Gauge signal**: shifted by the wave travel time, not corrected for dispersion; the reference point of '
        'the 400 mm distance is to be confirmed (≈ 6 µs uncertainty).',
        '**Initial contact without pre-load**, as described by the lab; a residual clearance or a pre-load in a '
        'real test would change the start of the signals.',
        '**Assumed values**: densities of the bars and of the striker; material of the pusher (maraging '
        'according to Beerli et al. 2026, tool steel according to an old CAD file).',
        '**Guides** modelled as continuous, frictionless and without clearance.',
        '**UT40 drawing**: slight taper of the parallel section and teeth 0.10 mm thicker than on the UT19, as '
        'in the cutting file; to be confirmed on real specimens.',
    ])

    # ------------------------------------------------------------------ conclusions
    D.H(2, 'Conclusions and recommendations')
    P('**Answer 1 – Force equilibrium.**')
    D.bullets([
        '**UT19**: quasi-static force equilibrium is reached from the very start of loading and maintained up to '
        '30 %% strain at 100, 500 and 1000 s⁻¹ ($\\lvert R\\rvert$ < 5 %%, $\\lvert R_{mod}\\rvert$ < %s over the '
        'whole window).' % pct(max(r['Rmod_max_all'] for r in u19), 0),
        '**UT40**: equilibrium at 100 s⁻¹ (from %s strain); at 500 and 1000 s⁻¹ only during the hardening phase '
        'and the beginning of necking (%s to %s and %s to %s strain).'
        % (pct(by[('UT40', 100)][0]['eps_eq'], 1), pct(r5['eq_from'], 1), pct(r5['eq_to'], 1),
           pct(r10['eq_from'], 1), pct(r10['eq_to'], 1)),
        'The short specimen should be preferred for dynamic tests at 500 and 1000 s⁻¹.',
    ])
    P('**Answer 2 – Loading speeds.**')
    D.tab('reco', 'Striker velocities for the experiments (5 m striker)',
          ['Specimen', '100 s⁻¹', '500 s⁻¹', '1000 s⁻¹'],
          [[s] + [('%.2f m/s → %s max' % (by[(s, k)][0]['v_striker'], pct(by[(s, k)][0]['eps_max'], 0)))
                  if not by[(s, k)][0]['reached_30'] else
                  '%.2f m/s → 30 %% in %.2f ms' % (by[(s, k)][0]['v_striker'], by[(s, k)][0]['time_to_30_ms'])
                  for k in (100, 500, 1000)] for s in ('UT19', 'UT40')],
          'Velocities of the reference simulations (rate-independent material). Refined values: %s.' % T('refit'))
    D.bullets([
        '30 %% strain cannot be reached below ≈ %.0f s⁻¹ with the 5 m striker.' % rate_min,
        'For DP1000, 30 % engineering strain is beyond the fracture strain of the UT40 (≈ 11 %).',
        '**For the tests**: bring the specimen teeth into contact with both pockets before the shot (as done in '
        'the lab); otherwise the gauge measures the impact of the specimen on the output head.',
    ])

    # ------------------------------------------------------------------ questions
    D.H(2, 'Open questions for the supervisors')
    D.bullets([
        'Is the specimen material of Task I DP1000? If yes, is 30 % engineering strain a meaningful target, '
        'given its fracture strain of ≈ 11 % on the UT40?',
        'Should a fracture criterion be added, and with which data (fracture strain or Hosford–Coulomb '
        'parameters)?',
        'Maximum striker velocity of the launcher (needed: up to %.1f m/s).' % max(r['v_striker'] for r in rows),
        'Reference point of the 400 mm distance of the output gauge; densities of the bars and of the striker; '
        'material of the pusher.',
        'Are the taper of the UT40 parallel section and its thicker teeth real (cutting file) or a drawing '
        'detail?',
    ])

    # ------------------------------------------------------------------ annexes
    D.H(2, 'Appendix A – Specimen forces over the whole test')
    P('$F_{in}$ and $F_{out}$ (exact section forces, filtered at 100 kHz) from the loading start to the end of '
      'the useful window (+ 15 %), one panel per target rate. Dotted lines: 5, 10, 20 and 30 % strain; red '
      'line: sudden localisation, if any. Equilibrium means that the two curves overlap.')
    for s in ('UT19', 'UT40'):
        D.fig('fa_%s' % s, 'FA_forces_full_%s.png' % s, '%s: input and output specimen forces over the whole test' % s,
              '$F_{in}$ (coloured) and $F_{out}$ (black dashed) against the time from the loading start, one panel '
              'per target rate.', 'reference study `%s`, filtered section forces.' % REF[s],
              'where the two curves overlap the specimen is in equilibrium; the vertical distance between them is '
              '$\\Delta F$.')
    D.H(2, 'Appendix B – UT19 centred in the pockets (study `%s`)' % CENTRED_UT19)
    P('Results of the UT19 with the old placement (specimen centred, clearance of 0.36 mm on each side), kept '
      'for comparison (%s).' % T('contact'))
    cen = [r for r, _ in centred]
    D.tab('cen', 'UT19 centred: main indicators',
          ['Target rate (s⁻¹)', 'Achieved rate', 'Equilibrium, $R$', 'Max $\\lvert R\\rvert$ after 5 %', 'Gauge error'],
          [['%d' % r['target_rate'], '%.0f s⁻¹' % r['achieved_rate'], eq_short(r), pct(r['R_max_after5'], 1),
            pct(r['gauge_err_after5'], 1)] for r in cen])
    D.H(2, 'Appendix C – First UT40 study and recalibration (study `%s`)' % FIRST_UT40)
    fst = [r for r, _ in first]
    P('The first UT40 velocities were estimated with $L_{eff}$ = 34 mm and $F$ = 15 kN (scaled from the UT19).')
    D.tab('first', 'First UT40 study: main indicators',
          ['Target rate (s⁻¹)', 'Striker velocity', 'Achieved rate', 'Max strain', 'Equilibrium, $R$', 'Sudden localisation'],
          [['%d' % r['target_rate'], '%.2f m/s' % r['v_striker'], '%.0f s⁻¹' % r['achieved_rate'],
            pct(r['eps_max'], 1), eq_short(r),
            ('at %s' % pct(r['drop_eps'], 1)) if not np.isnan(r['drop_eps']) else 'none'] for r in fst])
    a, b = by_f[100], by_f[500]
    P('**Recalibration.** Writing $2KV = \\dot\\varepsilon\\,L_{eff} + 2F/\\rho c A$ for the runs at 100 and '
      '500 s⁻¹ (the 1000 s⁻¹ run is not usable: localisation outside the extensometer) gives two equations for '
      'two unknowns:')
    P('$$\n2 \\times %.3f \\times %.2f = %.0f\\,L_{eff} + \\frac{2F}{%.0f}, \\qquad '
      '2 \\times %.3f \\times %.2f = %.0f\\,L_{eff} + \\frac{2F}{%.0f}\n$$'
      % (K, a['v_striker'], a['achieved_rate'], Z_BAR, K, b['v_striker'], b['achieved_rate'], Z_BAR))
    Lc, Fc = refit([(a['achieved_rate'], a['v_striker']), (b['achieved_rate'], b['v_striker'])])
    P('so $L_{eff}$ = %.1f mm and $F$ = %.1f kN (rounded to 30.1 mm and 10.4 kN in `make_run.py`). The '
      'effective force is low because the force of the UT40 drops strongly during necking.' % (Lc, Fc / 1e3))
    D.H(2, 'Appendix D – Force probes and control figures')
    P('Force along the output side for the two 1000 s⁻¹ reference runs (each probe compared with the true '
      'specimen force):')
    D.img('pr19', 'img/UT19_R1000_00_probes.png', 'UT19 / 1000 in contact: force at each probe',
          'grey thick line: true specimen force; blue: force through the slice at that position, moved back by '
          'its wave travel time; one panel per position from the output head (top) to the gauge (bottom).',
          '`scripts/post/plot_probes.py`, study `%s`.' % REF['UT19'])
    D.img('pr40', 'img/UT40_R1000_00_probes.png', 'UT40 / 1000 recalibrated: force at each probe',
          'as %s.' % F('pr19'), '`scripts/post/plot_probes.py`, study `%s`.' % REF['UT40'])
    P('Control figure of each reference simulation (unfiltered signals over the whole simulated time: bar '
      'gauges, specimen forces and gauge force not shifted, $R$, extensometer strain; shaded: from the loading '
      'start to 30 % strain):')
    for r in rows:
        D.fig('ov_%s' % r['case_id'], 'img/%s_overview.png' % r['case_id'], 'Control figure – %s' % label_long(r),
              'against the simulated time, top to bottom: strain of the input and output bar gauges; specimen '
              'forces $F_{in}$, $F_{out}$ and output gauge force (not shifted); $R$ unfiltered; extensometer '
              'strain.', 'study `%s`, raw signals (not filtered).' % r['study'],
              'shaded: from the loading start to 30 % strain (or to the maximum strain). The input gauge shows '
              'the incident pulse and the reflected wave; the output gauge shows the transmitted force about '
              '82 µs after the specimen force.')
    D.H(2, 'Appendix E – Files and reproducibility')
    D.bullets([
        '`T_all_runs.csv` (next to this report): every indicator of every simulation used in this report.',
        'Per-study reports: `results/<study>/report/report.md` (`scripts/post/report_taskI.py`).',
        'This report: `python shpb-ut-equilibrium/scripts/post/report_taskI_final.py` (reads the history files '
        'of the studies listed above; Abaqus/Viewer images are copied from `journal/figures/`).',
        'Model: `scripts/cae/build_bench.py` (Abaqus/CAE), `scripts/pre/make_run.py` (striker velocity and '
        'simulated time), `model/templates/SHPB_UT_main.inp`; documentation in `docs/`.',
        'References: Beerli et al. (2026), dynamic tensile testing with the load inversion device; Roth et al. '
        '(2015), mesh sizes and gauge filtering.',
    ])
    return D.text()


# ---------------------------------------------------------------- petits calculs pour le texte
def rmod_from(r, prefix, with_time=False):
    if r['t_eq_mod_ms'] < 0.005:
        return prefix + 'from the loading start'
    return prefix + 'from %s' % pct(r['eps_eq_mod'], 1) + (' (%.2f ms)' % r['t_eq_mod_ms'] if with_time else '')


def sgn(x):
    """Ecart relatif signe, en %, sans '-0 %'."""
    v = round(100 * x)
    return ('+%d %%' % v if v > 0 else ('−%d %%' % -v if v < 0 else '0 %'))


def eq_from_txt(r):
    if eq_ok(r):
        return pct(r['eps_eq'], 1)
    if not np.isnan(r['eq_from']):
        return 'partial'
    return 'never'


def t_fmax(rc):
    r, c = rc
    return c['t_ms'][c['iF']] * 1e-3          # s


def force_at(rc, e):
    """Force moyenne a la deformation e, en fraction de la force max."""
    r, c = rc
    i = int(np.argmax(c['eps'] >= e))
    return 0.5 * (c['Fi'][i] + c['Fo'][i]) / (1e3 * r['F_max_kN'])


def t_at(rc, e):
    r, c = rc
    return c['t_ms'][int(np.argmax((c['eps'] >= e) & (c['t_ms'] >= 0)))]


def rmod_range_before(rc):
    """Min et max de R_mod entre le debut du chargement et le debut du plus long intervalle d'equilibre."""
    r, c = rc
    m = c['win'] & (c['eps'] < r['eq_from'])
    return np.nanmin(c['R_mod'][m]), np.nanmax(c['R_mod'][m])


def rmod_peak_after(rc):
    """|R_mod| max apres l'intervalle d'equilibre (et avant une localisation brutale), avec les forces."""
    r, c = rc
    lim = r['drop_eps'] if not np.isnan(r['drop_eps']) else np.inf
    m = c['win'] & (c['eps'] > r['eq_to']) & (c['eps'] < lim)
    i = int(np.nanargmax(np.abs(np.where(m, c['R_mod'], np.nan))))
    return {'rmod': c['R_mod'][i], 'eps': c['eps'][i], 'fi': c['Fi'][i] / 1e3, 'fo': c['Fo'][i] / 1e3}


def rmod_before(rc):
    """|R_mod| max entre 5 % et la localisation brutale."""
    r, c = rc
    m = c['win'] & (c['eps'] >= rt.EPS_PLATEAU) & (c['eps'] < r['drop_eps'])
    return np.nanmax(np.abs(c['R_mod'][m]))


def drop_detail(rc):
    """Forces brutes au debut de la chute et 10 us plus tard."""
    r, c = rc
    t = c['t_ms']
    i0 = int(np.argmin(np.abs(t - r['drop_t_ms'])))
    i1 = int(np.argmin(np.abs(t - (r['drop_t_ms'] + 1e-3 * rt.DROP_US))))
    return {'fi0': c['Fi_raw'][i0] / 1e3, 'fi1': c['Fi_raw'][i1] / 1e3,
            'fo0': c['Fo_raw'][i0] / 1e3, 'fo1': c['Fo_raw'][i1] / 1e3}


# ============================================================
def main():
    os.makedirs(os.path.join(OUT, 'img'), exist_ok=True)
    ref = load(REF['UT19']) + load(REF['UT40'])
    ref.sort(key=lambda rc: (rc[0]['specimen'], rc[0]['target_rate']))
    centred = load(CENTRED_UT19)
    first = load(FIRST_UT40)
    groups = groups_of(ref)

    # figures communes avec report_taskI.py (les deux eprouvettes)
    rt.fig_equilibrium(groups, OUT)
    rt.fig_equilibrium_mod(groups, OUT)
    for spec, items in groups:
        rt.fig_forces_full(spec, items, OUT)
        rt.fig_equilibrium_onset(spec, items, OUT)
        rt.fig_forces(spec, items, OUT)
    rt.fig_stress_strain(groups, OUT)
    rt.fig_strain_rate(groups, OUT)
    rt.fig_striker(groups, OUT)
    # figures propres au rapport final
    fig_test_window(groups, OUT)
    fig_compare_specimens(ref, OUT)
    fig_contact_effect(centred, [rc for rc in ref if rc[0]['specimen'] == 'UT19'], OUT)
    fig_first_ut40(first, ref, OUT)
    prb = [(name, probe_errors(st, case)) for st, case, name in PROBE_RUNS]
    fig_probes(prb, OUT)

    # images copiees (journal, sondes, figures de controle)
    for src in JOURNAL_IMG:
        shutil.copy(os.path.join(REPO, src), os.path.join(OUT, 'img', os.path.basename(src)))
    for st, case in ((REF['UT19'], 'UT19_R1000_00'), (REF['UT40'], 'UT40_R1000_00')):
        shutil.copy(os.path.join(RESULTS, st, case, case + '_probes.png'), os.path.join(OUT, 'img'))
    for r, _ in ref:
        shutil.copy(os.path.join(RESULTS, r['study'], r['case_id'], r['case_id'] + '_overview.png'),
                    os.path.join(OUT, 'img'))

    # tableau de tous les indicateurs
    allrows = [r for r, _ in ref + centred + first]
    df = pd.DataFrame([{label_: r[k] for k, label_ in rt.CSV_COLS} for r in allrows])
    df.insert(0, 'case_id', [r['case_id'] for r in allrows])
    df.insert(0, 'study', [r['study'] for r in allrows])
    for k in ('eps_eq_mod', 'Rmod_max_after5', 'Rmod_max_all', 'drop_eps', 'fastest_drop_kN', 'gauge_err_before_drop',
              'increments', 'wall_min'):
        df[k] = [r[k] for r in allrows]
    df.to_csv(os.path.join(OUT, 'T_all_runs.csv'), index=False, float_format='%.4g')

    text = write(ref, centred, first, prb, OUT)
    with open(os.path.join(OUT, 'report.md'), 'w', encoding='utf-8') as f:
        f.write(text.rstrip() + '\n')
    print('Rapport final : %s (%d lignes)' % (os.path.join(OUT, 'report.md'), text.count('\n')))


if __name__ == '__main__':
    main()
