# -*- coding: utf-8 -*-
"""
make_plan.py -- Complete EDM cutting plan from an order file ("5 UT at 30 deg, 3 NT20 at 45 deg...").

Run (Python 3 + ezdxf, shapely, matplotlib, scipy, pyyaml, spyrrow, packingsolver), from the repository root:
    py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/example.yaml

Steps:
    1. read the order (YAML, see cutting-sheets/orders/) and check it: known type, angle multiple of 15 deg and
       codable (0-135 deg), index 0-9, never the same code twice on the same type;
    2. one specimen = template without code (templates/<name>/) + its notch code (notchcode.py);
       angle = direction of the coded end from the rolling direction (+Y), counter-clockwise;
    3. automatic placement (placement.py): PackingSolver assigns the specimens to sheets, sparrow moves specimens to
       empty the least filled sheet, then compacts each sheet; ordered angle or half turn (+180 deg), never
       mirrored, gap and margins;
    4. DXF plan (mm, layers Q3_NORMAL / Q4_MEDIUM / Q5_HIGH);
    5. checks: check_sheet.py (contours, gaps, margins...), then every specimen is READ BACK from the final DXF
       (outline, code, direction) and compared with the order;
    6. specimen registry (registry.csv) and notice for the workshop (notice.pdf: numbered plan, qualities, rolling
       direction).

Outputs in cutting-sheets/runs/<name>/ (IGNORED by git: runs can be repeated without git conflicts), or in
cutting-sheets/output/<name>/ (tracked by git) with --final, for a plan to keep or to send to the workshop:
<name>.dxf (plan for the workshop), notice.pdf, registry.csv and preview.png (plan with the machine margins in red).
Intermediate files (coded specimens, check report) are written to a temporary folder and deleted.
"""
import argparse
import collections
import csv
import datetime
import os
import shutil
import sys
import tempfile
import time

import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyArrow, Rectangle  # noqa: E402
import yaml                                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_sheet                                    # noqa: E402
import make_templates as mt                           # noqa: E402
import notchcode as nc                                # noqa: E402
import placement as sp                                # noqa: E402
from progress import Bar, step, _fmt as progress_fmt  # noqa: E402
import sheetlib as sl                                 # noqa: E402

BASE = os.path.abspath(os.path.join(HERE, '..'))       # cutting-sheets folder
DEFAULT_TEMPLATES = os.path.join(BASE, 'templates', 'CTLG_261102')     # lab catalogue + MNAK_RECT
ACI_RGB = {3: '#16a34a', 4: '#06b6d4', 5: '#2546d6', 7: '#222222'}

SIDES = ('left', 'bottom', 'right', 'top')       # bottom = start of the rolling direction (+Y)

# order-file keys of the first (French) version, still accepted
LEGACY_KEYS = {'nom': 'name', 'gabarits': 'templates', 'tole': 'sheet', 'ecart': 'gap', 'marge': 'margin',
               'marges': 'margins', 'temps': 'time', 'graine': 'seed', 'ajouts': 'fill_tries',
               'temps_ajout': 'fill_time', 'toles_max': 'max_sheets', 'identifiant': 'specimen_id',
               'eprouvettes': 'specimens'}
LEGACY_SIDES = {'gauche': 'left', 'bas': 'bottom', 'droite': 'right', 'haut': 'top'}
LEGACY_LINE = {'nombre': 'count', 'premier_index': 'first_index', 'geometrie_essai': 'test_geometry'}
LEGACY_ID = {'lot': 'batch', 'geometrie_echantillon': 'sample_geometry', 'supplement': 'additional',
             'geometrie_essai': 'test_geometry'}


class OrderError(Exception):
    pass


# ============================================================
# ORDER
# ============================================================
def resolve(path, order_dir):
    for cand in (path, os.path.join(order_dir, path), os.path.join(BASE, path),
                 os.path.join(os.path.dirname(BASE), path)):
        if os.path.exists(cand):
            return os.path.abspath(cand)
    raise OrderError('not found: %s' % path)


