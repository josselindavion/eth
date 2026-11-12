# -*- coding: utf-8 -*-
"""
make_material_cuts_pdf.py -- For each material, its real sheets with the 600 (RD) x 500 (TD) cutting sheets of its
campaign drawn on them (user, 12/11/2026). The best sheets are used first (the ones that hold a 600 x 500 plan with
the most room, then the largest); the fullest plans go on the best sheets. Plans keep their RD along the RD of the
sheet and are put in the bottom-left corner (the clamp corner of the L). A large sheet holds several plans side by
side (cut it into 600 x 500 blanks first). Data: materials_data.py; plans: the DXF of the campaign orders.

    py cutting-sheets/scripts/make_material_cuts_pdf.py cutting-sheets/materials/material_cuts.pdf

Sober: black and greys, outlines only. Same scale on every page (1:7 on A4).
"""
import os
import sys

import yaml
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sheetlib                                              # noqa: E402
from materials_data import MATERIALS, assign, plans_of, short   # noqa: E402

ROOT = os.path.join(HERE, '..')
FONT, BOLD = 'Helvetica', 'Helvetica-Bold'
found = []
for name, f in (('Sans', 'DejaVuSans.ttf'), ('Sans-Bold', 'DejaVuSans-Bold.ttf')):
    for d in ('/usr/share/fonts/truetype/dejavu', 'C:/Windows/Fonts'):
        if os.path.exists(os.path.join(d, f)):
            pdfmetrics.registerFont(TTFont(name, os.path.join(d, f)))
            found.append(name)
            break
if len(found) == 2:
    FONT, BOLD = 'Sans', 'Sans-Bold'

BLACK = colors.black
G_TEXT = colors.Color(0.40, 0.40, 0.40)
G_LINE = colors.Color(0.55, 0.55, 0.55)
G_CUT = colors.Color(0.15, 0.15, 0.15)
PW, PH = A4
S = mm / 7.0                                                 # scale 1:7 (points per mm of the sheet)
DATE = '12/11/2026'


def order_dxf(order):
    for d in ('output', 'runs'):
        p = os.path.join(ROOT, d, order, order + '.dxf')
        if os.path.exists(p):
            return p
    raise SystemExit('no DXF for order %s: run it first (make_plan.py)' % order)


_PLANS = {}


def plan(order, idx):
    """(polylines [(pts)], bounds of the pieces (x0, y0, x1, y1), clamps [(x, y, w, h)]) of sheet idx of an order, in
    the coordinates of its frame (x = TD, y = RD)."""
    if (order, idx) not in _PLANS:
        d = sheetlib.Drawing(order_dxf(order))
        fx, fy, fx1, fy1 = sheetlib.frames(d)[idx].bounds
        lines, bx = [], [1e9, 1e9, -1e9, -1e9]
        for s in d.cut:
            xs, ys = [p[0] for p in s.pts], [p[1] for p in s.pts]
            if min(xs) >= fx - 1 and max(xs) <= fx1 + 1 and min(ys) >= fy - 1 and max(ys) <= fy1 + 1:
                lines.append([(x - fx, y - fy) for x, y in s.pts])
                bx = [min(bx[0], min(xs) - fx), min(bx[1], min(ys) - fy), max(bx[2], max(xs) - fx),
                      max(bx[3], max(ys) - fy)]
        cfg = yaml.safe_load(open(os.path.join(ROOT, 'orders', order + '.yaml')))
        cl = []
        for k in cfg.get('clamps', []):
            if k['side'] == 'left':
                cl.append((0, k['at'] - k['width'] / 2.0, k['depth'], k['width']))
            elif k['side'] == 'bottom':
                cl.append((k['at'] - k['width'] / 2.0, 0, k['width'], k['depth']))
        _PLANS[(order, idx)] = (lines, bx, cl)
    return _PLANS[(order, idx)]


def hatch(c, x, y, w, h, step=1.2 * mm):
    p = c.beginPath()
    p.rect(x, y, w, h)
    c.saveState()
    c.clipPath(p, stroke=0, fill=0)
    k = -h
    while k < w:
        c.line(x + k, y, x + k + h, y + h)
        k += step
    c.restoreState()


