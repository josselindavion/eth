"""Proposal of Mikrosteg positions for one specimen type: outline with code, test zone, clamping zones, recesses."""
import sys, math
sys.path.insert(0, '/home/claude/eth/cutting-sheets/scripts')
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from shapely.geometry import Point
import make_templates as mt

R = 1.0     # recess radius (mm), proposal

TYPES = {
    'UTUT': dict(test=(-21.75, 18.75), grips=[(-52.94, -24.0), (21.0, 52.94)],
                 ms=[((0.0, -52.9435), 'end face of the bottom grip, centred'),
                     ((10.0, 49.6), 'right side of the top grip (end face = code,\nleft side = chamfer)')]),
    'NT20': dict(test=(-22.95, 20.0), test_label='test zone\n(notch R 20 and\n20 mm wide section)',
                 grips=[(-52.94, -22.95), (20.0, 52.94)],
                 ms=[((0.0, -52.9435), 'end face of the bottom grip, centred'),
                     ((10.0, 49.6), 'right side of the top grip (end face = code,\nleft side = chamfer)')]),
    'CHCH': dict(test=(-23.0, 20.0), test_label='test zone\n(central hole 4.8 mm and\n20 mm wide section)',
                 grips=[(-52.94, -23.0), (20.0, 52.94)],
                 ms=[((0.0, -52.944), 'end face of the bottom grip, centred'),
                     ((10.0, 49.6), 'right side of the top grip (end face = code,\nleft side = chamfer)')]),
    'UTST': dict(test=(-10.0, 6.9), test_label='test zone\n(parallel length, 5 mm wide)',
                 grips=[(-40.39, -10.0), (6.9, 40.39)],
                 ms=[((0.0, -40.3935), 'end face of the bottom grip, centred'),
                     ((10.0, 37.0), 'right side of the top grip (end face = code,\nleft side = chamfer)')]),
    'SHLD': dict(test=(-11.3, 8.2), test_label='test zone\n(central section,\n20 mm wide)',
                 grips=[(-40.39, -11.3), (8.2, 40.39)],
                 ms=[((0.0, -40.394), 'end face of the bottom grip, centred'),
                     ((10.0, 37.0), 'right side of the top grip (end face = code,\nleft corner = SHLD detail)')]),
    'SHMD': dict(test=(-11.3, 8.2), test_label='test zone\n(central section,\n20 mm wide)',
                 grips=[(-40.39, -11.3), (8.2, 40.39)],
                 ms=[((0.0, -40.394), 'end face of the bottom grip, centred'),
                     ((10.0, 37.0), 'right side of the top grip (end face = code,\nleft corner = SHMD detail)')]),
    'SHHD': dict(test=(-11.3, 8.2), test_label='test zone\n(central section,\n20 mm wide)',
                 grips=[(-40.39, -11.3), (8.2, 40.39)],
                 ms=[((0.0, -40.394), 'end face of the bottom grip, centred'),
                     ((10.0, 37.0), 'right side of the top grip (end face = code,\nleft corner = SHHD detail)')]),
    'MNAK_HOLE': dict(test_r=20.0, label_y=[16, -24], test_label='test zone (assumed:\ncentre, r < 20 mm)',
                 ms=[((25.9808, 15.0000), 'rim at 30 deg (right, above the\nside notch)'),
                     ((-25.9808, -15.0000), 'rim at 210 deg, diametrically\nopposite')]),
    'MNAK_FULL': dict(test_r=20.0, label_y=[16, -24], test_label='test zone (assumed:\ncentre, r < 20 mm)',
                 ms=[((25.9808, 15.0000), 'rim at 30 deg (right, above the\nside notch)'),
                     ((-25.9808, -15.0000), 'rim at 210 deg, diametrically\nopposite')]),
    'NT06': dict(test=(-23.0, 20.0), test_label='test zone\n(notch R 6.67 and\n20 mm wide section)',
                 grips=[(-52.94, -23.0), (20.0, 52.94)],
                 ms=[((0.0, -52.9435), 'end face of the bottom grip, centred'),
                     ((10.0, 49.6), 'right side of the top grip (end face = code,\nleft side = chamfer)')]),
}


