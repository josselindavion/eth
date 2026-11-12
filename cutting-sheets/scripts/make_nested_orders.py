# -*- coding: utf-8 -*-
"""
make_nested_orders.py -- Orders of campaigns A, B and C as nested sheets (user, 12/11/2026). The campaigns are nested
(C in B in A, same notch codes), so their sheets are shared:
    sheet 1      (A, B, C)  the 60 slow-rate tension-type specimens + 1 LASER = orders/CAMPAIGN_600x500mm_WATERJET
                            (already made and checked, kept as it is)
    sheets 2-3   (A, B)     the rest of B (+ LASER)                   -> AB_SHEETS23_600x500mm_WATERJET (2 sheets)
    sheet 4      (A)        A minus B: SHLD, SHHD at 45, 90 deg       -> A_SHEET4_600x500mm_WATERJET
    sheet 2 of C (C)        the rest of C (+ LASER)                   -> C_SHEET2_600x500mm_WATERJET
So A = sheets 1, 2, 3, 4; B = sheets 1, 2, 3; C = sheet 1 + its own sheet 2. The shear specimens may now be mixed
with the others (user, 12/11/2026). LASER: 4 per campaign (1 on sheet 1, 3 on sheets 2-3 for A and B, 3 on C's
sheet 2); A's sheet 4 gets none (A already has 4).

    py cutting-sheets/scripts/make_nested_orders.py
"""
import collections
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_campaign_orders import campaign, SH, FIRST   # noqa: E402

ORDERS = os.path.join(HERE, '..', 'orders')
SHEET1 = os.path.join(ORDERS, 'CAMPAIGN_600x500mm_WATERJET.yaml')
N_LASER = {'AB_SHEETS23': 3, 'C_SHEET2': 3, 'A_SHEET4': 0}


def bag(rows):
    """Counter of (rate, type, angle) -> count."""
    c = collections.Counter()
    for rate, t, a, n in rows:
        c[(rate, t, a)] += n
    return c


A = bag(campaign(SH))
B = bag(campaign(('SHMD',)))
C = bag(campaign(('SHMD',), fast_angles=(0,)))
assert not (B - A) and not (C - B), 'campaigns are not nested'
# sheet 1: what the existing order holds (slow rate, index 1-3)
S1 = collections.Counter()
for l in yaml.safe_load(open(SHEET1, encoding='utf-8'))['specimens']:
    if l['type'] != 'LASER':
        assert l.get('first_index') == FIRST['slow'], 'sheet 1 must use the slow-rate indices'
        S1[('slow', l['type'], l['angle'])] += l['count']
assert not (S1 - C), 'sheet 1 is not inside campaign C'


def write(name, title, content):
    base = open(SHEET1, encoding='utf-8').read()
    i0, i1, i2 = base.index('templates:'), base.index('# ---------- Placement (time budget) ----------'), \
        base.index('specimens:\n')
    i3 = base.index('# ---------- Specimens: one line')
    place = base[i1:i3]
    if name == 'AB_SHEETS23':                           # 2 sheets to reach: more tries and time, 3 placements
        place = place.replace('fill_tries: 8          #', 'fill_tries: 14         #').replace(
            'fill_time: 10          #', 'fill_time: 15          #').replace('time: 10               #',
                                                                       'time: 15               #')
    place = place.replace('spread_tries: 3        # 3 here: seed 1, 2, 3 tried (seed 2 left 1 pair on 10/11)',
                          'spread_tries: 3        # 3 placements tried (fewest sheets kept): 2 sheets must be reached'
                          if name == 'AB_SHEETS23' else
                          'spread_tries: 1        # placements tried to keep the repeats apart')
    n_laser = N_LASER[name]
    lines = ['specimens:']
    n = 0
    for rate in ('slow', 'medium', 'high'):
        rows = [(k, v) for k, v in sorted(content.items()) if k[0] == rate]
        if rows:
            lines.append('  # %s rate' % rate)
        for (r, t, a), c in sorted(rows, key=lambda kv: (kv[0][1].startswith('SH'), kv[0][1], kv[0][2])):
            lines.append('  - {type: %-16s angle: %-4s count: %d, first_index: %d}' % (t + ',', '%d,' % a, c,
                                                                                       FIRST[rate]))
            n += c
    if n_laser:
        lines += ['  # speckle contrast strips (no code)', '  - {type: LASER,           angle: 0,   count: %d}'
                  % n_laser]
    full = name + '_600x500mm_WATERJET'
    head = ('# %s\n# Written by scripts/make_nested_orders.py (nested campaigns, user 12/11/2026): %d specimens + %d '
            'LASER.\n# Index of the notch code = strain rate: slow 1-3, medium 4-6, high 7-9 (shear: 1-2, 4-5, 7-8).\n'
            '# Run from the repository root:\n#   py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/%s.yaml'
            '\n\nname: %s\n' % (title, n, n_laser, full, full))
    body = base[i0:i1].replace('name: CAMPAIGN_600x500mm_WATERJET', '')
    with open(os.path.join(ORDERS, full + '.yaml'), 'w', encoding='utf-8') as f:
        f.write(head + body + place + base[i3:i2] + '\n'.join(lines) + '\n')
    print('written %s (%d specimens + %d LASER)' % (full, n, n_laser))


write('AB_SHEETS23', 'Campaigns A and B, sheets 2 and 3 (common to A and B): the rest of B after sheet 1', B - S1)
write('A_SHEET4', 'Campaign A, sheet 4 (A only): A minus B = SHLD and SHHD at 45 and 90 deg, all rates', A - B)
write('C_SHEET2', 'Campaign C, sheet 2 (C only): the rest of C after sheet 1', C - S1)
print('sheet 1 (A, B, C): %d specimens + 1 LASER, B - sheet 1: %d, A - B: %d, C - sheet 1: %d'
      % (sum(S1.values()), sum((B - S1).values()), sum((A - B).values()), sum((C - S1).values())))
