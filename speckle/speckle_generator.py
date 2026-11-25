"""
speckle_generator.py -- Speckle patterns engraved on the specimens for DIC.

From the generator of Ruben Zwicker (Inspire AG, 16/11/2026), cleaned on 24/11/2026: unused functions and prints
removed, speckle shapes added (Ruben: "it could be interesting to investigate different shaped speckles"), strain-rate
presets read from speckle_settings.yaml (pattern, and the DIC setup of Beerli et al. 2026 used to evaluate it). With shape='square' the pattern is the same as Ruben's for the same seed.

The pattern is a raster at the pitch of the engraver (33 um, close to its minimum resolution): True = engrave.
Speckle centres: Poisson-disk samples (blue noise: random but evenly spaced, no clusters, no holes) filling the bounding
box of the mask, thinned at random to the target number; every speckle has the area of a square of side size_um, so
the density is comparable between shapes; speckles are clipped to the mask.

    from speckle_generator import generate_speckle_pattern, preset
    img = generate_speckle_pattern(21, 21, **preset('slow'), shape='circle', seed=1)
"""
import math
import os

import numpy as np
from PIL import Image
from scipy.stats import qmc

HERE = os.path.dirname(os.path.abspath(__file__))
POISSON_FILL_CONSTANT = 0.60  # points per area * radius^2 when qmc.PoissonDisk fills the space
POISSON_OVERFILL = 1.1        # fill with this many times the target, then thin out at random
SHAPES = ('square', 'circle', 'rotated_square', 'ellipse', 'polygon')


