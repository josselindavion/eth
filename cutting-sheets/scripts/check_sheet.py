# -*- coding: utf-8 -*-
"""
check_sheet.py -- Verifie un plan de decoupe EDM (DXF) avant envoi a l'atelier.

Lancement (Python 3 + ezdxf, shapely, matplotlib), depuis la racine du repo :
    py cutting-sheets/scripts/check_sheet.py cutting-sheets/input/<plan>.dxf [--min-gap 3] [--warn-gap 5] [--min-margin 5]

Sorties dans cutting-sheets/reports/<plan>/ :
    report.md      rapport (anglais) : verdict, controles, inventaire des eprouvettes, details des problemes
    preview.png    plan complet, problemes entoures
    issues.png     zooms sur chaque probleme bloquant
    pieces.csv     une ligne par eprouvette (tole, type, orientation / laminage, position, code)

Controles (ERROR = bloquant, WARNING = a verifier, INFO) : voir CHECKS ci-dessous et README.md.
Ecart minimal entre pieces : 5 mm (regle donnee par les encadrants le 29/10/2026). Marge au bord : 5 mm,
valeur provisoire (non precisee). Pas de Mikrosteg dans le DXF (ils restent sur la notice).
"""
import argparse
import collections
import csv
import math
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt          # noqa: E402
from shapely.geometry import Point, Polygon      # noqa: E402
from shapely.ops import nearest_points           # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheetlib as sl                    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.abspath(os.path.join(HERE, '..', 'reports'))
ACI_RGB = {3: '#16a34a', 4: '#06b6d4', 5: '#2546d6', 7: '#333333'}
QUALITY_LAYERS = {'3': 3, '4': 4, '5': 5, 'NORMAL_QUALITY': 3, 'MEDIUM_QUALITY': 4, 'HIGH_QUALITY': 5}


