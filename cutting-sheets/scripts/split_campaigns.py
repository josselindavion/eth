# -*- coding: utf-8 -*-
"""
split_campaigns.py -- Splits campaigns A and B into sheets with the user's rules (11/11/2026):
    - 2 sheets common to A and B (tension-type specimens only);
    - B = 3 sheets: the 2 common ones + ONE sheet with all the shear of B (+ tension-type specimens, + LASER strips,
      at least 1, up to n_laser);
    - A = 4 sheets: the 2 common ones + sheet 3 (the same tension-type specimens as B's sheet 3 + the LASER strips of A,
      first choice) + sheet 4 (the shear of A, + the LASER strips that did not fit on sheet 3).
Method: B's sheet 3 is filled first (shear of B + 1 LASER, then tension-type specimens added one by one, kept when the
sheet still fits, UT19 first); the rest must fit on 2 sheets (several tries, different orders and seeds); then LASER
strips are added. Writes the orders (codes kept: same specimen = same code in A and B):
    COMMON_AB_600x500mm_WATERJET, B_SHEET3_600x500mm_WATERJET, A_SHEET3_600x500mm_WATERJET, A_SHEET4_600x500mm_WATERJET

    py cutting-sheets/scripts/split_campaigns.py [n_laser]      (default 4)
"""
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(os.path.join(HERE, '..', '..'))
import make_plan as mp                  # noqa: E402
import make_templates as mt             # noqa: E402
import placement as sp                  # noqa: E402

ORD = 'cutting-sheets/orders/'
N_LASER = int(sys.argv[1]) if len(sys.argv) > 1 else 4
T0 = time.time()


def log(msg):
    print('[%5.0f s] %s' % (time.time() - T0, msg), flush=True)


def load(name):
    cfg = mp.read_order(ORD + name + '.yaml')
    return cfg, mp.expand(cfg, temps)


base_cfg = mp.read_order(ORD + 'campaign_sources/TENSION_AB_600x500mm_WATERJET.yaml')
temps = mt.load_templates(base_cfg['templates'])
_, tension_all = load('campaign_sources/TENSION_AB_600x500mm_WATERJET')
tension = [s for s in tension_all if s['T'].alias != 'LASER']
laser_spec = [s for s in tension_all if s['T'].alias == 'LASER'][0]
_, shear_b = load('campaign_sources/SHEAR_B_600x500mm_WATERJET')
_, shear_a = load('campaign_sources/SHEAR_A_600x500mm_WATERJET')
polys = {}
for s in tension_all + shear_a:
    polys.setdefault(s['T'].kind, mt.template_polygon(s['T'], closed=True))
W, H, m, gap = base_cfg['W'], base_cfg['H'], base_cfg['margins'], base_cfg['gap']
keep = base_cfg['zones']['keepouts']
lim = H - m['top'] + 1e-6
log('%d tension-type, %d shear B, %d shear A' % (len(tension), len(shear_b), len(shear_a)))


def lasers(n):
    return [dict(laser_spec) for _ in range(n)]


def fits(specs, seconds=15, seed=1):
    """One sheet? (sparrow, stopped as soon as it fits). Judged on the REAL top of the specimens: the top reported
    by sparrow is the one of the clamp wall, up to 0.3 mm too high when the wall sits slightly off its place."""
    pl, t = sp.sparrow(specs, polys, W, gap, m, seconds, seed, target=lim + 0.35, keepouts=keep, lim=lim)
    if pl is None:
        return False, t
    real = max(p[4].bounds[3] for p in pl)
    if real > lim:
        return False, real
    pl = sp.repair(pl, keep, polys, W, H, gap, m)
    return pl is not None, real


def fill_sheet3(order, seed):
    """B's sheet 3: shear B + 1 LASER, then tension-type specimens added one by one in "order"."""
    on, rest = [], []
    cur = shear_b + lasers(1)
    misses = 0
    for s in order:
        if misses >= 6:                         # 6 misses in a row: the sheet is full
            rest.append(s)
            continue
        ok, t = fits(cur + on + [s], seconds=12, seed=seed + len(on))
        if ok:
            on.append(s)
            misses = 0
        else:
            rest.append(s)
            misses += 1
    return on, rest


def two_sheets(specs, seed):
    sheets = sp.place(specs, polys, W, H, gap, m, 15, seed, max_sheets=4, assign_seconds=30, fill_tries=14,
                      fill_seconds=15, keepouts=keep)
    return len(sheets), sheets


