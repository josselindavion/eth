# -*- coding: utf-8 -*-
"""
make_campaigns_pdf.py -- Test campaigns of one DP steel sheet (slow, medium, high rate) and the questions for the
supervisors, as a sober PDF (black, greys, bold, capitals; yellow only for what is not sure). User request of
11/11/2026. Same content as make_campaigns_xlsx.py; source Beerli et al. (2026), Int. J. Impact Eng. 215, 105761.

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
G_HEAD = colors.Color(0.80, 0.80, 0.80)
G_BLOCK = colors.Color(0.92, 0.92, 0.92)
G_TOTAL = colors.Color(0.85, 0.85, 0.85)
G_LINE = colors.Color(0.60, 0.60, 0.60)
G_TEXT = colors.Color(0.35, 0.35, 0.35)
YELLOW = colors.Color(1.0, 0.95, 0.40)

st_title = ParagraphStyle('t', fontName=BOLD, fontSize=15, leading=19, spaceAfter=2)
st_sub = ParagraphStyle('s', fontName=FONT, fontSize=8.5, leading=11, textColor=G_TEXT)
st_h = ParagraphStyle('h', fontName=BOLD, fontSize=11, leading=14, spaceBefore=10, spaceAfter=2)
st_load = ParagraphStyle('l', fontName=FONT, fontSize=8.5, leading=11, textColor=G_TEXT, spaceAfter=4)
st_cell = ParagraphStyle('c', fontName=FONT, fontSize=9, leading=11)
st_q = ParagraphStyle('q', fontName=FONT, fontSize=9.5, leading=13, leftIndent=8 * mm, firstLineIndent=-8 * mm,
                      spaceAfter=5)
st_note = ParagraphStyle('n', fontName=FONT, fontSize=8, leading=10, textColor=G_TEXT)

ALL7 = '0, 15, 30, 45, 60, 75, 90'
A3 = '0, 45, 90'
# row: (specimen, orientations, n orientations, repeats, unsure columns {0 specimen, 1 orientations, 3 repeats}, Qs)
RATES = [
    ('1.  SLOW RATE (QUASI-STATIC)',
     'UT: 0.001 /s  ·  other specimens: 6.6e-6 m/s  ·  100 kN hydraulic testing machine',
     [('UT40', ALL7, 7, 3, (), ''),
      ('NT20', A3, 3, 3, (), ''),
      ('NT06', A3, 3, 3, (), ''),
      ('CHD48 (CH5)', A3, 3, 3, (0,), 'Q1, Q6'),
      ('MNAK_RECT_FULL (punch)', A3, 3, 3, (0, 1, 3), 'Q5'),
      ('MNAK_RECT_HOLE (mini-Nakazima)', A3, 3, 3, (0, 1, 3), 'Q5')],
     [('SHMD', A3, 3, 2, (0, 1), 'Q4')]),
    ('2.  MEDIUM RATE (INTERMEDIATE)',
     'UT: 1 /s  ·  other specimens: 6.6e-3 m/s  ·  Instron 8801 (100 kN)',
     [('UT40', '0', 1, 3, (3,), 'Q2'),
      ('NT20', '0', 1, 3, (3,), 'Q2'),
      ('NT06', '0', 1, 3, (3,), 'Q2'),
      ('CHD48 (CH5)', '0', 1, 3, (0, 3), 'Q1, Q2, Q6')],
     [('SHMD', '0', 1, 2, (0,), 'Q4')]),
    ('3.  HIGH RATE',
     'UT: 100 /s  ·  other specimens: about 1.4 m/s  ·  split Hopkinson tensile bar',
     [('UT19 (small UT)', '0', 1, 3, (3,), 'Q2'),
      ('NT20', '0', 1, 3, (3,), 'Q2'),
      ('NT06', '0', 1, 3, (3,), 'Q2'),
      ('CHD48 (CH5)', '0', 1, 3, (0, 3), 'Q1, Q2, Q6')],
     [('SHMD', '0', 1, 2, (0,), 'Q4')]),
]
# shear: 2 repeats at every rate (user, 11/11/2026)

QUESTIONS = [
    ('Material', 'Which steel grade and which sheet thickness is this campaign for? The grade sets the shear '
                 'geometry (low, medium or high ductility). Grade and thickness together set the maximum force of '
                 'the central-hole specimen, hence CH5 or CH8 (see Q6).'),
    ('Repeats at medium and high rate', '3 per tension-type specimen? The paper does not say; 3 is inferred from its '
                                        '150 tests (5 materials × 2 rates × 5 specimen types × 3).'),
    ('Orientations at medium and high rate', 'Only 0° to the rolling direction, as in the paper?'),
    ('Shear', 'Only SHMD (the paper uses the "medium ductility" geometry), or all three LD / MD / HD? Orientations '
              '0, 45, 90° (paper) or also 135° (2025 plan)? (2 repeats: confirmed.)'),
    ('Punch and mini-Nakazima', 'Is MNAK_RECT_FULL the punch specimen (equi-biaxial) and MNAK_RECT_HOLE the dihedral '
                                'mini-Nakazima (plane strain)? 0, 45, 90° × 3 for both? (The current 600 × 500 order '
                                'has MNAK_RECT_FULL at 0° only.)'),
    ('Central hole', 'Our catalogue central-hole specimen has a 4.8 mm hole. In the paper the hole is reamed to its '
                     'final size after waterjet cutting, for a clean edge. (a) Is the 4.8 mm hole a pre-hole, to be '
                     'reamed to 5 mm (CH5) after cutting? (b) For high-strength grades (DP1180, DP1470) the paper uses '
                     'an 8 mm hole (CH8) to keep the force below the limit of the clamps. Does this material need '
                     'CH8? (Then a new template is needed: it is not in the catalogue.)'),
    ('Clamping ends', 'In the paper the ends of the specimens (the part held by the grips) have a different shape for '
                      'each rate: one for the slow machine, one for the Instron, a fir-tree shape for the Hopkinson '
                      'bar (Fig. 2f-h). All specimens of our catalogue have fir-tree ends. Do the grips of the slow '
                      'and medium machines take these fir-tree specimens, or do the slow and medium specimens need '
                      'other ends (other templates)?'),
]

W_COL = [61 * mm, 40 * mm, 19 * mm, 16 * mm, 16 * mm, 22 * mm]   # 174 mm = A4 - margins
HEAD = ['SPECIMEN', 'ORIENTATIONS TO RD (°)', 'NO. ORIENT.', 'REPEATS', 'NUMBER', 'QUESTION']


def table(tension, shear):
    data = [HEAD]
    style = [('FONT', (0, 0), (-1, -1), FONT, 9),
             ('FONT', (0, 0), (-1, 0), BOLD, 7.5),
             ('BACKGROUND', (0, 0), (-1, 0), G_HEAD),
             ('GRID', (0, 0), (-1, -1), 0.4, G_LINE),
             ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
    total = 0
    for label, rows in (('Tension-type specimens (waterjet)', tension), ('Shear (wire EDM)', shear)):
        r = len(data)
        data.append([label, '', '', '', '', ''])
        style += [('SPAN', (0, r), (-1, r)), ('BACKGROUND', (0, r), (-1, r), G_BLOCK),
                  ('FONT', (0, r), (-1, r), BOLD, 8.5), ('ALIGN', (0, r), (-1, r), 'LEFT')]
        sub = 0
        for spec, ori, n, rep, unsure, q in rows:
            r = len(data)
            data.append([spec, ori, str(n), str(rep), str(n * rep), q])
            for c in unsure:
                style.append(('BACKGROUND', (c, r), (c, r), YELLOW))
            sub += n * rep
        r = len(data)
        data.append(['Subtotal', '', '', '', str(sub), ''])
        style += [('FONT', (0, r), (-1, r), BOLD, 9)]
        total += sub
    r = len(data)
    data.append(['TOTAL', '', '', '', str(total), ''])
    style += [('FONT', (0, r), (-1, r), BOLD, 9.5), ('BACKGROUND', (0, r), (-1, r), G_TOTAL),
              ('LINEABOVE', (0, r), (-1, r), 1.0, BLACK)]
    t = Table(data, colWidths=W_COL, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t, total


story = [Paragraph('TEST CAMPAIGNS: DP STEEL SHEET', st_title),
         Paragraph('One material (one steel sheet), per strain rate. Source: Beerli et al. (2026), Int. J. Impact '
                   'Eng. 215, 105761, sections 2.2, 4.1 and 4.2. Lab names of the catalogue (10/11/2026). '
                   'RD = rolling direction.', st_sub),
         Spacer(1, 4)]
legend = Table([['', 'Not sure: inferred from the paper or to choose. The last column gives the question (end of the document).']],
               colWidths=[8 * mm, 166 * mm])
legend.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, 0), YELLOW), ('BOX', (0, 0), (0, 0), 0.4, G_LINE),
                            ('FONT', (0, 0), (-1, -1), FONT, 8.5), ('TEXTCOLOR', (1, 0), (1, 0), G_TEXT),
                            ('LEFTPADDING', (1, 0), (1, 0), 6), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
story += [legend]
grand = []
for title, loading, tension, shear in RATES:
    t, tot = table(tension, shear)
    grand.append((title.split('  ')[1].title(), tot))
    story.append(KeepTogether([Paragraph(title, st_h), Paragraph(loading, st_load), t]))
story += [Spacer(1, 8),
          Paragraph('All rates: %s' % ' + '.join('%d' % g[1] for g in grand) +
                    ' = <b>%d specimens per material</b>.' % sum(g[1] for g in grand), st_cell),
          Spacer(1, 14),
          Paragraph('QUESTIONS FOR THE SUPERVISORS', st_title), Spacer(1, 6)]
for i, (topic, text) in enumerate(QUESTIONS, 1):
    story.append(Paragraph('<b>Q%d</b>&nbsp;&nbsp;&nbsp;<b>%s.</b> %s' % (i, topic.upper(), text), st_q))
story += [Spacer(1, 8), Paragraph('Q1 first: it decides the central-hole type and the shear geometry.', st_note)]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(G_TEXT)
    canvas.drawString(18 * mm, 10 * mm, 'Test campaigns, DP steel sheet · Mohr lab, ETH Zurich · 11/11/2026')
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, 'page %d' % doc.page)
    canvas.restoreState()


doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                        bottomMargin=16 * mm, title='Test campaigns, DP steel sheet', author='Mohr lab, ETH Zurich')
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print('written', OUT)
