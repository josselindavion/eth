# -*- coding: utf-8 -*-
"""
make_templates.py -- Gabarits d'eprouvettes SANS code, a partir d'une bibliotheque extraite d'un plan.

Lancement (depuis la racine du repo) :
    py cutting-sheets/scripts/make_templates.py cutting-sheets/library/CT_600x500_v20260901 CT_v20260901

Pour chaque type d'eprouvette :
    1. une eprouvette du plan (repare) sert de modele ; son code est lu (notchcode.read_piece) ;
    2. le gabarit = ses traits, SANS les 19 traits du code ni le trait Q3 qui suit le code (sa longueur depend du
       code : le code fait 12 ou 13 mm) ; on garde la position du code et le point ou ce trait se termine ;
    3. repere du gabarit : centre du rectangle englobant minimal a l'origine, code en haut (+Y) ;
       angle de l'eprouvette = direction du code depuis le sens de laminage (+Y) ;
    4. Mikrosteg (pour la notice seulement) : milieu du plus long trait droit Q3 du contour, loin du code.

Validation : CHAQUE eprouvette codee du plan est regeneree a partir du gabarit et de son code lu (angle, index),
puis comparee a l'originale : traits du code (ecart max) et contour complet (surface de difference).

Sorties dans cutting-sheets/templates/<nom>/ : templates.dxf (un bloc T__<type> par type), templates.csv,
validation.csv, templates.png, README.md.
"""
import collections
import csv
import math
import os
import sys

import ezdxf
from ezdxf import path as dpath
from ezdxf.math import Matrix44
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt          # noqa: E402
from shapely import affinity             # noqa: E402
from shapely.geometry import LineString, Point, Polygon   # noqa: E402
from shapely.ops import polygonize, unary_union          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import notchcode as nc                   # noqa: E402
import sheetlib as sl                    # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', 'templates'))
LAYERS = {3: 'Q3_NORMAL', 4: 'Q4_MEDIUM', 5: 'Q5_HIGH'}
ACI_RGB = {3: '#16a34a', 4: '#06b6d4', 5: '#2546d6', 7: '#444444'}
# noms courts utilisables dans le fichier de commande
ALIASES = {'UT_L106': 'UT', 'NT_R20.00_L106': 'NT20', 'NT_R6.67_L106': 'NT6.67', 'CH_D4.8_L106': 'CH',
           'DISC_0H': 'DISC0', 'DISC_2H': 'DISC2', 'STRIP_140x30': 'STRIP'}


def family(kind):
    """Les disques a 2 trous (00 / 45 / 90) sont un seul gabarit tourne : DISC_2H."""
    return 'DISC_2H' if kind.startswith('DISC_2H') else kind


# ============================================================
# GABARIT
# ============================================================
class Template:
    """Gabarit d'un type : entites (repere du gabarit), position du code, fin du trait qui suit le code."""

    def __init__(self, kind, alias, ents, code_origin=None, tail_end_x=None, tail_color=3, mikrosteg=None,
                 L=0.0, W=0.0, holes=0, depth=nc.DEPTH, source=''):
        self.kind, self.alias, self.ents = kind, alias, ents         # ents : liste (entite ezdxf, couleur)
        self.code_origin, self.tail_end_x, self.tail_color = code_origin, tail_end_x, tail_color
        self.mikrosteg, self.L, self.W, self.holes, self.depth, self.source = mikrosteg, L, W, holes, depth, source

    @property
    def has_code(self):
        return self.code_origin is not None

    def code_prims(self, a_digit, index):
        """Traits a ajouter au gabarit pour un code : liste ((x0, y0), (x1, y1), couleur)."""
        ox, oy = self.code_origin
        lines, length = nc.code_lines(a_digit, index, self.depth)
        prims = [((ox + a[0], oy + a[1]), (ox + b[0], oy + b[1]), 5) for a, b in lines]
        prims.append(((ox + length, oy), (self.tail_end_x, oy), self.tail_color))
        return prims

    def closing_prim(self):
        """Trait droit qui ferme le gabarit a la place du code (contour exterieur pour le placement)."""
        ox, oy = self.code_origin
        return ((ox, oy), (self.tail_end_x, oy), self.tail_color)


