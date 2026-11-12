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
from materials_data import MATERIALS, assign, pid, plans_of, short   # noqa: E402

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


def plan_pieces(order, idx):
    """Rows of the registry of an order on sheet idx (one row per piece)."""
    import csv
    p = os.path.dirname(order_dxf(order))
    with open(os.path.join(p, 'registry.csv'), encoding='utf-8') as f:
        return [r for r in csv.DictReader(f) if int(r['sheet']) == idx + 1]


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


def draw_sheet(c, ox, oy, rd, td, put, sc=S):
    """Real sheet rd x td (outline) at (ox, oy) with its plans; returns the margins of the pieces to the real edges
    (left, bottom, right, top) or None."""
    ext = [1e9, 1e9, -1e9, -1e9]
    for label, order, idx, x0, y0, prd, ptd in put:
        lines, bx, cl = plan(order, idx)
        c.setStrokeColor(G_LINE)
        c.setLineWidth(0.5)
        c.setDash(3, 2)
        c.rect(ox + x0 * sc, oy + y0 * sc, ptd * sc, prd * sc, fill=0, stroke=1)
        c.setDash()
        c.setLineWidth(0.3)
        for x, y, w, h in cl:                                # clamps: outline + hatch
            c.rect(ox + (x0 + x) * sc, oy + (y0 + y) * sc, w * sc, h * sc, fill=0, stroke=1)
            hatch(c, ox + (x0 + x) * sc, oy + (y0 + y) * sc, w * sc, h * sc)
        c.setStrokeColor(G_CUT)
        c.setLineWidth(0.12)
        for pts in lines:
            p = c.beginPath()
            p.moveTo(ox + (x0 + pts[0][0]) * sc, oy + (y0 + pts[0][1]) * sc)
            for x, y in pts[1:]:
                p.lineTo(ox + (x0 + x) * sc, oy + (y0 + y) * sc)
            c.drawPath(p, stroke=1, fill=0)
        ext = [min(ext[0], x0 + bx[0]), min(ext[1], y0 + bx[1]), max(ext[2], x0 + bx[2]), max(ext[3], y0 + bx[3])]
        if len(put) > 1:                                     # several plans: name of each blank outside the sheet
            c.setFillColor(G_TEXT)
            c.setFont(BOLD, 7)
            ty = oy + rd * sc + 1.2 * mm if y0 > 0 else oy - 3.2 * mm
            c.drawString(ox + (x0 + 4) * sc, ty, '%s · %s · %s' % (pid((label, order, idx)), label, short(order)))
    c.setStrokeColor(BLACK)
    c.setLineWidth(1.3)
    c.rect(ox, oy, td * sc, rd * sc, fill=0, stroke=1)
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
    c.drawString(15 * mm, 8 * mm, 'Mohr lab, ETH Zurich  ·  %s  ·  real sheets RD × TD in mm' % DATE)
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
    header(c, 'MATERIALS  ·  WHICH CUTTING PLAN ON WHICH SHEET',
           ['One page per material: its campaign, the cutting plan (P1 ... P6, see cutting_plans.pdf) on each of its '
            'sheets,', 'and the plans drawn on the real sheets. Best sheets first (most room around the plan, then the '
            'largest), fullest plans', 'on the best sheets; RD of the plan = RD of the sheet; plan in the bottom-left '
            'corner (clamp corner).'])
    cols = [15, 66, 92, 104, 172]
    y = PH - 46 * mm
    c.setFont(BOLD, 7.5)
    c.setFillColor(BLACK)
    for x, t in zip(cols, ('MATERIAL', 'ID', 'CAMP.', 'SHEET → PLAN', 'STATUS')):
        c.drawString(x * mm, y, t)
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.6)
    c.line(15 * mm, y - 1.8 * mm, PW - 15 * mm, y - 1.8 * mm)
    y -= 6.5 * mm
    for name, mid, camp, used, status in rows:
        c.setFont(BOLD, 8.5 if len(name) < 16 else 7.5)
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
    for t in ('Cutting plans (orders in cutting-sheets/orders/<order>.yaml):',
              '   P1 = CAMPAIGN · P2, P3 = AB_SHEETS23 (sheets 1, 2) · P4 = A_SHEET4 · P5 = C_SHEET2 (all 600 × 500)',
              '   P6 = B_LARGE (900 × 1146) = P1 + P2 + P3 in one plan, for the large sheets',
              'Campaigns: A = P1 + P2 + P3 + P4 · B = P1 + P2 + P3 (large sheet: P6) · C = P1 + P5',
              'Margins under each sheet: smallest distance from the cut pieces to the edges of the real sheet '
              '(at least 5 mm).'):
        c.drawString(15 * mm, y, t)
        y -= 4.5 * mm


