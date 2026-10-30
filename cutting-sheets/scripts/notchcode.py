# -*- coding: utf-8 -*-
"""
notchcode.py -- Code d'identification a encoches des eprouvettes : codage et lecture.

Code-barres "Interleaved 2 of 5" (document du labo "Specimen ID", confirme sur tous les plans) :
    - 9 elements visibles, de gauche a droite (code en haut) : E1 P1 E2 P2 E3 P3 E4 P4 E5 ;
      E = encoche (3 mm de profondeur), P = plein (matiere) ; le 5e plein P5 est implicite (bord de la tete) ;
    - largeur d'un element : 1 mm (etroit) ou 2 mm (large) ; dans chaque groupe de 5, exactement 2 larges ;
    - chiffre = somme des poids 1-2-4-7-0 des 2 elements larges (4 + 7 = 11 -> 0) ;
    - encoches E1..E5 -> INDEX de l'eprouvette ; pleins P1..P5 -> chiffre d'ANGLE, angle = chiffre x 15 deg.

Repere local du code : u le long du bord (gauche -> droite, code en haut), v vers l'exterieur de la piece ;
origine = coin haut-gauche de la premiere encoche E1 (le bord de la piece est la droite v = 0).
"""
import math

WEIGHTS = (1, 2, 4, 7, 0)
NARROW, WIDE = 1.0, 2.0
DEPTH = 3.0
ANGLE_STEP = 15.0


def _digit_of(wide_flags):
    v = sum(w for w, f in zip(WEIGHTS, wide_flags) if f)
    return 0 if v == 11 else v


PATTERNS = {}
for _i in range(5):
    for _j in range(_i + 1, 5):
        _f = [k in (_i, _j) for k in range(5)]
        PATTERNS[_digit_of(_f)] = tuple(WIDE if x else NARROW for x in _f)
assert sorted(PATTERNS) == list(range(10))


def angle_digit(angle_deg):
    """Chiffre d'angle (0-9) pour un angle au laminage ; None si l'angle n'est pas codable."""
    k = angle_deg / ANGLE_STEP
    if abs(k - round(k)) > 1e-6 or not 0 <= round(k) <= 9:
        return None
    return int(round(k))


def elements(a_digit, index):
    """Les 9 elements visibles : liste de ('E' | 'P', largeur), de gauche a droite."""
    n, p = PATTERNS[index], PATTERNS[a_digit]
    out = []
    for k in range(5):
        out.append(('E', n[k]))
        if k < 4:
            out.append(('P', p[k]))
    return out


def code_lines(a_digit, index, depth=DEPTH):
    """Traits du code dans le repere local : liste de ((u0, v0), (u1, v1)), et longueur du code (u de fin)."""
    lines, u = [], 0.0
    for kind, w in elements(a_digit, index):
        if kind == 'E':
            lines += [((u, 0.0), (u, -depth)), ((u, -depth), (u + w, -depth)), ((u + w, -depth), (u + w, 0.0))]
        else:
            lines.append(((u, 0.0), (u + w, 0.0)))
        u += w
    return lines, u


# ============================================================
# LECTURE (a partir des traits d'une piece)
# ============================================================
def frame(code_pts, tangent_vecs, piece_center):
    """Repere local du code a partir de ses traits.

    code_pts : points des traits du code ; tangent_vecs : vecteurs (dx, dy) de tous les traits du code ;
    piece_center : centre de la piece (sert seulement a savoir de quel cote est l'exterieur).
    Retourne (origine (x, y), t (vecteur unitaire u), n (vecteur unitaire v, vers l'exterieur)).
    """
    cx = sum(p[0] for p in code_pts) / len(code_pts)
    cy = sum(p[1] for p in code_pts) / len(code_pts)
    nx, ny = cx - piece_center[0], cy - piece_center[1]
    r = math.hypot(nx, ny)
    nx, ny = nx / r, ny / r
    tx0, ty0 = ny, -nx                                     # n tourne de -90 deg : u va de gauche a droite
    sx = sy = 0.0
    for dx, dy in tangent_vecs:
        L = math.hypot(dx, dy)
        if L == 0 or abs(dx * nx + dy * ny) > 0.5 * L:      # trait perpendiculaire au bord : ignore
            continue
        if dx * tx0 + dy * ty0 < 0:
            dx, dy = -dx, -dy
        sx, sy = sx + dx, sy + dy
    L = math.hypot(sx, sy)
    tx, ty = sx / L, sy / L
    nx, ny = -ty, tx
    u0 = min(p[0] * tx + p[1] * ty for p in code_pts)
    v0 = max(p[0] * nx + p[1] * ny for p in code_pts)
    return (u0 * tx + v0 * nx, u0 * ty + v0 * ny), (tx, ty), (nx, ny)


