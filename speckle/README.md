# speckle

Speckle patterns engraved on the specimens for DIC (digital image correlation).

| File | What it does |
|---|---|
| `speckle_generator.py` | generator of Ruben Zwicker (Inspire AG, 16/11/2026), cleaned on 24/11/2026 (unused functions and prints removed); `speckle_raster(mask, pitch_mm, size_um, density, seed, shape)`: blue-noise speckles (Poisson-disk centres, thinned to the target number), clipped to a mask, bool raster (True = engrave); `generate_speckle_pattern(...)` the same on a rectangle as an image; `preset(name)` reads a preset; shapes: `square` (Ruben's, same result for the same seed), `circle`, `rotated_square`, `ellipse` (aspect 2), `polygon` (irregular, 5-8 vertices), all with the area of the square |
| `speckle_settings.yaml` | presets per strain rate: `slow`, `int`, `fast` (pitch, speckle size, density); no camera setting |
| `speckle_quality.py` | indicators: coverage, MIG (mean intensity gradient), speckle size (autocorrelation), entropy, and a virtual DIC test (known sub-pixel shifts measured back on subsets with a translation DIC: bias and RMS error) |
| `compare_shapes.py` | compares the shapes for each preset: zooms, table and charts in `results/compare_shapes.pdf` |
| `show_speckle.py` | shows a pattern at once, nothing saved: `py show_speckle.py [preset] [width_mm] [height_mm] [shape]` |

Parameters (Ruben): pitch 33 µm = pixel size, close to the minimum resolution of the engraver (do not go below);
speckle size a multiple of the pitch. For engraving the raster is converted to DXF (at Inspire).

Needs Python ≥ 3.10 with numpy, scipy ≥ 1.15, Pillow, PyYAML, matplotlib. Lab PC: `py -3.1` (Python 3.14):

    py -3.1 -m pip install numpy scipy pillow pyyaml matplotlib
    py -3.1 show_speckle.py
    py -3.1 compare_shapes.py
