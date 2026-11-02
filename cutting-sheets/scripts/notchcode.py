# -*- coding: utf-8 -*-
"""
notchcode.py -- Notch identification code of the specimens: writing and reading.

"Interleaved 2 of 5" barcode (lab document "Specimen ID", confirmed on all drawings):
    - 9 visible elements, left to right (code on top): E1 P1 E2 P2 E3 P3 E4 P4 E5;
      E = notch (3 mm deep), P = land (material); the 5th land P5 is implicit (edge of the head);
    - element width: 1 mm (narrow) or 2 mm (wide); in each group of 5, exactly 2 are wide;
    - digit = sum of the weights 1-2-4-7-0 of the 2 wide elements (4 + 7 = 11 -> 0);
    - notches E1..E5 -> INDEX of the specimen; lands P1..P5 -> ANGLE digit, angle = digit x 15 deg.

Local frame of the code: u along the edge (left -> right, code on top), v outwards from the piece;
origin = top-left corner of the first notch E1 (the edge of the piece is the line v = 0).
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
    """Angle digit (0-9) for an angle to the rolling direction; None if the angle cannot be coded."""
    k = angle_deg / ANGLE_STEP
    if abs(k - round(k)) > 1e-6 or not 0 <= round(k) <= 9:
        return None
    return int(round(k))


def elements(a_digit, index):
    """The 9 visible elements: list of ('E' | 'P', width), left to right."""
    n, p = PATTERNS[index], PATTERNS[a_digit]
    out = []
    for k in range(5):
        out.append(('E', n[k]))
        if k < 4:
            out.append(('P', p[k]))
    return out


def code_lines(a_digit, index, depth=DEPTH):
    """Lines of the code in the local frame: list of ((u0, v0), (u1, v1)), and length of the code (end u)."""
    lines, u = [], 0.0
    for kind, w in elements(a_digit, index):
        if kind == 'E':
            lines += [((u, 0.0), (u, -depth)), ((u, -depth), (u + w, -depth)), ((u + w, -depth), (u + w, 0.0))]
        else:
            lines.append(((u, 0.0), (u + w, 0.0)))
        u += w
    return lines, u


# ============================================================
# READING (from the lines of a piece)
# ============================================================
def frame(code_pts, tangent_vecs, piece_center):
    """Local frame of the code from its lines.

    code_pts: points of the code lines; tangent_vecs: vectors (dx, dy) of all the code lines;
    piece_center: centre of the piece (only used to know which side is outside).
    Returns (origin (x, y), t (unit vector u), n (unit vector v, outwards)).
    """
    cx = sum(p[0] for p in code_pts) / len(code_pts)
    cy = sum(p[1] for p in code_pts) / len(code_pts)
    nx, ny = cx - piece_center[0], cy - piece_center[1]
    r = math.hypot(nx, ny)
    nx, ny = nx / r, ny / r
    tx0, ty0 = ny, -nx                                     # n turned by -90 deg: u goes left to right
    sx = sy = 0.0
    for dx, dy in tangent_vecs:
        L = math.hypot(dx, dy)
        if L == 0 or abs(dx * nx + dy * ny) > 0.5 * L:      # line perpendicular to the edge: ignored
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
    """Reads a code from its lines in the local frame. Returns a dict, or raises ValueError.

    The notch bottoms are the lines parallel to the edge at v < -1 mm; the lands are the intervals between two
    successive notches; the 5th (implicit) land is wide if only one of the 4 visible lands is wide.
    """
    bottoms = []
    for (u0, v0), (u1, v1) in lines_local:
        if abs(v0 - v1) < 0.01 and v0 < -1.0:
            bottoms.append((min(u0, u1), max(u0, u1), v0))
    bottoms.sort()
    if len(bottoms) != 5:
        raise ValueError('%d notch bottoms instead of 5' % len(bottoms))
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
                raise ValueError('width %.3f mm neither narrow nor wide' % w)
        return out
    nf, pf = classify(notch_w), classify(land_w)
    if sum(nf) != 2:
        raise ValueError('%d wide notches instead of 2' % sum(nf))
    if sum(pf) not in (1, 2):
        raise ValueError('%d wide visible lands (1 or 2 expected)' % sum(pf))
    pf.append(sum(pf) == 1)                                  # implicit P5
    a = _digit_of(pf)
    return {'index': _digit_of(nf), 'angle_digit': a, 'angle_deg': a * ANGLE_STEP,
            'notch_mm': [round(w, 3) for w in notch_w], 'land_mm': [round(w, 3) for w in land_w],
            'depth_mm': round(-sum(b[2] for b in bottoms) / 5, 3), 'length_mm': round(bottoms[-1][1] - bottoms[0][0], 3)}


def read_piece(piece):
    """Reads the code of a sheetlib piece (None if no code). Adds the direction of the code (deg from +Y,
    counter-clockwise, from the piece to the code) and the local frame."""
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