def _rename(d, table):
    return {table.get(k, k): v for k, v in d.items()} if isinstance(d, dict) else d


def read_order(path):
    with open(path, encoding='utf-8') as f:
        o = yaml.safe_load(f)
    o = _rename(o, LEGACY_KEYS)
    if not isinstance(o, dict) or 'specimens' not in o:
        raise OrderError('the order must contain a list "specimens"')
    odir = os.path.dirname(os.path.abspath(path))
    cfg = {
        'name': str(o.get('name') or os.path.splitext(os.path.basename(path))[0]),
        'templates': resolve(o['templates'], odir) if o.get('templates') else DEFAULT_TEMPLATES,
        'sheet': str(o.get('sheet', '500x600')),
        'gap': float(o.get('gap', 5.0)),
        'margin': float(o.get('margin', 5.0)),              # same margin on the 4 sides (shortcut)
        'time': float(o.get('time', 15)),                   # sparrow compaction per sheet (s; 0 = no compaction)
        'assign_time': float(o.get('assign_time', 30)),     # PackingSolver assignment (s)
        'seed': int(o.get('seed', 1)),
        'fill_tries': int(o.get('fill_tries', 8)),          # tries to move specimens off the least filled sheet
        'fill_time': float(o.get('fill_time', 10)),         # sparrow, per try to move a specimen (s, at most)
        'max_sheets': int(o.get('max_sheets', 20)),
        'specimen_id': _rename(o.get('specimen_id') or {}, LEGACY_ID),
        'lines': [_rename(line, LEGACY_LINE) for line in o['specimens']],
    }
    try:
        cfg['W'], cfg['H'] = (float(v) for v in cfg['sheet'].lower().split('x'))
    except ValueError:
        raise OrderError('sheet: "%s" is not of the form 500x600' % cfg['sheet'])
    # margins per side: "margins: {left: 40, bottom: 40, right: 5, top: 5}"; a missing side takes "margin"
    mg = _rename(o.get('margins') or {}, LEGACY_SIDES)
    if not isinstance(mg, dict) or set(mg) - set(SIDES):
        raise OrderError('margins: expected a dict with the keys %s, e.g. {left: 40, bottom: 40, right: 5, top: 5}'
                         % ', '.join(SIDES))
    cfg['margins'] = {k: float(mg.get(k, cfg['margin'])) for k in SIDES}
    if cfg['W'] - cfg['margins']['left'] - cfg['margins']['right'] <= 0 or \
            cfg['H'] - cfg['margins']['bottom'] - cfg['margins']['top'] <= 0:
        raise OrderError('margins larger than the sheet %s' % cfg['sheet'])
    return cfg


def fmt_margins(m):
    if len(set(m.values())) == 1:
        return '%g mm' % m['left']
    return ', '.join('%s %g' % (k, m[k]) for k in SIDES) + ' mm'


def expand(cfg, temps):
    """One entry per specimen: template, angle, angle digit, index. Raises OrderError if the order is wrong."""
    specs, used, nxt = [], {}, {}
    errors = []
    for k, line in enumerate(cfg['lines'], 1):
        where = 'line %d (%s)' % (k, line)
        if not isinstance(line, dict) or 'type' not in line or 'angle' not in line:
            errors.append('%s: "type" and "angle" are required' % where)
            continue
        T = temps.get(str(line['type']).upper()) or temps.get(str(line['type']))
        if T is None:
            errors.append('%s: unknown type; available types: %s'
                          % (where, ', '.join(sorted(set(t.alias for t in temps.values())))))
            continue
        ang = float(line['angle'])
        n = int(line.get('count', 1))
        if not 0 <= ang < 180:
            errors.append('%s: angle outside [0, 180[ deg' % where)
            continue
        a_digit = nc.angle_digit(ang)
        if T.has_code and a_digit is None:
            errors.append('%s: angle %g deg cannot be coded (codable: 0, 15, ..., 135 deg)' % (where, ang))
            continue
        key = (T.kind, ang)
        idx = int(line['first_index']) if 'first_index' in line else nxt.get(key, 0)     # 0-9, as in the catalogue
        for j in range(n):
            i = idx + j
            if T.has_code and not 0 <= i <= 9:
                errors.append('%s: index %d impossible (one digit, 0-9); at most 10 specimens per type and angle'
                              % (where, i))
                break
            if (T.kind, ang, i) in used:
                errors.append('%s: %s at %g deg index %d already ordered (%s): two specimens would have the same code'
                              % (where, T.alias, ang, i, used[(T.kind, ang, i)]))
                continue
            used[(T.kind, ang, i)] = 'line %d' % k
            specs.append({'T': T, 'angle': ang, 'rot': (ang + T.angle_offset) % 360.0,   # rot = placement angle
                          'a_digit': a_digit, 'index': i, 'line': k,
                          'test_geometry': str(line.get('test_geometry', '') or ''),
                          'block': '%s__%03ddeg__%s%d' % (T.kind, round(ang), 'i' if T.has_code else 'n', i)})
        nxt[key] = idx + n
    if errors:
        raise OrderError('\n'.join(errors))
    return specs


