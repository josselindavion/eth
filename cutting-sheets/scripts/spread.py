# -*- coding: utf-8 -*-
"""
spread.py -- Repeats of the same specimen kept apart (supervisors' remark 6, 10/11/2026; used by make_plan.py).

Rule: two REPEATS of the same group (same type and same angle, e.g. UT40 0 deg index 1 and index 2) should not be
side by side on a sheet. "Side by side" = their outlines are closer than spread_distance (order field, default 10 mm;
with a gap of 5 mm this means direct neighbours, corner to corner included). Specimens without code (LASER) have no
angle and are not concerned. It is a preference: fitting the sheets comes first, the pairs left are reported.

Two tools:
    - conflicts(): the pairs of repeats side by side (check "Repeats side by side" and orange circles on the preview);
    - improve(): SWAPS after the placement. Two specimens of different groups placed at the same rotation (modulo
      180 deg) exchange their places: each takes the position and the rotation of the other. Many specimens share the
      same outer shape (UT40 / NT20 / NT06 / CHD48: 106 x 30 mm with the same grips; UT19 / SHLD / SHMD / SHHD;
      MNAK_RECT_FULL / MNAK_RECT_HOLE), and their middle parts differ, so each swap is checked on the real outlines
      (gap to every other specimen, margins, clamp zones). The best swap (largest decrease of the number of pairs) is
      made, and again, until no swap helps. No specimen moves elsewhere, so nothing is lost on the sheets.
      Swaps between sheets are allowed.
A group whose angle is used by no other type (e.g. UT40 at 15, 30, 60, 75 deg) cannot be helped by swaps: make_plan
then tries other placements (order field spread_tries, other seeds of sparrow) and keeps the best.
"""
from shapely.geometry import box

SAFETY = 0.01          # mm above the gap asked for a swapped specimen (the layout outlines have no notches: they are
                       # already slightly larger than the cut specimens)


def group(spec):
    """(type, angle) of a coded specimen; None for a specimen without code (no angle)."""
    return (spec['T'].alias, spec['angle']) if spec['T'].has_code else None


def _far(a, b, d):
    """True when the bounding boxes a and b (minx, miny, maxx, maxy) are at least d apart: then the outlines are too
    (cheap test before the exact distance; same result, faster on large sheets)."""
    return a[0] - b[2] >= d or b[0] - a[2] >= d or a[1] - b[3] >= d or b[1] - a[3] >= d


def conflicts(sheets, dist):
    """Pairs of repeats side by side: list of (sheet index, i, j, distance) with i < j indices in the sheet."""
    out = []
    for k, s in enumerate(sheets):
        by_group = {}
        for i, p in enumerate(s):
            g = group(p[0])
            if g is not None:
                by_group.setdefault(g, []).append(i)
        for idx in by_group.values():
            for a in range(len(idx)):
                for b in range(a + 1, len(idx)):
                    if _far(s[idx[a]][4].bounds, s[idx[b]][4].bounds, dist):
                        continue
                    d = s[idx[a]][4].distance(s[idx[b]][4])
                    if d < dist:
                        out.append((k, idx[a], idx[b], d))
    return out


def _same_rot(r, rot):
    """True when a specimen of placement angle rot may be placed at rotation r (rot or rot + 180)."""
    return abs((r - rot + 90.0) % 180.0 - 90.0) < 1e-6


def _count(sheets, dist, ks):
    """Number of pairs side by side on the sheets ks."""
    return len(conflicts([sheets[k] for k in ks], dist))


def improve(sheets, place_fn, W, H, gap, m, keepouts=None, dist=10.0, max_swaps=500):
    """Swaps that reduce the pairs of repeats side by side (see the module docstring).
    place_fn(spec, r, x, y) -> placed tuple (spec, r, x, y, outline). Returns (new sheets, number of swaps)."""
    sheets = [list(s) for s in sheets]
    inner = box(m['left'], m['bottom'], W - m['right'], H - m['top']).buffer(1e-6)
    keepouts = keepouts or []

    def fits(k, new, skip):
        P = new[4]
        if not inner.contains(P) or any(P.intersection(z).area > 1e-6 for z in keepouts):
            return False
        pb, g = P.bounds, gap + SAFETY
        return all(_far(pb, q[4].bounds, g) or P.distance(q[4]) >= g for j, q in enumerate(sheets[k]) if j not in skip)

    swaps = 0
    while swaps < max_swaps:
        cur = conflicts(sheets, dist)
        if not cur:
            break
        hot = sorted(set((k, i) for k, i, j, _ in cur) | set((k, j) for k, i, j, _ in cur))
        slots = [(k, i) for k in range(len(sheets)) for i in range(len(sheets[k]))]
        best = None
        for ka, ia in hot:
            A = sheets[ka][ia]
            for kb, ib in slots:
                if (kb, ib) == (ka, ia):
                    continue
                B = sheets[kb][ib]
                if group(B[0]) == group(A[0]) or not _same_rot(A[1], B[0]['rot']) or \
                        not _same_rot(B[1], A[0]['rot']):
                    continue
                A2 = place_fn(B[0], A[1], A[2], A[3])          # B's specimen in A's place
                B2 = place_fn(A[0], B[1], B[2], B[3])          # A's specimen in B's place
                if ka == kb:
                    if A2[4].distance(B2[4]) < gap + SAFETY or not fits(ka, A2, {ia, ib}) or \
                            not fits(kb, B2, {ia, ib}):
                        continue
                elif not fits(ka, A2, {ia}) or not fits(kb, B2, {ib}):
                    continue
                ks = sorted({ka, kb})
                before = _count(sheets, dist, ks)
                sheets[ka][ia], sheets[kb][ib] = A2, B2
                gain = before - _count(sheets, dist, ks)
                sheets[ka][ia], sheets[kb][ib] = A, B
                if gain > 0 and (best is None or gain > best[0]):
                    best = (gain, ka, ia, kb, ib, A2, B2)
        if best is None:
            break
        _, ka, ia, kb, ib, A2, B2 = best
        sheets[ka][ia], sheets[kb][ib] = A2, B2
        swaps += 1
    return sheets, swaps
