# -*- coding: utf-8 -*-
"""
placement.py -- Placement of the specimens on the sheets, then DXF output (used by make_plan.py).

Two engines, both open source:
    - PackingSolver (F. Fontan; pip install packingsolver): "bin packing" of irregular shapes on sheets of fixed
      size; it decides quickly which specimen goes on which sheet and gives a valid layout of each sheet;
    - sparrow (Gardeyn, Vanden Berghe, Wauters, KU Leuven, 2025; pip install spyrrow==0.9.0): "strip packing" of
      irregular shapes, denser; used to fit more specimens on a sheet and to compact each sheet. It runs in a separate
      process (sparrow_worker.py) so that it can be stopped as soon as the specimens fit.

Method (see place):
    1. ASSIGNMENT: PackingSolver places all the specimens on sheets ("assign_seconds") -> n sheets, valid layouts;
    2. REDUCTION: while the specimens could fit on one sheet less (area <= fill_max x usable area of n - 1 sheets),
       the specimens of the least filled sheet are moved, largest first, to the sheets with the most free room (up to
       3 sheets tried per specimen): sparrow packs the receiving sheet with one specimen more and is stopped as soon as
       everything fits (often 1-3 s; at most "fill_seconds"); when the sheet is empty, n decreases; when a specimen
       fits nowhere, or after "fill_tries" failed tries, the reduction stops (the specimens keep their place: nothing
       is started again from scratch);
    3. COMPACTION: sparrow packs each sheet as low as possible (at most "seconds", stopped when the layout has not
       improved for a third of that time); the result is kept only if it fits. The receiving sheets are compacted
       before the reduction, so that their real free room is known (lowest top first); when a specimen fits on none
       of the 3 sheets with the most room, the sheets changed since are compacted again and 3 more sheets are tried.
    When a specimen misses a sheet by less than 10 mm, that sheet gives its smallest specimen to a third sheet
    (rebalancing) instead of giving up.

Rules (supervisors, 29/10/2026 and 02/11/2026):
    - gap between pieces >= gap: both engines get gap + 0.05 mm (SAFETY);
    - margins to the sheet edge, one per side (left, bottom, right, top; e.g. L-shaped clamping area of 40 mm);
    - fixed angle: each specimen is placed at its placement angle or that angle + 180 deg, never mirrored; placement
      angle = ordered angle + offset of the type (0, except MNAK_RECT: -90, see make_templates.ANGLE_OFFSET).
"""
import collections
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time

import ezdxf
from shapely import affinity

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, 'sparrow_worker.py')
SAFETY = 0.05           # mm added to the gap asked from the engines
SHEET_SPACING = 40.0    # mm between two sheets in the DXF (as in the lab drawings)


class PlacementError(Exception):
    pass


def _area(polys, s, gap):
    return polys[s['T'].kind].buffer(gap / 2.0, join_style=1).area


def _snap(a, rot):
    """Engine angle -> exact allowed angle (rot or rot + 180)."""
    return min((rot % 360.0, (rot + 180.0) % 360.0), key=lambda c: abs((a - c + 180.0) % 360.0 - 180.0))


def _placed(s, r, x, y, polys):
    return (s, r, x, y, affinity.translate(affinity.rotate(polys[s['T'].kind], r, origin=(0, 0)), x, y))


# ============================================================
# SPARROW (separate process, can be stopped early)
# ============================================================
def _touches(k, m, H=None):
    """Side(s) of the effective area that a keep-out zone touches: 'left', 'bottom' (the clamps of the L)."""
    b = k.bounds
    return ('left' if abs(b[0] - m['left']) < 1e-6 else '') + ('bottom' if abs(b[1] - m['bottom']) < 1e-6 else '')