# ============================================================
# SPECIMENS -> BLOCKS
# ============================================================
def build_specimens(specs, path):
    doc = ezdxf.new('R2000', setup=True)
    doc.header['$INSUNITS'] = 4
    for c, ln in mt.LAYERS.items():
        doc.layers.add(ln, color=c)
    for s in specs:
        T = s['T']
        blk = doc.blocks.new(s['block'])
        for e, c in T.ents:
            x = e.copy()
            x.dxf.layer, x.dxf.color = mt.LAYERS.get(c, '0'), c
            blk.add_foreign_entity(x, copy=False)
        if T.has_code:
            for a, b, c in T.code_prims(s['a_digit'], s['index']):
                blk.add_line(a, b, dxfattribs={'layer': mt.LAYERS[c], 'color': c})
    doc.saveas(path)
    return doc


# ============================================================
# CHECK OF THE SPECIMENS IN THE FINAL DXF
# ============================================================
def code_check(R, rows, specs_by_block, on_progress=None):
    """Every specimen of the final DXF, read back without assumptions: its outline must be the template's (with its
    code) turned by the placement angle, its code must be the one ordered, and the code direction the placement angle."""
    from shapely import affinity
    from shapely.geometry import Point
    bad, cache = [], {}
    for r in rows:
        s = specs_by_block[r['block']]
        T = s['T']
        pt = Point(r['insert_x_mm'], r['insert_y_mm'])
        p = min(R['pieces'], key=lambda q: Point(q.center).distance(pt))
        msg = []
        key = (T.kind, s['a_digit'], s['index'])
        if key not in cache:
            cache[key] = mt.template_polygon(T, s['a_digit'], s['index']) if T.has_code else mt.template_polygon(T)
        want = affinity.translate(affinity.rotate(cache[key], r['rotation_deg'], origin=(0, 0)),
                                  r['insert_x_mm'], r['insert_y_mm'])
        if len(want.interiors) != len(p.poly.interiors):
            msg.append('%d hole(s) instead of %d' % (len(p.poly.interiors), len(want.interiors)))
        else:
            rings = lambda g: [g.exterior] + list(g.interiors)                    # noqa: E731
            dev = max(min(a.hausdorff_distance(b) for b in rings(p.poly)) for a in rings(want))
            if dev > 0.02:
                msg.append('outline differs from the template (%.3f mm)' % dev)
        if T.has_code:
            try:
                c = nc.read_piece(p)
            except ValueError as e:
                c = None
                msg.append('unreadable code (%s)' % e)
            if c is None and not msg:
                msg.append('no code')
            elif c:
                if (c['angle_digit'], c['index']) != (s['a_digit'], s['index']):
                    msg.append('code read: angle %g / index %d' % (c['angle_deg'], c['index']))
                d = (c['direction_deg'] - s['rot']) % 180.0
                if min(d, 180.0 - d) > 0.5:
                    msg.append('direction %.1f deg' % c['direction_deg'])
                r['code_read'] = '%d%d' % (c['angle_digit'], c['index'])
        r['piece'] = p
        if msg:
            bad.append('%s: %s' % (r['block'], ', '.join(msg)))
        if on_progress:
            on_progress(rows.index(r) + 1)
    return bad


