# -*- coding: utf-8 -*-
"""
make_campaign_sheets_pdf.py -- PDF of the sheets of campaigns A, B and C (nested, user 12/11/2026): page 1 = diagram
of which sheet is used by which campaign; then one page per plan preview (sheet 1, sheets 2-3, A sheet 4, C sheet 2).
Sober: black and greys, no flat colours. Previews: output/CAMPAIGN_600x500mm_WATERJET and runs/<order>/preview.png.

    py cutting-sheets/scripts/make_campaign_sheets_pdf.py cutting-sheets/campaigns/campaigns_A_B_C_sheets.pdf
"""
import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

OUT = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
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

PW, PH = landscape(A4)
BLACK = colors.black
G_TEXT = colors.Color(0.40, 0.40, 0.40)

PAGES = [('output/CAMPAIGN_600x500mm_WATERJET', 'SHEET 1  ·  campaigns A, B and C',
          '60 slow-rate tension-type specimens + 1 LASER'),
         ('runs/AB_SHEETS23_600x500mm_WATERJET', 'SHEETS 2 AND 3  ·  campaigns A and B',
          'the rest of campaign B: 126 specimens (tension-type and shear) + 3 LASER (61 + 68 pieces)'),
         ('runs/A_SHEET4_600x500mm_WATERJET', 'SHEET 4  ·  campaign A only',
          '24 shear specimens: SHLD and SHHD at 45 and 90 deg, all rates'),
         ('runs/C_SHEET2_600x500mm_WATERJET', 'SHEET 2 OF C  ·  campaign C only',
          'the rest of campaign C: 46 specimens (shear and 0 deg medium / high rate) + 3 LASER')]


def footer(c, page):
    c.setFont(FONT, 7)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, 8 * mm, 'Mohr lab, ETH Zurich  ·  12/11/2026  ·  sheets 600 (RD) × 500 (TD) mm, waterjet')
    c.drawRightString(PW - 15 * mm, 8 * mm, 'page %d' % page)


def sheet(c, x, y, w, h, lines, own, order):
    """One sheet drawn as an outline (no fill): thick border = sheet of this campaign only, thin = common sheet."""
    c.setStrokeColor(BLACK)
    c.setLineWidth(1.8 if own else 0.7)
    if not own:
        c.setDash(3, 2)
    c.rect(x, y, w, h, fill=0, stroke=1)
    c.setDash()
    c.setFillColor(BLACK)
    for i, (txt, bold, size) in enumerate(lines):
        c.setFont(BOLD if bold else FONT, size)
        c.drawCentredString(x + w / 2, y + h - 7.5 * mm - i * 4.4 * mm, txt)
    c.setFont(FONT, 6.5)
    c.setFillColor(G_TEXT)
    c.drawCentredString(x + w / 2, y + 3.5 * mm, order)


S1 = [('SHEET 1', True, 11), ('COMMON A · B · C', True, 8), ('60 slow tension', False, 8.5), ('1 LASER', False, 8.5)]
S2 = [('SHEET 2', True, 11), ('COMMON A · B', True, 8), ('rest of B', False, 8.5), ('(tension + shear)', False, 8.5)]
S3 = [('SHEET 3', True, 11), ('COMMON A · B', True, 8), ('rest of B', False, 8.5), ('3 LASER on 2 + 3', False, 8.5)]
ROWS = [('CAMPAIGN A', '4 sheets', [(S1, False, 'CAMPAIGN'), (S2, False, 'AB_SHEETS23'), (S3, False, 'AB_SHEETS23'),
                                    ([('SHEET 4', True, 11), ('A only', True, 8), ('24 shear', False, 8.5),
                                      ('SHLD, SHHD 45/90', False, 8.5)], True, 'A_SHEET4')]),
        ('CAMPAIGN B', '3 sheets', [(S1, False, 'CAMPAIGN'), (S2, False, 'AB_SHEETS23'), (S3, False, 'AB_SHEETS23')]),
        ('CAMPAIGN C', '2 sheets', [(S1, False, 'CAMPAIGN'),
                                    ([('SHEET 2', True, 11), ('C only', True, 8), ('rest of C', False, 8.5),
                                      ('3 LASER', False, 8.5)], True, 'C_SHEET2')])]


