# -*- coding: utf-8 -*-
"""
make_cutting_list_pdf.py -- Cutting list for the waterjet workshop (user, 16/11/2026): the materials in the cutting
order, their thickness, and for each sheet to cut the cutting plan (DXF name) and the size of the plan. Simple and
sober: no campaign, no notes, no modules, only the sheets that are cut.

    py cutting-sheets/scripts/make_cutting_list_pdf.py cutting-sheets/delivery/templates_2026-11-13/cutting_list.pdf

Data: materials_data.py (MATERIALS in the cutting order, dxf_name() = lab naming convention).
"""
import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from materials_data import MATERIALS, assign, dxf_name, plans_of   # noqa: E402

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
G_LINE = colors.Color(0.80, 0.80, 0.80)
G_MAT = colors.Color(0.93, 0.93, 0.93)
G_HEAD = colors.Color(0.20, 0.20, 0.20)
DATE = '16/11/2026'

OUT = sys.argv[1]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
st_mat = ParagraphStyle('m', fontName=BOLD, fontSize=9.5, leading=11)
st_long = ParagraphStyle('ml', fontName=BOLD, fontSize=8.3, leading=10)
data = [['#', 'MATERIAL  /  CUTTING PLAN (DXF)', 'ID', 'THICKNESS', 'SHEETS', 'PLAN SIZE']]
style = [('FONT', (0, 0), (-1, 0), BOLD, 7.5), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
         ('BACKGROUND', (0, 0), (-1, 0), G_HEAD), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
         ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
         ('ALIGN', (0, 0), (0, -1), 'CENTER'), ('ALIGN', (3, 0), (4, -1), 'CENTER')]
n_sheets = 0
for k, m in enumerate(MATERIALS, 1):
    name, mid, thk, camp, sheets, note, mods = m
    use, missing = assign(m)
    assert not missing, (name, missing)
    plans = plans_of(m)                                      # every template is placed (checked above)
    r = len(data)
    data.append([str(k), Paragraph(name.replace('-', '-\u200b'), st_mat if len(name) < 20 else st_long), mid, '%s mm' % thk,
                 str(len(plans)), ''])
    style += [('BACKGROUND', (0, r), (-1, r), G_MAT), ('FONT', (0, r), (-1, r), BOLD, 9.5),
              ('FONT', (2, r), (2, r), FONT, 9), ('LINEABOVE', (0, r), (-1, r), 0.8, BLACK)]
    for t in plans:
        r = len(data)
        data.append(['', '\u2192  ' + os.path.splitext(dxf_name(t))[0], '', '', '', '%d × %d mm' % (t[3], t[4])])
        style += [('SPAN', (1, r), (4, r)), ('FONT', (0, r), (-1, r), FONT, 8.5),
                  ('LEFTPADDING', (1, r), (1, r), 12), ('LINEBELOW', (1, r), (-1, r), 0.3, G_LINE)]
        n_sheets += 1
table = Table(data, colWidths=[8 * mm, 66 * mm, 28 * mm, 22 * mm, 18 * mm, 32 * mm], repeatRows=1)
table.setStyle(TableStyle(style))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 7)
    canvas.setFillColor(G_TEXT)
    canvas.drawString(18 * mm, 10 * mm, 'Mohr lab, ETH Zurich  ·  %s' % DATE)
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, 'page %d' % doc.page)
    canvas.restoreState()


st_title = ParagraphStyle('t', fontName=BOLD, fontSize=16, leading=20)
st_sub = ParagraphStyle('s', fontName=FONT, fontSize=8.5, leading=11, textColor=G_TEXT)
doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                        bottomMargin=16 * mm, title='Cutting list', author='Mohr lab, ETH Zurich')
story = [Paragraph('CUTTING LIST  ·  WATERJET', st_title), Spacer(1, 3),
         Paragraph('%d materials, %d sheets, in the cutting order  ·  one row per sheet to cut: its cutting plan (DXF and '
                   'PDF of the same name in dxf/) and the size of the plan, RD × TD (rolling direction first)'
                   % (len(MATERIALS), n_sheets), st_sub), Spacer(1, 8), table]
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print('written %s (%d materials, %d sheets)' % (OUT, len(MATERIALS), n_sheets))
