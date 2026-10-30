# -*- coding: utf-8 -*-
"""
make_templates.py -- Gabarits d'eprouvettes SANS code, a partir du catalogue du labo.

Lancement (depuis la racine du repo ; une fois par nouveau catalogue) :
    py cutting-sheets/scripts/make_templates.py cutting-sheets/input/specimen_templates_261029_barcoded.dxf CTLG_261029

Le catalogue a un bloc par eprouvette, nomme <famille>_<nn> (ex. CTLG_UTUT_21 : angle 2 x 15 = 30 deg, index 1).
Le type d'une eprouvette est le NOM DE SA FAMILLE (lu dans le fichier) ; le modele de chaque famille est son bloc _00.

Pour chaque type d'eprouvette :
    1. le bloc _00 sert de modele ; son code est lu (notchcode.read_piece) ;
    2. le gabarit = ses traits, SANS les 19 traits du code ni le trait Q3 qui suit le code (sa longueur depend du
       code : le code fait 12 ou 13 mm) ; on garde la position du code et le point ou ce trait se termine ;
    3. repere du gabarit : centre du rectangle englobant minimal a l'origine, code en haut (+Y) ;
       angle de l'eprouvette = direction du code depuis le sens de laminage (+Y).

Validation : CHAQUE eprouvette du catalogue est regeneree a partir du gabarit et de son code lu (angle, index),
puis comparee a l'originale : traits du code (ecart max) et contour complet ; le code lu doit aussi etre le numero
du bloc (CTLG_UTUT_21 -> angle 2 x 15 = 30 deg, index 1).

Sorties dans cutting-sheets/templates/<nom>/ : templates.dxf (un bloc T__<type> par type), templates.csv,
validation.csv, templates.png, README.md.
"""
import collections
import csv
import math
import os
import re
import sys

import ezdxf
from ezdxf import path as dpath
from ezdxf.math import Matrix44
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt          # noqa: E402
from shapely import affinity             # noqa: E402
from shapely.geometry import LineString, Polygon   # noqa: E402
from shapely.ops import polygonize, unary_union          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import notchcode as nc                   # noqa: E402
import sheetlib as sl                    # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', 'templates'))
LAYERS = {3: 'Q3_NORMAL', 4: 'Q4_MEDIUM', 5: 'Q5_HIGH'}
ACI_RGB = {3: '#16a34a', 4: '#06b6d4', 5: '#2546d6', 7: '#444444'}
# noms courts utilisables dans le fichier de commande
# catalogue du labo : famille (nom de bloc sans _nn) -> noms utilisables dans la commande (le premier est affiche)
CATALOGUE_ALIASES = {
    'CTLG_UTUT': ['UTUT', 'UT'], 'CTLG_NT20': ['NT20'], 'CTLG_NT06': ['NT06', 'NT6.67'], 'CTLG_CHCH': ['CHCH', 'CH'],
    'CTST_UTST': ['UTST'], 'CTST_SHLD': ['SHLD'], 'CTST_SHMD': ['SHMD'], 'CTST_SHHD': ['SHHD'],
    'MNAK_FULL': ['MNAK_FULL', 'DISC0'], 'MNAK_HOLE': ['MNAK_HOLE', 'DISC2'], 'TENS_FULL': ['TENS_FULL', 'STRIP']}
BLOCK_RE = re.compile(r'^(.*?)_(\d+)$')


# ============================================================
# GABARIT
# ============================================================
class Template:
    """Gabarit d'un type : entites (repere du gabarit), position du code, fin du trait qui suit le code."""

    def __init__(self, kind, alias, ents, code_origin=None, tail_end_x=None, tail_color=3,
                 L=0.0, W=0.0, holes=0, depth=nc.DEPTH, source='', aliases=None, angles=None):
        self.kind, self.alias, self.ents = kind, alias, ents         # ents : liste (entite ezdxf, couleur)
        self.aliases = aliases or [alias]                            # noms acceptes dans la commande
        self.angles = angles or []                                   # angles presents dans le catalogue (info)
        self.code_origin, self.tail_end_x, self.tail_color = code_origin, tail_end_x, tail_color
        self.L, self.W, self.holes, self.depth, self.source = L, W, holes, depth, source

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