def analyse(path, min_gap, warn_gap, min_margin):
    d = sl.Drawing(path)
    frs = sl.frames(d)
    pcs = sl.pieces(d)
    sl.assign_sheets(pcs, frs)
    cut = d.cut
    R = {'drawing': d, 'frames': frs, 'pieces': pcs, 'checks': [], 'issues': []}

    def check(name, status, detail):
        R['checks'].append((name, status, detail))

    # 1. unites
    check('Units', 'OK' if d.units == 4 else ('WARNING' if d.units == 0 else 'ERROR'),
          '$INSUNITS = %d (%s)%s' % (d.units, sl.unit_name(d.units),
                                     '' if d.units == 4 else '; the lab drawings use millimetres (4): set it so that the '
                                                             'workshop software does not guess'))
    # 2. toles
    check('Sheets', 'OK' if frs else 'ERROR', '%d sheet frame(s): %s' % (len(frs), ', '.join(
        '%.0f × %.0f mm' % (f.bounds[2] - f.bounds[0], f.bounds[3] - f.bounds[1]) for f in frs)) if frs else
          'no closed rectangle of colour 7 found')
    # 3. contours fermes
    pairs, lone = sl.pair_open_ends(sl.open_ends(cut))
    comp_of = {}
    for comp in sl.components(cut):
        for s in comp:
            for q in s.ends():
                comp_of[q] = comp
    n_stray = 0
    for a, b, dist in list(pairs):
        comp = comp_of.get(a)
        if comp is not None and comp is comp_of.get(b) and sum(s.length for s in comp) < 5.0 and \
                all(q in (a, b) or sum(1 for s2 in comp for e in s2.ends() if e == q) % 2 == 0 for s in comp for q in s.ends()):
            pairs.remove((a, b, dist))
            n_stray += 1
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            sheet = next((i + 1 for i, f in enumerate(frs) if f.contains(Point(mid))), 0)
            R['issues'].append(('ERROR', 'stray fragment', mid, 'isolated %s, %.2f mm long, connected to nothing '
                                '(to delete, or a piece of contour placed at the wrong spot)'
                                % (', '.join('%s %s%s' % (s.kind, sl.QUALITY.get(s.color, s.color), ' R%.2f' % s.radius
                                                          if s.radius else '') for s in comp), sum(s.length for s in comp)), sheet))
    for a, b, dist in pairs:
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        near = [s for s in cut if s.line.distance(Point(mid)) < dist + 0.5]
        sheet = next((i + 1 for i, f in enumerate(frs) if f.contains(Point(mid))), 0)
        R['issues'].append(('ERROR', 'open contour', mid, 'gap of %.2f mm between (%.3f, %.3f) and (%.3f, %.3f); '
                            'neighbouring lines: %s' % (dist, a[0], a[1], b[0], b[1],
                                                        ', '.join(sorted(set('%s %s' % (s.kind, sl.QUALITY.get(s.color, s.color))
                                                                             for s in near)))), sheet))
    for a in lone:
        R['issues'].append(('ERROR', 'open contour', a, 'dangling end at (%.3f, %.3f)' % a, 0))
    n_open = len(pairs) + len(lone)
    check('Closed contours', 'OK' if not n_open and not n_stray else 'ERROR',
          'all cutting contours are closed' if not n_open and not n_stray else
          '%d open contour(s) (the wire cannot follow them; the specimens concerned are not counted below) and %d '
          'stray fragment(s) connected to nothing' % (n_open, n_stray))
    # 4. doublons
    dup = sl.duplicates(cut)
    for s, first in dup:
        m = s.line.interpolate(0.5, normalized=True)
        R['issues'].append(('WARNING', 'duplicate line', (m.x, m.y), '%s drawn twice' % s.kind, 0))
    check('Duplicate lines', 'OK' if not dup else 'WARNING',
          'none' if not dup else '%d line(s) drawn twice (the wire may cut twice)' % len(dup))
    # 5. couleurs
    bad = [s for s in cut if s.color not in sl.CUT_COLORS]
    mism = [s for s in cut if QUALITY_LAYERS.get(s.layer.upper()) not in (None, s.color)]
    check('Colours = EDM quality', 'OK' if not bad else 'ERROR',
          'cutting lines use only colours 3 / 4 / 5 (Q3 / Q4 / Q5): %s' % dict(sorted(collections.Counter(s.color for s in cut).items()))
          if not bad else '%d line(s) with a colour outside 3 / 4 / 5: %s' % (len(bad), dict(collections.Counter(s.color for s in bad))))
    if mism:
        check('Layer name vs colour', 'WARNING', '%d line(s) on a quality layer with another colour (%s); the colour is '
              'what counts' % (len(mism), dict(collections.Counter((s.layer, s.color) for s in mism))))
    # 6. pieces hors tole / a cheval
    for p in pcs:
        f = frs[p.sheet - 1] if p.sheet else None
        if f is None:
            R['issues'].append(('ERROR', 'outside sheet', p.center, 'piece %d (%s) outside every sheet' % (p.k, p.kind), 0))
        elif not f.contains(p.poly):
            R['issues'].append(('ERROR', 'crosses sheet edge', p.center, 'piece %d (%s)' % (p.k, p.kind), p.sheet))
    # 7-8. chevauchements, ecarts, marges
    gaps, overl = [], []
    for i in range(len(pcs)):
        for j in range(i + 1, len(pcs)):
            a, b = pcs[i].poly, pcs[j].poly
            dist = a.distance(b)
            if dist > warn_gap:
                gaps.append((dist, pcs[i], pcs[j], None, None))
                continue
            if a.intersects(b) and a.intersection(b).area > 1e-6:
                overl.append((pcs[i], pcs[j]))
                c = a.intersection(b).centroid
                R['issues'].append(('ERROR', 'overlap', (c.x, c.y), 'pieces %d and %d overlap (%.2f mm²)'
                                    % (pcs[i].k, pcs[j].k, a.intersection(b).area), pcs[i].sheet))
            else:
                dd = a.exterior.distance(b.exterior)
                pa, pb = nearest_points(a.exterior, b.exterior)
                gaps.append((dd, pcs[i], pcs[j], (pa.x, pa.y), (pb.x, pb.y)))
                if dd < warn_gap - 1e-3:
                    R['issues'].append(('ERROR' if dd < min_gap - 1e-3 else 'WARNING', 'small gap', ((pa.x + pb.x) / 2, (pa.y + pb.y) / 2),
                                        '%.2f mm between pieces %d (%s) and %d (%s)' % (dd, pcs[i].k, pcs[i].kind, pcs[j].k, pcs[j].kind),
                                        pcs[i].sheet))
    n_err_gap = sum(1 for g in gaps if g[0] < min_gap - 1e-3)
    n_warn_gap = sum(1 for g in gaps if min_gap - 1e-3 <= g[0] < warn_gap - 1e-3)
    check('Overlaps', 'OK' if not overl else 'ERROR', 'none' if not overl else '%d pair(s)' % len(overl))
    check('Gap between pieces', 'ERROR' if n_err_gap else ('WARNING' if n_warn_gap else 'OK'),
          'smallest gap %.2f mm; %d pair(s) below %.1f mm, %d more below %.1f mm'
          % (min(g[0] for g in gaps) if gaps else float('nan'), n_err_gap, min_gap, n_warn_gap, warn_gap))
    margins = []
    for p in pcs:
        if p.sheet:
            m = frs[p.sheet - 1].exterior.distance(p.poly)
            margins.append(m)
            if m < min_margin - 1e-3:
                q1, q2 = nearest_points(frs[p.sheet - 1].exterior, p.poly.exterior)
                R['issues'].append(('ERROR', 'small margin', (q2.x, q2.y), '%.2f mm between piece %d (%s) and the sheet edge'
                                    % (m, p.k, p.kind), p.sheet))
    check('Margin to sheet edge', 'OK' if not margins or min(margins) >= min_margin - 1e-3 else 'ERROR',
          'smallest margin %.1f mm (limit %.1f mm)' % (min(margins), min_margin) if margins else 'no piece on a sheet')
    # 9. codes
    need = [p for p in pcs if not p.kind.startswith('STRIP')]
    nocode = [p for p in need if not p.code]
    sigs = collections.defaultdict(list)
    for p in pcs:
        if p.code:
            sigs[sl.code_signature(p)].append(p)
    # meme code sur deux eprouvettes du MEME type : impossibles a distinguer apres decoupe (WARNING) ;
    # meme code sur des types differents : elles se distinguent par leur forme (INFO, convention des plans 2025)
    same_type, other_type = [], []
    for v in sigs.values():
        if len(v) < 2:
            continue
        byk = collections.defaultdict(list)
        for p in v:
            byk[p.kind].append(p)
        clash = [g for g in byk.values() if len(g) > 1]
        (same_type if clash else other_type).append(v)
    for p in nocode:
        R['issues'].append(('WARNING', 'no ID code', p.center, 'piece %d (%s) has no notch code' % (p.k, p.kind), p.sheet))
    for v in same_type:
        R['issues'].append(('WARNING', 'same ID code, same type', v[0].center, 'pieces %s share the same notch code'
                            % ', '.join('%d (%s, %.0f°)' % (p.k, p.kind, sl.fold_rd(p.axis_deg)) for p in v), v[0].sheet))
    check('ID codes', 'OK' if not nocode and not same_type else 'WARNING',
          '%d of %d specimens carry a notch code; %d distinct codes%s%s' % (
              len(need) - len(nocode), len(need), len(sigs),
              '' if not same_type else '; %d code(s) shared by specimens of the same type (indistinguishable)' % len(same_type),
              '' if not other_type else '; %d code(s) shared only by specimens of different types (distinguishable by '
                                        'their shape)' % len(other_type)))
    if d.skipped:
        check('Unreadable entities', 'INFO', 'ignored: %s (zero length)' % dict(d.skipped))
    R['gaps'] = gaps
    R['margins'] = margins
    return R


