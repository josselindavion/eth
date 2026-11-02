# -*- coding: utf-8 -*-
"""
sparrow_place.py -- Placement of the specimens on the sheets with sparrow, then DXF output (used by make_plan.py).

Engine: sparrow (Gardeyn, Vanden Berghe, Wauters, KU Leuven, 2025; MIT licence), through its Python interface spyrrow:
    py -m pip install spyrrow==0.9.0
sparrow solves irregular "strip packing": a strip of fixed height whose length is minimised. Here the strip is the
sheet lying on its side: its fixed height is the sheet width W, its length is the rolling direction (+Y), minimised.

Rules (supervisors, 29/10/2026):
    - gap between pieces >= gap (5 mm): sparrow's min_items_separation (+ 0.05 mm of safety, since sparrow allows
      ~0.01 mm less); sparrow also keeps this distance to the strip borders;
    - margins to the sheet edge, one per side (left, bottom, right, top; e.g. L-shaped clamping area of 40 mm on the
      left and at the bottom): the strip lies between x = left - gap and x = W - right + gap and starts at
      y = bottom - gap; since sparrow keeps the separation (gap + 0.05) to the strip borders, every piece is at least
      margin + 0.05 from the edge; at the top, a piece stays on the sheet only if it is at least "top" from the edge;
    - fixed angle: each specimen can only be placed at its placement angle or that angle + 180 deg; placement
      angle = ordered angle + offset of the type (0, except MNAK_RECT: -90, see make_templates.ANGLE_OFFSET);
      sparrow never mirrors a piece when it is given a list of angles.

Several sheets (see place): the specimens are split into groups of equal area, sparrow packs one group per sheet,
each sheet is then filled with specimens of the next groups; if a group does not fit, one sheet more is tried.
"""
import collections
import math
import threading
import time

import ezdxf
from shapely import affinity

SAFETY = 0.05           # mm added to the separation asked from sparrow
SHEET_SPACING = 40.0    # mm between two sheets in the DXF (as in the lab drawings)


class PlacementError(Exception):
    pass


def _solve_strip(specs, polys, W, gap, m, seconds, seed, workers, on_progress):
    """One strip: returns [(spec, rotation_deg, x, y, placed_outline)] in the sheet frame (y from the bottom).
    m: margins per side {'left', 'bottom', 'right', 'top'} in mm."""
    import spyrrow
    sep = gap + SAFETY
    x0, x1 = m['left'] - gap, W - m['right'] + gap          # strip borders, x on the sheet
    y0 = m['bottom'] - gap                                  # start of the strip, y on the sheet
    strip_h = x1 - x0
    if strip_h <= 2 * sep:
        raise PlacementError('left + right margins too large for a sheet %g mm wide' % W)
    groups = collections.OrderedDict()
    for s in specs:
        groups.setdefault('%s|%g' % (s['T'].kind, s['angle']), []).append(s)
    items = []
    for gid, ss in groups.items():
        g = affinity.rotate(polys[ss[0]['T'].kind], -90, origin=(0, 0))     # our +Y = +X of the strip
        a = ss[0]['rot']
        items.append(spyrrow.Item(gid, list(g.exterior.coords)[:-1], demand=len(ss),
                                  allowed_orientations=[a, (a + 180.0) % 360.0]))
    inst = spyrrow.StripPackingInstance('plan', strip_height=strip_h, items=items)
    conf = spyrrow.StripPackingConfig(total_computation_time=int(seconds), min_items_separation=sep,
                                      num_workers=workers, seed=seed, early_termination=True)
    queue = spyrrow.ProgressQueue()
    box = {}

    def work():
        try:
            box['sol'] = inst.solve(conf, progress=queue)
        except Exception as e:              # passed back to the main thread
            box['err'] = e
    th = threading.Thread(target=work, daemon=True)
    t0 = time.time()
    th.start()
    best = None
    while th.is_alive():
        th.join(0.25)
        for rtype, sol in queue.drain():
            if 'Feas' in str(rtype) and 'Infeas' not in str(rtype):
                top = sol.width - sep + y0
                best = top if best is None else min(best, top)
        if on_progress:
            on_progress(time.time() - t0, best)
    if 'err' in box:
        raise box['err']
    sol = box['sol']
    placed = []
    pool = {gid: list(ss) for gid, ss in groups.items()}
    # bottom -> top, then left -> right, so that the indices increase in reading order
    for pi in sorted(sol.placed_items, key=lambda p: (round(p.translation[0], 1), -p.translation[1])):
        s = pool[pi.id].pop(0)
        a = s['rot']                                        # exact angle: a or a + 180 (sparrow works in float32)
        r = min((a % 360.0, (a + 180.0) % 360.0), key=lambda c: abs((pi.rotation - c + 180.0) % 360.0 - 180.0))
        tx, ty = pi.translation
        x, y = x1 - ty, y0 + tx                             # strip -> sheet (rotation +90 deg, then offset)
        poly = affinity.translate(affinity.rotate(polys[s['T'].kind], r, origin=(0, 0)), x, y)
        placed.append((s, r, x, y, poly))
    return placed


