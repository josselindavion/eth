# -*- coding: utf-8 -*-
"""
sheetlib.py -- Lecture d'un plan de decoupe EDM (DXF) : traits, toles, pieces, codes, types d'eprouvettes.

Module commun a check_sheet.py (verification) et extract_library.py (bibliotheque d'eprouvettes).

Conventions des plans du labo (voir README.md) :
    - unites : mm ;
    - cadre de tole : rectangle de couleur 7 (blanc/noir) ;
    - traits de coupe : couleur = qualite EDM, 3 = Q3 normale (vert), 4 = Q4 moyenne (cyan), 5 = Q5 maximale (bleu) ;
    - sens de laminage (RD) : axe +Y du dessin ;
    - code d'identification : "peigne" d'encoches bleues (Q5) dans le bord d'une tete, ~13 x 3 mm.

Dependances : ezdxf, shapely (pip install ezdxf shapely).
"""
import collections
import math

import ezdxf
from ezdxf import path as dpath
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

SNAP = 3                 # arrondi des coordonnees (1e-3 mm)
JOIN_TOL = 0.005         # mm : deux extremites plus proches que ca sont le meme point (fusionnees a la lecture)
FLAT_TOL = 0.01          # tolerance de discretisation des arcs (mm)
FRAME_MIN_AREA = 1e4     # un cadre de tole fait au moins 100 x 100 mm
PIECE_MIN_AREA = 300.0   # mm2 : en dessous, contour interieur (trou) ou debris
CODE_SEG_MAX = 3.2       # mm : longueur max d'un trait du code a encoches
CODE_MIN_SEGS = 8        # nombre min de petits traits bleus pour reconnaitre un code
QUALITY = {3: 'Q3 normal', 4: 'Q4 medium', 5: 'Q5 highest'}
CUT_COLORS = (3, 4, 5)


# ============================================================
# LECTURE
# ============================================================
class Seg:
    """Un trait du dessin (entite DXF a plat, coordonnees du dessin)."""
    __slots__ = ('i', 'kind', 'layer', 'color', 'raw_color', 'pts', 'line', 'length', 'radius', 'center',
                 'entity', 'source')

    def __init__(self, i, e, color, pts, source):
        self.i = i
        self.kind = e.dxftype()
        self.layer = e.dxf.layer
        self.color = color
        self.raw_color = e.dxf.get('color', 256)
        self.pts = pts
        self.line = LineString(pts)
        self.length = self.line.length
        self.radius = e.dxf.radius if self.kind in ('ARC', 'CIRCLE') else None
        self.center = (e.dxf.center.x, e.dxf.center.y) if self.kind in ('ARC', 'CIRCLE') else None
        self.entity = e          # entite virtuelle (deja dans le repere du dessin) : sert a recopier la geometrie exacte
        self.source = source     # nom du bloc d'origine (ou 'modelspace')

    @property
    def closed(self):
        return self.kind == 'CIRCLE' or (len(self.pts) > 2 and self.pts[0] == self.pts[-1])

    def ends(self):
        return self.pts[0], self.pts[-1]


def _flat(e, source='modelspace'):
    """Entites a plat : les INSERT (blocs, y compris imbriques) sont eclates."""
    if e.dxftype() == 'INSERT':
        for v in e.virtual_entities():
            yield from _flat(v, e.dxf.name if source == 'modelspace' else source)
    else:
        yield e, source


def resolve_color(doc, e):
    """Couleur ACI effective : 256 (DUCALQUE) -> couleur du calque ; 0 (DUBLOC) -> couleur du calque (approximation)."""
    c = e.dxf.get('color', 256)
    if c in (0, 256):
        lay = doc.layers.get(e.dxf.layer)
        c = lay.dxf.color if lay is not None else 7
    return abs(c)


