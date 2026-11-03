import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from shapely.geometry import box, Point
from shapely.ops import unary_union
R, k, b = 1.5, 0.3, 0.4     # notch radius, kerf (wire + spark), bridge width: illustrative values
spec = box(0, -6, 6, 6).difference(Point(0, 0).buffer(R, 64))          # specimen (right), edge at x = 0
kerf = spec.buffer(k, 64).difference(spec).intersection(box(-k - 0.01, -6, 6, 6))
bridge = box(R - k - 0.05, -b / 2, R + 0.05, b / 2)
kerf_cut = kerf.difference(bridge)
outside = box(-6, -6, 6, 6).difference(spec).difference(kerf)
nub = box(R - 0.12, -b / 2, R + 0.01, b / 2)

def fill(ax, g, **kw):
    for p in (g.geoms if hasattr(g, "geoms") else [g]):
        if p.geom_type != "Polygon":
            continue
        ax.fill(*p.exterior.xy, **kw)
        for h in p.interiors:
            ax.fill(*h.xy, color='white')

fig, axs = plt.subplots(1, 2, figsize=(11, 5.6))
for ax in axs:
    ax.set_xlim(-4, 5); ax.set_ylim(-4, 4); ax.set_aspect('equal'); ax.axis('off')
a = axs[0]
fill(a, outside, color='#d1d5db'); fill(a, spec, color='#93c5fd'); fill(a, kerf_cut, color='#111827')
fill(a, bridge.intersection(kerf), color='#dc2626')
a.text(-3.5, 3.3, 'OUTSIDE (scrap)', fontsize=11); a.text(2.2, 3.3, 'SPECIMEN', fontsize=11)
a.annotate('wire path (kerf)', xy=(-0.15, -2.5), xytext=(-3.8, -3.5), fontsize=9, arrowprops=dict(arrowstyle='->'))
a.annotate('Mikrosteg: the wire stops here,\nthe specimen stays attached', xy=(R - 0.12, 0), xytext=(1.9, -2.6),
           fontsize=9, color='#dc2626', arrowprops=dict(arrowstyle='->', color='#dc2626'))
a.annotate('half-circle recess\ndrawn in the DXF (R = %.1f mm)' % R, xy=(R * 0.7, R * 0.7), xytext=(1.9, 1.6), fontsize=9,
           arrowprops=dict(arrowstyle='->'))
a.set_title('1. During cutting', fontsize=12, loc='left')
b2 = axs[1]
fill(b2, spec.union(nub), color='#93c5fd')
b2.plot([0, 0], [-4, 4], ls='--', color='#374151', lw=1)
fill(b2, nub, color='#dc2626')
b2.text(-3.6, 3.3, 'specimen edge (x = 0)', fontsize=9, color='#374151')
b2.annotate('rest of the Mikrosteg after breaking:\ninside the recess, never beyond the edge', xy=(R - 0.06, 0.1),
            xytext=(-3.9, -2.6), fontsize=9, color='#dc2626', arrowprops=dict(arrowstyle='->', color='#dc2626'))
b2.set_title('2. After breaking the specimen out', fontsize=12, loc='left')
fig.suptitle('Internal Mikrosteg (zoom on one specimen edge; values for illustration only: R %.1f, kerf %.1f, '
             'bridge %.1f mm)' % (R, k, b), fontsize=10, y=0.98)
fig.tight_layout()
fig.savefig('mikrosteg_concept.png', dpi=150)