def _area(polys, s, gap):
    return polys[s['T'].kind].buffer(gap / 2.0, join_style=1).area


def _split(specs, polys, n, gap):
    """Splits the specimens into n groups of about equal area (piece + half the gap): the largest remaining specimen
    goes to the least loaded group ("LPT" rule), which also mixes the types."""
    area = {}
    for s in specs:
        k = s['T'].kind
        if k not in area:
            area[k] = _area(polys, s, gap)
    groups, load = [[] for _ in range(n)], [0.0] * n
    for s in sorted(specs, key=lambda s: (-area[s['T'].kind], s['block'])):
        i = load.index(min(load))
        groups[i].append(s)
        load[i] += area[s['T'].kind]
    return [g for g in groups if g]


def place(specs, polys, W, H, gap, margins, seconds, seed=1, workers=None, max_sheets=20, on_progress=None,
          log=None, fill_tries=8, fill_seconds=None, fill_max=0.85, fill_fails=3):
    """All the specimens on sheets W x H. margins: {'left', 'bottom', 'right', 'top'} in mm.

    Method:
      1. starting number of sheets n = area of the pieces (+ half the gap) / usable area of a sheet, rounded up
         (a lower bound: fewer sheets are impossible);
      2. sheet by sheet: the remaining specimens are split into as many groups of equal area as there are sheets
         left (_split); sparrow packs the first group on the sheet ("seconds");
      3. FILLING: specimens of the next groups are tried, from the largest to the smallest; sparrow packs the sheet
         again with one specimen more ("fill_seconds"); if everything fits, it stays, otherwise that shape is not
         tried again on this sheet; stop after "fill_fails" failures in a row or "fill_tries" tries, and only try
         while the occupied area would stay <= fill_max x usable area;
      4. if all specimens are placed before the last planned sheet, stop (fewer sheets);
         if a group does not fit on its sheet, start again with n + 1 sheets.
    Returns a list of sheets, each a list of (spec, rotation_deg, x, y, placed_outline).
    on_progress(label, elapsed_seconds, best_height, planned_duration); log(message).
    """
    uw = W - margins['left'] - margins['right']
    uh = H - margins['bottom'] - margins['top']
    lim = H - margins['top'] + 1e-6
    for s in specs:                                          # each piece must fit alone in the usable area
        T = s['T']
        b = affinity.rotate(polys[T.kind], s['rot'], origin=(0, 0)).bounds
        if b[2] - b[0] > uw + 1e-6 or b[3] - b[1] > uh + 1e-6:
            raise PlacementError('%s at %g deg (%.0f x %.0f mm once turned) does not fit in the usable area of the '
                                 'sheet (%g x %g mm, margins excluded)' % (T.alias, s['angle'], b[2] - b[0],
                                                                         b[3] - b[1], uw, uh))
    fill_seconds = fill_seconds or max(5, seconds / 2.0)
    U = (uw + gap) * (uh + gap)
    total = sum(_area(polys, s, gap) for s in specs)
    n = max(1, int(math.ceil(total / U - 1e-9)))

    def solve(group, label, sec):
        placed = _solve_strip(group, polys, W, gap, margins, sec, seed, workers,
                              (lambda t, b: on_progress(label, t, b, sec)) if on_progress else None)
        return placed, max(p[4].bounds[3] for p in placed)

    while n <= min(max_sheets, len(specs)):
        remaining, sheets = list(specs), []
        while remaining:
            k = len(sheets) + 1
            left = n - k + 1
            if left <= 0:
                break
            group = list(_split(remaining, polys, left, gap)[0]) if left > 1 else list(remaining)
            placed, t = solve(group, '%d sheets: %d/%d' % (n, k, n), seconds)
            if t > lim:
                if log:
                    log('sheet %d of %d: %.1f mm too high -> trying %d sheets' % (k, n, t - lim, n + 1))
                break
            ids = set(id(x) for x in group)
            rest = [x for x in remaining if id(x) not in ids]
            # filling with specimens of the next groups
            used, failed, tries, streak = sum(_area(polys, x, gap) for x in group), set(), 0, 0
            while rest and tries < fill_tries and streak < fill_fails:
                cands = sorted((x for x in rest if (x['T'].kind, x['angle']) not in failed
                                and (used + _area(polys, x, gap)) / U <= fill_max),
                               key=lambda x: (-_area(polys, x, gap), x['block']))
                if not cands:
                    break
                c = cands[0]
                tries += 1
                name = '%s %g deg' % (c['T'].alias, c['angle'])
                trial, tt = solve(group + [c], 'sheet %d: +%s' % (k, c['T'].alias), fill_seconds)
                if tt <= lim:
                    group.append(c)
                    placed, t = trial, tt
                    used += _area(polys, c, gap)
                    rest = [x for x in rest if x is not c]
                    streak = 0
                    if log:
                        log('sheet %d: + %s added (%d specimens)' % (k, name, len(group)))
                else:
                    failed.add((c['T'].kind, c['angle']))
                    streak += 1
                    if log:
                        log('sheet %d: + %s does not fit' % (k, name))
            sheets.append(placed)
            remaining = rest
        if not remaining:
            return sheets
        n += 1
    raise PlacementError('the specimens do not fit on %d sheets' % min(max_sheets, len(specs)))


