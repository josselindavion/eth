# -*- coding: utf-8 -*-
"""
materials_data.py -- The materials of the lab, their sheets and the MODULES cut on them (user's handwritten table,
photo of 11/11/2026; names of 12/11/2026; modules per material of 12/11/2026, modular strategy of the supervisor).
Shared by make_materials_pdf.py (inventory) and make_material_cuts_pdf.py (templates drawn on the real sheets).

Sizes: RD x TD in mm, the first value is always the rolling direction (user, 11/11/2026). Sheet ID = material ID +
"-" + number of the sheet in the user's list. A TEMPLATE = one sheet of a module (one DXF sheet, the same every time
it is cut); a module has 1 or 2 templates (see make_module_orders.py). A module entry 'MEDHIGH66@high' = the module
MEDHIGH66 cut for the high rate (same template as for the medium rate, user 12/11/2026).
"""
import csv
import functools
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')

# (name, ID, thickness mm, campaign, sheets [(RD, TD, size text, note)], material note, modules)
MATERIALS = [
    ('DP980', '2020_06_03A', '1.0', 'A',
     [(605, 505, '605 × 505', ''), (598, 502, '598 × 502', ''), (605, 501, '605 × 501', ''),
      (598, 500, '598 × 500', 'edges not straight'), (599, 507, '599 × 507', 'edges not straight'),
      (603, 502, '603 × 502', 'edges not straight'), (596, 500, '596 × 500', 'edges not straight')], '',
     ['SLOW78', 'MEDIUM66', 'HIGH66']),
    ('DC01', '2025_11_25_B', '2.0', 'C medium + high', [(599, 500, '599 × 500', ''), (None, None, 'custom size', '')],
     '', ['MH18']),
    ('S235JR', '2023_02_28_D', '3.0', 'A medium + high', [(600, 500, '600 × 500', '')] * 3, '',
     ['MEDIUM66', 'HIGH66']),
    ('AW5754-H22', '2023_02_28_A', '3.0', 'A medium + high', [(600, 500, '600 × 500', '')] * 4, '',
     ['MEDIUM66', 'HIGH66']),
    ('S355MC', '2023_02_28_C', '3.0', 'A medium + high', [(600, 500, '600 × 500', '')] * 3, '',
     ['MEDIUM66', 'HIGH66']),
    ('RA980', '2022_05_04_D', '1.4', 'A (one large plan)', [(900, 1200, '900 × 1200', '')], '', ['A_LARGE']),
    ('RA1200', '2022_05_04_E', '1.4', 'A (one large plan)', [(913, 1146, '913–915 × 1146', 'RD 913 to 915')], '',
     ['A_LARGE']),
    ('CR1200Y1500T-MS-UNCOATED', '2022_05_04_G', '1.4', 'A (one large plan)', [(916, 1267, '916 × 1267', '')], '',
     ['A_LARGE']),
]

# module -> (order, RD, TD); its templates = the sheets of the order's plan (runs/<order>/ or output/<order>/)
MODULE_ORDERS = {m: ('MOD_%s_600x500mm_WATERJET' % m, 600, 500) for m in ('SLOW78', 'MEDIUM66', 'HIGH66', 'MH18')}
MODULE_ORDERS['A_LARGE'] = ('MOD_A_LARGE_900x1140mm_WATERJET', 900, 1140)
PLAN_RD, PLAN_TD = 600, 500


def plan_dir(order):
    for d in ('output', 'runs'):
        p = os.path.join(ROOT, d, order)
        if os.path.exists(os.path.join(p, 'registry.csv')):
            return p
    raise SystemExit('no plan for order %s: run it first (make_plan.py)' % order)


@functools.lru_cache(None)
def registry(order):
    with open(os.path.join(plan_dir(order), 'registry.csv'), encoding='utf-8') as f:
        return tuple(csv.DictReader(f))


def n_sheets(order):
    return max(int(r['sheet']) for r in registry(order))


def pieces(order, idx):
    """Rows of the registry on sheet idx (0-based) of a plan: one per piece."""
    return [r for r in registry(order) if int(r['sheet']) == idx + 1]


def templates(entry):
    """[(template id, order, index of the sheet in the DXF, RD, TD, module entry)] of a module entry ('MEDHIGH66' or
    'MEDHIGH66@high')."""
    module = entry.split('@')[0]
    order, rd, td = MODULE_ORDERS[module]
    n = n_sheets(order)
    return [(module + ('-%d' % (k + 1) if n > 1 else ''), order, k, rd, td, entry) for k in range(n)]


