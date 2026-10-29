# -*- coding: utf-8 -*-
"""
extract_library.py -- Bibliotheque d'eprouvettes a partir d'un plan de decoupe DXF existant.

Lancement (Python 3 + ezdxf, shapely, matplotlib), depuis la racine du repo :
    py cutting-sheets/scripts/extract_library.py cutting-sheets/input/<plan>.dxf <nom_bibliotheque>

Etapes :
    1. lecture du plan (sheetlib) ;
    2. reparation des contours ouverts a partir d'une eprouvette JUMELLE intacte (meme type, meme forme) :
       la jumelle est superposee a l'eprouvette cassee (rotation + translation), les traits qui manquent sont
       recopies de la jumelle (geometrie exacte : arcs restent des arcs), les morceaux isoles en trop sont retires ;
       le code a encoches de l'eprouvette cassee n'est jamais modifie ;
    3. une piece = une eprouvette ; chacune est ramenee dans un repere canonique (centre a l'origine, axe vers la
       tete qui porte le code = +Y) et ecrite comme un bloc DXF ;
    4. controle : toutes les eprouvettes d'un meme type doivent avoir la meme forme (au code pres).

Sorties dans cutting-sheets/library/<nom>/ :
    specimens.dxf        un bloc par eprouvette (calques Q3_NORMAL / Q4_MEDIUM / Q5_HIGH, couleurs 3 / 4 / 5, mm) ;
                         le modelspace montre tous les blocs en grille, avec leur nom
    index.csv            une ligne par bloc : type, orientation dans le plan d'origine, tole, position, code, reparation
    repaired_source.dxf  le plan d'origine repare, a plat (sans blocs), pour verification avec check_sheet.py
    types.png, README.md un exemple par type, dimensions, controle de forme, reparations effectuees
"""
import collections
import csv
import math
import os
import sys

import ezdxf
from ezdxf.math import Matrix44
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt          # noqa: E402
from shapely import affinity             # noqa: E402
from shapely.geometry import MultiPoint, Point   # noqa: E402
from shapely.ops import unary_union       # noqa: E402
from shapely.strtree import STRtree       # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheetlib as sl                    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, '..', 'library'))
MATCH_TOL = 0.05          # mm : deux traits sont "les memes" si tous leurs points sont a moins de 0,05 mm
LAYERS = {3: 'Q3_NORMAL', 4: 'Q4_MEDIUM', 5: 'Q5_HIGH'}
ACI_RGB = {3: '#16a34a', 4: '#06b6d4', 5: '#2546d6'}


# ============================================================
# REPARATION
# ============================================================
def is_code_seg(s):
    return s.color == 5 and s.kind == 'LINE' and s.length <= sl.CODE_SEG_MAX


def sample(lines, step=0.5):
    pts = []
    for ln in lines:
        n = max(2, int(ln.length / step) + 1)
        pts += [ln.interpolate(k / (n - 1), normalized=True) for k in range(n)]
    return pts


def frame_of(points):
    """Centre et axe long (degres depuis +Y) d'un nuage de points, par le rectangle englobant minimal."""
    hull = MultiPoint(points).convex_hull
    r = hull.minimum_rotated_rectangle
    xs = list(r.exterior.coords)
    e1 = (xs[1][0] - xs[0][0], xs[1][1] - xs[0][1])
    e2 = (xs[2][0] - xs[1][0], xs[2][1] - xs[1][1])
    l1, l2 = math.hypot(*e1), math.hypot(*e2)
    u = e1 if l1 >= l2 else e2
    c = r.centroid
    return (c.x, c.y), math.degrees(math.atan2(-u[0], u[1])), max(l1, l2), min(l1, l2), hull.area


