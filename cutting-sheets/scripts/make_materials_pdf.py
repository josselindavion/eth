# -*- coding: utf-8 -*-
"""
make_materials_pdf.py -- Inventory of the materials and of their sheets as a sober PDF: one line per material (name,
ID, number of sheets, notes), its sheets below as indented bullets (sheet ID, size, thickness). Data copied from the
user's handwritten table (photo of 11/11/2026), values confirmed by the user; names and campaigns of 12/11/2026
(data in materials_data.py). CAMPAIGN: A, B or C per material (see make_campaigns_pdf.py); per sheet, the 600 x 500
cutting sheet of the campaign it carries (make_material_cuts_pdf.py), or spare.

    py cutting-sheets/scripts/make_materials_pdf.py cutting-sheets/materials/materials_and_sheets.pdf

"""
import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUT = sys.argv[1]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
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
G_HEAD = colors.Color(0.20, 0.20, 0.20)
G_MAT = colors.Color(0.88, 0.88, 0.88)
G_LINE = colors.Color(0.75, 0.75, 0.75)
G_TEXT = colors.Color(0.40, 0.40, 0.40)
YELLOW = colors.Color(1.0, 0.93, 0.35)

from materials_data import MATERIALS, assign

U = '?'     # marks a value to check: the cell is highlighted, the mark is removed from the text

st_title = ParagraphStyle('t', fontName=BOLD, fontSize=16, leading=20)
st_sub = ParagraphStyle('s', fontName=FONT, fontSize=8.5, leading=11, textColor=G_TEXT)
st_note = ParagraphStyle('n', fontName=FONT, fontSize=8, leading=10.5, textColor=G_TEXT)

HEAD = ['MATERIAL', 'ID', 'SHEETS', 'CAMPAIGN', 'SIZE RD × TD', 'THICKNESS', 'NOTES']
W = [40 * mm, 27 * mm, 13 * mm, 24 * mm, 26 * mm, 16 * mm, 28 * mm]     # 174 mm


def val(v):
    """(text, to check?)"""
    return (v[1:], True) if v.startswith(U) else (v, False)


data = [HEAD]
style = [('FONT', (0, 0), (-1, -1), FONT, 8.8),
         ('FONT', (0, 0), (-1, 0), BOLD, 7.5),
         ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
         ('BACKGROUND', (0, 0), (-1, 0), G_HEAD),
         ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
         ('ALIGN', (2, 0), (5, -1), 'CENTER'),
         ('LINEBELOW', (0, 1), (-1, -1), 0.3, G_LINE),
         ('TOPPADDING', (0, 0), (-1, -1), 2.6), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.6)]
st_mat = ParagraphStyle('m', fontName=BOLD, fontSize=9.5, leading=11)
st_nt = ParagraphStyle('nt', fontName=FONT, fontSize=7.5, leading=9, textColor=G_TEXT)
n_sheets = 0
for m in MATERIALS:
    name, mid, thk, camp, sheets, mnote, drawn = m
    use, missing = assign(m) if drawn else ([], [])
    use = dict(use)
    if missing:
        mnote = (mnote + '; ' if mnote else '') + '%s does not fit' % (
            ', '.join(p[0] for p in missing))
    r = len(data)
    cells = [(Paragraph(name.replace('-', '-\u200b'), st_mat), False), val(mid), (str(len(sheets)), False),
             (camp, False), ('', False), ('', False), (Paragraph(mnote, st_nt), False)]
    data.append([c[0] for c in cells])
    style += [('BACKGROUND', (0, r), (-1, r), G_MAT), ('FONT', (0, r), (2, r), BOLD, 9.5),
              ('FONT', (3, r), (3, r), BOLD, 10),
              ('LINEABOVE', (0, r), (-1, r), 0.8, BLACK), ('TOPPADDING', (0, r), (-1, r), 4),
              ('BOTTOMPADDING', (0, r), (-1, r), 4), ('TEXTCOLOR', (6, r), (6, r), G_TEXT),
              ('FONT', (6, r), (6, r), FONT, 7.5), ('BOX', (3, r), (3, r), 0.5, G_TEXT),
              ('BACKGROUND', (3, r), (3, r), colors.white)]
    style += [('BACKGROUND', (c, r), (c, r), YELLOW) for c, x in enumerate(cells) if x[1]]
    for i, (rd, td, size, note) in enumerate(sheets):
        r = len(data)
        if i in use and len(use[i]) > 1:
            role = 'sheets ' + ', '.join(p[0].split()[1] + ('*' if 'variant' in p[0] else '') for p in use[i])
            if any('variant' in p[0] for p in use[i]):
                note = (note + '; ' if note else '') + '* sheet 3: variant 300 × 1146'
        elif i in use and use[i]:
            role = use[i][0][0]
        elif drawn and rd:
            role = 'spare'
        else:
            role = ''
        cells = [('•  Sheet %d' % (i + 1), False), ('%s-%d' % (val(mid)[0], i + 1), False), ('', False),
                 (role, False), val(size), val(thk), (Paragraph(note, st_nt), False)]
        data.append([c[0] for c in cells])
        style += [('LEFTPADDING', (0, r), (0, r), 14), ('TEXTCOLOR', (1, r), (1, r), G_TEXT),
                  ('TEXTCOLOR', (6, r), (6, r), G_TEXT), ('FONT', (6, r), (6, r), FONT, 7.5),
                  ('FONT', (3, r), (3, r), FONT, 7.5)]
        if role == 'spare':
            style += [('TEXTCOLOR', (3, r), (3, r), G_TEXT)]
        style += [('BACKGROUND', (c, r), (c, r), YELLOW) for c, x in enumerate(cells) if x[1]]
        n_sheets += 1

table = Table(data, colWidths=W, repeatRows=1)
table.setStyle(TableStyle(style))
story = [Paragraph('MATERIALS AND SHEETS', st_title),
         Paragraph('%d materials  ·  %d sheets  ·  sizes RD × TD and thickness in mm (rolling direction first)  ·  '
                   'sheet ID = material ID + sheet number  ·  campaign of each sheet: the 600 × 500 cutting sheet '
                   'it carries (see material_cuts.pdf), spare = not used' % (len(MATERIALS), n_sheets), st_sub),
         Spacer(1, 8), table]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 7)
    canvas.setFillColor(G_TEXT)
    canvas.drawString(18 * mm, 10 * mm, 'Mohr lab, ETH Zurich  ·  12/11/2026')
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=14 * mm,
                        bottomMargin=15 * mm, title='Materials and sheets', author='Mohr lab, ETH Zurich')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print('written %s (%d materials, %d sheets)' % (OUT, len(MATERIALS), n_sheets))
