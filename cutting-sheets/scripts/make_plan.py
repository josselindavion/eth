# -*- coding: utf-8 -*-
"""
make_plan.py -- Plan de decoupe EDM complet a partir d'un fichier de commande ("5 UT a 30 deg, 3 NT20 a 45 deg...").

Lancement (Python 3 + ezdxf, shapely, matplotlib, scipy, pyyaml), depuis la racine du repo :
    py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/exemple_UT30.yaml

Etapes :
    1. lecture de la commande (YAML, voir cutting-sheets/orders/) et controle : type connu, angle multiple de 15 deg
       et codable (0-135 deg), index 0-9, pas deux fois le meme code sur le meme type ;
    2. une eprouvette = gabarit sans code (templates/<nom>/) + son code a encoches (notchcode.py) ;
       angle = direction de la tete qui porte le code depuis le sens de laminage (+Y), sens trigonometrique ;
    3. placement automatique (nest.py) : angle impose ou demi-tour (+180 deg), pas de miroir, ecart et marge ;
    4. plan DXF (mm, calques Q3_NORMAL / Q4_MEDIUM / Q5_HIGH) ;
    5. verifications : check_sheet.py (contours, ecarts, marges...) puis RELECTURE DU CODE de chaque eprouvette dans
       le DXF final (angle, index, direction) et comparaison a la commande ;
    6. registre des eprouvettes (registry.csv) et notice pour l'atelier (notice.pdf : plan numerote, qualites,
       sens de laminage).

Sorties dans cutting-sheets/runs/<nom>/ (dossier IGNORE par git : on peut relancer sans creer de conflit), ou dans
cutting-sheets/output/<nom>/ (suivi par git) avec --final, pour un plan a garder ou a envoyer a l'atelier :
<nom>.dxf, notice.pdf, registry.csv, placement.csv, specimens.dxf, check/ (rapport de verification), README.md.
"""
import argparse
import collections
import csv
import datetime
import math
import os
import sys
import time

import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyArrow           # noqa: E402
import yaml                                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_sheet                                    # noqa: E402
import make_templates as mt                           # noqa: E402
import nest                                           # noqa: E402
import notchcode as nc                                # noqa: E402
import sheetlib as sl                                 # noqa: E402

BASE = os.path.abspath(os.path.join(HERE, '..'))       # dossier cutting-sheets
DEFAULT_TEMPLATES = os.path.join(BASE, 'templates', 'CTLG_261029')     # catalogue du labo
ACI_RGB = {3: '#16a34a', 4: '#06b6d4', 5: '#2546d6', 7: '#222222'}


class OrderError(Exception):
    pass


# ============================================================
# COMMANDE
# ============================================================
def resolve(path, order_dir):
    for cand in (path, os.path.join(order_dir, path), os.path.join(BASE, path),
                 os.path.join(os.path.dirname(BASE), path)):
        if os.path.exists(cand):
            return os.path.abspath(cand)
    raise OrderError('introuvable : %s' % path)


def read_order(path):
    with open(path, encoding='utf-8') as f:
        o = yaml.safe_load(f)
    if not isinstance(o, dict) or 'eprouvettes' not in o:
        raise OrderError('la commande doit contenir une liste "eprouvettes"')
    odir = os.path.dirname(os.path.abspath(path))
    cfg = {
        'nom': str(o.get('nom') or os.path.splitext(os.path.basename(path))[0]),
        'gabarits': resolve(o['gabarits'], odir) if o.get('gabarits') else DEFAULT_TEMPLATES,
        'tole': str(o.get('tole', '500x600')),
        'ecart': float(o.get('ecart', 5.0)),
        'marge': float(o.get('marge', 5.0)),
        'recuit': int(o.get('recuit', 0)),
        'coeurs': int(o['coeurs']) if str(o.get('coeurs', 'auto')).lower() != 'auto' else nest.default_procs(),
        'toles_max': int(o.get('toles_max', 20)),
        'identifiant': o.get('identifiant') or {},
        'lignes': o['eprouvettes'],
    }
    try:
        cfg['W'], cfg['H'] = (float(v) for v in cfg['tole'].lower().split('x'))
    except ValueError:
        raise OrderError('tole : "%s" n\'est pas de la forme 500x600' % cfg['tole'])
    return cfg