def piece_transform(p, code):
    """Matrice qui amene la piece dans le repere du gabarit : centre a l'origine, code (ou axe) vers +Y."""
    ang = code['direction_deg'] if code else sl.pose_angle(p)
    cx, cy = p.center
    return Matrix44.chain(Matrix44.translate(-cx, -cy, 0), Matrix44.z_rotate(math.radians(-ang))), ang, (cx, cy)


def apply(m, pt):
    v = m.transform((pt[0], pt[1], 0))
    return (v.x, v.y)


def build_template(p, alias):
    code = nc.read_piece(p)
    m, ang, c = piece_transform(p, code)
    code_ids = set(id(s) for s in p.code['segs']) if code else set()
    tail, origin, tail_end = None, None, None
    if code:
        o, t, n = code['frame']
        end = nc.to_global((code['length_mm'], 0.0), o, t, n)
        for s in p.segs:
            if id(s) in code_ids or s.kind != 'LINE':
                continue
            a, b = s.ends()
            if math.dist(a, end) < 0.02 or math.dist(b, end) < 0.02:
                far = b if math.dist(a, end) < 0.02 else a
                if abs(nc.to_local(far, o, t, n)[1]) < 0.02:
                    tail = s
                    tail_end = apply(m, far)
        if tail is None:
            raise SystemExit('%s : trait qui suit le code introuvable' % p.kind)
        origin = apply(m, o)
    ents = []
    for s in p.segs:
        if id(s) in code_ids or s is tail:
            continue
        e = s.entity.copy()
        e.transform(m)
        ents.append((e, s.color))
    T = Template(family(p.kind), alias, ents, origin, tail_end[0] if tail else None, tail.color if tail else 3,
                 L=p.L, W=p.W, holes=len(p.poly.interiors), depth=code['depth_mm'] if code else nc.DEPTH)
    if code:
        T.code_origin = (round(origin[0], 4), round(origin[1], 4))
        T.tail_end_x = round(T.tail_end_x, 4)
    T.mikrosteg = mikrosteg_point(T)
    return T


def mikrosteg_point(T):
    """Milieu du plus long trait droit Q3 du contour exterieur, a plus de 3 mm du code ; sinon milieu du plus long
    arc Q3. Proposition a confirmer : la notice du labo dit seulement "au milieu d'un cote sans importance"."""
    outer = template_polygon(T, closed=True).exterior
    zone = None
    if T.has_code:
        ox, oy = T.code_origin
        zone = LineString([(ox, oy), (T.tail_end_x, oy)]).buffer(3.0 + T.depth)
    best = None
    for e, c in T.ents:
        if c != 3:
            continue
        ln = LineString(flatten(e))
        if outer.distance(ln) > 0.02 or ln.length < 3.0 or (zone is not None and zone.intersects(ln)):
            continue
        rank = (e.dxftype() == 'LINE', round(ln.length, 2))
        if best is None or rank > best[0]:
            best = (rank, ln.interpolate(0.5, normalized=True))
    return (round(best[1].x, 3), round(best[1].y, 3)) if best else None


def flatten(e):
    return [(round(v.x, 4), round(v.y, 4)) for v in dpath.make_path(e).flattening(0.01)]


