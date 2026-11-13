# -*- coding: utf-8 -*-
"""
make_module_orders.py -- Orders of the MODULES, waterjet (supervisor's modular strategy, user 12/11/2026). A module
= the specimens of one campaign at one strain rate, cut on its own sheet(s) and reused as it is; a material then gets
a combination of modules.

    py cutting-sheets/scripts/make_module_orders.py        -> cutting-sheets/orders/modules/MOD_<NAME>_<size>mm_WATERJET.yaml

Changes of 12/11/2026 afternoon (user): every UT19 replaced by UT40, so medium and high rate have the same
specimens; they stay separate templates (MEDIUM66 / HIGH66) so that every specimen of a material
keeps a unique notch code (index 4-6 medium, 7-9 high). SLOW70 removed; MEDIUM54 / HIGH54 (campaign B) removed
on 13/11/2026 (not needed). Clamping per module (see CLAMPS).
(A single MEDHIGH template for both rates was tried on 12/11 and dropped: same codes on the medium and high cuts.)

Modules (specimens; shear 2 repeats, the others 3):
    SLOW78     campaign A, slow: 60 tension-type + 18 shear (SHLD, SHMD, SHHD at 0/45/90) + 4 LASER;
               full L clamping 60 mm, edge margin 15 mm
    MEDIUM66   campaign A, medium: 48 tension-type (UT40) + 18 shear; 4 clamps 50 x 40, edge margin 5 mm
    HIGH66     campaign A, high: the same specimens with the high codes (7-9); same clamping
    MH18       campaign C, medium + high on one sheet: 2 x (12 tension-type at 0 deg + 6 shear at 0 deg) = 36 (medium
               codes 4-6, high codes 7-9: both on the same sheet); full L clamping 60 mm, edge margin 15 mm
    A_LARGE    campaign A on one sheet of 900 x 1140 (large sheets): slow 78 + medium 66 + high 66 = 210 + 4 LASER
               (medium 4-6, high 7-9: on the same sheet); 7 clamps 50 x 40: 2 on each short side (left and right,
               at 300 and 600) and 3 on the long bottom side (at 285, 570, 855)
Index of the notch code = strain rate: slow 1-3, medium 4-6, high 7-9 (shear: 1-2, 4-5, 7-8).
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'orders', 'modules')
BASE = os.path.join(HERE, '..', 'orders', 'CAMPAIGN_600x500mm_WATERJET.yaml')

ALL7 = (0, 15, 30, 45, 60, 75, 90)
A3 = (0, 45, 90)
SH_ALL = [(g, a) for g in ('SHLD', 'SHMD', 'SHHD') for a in A3]
SH_C_FAST = [(g, 0) for g in ('SHLD', 'SHMD', 'SHHD')]
FIRST = {'slow': 1, 'medium': 4, 'high': 7}


def part(rate, shear, angles7=ALL7, angles3=A3):
    """[(rate, type, angle, count)] of one strain rate (UT40 at every rate since 12/11/2026)."""
    out = [(rate, 'UT40', a, 3) for a in angles7]
    out += [(rate, t, a, 3) for t in ('NT20', 'NT06', 'CHD48') for a in angles3]
    if rate == 'slow':
        out += [(rate, 'MNAK_RECT_FULL', 0, 3)] + [(rate, 'MNAK_RECT_HOLE', a, 3) for a in A3]
    out += [(rate, g, a, 2) for g, a in shear]
    return out


def single(clamps, width, depth=40):
    return ''.join('  - {side: %-7s at: %d, width: %d, depth: %d}\n' % (s + ',', a, width, depth) for s, a in clamps)


L4 = [('left', 175), ('left', 475), ('bottom', 140), ('bottom', 375)]
CLAMPS = {   # clamping block of each module: (YAML text, edge_margin)
    'L60': ("clamping: {left: 60, bottom: 60}   # full L clamping, 60 mm wide on the left and bottom edges (user,\n"
            "                                   #   12/11/2026: there is room on this module)\n", 15),
    'C50': ("clamps:                # single clamps of the L (user, 10/11/2026): 2 on the left edge, 2 on the bottom edge\n"
            "                       #   at = centre of the clamp, in mm from the bottom-left corner along that edge;\n"
            "                       #   width = along the edge, depth = into the sheet (40 = depth of the L)\n"
            + single(L4, 50), 5),
    'LARGE': ("clamps:                # 7 single clamps 50 x 40 (user, 12/11/2026): 2 on each short side (left, right),\n"
              "                       #   spread at 300 and 600 mm; 3 on the long bottom side, spread at 285, 570, 855 mm\n"
              + single([('left', 300), ('left', 600), ('right', 300), ('right', 600), ('bottom', 285),
                        ('bottom', 570), ('bottom', 855)], 50), 5),
}

# name: (title, rows, LASER, expected number of coded specimens, sheet, clamping)
MODULES = {
    'SLOW78': ('campaign A, slow rate', part('slow', SH_ALL), 4, 78, '600x500', 'L60'),
    'MEDIUM66': ('campaign A, medium rate', part('medium', SH_ALL), 0, 66, '600x500', 'C50'),
    'HIGH66': ('campaign A, high rate', part('high', SH_ALL), 0, 66, '600x500', 'C50'),
    'MH18': ('campaign C, medium + high on one sheet',
             part('medium', SH_C_FAST, (0,), (0,)) + part('high', SH_C_FAST, (0,), (0,)), 0, 36, '600x500', 'L60'),
}
# large sheets (user, 12/11/2026): the whole campaign A on one plan of 900 (RD) x 1140 (TD) mm, which fits on the
# three large sheets (900 x 1200, 913 x 1146, 916 x 1267)
LARGE = {'A_LARGE': ('campaign A on one large sheet (= SLOW78 + MEDIUM66 + HIGH66)',
                     part('slow', SH_ALL) + part('medium', SH_ALL) + part('high', SH_ALL), 4, 210, '900x1140', 'LARGE')}


def write(name, title, rows, n_laser, expected, sheet, clamping):
    n = sum(r[3] for r in rows)
    assert n == expected, (name, n, expected)
    base = open(BASE, encoding='utf-8').read()
    i0, i1, i2 = base.index('templates:'), base.index('# ---------- Specimens: one line'), base.index('specimens:\n')
    order = 'MOD_%s_%smm_WATERJET' % (name, sheet)
    rd, td = (int(v) for v in sheet.split('x'))
    head = ("# Module %s: %s, waterjet, sheets of %d (RD) x %d (TD) mm.\n"
            "# Written by scripts/make_module_orders.py (modular strategy, user 12/11/2026): %d specimens + %d LASER.\n"
            "# Index of the notch code = strain rate: slow 1-3, medium 4-6, high 7-9 (shear: 1-2, 4-5, 7-8).\n"
            "# Run from the repository root:\n"
            "#   py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/modules/%s.yaml\n\nname: %s\n"
            % (name, title, rd, td, n, n_laser, order, order))
    body = base[i0:i1].replace("spread_tries: 3        # 3 here: seed 1, 2, 3 tried (seed 2 left 1 pair on 10/11)",
                               "spread_tries: 3        # 3 placements tried: seed 1, 2, 3")
    block, edge = CLAMPS[clamping]
    body = re.sub(r'clamps:.*?\n(?=clamp_margin:)', lambda m: block, body, flags=re.S)
    body = re.sub(r'edge_margin: 5 ', 'edge_margin: %-2d' % edge, body)
    body = re.sub(r'# -> effective area.*?\n(?=\n)', '# -> effective area: see preview.png (zones of the sheet)\n', body,
                  flags=re.S)
    if sheet != '600x500':
        a = 'sheet: 600x500         # complete sheet, RD x TD: rolling direction first (required)'
        assert body.count(a) == 1
        body = body.replace(a, 'sheet: %-15s# complete sheet, RD x TD: rolling direction first (required)' % sheet)
        body = body.replace('time: 10               #', 'time: 30               #')
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
