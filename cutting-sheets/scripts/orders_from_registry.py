# -*- coding: utf-8 -*-
"""
orders_from_registry.py -- Writes an order with the specimens of some sheets of a plan already made (its
registry.csv), keeping their notch codes (same type, angle and index), optionally + the specimens of other orders and
LASER strips. Used to split a plan into sheets common to several campaigns and sheets of each campaign
(user, 11/11/2026). The sheet block, clamps and placement settings are copied from a base order.

    py cutting-sheets/scripts/orders_from_registry.py REGISTRY --sheets 1,2 --name NAME --base ORDER
                                                      [--add ORDER ...] [--laser N] [--title TEXT]
"""
import argparse
import collections
import csv
import os
import textwrap

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ORDERS = os.path.join(HERE, '..', 'orders')


def runs(indices):
    """[1, 2, 3, 5] -> [(1, 3), (5, 1)]: (first index, count) of consecutive indices."""
    out = []
    for i in sorted(indices):
        if out and i == out[-1][0] + out[-1][1]:
            out[-1] = (out[-1][0], out[-1][1] + 1)
        else:
            out.append((i, 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('registry')
    ap.add_argument('--sheets', required=True, help='sheets of the plan to take, e.g. 1,2')
    ap.add_argument('--name', required=True)
    ap.add_argument('--base', required=True, help='order whose sheet block and settings are copied')
    ap.add_argument('--add', nargs='*', default=[], help='orders whose specimens are added')
    ap.add_argument('--laser', type=int, default=0, help='LASER strips added')
    ap.add_argument('--title', default='')
    a = ap.parse_args()
    sheets = set(a.sheets.split(','))
    groups, n_laser = collections.defaultdict(list), a.laser
    with open(a.registry, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['sheet'] not in sheets:
                continue
            if r['alias'] == 'LASER':
                n_laser += 1
            else:
                groups[(r['alias'], int(float(r['angle_deg'])))].append(int(r['index']))
    src = os.path.relpath(a.registry, os.path.join(HERE, '..', '..'))
    lines = ['specimens:', '  # from sheet(s) %s of %s' % (a.sheets, src)]
    n = 0
    for (alias, ang), idx in sorted(groups.items(), key=lambda kv: (kv[0][0].startswith('SH'), kv[0])):
        for first, count in runs(idx):
            lines.append('  - {type: %-16s angle: %-4s count: %d, first_index: %d}' % (alias + ',', '%d,' % ang, count,
                                                                                       first))
            n += count
    for o in a.add:
        lines.append('  # from %s' % os.path.basename(o))
        for l in yaml.safe_load(open(o, encoding='utf-8'))['specimens']:
            if l['type'] == 'LASER':
                n_laser += l['count']
                continue
            lines.append('  - {type: %-16s angle: %-4s count: %d, first_index: %d}'
                         % (l['type'] + ',', '%d,' % l['angle'], l['count'], l.get('first_index', 0)))
            n += l['count']
    if n_laser:
        lines.append('  # speckle contrast strips (no code)')
        lines.append('  - {type: LASER,           angle: 0,   count: %d}' % n_laser)
    base = open(a.base, encoding='utf-8').read()
    i0, i1, i2 = base.index('templates:'), base.index('# ---------- Specimens: one line'), base.index('specimens:\n')
    head = ('%s\n# Written by scripts/orders_from_registry.py: specimens of sheet(s) %s of the plan %s (codes kept)%s;'
            '\n# %d specimens + %d LASER strips.\n# Run from the repository root:\n'
            '#   py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/%s.yaml\n\nname: %s\n'
            % ('\n'.join('# ' + l for l in textwrap.wrap(a.title or a.name, 116)), a.sheets, os.path.basename(os.path.dirname(a.registry)),
               (' + ' + ', '.join(os.path.basename(o) for o in a.add)) if a.add else '', n, n_laser, a.name, a.name))
    path = os.path.join(ORDERS, a.name + '.yaml')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(head + base[i0:i1] + base[i1:i2] + '\n'.join(lines) + '\n')
    print('written %s (%d specimens + %d LASER)' % (os.path.relpath(path), n, n_laser))


if __name__ == '__main__':
    main()