def diagram(c):
    c.setFillColor(BLACK)
    c.setFont(BOLD, 18)
    c.drawString(15 * mm, PH - 20 * mm, 'CAMPAIGNS A, B AND C  ·  SHEETS')
    c.setFont(FONT, 9)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, PH - 27 * mm, 'One row per campaign, its sheets in order. The campaigns are nested (C inside B '
                                       'inside A, same codes), so their first sheets are the same.')
    x0, lab = 15 * mm, 45 * mm
    sh = 36 * mm                                            # sheet height; width from 600 (RD) x 500 (TD)
    sw = sh * 500.0 / 600.0
    gap = 9 * mm
    ys = [PH - 36 * mm - sh - k * (sh + 8 * mm) for k in range(3)]
    for (name, n, sheets), y in zip(ROWS, ys):
        c.setFillColor(BLACK)
        c.setFont(BOLD, 13)
        c.drawString(x0, y + sh / 2 + 2 * mm, name)
        c.setFont(FONT, 9)
        c.setFillColor(G_TEXT)
        c.drawString(x0, y + sh / 2 - 5 * mm, n)
        for i, (lines, own, order) in enumerate(sheets):
            x = x0 + lab + i * (sw + gap)
            sheet(c, x, y, sw, sh, lines, own, order)
            if i:                                           # arrow from the previous sheet
                c.setStrokeColor(G_TEXT)
                c.setLineWidth(0.6)
                ax = x - gap
                c.line(ax + 1.5 * mm, y + sh / 2, x - 1.5 * mm, y + sh / 2)
                c.line(x - 1.5 * mm, y + sh / 2, x - 3.5 * mm, y + sh / 2 + 1.5 * mm)
                c.line(x - 1.5 * mm, y + sh / 2, x - 3.5 * mm, y + sh / 2 - 1.5 * mm)
    # legend (outlines only)
    ly = ys[2] - 10 * mm
    for i, (own, t) in enumerate(((False, 'dashed: common sheet, identical in the campaigns named on it'),
                                  (True, 'thick: sheet of one campaign only'))):
        x = x0 + i * 125 * mm
        c.setStrokeColor(BLACK)
        c.setLineWidth(1.8 if own else 0.7)
        if not own:
            c.setDash(3, 2)
        c.rect(x, ly, 8 * mm, 5 * mm, fill=0, stroke=1)
        c.setDash()
        c.setFillColor(BLACK)
        c.setFont(FONT, 8.5)
        c.drawString(x + 11 * mm, ly + 1.4 * mm, t)
    c.setFont(FONT, 8)
    c.setFillColor(G_TEXT)
    for k, t in enumerate(('Notch code: same specimen = same code in A, B and C; index = strain rate: slow 1-3, medium 4-6, '
                           'high 7-9 (shear: 1-2, 4-5, 7-8).',
                           'Orders in cutting-sheets/orders/: name shown under each sheet + _600x500mm_WATERJET.yaml.',
                           'Shear specimens may be mixed with the others (user, 12/11/2026).')):
        c.drawString(x0, ly - 8 * mm - k * 5 * mm, t)


def preview_page(c, order, title, sub):
    c.setFillColor(BLACK)
    c.setFont(BOLD, 15)
    c.drawString(15 * mm, PH - 17 * mm, title)
    c.setFont(FONT, 9)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, PH - 23 * mm, '%s  ·  order %s' % (sub, os.path.basename(order)))
    img = os.path.join(HERE, '..', order, 'preview.png')
    ir = ImageReader(img)
    iw, ih = ir.getSize()
    maxw, maxh = PW - 30 * mm, PH - 40 * mm
    s = min(maxw / iw, maxh / ih)
    w, h = iw * s, ih * s
    c.drawImage(ir, (PW - w) / 2, 14 * mm + (maxh - h) / 2, w, h)


from reportlab.pdfgen import canvas     # noqa: E402
cv = canvas.Canvas(OUT, pagesize=landscape(A4))
cv.setTitle('Campaigns A, B and C, sheets')
cv.setAuthor('Mohr lab, ETH Zurich')
diagram(cv)
footer(cv, 1)
cv.showPage()
for i, (o, t, s) in enumerate(PAGES, 2):
    preview_page(cv, o, t, s)
    footer(cv, i)
    cv.showPage()
cv.save()
print('written', OUT)