def expand(cfg, temps):
    """Une entree par eprouvette : gabarit, angle, chiffre d'angle, index. Leve OrderError si la commande est fausse."""
    specs, used, nxt = [], {}, {}
    errors = []
    for k, line in enumerate(cfg['lignes'], 1):
        where = 'ligne %d (%s)' % (k, line)
        if not isinstance(line, dict) or 'type' not in line or 'angle' not in line:
            errors.append('%s : il faut au moins "type" et "angle"' % where)
            continue
        T = temps.get(str(line['type']).upper()) or temps.get(str(line['type']))
        if T is None:
            errors.append('%s : type inconnu ; types disponibles : %s'
                          % (where, ', '.join(sorted(set(t.alias for t in temps.values())))))
            continue
        ang = float(line['angle'])
        n = int(line.get('nombre', 1))
        if not 0 <= ang < 180:
            errors.append('%s : angle hors de [0, 180[ deg' % where)
            continue
        a_digit = nc.angle_digit(ang)
        if T.has_code and a_digit is None:
            errors.append('%s : angle %g deg non codable (codables : 0, 15, ..., 135 deg)' % (where, ang))
            continue
        key = (T.kind, ang)
        idx = int(line['premier_index']) if 'premier_index' in line else nxt.get(key, 0)     # 0-9, comme le catalogue
        for j in range(n):
            i = idx + j
            if T.has_code and not 0 <= i <= 9:
                errors.append('%s : index %d impossible (un seul chiffre, 0-9) ; maximum 10 eprouvettes par type et '
                              'par angle' % (where, i))
                break
            if (T.kind, ang, i) in used:
                errors.append('%s : %s a %g deg index %d deja commande (%s) : deux eprouvettes auraient le meme code'
                              % (where, T.alias, ang, i, used[(T.kind, ang, i)]))
                continue
            used[(T.kind, ang, i)] = 'ligne %d' % k
            specs.append({'T': T, 'angle': ang, 'a_digit': a_digit, 'index': i, 'line': k,
                          'test_geometry': str(line.get('geometrie_essai', '') or ''),
                          'block': '%s__%03ddeg__%s%d' % (T.kind, round(ang), 'i' if T.has_code else 'n', i)})
        nxt[key] = idx + n
    if errors:
        raise OrderError('\n'.join(errors))
    return specs


# ============================================================
# EPROUVETTES -> BLOCS
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


def make_items(specs):
    polys = {}
    items = []
    for s in specs:
        T = s['T']
        if T.kind not in polys:
            polys[T.kind] = mt.template_polygon(T, closed=True)        # contour sans encoches : conservatif
        row = {'block': s['block'], 'type': T.kind, 'orientation_to_RD_deg': '%g' % sl.fold_rd(s['angle']),
               'axis_angle_in_source_deg': s['angle'], 'rotation_deg': s['angle'], 'shape_key': T.kind}
        it = nest.Item(row, polys[T.kind])
        it.spec = s
        items.append(it)
    return items


# ============================================================
# VERIFICATION DU CODE DANS LE DXF FINAL
# ============================================================
def code_check(R, rows, specs_by_block):
    """Chaque eprouvette du DXF final, relue sans rien supposer : son contour doit etre celui du gabarit (avec son
    code) tourne de l'angle de pose, son code lu doit etre celui commande, et la direction du code l'angle commande."""
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
            msg.append('%d trou(s) au lieu de %d' % (len(p.poly.interiors), len(want.interiors)))
        else:
            rings = lambda g: [g.exterior] + list(g.interiors)                    # noqa: E731
            dev = max(min(a.hausdorff_distance(b) for b in rings(p.poly)) for a in rings(want))
            if dev > 0.02:
                msg.append('contour different du gabarit (ecart %.3f mm)' % dev)
        if T.has_code:
            try:
                c = nc.read_piece(p)
            except ValueError as e:
                c = None
                msg.append('code illisible (%s)' % e)
            if c is None and not msg:
                msg.append('pas de code')
            elif c:
                if (c['angle_digit'], c['index']) != (s['a_digit'], s['index']):
                    msg.append('code lu angle %g / index %d' % (c['angle_deg'], c['index']))
                d = (c['direction_deg'] - s['angle']) % 180.0
                if min(d, 180.0 - d) > 0.5:
                    msg.append('direction %.1f deg' % c['direction_deg'])
                r['code_read'] = '%d%d' % (c['angle_digit'], c['index'])
        r['piece'] = p
        if msg:
            bad.append('%s : %s' % (r['block'], ', '.join(msg)))
    return bad