def draw_sheet(c, ox, oy, rd, td, put):
    """Real sheet rd x td (outline) at (ox, oy) with its plans; returns the margins of the pieces to the real edges
    (left, bottom, right, top) or None."""
    ext = [1e9, 1e9, -1e9, -1e9]
    for label, order, idx, x0, y0, prd, ptd in put:
        lines, bx, cl = plan(order, idx)
        c.setStrokeColor(G_LINE)
        c.setLineWidth(0.5)
        c.setDash(3, 2)
        c.rect(ox + x0 * S, oy + y0 * S, ptd * S, prd * S, fill=0, stroke=1)
        c.setDash()
        c.setLineWidth(0.3)
        for x, y, w, h in cl:                                # clamps: outline + hatch
            c.rect(ox + (x0 + x) * S, oy + (y0 + y) * S, w * S, h * S, fill=0, stroke=1)
            hatch(c, ox + (x0 + x) * S, oy + (y0 + y) * S, w * S, h * S)
        c.setStrokeColor(G_CUT)
        c.setLineWidth(0.12)
        for pts in lines:
            p = c.beginPath()
            p.moveTo(ox + (x0 + pts[0][0]) * S, oy + (y0 + pts[0][1]) * S)
            for x, y in pts[1:]:
                p.lineTo(ox + (x0 + x) * S, oy + (y0 + y) * S)
            c.drawPath(p, stroke=1, fill=0)
        ext = [min(ext[0], x0 + bx[0]), min(ext[1], y0 + bx[1]), max(ext[2], x0 + bx[2]), max(ext[3], y0 + bx[3])]
        if len(put) > 1:                                     # several plans: name of each blank outside the sheet
            c.setFillColor(G_TEXT)
            c.setFont(BOLD, 7)
            ty = oy + rd * S + 1.2 * mm if y0 > 0 else oy - 3.2 * mm
            c.drawString(ox + (x0 + 4) * S, ty, '%s · %s (%d × %d)' % (label, short(order), prd, ptd))
    c.setStrokeColor(BLACK)
    c.setLineWidth(1.3)
    c.rect(ox, oy, td * S, rd * S, fill=0, stroke=1)
    # rolling direction
    c.setLineWidth(0.6)
    ax = ox - 4 * mm
    c.line(ax, oy, ax, oy + 22 * mm)
    c.line(ax, oy + 22 * mm, ax - 1.2 * mm, oy + 19.5 * mm)
    c.line(ax, oy + 22 * mm, ax + 1.2 * mm, oy + 19.5 * mm)
    c.saveState()
    c.translate(ax - 1.5 * mm, oy + 1 * mm)
    c.rotate(90)
    c.setFont(FONT, 6.5)
    c.setFillColor(BLACK)
    c.drawString(0, 0, 'RD')
    c.restoreState()
    if not put:
        return None
    return ext[0], ext[1], td - ext[2], rd - ext[3]


def header(c, title, sub):
    c.setFillColor(BLACK)
    c.setFont(BOLD, 15)
    c.drawString(15 * mm, PH - 18 * mm, title)
    c.setFont(FONT, 8.5)
    c.setFillColor(G_TEXT)
    for k, t in enumerate(sub):
        c.drawString(15 * mm, PH - 24.5 * mm - k * 4.2 * mm, t)


def footer(c, page):
    c.setFont(FONT, 7)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, 8 * mm, 'Mohr lab, ETH Zurich  ·  %s  ·  real sheets RD × TD in mm, scale 1:7 on A4' % DATE)
    c.drawRightString(PW - 15 * mm, 8 * mm, 'page %d' % page)


def legend(c, y):
    c.setLineWidth(1.3)
    c.setStrokeColor(BLACK)
    c.rect(15 * mm, y, 7 * mm, 3.5 * mm, fill=0, stroke=1)
    c.setLineWidth(0.5)
    c.setStrokeColor(G_LINE)
    c.setDash(3, 2)
    c.rect(68 * mm, y, 7 * mm, 3.5 * mm, fill=0, stroke=1)
    c.setDash()
    c.setLineWidth(0.3)
    c.rect(132 * mm, y, 7 * mm, 3.5 * mm, fill=0, stroke=1)
    hatch(c, 132 * mm, y, 7 * mm, 3.5 * mm)
    c.setFont(FONT, 7.5)
    c.setFillColor(BLACK)
    c.drawString(24 * mm, y + 0.9 * mm, 'real sheet')
    c.drawString(77 * mm, y + 0.9 * mm, 'cutting plan (blank)')
    c.drawString(141 * mm, y + 0.9 * mm, 'clamp (50 × 40)')


