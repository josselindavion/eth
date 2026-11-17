import math
import numpy as np
from numpy.random import default_rng
from PIL import Image, ImageDraw
import random
from scipy.stats import qmc


def _poisson_radius_for_target_n(n: int, efficiency: float = 0.9) -> float:
    """
    Estimate the PoissonDisk 'radius' (normalized to [0,1]) to fit ~n points.
    efficiency=1.0 corresponds to hex packing (optimistic upper bound).
    For random Poisson-disk sampling, 0.85–0.95 is typical.
    """
    if n <= 0:
        raise ValueError("n must be > 0")
    hex_const = 2.0 / (3.0 ** 0.5)      # 2 / sqrt(3) ≈ 1.1547
    alpha = efficiency * hex_const      # effective packing constant
    r = (alpha / n) ** 0.5
    # keep r in a sane open interval
    return max(1e-4, min(0.5, r))


def _blue_noise_samples(width_px, height_px, target_n, m=1, rng=None):
    """
    Mitchell's Best Candidate blue-noise sampler with toroidal distance.

    Args:
        width_px (int): Width of the domain in pixels.
        height_px (int): Height of the domain in pixels.
        target_n (int): Number of samples to generate.
        m (int): Multiplier for number of candidates per iteration (NumSamples*m + 1).
                 Higher m => better blue-noise, slower. m=1 already works well.
        rng (random.Random | None): Optional PRNG for reproducibility.

    Returns:
        list[tuple[float, float]]: List of (x, y) sample coordinates in [0, width) x [0, height).
    """
    if target_n <= 0 or width_px <= 0 or height_px <= 0:
        return []

    if rng is None:
        rng = random.Random()

    def toroidal_dist2(ax, ay, bx, by):
        # wrap-around distance squared on a width x height torus
        dx = abs(ax - bx)
        dy = abs(ay - by)
        dx = min(dx, width_px - dx)
        dy = min(dy, height_px - dy)
        return dx * dx + dy * dy

    # 1) place the first sample randomly
    samples = [(rng.uniform(0, width_px), rng.uniform(0, height_px))]

    # 2) iteratively add best candidates
    while len(samples) < target_n:
        n_existing = len(samples)
        print(f"Placed {n_existing}/{target_n} samples...", end="\r")
        n_candidates = n_existing * m + 1  # scales with existing samples

        best_candidate = None
        best_min_d2 = -1.0

        for _ in range(n_candidates):
            cx = rng.uniform(0, width_px)
            cy = rng.uniform(0, height_px)

            # distance to the nearest existing sample (toroidal)
            min_d2 = float("inf")
            for (px, py) in samples:
                d2 = toroidal_dist2(cx, cy, px, py)
                if d2 < min_d2:
                    min_d2 = d2
                    if min_d2 == 0.0:
                        break  # can't do better than exact overlap

            if min_d2 > best_min_d2:
                best_min_d2 = min_d2
                best_candidate = (cx, cy)

        samples.append(best_candidate)
    print(f"Placed {target_n}/{target_n} samples.            ")
    return samples


POISSON_FILL_CONSTANT = 0.60  # Points per area * radius^2 when qmc.PoissonDisk fills the space
POISSON_OVERFILL = 1.1        # Fill with this many times the target, then thin out at random


def speckle_px(pitch_mm, size_um):
    """Speckle side length in whole pixels (at least 1)."""
    return max(1, int(round(size_um / 1000.0 / pitch_mm)))