def sheet_table(c, m, use, y):
    """Table of the sheets of a material (sheet, size, plan, campaign sheet, pieces, note); returns the y below."""
    name, mid, thk, camp, sheets, note, drawn = m
    use = dict(use)
    cols = [22, 58, 86, 100, 138, 158]
    c.setFont(BOLD, 7)
    c.setFillColor(BLACK)
    for x, t in zip(cols, ('SHEET', 'SIZE RD × TD', 'PLAN', 'IN THE CAMPAIGN', 'PIECES', 'NOTE')):
        c.drawString(x * mm, y, t)
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.6)
    c.line(22 * mm, y - 1.5 * mm, PW - 18 * mm, y - 1.5 * mm)
    y -= 5 * mm
    for i, (rd, td, size, snote) in enumerate(sheets):
        put = use.get(i, [])
        c.setFont(FONT, 8)
        c.setFillColor(BLACK if put else G_TEXT)
        c.drawString(cols[0] * mm, y, '%s-%d' % (mid, i + 1))
        c.drawString(cols[1] * mm, y, size)
        if put:
            c.setFont(BOLD, 9)
            c.drawString(cols[2] * mm, y, ' + '.join(pid(p) for p in put))
            c.setFont(FONT, 8)
            c.drawString(cols[3] * mm, y, ', '.join(p[0] if p[0].startswith('all') else '%s %s' % (camp, p[0]) for p in put))
            c.drawString(cols[4] * mm, y, '%d' % sum(PIECES[pid(p)] for p in put))
        else:
            c.drawString(cols[2] * mm, y, 'spare')
        c.setFillColor(G_TEXT)
        c.setFont(FONT, 7)
        c.drawString(cols[5] * mm, y, snote)
        c.setStrokeColor(colors.Color(0.85, 0.85, 0.85))
        c.setLineWidth(0.3)
        c.line(22 * mm, y - 1.6 * mm, PW - 18 * mm, y - 1.6 * mm)
        y -= 4.6 * mm
    return y