# ============================================================
# REGISTRY
# ============================================================
def registry(rows, specs_by_block, cfg):
    ident = dict(cfg['specimen_id'] or {})
    per_type = ident.get('test_geometry') if isinstance(ident.get('test_geometry'), dict) else {}
    ident = {k: ('' if v is None else str(v)) for k, v in ident.items() if k != 'test_geometry'}
    out = []
    order = sorted(rows, key=lambda r: (r['sheet'], -round(r['y_sheet'] / 25.0), r['x_sheet']))
    for n, r in enumerate(order, 1):
        s = specs_by_block[r['block']]
        T = s['T']
        code = '%d%d' % (s['a_digit'], s['index']) if T.has_code else ''
        tg = s['test_geometry'] or str(per_type.get(T.alias, '') or '')
        parts = [ident.get('batch', ''), ident.get('sample_geometry', ''), tg, code, ident.get('additional', '')]
        full = ''.join(parts) if all(parts) else ''
        r['n'] = n
        out.append({'n': n, 'sheet': r['sheet'], 'type': T.kind, 'alias': T.alias, 'angle_deg': '%g' % s['angle'],
                    'angle_digit': s['a_digit'] if T.has_code else '', 'index': s['index'] if T.has_code else '',
                    'notch_code': code, 'rotation_on_sheet_deg': r['rotation_deg'],
                    'x_on_sheet_mm': round(r['x_sheet'], 1), 'y_on_sheet_mm': round(r['y_sheet'], 1),
                    'batch': ident.get('batch', ''), 'sample_geometry': ident.get('sample_geometry', ''),
                    'test_geometry': tg, 'additional': ident.get('additional', ''), 'specimen_id': full,
                    'order_line': s['line'], 'block': r['block']})
    return out