# ============================================================
# FIGURES
# ============================================================
def draw_base(ax, R, lw=0.5):
    d = R['drawing']
    for s in d.segs:
        xs, ys = zip(*s.pts)
        ax.plot(xs, ys, color=ACI_RGB.get(s.color, '#d03b3b'), lw=lw if s.color != 7 else 0.8)
    ax.set_aspect('equal')


def fig_preview(R, out):
    frs = R['frames']
    d = R['drawing']
    xs = [x for s in d.segs for x, _ in s.pts]
    ys = [y for s in d.segs for _, y in s.pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    fig, ax = plt.subplots(figsize=(min(16, 4 + 10 * w / max(h, 1)), 10))
    draw_base(ax, R)
    for p in R['pieces']:
        x, y = p.center
        ax.text(x, y, str(p.k), fontsize=5, ha='center', va='center', color='#555555')
    for sev, kind, (x, y), txt, sheet in R['issues']:
        col = '#d03b3b' if sev == 'ERROR' else '#f59e0b'
        ax.add_patch(plt.Circle((x, y), 6, fill=False, color=col, lw=1.6))
    for i, f in enumerate(frs):
        ax.text(f.bounds[0] + 4, f.bounds[3] - 4, 'sheet %d' % (i + 1), fontsize=9, va='top')
    ax.set_title('%s  –  red: blocking problem, orange: to check; small numbers: piece index'
                 % os.path.basename(d.path), fontsize=9, loc='left')
    ax.axis('off')
    fig.tight_layout()
    fig.savefig(out, dpi=170)
    plt.close(fig)


def fig_issues(R, out, maxn=12):
    errs = [i for i in R['issues'] if i[0] == 'ERROR'][:maxn]
    if not errs:
        return False
    n = len(errs)
    cols = min(4, n)
    rows = int(math.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(3.6 * cols, 3.6 * rows), squeeze=False)
    for ax in axs.flat:
        ax.axis('off')
    for ax, (sev, kind, (x, y), txt, sheet) in zip(axs.flat, errs):
        ax.axis('on')
        draw_base(ax, R, lw=1.2)
        r = 8 if kind != 'small margin' else 12
        ax.set_xlim(x - r, x + r)
        ax.set_ylim(y - r, y + r)
        ax.add_patch(plt.Circle((x, y), 1.5 if kind == 'open contour' else 2.5, fill=False, color='#d03b3b', lw=1.2))
        ax.set_title('%s – sheet %s\n(%.1f, %.1f)' % (kind, sheet or '?', x, y), fontsize=8)
        ax.tick_params(labelsize=6)
        ax.grid(True, lw=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return True


# ============================================================
# RAPPORT
# ============================================================
def write_outputs(R, outdir, args):
    os.makedirs(outdir, exist_ok=True)
    d, pcs, frs = R['drawing'], R['pieces'], R['frames']
    fig_preview(R, os.path.join(outdir, 'preview.png'))
    has_zoom = fig_issues(R, os.path.join(outdir, 'issues.png'))
    with open(os.path.join(outdir, 'pieces.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['piece', 'sheet', 'type', 'angle_to_RD_deg', 'orientation_to_RD_deg', 'x_mm', 'y_mm', 'L_mm', 'W_mm',
                    'holes', 'code_signature'])
        for p in pcs:
            w.writerow([p.k, p.sheet, p.kind, round(p.axis_deg, 2), round(sl.fold_rd(p.axis_deg), 1), round(p.center[0], 2),
                        round(p.center[1], 2), round(p.L, 2), round(p.W, 2), len(p.poly.interiors),
                        '%08x' % sl.code_signature(p) if p.code else ''])
    nerr = sum(1 for c in R['checks'] if c[1] == 'ERROR')
    nwarn = sum(1 for c in R['checks'] if c[1] == 'WARNING')
    L = []
    P = lambda *a: L.extend([''.join(a), ''])      # noqa: E731
    P('# Cutting sheet check – `%s`' % os.path.basename(d.path))
    P('*Generated by `cutting-sheets/scripts/check_sheet.py`. Limits: gap between pieces ≥ %.1f mm (warning below '
      '%.1f mm), margin to the sheet edge ≥ %.1f mm (gap: rule of the supervisors; margin: provisional).*'
      % (args.min_gap, args.warn_gap, args.min_margin))
    P('**Verdict: %s** – %d blocking problem(s) in %d check(s), %d check(s) with warnings.'
      % ('NOT READY for the workshop' if nerr else ('ready, with points to check' if nwarn else 'ready'),
         sum(1 for i in R['issues'] if i[0] == 'ERROR'), nerr, nwarn))
    P('## Checks')
    P('| Check | Status | Detail |\n|---|---|---|\n' + '\n'.join('| %s | %s | %s |' % c for c in R['checks']))
    P('## Specimens found')
    inv = collections.Counter((p.kind, int(round(sl.fold_rd(p.axis_deg) / 15.0)) * 15 if not p.kind.startswith('DISC') else None)
                              for p in pcs)
    kinds = sorted(set(k for k, _ in inv))
    rows = []
    for k in kinds:
        angs = sorted((a, n) for (kk, a), n in inv.items() if kk == k)
        tot = sum(n for _, n in angs)
        rows.append('| %s | %s | %d |' % (k, ', '.join(('%d° × %d' % (a, n)) if a is not None else '× %d' % n for a, n in angs), tot))
    P('| Type (provisional name) | Orientation to rolling direction × number | Total |\n|---|---|---|\n' + '\n'.join(rows))
    P('*Type names are derived from the geometry: UT = uniaxial tension, NT_R = notched tension with notch radius R, '
      'CH_D = central hole of diameter D, DISC_nH = disc with n holes (2H_xx: axis of the holes at xx° to the rolling '
      'direction), STRIP / BLANK = rectangle without a gauge section (BLANK: with a notch code); L = length in mm. '
      'Orientation: angle between the specimen axis and the rolling direction (drawing +Y), folded into 0–90° (orthotropic '
      'sheet). Per-piece list: `pieces.csv`.*')
    P('| Sheet | Size | Pieces | Area used | Smallest margin |\n|---|---|---|---|---|\n' + '\n'.join(
        '| %d | %.0f × %.0f mm | %d | %.0f %% | %s |' % (
            i + 1, f.bounds[2] - f.bounds[0], f.bounds[3] - f.bounds[1], sum(1 for p in pcs if p.sheet == i + 1),
            100 * sum(p.poly.area for p in pcs if p.sheet == i + 1) / f.area,
            '%.1f mm' % min([f.exterior.distance(p.poly) for p in pcs if p.sheet == i + 1] or [float('nan')]))
        for i, f in enumerate(frs)))
    P('![Preview](preview.png)')
    P('> **Figure 1 – The cutting sheet and its problems.**\n>\n> *Plotted* – every line of the DXF in its EDM quality '
      'colour (green Q3, cyan Q4, blue Q5), sheet frames in black, piece index in small grey numbers; red circles: '
      'blocking problems; orange circles: points to check.\n>\n> *Source* – `%s`.\n>\n> *How to read it* – each circle '
      'is listed in the table below with its coordinates (drawing millimetres).' % os.path.basename(d.path))
    if has_zoom:
        P('![Blocking problems](issues.png)')
        P('> **Figure 2 – Zoom on each blocking problem.**\n>\n> *Plotted* – a 16 mm window around each problem '
          '(24 mm for margins), same colours as Figure 1, red circle at the problem.\n>\n> *Source* – same drawing.'
          '\n>\n> *How to read it* – an open contour shows as two line ends that do not meet.')
    P('## Problems')
    if R['issues']:
        order = {'ERROR': 0, 'WARNING': 1}
        P('| # | Severity | Problem | Sheet | Position (mm) | Detail |\n|---|---|---|---|---|---|\n' + '\n'.join(
            '| %d | %s | %s | %s | (%.1f, %.1f) | %s |' % (n + 1, s, k, sh or '–', x, y, t)
            for n, (s, k, (x, y), t, sh) in enumerate(sorted(R['issues'], key=lambda i: (order.get(i[0], 2), i[1], i[4], i[2])))))
    else:
        P('None.')
    with open(os.path.join(outdir, 'report.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L).rstrip() + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('dxf')
    ap.add_argument('--min-gap', type=float, default=5.0, help='ecart minimal entre pieces (mm), sinon ERROR (encadrants, 29/10/2026 : 5 mm)')
    ap.add_argument('--warn-gap', type=float, default=5.0, help='ecart en dessous duquel on signale (mm)')
    ap.add_argument('--min-margin', type=float, default=5.0, help='marge minimale au bord de la tole (mm ; valeur provisoire, non precisee par les encadrants)')
    ap.add_argument('--out', default=None, help='dossier de sortie (defaut : cutting-sheets/reports/<plan>/)')
    args = ap.parse_args()
    R = analyse(args.dxf, args.min_gap, args.warn_gap, args.min_margin)
    out = args.out or os.path.join(REPORTS, os.path.splitext(os.path.basename(args.dxf))[0])
    write_outputs(R, out, args)
    for c in R['checks']:
        print('%-24s %-8s %s' % c)
    print('Rapport : %s' % os.path.join(out, 'report.md'))


if __name__ == '__main__':
    main()
