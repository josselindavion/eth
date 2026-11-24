"""
parameter_study.py -- Best speckle parameters at each strain rate, over several random draws (user, 24/11/2026).

For each preset of speckle_settings.yaml (slow, int, fast: it fixes the speckle size), every shape x density is drawn
with several seeds and measured with speckle_quality.py (virtual DIC error, MIG). Then:
    - mean and spread (standard deviation over the seeds) of the DIC error, plotted against the density per shape;
    - a quadratic fit of the error against the density per shape: the density of its minimum;
    - the best (shape, density) per preset, and a Welch t-test against the square at the same density (is the
      difference real or just the draw?);
    - a size sweep (error against the speckle size, square and circle) to see the effect of the size.
Results: results/parameter_study.csv (every run) and results/parameter_study.pdf.

    py parameter_study.py            -> full study (about 10 min on 2 cores; 624 patterns)
    py parameter_study.py --quick    -> fewer seeds and densities, to test
    py parameter_study.py --replot   -> analysis and PDF again from the CSV (no new runs)
"""
import csv
import os
import sys
from multiprocessing import Pool

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                              # noqa: E402
import numpy as np                                           # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages        # noqa: E402
from scipy import stats                                      # noqa: E402

from speckle_generator import SHAPES, preset, speckle_raster   # noqa: E402
from speckle_quality import quality                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
QUICK = '--quick' in sys.argv
PRESETS = ['slow', 'int', 'fast']
DENSITIES = [0.15, 0.25, 0.35, 0.45, 0.55, 0.65] if not QUICK else [0.25, 0.45]
SEEDS = list(range(1, 7)) if not QUICK else [1, 2]
SIZES_UM = [66, 99, 132, 165, 198, 264, 330] if not QUICK else [99, 198]
SIZE_SHAPES = ['square', 'circle']
SIZE_DENSITY = 0.35
AREA_MM = 10.0
GREY = ['0.0', '0.25', '0.45', '0.62', '0.78']
MARK = ['s', 'o', 'D', 'v', 'P']


def run(job):
    """One pattern measured: job = (study, preset, shape, size_um, density, seed, pitch_um)."""
    study, name, shape, size, dens, seed, pitch = job
    n = int(round(AREA_MM * 1000 / pitch))
    r = speckle_raster(np.ones((n, n), bool), pitch / 1000.0, size, dens, seed, shape)
    q = quality(r, pitch, seed=seed)
    return dict(study=study, preset=name, shape=shape, size_um=size, density=dens, seed=seed, **q)


def jobs():
    out = []
    for name in PRESETS:
        p = preset(name)
        for sh in SHAPES:
            for d in DENSITIES:
                for s in SEEDS:
                    out.append(('density', name, sh, p['speckle_size_um'], d, s, p['pitch_um']))
    pitch = preset('slow')['pitch_um']
    for sh in SIZE_SHAPES:
        for size in SIZES_UM:
            for s in SEEDS:
                out.append(('size', '-', sh, size, SIZE_DENSITY, s, pitch))
    return out


def stat(rows, key='rms_um'):
    v = np.array([r[key] for r in rows])
    return v.mean(), v.std(ddof=1) if len(v) > 1 else 0.0, v


def analyse(res):
    """Best (shape, density) per preset, quadratic fits, t-test against the square."""
    out = {}
    for name in PRESETS:
        rows = [r for r in res if r['study'] == 'density' and r['preset'] == name]
        cells = {}
        for sh in SHAPES:
            for d in DENSITIES:
                cells[(sh, d)] = stat([r for r in rows if r['shape'] == sh and r['density'] == d])
        best = min(cells, key=lambda k: cells[k][0])
        best_sq = min([k for k in cells if k[0] == 'square'], key=lambda k: cells[k][0])   # square at its best density
        t = stats.ttest_ind(cells[best][2], cells[best_sq][2], equal_var=False) if best[0] != 'square' else None
        fits = {}
        for sh in SHAPES:
            x = np.array([r['density'] for r in rows if r['shape'] == sh])
            y = np.array([r['rms_um'] for r in rows if r['shape'] == sh])
            if len(set(x)) >= 3:
                c = np.polyfit(x, y, 2)
                xm = -c[1] / (2 * c[0]) if c[0] > 0 else (x.min() if c[1] > 0 else x.max())
                xm = float(np.clip(xm, min(DENSITIES), max(DENSITIES)))
                fits[sh] = (c, xm, float(np.polyval(c, xm)))
        out[name] = dict(cells=cells, best=best, best_sq=best_sq, ttest=t, fits=fits)
    return out


