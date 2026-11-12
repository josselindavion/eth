# -*- coding: utf-8 -*-
"""
make_module_orders.py -- Orders of the MODULES on 600 (RD) x 500 (TD) sheets, waterjet (supervisor's modular
strategy, user 12/11/2026). A module = the specimens of one campaign at one strain rate, cut on its own sheet(s) and
reused as it is; a material then gets a combination of modules. Medium and high rate are different modules (codes
4-6 vs 7-9, UT40 at medium vs UT19 at high). The medium and high modules of campaign C are combined on one sheet
(module MH18 = medium 18 + high 18).

    py cutting-sheets/scripts/make_module_orders.py        -> cutting-sheets/orders/modules/MOD_<NAME>_600x500mm_WATERJET.yaml

Modules (specimens; shear 2 repeats, the others 3):
    SLOW78   campaign A, slow:   60 tension-type + 18 shear (SHLD, SHMD, SHHD at 0/45/90) + 4 LASER
    MEDIUM66 campaign A, medium: 48 tension-type (UT40) + 18 shear
    HIGH66   campaign A, high:   48 tension-type (UT19) + 18 shear
    SLOW70   campaigns B and C, slow: 60 tension-type + 10 shear (SHMD 0/45/90, SHLD 0, SHHD 0) + 4 LASER
    MEDIUM54 campaign B, medium: 48 tension-type (UT40) + 6 shear (SHMD 0/45/90; no SHLD, SHHD: user 12/11/2026)
    HIGH54   campaign B, high:   48 tension-type (UT19) + 6 shear (SHMD 0/45/90)
    MH18     campaign C, medium + high on one sheet: 2 x (12 tension-type at 0 deg + 6 shear at 0 deg) = 36
    A_LARGE  campaign A on one sheet of 900 x 1140 (large sheets): SLOW78 + MEDIUM66 + HIGH66 = 210 + 4 LASER
Index of the notch code = strain rate: slow 1-3, medium 4-6, high 7-9 (shear: 1-2, 4-5, 7-8).
LASER: 4 per material, on the slow module (its second sheet has room); to confirm with the supervisor.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'orders', 'modules')
BASE = os.path.join(HERE, '..', 'orders', 'CAMPAIGN_600x500mm_WATERJET.yaml')

ALL7 = (0, 15, 30, 45, 60, 75, 90)
A3 = (0, 45, 90)
SH_ALL = [(g, a) for g in ('SHLD', 'SHMD', 'SHHD') for a in A3]
SH_B = [('SHMD', a) for a in A3] + [('SHLD', 0), ('SHHD', 0)]
SH_B_FAST = [('SHMD', a) for a in A3]
SH_C_FAST = [(g, 0) for g in ('SHLD', 'SHMD', 'SHHD')]
FIRST = {'slow': 1, 'medium': 4, 'high': 7}


def part(rate, shear, angles7=ALL7, angles3=A3):
    """[(rate, type, angle, count)] of one strain rate."""
    ut = 'UT19' if rate == 'high' else 'UT40'
    out = [(rate, ut, a, 3) for a in angles7]
    out += [(rate, t, a, 3) for t in ('NT20', 'NT06', 'CHD48') for a in angles3]
    if rate == 'slow':
        out += [(rate, 'MNAK_RECT_FULL', 0, 3)] + [(rate, 'MNAK_RECT_HOLE', a, 3) for a in A3]
    out += [(rate, g, a, 2) for g, a in shear]
    return out


# name: (title, rows, LASER, expected number of coded specimens)
MODULES = {
    'SLOW78': ('campaign A, slow rate', part('slow', SH_ALL), 4, 78),
    'MEDIUM66': ('campaign A, medium rate', part('medium', SH_ALL), 0, 66),
    'HIGH66': ('campaign A, high rate', part('high', SH_ALL), 0, 66),
    'SLOW70': ('campaigns B and C, slow rate', part('slow', SH_B), 4, 70),
    'MEDIUM54': ('campaign B, medium rate (no SHLD, SHHD)', part('medium', SH_B_FAST), 0, 54),
    'HIGH54': ('campaign B, high rate (no SHLD, SHHD)', part('high', SH_B_FAST), 0, 54),
    'MH18': ('campaign C, medium + high on one sheet',
             part('medium', SH_C_FAST, (0,), (0,)) + part('high', SH_C_FAST, (0,), (0,)), 0, 36),
}
# large sheets (user, 12/11/2026): the whole campaign A on one plan of 900 (RD) x 1140 (TD) mm, which fits on the
# three large sheets (900 x 1200, 913 x 1146, 916 x 1267); same specimens and codes as SLOW78 + MEDIUM66 + HIGH66
LARGE = {'A_LARGE': ('campaign A on one large sheet (= SLOW78 + MEDIUM66 + HIGH66)',
                     part('slow', SH_ALL) + part('medium', SH_ALL) + part('high', SH_ALL), 4, 210, '900x1140')}


def write(name, title, rows, n_laser, expected, sheet='600x500'):
    n = sum(r[3] for r in rows)
    assert n == expected, (name, n, expected)
    base = open(BASE, encoding='utf-8').read()
    i0, i1, i2 = base.index('templates:'), base.index('# ---------- Specimens: one line'), base.index('specimens:\n')
    order = 'MOD_%s_%smm_WATERJET' % (name, sheet)
    head = ("# Module %s: %s, waterjet, sheets of %s (RD) x %s (TD) mm.\n"
            "# Written by scripts/make_module_orders.py (modular strategy, user 12/11/2026): %d specimens + %d LASER.\n"
            "# Index of the notch code = strain rate: slow 1-3, medium 4-6, high 7-9 (shear: 1-2, 4-5, 7-8).\n"
            "# Run from the repository root:\n"
            "#   py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/modules/%s.yaml\n\nname: %s\n"
            % (name, title, sheet.split('x')[0], sheet.split('x')[1], n, n_laser, order, order))
    body = base[i0:i1].replace("spread_tries: 3        # 3 here: seed 1, 2, 3 tried (seed 2 left 1 pair on 10/11)",
                               "spread_tries: 3        # 3 placements tried: seed 1, 2, 3")
    if sheet != '600x500':
        a = 'sheet: 600x500         # complete sheet, RD x TD: rolling direction first (required)'
        assert body.count(a) == 1
        body = body.replace(a, 'sheet: %-15s# complete sheet, RD x TD: rolling direction first (required)' % sheet)
        body = body.replace('time: 10               #', 'time: 30               #')
        body = body.replace('# -> effective area (where the specimens go) = 580 (RD) x 480 (TD) mm',
                            '# -> effective area (where the specimens go) = %d (RD) x %d (TD) mm'
                            % (int(sheet.split('x')[0]) - 20, int(sheet.split('x')[1]) - 20))
    lines = ['specimens:']
    for rate in ('slow', 'medium', 'high'):
        rr = [r for r in rows if r[0] == rate]
        if rr:
            lines.append('  # %s rate' % rate)
        for r, t, a, c in rr:
            lines.append('  - {type: %-16s angle: %-4s count: %d, first_index: %d}' % (t + ',', '%d,' % a, c,
                                                                                       FIRST[rate]))
    if n_laser:
        lines.append('  # speckle contrast strips (no code)')
        lines.append('  - {type: LASER,           angle: 0,   count: %d}' % n_laser)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, order + '.yaml')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(head + body + base[i1:i2] + '\n'.join(lines) + '\n')
    print('written %s (%d specimens + %d LASER)' % (os.path.relpath(path), n, n_laser))


if __name__ == '__main__':
    for k, v in list(MODULES.items()) + list(LARGE.items()):
        write(k, *v)
