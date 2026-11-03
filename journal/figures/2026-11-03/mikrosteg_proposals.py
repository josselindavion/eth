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
    'MNAK_RECT_HOLE': dict(test_r=20.0, rect=True, label_y=[-30, 30], test_label='test zone (assumed:\ncentre, r < 20 mm)',
                 ms=[((-14.0, -40.0), 'bottom end, left of centre'),
                     ((14.0, 40.0), 'coded end, right of the code\n(point-symmetric to Mikrosteg 1)')]),
    'MNAK_RECT_FULL': dict(test_r=20.0, rect=True, label_y=[-30, 30], test_label='test zone (assumed:\ncentre, r < 20 mm)',
                 ms=[((-14.0, -40.0), 'bottom end, left of centre'),
                     ((14.0, 40.0), 'coded end, right of the code\n(point-symmetric to Mikrosteg 1)')]),
    'TENS_FULL': dict(test=(-40.0, 40.0), test_label='test zone (assumed:\nmiddle of the strip)',
                 grips=[(-70.0, -40.0), (40.0, 70.0)], label_y=[-66, 62],
                 ms=[((0.0, -70.0), 'bottom end face, centred'),
                     ((0.0, 70.0), 'top end face, centred (no code on\nthis strip)')]),
    'NT06': dict(test=(-23.0, 20.0), test_label='test zone\n(notch R 6.67 and\n20 mm wide section)',
                 grips=[(-52.94, -23.0), (20.0, 52.94)],
                 ms=[((0.0, -52.9435), 'end face of the bottom grip, centred'),
                     ((10.0, 49.6), 'right side of the top grip (end face = code,\nleft side = chamfer)')]),
}


def draw(alias, out):
    """Outline of the specimen with its recesses, and a red circle around each Mikrosteg (nothing else)."""
    temps = mt.load_templates('/home/claude/eth/cutting-sheets/templates/CTLG_261102')
    T = [v for v in temps.values() if v.alias == alias][0]
    cfg = TYPES[alias]
    poly = mt.template_polygon(T, a_digit=2, index=1) if T.has_code else mt.template_polygon(T)
    for (x, y), _ in cfg['ms']:
        poly = poly.difference(Point(x, y).buffer(R, 64))
    x0, y0, x1, y1 = poly.bounds
    w, h = x1 - x0, y1 - y0
    fig, ax = plt.subplots(figsize=(1.0 + w / 12.0, 1.0 + h / 12.0))
    ax.plot(*poly.exterior.xy, color='#111827', lw=1.2)
    for ring in poly.interiors:
        ax.plot(*ring.xy, color='#111827', lw=1.2)
    for (x, y), _ in cfg['ms']:
        ax.plot(x, y, 'o', ms=18, mfc='none', mec='#dc2626', mew=2)
    ax.set_xlim(x0 - 4, x1 + 4)
    ax.set_ylim(y0 - 4, y1 + 4)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(alias, fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    draw(sys.argv[1], sys.argv[2])
