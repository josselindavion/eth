"""
speckle_quality.py -- Quality of an engraved speckle pattern for DIC (user, 24-25/11/2026).

1. Camera model. The engraved pattern (bool raster at the engraver pitch, 33 um; True = speckle) is seen by the camera
   of the test: grey levels dark 0.1 / light 0.9, each camera pixel integrates the engraved raster under it (image
   scale in um/px from Beerli et al. 2026, Table 1), optical blur (Gaussian, 0.6 camera px) and camera noise (Gaussian,
   2 % of the grey range, independent on every image).
2. DIC. The images are correlated subset by subset, as in VIC-2D: square subset (size from Beerli Table 2), first-order
   (affine) shape function u(x, y) = u + ux.dx + uy.dy (same for v), Gauss-Newton on the sum of squared differences,
   bicubic interpolation of the deformed image.
3. Virtual tests (the "fake" deformations): the deformed image is made by moving the engraved pattern by a known
   amount, then seen again by the camera with new noise, so the exact answer is known:
       translation test: rigid shifts of 0.25 camera px in x and 0.5 camera px in y; error of the measured
                         displacement (bias and RMS, in px and um) = matching precision of the pattern;
       strain test:      uniform uniaxial stretch, exx = 1 %, eyy = -0.5 % (like a tensile test); error of the measured
                         strain exx = ux of each subset (bias and standard deviation = "strain noise"), no strain filter.
4. Pattern indicators, on the camera image of the undeformed pattern:
       coverage   fraction of the engraved raster that is speckle (real density, overlaps counted once);
       MIG        mean intensity gradient = mean |grad I| (grey levels per px): contrast of the speckle edges; the
                  matching error of DIC goes roughly as noise / (MIG x subset size), so higher = better;
       size       width at half height of the autocorrelation peak of the image (px and um): the speckle size the
                  DIC really sees (blur and pixel integration included);
       entropy    Shannon entropy of the grey-level histogram (bits): how spread the grey levels are.

    from speckle_quality import quality
    q = quality(raster, pitch_um=33, cam_um=33.5, subset_px=27)
"""
import numpy as np
from scipy import ndimage

DARK, LIGHT = 0.1, 0.9
BLUR_PX = 0.6
NOISE = 0.02
SHIFTS = ((0.25, 0.0), (0.0, 0.5))                         # (ux, uy) camera px
STRAIN = (0.01, -0.005)