class Drawing:
    """Contenu d'un DXF : traits, textes, en-tete."""

    def __init__(self, path):
        self.path = path
        self.doc = ezdxf.readfile(path)
        self.units = self.doc.header.get('$INSUNITS', 0)
        self.segs, self.texts, self.skipped = [], [], collections.Counter()
        self._grid = collections.defaultdict(list)
        for e0 in self.doc.modelspace():
            for e, src in _flat(e0):
                t = e.dxftype()
                if t in ('TEXT', 'MTEXT'):
                    txt = e.dxf.text if t == 'TEXT' else e.plain_text()
                    self.texts.append((Point(e.dxf.insert.x, e.dxf.insert.y), txt.strip()))
                    continue
                try:
                    p = dpath.make_path(e)
                    pts = [(round(v.x, SNAP), round(v.y, SNAP)) for v in p.flattening(FLAT_TOL)]
                except Exception:
                    self.skipped[t] += 1
                    continue
                pts[0], pts[-1] = self._vertex(pts[0]), self._vertex(pts[-1])
                pts = [q for k, q in enumerate(pts) if k == 0 or q != pts[k - 1]]
                if len(pts) < 2:
                    self.skipped[t] += 1
                    continue
                self.segs.append(Seg(len(self.segs), e, resolve_color(self.doc, e), pts, src))

    def _vertex(self, p):
        """Fusionne les extremites a moins de JOIN_TOL : renvoie le premier sommet deja vu dans ce rayon."""
        gx, gy = int(math.floor(p[0] / 0.01)), int(math.floor(p[1] / 0.01))
        for i in (gx - 1, gx, gx + 1):
            for j in (gy - 1, gy, gy + 1):
                for q in self._grid[(i, j)]:
                    if abs(q[0] - p[0]) <= JOIN_TOL and abs(q[1] - p[1]) <= JOIN_TOL:
                        return q
        self._grid[(gx, gy)].append(p)
        return p

    @property
    def cut(self):
        return [s for s in self.segs if s.color != 7]

    @property
    def black(self):
        return [s for s in self.segs if s.color == 7]


# ============================================================
# TOLES, EXTREMITES LIBRES, DOUBLONS
# ============================================================
def frames(drawing):
    """Cadres de tole (rectangles de couleur 7), tries de gauche a droite puis de haut en bas."""
    polys = [p for p in polygonize(unary_union([s.line for s in drawing.black])) if p.area > FRAME_MIN_AREA]
    return sorted(polys, key=lambda p: (round(p.bounds[0] / 50), -round(p.bounds[3] / 50)))


def open_ends(segs):
    """Extremites libres : points touches par un nombre impair d'extremites de traits (contour non ferme)."""
    c = collections.Counter()
    for s in segs:
        if not s.closed:
            a, b = s.ends()
            c[a] += 1
            c[b] += 1
    return [p for p, n in c.items() if n % 2]


def pair_open_ends(ends):
    """Regroupe les extremites libres deux a deux (plus proches voisines) : chaque paire = un trou dans un contour."""
    left, pairs = list(ends), []
    while len(left) > 1:
        a = left.pop(0)
        j = min(range(len(left)), key=lambda k: math.dist(a, left[k]))
        b = left.pop(j)
        pairs.append((a, b, math.dist(a, b)))
    return pairs, left