# ============================================================
# NOTICE
# ============================================================
def notice(path, cfg, dxf_path, sheets_rows, reg, specs_by_block, checks):
    W, H = cfg['W'], cfg['H']
    d = sl.Drawing(dxf_path)
    n_sheets = max(r['sheet'] for r in reg)
    today = datetime.date.today().isoformat()
    with PdfPages(path) as pdf:
        for k in range(n_sheets):
            ox = k * (W + sp.SHEET_SPACING)
            fig = plt.figure(figsize=(8.27, 11.69))
            ax = fig.add_axes([0.20, 0.10, 0.72, 0.78])
            for s in d.segs:
                xs = [p[0] - ox for p in s.pts]
                if min(xs) < -1 or max(xs) > W + 1:
                    continue
                ys = [p[1] for p in s.pts]
                ax.plot(xs, ys, color=ACI_RGB.get(s.color, '#222222'), lw=0.35 if s.color != 7 else 0.8)
            for r in sheets_rows:
                if r['sheet'] != k + 1:
                    continue
                s = specs_by_block[r['block']]
                T = s['T']
                cx, cy = r['x_sheet'], r['y_sheet']
                ax.text(cx, cy + (0.18 * T.L if T.L / max(T.W, 1) > 1.25 and T.holes else 0), str(r['n']),
                        ha='center', va='center', fontsize=7, color='#333333', zorder=6,
                        bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.8))
            # hatched margins (clamping area + margins): nothing is cut there
            m = cfg['margins']
            bands = [(0, 0, W, m['bottom']), (0, H - m['top'], W, m['top']),
                     (0, m['bottom'], m['left'], H - m['bottom'] - m['top']),
                     (W - m['right'], m['bottom'], m['right'], H - m['bottom'] - m['top'])]
            for bx, by, bw, bh in bands:
                if bw > 0 and bh > 0:
                    ax.add_patch(Rectangle((bx, by), bw, bh, fill=False, hatch='////', ec='#9ca3af', lw=0, zorder=0))
            ax.add_patch(Rectangle((m['left'], m['bottom']), W - m['left'] - m['right'], H - m['bottom'] - m['top'],
                                   fill=False, ec='#9ca3af', lw=0.5, ls='--', zorder=0))
            fs = 6.5
            ax.text(m['left'] / 2, H / 2, '%g mm' % m['left'], rotation=90, ha='center', va='center', fontsize=fs,
                    color='#4b5563', bbox=dict(fc='white', ec='none', pad=0.5))
            ax.text(W - m['right'] / 2, H / 2, '%g mm' % m['right'], rotation=90, ha='center', va='center',
                    fontsize=fs, color='#4b5563', bbox=dict(fc='white', ec='none', pad=0.5))
            ax.text(W / 2, m['bottom'] / 2, '%g mm' % m['bottom'], ha='center', va='center', fontsize=fs,
                    color='#4b5563', bbox=dict(fc='white', ec='none', pad=0.5))
            ax.text(W / 2, H - m['top'] / 2, '%g mm' % m['top'], ha='center', va='center', fontsize=fs,
                    color='#4b5563', bbox=dict(fc='white', ec='none', pad=0.5))
            ax.set_xlim(-10, W + 10)
            ax.set_ylim(-10, H + 10)
            ax.set_aspect('equal')
            ax.axis('off')
            ax.annotate('', xy=(0, -7), xytext=(W, -7), arrowprops=dict(arrowstyle='<->', lw=0.6))
            ax.text(W / 2, -9, 'min %g mm' % W, ha='center', va='top', fontsize=8)
            ax.annotate('', xy=(W + 7, 0), xytext=(W + 7, H), arrowprops=dict(arrowstyle='<->', lw=0.6))
            ax.text(W + 9, H / 2, 'min %g mm' % H, rotation=90, ha='left', va='center', fontsize=8)
            # legend on the left
            lg = fig.add_axes([0.02, 0.10, 0.17, 0.78])
            lg.axis('off')
            lg.set_xlim(0, 1)
            lg.set_ylim(0, 1)
            lg.add_patch(FancyArrow(0.20, 0.86, 0, 0.10, width=0.10, head_width=0.20, head_length=0.04,
                                    color='#3b6fb6'))
            lg.text(0.42, 0.92, 'Rolling\ndirection\n0°', fontsize=8, va='center')
            y = 0.78
            for c, t in ((3, 'Normal quality (Q3)'), (4, 'Medium quality (Q4)'), (5, 'Highest quality (Q5)')):
                lg.plot([0.02, 0.18], [y, y], color=ACI_RGB[c], lw=2)
                lg.text(0.22, y, t, color=ACI_RGB[c], fontsize=7.5, va='center')
                y -= 0.05
            lg.add_patch(Rectangle((0.02, y - 0.015), 0.16, 0.03, fill=False, hatch='////', ec='#9ca3af', lw=0.5))
            lg.text(0.22, y, 'Clamping area /\nmargin: no parts', fontsize=7.5, va='center', color='#4b5563')
            y -= 0.07
            lg.text(0.02, y, 'Numbers: specimen no.\n(see list). Only for\ninformation, bitte\nnicht gravieren.',
                    fontsize=7, va='top', color='#555555')
            lg.text(0.02, 0.13, '%s\n\nsheet %d / %d\n\n%s' % (cfg['name'].replace('_SHEET', '_\nSHEET'), k + 1,
                                                                n_sheets, today),
                    fontsize=7, va='top', bbox=dict(boxstyle='square', fc='white', ec='black', lw=0.6))
            fig.suptitle('EDM cutting sheet %d / %d – %s' % (k + 1, n_sheets, cfg['name']), fontsize=10, y=0.96)
            fig.text(0.20, 0.925, 'DXF: %s\nunits mm  ·  gap between parts ≥ %g mm  ·  margins: %s' % (
                os.path.basename(dxf_path), cfg['gap'], check_sheet.fmt_margins(cfg['margins'])),
                     fontsize=7, color='#444444', va='top')
            pdf.savefig(fig)
            plt.close(fig)
        # specimen list
        per = 45
        for p0 in range(0, len(reg), per):
            fig = plt.figure(figsize=(8.27, 11.69))
            ax = fig.add_axes([0.06, 0.05, 0.88, 0.86])
            ax.axis('off')
            cols = ['No.', 'Sheet', 'Type', 'Angle to RD', 'Notch code\n(angle digit, index)', 'Specimen ID']
            cells = [[r['n'], r['sheet'], r['alias'], '%s°' % r['angle_deg'],
                      '%s, %s' % (r['angle_digit'], r['index']) if r['notch_code'] else '–',
                      r['specimen_id'] or '–'] for r in reg[p0:p0 + per]]
            tb = ax.table(cellText=cells, colLabels=cols, loc='upper center', cellLoc='center',
                          colWidths=[0.07, 0.07, 0.12, 0.13, 0.22, 0.30])
            tb.auto_set_font_size(False)
            tb.set_fontsize(7.5)
            tb.scale(1, 1.25)
            fig.suptitle('Specimen list – %s (%d specimens)' % (cfg['name'], len(reg)), fontsize=10, y=0.96)
            pdf.savefig(fig)
            plt.close(fig)


