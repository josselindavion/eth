"""
show_speckle.py -- Show a speckle pattern right away, nothing saved.

    py show_speckle.py                          -> preset slow, 21 x 21 mm, square speckles
    py show_speckle.py int 30 10                -> preset int, 30 x 10 mm
    py show_speckle.py fast 30 10 circle        -> preset fast, 30 x 10 mm, round speckles

Presets (slow, int, fast) in speckle_settings.yaml; shapes: square, circle, rotated_square, ellipse, polygon.
The image opens in the default image viewer.
"""
import sys

from speckle_generator import generate_speckle_pattern, preset

a = sys.argv[1:]
name = a[0] if len(a) > 0 else 'slow'
width = float(a[1]) if len(a) > 1 else 21
height = float(a[2]) if len(a) > 2 else width
shape = a[3] if len(a) > 3 else 'square'

generate_speckle_pattern(width, height, **preset(name), shape=shape).show()
