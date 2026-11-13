# -*- coding: utf-8 -*-
"""
make_delivery.py -- Delivery folder of the templates (user, 13/11/2026):

    <folder>/templates.pdf       every template: name, content, specimens drawn (colour plan), rolling direction
    <folder>/instructions.pdf    for each material: which sheet gets which template (and which DXF file)
    <folder>/dxf/ETH_<RD>x<TD>mm_<NAME>_<n>_SHEET_<k>_<version>.dxf   one DXF per template (lab naming convention,
                                 13/11/2026; a module on 2 sheets is split in 2 files) + a PDF with the same name
    <folder>/README.txt

    py cutting-sheets/scripts/make_delivery.py cutting-sheets/delivery/templates_2026-11-13

The templates are the plans of the module orders (runs/MOD_*/; run them first). Each DXF is the sheet of the plan
moved to the origin (bottom-left corner = clamp corner), checked after writing (one frame, same number of pieces).
"""
import os
import subprocess
import sys

import ezdxf
from ezdxf import bbox

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sheetlib                                              # noqa: E402
from make_dxf_sheet_pdf import make as sheet_pdf             # noqa: E402
from materials_data import MATERIALS, MODULE_ORDERS, assign, dxf_name, pieces, plan_dir, templates   # noqa: E402

OUT = os.path.abspath(sys.argv[1])
DXF = os.path.join(OUT, 'dxf')
os.makedirs(DXF, exist_ok=True)
for f in os.listdir(DXF):                                   # start clean: old names go
    os.remove(os.path.join(DXF, f))

# 1. one DXF per template
names = []
for mod in MODULE_ORDERS:
    for t in templates(mod):
        tid, order, idx, rd, td, entry = t
        src = os.path.join(plan_dir(order), order + '.dxf')
        fx, fy, fx1, fy1 = sheetlib.frames(sheetlib.Drawing(src))[idx].bounds
        doc = ezdxf.readfile(src)
        msp = doc.modelspace()
        for e in list(msp):
            b = bbox.extents([e])
            if b.has_data and b.extmin.x >= fx - 1 and b.extmax.x <= fx1 + 1:
                e.translate(-fx, -fy, 0)
            else:
                msp.delete_entity(e)
        path = os.path.join(DXF, dxf_name(t))
        doc.saveas(path)
        d = sheetlib.Drawing(path)
        fr = [f.bounds for f in sheetlib.frames(d)]
        n = len(sheetlib.pieces(d))
        assert len(fr) == 1 and abs(fr[0][2] - td) < 0.5 and abs(fr[0][3] - rd) < 0.5, (path, fr)
        assert n == len(pieces(order, idx)), (path, n, len(pieces(order, idx)))
        names.append((dxf_name(t), tid, rd, td, n))
        print('written dxf/%s (%d pieces)' % (dxf_name(t), n))
        sheet_pdf(path)                                      # PDF with the same name, layout of the lab's drawings

# 2. the two PDFs
py = sys.executable
for script, name in (('make_module_templates_pdf.py', 'templates.pdf'),
                     ('make_material_templates_pdf.py', 'instructions.pdf')):
    subprocess.check_call([py, os.path.join(HERE, script), os.path.join(OUT, name)])

# 3. README
used = {}
for m in MATERIALS:
    use, missing = assign(m)
    for i, put in use:
        for p in put:
            used.setdefault(p[0], []).append('%s-%d' % (m[1], i + 1))
with open(os.path.join(OUT, 'README.txt'), 'w', encoding='utf-8') as f:
    f.write('Cutting templates, Mohr lab, ETH Zurich (waterjet)\n\n'
            'templates.pdf     every template: name, content (rate, type, angles, number), specimens drawn in colour,\n'
            '                  rolling direction (RD = vertical on the plans)\n'
            'instructions.pdf  for each material: which sheet gets which template, and which DXF file to cut\n'
            'dxf/              one DXF per template, sheet frame at the origin (bottom-left corner = clamp corner),\n'
            '                  and a PDF with the same name (drawing of the sheet: RD, qualities, dimensions)\n'
            '                  name: ETH_<RD>x<TD>mm_<NAME>_<sheets of the module>_SHEET_<sheet>_<version>\n'
            '                  NAME: SLOW78 = slow, INT66 = intermediate (medium) rate, FAST66 = high rate,\n'
            '                  INTFAST36 = intermediate + fast of campaign C, SLOWINTFAST_210 = whole campaign A\n\n'
            'Sizes RD x TD in mm (RD = rolling direction, first value). Lay every template with its RD along the RD of\n'
            'the sheet, in the bottom-left corner of the sheet.\n\n')
    for fn, tid, rd, td, n in names:
        f.write('%s\n    template %s, %d pieces, cut on: %s\n' % (fn, tid, n, ', '.join(used.get(tid, [])) or 'not used yet'))
print('written %s' % OUT)
