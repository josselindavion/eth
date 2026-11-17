# -*- coding: utf-8 -*-
"""
show_speckle.py -- Show a speckle pattern right away, nothing saved (user, 17/11/2026).

    py show_speckle.py                       -> 21 x 21 mm, speckle 99 um, density 0.25
    py show_speckle.py 30 10                 -> 30 x 10 mm
    py show_speckle.py 30 10 132 0.3         -> 30 x 10 mm, speckle 132 um, density 0.3

Uses generate_speckle_pattern() of speckle_generator.py (pitch 33 um). The image opens in the default image viewer.
"""
import sys

import _poisson_compat
_poisson_compat.install()                                    # old scipy (lab PC: Python 3.7, scipy 1.7.3)
from speckle_generator import generate_speckle_pattern       # noqa: E402

a = sys.argv[1:]
width = float(a[0]) if len(a) > 0 else 21
height = float(a[1]) if len(a) > 1 else width
size_um = float(a[2]) if len(a) > 2 else 99
density = float(a[3]) if len(a) > 3 else 0.25

generate_speckle_pattern(width, height, pitch_um=33, speckle_size_um=size_um, density=density).show()