# ============================================================
# PROGRAM
# ============================================================
def run(order_path, seconds=None, final=False):
    """Order -> plan. Intermediate files go to a temporary folder, always deleted (also after an error)."""
    with tempfile.TemporaryDirectory(prefix='cutting_plan_') as tmp:
        return _run(order_path, seconds, final, tmp)


def _run(order_path, seconds, final, tmp):
    N = 6
    t_start = time.time()
    step(1, N, 'Order and templates')
    cfg = read_order(order_path)
    if seconds is not None:
        cfg['time'] = seconds
    temps = mt.load_templates(cfg['templates'])
    specs = expand(cfg, temps)
    W, H = cfg['W'], cfg['H']
    out = os.path.join(BASE, 'output' if final else 'runs', cfg['name'])
    os.makedirs(out, exist_ok=True)
    for old in ('README.md', 'placement.csv', 'specimens.dxf', 'check'):     # files of older versions of the tool
        old = os.path.join(out, old)
        if os.path.isdir(old):
            shutil.rmtree(old, ignore_errors=True)
        elif os.path.exists(old):
            os.remove(old)
    print('    %s: %d specimens, sheet %g x %g mm, gap %g mm, margins %s'
          % (os.path.basename(order_path), len(specs), W, H, cfg['gap'], fmt_margins(cfg['margins'])))
    for (alias, ang), grp in sorted(collections.Counter(
            (s['T'].alias, s['angle']) for s in specs).items(), key=lambda kv: (kv[0][0], kv[0][1])):
        grp_specs = [s for s in specs if (s['T'].alias, s['angle']) == (alias, ang)]
        print('      %-9s %5g deg  x %d   %s' % (alias, ang, grp, ('index ' + ', '.join(str(s['index']) for s in grp_specs))
                                                if grp_specs[0]['T'].has_code else 'no code'))

    step(2, N, 'Specimens: template + notch code')
    specs_by_block = {s['block']: s for s in specs}
    libdoc = build_specimens(specs, os.path.join(tmp, 'specimens.dxf'))
    print('    %d coded specimens' % len(specs))

    step(3, N, 'Placement (PackingSolver + sparrow)')
    polys = {}
    for sp_ in specs:
        if sp_['T'].kind not in polys:
            polys[sp_['T'].kind] = mt.template_polygon(sp_['T'], closed=True)    # outline without notches
    t0 = time.time()
    state = {'bar': None, 'label': None}

    def on_progress(label, t, best, total):
        if label != state['label'] or t < state.get('t', 0):      # new label, or new run with the same label
            if state['bar']:
                state['bar'].done()
            state['bar'], state['label'] = Bar(label, int(total)), label
        state['t'] = t
        state['bar'].update(min(int(t), int(total)), ('top at %.1f mm' % best) if best else '')

    def log(msg):
        if state['bar']:
            state['bar'].done()
            state['bar'], state['label'], state['t'] = None, None, 0
        print('    ' + msg)
    try:
        sheets = sp.place(specs, polys, W, H, cfg['gap'], cfg['margins'], cfg['time'], cfg['seed'],
                          max_sheets=cfg['max_sheets'], on_progress=on_progress, log=log,
                          assign_seconds=cfg['assign_time'], fill_tries=cfg['fill_tries'],
                          fill_seconds=cfg['fill_time'])
    except sp.PlacementError as e:
        raise OrderError(str(e))
    if state['bar']:
        state['bar'].done()
    print('    %d sheet(s) in %.0f s: %s' % (len(sheets), time.time() - t0, '; '.join(
        'sheet %d = %d specimens, %.0f mm' % (k + 1, len(s), sp.top(s)) for k, s in enumerate(sheets))))

    step(4, N, 'Writing the DXF')
    dxf = os.path.join(out, '%s.dxf' % cfg['name'])
    rows = sp.write_dxf(dxf, sheets, libdoc, W, H)
    for r in rows:
        r['x_sheet'] = r['insert_x_mm'] - (r['sheet'] - 1) * (W + sp.SHEET_SPACING)
        r['y_sheet'] = r['insert_y_mm']

    step(5, N, 'Checking the final DXF')
    t0 = time.time()
    R = check_sheet.analyse(dxf, cfg['gap'], cfg['gap'], cfg['margins'])
    check_sheet.write_outputs(R, os.path.join(tmp, 'check'), argparse.Namespace(
        min_gap=cfg['gap'], warn_gap=cfg['gap'], min_margin=cfg['margins']))
    shutil.copyfile(os.path.join(tmp, 'check', 'preview.png'), os.path.join(out, 'preview.png'))
    print('    plan checks (contours, gaps, margins...) in %.0f s' % (time.time() - t0))
    bar = Bar('Specimens', len(rows))
    bad = code_check(R, rows, specs_by_block, on_progress=bar.update)
    bar.done('outline + code read back')
    checks = list(R['checks']) + [('Specimens vs order', 'OK' if not bad else 'ERROR',
                                   '%d of %d specimens: outline = template, code read in the DXF = code ordered, '
                                   'direction = angle ordered' % (len(rows) - len(bad), len(rows)))]
    for c in checks:
        print('    %-24s %-8s %s' % c)
    for b in bad:
        print('       ' + b)

    step(6, N, 'Notice and registry')
    reg = registry(rows, specs_by_block, cfg)
    with open(os.path.join(out, 'registry.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(reg[0].keys()))
        w.writeheader()
        w.writerows(reg)
    notice(os.path.join(out, 'notice.pdf'), cfg, dxf, rows, reg, specs_by_block, checks)

    status = all(c[1] in ('OK', 'INFO') for c in checks)
    print('')
    print('%s in %s' % ('DONE, all checks OK,' if status else 'DONE WITH ERRORS (see above)',
                        progress_fmt(time.time() - t_start)))
    print('    Plan    : %s' % dxf)
    print('    Notice  : %s' % os.path.join(out, 'notice.pdf'))
    print('    Registry: %s' % os.path.join(out, 'registry.csv'))
    print('    Preview : %s' % os.path.join(out, 'preview.png'))
    if not final:
        print('    (runs/ folder: ignored by git. To keep this plan in the repository, run again with --final)')
    return status, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('order', help='YAML order file')
    ap.add_argument('--time', type=float, default=None, help='overrides "time" of the order (compaction seconds per sheet)')
    ap.add_argument('--final', action='store_true',
                    help='write to output/ (tracked by git) instead of runs/ (ignored by git)')
    args = ap.parse_args()
    try:
        ok, out = run(args.order, args.time, args.final)
    except OrderError as e:
        print('ORDER REJECTED:\n' + str(e))
        sys.exit(2)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
