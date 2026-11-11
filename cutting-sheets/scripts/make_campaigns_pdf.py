# -*- coding: utf-8 -*-
"""
make_campaigns_pdf.py -- Test campaigns of one DP steel sheet as a sober PDF: for each campaign (slow, medium, high
rate) the number of specimens per geometry and per orientation, then short questions for the supervisors. Black and
greys only; yellow = not sure. User requests of 11/11/2026.

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
YELLOW = colors.Color(1.0, 0.93, 0.35)

st_title = ParagraphStyle('t', fontName=BOLD, fontSize=16, leading=20)
st_sub = ParagraphStyle('s', fontName=FONT, fontSize=8.5, leading=11, textColor=G_TEXT)
st_h = ParagraphStyle('h', fontName=BOLD, fontSize=11.5, leading=14, spaceBefore=12, spaceAfter=1)
st_load = ParagraphStyle('l', fontName=FONT, fontSize=8, leading=10, textColor=G_TEXT, spaceAfter=4)
st_q = ParagraphStyle('q', fontName=FONT, fontSize=8.8, leading=12, leftIndent=9 * mm, firstLineIndent=-9 * mm,
                      spaceAfter=2.5)

ALL7 = (0, 15, 30, 45, 60, 75, 90)
A3 = (0, 45, 90)
TEN = 'TENSION-TYPE  ·  waterjet'
SHE = 'SHEAR  ·  wire EDM, 2 repeats'


def row(geom, angles, n, label=False, cells=False, q=''):
    """(geometry, {angle: number}, geometry not sure, numbers not sure, question)."""
    return (geom, {a: n for a in angles}, label, cells, q)


# campaign: title, loading, orientation columns, blocks
CAMPAIGNS = [
    ('SLOW RATE', 'UT 0.001 /s  ·  others 6.6e-6 m/s', ALL7,
     [(TEN, [row('UT40', ALL7, 3),
             row('NT20', A3, 3),
             row('NT06', A3, 3),
             row('CHD48', A3, 3, True, False, 'Q1 Q6'),
             row('MNAK_RECT_FULL', A3, 3, True, True, 'Q5'),
             row('MNAK_RECT_HOLE', A3, 3, True, True, 'Q5')]),
      (SHE, [row('SHLD', A3, 2, q='Q4'), row('SHMD', A3, 2, q='Q4'), row('SHHD', A3, 2, q='Q4')])]),
    ('MEDIUM RATE', 'UT 1 /s  ·  others 6.6e-3 m/s', (0,),
     [(TEN, [row('UT40', (0,), 3, False, True, 'Q2'),
             row('NT20', (0,), 3, False, True, 'Q2'),
             row('NT06', (0,), 3, False, True, 'Q2'),
             row('CHD48', (0,), 3, True, True, 'Q1 Q2')]),
      (SHE, [row('SHLD', (0,), 2, True, True, 'Q4'), row('SHMD', (0,), 2, True, True, 'Q4'),
             row('SHHD', (0,), 2, True, True, 'Q4')])]),
    ('HIGH RATE', 'UT 100 /s  ·  others about 1.4 m/s', (0,),
     [(TEN, [row('UT19', (0,), 3, False, True, 'Q2'),
             row('NT20', (0,), 3, False, True, 'Q2'),
             row('NT06', (0,), 3, False, True, 'Q2'),
             row('CHD48', (0,), 3, True, True, 'Q1 Q2')]),
      (SHE, [row('SHLD', (0,), 2, True, True, 'Q4'), row('SHMD', (0,), 2, True, True, 'Q4'),
             row('SHHD', (0,), 2, True, True, 'Q4')])]),
]

QUESTIONS = [
    'Which steel grade? (CH5 up to DP1000, CH8 for DP1180 / DP1470.)',
    'Medium and high rate: 3 repeats per tension-type specimen?',
    'Medium and high rate: 0° only?',
    'Shear: also 135°? The 3 geometries (LD / MD / HD) also at medium and high rate?',
    'MNAK_RECT_FULL = punch and MNAK_RECT_HOLE = mini-Nakazima? 0, 45, 90° × 3 each?',
    'Central hole: is the 4.8 mm hole reamed to 5 mm after cutting? Is CH8 needed?',
    'Do the slow and medium machines take the fir-tree ends of our specimens?',
]


def matrix(cols, blocks, width):
    """Table: geometry | one column per orientation | total | question; returns (table, total)."""
    wg, wt, wq = 34 * mm, 15 * mm, 15 * mm
    wa = (width - wg - wt - wq) / len(cols)
    head = ['GEOMETRY'] + ['%d°' % a for a in cols] + ['TOTAL', 'Q']
    data, style = [head], [
        ('FONT', (0, 0), (-1, -1), FONT, 9),
        ('FONT', (0, 0), (-1, 0), BOLD, 8),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 0), (-1, 0), G_HEAD),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 1), (-1, -1), 0.3, G_LINE),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
    col_tot = [0] * len(cols)
    for bname, rows in blocks:
        r = len(data)
        data.append([bname] + [''] * (len(cols) + 2))
        style += [('SPAN', (0, r), (-1, r)), ('BACKGROUND', (0, r), (-1, r), G_SEC),
                  ('FONT', (0, r), (-1, r), BOLD, 7.5), ('ALIGN', (0, r), (-1, r), 'LEFT')]
        for geom, counts, ulabel, ucells, q in rows:
            r = len(data)
            data.append([geom] + [str(counts.get(a, '')) for a in cols] + [str(sum(counts.values())), q])
            style += [('FONT', (len(cols) + 1, r), (len(cols) + 1, r), BOLD, 9),
                      ('FONT', (-1, r), (-1, r), FONT, 7.5), ('TEXTCOLOR', (-1, r), (-1, r), G_TEXT)]
            if ulabel:
                style.append(('BACKGROUND', (0, r), (0, r), YELLOW))
            for j, a in enumerate(cols):
                if a in counts:
                    col_tot[j] += counts[a]
                    if ucells:
                        style.append(('BACKGROUND', (1 + j, r), (1 + j, r), YELLOW))
    r = len(data)
    total = sum(col_tot)
    data.append(['TOTAL'] + [str(v) for v in col_tot] + [str(total), ''])
    style += [('FONT', (0, r), (-1, r), BOLD, 9.5), ('BACKGROUND', (0, r), (-1, r), G_TOT),
              ('LINEABOVE', (0, r), (-1, r), 1.0, BLACK)]
    t = Table(data, colWidths=[wg] + [wa] * len(cols) + [wt, wq], hAlign='LEFT')
    t.setStyle(TableStyle(style))
    return t, total


PAGE_W = A4[0] - 36 * mm
story = [Paragraph('TEST CAMPAIGNS  ·  DP STEEL SHEET', st_title),
         Paragraph('Specimens per geometry and orientation to the rolling direction, one material. '
                   'Beerli et al. 2026; shear: 3 geometries (Roth &amp; Mohr 2018), 2 repeats.', st_sub)]
legend = Table([['', 'not sure  ·  Q = question below']], colWidths=[7 * mm, 80 * mm], hAlign='LEFT')
legend.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, 0), YELLOW), ('FONT', (0, 0), (-1, -1), FONT, 8),
                            ('TEXTCOLOR', (1, 0), (1, 0), G_TEXT), ('LEFTPADDING', (1, 0), (1, 0), 5),
                            ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
story += [Spacer(1, 5), legend]

totals = []
title, loading, cols, blocks = CAMPAIGNS[0]
t, tot = matrix(cols, blocks, PAGE_W)
totals.append(tot)
story.append(KeepTogether([Paragraph('%s  ·  %d specimens' % (title, tot), st_h), Paragraph(loading, st_load), t]))
half = (PAGE_W - 8 * mm) / 2                      # medium and high side by side
pair = []
for title, loading, cols, blocks in CAMPAIGNS[1:]:
    t, tot = matrix(cols, blocks, half)
    totals.append(tot)
    pair.append([Paragraph('%s  ·  %d specimens' % (title, tot), st_h), Paragraph(loading, st_load), t])
side = Table([pair], colWidths=[half + 8 * mm, half], hAlign='LEFT')
side.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                          ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
story += [side, Spacer(1, 8),
          Paragraph('ALL RATES: %s = %d SPECIMENS' % (' + '.join(str(x) for x in totals), sum(totals)),
                    ParagraphStyle('a', fontName=BOLD, fontSize=10.5, leading=13)),
          Spacer(1, 6), Paragraph('QUESTIONS', st_h)]
for i, q in enumerate(QUESTIONS, 1):
    story.append(Paragraph('<b>Q%d</b>&nbsp;&nbsp;&nbsp;%s' % (i, q), st_q))


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