def speckle_raster(mask, pitch_mm, size_um, density, seed=None):
    """
    Blue-noise square speckles inside a mask.

    The speckle centers are Poisson-disk samples filling the bounding box of the mask (in pixel units, so
    non-square areas are not distorted), thinned at random to the target count so that the whole area
    is covered evenly; the squares are clipped to the mask.

    Parameters:
        mask (numpy.ndarray): bool raster of the area to fill.
        pitch_mm (float): Pixel size in mm.
        size_um (float): Speckle side length in um; rounded to whole pixels.
        density (float): Target fraction of the mask covered by speckles, 0 to 1.
        seed (int | None, optional): Seed for a reproducible pattern.
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

    corners = np.floor(centers - size / 2).astype(int)
    for x, y in corners:
        speckles[max(r0 + y, r0):max(r0 + y + size, r0), max(c0 + x, c0):max(c0 + x + size, c0)] = True
    speckles &= mask
    return speckles


def generate_speckle_pattern(width, height, pitch_um, speckle_size_um, density, seed=None):
    """
    A rectangular speckle pattern: PIL.Image (mode 'L'), black square speckles on white.

    Parameters:
        width, height (float): Size in mm.
        pitch_um (float): Pixel size in um.
        speckle_size_um (float): Speckle side length in um, rounded to whole pixels.
        density (float): Fraction of the area covered by speckles, 0 to 1.
        seed (int | None, optional): Seed for a reproducible pattern.
    """
    pitch_mm = pitch_um / 1000.0
    width_px = max(1, int(round(width / pitch_mm)))
    height_px = max(1, int(round(height / pitch_mm)))
    print(f"Generating speckle pattern: {width}x{height} mm = {width_px}x{height_px} px, "
          f"speckle {speckle_px(pitch_mm, speckle_size_um)} px, density {density:.3f}")
    speckles = speckle_raster(np.ones((height_px, width_px), bool), pitch_mm, speckle_size_um, density, seed)
    return Image.fromarray(np.where(speckles, 0, 255).astype(np.uint8), mode="L")


def multiscale_blue_speckle(width_px, height_px,
                            min_size_px=12,  # size of the smallest dots
                            octaves=4,
                            density=0.1,
                            seed=None):
    rng = default_rng(seed)
    img = Image.new("L", (width_px, height_px), color=255)
    draw = ImageDraw.Draw(img)

    base_size_px = min_size_px * (2 ** (octaves - 1))
    coverage_per_octave = density / (octaves - 1)
    # helper: poisson radius in [0,1]^2 for ~target_n points
    def radius_for_n(n):
        # like your formula, scaled a bit “safe” for rejection sampling
        return math.sqrt(1.0 / (n * math.pi)) * 1.45

    total_area = width_px * height_px

    # optional occupancy mask (prevents smaller dots from erasing bigger ones)
    occ = np.zeros((height_px, width_px), dtype=bool)

    for i in range(octaves):
        print(f"Generating octave {i+1}/{octaves} with dot size ~{base_size_px // (2 ** i)} px")
        size_i = max(1, int(round(base_size_px / (2 ** i))))
        # keep roughly constant area contribution from each octave
        area_per_dot = size_i * size_i
        target_n = max(1, int(coverage_per_octave * total_area / area_per_dot))

        # blue-noise sampling in [0,1]^2
        # compute radius assuming target_n in unit square
        r = radius_for_n(target_n)
        eng = qmc.PoissonDisk(d=2, radius=r, seed=rng.integers(1<<31))
        pts = eng.random(target_n)  # [0,1]^2

        xs = (pts[:,0] * width_px).astype(int)
        ys = (pts[:,1] * height_px).astype(int)
        radius = size_i // 2

        for cx, cy in zip(xs, ys):
            radius = size_i // 2

            # intended square bbox (can go outside the image — that's OK for Pillow)
            x1, y1 = cx - radius, cy - radius
            x2, y2 = cx + radius, cy + radius

            # draw with the *unclamped* square bbox (Pillow will clip at edges without distorting)
            draw.ellipse([x1, y1, x2, y2], fill=0)

            # update occupancy with the intersection of bbox and the image bounds
            ix1 = max(0, x1)
            iy1 = max(0, y1)
            ix2 = min(width_px - 1, x2)
            iy2 = min(height_px - 1, y2)

            if ix1 <= ix2 and iy1 <= iy2:  # only mark if something actually overlaps
                occ[iy1:iy2 + 1, ix1:ix2 + 1] = True

    # slight antialias to reduce stair-stepping at small scales
    # use resize with resample to perform interpolation (filter expects ImageFilter)
    try:
        img = img.resize(img.size, resample=Image.Resampling.BILINEAR)
    except AttributeError:
        # Pillow older versions may expose resampling as Image.BILINEAR
        img = img.resize(img.size, resample=Image.BILINEAR)
    return img


def calculate_black_pixel_density(img, threshold=0.5):
    """
    Calculates the ratio of black pixels to total pixels in an image.
    
    Parameters:
        img (numpy.ndarray): Input image (grayscale or RGB).
        threshold (float): Threshold for considering a pixel as "black".
                           For grayscale images, pixels below this (0–1 or 0–255) are black.
    
    Returns:
        float: Ratio of black pixels to total pixels (between 0 and 1).
    """
    # Convert to grayscale if RGB
    if img.ndim == 3:
        img_gray = np.mean(img, axis=2)
    else:
        img_gray = img
    
    # Normalize if values are in 0–255 range
    if img_gray.max() > 1.0:
        img_gray = img_gray / 255.0
    
    # Count black pixels
    black_pixels = np.sum(img_gray < threshold)
    total_pixels = img_gray.size
    print(f"Black pixels: {black_pixels}, Total pixels: {total_pixels}")
    
    return black_pixels / total_pixels


if __name__ == "__main__":
    # Example usage:
    width = 21
    height = width  # non-square sizes work too
    pitch_um = 33      # pixel pitch in micrometers
    speckle_size_um = 99 # should be a multiple of pitch_um
    density = 0.25        # fraction of area covered by speckles [0..1]

    dpi = 25.4 * 1000 / pitch_um # max dpi on engraver is 999

    img = generate_speckle_pattern(width=width, height=height, pitch_um=pitch_um, speckle_size_um=speckle_size_um, density=density)
    image_name = f"speckle_{width}x{height}_size{speckle_size_um}um_density{int(density*100)}_dpi{round(dpi)}.png"
    """img = multiscale_blue_speckle(
        width_px=int(round((width * 1000.0) / pitch_um)),
        height_px=int(round((height * 1000.0) / pitch_um)),
        min_size_px=speckle_size_um // pitch_um,
        octaves=5,
        density=density,
        seed=42
    )"""
    image_name = f"speckle_{width}x{height}_size{speckle_size_um}um_density{int(density*100)}_dpi{round(dpi)}.png"
    image_path = f"./speckle_patterns/{image_name}"
    img.save(image_path, dpi=(dpi, dpi))
    print(f"Speckle pattern saved to {image_path}.")
    print(f"Actual black pixel density: {calculate_black_pixel_density(np.array(img), threshold=0.5):.4f}")
    img.show()