def camera(raster, pitch_um, cam_um, warp=None, noise=NOISE, rng=None, blur_px=BLUR_PX, margin_px=0):
    """Camera image (grey 0-1) of the engraved raster. warp(x, y) -> (X, Y): material point (um, reference) seen at the
    camera point (x, y) (um); None = no deformation. The camera field is the raster area minus margin_px camera px."""
    g = np.where(np.asarray(raster, bool), DARK, LIGHT).astype(float)
    ratio = cam_um / pitch_um
    if ratio > 1:                                            # pixel integration (box ~ Gaussian of sigma 0.42 px)
        g = ndimage.gaussian_filter(g, 0.42 * ratio)
    ny, nx = g.shape
    h = int((ny * pitch_um) // cam_um) - 2 * margin_px
    w = int((nx * pitch_um) // cam_um) - 2 * margin_px
    yy, xx = np.mgrid[0:h, 0:w]
    x = (xx + margin_px + 0.5) * cam_um                      # camera pixel centres in um
    y = (yy + margin_px + 0.5) * cam_um
    if warp is not None:
        x, y = warp(x, y)
    img = ndimage.map_coordinates(g, [y / pitch_um - 0.5, x / pitch_um - 0.5], order=1, mode='nearest')
    if blur_px > 0:
        img = ndimage.gaussian_filter(img, blur_px)
    if noise > 0:
        rng = rng if rng is not None else np.random.default_rng(0)
        img = img + rng.normal(0, noise, img.shape)
    return img


def mig(img):
    gy, gx = np.gradient(img)
    return float(np.mean(np.hypot(gx, gy)))


def speckle_size(img):
    """Width (px) at half height of the autocorrelation peak, mean of x and y."""
    f = img - img.mean()
    ac = np.fft.fftshift(np.real(np.fft.ifft2(np.abs(np.fft.fft2(f)) ** 2)))
    ac /= ac.max()
    cy, cx = np.array(ac.shape) // 2
    widths = []
    for prof in (ac[cy, cx:], ac[cy:, cx]):
        k = int(np.argmax(prof < 0.5))
        if k > 0:
            widths.append(2 * (k - 1 + (prof[k - 1] - 0.5) / (prof[k - 1] - prof[k])))
    return float(np.mean(widths)) if widths else float('nan')


def entropy(img, bins=256):
    h, _ = np.histogram(np.clip(img, 0, 1), bins=bins, range=(0, 1))
    p = h[h > 0] / float(h.sum())
    return float(-np.sum(p * np.log2(p)))


def dic_subset(ref, cur, yc, xc, half, iters=20):
    """Affine DIC of the subset of ref centred at (yc, xc): p = (u, ux, uy, v, vx, vy) with cur(x + u(x)) = ref(x).
    Gauss-Newton (forward additive, gradients of the reference). Returns p or None."""
    dy, dx = np.mgrid[-half:half + 1, -half:half + 1].astype(float)
    dx, dy = dx.ravel(), dy.ravel()
    sl = (slice(yc - half, yc + half + 1), slice(xc - half, xc + half + 1))
    r = ref[sl].ravel()
    gy, gx = np.gradient(ref)
    gx, gy = gx[sl].ravel(), gy[sl].ravel()
    J = np.column_stack([gx, gx * dx, gx * dy, gy, gy * dx, gy * dy])
    H = J.T @ J
    if np.linalg.cond(H) > 1e10:
        return None
    Hi = np.linalg.inv(H)
    p = np.zeros(6)
    for _ in range(iters):
        X = xc + dx + p[0] + p[1] * dx + p[2] * dy
        Y = yc + dy + p[3] + p[4] * dx + p[5] * dy
        w = ndimage.map_coordinates(cur, [Y, X], order=3, mode='nearest')
        dp = -Hi @ (J.T @ (w - r))
        p += dp
        if abs(dp[0]) < 1e-4 and abs(dp[3]) < 1e-4:
            break
    return p


def _grid(shape, half, n):
    """About n subset centres on a regular grid, away from the borders."""
    m = half + 6
    k = max(2, int(round(np.sqrt(n))))
    ys = np.linspace(m, shape[0] - m - 1, k).astype(int)
    xs = np.linspace(m, shape[1] - m - 1, k).astype(int)
    return [(y, x) for y in ys for x in xs]


def virtual_tests(raster, pitch_um, cam_um, subset_px, n_subsets=36, seed=0):
    """Translation and strain tests (see the module text). Returns a dict of errors."""
    rng = np.random.default_rng(seed)
    half = subset_px // 2
    ref = camera(raster, pitch_um, cam_um, noise=NOISE, rng=rng, margin_px=4)
    pts = _grid(ref.shape, half, n_subsets)
    # translation test
    err = []
    for ux, uy in SHIFTS:
        sx, sy = ux * cam_um, uy * cam_um
        cur = camera(raster, pitch_um, cam_um, warp=lambda x, y: (x - sx, y - sy), rng=rng, margin_px=4)
        for y, x in pts:
            p = dic_subset(ref, cur, y, x, half)
            if p is not None:
                err.append((p[0] - ux, p[3] - uy))
    e = np.array(err)
    # strain test: x = X (1 + exx) about the centre (same for y)
    exx, eyy = STRAIN
    ny, nx = ref.shape
    cx, cy = (nx / 2.0 + 4) * cam_um, (ny / 2.0 + 4) * cam_um
    cur = camera(raster, pitch_um, cam_um, warp=lambda x, y: (cx + (x - cx) / (1 + exx), cy + (y - cy) / (1 + eyy)),
                 rng=rng, margin_px=4)
    se = []
    for y, x in pts:
        p = dic_subset(ref, cur, y, x, half)
        if p is not None:
            se.append(p[1])                                  # du/dX = exx
    se = np.array(se)
    return {'shift_bias_px': float(e.mean()), 'shift_rms_px': float(np.sqrt(np.mean(e ** 2))),
            'shift_rms_um': float(np.sqrt(np.mean(e ** 2)) * cam_um),
            'strain_bias': float(se.mean() - exx), 'strain_noise': float(se.std(ddof=1))}


def quality(raster, pitch_um, cam_um, subset_px, seed=0):
    """Every indicator of a pattern for a camera of cam_um um/px and a DIC subset of subset_px px: dict."""
    raster = np.asarray(raster, bool)
    clean = camera(raster, pitch_um, cam_um, noise=0)
    noisy = camera(raster, pitch_um, cam_um, rng=np.random.default_rng(seed))
    size = speckle_size(clean)
    q = {'coverage': float(raster.mean()), 'mig': mig(noisy), 'seen_px': size, 'seen_um': size * cam_um,
         'entropy': entropy(noisy)}
    q.update(virtual_tests(raster, pitch_um, cam_um, subset_px, seed=seed))
    return q