def label(t):
    """Template id shown on a sheet: 'MEDHIGH66 · high' for a module cut for one rate."""
    return t[0] + (' · ' + t[5].split('@')[1] if '@' in t[5] else '')


def base_tid(tid):
    """'MEDHIGH66 · high' -> 'MEDHIGH66'"""
    return tid.split(' · ')[0]


def module_of(tid):
    """'SLOW78-2' or 'MEDHIGH66 · high' -> module name"""
    return re.sub(r'-\d+$', '', base_tid(tid))


def pretty(entry):
    """'MEDHIGH66@high' -> 'MEDHIGH66 (high)'"""
    return entry.replace('@', ' (') + ')' if '@' in entry else entry


def plans_of(material):
    return [t for m in material[6] for t in templates(m)]


def short(order):
    """MOD_SLOW78_600x500mm_WATERJET -> SLOW78"""
    s = order.rsplit('_', 2)[0]
    return s[4:] if s.startswith('MOD_') else s


def pid(plan):
    """Template id of a plan tuple."""
    return plan[0]


def rank(sheets):
    """Indices of the sheets, best first: the one that holds a 600 x 500 plan with the most room (smallest ratio of
    RD / 600 and TD / 500), then the larger area (user: the largest sheets first)."""
    ok = [i for i, s in enumerate(sheets) if s[0]]
    return sorted(ok, key=lambda i: (-min(sheets[i][0] / PLAN_RD, sheets[i][1] / PLAN_TD),
                                     -sheets[i][0] * sheets[i][1], i))


def _fit(rd, td, placed, prd, ptd):
    """Bottom-left position (x = TD, y = RD) of a plan prd x ptd on a sheet rd x td next to the plans placed, or None.
    A plan of 600 x 500 goes on a sheet of about 600 x 500 (a few mm less allowed: the pieces keep 10 mm)."""
    cands = [(0, 0)] + [(x + w, y) for x, y, h, w in placed] + [(x, y + h) for x, y, h, w in placed]
    for x, y in sorted(set(cands), key=lambda c: (c[1], c[0])):
        if y + prd > rd + 5 or x + ptd > td + 5:
            continue
        if all(x >= qx + qw or x + ptd <= qx or y >= qy + qh or y + prd <= qy for qx, qy, qh, qw in placed):
            return x, y
    return None


def assign(material):
    """[(sheet index, [(template id, order, dxf index, x0, y0, RD, TD)])] and the templates that do not fit: the
    templates of the modules of the material on its sheets, best sheets first, the fullest templates on the best
    sheets (a half-empty second sheet of a module goes last). RD of the template = RD of the sheet, bottom-left
    first (clamp corner)."""
    sheets = material[4]
    plans = sorted(plans_of(material), key=lambda t: -len(pieces(t[1], t[2])))
    out = []
    for i in rank(sheets):
        rd, td = sheets[i][0], sheets[i][1]
        placed, put = [], []
        while plans:
            tid, order, idx, prd, ptd, module = plans[0]
            pos = _fit(rd, td, placed, prd, ptd)
            if pos is None:
                break
            plans.pop(0)
            placed.append((pos[0], pos[1], prd, ptd))
            put.append((label((tid, order, idx, prd, ptd, module)), order, idx, pos[0], pos[1],
                        prd, ptd))
        out.append((i, put))
    return out, plans


def code_check(material):
    """Notch codes of all the specimens cut for a material (every template on its sheets): (number of coded specimens,
    [(alias, code, n)] cut more than once = NOT unique, number of codes shared by different types (told apart by their
    shape: convention of the 2025 drawings)). A code = angle digit + index (index = repeat and strain rate), so it is
    unique per specimen type; two different types may carry the same code."""
    use, missing = assign(material)
    seen = {}
    for i, put in use:
        for p in put:
            for r in pieces(p[1], p[2]):
                if r['notch_code']:
                    seen.setdefault((r['alias'], r['notch_code']), []).append('%s-%d' % (material[1], i + 1))
    dups = [(a, c, len(v)) for (a, c), v in sorted(seen.items()) if len(v) > 1]
    by_code = {}
    for a, c in seen:
        by_code.setdefault(c, set()).add(a)
    shared = sum(1 for c, al in by_code.items() if len(al) > 1)
    return sum(len(v) for v in seen.values()), dups, shared


def dxf_name(t):
    """File name of the DXF of a template in the delivery folder: SLOW78-1_600x500mm.dxf"""
    return '%s_%dx%dmm.dxf' % (base_tid(t[0]), t[3], t[4])