def top(sheet):
    return max(p[4].bounds[3] for p in sheet)


def write_dxf(path, sheets, libdoc, W, H):
    """DXF plan: one frame per sheet (colour 7) and one block per specimen (exact geometry), in mm."""
    doc = ezdxf.new('R2000', setup=True)
    doc.header['$INSUNITS'] = 4
    for name, c in (('Q3_NORMAL', 3), ('Q4_MEDIUM', 4), ('Q5_HIGH', 5), ('SHEET', 7)):
        doc.layers.add(name, color=c)
    msp = doc.modelspace()
    for name in sorted(set(p[0]['block'] for s in sheets for p in s)):
        blk = doc.blocks.new(name)
        for e in libdoc.blocks.get(name):
            blk.add_foreign_entity(e, copy=True)
    rows = []
    for k, s in enumerate(sheets):
        ox = k * (W + SHEET_SPACING)
        for a, b in (((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))):
            msp.add_line((ox + a[0], a[1]), (ox + b[0], b[1]), dxfattribs={'layer': 'SHEET', 'color': 7})
        for spec, r, x, y, poly in s:
            msp.add_blockref(spec['block'], (ox + x, y), dxfattribs={'rotation': r, 'layer': '0'})
            rows.append({'sheet': k + 1, 'block': spec['block'], 'type': spec['T'].kind,
                         'orientation_to_RD_deg': '%g' % (spec['angle'] % 180),     # ordered angle
                         'rotation_deg': round(r, 4),                                # placement angle
                         'insert_x_mm': round(ox + x, 4), 'insert_y_mm': round(y, 4)})
    doc.saveas(path)
    return rows