def fmt(m):
    return 'left %.0f · bottom %.0f · right %.0f · top %.0f mm' % m


def summary(c, rows):
    header(c, 'MATERIALS  ·  CUTTING SHEETS ON THE REAL SHEETS',
           ['One page per material: its sheets, with the 600 (RD) × 500 (TD) cutting sheets of its campaign drawn on '
            'them.', 'Best sheets first (most room around a 600 × 500 plan, then the largest); fullest plans on the '
            'best sheets;', 'RD of the plan = RD of the sheet; plan in the bottom-left corner (clamp corner).'])
    cols = [15, 72, 99, 112, 150]
    y = PH - 46 * mm
    c.setFont(BOLD, 7.5)
    c.setFillColor(BLACK)
    for x, t in zip(cols, ('MATERIAL', 'ID', 'CAMP.', 'SHEETS USED', 'STATUS')):
        c.drawString(x * mm, y, t)
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.6)
    c.line(15 * mm, y - 1.8 * mm, PW - 15 * mm, y - 1.8 * mm)
    y -= 6.5 * mm
    for name, mid, camp, used, status in rows:
        c.setFont(BOLD, 8.5)
        c.setFillColor(BLACK)
        c.drawString(cols[0] * mm, y, name)
        c.setFont(FONT, 8.5)
        c.drawString(cols[1] * mm, y, mid)
        c.setFont(BOLD, 9)
        c.drawString(cols[2] * mm, y, camp)
        c.setFont(FONT, 8)
        c.drawString(cols[3] * mm, y, used)
        c.setFillColor(G_TEXT)
        c.drawString(cols[4] * mm, y, status)
        c.setStrokeColor(colors.Color(0.8, 0.8, 0.8))
        c.setLineWidth(0.3)
        c.line(15 * mm, y - 2.2 * mm, PW - 15 * mm, y - 2.2 * mm)
        y -= 7 * mm
    y -= 6 * mm
    c.setFont(FONT, 8)
    c.setFillColor(G_TEXT)
    for t in ('Plans of each campaign (orders in cutting-sheets/orders/, + _600x500mm_WATERJET.yaml):',
              '   A: sheet 1 CAMPAIGN · sheets 2, 3 AB_SHEETS23 · sheet 4 A_SHEET4',
              '   B: sheet 1 CAMPAIGN · sheets 2, 3 AB_SHEETS23        C: sheet 1 CAMPAIGN · sheet 2 C_SHEET2',
              '   B on the large sheets (RD ≥ 900): one plan B_LARGE of 900 × 1146 instead of the 3 sheets (same specimens '
              'and codes)',
              'Margins under each sheet: smallest distance from the cut pieces to the edges of the real sheet '
              '(at least 5 mm).'):
        c.drawString(15 * mm, y, t)
        y -= 4.5 * mm