def page_summary(pdf, an, res):
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.text(0.04, 0.93, 'Speckle parameter study  ·  best parameters per strain rate', fontsize=15, fontweight='bold')
    fig.text(0.04, 0.895, 'DIC error = RMS of the virtual DIC test (known sub-pixel shifts measured back), in µm; mean '
             'over %d seeds (± standard deviation); %g × %g mm patterns; camera pixel = pattern pixel (33 µm).'
             % (len(SEEDS), AREA_MM, AREA_MM), fontsize=8.5, color='0.35')
    head = ['preset', 'speckle', 'best shape', 'best\ndensity', 'DIC error (µm)', 'best square\n(density: error)',
            'better than the square?\n(Welch t-test)', 'fit: best density\nper shape']
    cells = []
    for name in PRESETS:
        a = an[name]
        sh, d = a['best']
        m, s, _ = a['cells'][(sh, d)]
        dq = a['best_sq'][1]
        mq, sq, _ = a['cells'][a['best_sq']]
        if a['ttest'] is None:
            tt = 'it is the square'
        else:
            pv = a['ttest'].pvalue
            tt = 'p = %.3f: %s' % (pv, 'yes' if pv < 0.05 else 'no (within the draw)')
        ab = {'square': 'sq', 'circle': 'ci', 'rotated_square': 'rs', 'ellipse': 'el', 'polygon': 'po'}
        fl = ['%s %.2f' % (ab.get(k, k), v[1]) for k, v in a['fits'].items()]
        fit = ' · '.join(fl[:3]) + '\n' + ' · '.join(fl[3:])
        cells.append([name, '%g µm' % preset(name)['speckle_size_um'], sh, '%g' % d, '%.3f ± %.3f' % (m, s),
                      '%g: %.3f ± %.3f' % (dq, mq, sq), tt.replace(': ', ':\n'), fit])
    ax = fig.add_axes([0.03, 0.40, 0.94, 0.46])
    ax.axis('off')
    t = ax.table(cellText=cells, colLabels=head, loc='upper center', cellLoc='center',
                 colWidths=[0.07, 0.08, 0.11, 0.08, 0.13, 0.16, 0.19, 0.18])
    t.auto_set_font_size(False)
    t.set_fontsize(8.5)
    t.scale(1, 3.2)
    notes = ['How to read: for each preset (it fixes the speckle size) every shape × density is drawn %d times; the best '
             'cell is the lowest mean error.' % len(SEEDS),
             'Welch t-test: compares the best cell with the best square (at its own best density); p < 0.05 = the '
             'difference is larger than the scatter between draws.',
             'Fit: a parabola of the error against the density for each shape; the density of its minimum (clipped to '
             'the tested range %g-%g); sq square, ci circle, rs rotated square, el ellipse, po polygon.'
             % (min(DENSITIES), max(DENSITIES)),
             'Size sweep (last page): error against the speckle size at density %g, square and circle.' % SIZE_DENSITY]
    for k, s in enumerate(notes):
        fig.text(0.04, 0.30 - k * 0.035, s, fontsize=8.5)
    pdf.savefig(fig)
    plt.close(fig)


def page_preset(pdf, name, an, res):
    a = an[name]
    rows = [r for r in res if r['study'] == 'density' and r['preset'] == name]
    fig, axs = plt.subplots(1, 2, figsize=(11.69, 8.27))
    fig.subplots_adjust(left=0.07, right=0.97, top=0.86, bottom=0.12, wspace=0.25)
    p = preset(name)
    fig.suptitle('Preset %s  ·  speckle %g µm, pitch %g µm  ·  %d seeds per point (bars = ± 1 standard deviation)'
                 % (name, p['speckle_size_um'], p['pitch_um'], len(SEEDS)), fontsize=12, fontweight='bold',
                 x=0.03, ha='left')
    off = np.linspace(-0.012, 0.012, len(SHAPES))
    for k, sh in enumerate(SHAPES):
        for ax, key in ((axs[0], 'rms_um'), (axs[1], 'mig')):
            ms = [stat([r for r in rows if r['shape'] == sh and r['density'] == d], key) for d in DENSITIES]
            ax.errorbar(np.array(DENSITIES) + off[k], [m[0] for m in ms], yerr=[m[1] for m in ms], color=GREY[k],
                        marker=MARK[k], ms=5, capsize=3, lw=1, label=sh)
        if sh in a['fits']:
            c, xm, ym = a['fits'][sh]
            xs = np.linspace(min(DENSITIES), max(DENSITIES), 50)
            axs[0].plot(xs, np.polyval(c, xs), color=GREY[k], lw=0.7, ls='--')
    sh, d = a['best']
    m = a['cells'][(sh, d)][0]
    axs[0].plot([d], [m], marker='*', ms=16, mfc='none', mec='k', mew=1.3, ls='none', label='best: %s, %g' % (sh, d))
    axs[0].set_title('DIC error (lower = better); dashed = quadratic fit', fontsize=10)
    axs[0].set_xlabel('density')
    axs[0].set_ylabel('RMS error (µm)')
    axs[1].set_title('MIG, mean intensity gradient (higher = better)', fontsize=10)
    axs[1].set_xlabel('density')
    axs[1].set_ylabel('grey levels / px')
    for ax in axs:
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    pdf.savefig(fig)
    plt.close(fig)