def sparrow(specs, polys, W, gap, m, seconds, seed=1, target=None, stall=None, on_progress=None, keepouts=None,
            lim=None):
    """Packs specs on one sheet as a strip (length = rolling direction). Stops as soon as the top of the layout is
    <= target (if given), or when the top has not gone down by 0.5 mm for "stall" seconds (if given), otherwise after
    "seconds"; with a target, a try that is less than 2 mm above it after "seconds" gets up to "seconds" more. Returns (placed list, top) of the best solution, or (None, inf).
    m: margins per side {'left', 'bottom', 'right', 'top'} in mm.
    keepouts + lim: the clamp zones of the left and bottom edges are given to sparrow as one fixed "wall" item: a
    comb made of a thin bar along the left edge (from the bottom up to lim, the top limit of the sheet) and along the
    bottom edge, lying in the edge margin, with one tooth on each clamp zone. As long as the wall reaches lim, sparrow
    can only put it in one place (strip start, against the left side): solutions where it is elsewhere are refused."""
    sep = gap + SAFETY
    x0, x1 = m['left'] - gap, W - m['right'] + gap          # strip borders, x on the sheet
    y0 = m['bottom'] - gap                                  # start of the strip, y on the sheet
    wall = None
    walled = [k for k in (keepouts or []) if _touches(k, m)]
    if walled and lim is not None:
        from shapely.ops import unary_union
        from shapely.geometry import box as sbox
        bt = 1.0                                            # thickness of the bars of the wall
        x0, y0 = x0 - sep - bt, y0 - sep - bt                # strip widened so that the bars lie in the margin
        sx, sy = x0 + sep, y0 + sep                          # outer corner of the wall
        parts = [sbox(sx, sy, sx + bt, lim - 0.05), sbox(sx, sy, x1 - sep - 0.1, sy + bt)]   # not exactly the strip
        sk = sep / math.sqrt(2.0) - 0.05                     # tooth inset: the rounded clearance of sparrow
        for k in walled:                                    # (distance sep) must also cover the zone's corners
            kx0, ky0, kx1, ky1 = k.bounds
            t = _touches(k, m)
            parts.append(sbox(sx if 'left' in t else kx0 + sk, sy if 'bottom' in t else ky0 + sk,
                              kx1 - sk, ky1 - sk))
        wall = unary_union(parts)
        if wall.geom_type != 'Polygon' or list(wall.interiors):
            wall = None                                     # should not happen; then repair() does the work
            x0, y0 = m['left'] - gap, m['bottom'] - gap
    strip_h = x1 - x0
    if strip_h <= 2 * sep:
        raise PlacementError('left + right margins too large for a sheet %g mm wide' % W)
    groups = collections.OrderedDict()
    for s in specs:
        groups.setdefault('%s|%g' % (s['T'].kind, s['rot']), []).append(s)
    items = []
    for gid, ss in groups.items():
        g = affinity.rotate(polys[ss[0]['T'].kind], -90, origin=(0, 0))     # our +Y = +X of the strip
        a = ss[0]['rot']
        items.append([gid, [list(p) for p in g.exterior.coords[:-1]], len(ss), [a, (a + 180.0) % 360.0]])
    if wall is not None:                                    # sheet (x, y) -> strip (y - y0, x1 - x), fixed angle
        items.append(['WALL', [[y - y0, x1 - x] for x, y in wall.exterior.coords[:-1]], 1, [0.0]])
    budget = 2 * seconds if target is not None else seconds    # time given to sparrow itself
    job = {'items': items, 'strip_height': strip_h, 'separation': sep, 'seconds': budget, 'seed': seed,
           'workers': None}
    proc = subprocess.Popen([sys.executable, WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    proc.stdin.write(json.dumps(job))
    proc.stdin.close()
    lines = queue.Queue()
    reader = threading.Thread(target=lambda: [lines.put(l) for l in proc.stdout] + [lines.put(None)], daemon=True)
    reader.start()
    t0, best, best_top = time.time(), None, math.inf
    t_imp, top_imp = t0, math.inf                           # last real improvement (for "stall")
    try:
        while True:
            try:
                line = lines.get(timeout=0.25)
            except queue.Empty:
                line = ''
            if line is None:
                break
            if line:
                msg = json.loads(line)
                if msg['kind'] == 'error':
                    raise PlacementError('sparrow: %s' % msg['error'])
                top = msg['width'] - sep + y0
                if wall is not None:                        # the wall must be at its place, otherwise refused
                    w = [q for q in msg['placed'] if q[0] == 'WALL']
                    if not w or abs(w[0][2]) > 0.3 or abs(w[0][3]) > 0.3 or \
                            abs((w[0][1] + 180.0) % 360.0 - 180.0) > 0.01:
                        top = math.inf
                if top < best_top:
                    best, best_top = msg['placed'], top
                if top < top_imp - 0.5:
                    t_imp, top_imp = time.time(), top
                if on_progress:
                    on_progress(time.time() - t0, best_top)
                if msg['kind'] == 'final' or (target is not None and best_top <= target):
                    break
            if on_progress:
                on_progress(time.time() - t0, best_top if best is not None else None)
            el = time.time() - t0
            if stall and best is not None and time.time() - t_imp > stall:
                break
            if target is not None and el > seconds and not best_top - target < 2.0:
                break                                       # not close enough: give up after "seconds"
            if el > budget + 2:                             # sparrow sometimes overruns its budget
                break
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait()
    if best is None:
        err = proc.stderr.read().strip().splitlines()[-1:] if proc.stderr else []
        if err:
            raise PlacementError('sparrow: %s' % err[0])
        return None, math.inf
    pool = {gid: list(ss) for gid, ss in groups.items()}
    placed = []
    # bottom -> top, then left -> right, so that the indices increase in reading order
    for gid, rot, tx, ty in sorted(best, key=lambda p: (round(p[2], 1), -p[3])):
        if gid == 'WALL':
            continue
        s = pool[gid].pop(0)
        placed.append(_placed(s, _snap(rot, s['rot']), x1 - ty, y0 + tx, polys))   # strip -> sheet
    return placed, best_top


# ============================================================
# PACKINGSOLVER (assignment to sheets)
# ============================================================
def _ps_shape(poly):
    import packingsolver.irregular as pi
    p = poly.simplify(0.01)
    pts = [list(q) for q in p.exterior.coords[:-1]]
    if not p.exterior.is_ccw:
        pts = pts[::-1]
    return pi.build_shape(pts)


def packingsolver(specs, polys, W, H, gap, m, seconds, on_progress=None, keepouts=None, fixed=None, copies=-1):
    """Bin packing of all specs on sheets W x H with margins m. keepouts: forbidden zones (sheet coordinates, on
    every sheet, already with their margins); fixed: outlines already placed (one sheet only, copies=1), kept at
    gap mm. Returns a list of sheets (lists of placed), or None if copies is limited and not everything fits."""
    import packingsolver.irregular as pi
    from packingsolver import Objective
    from shapely.geometry import box as sbox
    uw = W - m['left'] - m['right'] - 2 * SAFETY
    uh = H - m['bottom'] - m['top'] - 2 * SAFETY
    ox, oy = m['left'] + SAFETY, m['bottom'] + SAFETY
    b = pi.InstanceBuilder()
    b.set_objective(Objective.BinPacking)
    bt = b.add_bin_type(pi.build_rectangle(uw, uh), copies=copies)
    b.set_item_item_minimum_spacing(gap + SAFETY)
    frame = sbox(0, 0, uw, uh)
    for k_list, spacing in ((keepouts or [], 0.0), (fixed or [], gap + SAFETY)):
        for g in k_list:
            g = affinity.translate(g, -ox, -oy).intersection(frame)
            for part in (g.geoms if hasattr(g, 'geoms') else [g]):
                if part.geom_type == 'Polygon' and part.area > 1e-6:
                    d = b.add_defect(bt, 0, pi.ShapeWithHoles(_ps_shape(part)))
                    b.set_item_defect_minimum_spacing(bt, d, spacing)
    groups = collections.OrderedDict()
    for s in specs:
        groups.setdefault((s['T'].kind, s['rot']), []).append(s)
    ids = {}
    for (kind, rot), ss in groups.items():
        p = polys[kind].simplify(0.01)
        pts = [list(q) for q in p.exterior.coords[:-1]]
        if not p.exterior.is_ccw:
            pts = pts[::-1]
        t = b.add_item_type(pi.build_shape(pts), copies=len(ss),
                            allowed_rotations=[(rot, rot, False), ((rot + 180.0) % 360.0, (rot + 180.0) % 360.0, False)])
        ids[t] = list(ss)
    par = pi.OptimizeParameters()
    par.time_limit = float(seconds)
    par.verbosity_level = 0
    box = {}
    th = threading.Thread(target=lambda: box.update(out=pi.optimize(b.build(), par)), daemon=True)
    t0 = time.time()
    th.start()
    while th.is_alive():
        th.join(0.25)
        if on_progress:
            on_progress(time.time() - t0, None)
    sol = box['out'].solution
    if not sol.feasible():
        if copies != -1:
            return None
        raise PlacementError('PackingSolver found no complete solution')
    sheets = []
    for k in range(sol.number_of_bins()):
        sheet = []
        for it in sol.bin(k).items:
            s = ids[it.item_type_id].pop(0)
            c = it.bl_corner
            sheet.append(_placed(s, _snap(it.angle, s['rot']), c.x + ox, c.y + oy, polys))
        sheets.append(sheet)
    return sheets


# ============================================================
# PLACEMENT
# ============================================================
def repair(layout, keepouts, specs_polys, W, H, gap, m, seconds=10):
    """A sparrow layout (sparrow knows no forbidden zones) made valid for the keep-out zones of the clamps: the
    specimens that touch a zone are taken out and PackingSolver puts them back in the free space of the same sheet
    (zones + other specimens as obstacles). Returns the new layout, or None if they do not all fit."""
    if layout is None or not keepouts:
        return layout
    bad = [p for p in layout if any(p[4].intersection(k).area > 1e-6 for k in keepouts)]
    if not bad:
        return layout
    keep = [p for p in layout if p not in bad]
    out = packingsolver([p[0] for p in bad], specs_polys, W, H, gap, m, seconds, keepouts=keepouts,
                        fixed=[p[4] for p in keep], copies=1)
    if not out or len(out) != 1 or len(out[0]) != len(bad):
        return None
    return keep + out[0]


def place(specs, polys, W, H, gap, margins, seconds, seed=1, max_sheets=20, on_progress=None, log=None,
          assign_seconds=30, fill_tries=8, fill_seconds=10, fill_max=0.85, keepouts=None):
    """All the specimens on sheets W x H (margins: {'left', 'bottom', 'right', 'top'} in mm). See the module docstring.
    Returns a list of sheets, each a list of (spec, rotation_deg, x, y, placed_outline).
    on_progress(label, elapsed_seconds, best_height_or_None, planned_duration); log(message)."""
    m = margins
    uw, uh = W - m['left'] - m['right'], H - m['bottom'] - m['top']
    lim = H - m['top'] + 1e-6
    for s in specs:                                          # each piece must fit alone in the usable area
        T = s['T']
        b = affinity.rotate(polys[T.kind], s['rot'], origin=(0, 0)).bounds
        if b[2] - b[0] > uw + 1e-6 or b[3] - b[1] > uh + 1e-6:
            raise PlacementError('%s at %g deg (%.0f x %.0f mm once turned) does not fit in the usable area of the '
                                 'sheet (%g x %g mm, margins excluded)' % (T.alias, s['angle'], b[2] - b[0],
                                                                         b[3] - b[1], uw, uh))
    prog = (lambda label, sec: (lambda t, best: on_progress(label, t, best, sec))) if on_progress else \
        (lambda label, sec: None)
    U = (uw + gap) * (uh + gap)
    area = lambda sheet: sum(_area(polys, p[0], gap) for p in sheet)      # noqa: E731

    # 1. assignment
    sheets = packingsolver(specs, polys, W, H, gap, m, assign_seconds, prog('Assignment', assign_seconds),
                           keepouts=keepouts)
    U -= sum(k.area for k in (keepouts or []))              # usable area without the clamp zones
    # with clamps, sparrow (which knows no forbidden zones) must leave room at the top for the specimens moved out
    # of the clamp zones by repair(): target lowered by the area of the zones / usable width
    dk = sum(k.area for k in (keepouts or []) if not _touches(k, m)) / max(uw, 1.0)
    if len(sheets) > max_sheets:
        raise PlacementError('the specimens need %d sheets (max_sheets = %d)' % (len(sheets), max_sheets))
    if log:
        log('PackingSolver: %d sheet(s) (%s specimens)' % (len(sheets), ', '.join(str(len(s)) for s in sheets)))
    # direct try on one sheet when the area allows it (PackingSolver is less dense than sparrow)
    if len(sheets) > 1 and sum(area(s) for s in sheets) <= fill_max * U:
        t1 = max(60.0, 4 * fill_seconds)
        trial, t = sparrow(specs, polys, W, gap, m, t1, seed, target=lim, on_progress=prog('One sheet', t1),
                           keepouts=keepouts, lim=lim)
        if trial is not None and t <= lim and keepouts:
            trial = repair(trial, keepouts, polys, W, H, gap, m)
        if trial is not None and t <= lim:
            sheets = [trial]
            if log:
                log('all the specimens fit on one sheet (sparrow)')
        elif log:
            log('one sheet: not reached (top %.1f mm for a limit of %.1f mm)' % (t, lim))

    def compact(k, label):
        """sparrow packs sheet k as low as possible; the result is kept only if it fits."""
        trial, t = sparrow([p[0] for p in sheets[k]], polys, W, gap, m, seconds, seed, stall=max(3.0, seconds / 3.0),
                           on_progress=prog(label, seconds), keepouts=keepouts, lim=lim)
        if trial is not None and t <= lim and keepouts:
            trial = repair(trial, keepouts, polys, W, H, gap, m)
        if trial is not None and t <= lim:
            sheets[k] = trial
        elif log:
            log('sheet %d: compaction does not fit, layout of the previous step kept' % (k + 1))
        done.add(id(sheets[k]))

    def fit(k, extra, without=None):
        """Sheet k with the specimens "extra" added (and the placed specimen "without" removed): a layout that fits
        (stopped as soon as found), or None and the top reached."""
        ss = [q[0] for q in sheets[k] if q is not without] + extra
        count[0] += 1                                       # a new seed for each try: more variety
        trial, t = sparrow(ss, polys, W, gap, m, fill_seconds, seed + count[0], target=lim - dk,
                           on_progress=prog('Sheet %d: +%s' % (k + 1, extra[0]['T'].alias), fill_seconds),
                           keepouts=keepouts, lim=lim)
        if trial is not None and t <= lim and keepouts:
            trial = repair(trial, keepouts, polys, W, H, gap, m)
            if trial is None:
                t = max(t, lim + 0.1)                       # counted as a miss
        return (trial if trial is not None and t <= lim else None), t

    def by_room(ks):
        """Most likely to receive a specimen first: lowest top of the layout, then least specimen area."""
        return sorted(ks, key=lambda k: (round(top(sheets[k])), area(sheets[k])))

    def candidates(src, a, tried):
        """Receiving sheets for a specimen of area a, most room first: the 3 best, then, if they all failed, the
        sheets changed since their compaction are compacted again (their real room is then known) and the 3 best
        not tried yet are given."""
        ok = lambda k: k != src and k not in tried and (area(sheets[k]) + a) / U <= fill_max   # noqa: E731
        for k in by_room(k for k in range(len(sheets)) if ok(k))[:3]:
            yield k
        stale = [k for k in range(len(sheets)) if k != src and id(sheets[k]) not in done]
        if seconds > 0 and stale and fails < fill_tries:
            for k in stale:
                compact(k, 'Compact %d/%d' % (k + 1, len(sheets)))
            for k in by_room(k for k in range(len(sheets)) if ok(k))[:3]:
                yield k

    done = set()                                            # ids of the sheet layouts already compacted
    count = [0]                                             # sparrow tries so far
    # 2. reduction: empty the least filled sheet into the others
    fails = 0
    while len(sheets) > 1 and fails < fill_tries:
        total = sum(area(s) for s in sheets)
        if total > fill_max * U * (len(sheets) - 1):
            if log:
                log('%d sheets cannot be reduced: the specimens would fill %.0f %% of %d sheets'
                    % (len(sheets), 100 * total / (U * (len(sheets) - 1)), len(sheets) - 1))
            break
        src = min(range(len(sheets)), key=lambda k: area(sheets[k]))
        if seconds > 0:                                     # real free room of the receiving sheets
            for k in range(len(sheets)):
                if k != src and id(sheets[k]) not in done:
                    compact(k, 'Compact %d/%d' % (k + 1, len(sheets)))
        moved_all = True
        for p in sorted(list(sheets[src]), key=lambda p: -_area(polys, p[0], gap)):
            a = _area(polys, p[0], gap)
            ok, tried = False, set()
            for k in candidates(src, a, tried):
                if fails >= fill_tries:
                    break
                trial, t = fit(k, [p[0]])
                if trial is None and t - lim < 10 and len(sheets) > 2 and fails + 1 < fill_tries:
                    # near miss: rebalance, i.e. sheet k gives its smallest specimen q to a third sheet
                    q = min((q for q in sheets[k]), key=lambda q: _area(polys, q[0], gap))
                    trial_k, _ = fit(k, [p[0]], without=q)
                    if trial_k is not None:
                        for j in by_room(j for j in range(len(sheets)) if j not in (src, k))[:2]:
                            trial_j, _ = fit(j, [q[0]])
                            if trial_j is not None:
                                sheets[j] = trial_j
                                trial = trial_k
                                if log:
                                    log('%s %g deg moved from sheet %d to sheet %d to make room'
                                        % (q[0]['T'].alias, q[0]['angle'], k + 1, j + 1))
                                break
                tried.add(k)
                if trial is not None:
                    sheets[k] = trial
                    sheets[src] = [q for q in sheets[src] if q[0] is not p[0]]
                    ok = True
                    if log:
                        log('%s %g deg moved from sheet %d to sheet %d' % (p[0]['T'].alias, p[0]['angle'],
                                                                          src + 1, k + 1))
                    break
                fails += 1
            if not ok:
                moved_all = False
                if log:
                    log('%s %g deg (sheet %d) fits on no other sheet: reduction stopped'
                        % (p[0]['T'].alias, p[0]['angle'], src + 1))
                break
        if not sheets[src]:
            del sheets[src]
            if log:
                log('one sheet less: %d sheet(s)' % len(sheets))
        if not moved_all or fails >= fill_tries:
            break

    # 3. compaction of the sheets not compacted yet (or changed since)
    if seconds > 0:
        for k in range(len(sheets)):
            if id(sheets[k]) not in done:
                compact(k, 'Compact %d/%d' % (k + 1, len(sheets)))
    # sheets ordered from the fullest to the emptiest
    sheets.sort(key=lambda s: -area(s))
    return sheets


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
        for spec, r, x, y, poly in sorted(s, key=lambda p: (round(p[3] / 10.0), p[2])):
            msp.add_blockref(spec['block'], (ox + x, y), dxfattribs={'rotation': r, 'layer': '0'})
            rows.append({'sheet': k + 1, 'block': spec['block'], 'type': spec['T'].kind,
                         'orientation_to_RD_deg': '%g' % (spec['angle'] % 180),     # ordered angle
                         'rotation_deg': round(r, 4),                                # placement angle
                         'insert_x_mm': round(ox + x, 4), 'insert_y_mm': round(y, 4)})
    doc.saveas(path)
    return rows
