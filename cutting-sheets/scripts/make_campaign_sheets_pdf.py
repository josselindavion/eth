# -*- coding: utf-8 -*-
"""
make_campaign_sheets_pdf.py -- PDF of the sheets of campaigns A and B (user, 11/11/2026): page 1 = diagram of which
sheet is used by which campaign; then one page per plan preview (common sheets, B sheet 3, A sheet 3, A sheet 4).
Sober: black and greys. Previews taken from runs/<order>/preview.png (run the 4 orders first).

    py cutting-sheets/scripts/make_campaign_sheets_pdf.py cutting-sheets/campaigns/campaigns_A_B_sheets.pdf
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
RUNS = os.path.join(HERE, '..', 'runs')
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
BLACK, WHITE = colors.black, colors.white
G_COMMON = colors.Color(0.82, 0.82, 0.82)
G_OWN = colors.Color(0.95, 0.95, 0.95)
G_DARK = colors.Color(0.20, 0.20, 0.20)
G_TEXT = colors.Color(0.40, 0.40, 0.40)

# sheets: key, title, order, content lines
SHEETS = {
    'C1': ('COMMON SHEET 1', 'COMMON_AB_600x500mm_WATERJET (sheet 1)', ['61 tension-type specimens']),
    'C2': ('COMMON SHEET 2', 'COMMON_AB_600x500mm_WATERJET (sheet 2)', ['61 tension-type specimens']),
    'A3': ('A · SHEET 3', 'A_SHEET3_600x500mm_WATERJET', ['34 tension-type specimens', '+ 4 LASER']),
    'A4': ('A · SHEET 4', 'A_SHEET4_600x500mm_WATERJET', ['54 SHEAR specimens of A', '(alone on the sheet)']),
    'B3': ('B · SHEET 3', 'B_SHEET3_600x500mm_WATERJET', ['30 SHEAR specimens of B', '+ 34 tension-type specimens',
                                                         '(the same as A · sheet 3)', '+ 4 LASER']),
}
PAGES = [('COMMON_AB_600x500mm_WATERJET', 'COMMON SHEETS 1 AND 2  ·  campaigns A and B',
          '122 tension-type specimens (61 + 61)'),
         ('B_SHEET3_600x500mm_WATERJET', 'B · SHEET 3  ·  campaign B only',
          '30 shear specimens of B + 34 tension-type specimens + 4 LASER (68 pieces)'),
         ('A_SHEET3_600x500mm_WATERJET', 'A · SHEET 3  ·  campaign A only',
          '34 tension-type specimens (the same as on B · sheet 3) + 4 LASER'),
         ('A_SHEET4_600x500mm_WATERJET', 'A · SHEET 4  ·  campaign A only', '54 shear specimens of A, alone')]


def footer(c, page):
    c.setFont(FONT, 7)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, 8 * mm, 'Mohr lab, ETH Zurich  ·  11/11/2026  ·  sheets 600 (RD) × 500 (TD) mm, waterjet')
    c.drawRightString(PW - 15 * mm, 8 * mm, 'page %d' % page)


def box(c, x, y, w, h, key, fill, shear=False):
    title, order, lines = SHEETS[key]
    c.setFillColor(fill)
    c.setStrokeColor(BLACK)
    c.setLineWidth(2.0 if shear else 0.8)
    c.rect(x, y, w, h, fill=1, stroke=1)
    c.setFillColor(BLACK)
    c.setFont(BOLD, 11)
    c.drawCentredString(x + w / 2, y + h - 9 * mm, title)
    c.setFont(FONT, 8.5)
    for i, l in enumerate(lines):
        c.setFont(BOLD if 'SHEAR' in l else FONT, 8.5)
        c.drawCentredString(x + w / 2, y + h - 17 * mm - i * 4.6 * mm, l)
    c.setFont(FONT, 6.5)
    c.setFillColor(G_TEXT)
    c.drawCentredString(x + w / 2, y + 3.5 * mm, 'order ' + order.replace('_600x500mm_WATERJET', ''))


def diagram(c):
    c.setFillColor(BLACK)
    c.setFont(BOLD, 18)
    c.drawString(15 * mm, PH - 20 * mm, 'CAMPAIGNS A AND B  ·  SHEETS')
    c.setFont(FONT, 9)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, PH - 27 * mm, 'Which sheet is used by which campaign. A = 4 sheets, B = 3 sheets; the shear '
                                       'specimens of each campaign are on one sheet only.')
    x0, lab = 15 * mm, 42 * mm
    gx = x0 + lab                                           # start of the boxes
    bw, gap = 50 * mm, 6 * mm
    rh, rgap = 52 * mm, 12 * mm
    ya = PH - 45 * mm - rh                                  # row A
    yb = ya - rgap - rh                                     # row B
    # row labels
    for y, t, n in ((ya, 'CAMPAIGN A', '4 sheets'), (yb, 'CAMPAIGN B', '3 sheets')):
        c.setFillColor(G_DARK)
        c.rect(x0, y, lab - 6 * mm, rh, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(BOLD, 12)
        c.drawCentredString(x0 + (lab - 6 * mm) / 2, y + rh / 2 + 2 * mm, t)
        c.setFont(FONT, 9)
        c.drawCentredString(x0 + (lab - 6 * mm) / 2, y + rh / 2 - 5 * mm, n)
    # common sheets: span both rows
    for i, k in enumerate(('C1', 'C2')):
        box(c, gx + i * (bw + gap), yb, bw, ya + rh - yb, k, G_COMMON)
    c.setFont(BOLD, 8)
    c.setFillColor(BLACK)
    c.drawCentredString(gx + bw + gap / 2, ya + rh + 3 * mm, 'COMMON TO A AND B')
    c.setLineWidth(0.6)
    c.line(gx, ya + rh + 1.5 * mm, gx + 2 * bw + gap, ya + rh + 1.5 * mm)
    # own sheets
    ox = gx + 2 * (bw + gap) + 4 * mm
    box(c, ox, ya, bw, rh, 'A3', G_OWN)
    box(c, ox + bw + gap, ya, bw, rh, 'A4', G_OWN, shear=True)
    box(c, ox, yb, bw, rh, 'B3', G_OWN, shear=True)
    c.setFont(BOLD, 8)
    c.drawCentredString(ox + bw + gap / 2, ya + rh + 3 * mm, 'OWN SHEETS')
    c.line(ox, ya + rh + 1.5 * mm, ox + 2 * bw + gap, ya + rh + 1.5 * mm)
    # link: same tension-type specimens on A3 and B3
    c.setDash(2, 2)
    c.setStrokeColor(G_TEXT)
    c.line(ox + bw / 2, ya, ox + bw / 2, yb + rh)
    c.setDash()
    c.setFont(FONT, 7)
    c.setFillColor(G_TEXT)
    c.drawString(ox + bw / 2 + 2 * mm, (ya + yb + rh) / 2 - 1 * mm, 'same 34 tension-type specimens')
    # legend
    ly = yb - 11 * mm
    for i, (fill, lw, t) in enumerate(((G_COMMON, 0.8, 'sheet common to A and B'),
                                       (G_OWN, 0.8, 'sheet of one campaign'),
                                       (G_OWN, 2.0, 'thick border: the sheet with the shear specimens'))):
        x = x0 + i * 75 * mm
        c.setFillColor(fill)
        c.setLineWidth(lw)
        c.setStrokeColor(BLACK)
        c.rect(x, ly, 8 * mm, 5 * mm, fill=1, stroke=1)
        c.setFillColor(BLACK)
        c.setFont(FONT, 8)
        c.drawString(x + 10 * mm, ly + 1.3 * mm, t)
    c.setFont(FONT, 8)
    c.setFillColor(G_TEXT)
    c.drawString(x0, ly - 9 * mm, 'Codes: the same specimen has the same notch code in A and B. Index of the code = '
                                  'strain rate: slow 1-3, medium 4-6, high 7-9 (shear: 1-2, 4-5, 7-8).')
    c.drawString(x0, ly - 14 * mm, 'To cut campaign A: common sheets 1, 2 + A · sheet 3 + A · sheet 4.     '
                                   'To cut campaign B: common sheets 1, 2 + B · sheet 3.')
    c.drawString(x0, ly - 19 * mm, 'Orders (cutting-sheets/orders/): COMMON_AB, A_SHEET3, A_SHEET4, B_SHEET3, each '
                                   'followed by _600x500mm_WATERJET.yaml.')


def preview_page(c, order, title, sub):
    c.setFillColor(BLACK)
    c.setFont(BOLD, 15)
    c.drawString(15 * mm, PH - 17 * mm, title)
    c.setFont(FONT, 9)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, PH - 23 * mm, '%s  ·  order %s' % (sub, order))
    img = os.path.join(RUNS, order, 'preview.png')
    ir = ImageReader(img)
    iw, ih = ir.getSize()
    maxw, maxh = PW - 30 * mm, PH - 40 * mm
    s = min(maxw / iw, maxh / ih)
    w, h = iw * s, ih * s
    c.drawImage(ir, (PW - w) / 2, 14 * mm + (maxh - h) / 2, w, h)


from reportlab.pdfgen import canvas     # noqa: E402
cv = canvas.Canvas(OUT, pagesize=landscape(A4))
cv.setTitle('Campaigns A and B, sheets')
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
