# -*- coding: utf-8 -*-
"""
make_campaign_orders.py -- Writes the orders of campaigns A and B on 600 x 500 sheets (waterjet), from the campaign
rules of 11/11/2026 (same rules as make_campaigns_pdf.py). Sheet block, clamps and placement settings are copied from
orders/CAMPAIGN_600x500mm_WATERJET.yaml.

    py cutting-sheets/scripts/make_campaign_orders.py [n_laser]        (default 4 LASER strips: 2 at first, + 2 asked
                                                                        by the user on 11/11/2026 for the last common sheet)

Index of the notch code = strain rate, the same for every type: slow 1-3, medium 4-6, high 7-9 (shear, 2 repeats:
1-2, 4-5, 7-8), so that specimens of the same type and angle at different rates have different codes.
The shear specimens are ALONE on their sheets (user, 11/11/2026). Written into orders/campaign_sources/:
TENSION_AB_600x500mm_WATERJET (tension-type specimens + LASER, the same for A and B), SHEAR_A_600x500mm_WATERJET and
SHEAR_B_600x500mm_WATERJET (shear only). They are the SOURCES of split_campaigns.py, which writes the orders of the
sheets themselves (2 common sheets, sheets of A, sheet of B).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ORDERS = os.path.join(HERE, '..', 'orders', 'campaign_sources')    # sources of split_campaigns.py
BASE = os.path.join(HERE, '..', 'orders', 'CAMPAIGN_600x500mm_WATERJET.yaml')
N_LASER = int(sys.argv[1]) if len(sys.argv) > 1 and __name__ == '__main__' else 4

ALL7 = (0, 15, 30, 45, 60, 75, 90)
A3 = (0, 45, 90)
SH = ('SHLD', 'SHMD', 'SHHD')
FIRST = {'slow': 1, 'medium': 4, 'high': 7}


def campaign(shear_45_90, fast_angles=None):
    """[(rate, type, angle, count)] of campaign A (shear_45_90 = SH), B (shear_45_90 = ('SHMD',)) or C (as B, and
    fast_angles = (0,): medium and high rate at 0 deg only, UT included)."""
    out = []
    for rate in ('slow', 'medium', 'high'):
        ut = 'UT19' if rate == 'high' else 'UT40'
        ang7 = ALL7 if rate == 'slow' or fast_angles is None else fast_angles
        ang3 = A3 if rate == 'slow' or fast_angles is None else fast_angles
        out += [(rate, ut, a, 3) for a in ang7]
        out += [(rate, t, a, 3) for t in ('NT20', 'NT06', 'CHD48') for a in ang3]
        if rate == 'slow':
            out += [(rate, 'MNAK_RECT_FULL', 0, 3)] + [(rate, 'MNAK_RECT_HOLE', a, 3) for a in A3]
        out += [(rate, g, a, 2) for g in SH for a in ang3 if a == 0 or g in shear_45_90]
    return out


def write(letter, title, rows, shear=False):
    base = open(BASE, encoding='utf-8').read()
    i0 = base.index("templates:")
    i1 = base.index("# ---------- Specimens: one line")
    i2 = base.index("specimens:\n")
    rows = [r for r in rows if r[1].startswith('SH') == shear]
    name = 'SHEAR_%s_600x500mm_WATERJET' % letter if shear else 'TENSION_AB_600x500mm_WATERJET'
    n_laser = 0 if shear else N_LASER
    n = sum(r[3] for r in rows)
    who = ('Campaign %s (%s) for one material, SHEAR SPECIMENS ONLY' % (letter, title) if shear else
           'Campaigns A and B, tension-type specimens (the same in both)')
    head = ("# %s, waterjet cutting on sheets of 600 (RD) x 500 (TD) mm,\n"
            "# written by scripts/make_campaign_orders.py from the campaign rules of 11/11/2026 (campaigns PDF\n"
            "# campaigns/DP_test_campaigns_Beerli2026.pdf): %d specimens + %d LASER strips.\n# %s\n"
            "# Index of the notch code = strain rate: slow 1-3, medium 4-6, high 7-9 (shear: 1-2, 4-5, 7-8).\n"
            "# Run from the repository root:\n"
            "#   py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/campaign_sources/%s.yaml\n\n"
            "name: %s\n" % (who, n, n_laser, 'Shear specimens alone on their sheets (then finished by wire EDM). SOURCE of '
                             'split_campaigns.py.' if shear else 'Same for campaigns A and B (they differ only by their '
                             'shear: SHEAR_A, SHEAR_B). SOURCE of split_campaigns.py.', name, name))
    body = base[i0:i1].replace("spread_tries: 3        # 3 here: seed 1, 2, 3 tried (seed 2 left 1 pair on 10/11)",
                               "spread_tries: 1        # placements tried to keep the repeats apart")
    lines = ["specimens:"]
    for rate in ('slow', 'medium', 'high'):
        lines.append("  # %s rate" % rate)
        for r, t, a, c in rows:
            if r == rate:
                lines.append("  - {type: %-16s angle: %-4s count: %d, first_index: %d}"
                             % (t + ',', '%d,' % a, c, FIRST[rate]))
    if n_laser:
        lines.append("  # speckle contrast strips (no code)")
        lines.append("  - {type: LASER,           angle: 0,   count: %d}" % n_laser)
    path = os.path.join(ORDERS, name + '.yaml')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(head + body + base[i1:i2] + '\n'.join(lines) + '\n')
    print('written %s (%d specimens + %d LASER)' % (path, n, n_laser))


if __name__ == '__main__':                              # campaign() is also used by make_nested_orders.py
    write('A', 'full', campaign(SH))                    # tension-type: the same for A and B
    write('A', 'full', campaign(SH), True)
    write('B', 'A without SHLD, SHHD at 45, 90 deg', campaign(('SHMD',)), True)