def page_size(pdf, res):
    rows = [r for r in res if r['study'] == 'size']
    fig, axs = plt.subplots(1, 2, figsize=(11.69, 8.27))
    fig.subplots_adjust(left=0.07, right=0.97, top=0.86, bottom=0.12, wspace=0.25)
    fig.suptitle('Size sweep  ·  density %g, %d seeds per point (± 1 standard deviation)' % (SIZE_DENSITY, len(SEEDS)),
                 fontsize=12, fontweight='bold', x=0.03, ha='left')
    for k, sh in enumerate(SIZE_SHAPES):
        for ax, key in ((axs[0], 'rms_um'), (axs[1], 'mig')):
            ms = [stat([r for r in rows if r['shape'] == sh and r['size_um'] == s], key) for s in SIZES_UM]
            ax.errorbar(SIZES_UM, [m[0] for m in ms], yerr=[m[1] for m in ms], color=GREY[k * 2], marker=MARK[k],
                        capsize=3, label=sh)
    for name in PRESETS:
        for ax in axs:
            ax.axvline(preset(name)['speckle_size_um'], color='0.7', lw=0.8, ls=':')
            ax.text(preset(name)['speckle_size_um'], ax.get_ylim()[1], ' ' + name, fontsize=8, color='0.4', va='top')
    axs[0].set_title('DIC error against the speckle size', fontsize=10)
    axs[0].set_ylabel('RMS error (µm)')
    axs[1].set_title('MIG against the speckle size', fontsize=10)
    axs[1].set_ylabel('grey levels / px')
    for ax in axs:
        ax.set_xlabel('speckle size (µm)  ·  1 px = 33 µm')
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    pdf.savefig(fig)
    plt.close(fig)


if __name__ == '__main__':
    out_dir = os.path.join(HERE, 'results')
    os.makedirs(out_dir, exist_ok=True)
    name = 'parameter_study' + ('_quick' if QUICK else '')
    csv_path = os.path.join(out_dir, name + '.csv')
    if '--replot' in sys.argv:                               # analysis and PDF again from the CSV, no new runs
        with open(csv_path, encoding='utf-8') as f:
            res = [{k: (v if k in ('study', 'preset', 'shape') else float(v)) for k, v in r.items()}
                   for r in csv.DictReader(f)]
    else:
        js = jobs()
        print('%d patterns to measure...' % len(js))
        res = []
        with Pool() as pool:
            for k, r in enumerate(pool.imap_unordered(run, js), 1):
                res.append(r)
                if k % 20 == 0 or k == len(js):
                    print('  %d / %d' % (k, len(js)))
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(res[0]))
            w.writeheader()
            w.writerows(sorted(res, key=lambda r: (r['study'], r['preset'], r['shape'], r['size_um'], r['density'],
                                                   r['seed'])))
    an = analyse(res)
    with PdfPages(os.path.join(out_dir, name + '.pdf')) as pdf:
        page_summary(pdf, an, res)
        for n in PRESETS:
            page_preset(pdf, n, an, res)
        page_size(pdf, res)
    for n in PRESETS:
        sh, d = an[n]['best']
        m, s, _ = an[n]['cells'][(sh, d)]
        print('%-5s best: %-15s density %.2f  error %.3f ± %.3f um' % (n, sh, d, m, s))
    print('written results/%s.csv and .pdf' % name)
