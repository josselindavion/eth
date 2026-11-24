"""
compare_shapes.py -- Compare the speckle shapes for each strain-rate preset (user, 24/11/2026).

For each preset of speckle_settings.yaml (slow, int, fast) and each shape (square, circle, rotated_square, ellipse,
polygon): the same area with the same seed, a zoom on the pattern and the quality indicators of speckle_quality.py.
One page per preset in a PDF, and the table in the terminal.

    py compare_shapes.py                     -> results/compare_shapes.pdf (all presets)
    py compare_shapes.py slow                -> slow only
    py compare_shapes.py --show              -> also opens the figures
"""
import os
import sys

import matplotlib
if '--show' not in sys.argv:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt                              # noqa: E402
import numpy as np                                           # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages        # noqa: E402

from speckle_generator import SHAPES, preset, speckle_raster   # noqa: E402
from speckle_quality import quality                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
AREA_MM = 10.0       # side of the square pattern used for the indicators
ZOOM_MM = 3.0        # side of the zoom shown
SEED = 1
ROWS = [('coverage', 'coverage', '%.3f'), ('mig', 'MIG (grey/px)', '%.3f'), ('speckle_um', 'speckle size (µm)', '%.0f'),
        ('entropy', 'entropy (bits)', '%.2f'), ('rms_px', 'DIC error RMS (px)', '%.4f'),
        ('rms_um', 'DIC error RMS (µm)', '%.3f')]


def page(name, pdf):
    p = preset(name)
    n = int(round(AREA_MM * 1000 / p['pitch_um']))
    z = int(round(ZOOM_MM * 1000 / p['pitch_um']))
    res = {}
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.suptitle('Speckle shapes  ·  preset %s: speckle %g µm, density %g, pitch %g µm' % (
        name, p['speckle_size_um'], p['density'], p['pitch_um']), fontsize=13, fontweight='bold', x=0.02, ha='left')
    for k, sh in enumerate(SHAPES):
        r = speckle_raster(np.ones((n, n), bool), p['pitch_um'] / 1000.0, p['speckle_size_um'], p['density'], SEED, sh)
        res[sh] = quality(r, p['pitch_um'])
        ax = fig.add_axes([0.02 + k * 0.196, 0.47, 0.18, 0.40])
        ax.imshow(~r[:z, :z], cmap='gray', interpolation='nearest', vmin=0, vmax=1)
        ax.set_title(sh, fontsize=11)
        ax.set_xticks([])
        ax.set_yticks([])
        print('%-5s %-15s ' % (name, sh) + '  '.join(lab.split(' (')[0] + ' ' + fm % res[sh][key]
                                                     for key, lab, fm in ROWS))
    fig.text(0.02, 0.445, 'zoom %g × %g mm; indicators on %g × %g mm, seed %d; camera pixel = pattern pixel, blur 0.6 px, '
             'noise 2 %%; DIC: subsets 31 px, shifts 0.25/0.5/0.75 px in x and y' % (ZOOM_MM, ZOOM_MM, AREA_MM, AREA_MM,
                                                                                     SEED), fontsize=8, color='0.35')
    cells = [[fm % res[sh][key] for sh in SHAPES] for key, lab, fm in ROWS]
    tab = fig.add_axes([0.13, 0.05, 0.42, 0.33])
    tab.axis('off')
    t = tab.table(cellText=cells, rowLabels=[lab for key, lab, fm in ROWS], colLabels=list(SHAPES), loc='center',
                  cellLoc='center')
    t.auto_set_font_size(False)
    t.set_fontsize(8.5)
    t.scale(1, 1.5)
    for key, lab, ylab, x0 in (('mig', 'MIG (higher = better)', 'grey levels / px', 0.62),
                               ('rms_um', 'DIC error RMS (lower = better)', 'µm', 0.81)):
        ax = fig.add_axes([x0, 0.08, 0.16, 0.28])
        ax.bar(range(len(SHAPES)), [res[sh][key] for sh in SHAPES], color='0.45')
        ax.set_xticks(range(len(SHAPES)))
        ax.set_xticklabels([s.replace('_', '\n') for s in SHAPES], fontsize=7)
        ax.set_title(lab, fontsize=9)
        ax.set_ylabel(ylab, fontsize=8)
        ax.tick_params(axis='y', labelsize=7)
    pdf.savefig(fig)
    return fig


if __name__ == '__main__':
    names = [a for a in sys.argv[1:] if not a.startswith('--')] or ['slow', 'int', 'fast']
    out = os.path.join(HERE, 'results', 'compare_shapes.pdf')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with PdfPages(out) as pdf:
        figs = [page(n, pdf) for n in names]
    print('written %s' % out)
    if '--show' in sys.argv:
        plt.show()