def material_page(c, m, use, missing):
    name, mid, thk, camp, sheets, note, drawn = m
    used = [(i, put) for i, put in use if put]
    pl = plans_of(m)
    header(c, '%s  ·  %s  ·  campaign %s' % (name, mid, camp),
           ['thickness %s mm  ·  %d sheet(s)  ·  campaign %s here = %s' % (
               thk, len(sheets), camp, ' + '.join('%s (%s, %s)' % (pid(p), p[0], short(p[1])) for p in pl[:2])) +
            (' +' if len(pl) > 2 else ''),
            ' + '.join('%s (%s, %s)' % (pid(p), p[0], short(p[1])) for p in pl[2:])])
    y = sheet_table(c, m, use, PH - 38 * mm)
    legend(c, y - 5 * mm)
    top = y - 12 * mm
    big = any(sheets[i][1] > 700 for i, _ in used)
    if not big:                                              # grid 2 x 2 of 600 x 500 sheets, scale 1:8
        sc = mm / 8.0
        cw, ch = 88 * mm, 91 * mm
        for k, (i, put) in enumerate(used):
            rd, td, size, snote = sheets[i]
            x = 24 * mm + (k % 2) * cw
            ytop = top - (k // 2) * ch
            c.setFont(BOLD, 8.5)
            c.setFillColor(BLACK)
            c.drawString(x, ytop, '%s-%d  ·  %s  →  %s' % (mid, i + 1, size, pid(put[0])))
            c.setFont(FONT, 7.2)
            c.setFillColor(G_TEXT)
            c.drawString(x, ytop - 3.6 * mm, 'campaign %s %s · order %s' % (camp, put[0][0], short(put[0][1])) +
                         ('  ·  %s' % snote if snote else ''))
            oy = ytop - 6 * mm - rd * sc
            mg = draw_sheet(c, x, oy, rd, td, put, sc)
            c.setFont(FONT, 6.5)
            c.setFillColor(G_TEXT)
            c.drawString(x, oy - 3.3 * mm, 'margins: ' + fmt(mg))
        scale = '1:8'
    else:                                                    # one large sheet, scale 1:7
        yb = top
        for i, put in used:
            rd, td, size, snote = sheets[i]
            c.setFont(BOLD, 8.5)
            c.setFillColor(BLACK)
            c.drawString(22 * mm, yb, '%s-%d  ·  %s  →  %s' % (mid, i + 1, size, ' + '.join(pid(p) for p in put)) +
                         ('  ·  %s' % snote if snote else ''))
            c.setFont(FONT, 7.2)
            c.setFillColor(G_TEXT)
            c.drawString(22 * mm, yb - 3.6 * mm, ', '.join('campaign %s: %s · order %s' % (camp, p[0], short(p[1]))
                                                         for p in put))
            oy = yb - 7 * mm - rd * S
            mg = draw_sheet(c, 22 * mm, oy, rd, td, put)
            c.setFont(FONT, 6.5)
            c.drawString(22 * mm, oy - 3.5 * mm, 'margins: ' + fmt(mg))
            used_area = sum(p[5] * p[6] for p in put)
            yb = oy - 10 * mm
            c.setFont(FONT, 8)
            c.setFillColor(BLACK)
            for t in ['%s = P1 + P2 + P3 in one plan of %s (RD × TD), in the bottom-left corner (clamp corner), RD kept.'
                      % (' + '.join(pid(p) for p in put), ', '.join('%d × %d' % (p[5], p[6]) for p in put)),
                      'Rest of the sheet (outside the plan): %.0f %% of its area.'
                      % (100.0 * (1 - used_area / float(rd * td)))]:
                c.drawString(22 * mm, yb, t)
                yb -= 4.4 * mm
        scale = '1:7'
    if missing:
        c.setFont(BOLD, 8.5)
        c.setFillColor(BLACK)
        c.drawString(22 * mm, 18 * mm, 'Does not fit: %s.' % ', '.join(pid(p) for p in missing))
    c.setFont(FONT, 7)
    c.setFillColor(G_TEXT)
    c.drawRightString(PW - 18 * mm, PH - 18 * mm, 'drawings at %s on A4' % scale)


OUT = sys.argv[1]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
PIECES = {}
for _m in MATERIALS:
    for _p in plans_of(_m):
        if pid(_p) not in PIECES:
            PIECES[pid(_p)] = len(plan_pieces(_p[1], _p[2]))
cv = canvas.Canvas(OUT, pagesize=A4)
cv.setTitle('Materials: which cutting plan on which sheet')
cv.setAuthor('Mohr lab, ETH Zurich')
rows, pages = [], []
for m in MATERIALS:
    name, mid, thk, camp, sheets, note, drawn = m
    if not drawn:
        rows.append((name, mid, camp, 'later: ' + ' + '.join(pid(p) for p in plans_of(m)), note or 'not drawn'))
        continue
    use, missing = assign(m)
    used = ['-%d → %s' % (i + 1, ' + '.join(pid(p) for p in put)) for i, put in use if put]
    rows.append((name, mid, camp, ' · '.join(used),
                 'missing: %s' % ', '.join(pid(p) for p in missing) if missing else 'complete'))
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