def components(segs):
    """Composantes connexes des traits (deux traits sont relies s'ils partagent une extremite)."""
    parent = list(range(len(segs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    at = collections.defaultdict(list)
    for k, s in enumerate(segs):
        for p in s.ends():
            at[p].append(k)
    for ks in at.values():
        for k in ks[1:]:
            parent[find(k)] = find(ks[0])
    comp = collections.defaultdict(list)
    for k in range(len(segs)):
        comp[find(k)].append(segs[k])
    return list(comp.values())


def seg_key(s):
    a, b = sorted(s.ends())
    mid = s.line.interpolate(0.5, normalized=True)
    return (s.kind, a, b, round(mid.x, 2), round(mid.y, 2))


def duplicates(segs):
    """Traits dessines plusieurs fois (memes extremites, meme milieu). Retourne les doublons (pas le premier)."""
    seen, dup = {}, []
    for s in segs:
        k = seg_key(s)
        if k in seen:
            dup.append((s, seen[k]))
        else:
            seen[k] = s
    return dup


# ============================================================
# PIECES
# ============================================================
class Piece:
    """Une eprouvette : contour exterieur ferme (Polygon avec trous) et ses traits."""

    def __init__(self, k, poly, segs):
        self.k = k
        self.poly = poly
        self.segs = segs
        self.sheet = None
        self.code = code_info(self)
        self.axis_deg, self.L, self.W = axis_angle(self)
        self.kind, self.features = classify(self)

    @property
    def center(self):
        """Centre du rectangle englobant minimal (insensible aux encoches du code, contrairement au centroide)."""
        c = self.poly.minimum_rotated_rectangle.centroid
        return c.x, c.y

    def colors(self):
        return collections.Counter(s.color for s in self.segs)


def pieces(drawing, segs=None):
    """Pieces = polygones fermes formes par les traits de coupe ; les contours inclus dans un autre sont des trous."""
    segs = drawing.cut if segs is None else segs
    polys = sorted(polygonize(unary_union([s.line for s in segs])), key=lambda p: -p.area)
    outer = []
    for p in polys:
        if p.area < 1e-6:
            continue
        host = next((o for o in outer if o.buffer(0.01).contains(p)), None)
        if host is None:
            if p.area >= PIECE_MIN_AREA:
                outer.append(p)
    tree = STRtree([s.line for s in segs])
    res = []
    for k, p in enumerate(outer):
        zone = Polygon(p.exterior).buffer(0.02)
        mine = [segs[i] for i in tree.query(zone, predicate='contains')]
        # trous : contours fermes a l'interieur du contour exterieur
        holes = [q for q in polys if q.area < p.area and Polygon(p.exterior).contains(q.representative_point())
                 and not any(o is q for o in outer) and q.area < 0.5 * p.area]
        holes = [h for h in holes if not any(h2 is not h and h2.contains(h.representative_point()) and h2.area > h.area
                                             for h2 in holes)]
        poly = Polygon(p.exterior, [h.exterior for h in holes]) if holes else Polygon(p.exterior)
        res.append(Piece(k, poly, mine))
    return res


def assign_sheets(pcs, frs):
    for p in pcs:
        hit = [i for i, f in enumerate(frs) if f.contains(p.poly.representative_point())]
        p.sheet = hit[0] + 1 if hit else 0


# ============================================================
# CODE A ENCOCHES
# ============================================================
def code_info(piece):
    """Code d'identification : petits traits Q5 droits sur le bord. Retourne None ou un dict (centre, signature)."""
    cs = [s for s in piece.segs if s.color == 5 and s.kind == 'LINE' and s.length <= CODE_SEG_MAX
          and piece_boundary(piece).distance(s.line) < 0.01]
    if len(cs) < CODE_MIN_SEGS:
        return None
    g = unary_union([s.line for s in cs])
    # garde le plus gros amas (le code), au cas ou d'autres petits traits bleus existent
    c = g.centroid
    return {'segs': cs, 'center': (c.x, c.y), 'bounds': g.bounds, 'geom': g}


def piece_boundary(piece):
    return piece.poly.exterior if hasattr(piece, 'poly') else None


def code_signature(piece, step=0.05):
    """Signature du code, independante de la piece : traits du code tournes pour que l'axe de la piece (vers le
    code) soit +Y, puis exprimes par rapport au coin du rectangle englobant du code, arrondis a 0,05 mm."""
    if not piece.code:
        return None
    g = affinity.rotate(piece.code['geom'], -(piece.axis_deg or 0.0), origin=(0, 0))
    x0, y0 = g.bounds[0], g.bounds[1]
    segs = []
    for ln in getattr(g, 'geoms', [g]):
        segs.append(tuple(sorted((round((x - x0) / step) * step, round((y - y0) / step) * step) for x, y in ln.coords)))
    return hash(tuple(sorted(segs))) & 0xFFFFFFFF


# ============================================================
# ORIENTATION ET TYPE
# ============================================================
def axis_angle(piece):
    """Angle (degres, sens trigonometrique, depuis +Y = sens de laminage) de l'axe long de la piece, oriente vers
    la tete qui porte le code ; plus longueur et largeur du rectangle englobant minimal."""
    r = piece.poly.minimum_rotated_rectangle
    xs = list(r.exterior.coords)
    e1 = (xs[1][0] - xs[0][0], xs[1][1] - xs[0][1])
    e2 = (xs[2][0] - xs[1][0], xs[2][1] - xs[1][1])
    l1, l2 = math.hypot(*e1), math.hypot(*e2)
    L, W = max(l1, l2), min(l1, l2)
    if L / W < 1.25:                               # disque ou piece presque carree : pas d'axe long
        if piece.code:                             # axe = du centre vers le code
            cx, cy = piece.poly.centroid.x, piece.poly.centroid.y
            dx, dy = piece.code['center'][0] - cx, piece.code['center'][1] - cy
            return _deg(-dx, dy), L, W
        return 0.0, L, W
    ux, uy = (e1 if l1 >= l2 else e2)
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    if piece.code:
        cx, cy = piece.poly.centroid.x, piece.poly.centroid.y
        if (piece.code['center'][0] - cx) * ux + (piece.code['center'][1] - cy) * uy < 0:
            ux, uy = -ux, -uy
    return _deg(-ux, uy), L, W


def _deg(sx, cy):
    """Angle de la direction (-sx, cy) mesure depuis +Y, sens trigonometrique, dans ]-180, 180]."""
    a = math.degrees(math.atan2(sx, cy))
    return 180.0 if abs(a + 180.0) < 1e-9 else a


def fold_rd(angle):
    """Orientation par rapport au laminage pour un materiau orthotrope : |angle| ramene dans [0, 90]."""
    a = abs(angle) % 180.0
    return min(a, 180.0 - a)


def pose_angle(piece):
    """Rotation qui ramene la piece dans son repere canonique : axe vers le code = +Y pour les barreaux ; aucune
    pour les disques (leur orientation par rapport au laminage est donnee par les trous, on la conserve)."""
    return 0.0 if piece.L / piece.W < 1.25 else piece.axis_deg


def canonical(piece, geom):
    """Geometrie exprimee dans le repere canonique de la piece (centre a l'origine, voir pose_angle)."""
    cx, cy = piece.center
    g = affinity.translate(geom, -cx, -cy)
    return affinity.rotate(g, -pose_angle(piece), origin=(0, 0))


def classify(piece):
    """Type d'eprouvette d'apres la geometrie (noms provisoires, a confirmer avec le labo)."""
    L, W = piece.L, piece.W
    f = {'L': round(L, 1), 'W': round(W, 1), 'holes': len(piece.poly.interiors),
         'colors': dict(sorted(piece.colors().items()))}
    tag = 'L%.0f' % L
    if L / W < 1.25:
        if f['holes'] == 2:
            h0, h1 = [Polygon(h).centroid for h in piece.poly.interiors]
            ab = fold_rd(_deg(-(h1.x - h0.x), h1.y - h0.y))       # axe des deux trous par rapport au laminage
            f['holes_rd'] = round(ab, 1)
            return 'DISC_2H_%02d' % (int(round(ab / 15.0)) * 15), f
        return 'DISC_%dH' % f['holes'], f
    cols = piece.colors()
    code_ids = set(id(s) for s in piece.code['segs']) if piece.code else set()
    q5_other = [s for s in piece.segs if s.color == 5 and id(s) not in code_ids]
    if not cols.get(4) and not q5_other:
        # pas de zone utile decoupee en Q4/Q5 : bande ou ebauche (le code eventuel ne compte pas)
        return ('BLANK_%.0fx%.0f' if piece.code else 'STRIP_%.0fx%.0f') % (L, W), f
    if f['holes'] >= 1:
        d = 2 * math.sqrt(Polygon(piece.poly.interiors[0]).area / math.pi)
        f['hole_d'] = round(d, 2)
        return 'CH_D%.1f_%s' % (d, tag), f
    # entailles : arcs Q5 dont le centre est pres du milieu de la piece (le long de l'axe)
    notch = []
    for s in piece.segs:
        if s.kind == 'ARC' and s.color == 5 and s.radius > 1.0:
            c = canonical(piece, Point(s.center))
            if abs(c.y) < 6.0:
                notch.append(round(s.radius, 2))
    if notch:
        r = max(set(notch), key=notch.count)
        f['notch_R'] = r
        return 'NT_R%.2f_%s' % (r, tag), f
    return 'UT_%s' % tag, f


# ============================================================
# PETITS OUTILS
# ============================================================
def unit_name(code):
    return {0: 'unitless (not set)', 1: 'inches', 2: 'feet', 4: 'millimetres', 5: 'centimetres', 6: 'metres'}.get(code, str(code))
