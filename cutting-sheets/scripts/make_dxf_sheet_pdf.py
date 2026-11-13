# -*- coding: utf-8 -*-
"""
make_dxf_sheet_pdf.py -- One PDF per DXF, with exactly the same name (.pdf instead of .dxf), in the layout of the
lab's sheet drawings (ETH_600x500mm_2_SHEET_v20250220.pdf; user 13/11/2026): rolling-direction arrow, the three
cutting qualities with an arrow to a line of that colour, the name box (ETH/<size>_ / <rest> / version), the sheet
with its cut lines in the EDM colours, and its dimensions (without "min").

    py cutting-sheets/scripts/make_dxf_sheet_pdf.py <file.dxf> [...]        -> <file.pdf> next to each DXF

One page per sheet frame of the DXF. No "Mikrosteg" label: the DXF have no micro-joints (no red entity); it is
added automatically when a DXF has red (colour 1) entities.
"""
import os
import sys

from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sheetlib                                              # noqa: E402

FONT = 'Helvetica'
for d in ('/usr/share/fonts/truetype/dejavu', 'C:/Windows/Fonts'):
    if os.path.exists(os.path.join(d, 'DejaVuSans.ttf')):
        pdfmetrics.registerFont(TTFont('Sans', os.path.join(d, 'DejaVuSans.ttf')))
        FONT = 'Sans'
        break
PW, PH = 720, 540                                            # points, as the lab's drawings (10 x 7.5 in)
ACI = {1: colors.Color(1, 0, 0), 3: colors.Color(0.0, 0.78, 0.0), 4: colors.Color(0.0, 0.72, 0.88),
       5: colors.Color(0.0, 0.0, 1.0), 7: colors.black}
LABEL = {3: ('Normal quality', '(Q3)', colors.Color(0.0, 0.69, 0.31)),
         4: ('Medium', 'quality (Q4)', colors.Color(0.0, 0.69, 0.94)),
         5: ('Highest quality', '(Q5)', colors.Color(0.0, 0.44, 0.75)),
         1: ('Mikrosteg', '', colors.Color(1, 0, 0))}
ARROW_BLUE = colors.Color(0.31, 0.51, 0.74)
ARROW_EDGE = colors.Color(0.22, 0.37, 0.55)


def arrow_head(c, x0, y0, x1, y1, size=6):
    """Line from (x0, y0) to (x1, y1) with a filled head at the end."""
    import math
    c.line(x0, y0, x1, y1)
    a = math.atan2(y1 - y0, x1 - x0)
    p = c.beginPath()
    p.moveTo(x1, y1)
    p.lineTo(x1 - size * math.cos(a - 0.35), y1 - size * math.sin(a - 0.35))
    p.lineTo(x1 - size * math.cos(a + 0.35), y1 - size * math.sin(a + 0.35))
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def name_box(stem):
    """'ETH_600x500mm_FAST66_1_SHEET_1_v20261113' -> ('ETH/600x500mm_', 'FAST66_1_SHEET_1', 'v20261113')"""
    base, ver = stem.rsplit('_v', 1) if '_v' in stem else (stem, '')
    parts = base.split('_')
    return '%s/%s_' % (parts[0], parts[1]), '_'.join(parts[2:]), ('v' + ver) if ver else ''