def material_page(c, m, use, missing):
    name, mid, thk, camp, sheets, note, drawn = m
    used = [(i, put) for i, put in use if put]
    spare = [i for i, put in use if not put]
    header(c, '%s  ·  %s  ·  campaign %s' % (name, mid, camp),
           ['thickness %s mm  ·  %d sheet(s)  ·  campaign %s = %d cutting sheet(s):' % (
               thk, len(sheets), camp, len(plans_of(m))),
            ', '.join('%s = %s (%d × %d)' % (p[0], short(p[1]), p[3], p[4]) for p in plans_of(m)[:2]) +
            (',' if len(plans_of(m)) > 2 else ''),
            ', '.join('%s = %s (%d × %d)' % (p[0], short(p[1]), p[3], p[4]) for p in plans_of(m)[2:])])
    legend(c, PH - 41 * mm)
    big = any(sheets[i][1] > 700 for i, _ in used)
    top = PH - 48 * mm
    if not big:                                              # grid 2 x 2 of 600 x 500 sheets
        cw, ch = 92 * mm, 101 * mm
        for k, (i, put) in enumerate(used):
            rd, td, size, snote = sheets[i]
            col, row = k % 2, k // 2
            x = 22 * mm + col * cw
            ytop = top - row * ch
            c.setFont(BOLD, 8.5)
            c.setFillColor(BLACK)
            c.drawString(x, ytop, 'Sheet %s-%d  ·  %s' % (mid, i + 1, size))
            c.setFont(FONT, 7.5)
            c.setFillColor(G_TEXT)
            c.drawString(x, ytop - 3.8 * mm, '%s · order %s' % (put[0][0], short(put[0][1])) +
                         ('  ·  %s' % snote if snote else ''))
            oy = ytop - 6.5 * mm - rd * S
            mg = draw_sheet(c, x, oy, rd, td, put)
            c.setFont(FONT, 6.8)
            c.setFillColor(G_TEXT)
            c.drawString(x, oy - 3.5 * mm, 'margins: ' + fmt(mg))
        yb = top - 2 * ch + 2 * mm
    else:                                                    # one large sheet per page
        yb = top
        for i, put in used:
            rd, td, size, snote = sheets[i]
            c.setFont(BOLD, 8.5)
            c.setFillColor(BLACK)
            c.drawString(22 * mm, yb, 'Sheet %s-%d  ·  %s' % (mid, i + 1, size) + ('  ·  %s' % snote if snote else ''))
            c.setFont(FONT, 7.5)
            c.setFillColor(G_TEXT)
            c.drawString(22 * mm, yb - 3.8 * mm, ', '.join('%s · order %s' % (p[0], short(p[1])) for p in put))
            oy = yb - 11 * mm - rd * S
            mg = draw_sheet(c, 22 * mm, oy, rd, td, put)
            c.setFont(FONT, 6.8)
            c.setFillColor(G_TEXT)
            c.drawString(22 * mm, oy - 7.5 * mm, 'margins: ' + fmt(mg))
            used_area = sum(p[5] * p[6] for p in put)
            yb = oy - 14 * mm
            c.setFont(FONT, 8)
            c.setFillColor(BLACK)
            lines = ['Plan of %s (RD × TD) in the bottom-left corner (clamp corner), RD kept: it replaces the 3 '
                     'sheets of B.' % ', '.join('%d × %d' % (p[5], p[6]) for p in put),
                     'Rest of the sheet (outside the plan): %.0f %% of its area.' % (100.0 * (1 - used_area /
                                                                                          float(rd * td)))]
            for t in lines:
                c.drawString(22 * mm, yb, t)
                yb -= 4.4 * mm
    if missing:
        c.setFont(BOLD, 8.5)
        c.setFillColor(BLACK)
        c.drawString(22 * mm, yb - 2 * mm, 'Does not fit: campaign %s %s (%s).' % (
            camp, ', '.join(p[0] for p in missing), ', '.join('order %s' % short(p[1]) for p in missing)))
        yb -= 7 * mm
    if spare:                                                # spare sheets, small outlines (1:20)
        s2 = mm / 30.0
        c.setFont(BOLD, 7.5)
        c.setFillColor(BLACK)
        c.drawString(22 * mm, yb - 2 * mm, 'Spare sheets (not used, scale 1:30):')
        x = 22 * mm
        for i in spare:
            rd, td, size, snote = sheets[i]
            c.setStrokeColor(BLACK)
            c.setLineWidth(0.8)
            c.rect(x, yb - 6 * mm - rd * s2, td * s2, rd * s2, fill=0, stroke=1)
            c.setFont(FONT, 6.5)
            c.setFillColor(G_TEXT)
            c.drawString(x, yb - 9.5 * mm - rd * s2, '%s-%d · %s' % (mid, i + 1, size))
            if snote:
                c.drawString(x, yb - 12.5 * mm - rd * s2, snote)
            x += 40 * mm


OUT = sys.argv[1]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
cv = canvas.Canvas(OUT, pagesize=A4)
cv.setTitle('Materials: cutting sheets on the real sheets')
cv.setAuthor('Mohr lab, ETH Zurich')
rows, pages = [], []
for m in MATERIALS:
    name, mid, thk, camp, sheets, note, drawn = m
    if not drawn:
        rows.append((name, mid, camp, '–', note or 'not drawn'))
        continue
    use, missing = assign(m)
    used = ['-%d' % (i + 1) + (' (%s)' % ', '.join(short(p[1]) for p in put) if put[0][5] != 600 else '')
            for i, put in use if put]
    rows.append((name, mid, camp, ', '.join(used),
                 'does not fit: %s' % ', '.join(p[0] for p in missing) if missing else 'complete'))
    pages.append((m, use, missing))
summary(cv, rows)
footer(cv, 1)
cv.showPage()
for k, (m, use, missing) in enumerate(pages, 2):
    material_page(cv, m, use, missing)
    footer(cv, k)
    cv.showPage()
cv.save()
print('written %s (%d pages)' % (OUT, len(pages) + 1))
