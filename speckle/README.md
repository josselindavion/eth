# speckle

Speckle patterns engraved on the specimens for DIC (digital image correlation).

`speckle_generator.py`: received from Ruben Zwicker (Inspire AG) on 16/11/2026, kept as received.

| Function | What it does |
|---|---|
| `speckle_raster(mask, pitch_mm, size_um, density, seed)` | the pattern used: square speckles, centres by Poisson-disk sampling (blue noise, even spacing, no clusters) over the bounding box of `mask`, thinned at random to the target count, clipped to the mask; returns a bool array (True = engrave) |
| `generate_speckle_pattern(width, height, pitch_um, speckle_size_um, density, seed)` | the same on a full rectangle (mm), as a PIL image, black speckles on white |
| `speckle_px(pitch_mm, size_um)` | speckle side in whole pixels |
| `calculate_black_pixel_density(img)` | measured fraction of black pixels |
| `multiscale_blue_speckle(...)` | older variant: round dots of several sizes (octaves); not used |
| `_blue_noise_samples`, `_poisson_radius_for_target_n` | older helpers (Mitchell best candidate); not used |

Parameters (Ruben): pitch 33 µm = pixel size, close to the minimum resolution of the engraver (do not go below);
speckle size a multiple of the pitch (default 99 µm = 3 px); density = covered fraction (default 0.25). For engraving
the array is converted to DXF.

`show_speckle.py`: shows a pattern at once, nothing saved: `py show_speckle.py [width_mm] [height_mm] [speckle_um]
[density]` (default 21 × 21 mm, 99 µm, 0.25).

Needs numpy, scipy ≥ 1.15 (`qmc.PoissonDisk(..., rng=)`), Pillow. Lab PC (Python 3.7, scipy 1.7.3, no PoissonDisk):
`_poisson_compat.py` adds a small PoissonDisk (Bridson) when scipy's is missing or too old; `show_speckle.py` uses it
(same result: density 0.249 for 0.25, every centre at least the radius apart). The `__main__` example saves into
`./speckle_patterns/` (create the folder first).