def build_template(p, alias, kind):
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
    T = Template(kind, alias, ents, origin, tail_end[0] if tail else None, tail.color if tail else 3,
                 L=p.L, W=p.W, holes=len(p.poly.interiors), depth=code['depth_mm'] if code else nc.DEPTH)
    if code:
        T.code_origin = (round(origin[0], 4), round(origin[1], 4))
        T.tail_end_x = round(T.tail_end_x, 4)
    return T


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
FIELDS = ['type', 'alias', 'aliases', 'catalogue_angles', 'block', 'has_code', 'code_x0', 'code_y0', 'code_depth', 'tail_end_x', 'tail_color',
          'L_mm', 'W_mm', 'holes', 'source_piece']


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
        rows.append({'type': T.kind, 'alias': T.alias, 'aliases': ';'.join(T.aliases),
                     'catalogue_angles': ';'.join('%g' % a for a in T.angles),
                     'block': 'T__' + T.kind, 'has_code': int(T.has_code),
                     'code_x0': T.code_origin[0] if T.has_code else '', 'code_y0': T.code_origin[1] if T.has_code else '',
                     'code_depth': T.depth if T.has_code else '', 'tail_end_x': T.tail_end_x if T.has_code else '',
                     'tail_color': T.tail_color if T.has_code else '',
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
                         float(r['L_mm']), float(r['W_mm']), int(r['holes']),
                         float(r['code_depth']) if has else nc.DEPTH, r['source_piece'],
                         aliases=(r.get('aliases') or r['alias']).split(';'),
                         angles=[float(a) for a in (r.get('catalogue_angles') or '').split(';') if a])
            out[T.kind] = T
            out[T.kind.upper()] = T
            for a in T.aliases:
                out[a.upper()] = T
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
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title('%s\n(%s)' % (T.alias, T.kind), fontsize=6.5)
    fig.suptitle('Templates in their own frame (code up = +Y), shown with code "angle 0°, index 1". '
                 'Orange dot: code origin.', fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    lib, name = sys.argv[1], sys.argv[2]
    out = os.path.join(ROOT, name)
    os.makedirs(out, exist_ok=True)
    if not lib.lower().endswith('.dxf'):
        sys.exit('Il faut le fichier .dxf du catalogue du labo.')
    pcs = sl.pieces(sl.Drawing(lib))
    by = collections.defaultdict(list)
    for p in pcs:                              # type = nom du bloc (famille), numero = code attendu
        src = collections.Counter(s.source for s in p.segs).most_common(1)[0][0]
        m = BLOCK_RE.match(src)
        p.block, p.block_num = src, (int(m.group(2)) if m else None)
        by[m.group(1) if m else src].append(p)
    temps = []
    for kind in sorted(by):
        group = sorted(by[kind], key=lambda q: (q.block_num is None, q.block_num))
        model = group[0]                       # bloc _00 (angle 0, index 0)
        al = CATALOGUE_ALIASES.get(kind) or [kind.split('_', 1)[1] if '_' in kind else kind]
        T = build_template(model, al[0], kind)
        T.aliases = al
        T.source = 'block %s of %s' % (model.block, os.path.basename(lib))
        codes = [nc.read_piece(q) for q in group if q.code]
        T.angles = sorted(set(c['angle_deg'] for c in codes))
        temps.append((T, group))
    write_templates(out, [T for T, _ in temps])
    # relecture depuis le disque : la validation porte sur les gabarits ecrits
    loaded = load_templates(out)
    rows = []
    for T0, group in temps:
        T = loaded[T0.kind]
        for q in group:
            r = validate(T, q)
            if q.block_num is not None and r['angle_deg'] != '':
                r['code_is_block_number'] = 'yes' if (int(r['angle_deg'] // 15), r['index']) == divmod(q.block_num, 10) else 'NO'
            rows.append(dict(type=T.kind, block=q.block, x_mm=round(q.center[0], 2), y_mm=round(q.center[1], 2), **r))
    keys = ['type', 'block', 'x_mm', 'y_mm', 'direction_deg', 'angle_deg', 'index', 'code_is_block_number',
            'n_code_lines', 'code_max_dev_mm', 'outline_diff_mm2', 'outline_max_dev_mm']
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
        nb = sum(1 for r in rr if r.get('code_is_block_number') == 'yes')
        print('  %-11s %-9s %3d pieces  code : ecart max %.4f mm%s   contour : ecart max %.4f mm, difference max %.4f mm2'
              % (T.kind, T.alias, len(rr), dev, '  (= no de bloc : %d/%d)' % (nb, len(rr)),
                 odev, dif))
    print('Gabarits : %s' % out)


def write_readme(out, lib, name, temps, rows):
    catalogue = True
    L = ['# Specimen templates `%s`' % name, '',
         '*Generated by `cutting-sheets/scripts/make_templates.py` from %s `%s`.*'
         % ('the lab catalogue' if catalogue else 'the library', os.path.basename(lib.rstrip('/\\'))), '',
         'One template per specimen type, **without notch code**. The code (angle + index) is added by '
         '`make_plan.py` for each specimen ordered.%s' % (
             ' Types are the block families of the catalogue (block name without its number); the model of each '
             'type is its block `_00`.' if catalogue else ''), '',
         '| Type | Names in the order file | Size (mm) | Holes | Angles in the source | Code origin (mm) |',
         '|---|---|---|---|---|---|']
    for T in temps:
        L.append('| %s | %s | %.1f × %.1f | %d | %s | %s |' % (
            T.kind, ', '.join('`%s`' % a for a in T.aliases), T.L, T.W, T.holes,
            ', '.join('%g°' % a for a in T.angles) or '–',
            '(%.3f, %.3f)' % T.code_origin if T.has_code else 'no code'))
    L += ['', 'Template frame: centre of the minimum bounding rectangle at the origin, code towards +Y. The angle of a '
          'specimen is the direction of its code end, measured from the rolling direction (+Y), counter-clockwise. '
          'For discs with two holes, the holes are perpendicular to that direction (angle 90° = holes along the '
          'rolling direction).', '', '![Templates](templates.png)', '',
          '## Validation', '',
          'Every specimen of the source was rebuilt from its template and the code read on it, then compared with the '
          'original.%s' % (' For the catalogue, the code read must also be the block number (block `_21` = angle '
                           '2 × 15° = 30°, index 1).' if catalogue else ''), '',
          '| Type | Specimens | Indices | Code = block number | Code lines: max deviation (mm) | '
          'Outline: max deviation (mm) |', '|---|---|---|---|---|---|']
    for T in temps:
        rr = [r for r in rows if r['type'] == T.kind]
        idx = sorted(set(r['index'] for r in rr if r['index'] != ''))
        nb = sum(1 for r in rr if r.get('code_is_block_number') == 'yes')
        L.append('| %s | %d | %s | %s | %s | %.4f |' % (
            T.kind, len(rr), '%d–%d' % (idx[0], idx[-1]) if idx else '–',
            ('%d / %d' % (nb, len(rr))) if catalogue and T.has_code else '–',
            '%.4f' % max(r['code_max_dev_mm'] for r in rr) if T.has_code else '–',
            max(r['outline_max_dev_mm'] for r in rr)))
    L += ['', 'Details per specimen: `validation.csv`.']
    with open(os.path.join(out, 'README.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