def to_local(p, origin, t, n):
    dx, dy = p[0] - origin[0], p[1] - origin[1]
    return dx * t[0] + dy * t[1], dx * n[0] + dy * n[1]


def to_global(q, origin, t, n):
    return origin[0] + q[0] * t[0] + q[1] * n[0], origin[1] + q[0] * t[1] + q[1] * n[1]


def read(lines_local, tol=0.05):
    """Lit un code a partir de ses traits en repere local. Retourne un dict, ou leve ValueError.

    Les fonds d'encoche sont les traits paralleles au bord a v < -1 mm ; les pleins sont les intervalles entre deux
    encoches successives ; le 5e plein (implicite) est large si un seul des 4 pleins visibles est large.
    """
    bottoms = []
    for (u0, v0), (u1, v1) in lines_local:
        if abs(v0 - v1) < 0.01 and v0 < -1.0:
            bottoms.append((min(u0, u1), max(u0, u1), v0))
    bottoms.sort()
    if len(bottoms) != 5:
        raise ValueError('%d fonds d\'encoche au lieu de 5' % len(bottoms))
    notch_w = [b - a for a, b, _ in bottoms]
    land_w = [bottoms[k + 1][0] - bottoms[k][1] for k in range(4)]

    def classify(ws):
        out = []
        for w in ws:
            if abs(w - NARROW) <= tol:
                out.append(False)
            elif abs(w - WIDE) <= tol:
                out.append(True)
            else:
                raise ValueError('largeur %.3f mm ni etroite ni large' % w)
        return out
    nf, pf = classify(notch_w), classify(land_w)
    if sum(nf) != 2:
        raise ValueError('%d encoches larges au lieu de 2' % sum(nf))
    if sum(pf) not in (1, 2):
        raise ValueError('%d pleins larges visibles (1 ou 2 attendus)' % sum(pf))
    pf.append(sum(pf) == 1)                                  # P5 implicite
    a = _digit_of(pf)
    return {'index': _digit_of(nf), 'angle_digit': a, 'angle_deg': a * ANGLE_STEP,
            'notch_mm': [round(w, 3) for w in notch_w], 'land_mm': [round(w, 3) for w in land_w],
            'depth_mm': round(-sum(b[2] for b in bottoms) / 5, 3), 'length_mm': round(bottoms[-1][1] - bottoms[0][0], 3)}


def read_piece(piece):
    """Lit le code d'une piece sheetlib (None si pas de code). Ajoute la direction du code (deg depuis +Y, sens
    trigonometrique, de la piece vers le code) et le repere local."""
    if not piece.code:
        return None
    segs = piece.code['segs']
    pts = [p for s in segs for p in (s.pts[0], s.pts[-1])]
    vecs = [(s.pts[-1][0] - s.pts[0][0], s.pts[-1][1] - s.pts[0][1]) for s in segs]
    origin, t, n = frame(pts, vecs, piece.center)
    loc = [(to_local(s.pts[0], origin, t, n), to_local(s.pts[-1], origin, t, n)) for s in segs]
    r = read(loc)
    r['direction_deg'] = math.degrees(math.atan2(-n[0], n[1]))
    r['frame'] = (origin, t, n)
    return r