def repair(drawing):
    """Repare les contours ouverts. Retourne (liste des traits finaux sous forme (entite, couleur), journal)."""
    cut = drawing.cut
    log = []
    open_pts = set(sl.open_ends(cut))
    if not open_pts:
        return [(s.entity, s.color) for s in cut], log
    comps = sl.components(cut)
    broken = [c for c in comps if any(p in open_pts for s in c for p in s.ends())]
    ok_pieces = sl.pieces(drawing, [s for c in comps if c not in broken for s in c])
    removed, added = set(), []
    for comp in broken:
        pts = [Point(p) for s in comp for p in s.pts]
        (cx, cy), ang, L, W, area = frame_of(pts)
        where = '(%.1f, %.1f)' % (cx, cy)
        if L < 5.0:
            # petit morceau isole (ex. un bout d'arc egare) : on le retire s'il ne touche aucune piece fermee
            host = next((p for p in ok_pieces if p.poly.buffer(0.5).contains(MultiPoint([q.coords[0] for q in pts]))), None)
            for s in comp:
                removed.add(s.i)
            log.append('stray fragment (%s) at %s, not connected to any contour: removed%s'
                       % (', '.join('%s %s%s, %.2f mm long' % (s.kind, sl.QUALITY.get(s.color, s.color),
                                                               ' R%.2f' % s.radius if s.radius else '', s.length) for s in comp),
                          where, '' if host is None else
                          ' (it lay inside piece %d, which is closed without it)' % host.k))
            continue
        # jumelles possibles : pieces fermees de memes dimensions
        cands = [p for p in ok_pieces if abs(p.L - L) < 0.3 and abs(p.W - W) < 0.3]
        my_code = [s.line for s in comp if is_code_seg(s)]
        my_code_zone = unary_union(my_code).buffer(1.0) if my_code else None
        mine = [s for s in comp if not is_code_seg(s)]
        mine_pts = sample([s.line for s in mine])
        tree_mine = STRtree([s.line for s in mine])
        best = None
        for p in cands:
            tw = [s for s in p.segs if not is_code_seg(s)]
            (tx, ty), tang, *_ = frame_of([Point(q) for s in p.segs for q in s.pts])
            rots = (0, 180) if L / W > 1.25 else (0, 90, 180, 270)
            for k in rots:
                rot = ang - tang + k
                lines = [affinity.translate(affinity.rotate(s.line, rot, origin=(tx, ty)), cx - tx, cy - ty) for s in tw]
                tree = STRtree(lines)
                hit = sum(1 for q in mine_pts if tree.query(q.buffer(MATCH_TOL)).size and
                          min(lines[i].distance(q) for i in tree.query(q.buffer(MATCH_TOL))) <= MATCH_TOL)
                score = hit / max(len(mine_pts), 1)
                if best is None or score > best[0]:
                    best = (score, p, rot, (tx, ty), lines, tw)
        if best is None or best[0] < 0.95:
            log.append('open contour at %s: NOT repaired (no intact twin found, best match %.0f %%)'
                       % (where, 100 * (best[0] if best else 0)))
            continue
        score, twin, rot, (tx, ty), lines, tw = best
        # zones des codes (la piece cassee et la jumelle n'ont pas le meme code : on n'y touche pas)
        zones = [z for z in (my_code_zone, affinity.translate(affinity.rotate(twin.code['geom'], rot, origin=(tx, ty)),
                                                                 cx - tx, cy - ty).buffer(1.0) if twin.code else None) if z is not None]
        in_code = lambda ln: any(z.intersects(ln) for z in zones)       # noqa: E731
        # traits de la jumelle absents de la piece cassee -> a ajouter
        n_add = 0
        for ln, s in zip(lines, tw):
            if in_code(ln):
                continue
            qs = sample([ln], step=0.2)
            near = tree_mine.query(ln.buffer(MATCH_TOL))
            if all(any(mine[i].line.distance(q) <= MATCH_TOL for i in near) for q in qs):
                continue
            m = Matrix44.chain(Matrix44.translate(-tx, -ty, 0), Matrix44.z_rotate(math.radians(rot)),
                               Matrix44.translate(cx, cy, 0))
            e = s.entity.copy()
            e.transform(m)
            added.append((e, s.color))
            n_add += 1
        # traits de la piece cassee absents de la jumelle (hors code) -> morceaux en trop, retires
        tree_tw = STRtree(lines)
        n_rem = 0
        for s in mine:
            if in_code(s.line):
                continue
            qs = sample([s.line], step=0.2)
            near = tree_tw.query(s.line.buffer(MATCH_TOL))
            if not all(any(lines[i].distance(q) <= MATCH_TOL for i in near) for q in qs):
                removed.add(s.i)
                n_rem += 1
        log.append('open contour at %s (%s): repaired from twin piece %d (%s, match %.1f %%): %d line(s) copied, '
                   '%d stray line(s) removed' % (where, twin.kind, twin.k, '%.0f° rotation' % (rot % 360), 100 * score,
                                                 n_add, n_rem))
    final = [(s.entity, s.color) for s in cut if s.i not in removed] + added
    return final, log


def write_flat(path, ents, drawing):
    """DXF a plat : traits de coupe (calques par qualite) + cadres de tole, en mm."""
    doc = ezdxf.new('R2000', setup=True)
    doc.header['$INSUNITS'] = 4
    for c, name in LAYERS.items():
        doc.layers.add(name, color=c)
    doc.layers.add('SHEET', color=7)
    msp = doc.modelspace()
    for e, c in ents:
        x = e.copy()
        x.dxf.layer = LAYERS.get(c, '0')
        x.dxf.color = c
        msp.add_foreign_entity(x, copy=False)
    for s in drawing.black:
        x = s.entity.copy()
        x.dxf.layer = 'SHEET'
        x.dxf.color = 7
        msp.add_foreign_entity(x, copy=False)
    doc.saveas(path)


