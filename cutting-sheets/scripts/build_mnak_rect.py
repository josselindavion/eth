# -*- coding: utf-8 -*-
"""
build_mnak_rect.py -- Complementary catalogue: RECTANGULAR Mini-Nakajima, with and without holes (proposal of Erik,
02/11/2026).

Run (from the repository root):
    py cutting-sheets/scripts/build_mnak_rect.py

Input : cutting-sheets/catalogue/RoundSample_Dual_Hole_rectange.dxf (SolidWorks export of the part, mm, all colour 7)
Output: cutting-sheets/catalogue/specimen_templates_extra_MNAK_RECT.dxf, in the format of the lab catalogue:
        one block per specimen, named MNAK_RECT_HOLE_<angle digit><index> (2 holes) or MNAK_RECT_FULL_<...>
        (no holes), placed at its angle (0, 45, 90 deg; index 0 to 9, as MNAK_HOLE / MNAK_FULL), qualities by
        colour (3 = Q3, 5 = Q5).

Frame and code (decided on 02/11/2026):
    - frame of Erik's part, not turned: rectangle 54 (x) x 80 (y) mm, ends (short sides, 49 mm) at y = +-40,
      holes (R3.9) at (0, +-9), i.e. along the long axis;
    - notch code on the END y = +40, starting at x = CODE_X0 (as on the bars of the catalogue), Q3 lines on both sides
      up to the corners;
    - angle of the specimen (written in the code): SAME HOLE ORIENTATION AS THE DISC MNAK_HOLE with the same angle:
      holes at angle + 90 deg (angle 90 = holes along the rolling direction); since the holes of the rectangle lie
      along the coded end, the coded end is at angle - 90 deg (ANGLE_OFFSET);
    - qualities as on the disc: outline Q3 (green), holes Q5 (blue), code Q5;
    - marker CHAMFER: Erik's part is symmetric; the R2 corner on the left of the coded end (code on top) is replaced
      by a 45 deg chamfer of CHAMFER mm, like the chamfered corner of the other specimens, to know from which face the
      code is read;
    - version without holes: the same without the two circles.
"""
import math
import os
import sys

import ezdxf
from ezdxf.math import Matrix44

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import notchcode as nc                   # noqa: E402

SRC = os.path.join(HERE, '..', 'catalogue', 'RoundSample_Dual_Hole_rectange.dxf')
OUT = os.path.join(HERE, '..', 'catalogue', 'specimen_templates_extra_MNAK_RECT.dxf')
ANGLE_OFFSET = -90.0                     # coded end at angle - 90 deg: holes oriented as on the disc MNAK_HOLE
ROT_DEG = 0.0                            # rotation of Erik's part: none (the end y = +40 carries the code)
FAMILIES = (('MNAK_RECT_HOLE', True), ('MNAK_RECT_FULL', False))     # (family, with holes)
CHAMFER = 4.0                            # mm, legs of the 45 deg chamfer at the top-left corner
ANGLE_DIGITS = (0, 3, 6)                 # 0, 45, 90 deg, as MNAK_HOLE in the lab catalogue
CODE_X0, FLAT_Y = -6.0, 40.0          # start of the code (as on the bars); edge of the coded end
LAYERS = {3: 'Normal_Quality', 5: 'High_Quality'}


def base_entities(holes=True):
    """Entities of the part; the edge of the coded end is replaced by its two Q3 pieces (added with the code);
    the top-left corner (R2 arc) becomes a chamfer; no holes if holes is false."""
    doc = ezdxf.readfile(SRC)
    rot = Matrix44.z_rotate(math.radians(ROT_DEG))
    ents, flat, corner = [], None, None
    for e in doc.modelspace():
        x = e.copy()
        x.transform(rot)
        t = x.dxftype()
        if t == 'LINE' and abs(x.dxf.start.y - FLAT_Y) < 1e-6 and abs(x.dxf.end.y - FLAT_Y) < 1e-6:
            flat = sorted((x.dxf.start.x, x.dxf.end.x))
            continue
        if t == 'CIRCLE' and not holes:
            continue
        ents.append((x, 5 if t == 'CIRCLE' else 3))
    if flat is None:
        raise SystemExit('edge y = %g not found in %s' % (FLAT_Y, SRC))
    # top-left corner: arc whose centre is the furthest up and left
    arcs = [(e, c) for e, c in ents if e.dxftype() == 'ARC']
    arc, _ = min(arcs, key=lambda ec: ec[0].dxf.center.x - ec[0].dxf.center.y)
    cx, cy, r = arc.dxf.center.x, arc.dxf.center.y, arc.dxf.radius
    x0, y1 = cx - r, cy + r                         # left edge (x = x0) and top edge (y = y1) of the part
    for e, c in ents:
        if e.dxftype() != 'LINE':
            continue
        for end in ('start', 'end'):
            p = getattr(e.dxf, end)
            if abs(p.x - x0) < 1e-6 and abs(p.y - cy) < 1e-6:          # end of the left edge -> moved down
                setattr(e.dxf, end, (x0, y1 - CHAMFER, 0))
                corner = True
            elif abs(p.x - cx) < 1e-6 and abs(p.y - y1) < 1e-6:       # end of the top edge -> moved right
                setattr(e.dxf, end, (x0 + CHAMFER, y1, 0))
    if not corner:
        raise SystemExit('top-left corner not found')
    if abs(flat[0] - cx) < 1e-6 and abs(y1 - FLAT_Y) < 1e-6:     # the coded edge starts at the chamfered corner
        flat = [x0 + CHAMFER, flat[1]]
    ents = [(e, c) for e, c in ents if e is not arc]
    out = ezdxf.new('R2000')
    ents.append((out.modelspace().add_line((x0, y1 - CHAMFER), (x0 + CHAMFER, y1)), 3))
    return ents, flat


def main():
    out = ezdxf.new('R2000', setup=True)
    out.header['$INSUNITS'] = 4
    for c, name in LAYERS.items():
        out.layers.add(name, color=c)
    msp = out.modelspace()
    k = 0
    for family, holes in FAMILIES:
        ents, (fx0, fx1) = base_entities(holes)
        for a in ANGLE_DIGITS:
            for idx in range(10):
                name = '%s_%d%d' % (family, a, idx)
                blk = out.blocks.new(name)
                for e, c in ents:
                    y = e.copy()
                    y.dxf.layer, y.dxf.color = LAYERS[c], c
                    blk.add_foreign_entity(y, copy=False)
                lines, length = nc.code_lines(a, idx)
                blk.add_line((fx0, FLAT_Y), (CODE_X0, FLAT_Y), dxfattribs={'layer': LAYERS[3], 'color': 3})
                for (u0, v0), (u1, v1) in lines:
                    blk.add_line((CODE_X0 + u0, FLAT_Y + v0), (CODE_X0 + u1, FLAT_Y + v1),
                                 dxfattribs={'layer': LAYERS[5], 'color': 5})
                blk.add_line((CODE_X0 + length, FLAT_Y), (fx1, FLAT_Y), dxfattribs={'layer': LAYERS[3], 'color': 3})
                msp.add_blockref(name, (120.0 * (k % 10), -120.0 * (k // 10)),
                                 dxfattribs={'rotation': 15.0 * a + ANGLE_OFFSET})
                k += 1
    out.saveas(OUT)
    print('%d blocks (%s) -> %s' % (k, ', '.join(f for f, _ in FAMILIES), os.path.abspath(OUT)))

if __name__ == '__main__':
    main()