def polygon_from_lines(lines):
    """Polygone (avec trous) forme par des polylignes ; extremites fusionnees a sheetlib.JOIN_TOL."""
    verts = []

    def snap(q):
        for r in verts:
            if abs(r[0] - q[0]) <= sl.JOIN_TOL and abs(r[1] - q[1]) <= sl.JOIN_TOL:
                return r
        verts.append(q)
        return q
    ls = []
    for pts in lines:
        pts = list(pts)
        pts[0], pts[-1] = snap(pts[0]), snap(pts[-1])
        ls.append(LineString(pts))
    polys = sorted(polygonize(unary_union(ls)), key=lambda q: -q.area)
    if not polys:
        raise ValueError('contour non ferme')
    outer = polys[0]
    shell = Polygon(outer.exterior)
    holes = [h for h in polys[1:] if shell.contains(h.representative_point()) and h.area < 0.5 * outer.area]
    holes = [h for h in holes if not any(h2 is not h and h2.area > h.area and h2.contains(h.representative_point())
                                         for h2 in holes)]
    return Polygon(outer.exterior, [h.exterior for h in holes])


def template_polygon(T, a_digit=None, index=None, closed=False):
    """Contour de l'eprouvette : gabarit + code (a_digit, index), ou gabarit ferme par un trait droit."""
    lines = [flatten(e) for e, _ in T.ents]
    if T.has_code:
        prims = [T.closing_prim()] if closed or a_digit is None else T.code_prims(a_digit, index)
        lines += [[a, b] for a, b, _ in prims]
    return polygon_from_lines(lines)


# ============================================================
# ECRITURE / LECTURE
# ============================================================
FIELDS = ['type', 'alias', 'block', 'has_code', 'code_x0', 'code_y0', 'code_depth', 'tail_end_x', 'tail_color',
          'mikrosteg_x', 'mikrosteg_y', 'L_mm', 'W_mm', 'holes', 'source_piece']