# ============================================================
# BIBLIOTHEQUE
# ============================================================
def build(src, name):
    out = os.path.join(LIB, name)
    os.makedirs(out, exist_ok=True)
    d0 = sl.Drawing(src)
    ents, log = repair(d0)
    rep_path = os.path.join(out, 'repaired_source.dxf')
    write_flat(rep_path, ents, d0)
    d = sl.Drawing(rep_path)
    frs = sl.frames(d)
    pcs = sl.pieces(d)
    sl.assign_sheets(pcs, frs)
    still_open = sl.open_ends(d.cut)
    repaired_at = [l for l in log if 'repaired' in l or 'removed' in l]

    # blocs canoniques
    doc = ezdxf.new('R2000', setup=True)
    doc.header['$INSUNITS'] = 4
    for c, ln in LAYERS.items():
        doc.layers.add(ln, color=c)
    doc.layers.add('LABEL', color=7)
    msp = doc.modelspace()
    rows, names = [], collections.Counter()
    order = sorted(pcs, key=lambda p: (p.kind, round(sl.fold_rd(p.axis_deg)), p.sheet, -p.center[1], p.center[0]))
    canon = {}
    for p in order:
        o = round(sl.fold_rd(p.axis_deg))
        base = '%s__%02ddeg' % (p.kind, o) if not p.kind.startswith('DISC') else p.kind
        names[base] += 1
        bname = '%s__%02d' % (base, names[base])
        cx, cy = p.center
        m = Matrix44.chain(Matrix44.translate(-cx, -cy, 0), Matrix44.z_rotate(math.radians(-sl.pose_angle(p))))
        blk = doc.blocks.new(bname)
        for s in p.segs:
            e = s.entity.copy()
            e.transform(m)
            e.dxf.layer = LAYERS.get(s.color, '0')
            e.dxf.color = s.color
            blk.add_foreign_entity(e, copy=False)
        canon[bname] = (p, sl.canonical(p, p.poly))
        fixed = [l for l in repaired_at if p.poly.buffer(1.0).contains(Point(*map(float, l.split('at (')[1].split(')')[0].split(','))))]
        rows.append({'block': bname, 'type': p.kind, 'orientation_to_RD_deg': o if not p.kind.startswith('DISC') else '',
                     'axis_angle_in_source_deg': round(p.axis_deg, 2), 'source_sheet': p.sheet,
                     'source_x_mm': round(cx, 2), 'source_y_mm': round(cy, 2), 'L_mm': round(p.L, 2), 'W_mm': round(p.W, 2),
                     'holes': len(p.poly.interiors), 'hole_axis_to_RD_deg': p.features.get('holes_rd', ''),
                     'code_signature': '%08x' % sl.code_signature(p) if p.code else '',
                     'repaired': '; '.join(fixed)})
    # grille de visualisation dans le modelspace
    x, y, rowh, col = 0.0, 0.0, 0.0, None
    for r in rows:
        p, cpoly = canon[r['block']]
        b = cpoly.bounds
        w, h = b[2] - b[0], b[3] - b[1]
        if col is not None and col != r['type']:
            x, y, rowh = 0.0, y - rowh - 40, 0.0
        if x + w > 900:
            x, y, rowh = 0.0, y - rowh - 25, 0.0
        msp.add_blockref(r['block'], (x - b[0], y - b[3]))
        msp.add_text(r['block'], dxfattribs={'height': 2.0, 'layer': 'LABEL'}).set_placement((x, y + 3))
        x += w + 15
        rowh = max(rowh, h)
        col = r['type']
    doc.saveas(os.path.join(out, 'specimens.dxf'))

    with open(os.path.join(out, 'index.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # controle de forme : meme type = meme forme (au code pres)
    shape = {}
    for t in sorted(set(r['type'] for r in rows)):
        bl = [r['block'] for r in rows if r['type'] == t]
        ref_p, ref = canon[bl[0]]
        codes = lambda pp: (sl.canonical(pp, pp.code['geom']).buffer(1.5) if pp.code else None)  # noqa: E731
        worst = 0.0
        for b in bl[1:]:
            pp, g = canon[b]
            diff = ref.symmetric_difference(g)
            for cz in (codes(ref_p), codes(pp)):
                if cz is not None:
                    diff = diff.difference(cz)
            worst = max(worst, diff.area)
        shape[t] = (len(bl), worst, ref_p)
    fig_types(canon, rows, shape, os.path.join(out, 'types.png'))
    write_readme(out, src, name, rows, shape, log, still_open, d0, d)
    return rows, shape, log, still_open


def fig_types(canon, rows, shape, path):
    types = sorted(shape)
    n = len(types)
    cols = min(6, n)
    nr = int(math.ceil(n / cols))
    fig, axs = plt.subplots(nr, cols, figsize=(2.3 * cols, 4.0 * nr), squeeze=False)
    for ax in axs.flat:
        ax.axis('off')
    for ax, t in zip(axs.flat, types):
        b = next(r['block'] for r in rows if r['type'] == t)
        p, _ = canon[b]
        cx, cy = p.center
        for s in p.segs:
            ln = affinity.rotate(affinity.translate(s.line, -cx, -cy), -sl.pose_angle(p), origin=(0, 0))
            xs, ys = ln.xy
            ax.plot(xs, ys, color=ACI_RGB.get(s.color, 'k'), lw=0.7)
        ax.set_aspect('equal')
        ax.set_title('%s\n%.1f × %.1f mm, n = %d' % (t, p.L, p.W, shape[t][0]), fontsize=7)
    fig.suptitle('One specimen per type, canonical pose (code end up). Green Q3, cyan Q4, blue Q5.', fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def write_readme(out, src, name, rows, shape, log, still_open, d0, d):
    L = ['# Specimen library `%s`' % name, '',
         '*Generated by `cutting-sheets/scripts/extract_library.py` from `%s`.*' % os.path.basename(src), '',
         '## Content', '',
         '| Type (provisional name) | Size (mm) | Number | Orientations to rolling direction | Shape check |',
         '|---|---|---|---|---|']
    for t, (n, worst, p) in sorted(shape.items()):
        angs = collections.Counter(r['orientation_to_RD_deg'] for r in rows if r['type'] == t)
        L.append('| %s | %.1f × %.1f | %d | %s | %s |' % (
            t, p.L, p.W, n, ', '.join('%s° × %d' % (a, k) for a, k in sorted(angs.items())) if '' not in angs else '–',
            ('identical (residual %.2f mm², discretisation)' % worst) if worst < 0.5 else 'differs by up to %.2f mm² (outside the code)' % worst))
    L += ['', '*Shape check: all specimens of a type are brought to the same pose and compared with the first one; the '
          'area that differs, outside the notch code, must be ≈ 0.*', '',
          '![Types](types.png)', '',
          '> **Figure 1 – One specimen of each type.**', '>',
          '> *Plotted* – the first block of each type in its canonical pose (centre at the origin, axis towards the head '
          'with the notch code = +Y), lines in their EDM quality colour.', '>',
          '> *Source* – `specimens.dxf` of this library.', '>',
          '> *How to read it* – the type name gives the provisional family (UT, NT_R, CH_D, DISC, STRIP) and the overall '
          'length L.', '',
          '## Repairs of the source drawing', '']
    if log:
        L += ['- ' + l for l in log]
    else:
        L += ['None needed: every contour of the source drawing is closed.']
    L += ['', 'Source drawing: %d cutting lines, %d open end(s). Repaired drawing (`repaired_source.dxf`): %d cutting '
          'lines, %d open end(s).' % (len(d0.cut), len(sl.open_ends(d0.cut)), len(d.cut), len(still_open)), '',
          '## Files', '',
          '- `specimens.dxf`: one block per specimen, named `<type>__<orientation>deg__<n>` (discs: `<type>__<n>`), '
          'canonical pose, layers `Q3_NORMAL` / `Q4_MEDIUM` / `Q5_HIGH` (colours 3 / 4 / 5), millimetres. The model '
          'space shows all blocks in a grid with their names.',
          '- `index.csv`: one line per block: type, orientation to the rolling direction, axis angle in the source '
          'drawing (degrees from +Y, counter-clockwise, towards the code), source sheet and position, size, holes, '
          'notch-code signature, repair applied.',
          '- `repaired_source.dxf`: the source drawing after repair, without blocks (check it with `check_sheet.py`).']
    with open(os.path.join(out, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    rows, shape, log, still_open = build(sys.argv[1], sys.argv[2])
    for l in log:
        print('  ' + l)
    print('%d eprouvettes, %d types ; extremites libres restantes : %d' % (len(rows), len(shape), len(still_open)))
    for t, (n, worst, p) in sorted(shape.items()):
        print('  %-22s n=%2d  forme : %s' % (t, n, ('identique (residu %.2f mm2)' % worst) if worst < 0.5 else 'ecart %.2f mm2' % worst))
    print('Bibliotheque : %s' % os.path.join(LIB, sys.argv[2]))


if __name__ == '__main__':
    main()