def preset(name, path=os.path.join(HERE, 'speckle_settings.yaml')):
    """Parameters of a strain-rate preset (slow, int, fast) from speckle_settings.yaml:
    {'pitch_um', 'speckle_size_um', 'density'}, ready for generate_speckle_pattern(...)."""
    import yaml
    with open(path, encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    p = cfg['presets'][name]
    return {'pitch_um': float(cfg['pitch_um']), 'speckle_size_um': float(p['size_um']), 'density': float(p['density'])}


def setup(name, path=os.path.join(HERE, 'speckle_settings.yaml')):
    """Every value of a preset (pattern and DIC setup of Beerli et al. 2026) plus pitch_um: dict."""
    import yaml
    with open(path, encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    d = dict(cfg['presets'][name])
    d['pitch_um'] = float(cfg['pitch_um'])
    return d


def speckle_px(pitch_mm, size_um):
    """Speckle side length in whole pixels (at least 1)."""
    return max(1, int(round(size_um / 1000.0 / pitch_mm)))


def _inside(shape, size, dx, dy, rng):
    """bool array: pixel centres (dx, dy relative to the speckle centre, in px) inside one speckle of the given shape,
    whose area is size**2 (same area as the square)."""
    if shape == 'circle':
        r = size / math.sqrt(math.pi)
        return dx * dx + dy * dy <= r * r
    a = rng.uniform(0, math.pi)                              # random orientation
    u, v = dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
    if shape == 'rotated_square':
        return (np.abs(u) <= size / 2.0) & (np.abs(v) <= size / 2.0)
    if shape == 'ellipse':                                   # aspect ratio 2
        b = size / math.sqrt(2 * math.pi)
        return (u / (2 * b)) ** 2 + (v / b) ** 2 <= 1
    if shape == 'polygon':                                   # irregular star-shaped polygon, 5 to 8 vertices
        k = int(rng.integers(5, 9))
        ang = np.sort(rng.uniform(0, 2 * math.pi, k))
        rad = rng.uniform(0.6, 1.0, k)
        area = 0.5 * np.sum(rad * np.roll(rad, -1) * np.sin(np.roll(ang, -1) - ang + 2 * math.pi * (np.arange(k) == k - 1)))
        rad *= size / math.sqrt(abs(area))
        xs, ys = rad * np.cos(ang), rad * np.sin(ang)
        inside = np.zeros(u.shape, dtype=bool)
        for i in range(k):                                   # ray casting
            x1, y1, x2, y2 = xs[i], ys[i], xs[(i + 1) % k], ys[(i + 1) % k]
            cross = (y1 > v) != (y2 > v)
            with np.errstate(divide='ignore', invalid='ignore'):
                xi = x1 + (v - y1) * (x2 - x1) / (y2 - y1)
            inside ^= cross & (u < xi)
        return inside
    raise ValueError('unknown shape %r (one of %s)' % (shape, ', '.join(SHAPES)))


def speckle_raster(mask, pitch_mm, size_um, density, seed=None, shape='square'):
    """
    Blue-noise speckles inside a mask.

    Parameters:
        mask (numpy.ndarray): bool raster of the area to fill.
        pitch_mm (float): Pixel size in mm.
        size_um (float): Speckle size in um: side of a square of the same area; rounded to whole pixels.
        density (float): Target fraction of the mask covered by speckles, 0 to 1.
        seed (int | None, optional): Seed for a reproducible pattern.
        shape (str): one of SHAPES.
    Returns:
        numpy.ndarray: bool raster of the mask's shape, True where a speckle is.
    """
    if pitch_mm <= 0:
        raise ValueError("pitch_mm must be > 0")
    if not 0 < density < 1:
        raise ValueError("density must be between 0 and 1")
    if size_um <= 0:
        raise ValueError("size_um must be > 0")
    mask = np.asarray(mask, dtype=bool)
    speckles = np.zeros(mask.shape, dtype=bool)
    rows, cols = np.nonzero(mask)
    if rows.size == 0:
        return speckles
    r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
    width, height = c1 - c0, r1 - r0
    size = speckle_px(pitch_mm, size_um)

    target_n = max(1, int(round(density * width * height / size ** 2)))
    radius = math.sqrt(POISSON_FILL_CONSTANT * width * height / (POISSON_OVERFILL * target_n))
    rng = np.random.default_rng(seed)
    engine = qmc.PoissonDisk(d=2, radius=radius, l_bounds=[0, 0], u_bounds=[width, height], rng=rng)
    centers = engine.fill_space()
    if len(centers) > target_n:
        centers = centers[rng.choice(len(centers), target_n, replace=False)]

    if shape == 'square':                                    # Ruben's speckles
        corners = np.floor(centers - size / 2).astype(int)
        for x, y in corners:
            speckles[max(r0 + y, r0):max(r0 + y + size, r0), max(c0 + x, c0):max(c0 + x + size, c0)] = True
    else:
        h = int(math.ceil(size)) + 1                         # half window, enough for every shape of this area
        for cx, cy in centers:
            ix, iy = int(math.floor(cx)), int(math.floor(cy))
            xs = np.arange(ix - h, ix + h + 1)
            ys = np.arange(iy - h, iy + h + 1)
            dx, dy = np.meshgrid(xs + 0.5 - cx, ys + 0.5 - cy)
            ins = _inside(shape, size, dx, dy, rng)
            jj, ii = np.nonzero(ins)
            rr, cc = r0 + ys[jj], c0 + xs[ii]
            ok = (rr >= r0) & (rr < r1) & (cc >= c0) & (cc < c1)
            speckles[rr[ok], cc[ok]] = True
    speckles &= mask
    return speckles


def generate_speckle_pattern(width, height, pitch_um, speckle_size_um, density, seed=None, shape='square'):
    """
    A rectangular speckle pattern: PIL.Image (mode 'L'), black speckles on white.

    Parameters:
        width, height (float): Size in mm.
        pitch_um (float): Pixel size in um.
        speckle_size_um (float): Speckle size in um (side of a square of the same area), rounded to whole pixels.
        density (float): Fraction of the area covered by speckles, 0 to 1.
        seed (int | None, optional): Seed for a reproducible pattern.
        shape (str): one of SHAPES.
    """
    pitch_mm = pitch_um / 1000.0
    width_px = max(1, int(round(width / pitch_mm)))
    height_px = max(1, int(round(height / pitch_mm)))
    speckles = speckle_raster(np.ones((height_px, width_px), bool), pitch_mm, speckle_size_um, density, seed, shape)
    return Image.fromarray(np.where(speckles, 0, 255).astype(np.uint8), mode="L")


def calculate_black_pixel_density(img, threshold=0.5):
    """Ratio of black pixels to total pixels of an image (numpy array, grayscale or RGB, 0-1 or 0-255)."""
    img = np.asarray(img, dtype=float)
    img_gray = np.mean(img, axis=2) if img.ndim == 3 else img
    if img_gray.max() > 1.0:
        img_gray = img_gray / 255.0
    return float(np.sum(img_gray < threshold)) / img_gray.size


if __name__ == "__main__":
    # Example: a 21 x 21 mm pattern with the 'slow' preset, saved in ./speckle_patterns/
    width = height = 21
    p = preset('slow')
    dpi = 25.4 * 1000 / p['pitch_um']   # max dpi on engraver is 999
    img = generate_speckle_pattern(width, height, **p)
    os.makedirs(os.path.join(HERE, 'speckle_patterns'), exist_ok=True)
    image_path = os.path.join(HERE, 'speckle_patterns', 'speckle_%gx%g_size%gum_density%d_dpi%d.png' % (
        width, height, p['speckle_size_um'], round(p['density'] * 100), round(dpi)))
    img.save(image_path, dpi=(dpi, dpi))
    print("Speckle pattern saved to %s" % image_path)
    print("Actual black pixel density: %.4f" % calculate_black_pixel_density(np.array(img)))
