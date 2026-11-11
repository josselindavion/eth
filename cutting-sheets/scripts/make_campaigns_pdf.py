# -*- coding: utf-8 -*-
"""
make_campaigns_pdf.py -- Test campaigns of one DP steel sheet as a sober PDF: for each campaign (slow, medium, high
rate) the number of specimens per geometry and per orientation. Black and greys only. User requests and answers of the
supervisors of 11/11/2026.

Sources: Beerli et al. (2026), Int. J. Impact Eng. 215, 105761 (programme); Roth & Mohr (2018), Int. J. Mech. Sci.
149 (three shear geometries per material, LD / MD / HD); user, 11/11/2026: shear with 2 repeats.

    py cutting-sheets/scripts/make_campaigns_pdf.py cutting-sheets/campaigns/DP_test_campaigns_Beerli2026.pdf
"""
import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUT = sys.argv[1]
FONT, BOLD = 'Helvetica', 'Helvetica-Bold'          # fallback; DejaVu when available (for × and °)
found = []
for name, f in (('Sans', 'DejaVuSans.ttf'), ('Sans-Bold', 'DejaVuSans-Bold.ttf')):
    for d in ('/usr/share/fonts/truetype/dejavu', 'C:/Windows/Fonts'):
        if os.path.exists(os.path.join(d, f)):
            pdfmetrics.registerFont(TTFont(name, os.path.join(d, f)))
            found.append(name)
            break
if len(found) == 2:
    FONT, BOLD = 'Sans', 'Sans-Bold'
    pdfmetrics.registerFontFamily('Sans', normal='Sans', bold='Sans-Bold', italic='Sans', boldItalic='Sans-Bold')

BLACK = colors.black
G_HEAD = colors.Color(0.20, 0.20, 0.20)     # header: white text on dark grey
G_SEC = colors.Color(0.90, 0.90, 0.90)
G_TOT = colors.Color(0.82, 0.82, 0.82)
G_LINE = colors.Color(0.70, 0.70, 0.70)
G_TEXT = colors.Color(0.40, 0.40, 0.40)

st_title = ParagraphStyle('t', fontName=BOLD, fontSize=16, leading=20)
st_sub = ParagraphStyle('s', fontName=FONT, fontSize=8.5, leading=11, textColor=G_TEXT)
st_h = ParagraphStyle('h', fontName=BOLD, fontSize=11.5, leading=14, spaceBefore=12, spaceAfter=1)

ALL7 = (0, 15, 30, 45, 60, 75, 90)
A3 = (0, 45, 90)
TEN = 'TENSION-TYPE  ·  waterjet'
SHE = 'SHEAR  ·  waterjet + wire EDM'


def row(geom, angles, n):
    """(geometry, {angle: number of specimens})."""
    return (geom, {a: n for a in angles})


SHEAR3 = lambda angles: [row(g, angles, 2) for g in ('SHLD', 'SHMD', 'SHHD')]     # noqa: E731
# answers of the supervisors (user, 11/11/2026): CH4.8 (catalogue CHD48) = 4.8 mm hole re-drilled to 5 mm (CH5 everywhere, no CH8);
# MNAK_RECT_FULL = punch, 0 deg only, 3; MNAK_RECT_HOLE = mini-Nakazima; UT at all orientations at every rate
CAMPAIGNS = [
    ('SLOW RATE', [(TEN, [row('UT40', ALL7, 3), row('NT20', A3, 3), row('NT06', A3, 3), row('CH4.8', A3, 3),
                          row('MNAK_RECT_FULL', (0,), 3), row('MNAK_RECT_HOLE', A3, 3)]),
                   (SHE, SHEAR3(A3))]),
    ('MEDIUM RATE', [(TEN, [row('UT40', ALL7, 3), row('NT20', (0,), 3), row('NT06', (0,), 3), row('CH4.8', (0,), 3)]),
                     (SHE, SHEAR3((0,)))]),
    ('HIGH RATE', [(TEN, [row('UT19', ALL7, 3), row('NT20', (0,), 3), row('NT06', (0,), 3), row('CH4.8', (0,), 3)]),
                   (SHE, SHEAR3((0,)))]),
]


def matrix(cols, blocks, width):
    """Table: geometry | one column per orientation | total; returns (table, total)."""
    wg, wt = 40 * mm, 18 * mm
    wa = (width - wg - wt) / len(cols)
    data = [['GEOMETRY'] + ['%d°' % a for a in cols] + ['TOTAL']]
    style = [('FONT', (0, 0), (-1, -1), FONT, 9),
             ('FONT', (0, 0), (-1, 0), BOLD, 8),
             ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
             ('BACKGROUND', (0, 0), (-1, 0), G_HEAD),
             ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('LINEBELOW', (0, 1), (-1, -1), 0.3, G_LINE),
             ('FONT', (-1, 1), (-1, -1), BOLD, 9),
             ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
    col_tot = [0] * len(cols)
    for bname, rows in blocks:
        r = len(data)
        data.append([bname] + [''] * (len(cols) + 1))
        style += [('SPAN', (0, r), (-1, r)), ('BACKGROUND', (0, r), (-1, r), G_SEC),
                  ('FONT', (0, r), (-1, r), BOLD, 7.5), ('ALIGN', (0, r), (-1, r), 'LEFT')]
        for geom, counts in rows:
            data.append([geom] + [str(counts.get(a, '')) for a in cols] + [str(sum(counts.values()))])
            for j, a in enumerate(cols):
                col_tot[j] += counts.get(a, 0)
    r = len(data)
    total = sum(col_tot)
    data.append(['TOTAL'] + [str(v) for v in col_tot] + [str(total)])
    style += [('FONT', (0, r), (-1, r), BOLD, 9.5), ('BACKGROUND', (0, r), (-1, r), G_TOT),
              ('LINEABOVE', (0, r), (-1, r), 1.0, BLACK)]
    t = Table(data, colWidths=[wg] + [wa] * len(cols) + [wt], hAlign='LEFT')
    t.setStyle(TableStyle(style))
    return t, total


PAGE_W = A4[0] - 36 * mm
story = [Paragraph('TEST CAMPAIGNS  ·  DP STEEL SHEET', st_title),
         Paragraph('Number of specimens per geometry and orientation to the rolling direction, one material.', st_sub)]
totals = []
for title, blocks in CAMPAIGNS:
    t, tot = matrix(ALL7, blocks, PAGE_W)
    totals.append(tot)
    story.append(KeepTogether([Paragraph('%s  ·  %d specimens' % (title, tot), st_h), Spacer(1, 3), t]))
story += [Spacer(1, 12),
          Paragraph('ALL RATES: %s = %d SPECIMENS' % (' + '.join(str(x) for x in totals), sum(totals)),
                    ParagraphStyle('a', fontName=BOLD, fontSize=10.5, leading=13))]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 7)
    canvas.setFillColor(G_TEXT)
    canvas.drawString(18 * mm, 10 * mm, 'Mohr lab, ETH Zurich  ·  11/11/2026')
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm,
                        bottomMargin=15 * mm, title='Test campaigns, DP steel sheet', author='Mohr lab, ETH Zurich')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print('written %s (%s)' % (OUT, ' + '.join(str(x) for x in totals)))
