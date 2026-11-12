# -*- coding: utf-8 -*-
"""
materials_data.py -- The materials of the lab and their sheets (user's handwritten table, photo of 11/11/2026; names
and campaigns given by the user on 12/11/2026). Shared by make_materials_pdf.py (inventory) and
make_material_cuts_pdf.py (cutting plans drawn on the real sheets).

Sizes: RD x TD in mm, the first value is always the rolling direction (user, 11/11/2026). Sheet ID = material ID +
"-" + number of the sheet in the user's list. Campaign: A, B or C (see make_campaigns_pdf.py), '' = not decided.
"""

# (name, ID, thickness mm, campaign, sheets [(RD, TD, size text, note)], material note, drawn?)
MATERIALS = [
    ('DP980', '2020_06_03A', '1.0', 'A',
     [(605, 505, '605 × 505', ''), (598, 502, '598 × 502', ''), (605, 501, '605 × 501', ''),
      (598, 500, '598 × 500', 'edges not straight'), (599, 507, '599 × 507', 'edges not straight'),
      (603, 502, '603 × 502', 'edges not straight'), (596, 500, '596 × 500', 'edges not straight')], '', True),
    ('DC01', '2025_11_25_B', '2.0', 'C', [(599, 500, '599 × 500', ''), (None, None, 'custom size', '')],
     'cutting: later', False),
    ('S235JR', '2023_02_28_D', '3.0', 'B', [(600, 500, '600 × 500', '')] * 3, '', True),
    ('AW5754-H22', '2023_02_28_A', '3.0', 'A', [(600, 500, '600 × 500', '')] * 4, '', True),
    ('S355MC', '2023_02_28_C', '3.0', 'B', [(600, 500, '600 × 500', '')] * 3, '', True),
    ('RA980', '2022_05_04_D', '1.4', 'B', [(900, 1200, '900 × 1200', '')], '', True),
    ('RA1200', '2022_05_04_E', '1.4', 'B', [(913, 1146, '913–915 × 1146', 'RD 913 to 915')], '',
     True),
    ('CR1200Y1500T-MS-UNCOATED', '2022_04_04_G', '1.4', 'B', [(916, 1267, '916 × 1267', '')], '', True),
]

# cutting plans of each campaign, in order: (label, order, index of the sheet in its DXF, RD, TD). Orders in orders/
# (name + '.yaml'); the plans are read from their DXF in output/ or runs/.
P1 = ('sheet 1', 'CAMPAIGN_600x500mm_WATERJET', 0, 600, 500)
P_AB = [('sheet 2', 'AB_SHEETS23_600x500mm_WATERJET', 0, 600, 500),
        ('sheet 3', 'AB_SHEETS23_600x500mm_WATERJET', 1, 600, 500)]
PLANS = {'A': [P1] + P_AB + [('sheet 4', 'A_SHEET4_600x500mm_WATERJET', 0, 600, 500)],
         'B': [P1] + P_AB,
         'C': [P1, ('sheet 2', 'C_SHEET2_600x500mm_WATERJET', 0, 600, 500)]}
# on the large sheets, campaign B is one plan of 900 x 1146 that replaces its 3 sheets (user, 12/11/2026): the same
# specimens and codes; the 600 x 500 plans stay for the 600 x 500 sheets
PLANS_LARGE = {'B': [('campaign B (one plan)', 'B_LARGE_900x1146mm_WATERJET', 0, 900, 1146)]}
PLAN_RD, PLAN_TD = 600, 500
LARGE_RD = 900                                               # a sheet with RD >= 900 mm is a large sheet


def short(order):
    """CAMPAIGN_600x500mm_WATERJET -> CAMPAIGN"""
    return order.rsplit('_', 2)[0]


def plans_of(material):
    camp, sheets = material[3], material[4]
    if camp in PLANS_LARGE and any(sh[0] and sh[0] >= LARGE_RD for sh in sheets):
        return PLANS_LARGE[camp]
    return PLANS.get(camp, [])


def rank(sheets):
    """Indices of the sheets, best first: the one that holds a 600 x 500 plan with the most room (smallest ratio of
    RD / 600 and TD / 500), then the larger area (user: the largest sheets first)."""
    ok = [i for i, s in enumerate(sheets) if s[0]]
    return sorted(ok, key=lambda i: (-min(sheets[i][0] / PLAN_RD, sheets[i][1] / PLAN_TD),
                                     -sheets[i][0] * sheets[i][1], i))


def _fit(rd, td, placed, prd, ptd):
    """Bottom-left position (x = TD, y = RD) of a plan prd x ptd on a sheet rd x td next to the plans placed, or None.
    A plan of 600 x 500 always goes on a sheet of about 600 x 500 (a few mm less allowed: the pieces keep 10 mm)."""
    cands = [(0, 0)] + [(x + w, y) for x, y, h, w in placed] + [(x, y + h) for x, y, h, w in placed]
    for x, y in sorted(set(cands), key=lambda c: (c[1], c[0])):
        if y + prd > rd + 5 or x + ptd > td + 5:
            continue
        if all(x >= qx + qw or x + ptd <= qx or y >= qy + qh or y + prd <= qy for qx, qy, qh, qw in placed):
            return x, y
    return None


def assign(material):
    """[(sheet index, [(plan label, order, dxf index, x0, y0, RD, TD)])] and the plans that do not fit: the plans of
    the campaign of the material placed on its sheets, best sheets first, the fullest plans on the best sheets. Plans
    keep their RD along the RD of the sheet (no 90 deg turn), bottom-left first (clamp corner); a large sheet holds
    several plans side by side (cut it into blanks first)."""
    sheets = material[4]
    plans = list(plans_of(material))
    out = []
    for i in rank(sheets):
        rd, td = sheets[i][0], sheets[i][1]
        placed, put = [], []
        while plans:
            label, order, idx, prd, ptd = plans[0]
            pos = _fit(rd, td, placed, prd, ptd)
            if pos is None:
                break
            plans.pop(0)
            placed.append((pos[0], pos[1], prd, ptd))
            put.append((label, order, idx, pos[0], pos[1], prd, ptd))
        out.append((i, put))
    return out, plans