# ============================================================
# REGISTRE
# ============================================================
def registry(rows, specs_by_block, cfg):
    ident = dict(cfg['identifiant'] or {})
    per_type = ident.get('geometrie_essai') if isinstance(ident.get('geometrie_essai'), dict) else {}
    ident = {k: ('' if v is None else str(v)) for k, v in ident.items() if k != 'geometrie_essai'}
    out = []
    order = sorted(rows, key=lambda r: (r['sheet'], -round(r['y_sheet'] / 25.0), r['x_sheet']))
    for n, r in enumerate(order, 1):
        s = specs_by_block[r['block']]
        T = s['T']
        code = '%d%d' % (s['a_digit'], s['index']) if T.has_code else ''
        tg = s['test_geometry'] or str(per_type.get(T.alias, '') or '')
        parts = [ident.get('lot', ''), ident.get('geometrie_echantillon', ''), tg, code, ident.get('supplement', '')]
        full = ''.join(parts) if all(parts) else ''
        r['n'] = n
        out.append({'n': n, 'sheet': r['sheet'], 'type': T.kind, 'alias': T.alias, 'angle_deg': '%g' % s['angle'],
                    'angle_digit': s['a_digit'] if T.has_code else '', 'index': s['index'] if T.has_code else '',
                    'notch_code': code, 'rotation_on_sheet_deg': r['rotation_deg'],
                    'x_on_sheet_mm': round(r['x_sheet'], 1), 'y_on_sheet_mm': round(r['y_sheet'], 1),
                    'batch': ident.get('lot', ''), 'sample_geometry': ident.get('geometrie_echantillon', ''),
                    'test_geometry': tg, 'additional': ident.get('supplement', ''), 'specimen_id': full,
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
            ox = k * (W + nest.SHEET_SPACING)
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
            ax.set_xlim(-10, W + 10)
            ax.set_ylim(-10, H + 10)
            ax.set_aspect('equal')
            ax.axis('off')
            ax.annotate('', xy=(0, -7), xytext=(W, -7), arrowprops=dict(arrowstyle='<->', lw=0.6))
            ax.text(W / 2, -9, 'min %g mm' % W, ha='center', va='top', fontsize=8)
            ax.annotate('', xy=(W + 7, 0), xytext=(W + 7, H), arrowprops=dict(arrowstyle='<->', lw=0.6))
            ax.text(W + 9, H / 2, 'min %g mm' % H, rotation=90, ha='left', va='center', fontsize=8)
            # legende a gauche
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
            y -= 0.03
            lg.text(0.02, y, 'Numbers: specimen no.\n(see list). Only for\ninformation, bitte\nnicht gravieren.',
                    fontsize=7, va='top', color='#555555')
            lg.text(0.02, 0.13, '%s\n\nsheet %d / %d\n\n%s' % (cfg['nom'].replace('_SHEET', '_\nSHEET'), k + 1,
                                                                n_sheets, today),
                    fontsize=7, va='top', bbox=dict(boxstyle='square', fc='white', ec='black', lw=0.6))
            fig.suptitle('EDM cutting sheet %d / %d – %s' % (k + 1, n_sheets, cfg['nom']), fontsize=10, y=0.96)
            fig.text(0.20, 0.925, 'DXF: %s\nunits mm  ·  gap between parts ≥ %g mm  ·  margin ≥ %g mm' % (os.path.basename(dxf_path), cfg['ecart'], cfg['marge']),
                     fontsize=7, color='#444444', va='top')
            pdf.savefig(fig)
            plt.close(fig)
        # liste des eprouvettes
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
            fig.suptitle('Specimen list – %s (%d specimens)' % (cfg['nom'], len(reg)), fontsize=10, y=0.96)
            pdf.savefig(fig)
            plt.close(fig)


# ============================================================
# PROGRAMME
# ============================================================
def run(order_path, anneal=None, procs=None, final=False):
    cfg = read_order(order_path)
    if anneal is not None:
        cfg['recuit'] = anneal
    if procs is not None:
        cfg['coeurs'] = procs
    temps = mt.load_templates(cfg['gabarits'])
    specs = expand(cfg, temps)
    W, H = cfg['W'], cfg['H']
    out = os.path.join(BASE, 'output' if final else 'runs', cfg['nom'])
    os.makedirs(out, exist_ok=True)
    print('Commande %s : %d eprouvettes, tole %g x %g mm, ecart %g mm, marge %g mm'
          % (os.path.basename(order_path), len(specs), W, H, cfg['ecart'], cfg['marge']))
    for (alias, ang), grp in sorted(collections.Counter(
            (s['T'].alias, s['angle']) for s in specs).items(), key=lambda kv: (kv[0][0], kv[0][1])):
        idx = [s['index'] for s in specs if (s['T'].alias, s['angle']) == (alias, ang)]
        print('   %-7s %5g deg  x %d   index %s' % (alias, ang, grp, ', '.join(map(str, idx))))
    specs_by_block = {s['block']: s for s in specs}
    libdoc = build_specimens(specs, os.path.join(out, 'specimens.dxf'))
    items = make_items(specs)

    t0 = time.time()
    raster = nest.Raster(items, 0.5, cfg['ecart'])
    best = None
    orders = nest.initial_orders(items)
    scores = nest.score_orders(orders, items, raster, W, H, cfg['marge'], cfg['toles_max'], cfg['coeurs'])
    for nm, order in orders.items():
        sc = scores[nm]
        print('   ordre %-7s : %s tole(s), hauteur derniere tole %s mm' % (nm, sc[0], sc[1]))
        if best is None or sc < best[0]:
            best = (sc, order, nm)
    if best[0][0] == math.inf:
        raise OrderError('les eprouvettes ne tiennent pas sur %d toles' % cfg['toles_max'])
    order = best[1]
    if cfg['recuit']:
        print('Recuit simule : %d recuit(s) en parallele de %d iterations, depuis l\'ordre "%s"'
              % (cfg['coeurs'], cfg['recuit'], best[2]))
        order, _ = nest.anneal_parallel(order, items, raster, W, H, cfg['marge'], cfg['toles_max'], cfg['recuit'],
                                        procs=cfg['coeurs'])
    sheets = nest.place_all(order, items, raster, W, H, cfg['marge'], cfg['toles_max'])
    print('Placement : %d tole(s) en %.0f s' % (len(sheets), time.time() - t0))
    for k, s in enumerate(sheets):
        print('   tole %d : %d eprouvettes, hauteur occupee %.1f mm' % (k + 1, len(s.placed), s.top()))

    dxf = os.path.join(out, '%s.dxf' % cfg['nom'])
    rows = nest.write_dxf(dxf, sheets, libdoc, W, H)
    for r in rows:
        r['x_sheet'] = r['insert_x_mm'] - (r['sheet'] - 1) * (W + nest.SHEET_SPACING)
        r['y_sheet'] = r['insert_y_mm']
    R = check_sheet.analyse(dxf, cfg['ecart'], cfg['ecart'], cfg['marge'])
    check_sheet.write_outputs(R, os.path.join(out, 'check'), argparse.Namespace(
        min_gap=cfg['ecart'], warn_gap=cfg['ecart'], min_margin=cfg['marge']))
    bad = code_check(R, rows, specs_by_block)
    checks = list(R['checks']) + [('Specimens vs order', 'OK' if not bad else 'ERROR',
                                   '%d of %d specimens: outline = template, code read in the DXF = code ordered, '
                                   'direction = angle ordered' % (len(rows) - len(bad), len(rows)))]
    print('Verification du plan :')
    for c in checks:
        print('   %-24s %-8s %s' % c)
    for b in bad:
        print('      ' + b)

    reg = registry(rows, specs_by_block, cfg)
    with open(os.path.join(out, 'registry.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(reg[0].keys()))
        w.writeheader()
        w.writerows(reg)
    with open(os.path.join(out, 'placement.csv'), 'w', newline='') as f:
        keys = ['sheet', 'block', 'type', 'orientation_to_RD_deg', 'rotation_deg', 'insert_x_mm', 'insert_y_mm']
        w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    notice(os.path.join(out, 'notice.pdf'), cfg, dxf, rows, reg, specs_by_block, checks)
    write_readme(out, cfg, order_path, specs, sheets, checks, bad, reg)
    print('Plan    : %s' % dxf)
    print('Notice  : %s' % os.path.join(out, 'notice.pdf'))
    print('Registre: %s' % os.path.join(out, 'registry.csv'))
    if not final:
        print('(dossier runs/ : ignore par git. Pour garder ce plan dans le repo : relancer avec --final)')
    status = all(c[1] in ('OK', 'INFO') for c in checks)
    return status, out


def write_readme(out, cfg, order_path, specs, sheets, checks, bad, reg):
    L = ['# Cutting plan `%s`' % cfg['nom'], '',
         '*Generated on %s by `cutting-sheets/scripts/make_plan.py` from the order `%s` and the templates `%s`.*'
         % (datetime.date.today().isoformat(), os.path.basename(order_path), os.path.basename(cfg['gabarits'])), '',
         '## Order', '', '| Type | Angle to RD | Number | Indices (notch code) |', '|---|---|---|---|']
    grp = collections.OrderedDict()
    for s in specs:
        grp.setdefault((s['T'].alias, s['angle']), []).append(s['index'])
    for (a, ang), idx in grp.items():
        L.append('| %s | %g° | %d | %s |' % (a, ang, len(idx), ', '.join(map(str, idx))))
    L += ['', '## Result', '',
          '%d specimens on %d sheet(s) of %g × %g mm (gap ≥ %g mm, margin ≥ %g mm).'
          % (len(specs), len(sheets), cfg['W'], cfg['H'], cfg['ecart'], cfg['marge']), '',
          '| Sheet | Specimens | Height used (mm) |', '|---|---|---|']
    for k, s in enumerate(sheets):
        L.append('| %d | %d | %.1f |' % (k + 1, len(s.placed), s.top()))
    L += ['', '## Checks of the final DXF', '', '| Check | Status | Detail |', '|---|---|---|']
    L += ['| %s | %s | %s |' % c for c in checks]
    if bad:
        L += [''] + ['- ' + b for b in bad]
    L += ['', '![Plan](check/preview.png)', '',
          '## Files', '',
          '- `%s.dxf`: the plan for the workshop (mm, layers `Q3_NORMAL` / `Q4_MEDIUM` / `Q5_HIGH`).'
          % cfg['nom'],
          '- `notice.pdf`: one page per sheet (specimen numbers, qualities, rolling '
          'direction) and the specimen list.',
          '- `registry.csv`: one line per specimen: number, sheet, type, angle, notch code (angle digit, index), '
          'position, specimen ID (when the batch and geometry codes are given in the order).',
          '- `placement.csv`, `specimens.dxf`: blocks and their insertion; `check/`: report of `check_sheet.py`.']
    with open(os.path.join(out, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('order', help='fichier de commande YAML')
    ap.add_argument('--recuit', type=int, default=None, help='remplace "recuit" de la commande')
    ap.add_argument('--coeurs', type=int, default=None, help='remplace "coeurs" de la commande')
    ap.add_argument('--final', action='store_true',
                    help='ecrire dans output/ (suivi par git) au lieu de runs/ (ignore par git)')
    args = ap.parse_args()
    try:
        ok, out = run(args.order, args.recuit, args.coeurs, args.final)
    except OrderError as e:
        print('COMMANDE REFUSEE :\n' + str(e))
        sys.exit(2)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
