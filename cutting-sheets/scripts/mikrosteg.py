# -*- coding: utf-8 -*-
"""
mikrosteg.py -- Internal micro-joints (Mikrosteg): half-circle recesses in the outline of the specimens.

Principle (user's sketch, 03/11/2026): at each Mikrosteg the outline makes a small half-circle recess into the
specimen; the wire is stopped at the bottom of the recess (set by the workshop, from the notice), so that the rest of the
joint stays inside the recess after breaking, never beyond the specimen edge. The DXF only gets the recesses (part of
the closed contour, really cut); the Mikrosteg positions are shown on the notice.

Positions: 2 per specimen, validated type by type by the user (journal 2026-11-03, section 4), at opposite places, in
the clamping zones, as far as possible from the test zone. Coordinates in the template frame (centre at the origin,
coded end towards +Y); each point is projected onto the nearest outline element.
"""
import math

from shapely.geometry import LineString, Point

R = 1.0     # radius of the recess (mm), validated 03/11/2026

_LONG = [(0.0, -52.94), (10.0, 49.6)]       # 106 mm specimens: bottom end face centre; top grip, right side
_SHORT = [(0.0, -40.39), (10.0, 37.0)]      # 81 mm specimens: same places
_C30 = (30.0 * math.cos(math.radians(30)), 30.0 * math.sin(math.radians(30)))
POSITIONS = {
    'CTLG_UTUT': _LONG, 'CTLG_NT20': _LONG, 'CTLG_NT06': _LONG, 'CTLG_CHCH': _LONG,
    'CTST_UTST': _SHORT, 'CTST_SHLD': _SHORT, 'CTST_SHMD': _SHORT, 'CTST_SHHD': _SHORT,
    'MNAK_HOLE': [_C30, (-_C30[0], -_C30[1])], 'MNAK_FULL': [_C30, (-_C30[0], -_C30[1])],   # rim at 30 and 210 deg
    'MNAK_RECT_HOLE': [(-14.0, -40.0), (14.0, 40.0)], 'MNAK_RECT_FULL': [(-14.0, -40.0), (14.0, 40.0)],
    'TENS_FULL': [(0.0, -70.0), (0.0, 70.0)],
}


# ------------------------------------------------------------
# primitives: ('L', (x0, y0), (x1, y1), colour) | ('A', (cx, cy), r, a0_deg, a1_deg, colour) (counter-clockwise)
#             | ('C', (cx, cy), r, colour)
# ------------------------------------------------------------
def from_entity(e, c):
    t = e.dxftype()
    if t == 'LINE':
        return ('L', (e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y), c)
    if t == 'ARC':
        return ('A', (e.dxf.center.x, e.dxf.center.y), e.dxf.radius, e.dxf.start_angle % 360.0, e.dxf.end_angle % 360.0,
                c)
    if t == 'CIRCLE':
        return ('C', (e.dxf.center.x, e.dxf.center.y), e.dxf.radius, c)
    raise ValueError('unsupported entity in a template: %s' % t)


def _span(a0, a1):
    return (a1 - a0) % 360.0 or 360.0


def points(p, step=0.05):
    """Polyline of a primitive (for polygons and distances)."""
    if p[0] == 'L':
        return [p[1], p[2]]
    if p[0] == 'C':
        (cx, cy), r = p[1], p[2]
        n = max(16, int(2 * math.pi * r / step))
        return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]
    (cx, cy), r, a0, a1 = p[1], p[2], p[3], p[4]
    sp = _span(a0, a1)
    n = max(2, int(math.radians(sp) * r / step))
    return [(cx + r * math.cos(math.radians(a0 + sp * k / n)), cy + r * math.sin(math.radians(a0 + sp * k / n)))
            for k in range(n + 1)]


def polygon(prims):
    """Specimen polygon (outline with its holes) from closed chains of primitives."""
    from make_templates import polygon_from_lines
    return polygon_from_lines([points(p) for p in prims])


def _recess_arc(P, A, B, inward, colour):
    """Arc of radius R centred at P, from A to B, passing through P + R * inward."""
    aa = math.degrees(math.atan2(A[1] - P[1], A[0] - P[0])) % 360.0
    ab = math.degrees(math.atan2(B[1] - P[1], B[0] - P[0])) % 360.0
    am = math.degrees(math.atan2(inward[1], inward[0])) % 360.0
    if (am - aa) % 360.0 <= _span(aa, ab):                  # counter-clockwise from A to B goes through the inside
        return ('A', P, R, aa, ab, colour)
    return ('A', P, R, ab, aa, colour)


