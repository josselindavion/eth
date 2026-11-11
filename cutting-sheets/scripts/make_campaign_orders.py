# -*- coding: utf-8 -*-
"""
make_campaign_orders.py -- Writes the orders of campaigns A and B on 600 x 500 sheets (waterjet), from the campaign
rules of 11/11/2026 (same rules as make_campaigns_pdf.py). Sheet block, clamps and placement settings are copied from
orders/CAMPAIGN_600x500mm_WATERJET.yaml.

    py cutting-sheets/scripts/make_campaign_orders.py [n_laser]        (default 2 LASER strips)

Index of the notch code = strain rate, the same for every type: slow 1-3, medium 4-6, high 7-9 (shear, 2 repeats:
1-2, 4-5, 7-8), so that specimens of the same type and angle at different rates have different codes.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ORDERS = os.path.join(HERE, '..', 'orders')
BASE = os.path.join(ORDERS, 'CAMPAIGN_600x500mm_WATERJET.yaml')
N_LASER = int(sys.argv[1]) if len(sys.argv) > 1 else 2

ALL7 = (0, 15, 30, 45, 60, 75, 90)
A3 = (0, 45, 90)
SH = ('SHLD', 'SHMD', 'SHHD')
FIRST = {'slow': 1, 'medium': 4, 'high': 7}


def campaign(shear_45_90):
    """[(rate, type, angle, count)] of campaign A (shear_45_90 = SH) or B (shear_45_90 = ('SHMD',))."""
    out = []
    for rate in ('slow', 'medium', 'high'):
        ut = 'UT19' if rate == 'high' else 'UT40'
        out += [(rate, ut, a, 3) for a in ALL7]
        out += [(rate, t, a, 3) for t in ('NT20', 'NT06', 'CHD48') for a in A3]
        if rate == 'slow':
            out += [(rate, 'MNAK_RECT_FULL', 0, 3)] + [(rate, 'MNAK_RECT_HOLE', a, 3) for a in A3]
        out += [(rate, g, a, 2) for g in SH for a in A3 if a == 0 or g in shear_45_90]
    return out


def write(letter, title, rows):
    base = open(BASE, encoding='utf-8').read()
    i0 = base.index("templates:")
    i1 = base.index("# ---------- Specimens: one line")
    i2 = base.index("specimens:\n")
    name = 'CAMPAIGN_%s_600x500mm_WATERJET' % letter
    n = sum(r[3] for r in rows)
    head = ("# Campaign %s (%s) for one material, waterjet cutting on sheets of 600 (RD) x 500 (TD) mm, written by\n"
            "# scripts/make_campaign_orders.py from the campaign rules of 11/11/2026 (campaigns PDF\n"
            "# campaigns/DP_test_campaigns_Beerli2026.pdf): %d specimens + %d LASER strips. Shear specimens are cut here\n"
            "# (waterjet), then finished by wire EDM. Index of the notch code = strain rate: slow 1-3, medium 4-6,\n"
            "# high 7-9 (shear: 1-2, 4-5, 7-8).\n"
            "# Run from the repository root:\n"
            "#   py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/%s.yaml\n\n"
            "name: %s\n" % (letter, title, n, N_LASER, name, name))
    body = base[i0:i1].replace("spread_tries: 3        # 3 here: seed 1, 2, 3 tried (seed 2 left 1 pair on 10/11)",
                               "spread_tries: 1        # placements tried to keep the repeats apart")
    lines = ["specimens:"]
    for rate in ('slow', 'medium', 'high'):
        lines.append("  # %s rate" % rate)
        for r, t, a, c in rows:
            if r == rate:
                lines.append("  - {type: %-16s angle: %-4s count: %d, first_index: %d}"
                             % (t + ',', '%d,' % a, c, FIRST[rate]))
    if N_LASER:
        lines.append("  # speckle contrast strips (no code)")
        lines.append("  - {type: LASER,           angle: 0,   count: %d}" % N_LASER)
    path = os.path.join(ORDERS, name + '.yaml')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(head + body + base[i1:i2] + '\n'.join(lines) + '\n')
    print('written %s (%d specimens + %d LASER)' % (path, n, N_LASER))


write('A', 'full', campaign(SH))
write('B', 'space a little short: A without SHLD and SHHD at 45 and 90 deg', campaign(('SHMD',)))
