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

# cutting plans of 600 (RD) x 500 (TD) of each campaign, in order: (label, order, index of the sheet in its DXF)
PLANS = {'A': [('sheet 1', 'CAMPAIGN', 0), ('sheet 2', 'AB_SHEETS23', 0), ('sheet 3', 'AB_SHEETS23', 1),
               ('sheet 4', 'A_SHEET4', 0)],
         'B': [('sheet 1', 'CAMPAIGN', 0), ('sheet 2', 'AB_SHEETS23', 0), ('sheet 3', 'AB_SHEETS23', 1)],
         'C': [('sheet 1', 'CAMPAIGN', 0), ('sheet 2', 'C_SHEET2', 0)]}
PLAN_RD, PLAN_TD = 600, 500


def rank(sheets):
    """Indices of the sheets, best first: the one that holds a 600 x 500 plan with the most room (smallest ratio of
    RD / 600 and TD / 500), then the larger area (user: the largest sheets first)."""
    ok = [i for i, s in enumerate(sheets) if s[0]]
    return sorted(ok, key=lambda i: (-min(sheets[i][0] / PLAN_RD, sheets[i][1] / PLAN_TD),
                                     -sheets[i][0] * sheets[i][1], i))


def assign(material):
    """[(sheet index, [(plan label, order, dxf index, x0, y0)])]: the plans of the campaign of the material placed on
    its sheets. Plans are kept with their RD along the RD of the sheet (no 90 deg turn): a 600 x 500 sheet holds 1
    plan, a large sheet holds floor(RD / 600) x floor(TD / 500) plans side by side. The fullest plans go on the best
    sheets. Returns also the plans that do not fit."""
    name, mid, thk, camp, sheets, note, drawn = material
    plans = list(PLANS.get(camp, []))
    out = []
    for i in rank(sheets):
        rd, td = sheets[i][0], sheets[i][1]
        slots = [(k * PLAN_TD, j * PLAN_RD) for j in range(max(1, rd // PLAN_RD)) for k in range(max(1, td // PLAN_TD))]
        put = []
        for x0, y0 in slots:
            if not plans:
                break
            label, order, idx = plans.pop(0)
            put.append((label, order, idx, x0, y0))
        out.append((i, put))
    return out, plans
