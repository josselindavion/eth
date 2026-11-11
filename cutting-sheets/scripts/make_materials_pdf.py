# -*- coding: utf-8 -*-
"""
make_materials_pdf.py -- Inventory of the materials and of their sheets as a sober PDF: one line per material (name,
ID, number of sheets, notes), its sheets below as indented bullets (sheet ID, size, thickness). Data copied from the
user's handwritten table (photo of 11/11/2026); yellow = hard to read on the photo, to check.

    py cutting-sheets/scripts/make_materials_pdf.py cutting-sheets/materials/materials_and_sheets.pdf

Sizes are copied as written (which side is the rolling direction is not given). Sheet ID = material ID + "-" +
number of the sheet in the user's list.
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

U = '?'     # marks a value to check: the cell is highlighted, the mark is removed from the text
# material: (name, ID, thickness mm, sheets [(size, note)], material note); a leading '?' = hard to read, to check
MATERIALS = [
    ('DP980', '2020_06_03A', '1.0',
     [('605 × 505', ''), ('598 × 502', ''), ('605 × 501', ''), ('598 × 500', 'edges not straight'),
      ('?595 × 507', 'edges not straight'), ('603 × 502', 'edges not straight'), ('?596 × 500', 'edges not straight')],
     ''),
    ('DC01', '2025_11_25_B', '2.0', [('599 × 500', ''), ('?custom size', '"dim perso" on the list')], ''),
    ('S235JR', '2023_02_28_D', '?3.0', [('600 × 500', '')] * 3, ''),
    ('?S235JR', '2023_02_28_A', '3.0', [('600 × 500', '')] * 4, 'name not written'),
    ('?S235JR', '2023_02_28_C', '3.0', [('600 × 500', '')] * 3, 'name not written'),
    ('RA980', '2022_05_04_D', '?1.4', [('900 × 1200', '')], ''),
    ('RA1200', '2022_05_04_E', '1.4', [('913–915 × 1146', 'width 913 to 915 mm')], ''),
    ('?RA1200', '?2022_04_04_G', '1.4', [('?916 × 1260', 'last digit unclear')], 'name not written'),
]

st_title = ParagraphStyle('t', fontName=BOLD, fontSize=16, leading=20)
st_sub = ParagraphStyle('s', fontName=FONT, fontSize=8.5, leading=11, textColor=G_TEXT)
st_note = ParagraphStyle('n', fontName=FONT, fontSize=8, leading=10.5, textColor=G_TEXT)

HEAD = ['MATERIAL / SHEET', 'ID', 'SHEETS', 'SIZE (mm)', 'THICKN. (mm)', 'NOTES']
W = [30 * mm, 33 * mm, 14 * mm, 29 * mm, 24 * mm, 44 * mm]     # 174 mm


def val(v):
    """(text, to check?)"""
    return (v[1:], True) if v.startswith(U) else (v, False)


data = [HEAD]
style = [('FONT', (0, 0), (-1, -1), FONT, 8.8),
         ('FONT', (0, 0), (-1, 0), BOLD, 7.5),
         ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
         ('BACKGROUND', (0, 0), (-1, 0), G_HEAD),
         ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
         ('ALIGN', (2, 0), (4, -1), 'CENTER'),
         ('LINEBELOW', (0, 1), (-1, -1), 0.3, G_LINE),
         ('TOPPADDING', (0, 0), (-1, -1), 2.6), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.6)]
n_sheets = 0
for name, mid, thk, sheets, mnote in MATERIALS:
    r = len(data)
    cells = [val(name), val(mid), (str(len(sheets)), False), ('', False), ('', False), (mnote, False)]
    data.append([c[0] for c in cells])
    style += [('BACKGROUND', (0, r), (-1, r), G_MAT), ('FONT', (0, r), (2, r), BOLD, 9.5),
              ('LINEABOVE', (0, r), (-1, r), 0.8, BLACK), ('TOPPADDING', (0, r), (-1, r), 4),
              ('BOTTOMPADDING', (0, r), (-1, r), 4), ('TEXTCOLOR', (5, r), (5, r), G_TEXT),
              ('FONT', (5, r), (5, r), FONT, 7.5)]
    style += [('BACKGROUND', (c, r), (c, r), YELLOW) for c, x in enumerate(cells) if x[1]]
    for i, (size, note) in enumerate(sheets, 1):
        r = len(data)
        cells = [('•  Sheet %d' % i, False), ('%s-%d' % (val(mid)[0], i), False), ('', False), val(size), val(thk),
                 (note, False)]
        data.append([c[0] for c in cells])
        style += [('LEFTPADDING', (0, r), (0, r), 14), ('TEXTCOLOR', (1, r), (1, r), G_TEXT),
                  ('TEXTCOLOR', (5, r), (5, r), G_TEXT), ('FONT', (5, r), (5, r), FONT, 7.5)]
        style += [('BACKGROUND', (c, r), (c, r), YELLOW) for c, x in enumerate(cells) if x[1]]
        n_sheets += 1

table = Table(data, colWidths=W, repeatRows=1)
table.setStyle(TableStyle(style))
legend = Table([['', 'hard to read on the photo of the list: to check']], colWidths=[7 * mm, 100 * mm], hAlign='LEFT')
legend.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, 0), YELLOW), ('FONT', (0, 0), (-1, -1), FONT, 8),
                            ('TEXTCOLOR', (1, 0), (1, 0), G_TEXT), ('LEFTPADDING', (1, 0), (1, 0), 5),
                            ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
story = [Paragraph('MATERIALS AND SHEETS', st_title),
         Paragraph('%d materials  ·  %d sheets  ·  sizes as written on the list (rolling direction not given)  ·  '
                   'sheet ID = material ID + sheet number' % (len(MATERIALS), n_sheets), st_sub),
         Spacer(1, 5), legend, Spacer(1, 6), table]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 7)
    canvas.setFillColor(G_TEXT)
    canvas.drawString(18 * mm, 10 * mm, 'Mohr lab, ETH Zurich  ·  11/11/2026')
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=14 * mm,
                        bottomMargin=15 * mm, title='Materials and sheets', author='Mohr lab, ETH Zurich')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print('written %s (%d materials, %d sheets)' % (OUT, len(MATERIALS), n_sheets))
