# -*- coding: utf-8 -*-
"""
make_material_templates_pdf.py -- For each material, the templates it uses (modular strategy, user 12/11/2026):
which template goes on which of its sheets, drawn on the real sheets in the EDM quality colours; last page: every
different template, how many times and where it is cut, and the total number of different templates.

    py cutting-sheets/scripts/make_material_templates_pdf.py cutting-sheets/materials/material_templates.pdf

A template = one sheet of a module (one DXF sheet, the same every time it is cut). Best sheets first (most room around
the template, then the largest); the fullest templates on the best sheets; RD of the template = RD of the sheet;
template in the bottom-left corner (clamp corner of the L). Data: materials_data.py; templates: the DXF of the module
orders (runs/ or output/).
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
from make_module_orders import LARGE, MODULES                # noqa: E402
from materials_data import (MATERIALS, assign, base_tid, code_check, dxf_name, module_of, pieces, plan_dir,  # noqa: E402
                            plans_of, pretty)

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
G_ROW = colors.Color(0.85, 0.85, 0.85)
Q_COL = {3: colors.Color(0.17, 0.63, 0.17), 4: colors.Color(0.0, 0.62, 0.72), 5: colors.Color(0.16, 0.24, 0.80)}
PW, PH = A4
DATE = '13/11/2026'
TITLES = {k: v[0] for k, v in list(MODULES.items()) + list(LARGE.items())}
_PLANS = {}


def plan(order, idx):
    """(polylines [(colour, pts)], bounds of the pieces, clamps [(x, y, w, h)]) of sheet idx of an order, in the
    coordinates of its frame (x = TD, y = RD)."""
    if (order, idx) not in _PLANS:
        d = sheetlib.Drawing(os.path.join(plan_dir(order), order + '.dxf'))
        fx, fy, fx1, fy1 = sheetlib.frames(d)[idx].bounds
        lines, bx = [], [1e9, 1e9, -1e9, -1e9]
        for s in d.cut:
            xs, ys = [p[0] for p in s.pts], [p[1] for p in s.pts]
            if min(xs) >= fx - 1 and max(xs) <= fx1 + 1 and min(ys) >= fy - 1 and max(ys) <= fy1 + 1:
                lines.append((s.color, [(x - fx, y - fy) for x, y in s.pts]))
                bx = [min(bx[0], min(xs) - fx), min(bx[1], min(ys) - fy), max(bx[2], max(xs) - fx),
                      max(bx[3], max(ys) - fy)]
        cfg = yaml.safe_load(open(os.path.join(ROOT, 'orders', 'modules', order + '.yaml'), encoding='utf-8'))
        cl = []
        band = cfg.get('clamping') or {}
        if band.get('left'):                                 # full L clamping: bands along the edges
            cl.append((0, 0, band['left'], float(cfg['sheet'].split('x')[0])))
        if band.get('bottom'):
            cl.append((0, 0, float(cfg['sheet'].split('x')[1]), band['bottom']))
        for k in cfg.get('clamps', []):
            if k['side'] == 'left':
                cl.append((0, k['at'] - k['width'] / 2.0, k['depth'], k['width']))
            elif k['side'] == 'bottom':
                cl.append((k['at'] - k['width'] / 2.0, 0, k['width'], k['depth']))
            elif k['side'] == 'right':
                W = float(cfg['sheet'].split('x')[1])
                cl.append((W - k['depth'], k['at'] - k['width'] / 2.0, k['depth'], k['width']))
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


def draw_sheet(c, ox, oy, rd, td, put, sc):
    """Real sheet rd x td at (ox, oy) with its templates; returns the margins of the pieces to the real edges."""
    ext = [1e9, 1e9, -1e9, -1e9]
    for tid, order, idx, x0, y0, prd, ptd in put:
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
        c.setLineWidth(0.15)
        for col, pts in lines:                               # cut lines in the EDM quality colours
            c.setStrokeColor(Q_COL.get(col, BLACK))
            p = c.beginPath()
            p.moveTo(ox + (x0 + pts[0][0]) * sc, oy + (y0 + pts[0][1]) * sc)
            for x, y in pts[1:]:
                p.lineTo(ox + (x0 + x) * sc, oy + (y0 + y) * sc)
            c.drawPath(p, stroke=1, fill=0)
        ext = [min(ext[0], x0 + bx[0]), min(ext[1], y0 + bx[1]), max(ext[2], x0 + bx[2]), max(ext[3], y0 + bx[3])]
    c.setStrokeColor(BLACK)
    c.setLineWidth(1.3)
    c.rect(ox, oy, td * sc, rd * sc, fill=0, stroke=1)
    c.setLineWidth(0.6)                                      # rolling direction
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
    c.rect(22 * mm, y, 7 * mm, 3.5 * mm, fill=0, stroke=1)
    c.setLineWidth(0.5)
    c.setStrokeColor(G_LINE)
    c.setDash(3, 2)
    c.rect(52 * mm, y, 7 * mm, 3.5 * mm, fill=0, stroke=1)
    c.setDash()
    c.setLineWidth(0.3)
    c.rect(86 * mm, y, 7 * mm, 3.5 * mm, fill=0, stroke=1)
    hatch(c, 86 * mm, y, 7 * mm, 3.5 * mm)
    c.setFont(FONT, 7.5)
    c.setFillColor(BLACK)
    c.drawString(31 * mm, y + 0.9 * mm, 'real sheet')
    c.drawString(61 * mm, y + 0.9 * mm, 'template')
    c.drawString(95 * mm, y + 0.9 * mm, 'clamp / clamping band')
    x = 133 * mm
    for q, t in ((3, 'Q3'), (4, 'Q4'), (5, 'Q5 (codes)')):
        c.setStrokeColor(Q_COL[q])
        c.setLineWidth(1.2)
        c.line(x, y + 1.7 * mm, x + 6 * mm, y + 1.7 * mm)
        c.setFillColor(BLACK)
        c.drawString(x + 7.5 * mm, y + 0.9 * mm, t)
        x += 18 * mm if q < 5 else 0


def fmt(m):
    return 'left %.0f · bottom %.0f · right %.0f · top %.0f mm' % m


def summary(c, rows):
    header(c, 'MATERIALS  ·  TEMPLATES ON EACH SHEET',
           ['One page per material: the modules it gets, the template (one sheet of a module) on each of its sheets,',
            'and the templates drawn on the real sheets. Best sheets first, fullest templates on the best sheets;',
            'RD of the template = RD of the sheet; template in the bottom-left corner (clamp corner).',
            'CODES: notch codes of all the specimens of the material, checked unique per specimen type',
            '(code = angle digit + index). Last page: the different templates and their total.'])
    cols = [15, 60, 84, 122, 178]
    y = PH - 50 * mm
    c.setFont(BOLD, 7.5)
    c.setFillColor(BLACK)
    for x, t in zip(cols, ('MATERIAL', 'ID', 'MODULES', 'SHEET → TEMPLATE', 'CODES')):
        c.drawString(x * mm, y, t)
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.6)
    c.line(15 * mm, y - 1.8 * mm, PW - 15 * mm, y - 1.8 * mm)
    y -= 6.5 * mm
    for name, mid, mods, used, codes in rows:
        c.setFont(BOLD, 8.5 if len(name) < 16 else 6.8)
        c.setFillColor(BLACK)
        c.drawString(cols[0] * mm, y, name)
        c.setFont(FONT, 8.3)
        c.drawString(cols[1] * mm, y, mid)
        c.setFont(FONT, 7.3)
        mm_ = mods.split(' + ')
        for k in range(0, len(mm_), 2):
            c.drawString(cols[2] * mm, y - (k // 2) * 3.4 * mm, ' + '.join(mm_[k:k + 2]) + (' +' if k + 2 < len(mm_)
                                                                                           else ''))
        uu = used.split(' · ')
        for k in range(0, len(uu), 2):
            c.drawString(cols[3] * mm, y - (k // 2) * 3.4 * mm, ' · '.join(uu[k:k + 2]))
        c.setFont(BOLD, 7.3)
        c.drawString(cols[4] * mm, y, codes)
        c.setFont(FONT, 7.3)
        nl = max((len(mm_) + 1) // 2, (len(uu) + 1) // 2)
        c.setStrokeColor(G_ROW)
        c.setLineWidth(0.3)
        c.line(15 * mm, y - 2.2 * mm - (nl - 1) * 3.4 * mm, PW - 15 * mm, y - 2.2 * mm - (nl - 1) * 3.4 * mm)
        y -= 7 * mm + (nl - 1) * 3.4 * mm


def sheet_table(c, m, use, y):
    name, mid, thk, camp, sheets, note, mods = m
    use = dict(use)
    cols = [22, 49, 69, 90, 159, 169]
    c.setFont(BOLD, 7)
    c.setFillColor(BLACK)
    for x, t in zip(cols, ('SHEET', 'SIZE RD × TD', 'TEMPLATE', 'DXF FILE (folder dxf/)', 'PIECES', 'NOTE')):
        c.drawString(x * mm, y, t)
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.6)
    c.line(22 * mm, y - 1.5 * mm, PW - 15 * mm, y - 1.5 * mm)
    y -= 5 * mm
    for i, (rd, td, size, snote) in enumerate(sheets):
        put = use.get(i, [])
        c.setFont(FONT, 8)
        c.setFillColor(BLACK if put else G_TEXT)
        c.drawString(cols[0] * mm, y, '%s-%d' % (mid, i + 1))
        c.drawString(cols[1] * mm, y, size)
        if put:
            c.setFont(BOLD, 7.8)
            c.drawString(cols[2] * mm, y, ' + '.join(p[0] for p in put))
            c.setFont(FONT, 7.5)
            c.setFont(FONT, 6.2)
            c.drawString(cols[3] * mm, y, ', '.join(dxf_name((p[0], None, None, p[5], p[6])) for p in put))
            c.setFont(FONT, 7.5)
            c.drawString(cols[4] * mm, y, '%d' % sum(len(pieces(p[1], p[2])) for p in put))
        else:
            c.drawString(cols[2] * mm, y, 'spare' if rd else '–')
        c.setFillColor(G_TEXT)
        c.setFont(FONT, 7)
        c.drawString(cols[5] * mm, y, snote)
        c.setStrokeColor(G_ROW)
        c.setLineWidth(0.3)
        c.line(22 * mm, y - 1.6 * mm, PW - 15 * mm, y - 1.6 * mm)
        y -= 4.6 * mm
    return y


def material_page(c, m, use, missing):
    name, mid, thk, camp, sheets, note, mods = m
    used = [(i, put) for i, put in use if put]
    header(c, '%s  ·  %s' % (name, mid),
           ['thickness %s mm  ·  %d sheet(s)  ·  campaign %s' % (thk, len(sheets), camp),
            'modules: %s  ·  %d sheet(s) to cut' % (' + '.join(pretty(e) for e in mods), len(plans_of(m)))])
    y = sheet_table(c, m, use, PH - 38 * mm)
    n, dups, shared = code_check(m)
    c.setFont(BOLD, 8)
    c.setFillColor(BLACK)
    c.drawString(22 * mm, y - 1.5 * mm, ('Notch codes: %d coded specimens, every code unique per specimen type.' % n)
                 if not dups else ('Notch codes: %d NOT unique: %s' % (len(dups), ', '.join(
                     '%s %s ×%d' % d for d in dups[:6]))))
    y -= 5.5 * mm
    legend(c, y - 5 * mm)
    top = y - 13 * mm
    big = any(sheets[i][1] > 700 for i, _ in used)
    sc = mm / (7.0 if big else 8.0)
    cw, ch = 88 * mm, 91 * mm
    for k, (i, put) in enumerate(used):
        rd, td, size, snote = sheets[i]
        x = 24 * mm + (0 if big else (k % 2) * cw)
        ytop = top - (0 if big else (k // 2) * ch)
        c.setFont(BOLD, 8.5)
        c.setFillColor(BLACK)
        c.setFont(BOLD, 8 if big else 7.6)
        c.drawString(x, ytop, '%s-%d · %s → %s' % (mid, i + 1, size, ' + '.join(p[0] for p in put)))
        c.setFont(FONT, 7.2)
        c.setFillColor(G_TEXT)
        c.drawString(x, ytop - 3.6 * mm, ', '.join('%s · %d pieces' % (
            TITLES[module_of(p[0])].split(' (')[0], len(pieces(p[1], p[2]))) for p in put))
        oy = ytop - 6 * mm - rd * sc
        mg = draw_sheet(c, x, oy, rd, td, put, sc)
        c.setFont(FONT, 6.5)
        c.setFillColor(G_TEXT)
        c.drawString(x, oy - 3.3 * mm, 'margins: ' + fmt(mg))
        if big:
            area = sum(p[5] * p[6] for p in put)
            c.setFont(FONT, 8)
            c.setFillColor(BLACK)
            c.drawString(x, oy - 10 * mm, '%s = slow 78 + medium 66 + high 66 in one template of 900 × 1140 (RD × TD), '
                         'bottom-left corner, RD kept.' % put[0][0])
            c.drawString(x, oy - 14.4 * mm, 'Rest of the sheet (outside the template): %.0f %% of its area.'
                         % (100.0 * (1 - area / float(rd * td))))
    if missing:
        c.setFont(BOLD, 8.5)
        c.setFillColor(BLACK)
        c.drawString(22 * mm, 18 * mm, 'Does not fit: %s.' % ', '.join(p[0] for p in missing))
    c.setFont(FONT, 7)
    c.setFillColor(G_TEXT)
    c.drawRightString(PW - 15 * mm, PH - 18 * mm, 'drawings at %s on A4' % ('1:7' if big else '1:8'))


def templates_page(c, uses):
    """Last page: every different template, its size, pieces, and where it is cut; the total."""
    header(c, 'TEMPLATES  ·  TOTAL', ['Every different template (one sheet of a module, one DXF sheet), how many '
                                      'times and on which sheets it is cut.'])
    cols = [15, 42, 64, 80, 94, 120]
    y = PH - 40 * mm
    c.setFont(BOLD, 7.5)
    c.setFillColor(BLACK)
    for x, t in zip(cols, ('TEMPLATE', 'SIZE', 'PIECES', 'CUT', 'MODULE', 'SHEETS (material-sheet)')):
        c.drawString(x * mm, y, t)
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.6)
    c.line(15 * mm, y - 1.8 * mm, PW - 15 * mm, y - 1.8 * mm)
    y -= 6.5 * mm
    total_cuts = 0
    for t, where in uses:
        tid, order, idx, rd, td, mod = t
        c.setFont(BOLD, 10)
        c.setFillColor(BLACK)
        c.drawString(cols[0] * mm, y, tid)
        c.setFont(FONT, 8)
        c.drawString(cols[1] * mm, y, '%d × %d' % (rd, td))
        c.drawString(cols[2] * mm, y, '%d' % len(pieces(order, idx)))
        c.setFont(BOLD, 9)
        c.drawString(cols[3] * mm, y, '× %d' % len(where))
        mod = mod.split('@')[0]
        c.setFont(FONT, 7.3)
        c.drawString(cols[4] * mm, y, mod)
        c.setFillColor(G_TEXT)
        for k in range(0, len(where), 2):
            c.drawString(cols[5] * mm, y - (k // 2) * 3.3 * mm, ', '.join(where[k:k + 2]))
        c.setFont(FONT, 6.5)
        c.setFont(FONT, 6.2)
        c.drawString(cols[1] * mm, y - 3.6 * mm, TITLES[mod].split(' (')[0])
        nl = (len(where) + 1) // 2
        dy = max(5.5, 2.2 + nl * 3.3) * mm
        c.setStrokeColor(G_ROW)
        c.setLineWidth(0.3)
        c.line(15 * mm, y - dy, PW - 15 * mm, y - dy)
        y -= dy + 4.5 * mm
        total_cuts += len(where)
    y -= 6 * mm
    c.setStrokeColor(BLACK)
    c.setLineWidth(1.2)
    c.rect(15 * mm, y - 6 * mm, PW - 30 * mm, 14 * mm, fill=0, stroke=1)
    c.setFillColor(BLACK)
    c.setFont(BOLD, 13)
    c.drawString(20 * mm, y, 'In total: %d different templates' % len(uses))
    c.setFont(FONT, 9)
    c.drawString(20 * mm, y - 4.2 * mm, 'cut %d times in all (%d sheets of material), from %d modules: %s' % (
        total_cuts, total_cuts, len(set(t[0][5].split('@')[0] for t in uses)),
        ', '.join(sorted(set(t[0][5].split('@')[0] for t in uses)))))


OUT = sys.argv[1]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
cv = canvas.Canvas(OUT, pagesize=A4)
cv.setTitle('Materials: templates on each sheet')
cv.setAuthor('Mohr lab, ETH Zurich')
rows, pages, where = [], [], {}
order_t = []
for m in MATERIALS:
    name, mid, thk, camp, sheets, note, mods = m
    use, missing = assign(m)
    n, dups, shared = code_check(m)
    rows.append((name, mid, ' + '.join(pretty(e) for e in mods), ' · '.join('-%d → %s' % (i + 1, ' + '.join(p[0] for p in put))
                                                        for i, put in use if put),
                 'unique (%d)' % n if not dups else '%d DUPLICATE' % len(dups)))
    pages.append((m, use, missing))
    for t in plans_of(m):
        if t[0] not in [q[0] for q in order_t]:
            order_t.append(t)
    for i, put in use:
        for p in put:
            where.setdefault(base_tid(p[0]), []).append('%s-%d' % (mid, i + 1) + (
                ' (%s)' % p[0].split(' · ')[1] if ' · ' in p[0] else ''))
summary(cv, rows)
footer(cv, 1)
cv.showPage()
for k, (m, use, missing) in enumerate(pages, 2):
    material_page(cv, m, use, missing)
    footer(cv, k)
    cv.showPage()
templates_page(cv, [(t, where.get(t[0], [])) for t in order_t])
footer(cv, len(pages) + 2)
cv.showPage()
cv.save()
print('written %s (%d pages); %d different templates' % (OUT, len(pages) + 2, len(order_t)))
