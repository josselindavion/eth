"""
speckle_quality.py -- Quality of a speckle pattern for DIC (user, 24/11/2026).

The pattern (bool raster at the engraver pitch, True = speckle) is turned into a grey image as a camera would see it:
speckles dark (0.1), background light (0.9), a slight blur (optics) and camera noise. Assumption: one camera pixel =
one pattern pixel (no camera preset on purpose); every result is also given in um with the pitch.

Indicators:
    coverage      fraction of the area that is speckle (real density, overlaps counted once)
    MIG           mean intensity gradient (grey levels per px): higher = sharper, more contrast = better DIC
    speckle size  width of the autocorrelation peak at half height (px and um): the real speckle size seen by DIC
    entropy       Shannon entropy of the grey levels (bits): spread of the grey levels
    virtual test  known sub-pixel shifts imposed on the image (Fourier shift), measured back on many subsets with a
                  translation DIC (Gauss-Newton, the core of a DIC code); bias and RMS of the error (px and um)

    from speckle_quality import quality
    q = quality(raster, pitch_um=33)
"""
import numpy as np
from scipy import ndimage

DARK, LIGHT = 0.1, 0.9


def camera_image(raster, blur_px=0.6, noise=0.0, rng=None):
    """Grey image (0-1) of a pattern as a camera would see it: dark speckles, light background, blur, noise."""
    img = np.where(np.asarray(raster, bool), DARK, LIGHT).astype(float)
    if blur_px > 0:
        img = ndimage.gaussian_filter(img, blur_px)
    if noise > 0:
        rng = rng if rng is not None else np.random.default_rng(0)
        img = img + rng.normal(0, noise, img.shape)
    return img


def mig(img):
    """Mean intensity gradient (grey levels per px)."""
    gy, gx = np.gradient(img)
    return float(np.mean(np.hypot(gx, gy)))


def speckle_size(img):
    """Width (px) at half height of the autocorrelation peak, mean of the x and y directions."""
    f = img - img.mean()
    ac = np.fft.fftshift(np.real(np.fft.ifft2(np.abs(np.fft.fft2(f)) ** 2)))
    ac /= ac.max()
    cy, cx = np.array(ac.shape) // 2
    widths = []
    for prof in (ac[cy, cx:], ac[cy:, cx]):
        k = int(np.argmax(prof < 0.5))                       # first sample under half height
        if k == 0:
            continue
        x = k - 1 + (prof[k - 1] - 0.5) / (prof[k - 1] - prof[k])
        widths.append(2 * x)
    return float(np.mean(widths)) if widths else float('nan')


def entropy(img, bins=256):
    """Shannon entropy (bits) of the grey levels."""
    h, _ = np.histogram(np.clip(img, 0, 1), bins=bins, range=(0, 1))
    p = h[h > 0] / float(h.sum())
    return float(-np.sum(p * np.log2(p)))


def _dic_shift(ref, cur, y, x, half, iters=12):
    """Translation (uy, ux) of the subset of ref centred at (y, x), size 2*half+1, found in cur: cur(p + u) = ref(p).
    Gauss-Newton on the sum of squared differences, gradients of the reference (DIC, translation only)."""
    sl = (slice(y - half, y + half + 1), slice(x - half, x + half + 1))
    r = ref[sl]
    gy, gx = np.gradient(ref)
    gy, gx = gy[sl].ravel(), gx[sl].ravel()
    H = np.array([[gy @ gy, gy @ gx], [gx @ gy, gx @ gx]])
    if np.linalg.cond(H) > 1e8:
        return np.array([np.nan, np.nan])
    Hi = np.linalg.inv(H)
    u = np.zeros(2)
    m = half + 6                                             # window with a margin for the interpolation
    win = cur[y - m:y + m + 1, x - m:x + m + 1]
    for _ in range(iters):
        w = ndimage.shift(win, -u, order=3, mode='nearest')[6:-6, 6:-6]
        e = (w - r).ravel()
        du = -Hi @ np.array([gy @ e, gx @ e])
        u += du
        if np.hypot(*du) < 1e-4:
            break
    return u


def virtual_test(raster, subset=31, shifts=(0.25, 0.5, 0.75), n_subsets=40, noise=0.02, blur_px=0.6, seed=0):
    """Known shifts (in x and in y) imposed on the camera image, measured back with a translation DIC on n_subsets
    subsets of subset x subset px. Returns (bias, rms) of the error in px (mean signed error, root mean square)."""
    rng = np.random.default_rng(seed)
    clean = camera_image(raster, blur_px)
    ref = clean + rng.normal(0, noise, clean.shape)
    half = subset // 2
    m = half + 10
    ny, nx = clean.shape
    pts = np.column_stack([rng.integers(m, ny - m, n_subsets), rng.integers(m, nx - m, n_subsets)])
    errs = []
    for s in shifts:
        for d in ((0.0, s), (s, 0.0)):
            cur = np.real(np.fft.ifft2(ndimage.fourier_shift(np.fft.fft2(clean), d)))
            cur = cur + rng.normal(0, noise, cur.shape)
            for y, x in pts:
                u = _dic_shift(ref, cur, y, x, half)
                errs.append(u - np.array(d))
    e = np.array(errs)
    e = e[np.isfinite(e).all(axis=1)]
    return float(np.mean(e)), float(np.sqrt(np.mean(e ** 2)))


def quality(raster, pitch_um, subset=31, blur_px=0.6, noise=0.02, seed=0):
    """Every indicator of a pattern: dict (see the module text)."""
    raster = np.asarray(raster, bool)
    img = camera_image(raster, blur_px, noise, np.random.default_rng(seed))
    size = speckle_size(camera_image(raster, blur_px))
    bias, rms = virtual_test(raster, subset=subset, noise=noise, blur_px=blur_px, seed=seed)
    return {'coverage': float(raster.mean()), 'mig': mig(img), 'speckle_px': size, 'speckle_um': size * pitch_um,
            'entropy': entropy(img), 'bias_px': bias, 'rms_px': rms, 'rms_um': rms * pitch_um}
