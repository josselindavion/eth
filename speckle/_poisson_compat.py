# -*- coding: utf-8 -*-
"""
_poisson_compat.py -- Poisson-disk sampler for old scipy (user, 17/11/2026: lab PC with Python 3.7 and scipy 1.7.3,
where scipy.stats.qmc.PoissonDisk does not exist; it needs scipy >= 1.10, and the rng= argument used by
speckle_generator.py needs scipy >= 1.15, which needs Python >= 3.10).

install() puts a small PoissonDisk class (Bridson's algorithm) into scipy.stats.qmc when it is missing or too old, with
the only call speckle_generator.speckle_raster() makes: PoissonDisk(d=2, radius=, l_bounds=, u_bounds=, rng=)
.fill_space(). speckle_generator.py stays as received. With a recent scipy, nothing is changed.
"""
import inspect
import math

import numpy as np
from scipy.stats import qmc


class PoissonDisk(object):
    """2D Poisson-disk sampling in a box (Bridson 2007): every two points at least `radius` apart, the box filled."""

    def __init__(self, d=2, radius=0.05, l_bounds=(0, 0), u_bounds=(1, 1), rng=None, seed=None, ncandidates=30,
                 **kwargs):
        if d != 2:
            raise ValueError('only d=2 is supported')
        self.r = float(radius)
        self.lo = np.asarray(l_bounds, float)
        self.hi = np.asarray(u_bounds, float)
        self.k = ncandidates
        self.rng = rng if rng is not None else np.random.default_rng(seed)

    def fill_space(self):
        r, k, rng = self.r, self.k, self.rng
        w, h = self.hi - self.lo
        cell = r / math.sqrt(2)
        nx, ny = int(math.ceil(w / cell)), int(math.ceil(h / cell))
        grid = -np.ones((ny, nx), dtype=np.int64)              # index of the point in each cell, -1 = empty
        pts = []

        def add(p):
            grid[int(p[1] / cell), int(p[0] / cell)] = len(pts)
            pts.append(p)

        def far(p):
            gx, gy = int(p[0] / cell), int(p[1] / cell)
            for j in range(max(0, gy - 2), min(ny, gy + 3)):
                for i in range(max(0, gx - 2), min(nx, gx + 3)):
                    q = grid[j, i]
                    if q >= 0 and (pts[q][0] - p[0]) ** 2 + (pts[q][1] - p[1]) ** 2 < r * r:
                        return False
            return True

        add((rng.uniform(0, w), rng.uniform(0, h)))
        active = [0]
        while active:
            a = int(rng.integers(len(active)))
            px, py = pts[active[a]]
            ang = rng.uniform(0, 2 * math.pi, k)
            rad = r * np.sqrt(rng.uniform(1, 4, k))              # uniform in the ring [r, 2r]
            for x, y in zip(px + rad * np.cos(ang), py + rad * np.sin(ang)):
                if 0 <= x < w and 0 <= y < h and far((x, y)):
                    add((x, y))
                    active.append(len(pts) - 1)
                    break
            else:
                active[a] = active[-1]
                active.pop()
        return np.asarray(pts) + self.lo


def install():
    """Use this PoissonDisk if scipy's is missing or has no rng= argument (scipy < 1.15)."""
    old = getattr(qmc, 'PoissonDisk', None)
    if old is None or 'rng' not in inspect.signature(old.__init__).parameters:
        qmc.PoissonDisk = PoissonDisk
        return True
    return False