def page(c, d, frame, stem):
    fx, fy, fx1, fy1 = frame.bounds
    W, H = fx1 - fx, fy1 - fy                                # TD, RD in mm
    # sheet area on the page (right part), as in the lab's drawings
    bx0, bx1, by0, by1 = 228, 690, 40, 525
    sc = min((bx1 - bx0) / W, (by1 - by0) / H)
    ox = bx0 + (bx1 - bx0 - W * sc) / 2
    oy = by1 - H * sc
    segs = [s for s in d.segs if fx - 1 <= min(p[0] for p in s.pts) and max(p[0] for p in s.pts) <= fx1 + 1]
    # sheet outline and cut lines
    c.setStrokeColor(colors.Color(0.35, 0.35, 0.35))
    c.setLineWidth(0.6)
    c.rect(ox, oy, W * sc, H * sc, fill=0, stroke=1)
    c.setLineWidth(0.35)
    pts_by_col = {}
    for s in segs:
        if s.color == 7:
            continue
        c.setStrokeColor(ACI.get(s.color, colors.black))
        p = c.beginPath()
        p.moveTo(ox + (s.pts[0][0] - fx) * sc, oy + (s.pts[0][1] - fy) * sc)
        for x, y in s.pts[1:]:
            p.lineTo(ox + (x - fx) * sc, oy + (y - fy) * sc)
        c.drawPath(p, stroke=1, fill=0)
        mid = s.pts[len(s.pts) // 2]
        pts_by_col.setdefault(s.color, []).append((ox + (mid[0] - fx) * sc, oy + (mid[1] - fy) * sc))
    # dimensions (no "min")
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.black)
    c.setLineWidth(0.8)
    yd = oy - 10
    arrow_head(c, ox + W * sc / 2, yd, ox, yd, 5)
    arrow_head(c, ox + W * sc / 2, yd, ox + W * sc, yd, 5)
    c.setFont(FONT, 13)
    c.drawCentredString(ox + W * sc / 2, yd - 16, '%d mm' % round(W))
    xd = ox + W * sc + 12
    arrow_head(c, xd, oy + H * sc / 2, xd, oy, 5)
    arrow_head(c, xd, oy + H * sc / 2, xd, oy + H * sc, 5)
    c.saveState()
    c.translate(xd + 18, oy + H * sc / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, '%dmm' % round(H))
    c.restoreState()
    # rolling direction: block arrow + text
    ax, ay = 42, PH - 105
    c.setFillColor(ARROW_BLUE)
    c.setStrokeColor(ARROW_EDGE)
    c.setLineWidth(1)
    p = c.beginPath()
    p.moveTo(ax + 10, ay)
    p.lineTo(ax + 10, ay + 50)
    p.lineTo(ax, ay + 50)
    p.lineTo(ax + 20, ay + 78)
    p.lineTo(ax + 40, ay + 50)
    p.lineTo(ax + 30, ay + 50)
    p.lineTo(ax + 30, ay)
    p.close()
    c.drawPath(p, stroke=1, fill=1)
    c.setFillColor(colors.black)
    c.setFont(FONT, 13)
    for k, t in enumerate(('Rolling', 'Direction', '0°')):
        c.drawCentredString(ax + 88, ay + 58 - k * 17, t)
    # qualities: label + arrow to the nearest line of that colour
    anchors = {3: (150, 345), 4: (110, 280), 5: (95, 215), 1: (85, 140)}
    for col in (3, 4, 5, 1):
        if not pts_by_col.get(col):
            continue
        l1, l2, tc = LABEL[col]
        lx, ly = anchors[col]
        c.setFillColor(tc)
        c.setFont(FONT, 13)
        c.drawCentredString(lx, ly + 8, l1)
        if l2:
            c.drawCentredString(lx, ly - 9, l2)
        sx = lx + c.stringWidth(l1 if len(l1) > len(l2) else l2, FONT, 13) / 2 + 4
        sy = ly - 1
        tx, ty = min(pts_by_col[col], key=lambda q: (q[0] - sx) ** 2 + (q[1] - sy) ** 2 * 0.6)
        c.setStrokeColor(tc)
        c.setLineWidth(0.8)
        arrow_head(c, sx, sy, tx - 1, ty, 6)
    # name box
    a, b, v = name_box(stem)
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.black)
    c.setLineWidth(0.8)
    bw = max(110, max(c.stringWidth(t, FONT, 9.5) for t in (a, b, v)) + 16)
    c.rect(28, 48, bw, 72, fill=0, stroke=1)
    c.setFont(FONT, 9.5)
    for k, t in enumerate((a, b, '', v)):
        c.drawCentredString(28 + bw / 2, 104 - k * 15, t)


def make(dxf):
    d = sheetlib.Drawing(dxf)
    stem = os.path.splitext(os.path.basename(dxf))[0]
    out = os.path.splitext(dxf)[0] + '.pdf'
    c = canvas.Canvas(out, pagesize=(PW, PH))
    c.setTitle(stem)
    c.setAuthor('Mohr lab, ETH Zurich')
    for fr in sheetlib.frames(d):
        page(c, d, fr, stem)
        c.showPage()
    c.save()
    print('written %s' % out)
    return out


if __name__ == '__main__':
    for f in sys.argv[1:]:
        make(f)
