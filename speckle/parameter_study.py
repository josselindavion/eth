"""
parameter_study.py -- Best engraved speckle parameters at each strain rate, over several random draws
(user, 24-25/11/2026).

Each preset (slow, int, fast) is evaluated with the camera and DIC subset of Beerli et al. 2026 for that test
(speckle_settings.yaml; speckle_quality.py: camera model, affine DIC, translation and strain tests).

    stage 1: speckle size x density, square (Ruben's) and circle, SEEDS1 draws each. Sizes = 2, 3, 4, 6, 8 camera px
             (rounded to the 33 um engraver pitch): around the 3-5 px rule of DIC and the 4-8 px of Beerli's paint.
    stage 2: the five shapes at the best size and density of stage 1, SEEDS2 draws each, Welch t-test of each shape
             against the square.
Criterion: the strain noise (standard deviation of the measured strain in the 1 % strain test); also recorded: the
displacement error, MIG, real coverage and speckle size.

Results: results/parameter_study.csv (one row per pattern). The report: make_report.py.

    py parameter_study.py            -> full study (about 15-20 min on 2 cores)
    py parameter_study.py --quick    -> 1 seed, 3 sizes, 3 densities: to test the chain
"""
import csv
import os
import sys
from multiprocessing import Pool

import numpy as np

from speckle_generator import SHAPES, setup, speckle_raster
from speckle_quality import quality

HERE = os.path.dirname(os.path.abspath(__file__))
QUICK = '--quick' in sys.argv
PRESETS = ['slow', 'int', 'fast']
CAM_PX = [2, 3, 4, 6, 8] if not QUICK else [3, 4, 8]
DENSITIES = [0.25, 0.35, 0.45, 0.55, 0.65] if not QUICK else [0.25, 0.45, 0.65]
SEEDS1 = [1, 2, 3, 4] if not QUICK else [1]
SEEDS2 = list(range(1, 9)) if not QUICK else [1, 2]
STAGE1_SHAPES = ['square', 'circle']
AREA_MM = 8.0
CRITERION = 'strain_noise'
OUT = os.path.join(HERE, 'results', 'parameter_study' + ('_quick' if QUICK else '') + '.csv')


def sizes(name):
    """Speckle sizes (um) of a preset: CAM_PX camera px rounded to the engraver pitch."""
    s = setup(name)
    return sorted({max(1, int(round(k * s['camera_um_per_px'] / s['pitch_um']))) * int(s['pitch_um']) for k in CAM_PX})


def run(job):
    stage, name, shape, size, dens, seed = job
    s = setup(name)
    n = int(round(AREA_MM * 1000 / s['pitch_um']))
    r = speckle_raster(np.ones((n, n), bool), s['pitch_um'] / 1000.0, size, dens, seed, shape)
    q = quality(r, s['pitch_um'], s['camera_um_per_px'], s['subset_px'], seed=seed)
    return dict(stage=stage, preset=name, shape=shape, size_um=size, size_cam_px=size / s['camera_um_per_px'],
                density=dens, seed=seed, **q)


def measure(jobs, label):
    print('%s: %d patterns' % (label, len(jobs)))
    res = []
    with Pool() as pool:
        for k, r in enumerate(pool.imap_unordered(run, jobs), 1):
            res.append(r)
            if k % 25 == 0 or k == len(jobs):
                print('  %d / %d' % (k, len(jobs)))
    return res


def best_cell(res, name):
    """(size, density) of the lowest mean criterion in stage 1 (both shapes together)."""
    cells = {}
    for r in res:
        if r['preset'] == name:
            cells.setdefault((r['size_um'], r['density']), []).append(r[CRITERION])
    return min(cells, key=lambda k: np.mean(cells[k]))


if __name__ == '__main__':
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    jobs1 = [('size_density', n, sh, size, d, s) for n in PRESETS for sh in STAGE1_SHAPES for size in sizes(n)
             for d in DENSITIES for s in SEEDS1]
    res = measure(jobs1, 'stage 1 (size x density)')
    jobs2 = []
    for n in PRESETS:
        size, d = best_cell(res, n)
        print('  %s: best size %d um, density %.2f' % (n, size, d))
        jobs2 += [('shapes', n, sh, size, d, s) for sh in SHAPES for s in SEEDS2]
    res += measure(jobs2, 'stage 2 (shapes)')
    keys = ['stage', 'preset', 'shape', 'size_um', 'density', 'seed']
    with open(OUT, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(res[0]))
        w.writeheader()
        w.writerows(sorted(res, key=lambda r: [r[k] for k in keys]))
    print('written %s' % OUT)