def write_templates(out, temps):
    doc = ezdxf.new('R2000', setup=True)
    doc.header['$INSUNITS'] = 4
    for c, ln in LAYERS.items():
        doc.layers.add(ln, color=c)
    rows = []
    for T in temps:
        blk = doc.blocks.new('T__' + T.kind)
        for e, c in T.ents:
            x = e.copy()
            x.dxf.layer, x.dxf.color = LAYERS.get(c, '0'), c
            blk.add_foreign_entity(x, copy=False)
        rows.append({'type': T.kind, 'alias': T.alias, 'block': 'T__' + T.kind, 'has_code': int(T.has_code),
                     'code_x0': T.code_origin[0] if T.has_code else '', 'code_y0': T.code_origin[1] if T.has_code else '',
                     'code_depth': T.depth if T.has_code else '', 'tail_end_x': T.tail_end_x if T.has_code else '',
                     'tail_color': T.tail_color if T.has_code else '',
                     'mikrosteg_x': T.mikrosteg[0] if T.mikrosteg else '', 'mikrosteg_y': T.mikrosteg[1] if T.mikrosteg else '',
                     'L_mm': round(T.L, 2), 'W_mm': round(T.W, 2), 'holes': T.holes, 'source_piece': T.source})
    x = 0.0
    msp = doc.modelspace()
    for T in temps:
        msp.add_blockref('T__' + T.kind, (x + T.W, 0))
        x += 2 * T.W + 20
    doc.saveas(os.path.join(out, 'templates.dxf'))
    with open(os.path.join(out, 'templates.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def load_templates(tdir):
    """Gabarits d'un dossier templates/<nom>/ : dict type -> Template (et alias -> meme objet)."""
    doc = ezdxf.readfile(os.path.join(tdir, 'templates.dxf'))
    out = {}
    with open(os.path.join(tdir, 'templates.csv')) as f:
        for r in csv.DictReader(f):
            ents = [(e, abs(e.dxf.color)) for e in doc.blocks.get(r['block'])]
            has = r['has_code'] == '1'
            T = Template(r['type'], r['alias'], ents,
                         (float(r['code_x0']), float(r['code_y0'])) if has else None,
                         float(r['tail_end_x']) if has else None, int(r['tail_color']) if has else 3,
                         (float(r['mikrosteg_x']), float(r['mikrosteg_y'])) if r['mikrosteg_x'] else None,
                         float(r['L_mm']), float(r['W_mm']), int(r['holes']),
                         float(r['code_depth']) if has else nc.DEPTH, r['source_piece'])
            out[T.kind] = T
            out[T.alias.upper()] = T
    return out


# ============================================================
# VALIDATION
# ============================================================
def validate(T, p):
    """Regenere la piece p du plan a partir du gabarit T et de son code lu ; compare a l'originale."""
    code = nc.read_piece(p)
    m, ang, c = piece_transform(p, code)
    orig = affinity.rotate(affinity.translate(p.poly, -c[0], -c[1]), -ang, origin=(0, 0))
    res = {'angle_deg': '', 'index': '', 'code_max_dev_mm': '', 'outline_diff_mm2': '', 'outline_max_dev_mm': ''}
    if code:
        res['angle_deg'], res['index'] = code['angle_deg'], code['index']
        gen = [LineString([a, b]) for a, b, col in T.code_prims(code['angle_digit'], code['index']) if col == 5]
        mine = [LineString([apply(m, s.pts[0]), apply(m, s.pts[-1])]) for s in p.code['segs']]
        dev = max(min(g.hausdorff_distance(q) for q in mine) for g in gen)
        dev = max(dev, max(min(q.hausdorff_distance(g) for g in gen) for q in mine))
        res['code_max_dev_mm'] = round(dev, 4)
        res['n_code_lines'] = '%d / %d' % (len(gen), len(mine))
        poly = template_polygon(T, code['angle_digit'], code['index'])
    else:
        poly = template_polygon(T)
    res['outline_diff_mm2'] = round(poly.symmetric_difference(orig).area, 4)
    rings = lambda g: [g.exterior] + list(g.interiors)                     # noqa: E731
    if len(poly.interiors) != len(orig.interiors):
        res['outline_max_dev_mm'] = 'holes %d vs %d' % (len(poly.interiors), len(orig.interiors))
    else:
        res['outline_max_dev_mm'] = round(max(min(a.hausdorff_distance(b) for b in rings(orig)) for a in rings(poly)), 4)
    res['direction_deg'] = round(ang, 2)
    return res


def fig_templates(temps, path):
    n = len(temps)
    fig, axs = plt.subplots(1, n, figsize=(2.2 * n, 4.6))
    for ax, T in zip(axs, temps):
        for e, c in T.ents:
            xs, ys = zip(*flatten(e))
            ax.plot(xs, ys, color=ACI_RGB.get(c, 'k'), lw=0.7)
        if T.has_code:
            for a, b, c in T.code_prims(0, 1):
                ax.plot([a[0], b[0]], [a[1], b[1]], color=ACI_RGB[c], lw=0.7)
            ax.plot(*T.code_origin, 'o', ms=3, color='#d97706')
        if T.mikrosteg:
            ax.plot(*T.mikrosteg, 's', ms=5, color='red')
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title('%s\n(%s)' % (T.alias, T.kind), fontsize=7)
    fig.suptitle('Templates in their own frame (code up = +Y), shown with code "angle 0°, index 1". '
                 'Orange dot: code origin. Red square: proposed Mikrosteg.', fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    lib, name = sys.argv[1], sys.argv[2]
    out = os.path.join(ROOT, name)
    os.makedirs(out, exist_ok=True)
    d = sl.Drawing(os.path.join(lib, 'repaired_source.dxf'))
    pcs = sl.pieces(d)
    by = collections.defaultdict(list)
    for p in pcs:
        by[family(p.kind)].append(p)
    temps = []
    for kind in sorted(by):
        group = sorted(by[kind], key=lambda q: (-q.center[1], q.center[0]))
        model = next((q for q in group if q.code), group[0])
        T = build_template(model, ALIASES.get(kind, kind))
        T.source = 'piece at (%.1f, %.1f) of %s' % (model.center[0], model.center[1], os.path.basename(lib.rstrip('/\\')))
        temps.append((T, group))
    write_templates(out, [T for T, _ in temps])
    # relecture depuis le disque : la validation porte sur les gabarits ecrits
    loaded = load_templates(out)
    rows = []
    for T0, group in temps:
        T = loaded[T0.kind]
        for q in group:
            r = validate(T, q)
            rows.append(dict(type=T.kind, x_mm=round(q.center[0], 2), y_mm=round(q.center[1], 2), **r))
    keys = ['type', 'x_mm', 'y_mm', 'direction_deg', 'angle_deg', 'index', 'n_code_lines', 'code_max_dev_mm',
            'outline_diff_mm2', 'outline_max_dev_mm']
    with open(os.path.join(out, 'validation.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    fig_templates([loaded[T.kind] for T, _ in temps], os.path.join(out, 'templates.png'))
    write_readme(out, lib, name, [loaded[T.kind] for T, _ in temps], rows)
    for T, _ in temps:
        rr = [r for r in rows if r['type'] == T.kind]
        dev = max((r['code_max_dev_mm'] or 0) for r in rr)
        dif = max(r['outline_diff_mm2'] for r in rr)
        odev = max(r['outline_max_dev_mm'] for r in rr)
        print('  %-16s %-7s %2d pieces  code : ecart max %.4f mm   contour : ecart max %.4f mm, difference max %.4f mm2'
              % (T.kind, T.alias, len(rr), dev, odev, dif))
    print('Gabarits : %s' % out)


def write_readme(out, lib, name, temps, rows):
    L = ['# Specimen templates `%s`' % name, '',
         '*Generated by `cutting-sheets/scripts/make_templates.py` from the library `%s`.*'
         % os.path.basename(lib.rstrip('/\\')), '',
         'One template per specimen type, **without notch code**. The code (angle + index) is added by '
         '`make_plan.py` for each specimen ordered.', '',
         '| Type | Alias (order file) | Size (mm) | Holes | Code origin (mm) | End of the line after the code (mm) | '
         'Mikrosteg (proposed, mm) |', '|---|---|---|---|---|---|---|']
    for T in temps:
        L.append('| %s | `%s` | %.1f × %.1f | %d | %s | %s | %s |' % (
            T.kind, T.alias, T.L, T.W, T.holes, '(%.3f, %.3f)' % T.code_origin if T.has_code else 'no code',
            '%.3f' % T.tail_end_x if T.has_code else '–', '(%.1f, %.1f)' % T.mikrosteg if T.mikrosteg else '–'))
    L += ['', 'Template frame: centre of the minimum bounding rectangle at the origin, code towards +Y. The angle of a '
          'specimen is the direction of its code end, measured from the rolling direction (+Y), counter-clockwise. '
          'For `DISC2` the two holes are perpendicular to that direction (angle 90° = holes along the rolling '
          'direction).', '', '![Templates](templates.png)', '',
          '## Validation', '',
          'Every specimen of the source drawing was rebuilt from its template and the code read on it, then compared '
          'with the original.', '',
          '| Type | Specimens | Codes read (angle / index) | Code lines: max deviation (mm) | Outline: max deviation (mm) | Outline: max area difference (mm²) |',
          '|---|---|---|---|---|---|']
    for T in temps:
        rr = [r for r in rows if r['type'] == T.kind]
        codes = sorted(set('%g°/%s' % (r['angle_deg'], r['index']) for r in rr if r['angle_deg'] != ''))
        L.append('| %s | %d | %s | %s | %.4f | %.4f |' % (
            T.kind, len(rr), ', '.join(codes) or '–',
            '%.4f' % max(r['code_max_dev_mm'] for r in rr) if T.has_code else '–',
            max(r['outline_max_dev_mm'] for r in rr), max(r['outline_diff_mm2'] for r in rr)))
    L += ['', 'Details per specimen: `validation.csv`.']
    with open(os.path.join(out, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