result = None
for attempt in range(6):
    rnd = random.Random(attempt)
    ut19 = [s for s in tension if s['T'].alias == 'UT19']
    others = [s for s in tension if s['T'].alias != 'UT19']
    if attempt % 2:
        rnd.shuffle(others)
    else:                                       # diagonal pieces (45 deg) first: they pack worst on full sheets
        others.sort(key=lambda s: (s['angle'] % 90 == 0, s['T'].alias))
    order = ut19 + others if attempt < 4 else rnd.sample(tension, len(tension))
    on, rest = fill_sheet3(order, seed=1 + 10 * attempt)
    log('try %d: sheet 3 of B = %d shear + 1 LASER + %d tension-type; rest %d' % (attempt + 1, len(shear_b), len(on),
                                                                                  len(rest)))
    n, sheets = two_sheets(rest, seed=1 + attempt)
    log('try %d: rest on %d sheet(s) (%s)' % (attempt + 1, n, ', '.join(str(len(x)) for x in sheets)))
    if n <= 2:
        result = (on, rest)
        break
    # move back to sheet 3 is impossible (it is full): next try with another order
if result is None:
    log('FAILED: B cannot be split into 2 common sheets + 1 sheet with these rules')
    sys.exit(1)
on, rest = result

# LASER strips of B on its sheet 3: as many as fit, up to N_LASER (at least the 1 already there)
nb = 1
for k in range(2, N_LASER + 1):                         # 3 seeds of 40 s each (a short try may miss: 11/11)
    ok = any(fits(shear_b + on + lasers(k), seconds=40, seed=7 + k + 10 * j)[0] for j in range(3))
    if not ok:
        break
    nb = k
log('B sheet 3: %d LASER' % nb)
# A: sheet 3 = same tension-type specimens + LASER (first choice), sheet 4 = shear A + the other LASER
na3 = 0
for k in range(N_LASER, -1, -1):
    ok, _ = fits(on + lasers(k), seconds=20, seed=3 + k)
    if ok:
        na3 = k
        break
na4 = N_LASER - na3
if na4:
    ok, _ = fits(shear_a + lasers(na4), seconds=30, seed=5)
    if not ok:
        log('WARNING: %d LASER of A fit neither on sheet 3 nor on sheet 4; left out' % na4)
        na4 = 0
log('A sheet 3: %d LASER, A sheet 4: %d LASER' % (na3, na4))


def lines(specs):
    groups = {}
    for s in specs:
        groups.setdefault((s['T'].alias, s['angle']), []).append(s['index'])
    out = []
    for (alias, ang), idx in sorted(groups.items(), key=lambda kv: (kv[0][0].startswith('SH'), kv[0])):
        idx = sorted(idx)
        runs = []
        for i in idx:
            if runs and i == runs[-1][0] + runs[-1][1]:
                runs[-1][1] += 1
            else:
                runs.append([i, 1])
        for first, count in runs:
            out.append('  - {type: %-16s angle: %-4s count: %d, first_index: %d}' % (alias + ',', '%d,' % ang, count,
                                                                                     first))
    return out


def write(name, title, specs, n_laser, spread_tries=3):
    base = open(ORD + 'campaign_sources/TENSION_AB_600x500mm_WATERJET.yaml', encoding='utf-8').read()
    i0, i1, i2 = base.index('templates:'), base.index('# ---------- Specimens: one line'), base.index('specimens:\n')
    body = base[i0:i1].replace('spread_tries: 1        # placements tried to keep the repeats apart',
                               'spread_tries: %d        # %d placements tried: the one with the fewest sheets is kept'
                               % (spread_tries, spread_tries))
    if name.startswith('COMMON'):                       # as in the search: more tries to stay on 2 sheets
        body = body.replace('fill_tries: 8          #', 'fill_tries: 14         #').replace(
            'fill_time: 10          #', 'fill_time: 15          #').replace('time: 10               #', 'time: 15               #')
    ls = ['specimens:'] + lines(specs)
    if n_laser:
        ls += ['  # speckle contrast strips (no code)', '  - {type: LASER,           angle: 0,   count: %d}' % n_laser]
    head = ('# %s\n# Written by scripts/split_campaigns.py (rules of the user, 11/11/2026): %d specimens + %d LASER.\n'
            '# Run from the repository root:\n#   py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/%s.yaml'
            '\n\nname: %s\n' % (title, len(specs), n_laser, name, name))
    with open(ORD + name + '.yaml', 'w', encoding='utf-8') as f:
        f.write(head + body + base[i1:i2] + '\n'.join(ls) + '\n')
    log('written %s (%d + %d LASER)' % (name, len(specs), n_laser))


write('COMMON_AB_600x500mm_WATERJET', 'Campaigns A and B: the 2 common sheets (tension-type specimens only)', rest, 0,
      spread_tries=1)
write('B_SHEET3_600x500mm_WATERJET', 'Campaign B, sheet 3: all the shear of B + tension-type specimens + LASER',
      shear_b + on, nb)
write('A_SHEET3_600x500mm_WATERJET', 'Campaign A, sheet 3: the tension-type specimens of B sheet 3 + LASER', on, na3)
write('A_SHEET4_600x500mm_WATERJET', 'Campaign A, sheet 4: all the shear of A (+ LASER left)', shear_a, na4)
log('done')
