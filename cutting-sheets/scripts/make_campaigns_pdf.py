# -*- coding: utf-8 -*-
"""
make_campaigns_pdf.py -- Test campaigns of one DP steel sheet as a sober PDF: for each campaign (slow, medium, high
rate) the number of specimens per geometry and per orientation, for campaigns A (full), B (space a little short) and
C (space really short), one page each. Black and greys only. User requests and answers of the supervisors of
11/11/2026.

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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
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
st_h = ParagraphStyle('h', fontName=BOLD, fontSize=11.5, leading=14, spaceBefore=8, spaceAfter=1)

ALL7 = (0, 15, 30, 45, 60, 75, 90)
A3 = (0, 45, 90)
TEN = 'TENSION-TYPE  ·  waterjet'
SHE = 'SHEAR  ·  waterjet + wire EDM'


def row(geom, angles, n):
    """(geometry, {angle: number of specimens})."""
    return (geom, {a: n for a in angles})


SH = ('SHLD', 'SHMD', 'SHHD')


def rates(shear_45_90=SH, elevated=A3):
    """Slow, medium and high rate blocks. shear_45_90: shear geometries also cut at 45 and 90 deg (all rates);
    elevated: orientations of the medium and high rate specimens (UT at all 7 orientations unless only 0 deg)."""
    def shear(angles):
        return [row(g, tuple(a for a in angles if a == 0 or g in shear_45_90), 2) for g in SH]
    slow = [(TEN, [row('UT40', ALL7, 3), row('NT20', A3, 3), row('NT06', A3, 3), row('CH4.8', A3, 3),
                   row('MNAK_RECT_FULL', (0,), 3), row('MNAK_RECT_HOLE', A3, 3)]),
            (SHE, shear(A3))]
    ut = ALL7 if elevated != (0,) else (0,)

    def fast(uname):
        return [(TEN, [row(uname, ut, 3), row('NT20', elevated, 3), row('NT06', elevated, 3),
                       row('CH4.8', elevated, 3)]),
                (SHE, shear(elevated))]
    return [('SLOW RATE', slow), ('MEDIUM RATE', fast('UT40')), ('HIGH RATE', fast('UT19'))]


# campaigns A, B, C (user, 11/11/2026); CH4.8 = catalogue CHD48 (4.8 mm hole re-drilled to 5 mm), MNAK_RECT_FULL =
# punch (0 deg only), MNAK_RECT_HOLE = mini-Nakazima, shear 3 geometries (Roth & Mohr 2018) x 2 repeats
CAMPAIGNS = [
    ('CAMPAIGN A  ·  FULL', 'All specimens. Medium and high rate: NT20, NT06, CH4.8 and shear also at 45° and 90°.',
     rates()),
    ('CAMPAIGN B  ·  SPACE A LITTLE SHORT', 'Campaign A without SHLD and SHHD at 45° and 90°.',
     rates(shear_45_90=('SHMD',))),
    ('CAMPAIGN C  ·  SPACE REALLY SHORT', 'Slow rate as campaign B. Medium and high rate: 0° only.',
     [rates(shear_45_90=('SHMD',))[0]] + rates(shear_45_90=('SHMD',), elevated=(0,))[1:]),
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
             ('TOPPADDING', (0, 0), (-1, -1), 2.4), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.4)]
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
    data.append(['TOTAL'] + [str(v) if v else '' for v in col_tot] + [str(total)])
    style += [('FONT', (0, r), (-1, r), BOLD, 9.5), ('BACKGROUND', (0, r), (-1, r), G_TOT),
              ('LINEABOVE', (0, r), (-1, r), 1.0, BLACK)]
    t = Table(data, colWidths=[wg] + [wa] * len(cols) + [wt], hAlign='LEFT')
    t.setStyle(TableStyle(style))
    return t, total


def laser_table(width):
    """LASER strips (speckle contrast, no code) in every campaign, without a number: they fill the free space."""
    wg, wt = 40 * mm, 18 * mm
    wa = (width - wg - wt) / len(ALL7)
    data = [['OTHER  ·  waterjet, no code, number set by the free space'] + [''] * (len(ALL7) + 1),
            ['LASER'] + [''] * len(ALL7) + ['–']]
    t = Table(data, colWidths=[wg] + [wa] * len(ALL7) + [wt], hAlign='LEFT')
    t.setStyle(TableStyle([('SPAN', (0, 0), (-1, 0)), ('BACKGROUND', (0, 0), (-1, 0), G_SEC),
                           ('FONT', (0, 0), (-1, 0), BOLD, 7.5), ('FONT', (0, 1), (-1, 1), FONT, 9),
                           ('FONT', (-1, 1), (-1, 1), BOLD, 9), ('ALIGN', (1, 1), (-1, 1), 'CENTER'),
                           ('LINEBELOW', (0, 1), (-1, 1), 0.3, G_LINE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('TOPPADDING', (0, 0), (-1, -1), 2.4), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.4)]))
    return t


PAGE_W = A4[0] - 36 * mm
st_big = ParagraphStyle('a', fontName=BOLD, fontSize=10.5, leading=13)
story, summary = [], []
for k, (ctitle, csub, blocks) in enumerate(CAMPAIGNS):
    if k:
        story.append(PageBreak())
    story += [Paragraph(ctitle, st_title), Paragraph(csub + '  Specimens per geometry and orientation to the '
                                                     'rolling direction, one material.', st_sub)]
    tots = []
    for title, bl in blocks:
        t, tot = matrix(ALL7, bl, PAGE_W)
        tots.append(tot)
        story.append(KeepTogether([Paragraph('%s  ·  %d specimens' % (title, tot), st_h), Spacer(1, 3), t]))
    story += [Spacer(1, 8), KeepTogether([laser_table(PAGE_W), Spacer(1, 8), Paragraph(
        'TOTAL: %s = %d SPECIMENS (+ LASER)' % (' + '.join(str(x) for x in tots), sum(tots)), st_big)])]
    summary.append('%s %d' % (ctitle.split()[1], sum(tots)))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 7)
    canvas.setFillColor(G_TEXT)
    canvas.drawString(18 * mm, 10 * mm, 'Mohr lab, ETH Zurich  ·  11/11/2026')
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=13 * mm,
                        bottomMargin=14 * mm, title='Test campaigns, DP steel sheet', author='Mohr lab, ETH Zurich')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print('written %s (%s)' % (OUT, ', '.join(summary)))