def draw(alias, out):
    temps = mt.load_templates('/home/claude/eth/cutting-sheets/templates/CTLG_261102')
    T = [v for v in temps.values() if v.alias == alias][0]
    cfg = TYPES[alias]
    poly = mt.template_polygon(T, a_digit=2, index=1)          # example code: 30 deg, index 1
    for (x, y), _ in cfg['ms']:
        poly = poly.difference(Point(x, y).buffer(R, 64))
    x0, y0, x1, y1 = poly.bounds
    fig, ax = plt.subplots(figsize=(9.5, 6.2) if 'test_r' in cfg else (7.5, 9))
    if 'test_r' in cfg:                                         # disc: central test zone, clamped rim
        from matplotlib.patches import Circle
        ax.add_patch(Circle((0, 0), 31, fc='none', hatch='////', ec='#f59e0b', lw=0, zorder=0))
        ax.add_patch(Circle((0, 0), cfg['test_r'], fc='#bfdbfe', ec='none', zorder=0))
    else:
        ax.add_patch(Rectangle((x0 - 1, cfg['test'][0]), x1 - x0 + 2, cfg['test'][1] - cfg['test'][0], fc='#bfdbfe',
                               ec='none', zorder=0))
        for g0, g1 in cfg['grips']:
            ax.add_patch(Rectangle((x0 - 1, g0), x1 - x0 + 2, g1 - g0, fc='none', hatch='////', ec='#f59e0b', lw=0,
                                   zorder=0))
    ax.plot(*poly.exterior.xy, color='#111827', lw=1.2)
    for h in poly.interiors:
        ax.plot(*h.xy, color='#111827', lw=1.2)
    for k, ((x, y), txt) in enumerate(cfg['ms']):
        ax.plot(x, y, 'o', ms=16, mfc='none', mec='#dc2626', mew=2)
        d = (math.hypot(x, y) - cfg['test_r']) if 'test_r' in cfg else min(abs(y - cfg['test'][0]),
                                                                            abs(y - cfg['test'][1]))
        side = 1 if x >= 0 else -1
        ty = cfg['label_y'][k] if 'label_y' in cfg else y + (6 if y < 0 else -10)
        ax.annotate('Mikrosteg %d: %s\n%.0f mm from the test zone' % (k + 1, txt, d), xy=(x, y),
                    xytext=(x1 + 6, ty), fontsize=9, color='#dc2626',
                    arrowprops=dict(arrowstyle='->', color='#dc2626'))
    if 'test_r' in cfg:
        ax.text(x1 + 6, 2, cfg['test_label'], fontsize=9, color='#1d4ed8', va='center')
        ax.text(x1 + 6, -9, 'clamping zone (rim)', fontsize=9, color='#b45309')
    else:
        ax.text(x1 + 6, sum(cfg['test']) / 2, cfg.get('test_label', 'test zone\n(parallel length)'), fontsize=9,
                color='#1d4ed8', va='center')
        ax.text(x1 + 6, sum(cfg['grips'][1]) / 2 - 8, 'clamping zone', fontsize=9, color='#b45309')
        ax.text(x1 + 6, sum(cfg['grips'][0]) / 2 + 4, 'clamping zone', fontsize=9, color='#b45309')
    ax.set_xlim(x0 - 5, x1 + 55)
    ax.set_ylim(y0 - 5, y1 + 5)
    ax.set_aspect('equal')
    ax.set_xticks(range(int(x0) - 5, int(x1) + 6, 5)); ax.grid(lw=0.3)
    ax.set_title('%s – proposal: 2 internal Mikrostegs (recess R %.1f mm)\ncode at the top (example: 30 deg, '
                 'index 1); rolling direction not relevant here' % (alias, R), fontsize=10, loc='left')
    for (x, y), _ in cfg['ms']:                                 # zoom inset on each recess
        pass
    fig.tight_layout()
    fig.savefig(out, dpi=150)


if __name__ == '__main__':
    draw(sys.argv[1], sys.argv[2])