def add_recesses(prims, kind):
    """Primitives of one specimen (template + code) with the recesses of its type. The outline element nearest to each
    position is cut by a circle of radius R around the projected point, and the half-circle inside the specimen is
    added. Raises ValueError if a position is not on the outline or too close to its end."""
    pos = POSITIONS.get(kind, [])
    if not pos:
        return list(prims)
    prims = list(prims)
    body = polygon(prims)
    for x, y in pos:
        q = Point(x, y)
        k = min(range(len(prims)), key=lambda i: LineString(points(prims[i])).distance(q))
        p = prims[k]
        if LineString(points(p)).distance(q) > 0.5:
            raise ValueError('%s: Mikrosteg at (%g, %g) is not on the outline' % (kind, x, y))
        if p[0] == 'L':
            (x0, y0), (x1, y1) = p[1], p[2]
            L = math.hypot(x1 - x0, y1 - y0)
            ux, uy = (x1 - x0) / L, (y1 - y0) / L
            t = (x - x0) * ux + (y - y0) * uy                       # projection on the line
            if t - R < 0.2 or t + R > L - 0.2:
                raise ValueError('%s: Mikrosteg at (%g, %g) too close to the end of its edge' % (kind, x, y))
            P = (x0 + t * ux, y0 + t * uy)
            A, B = (P[0] - R * ux, P[1] - R * uy), (P[0] + R * ux, P[1] + R * uy)
            n = (-uy, ux)
            if not body.contains(Point(P[0] + 0.5 * R * n[0], P[1] + 0.5 * R * n[1])):
                n = (uy, -ux)
            new = [('L', (x0, y0), A, p[3]), _recess_arc(P, A, B, n, p[3]), ('L', B, (x1, y1), p[3])]
        elif p[0] == 'A':
            (cx, cy), r, a0, a1, c = p[1], p[2], p[3], p[4], p[5]
            th = math.degrees(math.atan2(y - cy, x - cx)) % 360.0
            if (th - a0) % 360.0 > _span(a0, a1):
                raise ValueError('%s: Mikrosteg at (%g, %g) is not on its arc' % (kind, x, y))
            P = (cx + r * math.cos(math.radians(th)), cy + r * math.sin(math.radians(th)))
            d = math.degrees(2 * math.asin(R / (2 * r)))             # half-angle of the cut
            if (th - a0) % 360.0 - d < 0.5 or _span(a0, a1) - (th - a0) % 360.0 - d < 0.5:
                raise ValueError('%s: Mikrosteg at (%g, %g) too close to the end of its arc' % (kind, x, y))
            A = (cx + r * math.cos(math.radians(th - d)), cy + r * math.sin(math.radians(th - d)))
            B = (cx + r * math.cos(math.radians(th + d)), cy + r * math.sin(math.radians(th + d)))
            radial = ((P[0] - cx) / r, (P[1] - cy) / r)
            n = (-radial[0], -radial[1])
            if not body.contains(Point(P[0] + 0.5 * R * n[0], P[1] + 0.5 * R * n[1])):
                n = radial
            new = [('A', (cx, cy), r, a0, (th - d) % 360.0, c), _recess_arc(P, A, B, n, c),
                   ('A', (cx, cy), r, (th + d) % 360.0, a1, c)]
        else:
            raise ValueError('%s: Mikrosteg on a full circle is not supported' % kind)
        prims[k:k + 1] = new
    return prims


def specimen_prims(T, a_digit=None, index=None):
    """All primitives of a specimen: template, code (if any) and recesses."""
    prims = [from_entity(e, c) for e, c in T.ents]
    if T.has_code:
        prims += [('L', a, b, c) for a, b, c in T.code_prims(a_digit, index)]
    return add_recesses(prims, T.kind)


def specimen_polygon(T, a_digit=None, index=None):
    return polygon(specimen_prims(T, a_digit, index))


def mark_points(T):
    """Position of each Mikrosteg = bottom of its recess (template frame), for the notice."""
    out = []
    base = polygon([from_entity(e, c) for e, c in T.ents] +
                   ([('L', a, b, c) for a, b, c in [T.closing_prim()]] if T.has_code else []))
    ring = base.exterior
    for x, y in POSITIONS.get(T.kind, []):
        d = ring.project(Point(x, y))
        q, q0, q1 = ring.interpolate(d), ring.interpolate(d - 0.2), ring.interpolate(d + 0.2)
        tx, ty = q1.x - q0.x, q1.y - q0.y
        L = math.hypot(tx, ty)
        n = (-ty / L, tx / L)
        if not base.contains(Point(q.x + 0.5 * R * n[0], q.y + 0.5 * R * n[1])):
            n = (-n[0], -n[1])
        out.append((q.x + R * n[0], q.y + R * n[1]))
    return out


def add_to_block(blk, prims, layers):
    """Writes primitives into an ezdxf block (layer and colour from the quality colour)."""
    for p in prims:
        c = p[-1]
        att = {'layer': layers.get(c, '0'), 'color': c}
        if p[0] == 'L':
            blk.add_line(p[1], p[2], dxfattribs=att)
        elif p[0] == 'A':
            blk.add_arc(p[1], p[2], p[3], p[4], dxfattribs=att)
        else:
            blk.add_circle(p[1], p[2], dxfattribs=att)
