# speckle

Speckle patterns engraved on the specimens for DIC (digital image correlation).

| File | What it does |
|---|---|
| `speckle_generator.py` | generator of Ruben Zwicker (Inspire AG, 16/11/2026), cleaned on 24/11/2026; `speckle_raster(mask, pitch_mm, size_um, density, seed, shape)`: blue-noise speckles (Poisson-disk centres), clipped to a mask, bool raster (True = engrave); `generate_speckle_pattern(...)` the same on a rectangle as an image; `preset(name)`, `setup(name)` read the presets; shapes: `square` (Ruben's, same result for the same seed), `circle`, `rotated_square`, `ellipse` (aspect 2), `polygon` (irregular, 5-8 vertices), all with the area of the square |
| `speckle_settings.yaml` | presets `slow`, `int`, `fast`: the pattern (size, density; updated with the study) and the DIC setup of Beerli et al. 2026 used to evaluate it (image scale, subset; Tables 1-2) |
| `speckle_quality.py` | camera model (pixel integration at the image scale of the test, blur, noise), affine subset DIC (as VIC-2D), virtual tests (sub-pixel translation; uniform 1 % strain = "fake elongation") and indicators (strain noise, displacement error, MIG, coverage, seen size, entropy) |
| `parameter_study.py` | stage 1: size × density (square, circle, 4 draws), stage 2: the five shapes at the best cell (8 draws, Welch t-tests); `results/parameter_study.csv` (`--quick` to test) |
| `make_report.py` | A4 report `results/speckle_report.pdf` (method, results per test with analyses, gallery) and one PNG per shape and test in `results/shapes/` |
| `show_speckle.py` | shows a pattern at once, nothing saved: `py show_speckle.py [preset] [width_mm] [height_mm] [shape]` |

Parameters (Ruben): pitch 33 µm = pixel size, close to the minimum resolution of the engraver (do not go below);
speckle size a multiple of the pitch. For engraving the raster is converted to DXF (at Inspire).

Needs Python ≥ 3.10 with numpy, scipy ≥ 1.15, Pillow, PyYAML, matplotlib. Lab PC: `py -3.1` (Python 3.14):

    py -3.1 -m pip install numpy scipy pillow pyyaml matplotlib
    py -3.1 show_speckle.py
    py -3.1 compare_shapes.py
