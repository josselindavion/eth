# -*- coding: utf-8 -*-
"""
check_sheet.py -- Checks an EDM cutting plan (DXF) before it is sent to the workshop.

Run (Python 3 + ezdxf, shapely, matplotlib), from the repository root:
    py cutting-sheets/scripts/check_sheet.py <plan>.dxf [--min-gap 5] [--warn-gap 5]
        [--min-margin 5 | --margins LEFT BOTTOM RIGHT TOP]

Outputs in cutting-sheets/runs/reports/<plan>/ (ignored by git), or reports/<plan>/ with --final:
    report.md      report: verdict, checks, inventory of the specimens, details of the problems
    preview.png    full plan, machine margins hatched in red, problems circled
    issues.png     zoom on each blocking problem
    pieces.csv     one line per specimen (sheet, type, orientation to the rolling direction, position, code)

Checks (ERROR = blocking, WARNING = to check, INFO): see analyse() below and README.md.
Minimum gap between pieces: 5 mm (rule given by the supervisors on 29/10/2026). Margins to the sheet edge: per side
(clamping area). Mikrostegs: half-circle recesses in the outline (mikrosteg.py), no gap in the cutting lines.
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
from matplotlib.patches import FancyArrow        # noqa: E402
from shapely.geometry import Point, Polygon      # noqa: E402
from shapely.ops import nearest_points           # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheetlib as sl                    # noqa: E402
from shapely import affinity             # noqa: E402
import zones                             # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.abspath(os.path.join(HERE, '..', 'reports'))              # --final: tracked by git
RUNS_REPORTS = os.path.abspath(os.path.join(HERE, '..', 'runs', 'reports'))  # default: ignored by git
ACI_RGB = {3: '#16a34a', 4: '#06b6d4', 5: '#2546d6', 7: '#333333'}
QUALITY_LAYERS = {'3': 3, '4': 4, '5': 5, 'NORMAL_QUALITY': 3, 'MEDIUM_QUALITY': 4, 'HIGH_QUALITY': 5}


SIDES = (('left', 'gauche'), ('bottom', 'bas'), ('right', 'droite'), ('top', 'haut'))


def side_margins(min_margin):
    """Margins per side {'left', 'bottom', 'right', 'top'} (mm) from a number or a dict (English keys, or the French
    keys gauche / bas / droite / haut of the first version)."""
    if isinstance(min_margin, dict):
        return {en: float(min_margin.get(en, min_margin.get(fr, 0.0))) for en, fr in SIDES}
    return {en: float(min_margin) for en, _ in SIDES}


def fmt_margins(min_margin):
    m = side_margins(min_margin)
    if len(set(m.values())) == 1:
        return '%g mm' % m['left']
    return ', '.join('%s %g' % (en, m[en]) for en, _ in SIDES) + ' mm'


def piece_side_margins(frame, poly):
    """Distance of the piece to each edge of the rectangular sheet frame."""
    fb, pb = frame.bounds, poly.bounds
    return {'left': pb[0] - fb[0], 'bottom': pb[1] - fb[1], 'right': fb[2] - pb[2], 'top': fb[3] - pb[3]}


def analyse(path, min_gap, warn_gap, min_margin, keepouts=None, forbidden=None):
    d = sl.Drawing(path)
    frs = sl.frames(d)
    pcs = sl.pieces(d)
    sl.assign_sheets(pcs, frs)
    cut = d.cut
    R = {'drawing': d, 'frames': frs, 'pieces': pcs, 'checks': [], 'issues': [], 'margin_limits': side_margins(min_margin)}

    def check(name, status, detail):
        R['checks'].append((name, status, detail))

    # 1. units
    check('Units', 'OK' if d.units == 4 else ('WARNING' if d.units == 0 else 'ERROR'),
          '$INSUNITS = %d (%s)%s' % (d.units, sl.unit_name(d.units),
                                     '' if d.units == 4 else '; the lab drawings use millimetres (4): set it so that the '
                                                             'workshop software does not guess'))
    # 2. sheets
    check('Sheets', 'OK' if frs else 'ERROR', '%d sheet frame(s): %s' % (len(frs), ', '.join(
        '%.0f × %.0f mm' % (f.bounds[2] - f.bounds[0], f.bounds[3] - f.bounds[1]) for f in frs)) if frs else
          'no closed rectangle of colour 7 found')
    # 3. closed contours
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
    # 4. duplicates
    dup = sl.duplicates(cut)
    for s, first in dup:
        m = s.line.interpolate(0.5, normalized=True)
        R['issues'].append(('WARNING', 'duplicate line', (m.x, m.y), '%s drawn twice' % s.kind, 0))
    check('Duplicate lines', 'OK' if not dup else 'WARNING',
          'none' if not dup else '%d line(s) drawn twice (the wire may cut twice)' % len(dup))
    # 5. colours
    bad = [s for s in cut if s.color not in sl.CUT_COLORS]
    mism = [s for s in cut if QUALITY_LAYERS.get(s.layer.upper()) not in (None, s.color)]
    check('Colours = EDM quality', 'OK' if not bad else 'ERROR',
          'cutting lines use only colours 3 / 4 / 5 (Q3 / Q4 / Q5): %s' % dict(sorted(collections.Counter(s.color for s in cut).items()))
          if not bad else '%d line(s) with a colour outside 3 / 4 / 5: %s' % (len(bad), dict(collections.Counter(s.color for s in bad))))
    if mism:
        check('Layer name vs colour', 'WARNING', '%d line(s) on a quality layer with another colour (%s); the colour is '
              'what counts' % (len(mism), dict(collections.Counter((s.layer, s.color) for s in mism))))
    # 6. pieces outside a sheet / across its edge
    for p in pcs:
        f = frs[p.sheet - 1] if p.sheet else None
        if f is None:
            R['issues'].append(('ERROR', 'outside sheet', p.center, 'piece %d (%s) outside every sheet' % (p.k, p.kind), 0))
        elif not f.contains(p.poly):
            R['issues'].append(('ERROR', 'crosses sheet edge', p.center, 'piece %d (%s)' % (p.k, p.kind), p.sheet))
    # 7-8. overlaps, gaps, margins
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
    # margins per side (left / bottom / right / top edge of the sheet; bottom = start of the rolling direction)
    lim = side_margins(min_margin)
    margins, smallest, n_bad = [], {en: float('inf') for en, _ in SIDES}, 0
    for p in pcs:
        if p.sheet:
            ms = piece_side_margins(frs[p.sheet - 1], p.poly)
            margins.append(min(ms.values()))
            for en, _ in SIDES:
                smallest[en] = min(smallest[en], ms[en])
            bad = [en for en, _ in SIDES if ms[en] < lim[en] - 1e-3]
            if bad:
                n_bad += 1
                q1, q2 = nearest_points(frs[p.sheet - 1].exterior, p.poly.exterior)
                R['issues'].append(('ERROR', 'small margin', (q2.x, q2.y), 'piece %d (%s) too close to the %s edge: %s'
                                    % (p.k, p.kind, ' / '.join(bad), ', '.join('%.2f mm (limit %g)' % (ms[en], lim[en])
                                                                             for en in bad)), p.sheet))
    check('Margin to sheet edge', 'OK' if not n_bad else 'ERROR',
          ('smallest margin per side: %s (limits: %s)%s' % (
              ', '.join('%s %.1f' % (en, smallest[en]) for en, _ in SIDES), fmt_margins(min_margin),
              '; %d piece(s) too close' % n_bad if n_bad else '')) if margins else 'no piece on a sheet')
    # keep-out zones of the single clamps (sheet coordinates, same on every sheet)
    if keepouts:
        n_ko = 0
        for p in pcs:
            if not p.sheet:
                continue
            x0, y0 = frs[p.sheet - 1].bounds[:2]
            for k in keepouts:
                kk = affinity.translate(k, x0, y0)
                if p.poly.intersection(kk).area > 1e-3:
                    n_ko += 1
                    c = p.poly.intersection(kk).representative_point()
                    R['issues'].append(('ERROR', 'clamp', (c.x, c.y), 'piece %d (%s) in the keep-out zone of a clamp'
                                        % (p.k, p.kind), p.sheet))
                    break
        check('Clamps (keep-out zones)', 'OK' if not n_ko else 'ERROR',
              '%d clamp zone(s) per sheet; %d piece(s) inside' % (len(keepouts), n_ko))
    # optional: forbidden zone of a partly used sheet (with its margin), same on every sheet
    if forbidden:
        n_fz = 0
        for p in pcs:
            if not p.sheet:
                continue
            x0, y0 = frs[p.sheet - 1].bounds[:2]
            for k in forbidden:
                kk = affinity.translate(k, x0, y0)
                if p.poly.intersection(kk).area > 1e-3:
                    n_fz += 1
                    c = p.poly.intersection(kk).representative_point()
                    R['issues'].append(('ERROR', 'forbidden', (c.x, c.y), 'piece %d (%s) in the forbidden zone '
                                        '(or its margin)' % (p.k, p.kind), p.sheet))
                    break
        check('Forbidden zone', 'OK' if not n_fz else 'ERROR',
              '%d zone(s) per sheet (with margin); %d piece(s) inside' % (len(forbidden), n_fz))
    # 9. codes
    need = [p for p in pcs if not p.kind.startswith('STRIP')]
    nocode = [p for p in need if not p.code]
    sigs = collections.defaultdict(list)
    for p in pcs:
        if p.code:
            sigs[sl.code_signature(p)].append(p)
    # same code on two specimens of the SAME type: impossible to tell apart after cutting (WARNING);
    # same code on different types: told apart by their shape (INFO, convention of the 2025 drawings)
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
    fw = min(16.0, 4 + 10 * w / max(h, 1))                  # width (inches), then height to the drawing's scale
    fig, ax = plt.subplots(figsize=(fw, min(10.0, max(3.0, fw * h / max(w, 1) + 0.8))))
    # machine margins (clamping area + margins): red hatching, nothing may be cut there
    m = R.get('margin_limits')
    z = R.get('zones')
    if z:                                                   # machine description given (zones.py)
        for f in frs:
            zones.draw(ax, z, f.bounds[0], f.bounds[1])
    elif m:
        for f in frs:
            x0, y0, x1, y1 = f.bounds
            bands = [(x0, y0, x1 - x0, m['bottom']), (x0, y1 - m['top'], x1 - x0, m['top']),
                     (x0, y0 + m['bottom'], m['left'], y1 - y0 - m['bottom'] - m['top']),
                     (x1 - m['right'], y0 + m['bottom'], m['right'], y1 - y0 - m['bottom'] - m['top'])]
            for bx, by, bw, bh in bands:
                if bw > 0 and bh > 0:
                    ax.add_patch(plt.Rectangle((bx, by), bw, bh, fill=False, hatch='////', ec='#dc2626', lw=0,
                                               alpha=0.55, zorder=0))
    draw_base(ax, R)
    for p in R['pieces']:
        x, y = p.center
        ax.text(x, y, str(p.k), fontsize=5, ha='center', va='center', color='#555555')
    for sev, kind, (x, y), txt, sheet in R['issues']:
        col = '#d03b3b' if sev == 'ERROR' else '#f59e0b'
        ax.add_patch(plt.Circle((x, y), 6, fill=False, color=col, lw=1.6))
    for i, f in enumerate(frs):
        ax.text(f.bounds[0] + 4, f.bounds[3] - 4, 'sheet %d' % (i + 1), fontsize=9, va='top')
        # rolling direction (+Y) next to the left edge of each sheet; sizes are written RD x TD
        fx0, fy0, fx1, fy1 = f.bounds
        L = min(80.0, 0.3 * (fy1 - fy0))
        ax.add_patch(FancyArrow(fx0 - 12, fy0, 0, L, width=2.0, head_width=7.0, head_length=8.0, color='#3b6fb6',
                                length_includes_head=True))
        ax.text(fx0 - 18, fy0 + L / 2, 'RD', rotation=90, ha='right', va='center', fontsize=8, color='#3b6fb6')
        ax.text((fx0 + fx1) / 2, fy0 - 4, '%g (RD) × %g (TD) mm' % (fy1 - fy0, fx1 - fx0), ha='center', va='top',
                fontsize=7, color='#555555')
    if z:
        ax.set_title('%s  –  red circle: blocking problem, orange: to check; small numbers: piece index'
                     % os.path.basename(d.path), fontsize=9, loc='left')
        ax.legend(handles=zones.legend_handles(z), loc='upper left', bbox_to_anchor=(0.0, 0.0), ncol=3, fontsize=8,
                  frameon=False)
    else:
        ax.set_title('%s  –  red hatching: machine margins (%s), no cutting; red circle: blocking problem, '
                     'orange: to check; small numbers: piece index'
                     % (os.path.basename(d.path), fmt_margins({k: v for k, v in m.items()}) if m else '–'),
                     fontsize=9, loc='left')
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
# REPORT
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
      '%.1f mm), margin to the sheet edge ≥ %s (gap: rule of the supervisors).*'
      % (args.min_gap, args.warn_gap, fmt_margins(args.min_margin)))
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
    ap.add_argument('--min-gap', type=float, default=5.0, help='minimum gap between pieces (mm), ERROR below '
                    '(supervisors, 29/10/2026: 5 mm)')
    ap.add_argument('--warn-gap', type=float, default=5.0, help='gap below which a warning is given (mm)')
    ap.add_argument('--min-margin', type=float, default=5.0, help='minimum margin to the sheet edge, same on the 4 sides (mm)')
    ap.add_argument('--margins', type=float, nargs=4, metavar=('LEFT', 'BOTTOM', 'RIGHT', 'TOP'),
                    help='margins per side in mm (replaces --min-margin), e.g. --margins 40 40 5 5')
    ap.add_argument('--out', default=None, help='output folder (default: cutting-sheets/runs/reports/<plan>/)')
    ap.add_argument('--final', action='store_true', help='write to reports/ (tracked by git) instead of runs/reports/')
    args = ap.parse_args()
    if args.margins:
        args.min_margin = dict(zip(('left', 'bottom', 'right', 'top'), args.margins))
    R = analyse(args.dxf, args.min_gap, args.warn_gap, args.min_margin)
    out = args.out or os.path.join(REPORTS if args.final else RUNS_REPORTS, os.path.splitext(os.path.basename(args.dxf))[0])
    write_outputs(R, out, args)
    for c in R['checks']:
        print('%-24s %-8s %s' % c)
    print('Report: %s' % os.path.join(out, 'report.md'))


if __name__ == '__main__':
    main()
