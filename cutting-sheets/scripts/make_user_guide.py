# -*- coding: utf-8 -*-
"""
make_user_guide.py -- Builds cutting-sheets/user_guide.pdf (how to use the cutting-plan tool).

Run from the repository root, after a run of the shear plan order (the guide shows its preview and notice):
    py cutting-sheets/scripts/make_plan.py cutting-sheets/orders/ETH_450x380mm_ShearEDM_v20250520.yaml
    py cutting-sheets/scripts/make_user_guide.py
Needs reportlab and pdftoppm (poppler) for the notice picture.
"""
import datetime
import glob
import os
import subprocess
import tempfile

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
OUT = os.path.join(BASE, 'user_guide.pdf')
RUN = os.path.join(BASE, 'output', 'ETH_450x380mm_ShearEDM_v20250520_EDM')   # run of the shear plan order (--final)
if not os.path.isdir(RUN):
    RUN = os.path.join(BASE, 'runs', 'ETH_450x380mm_ShearEDM_v20250520_EDM')

for name, f in (('Sans', 'DejaVuSans.ttf'), ('Sans-Bold', 'DejaVuSans-Bold.ttf'), ('Mono', 'DejaVuSansMono.ttf')):
    for d in ('/usr/share/fonts/truetype/dejavu', 'C:/Windows/Fonts'):
        if os.path.exists(os.path.join(d, f)):
            pdfmetrics.registerFont(TTFont(name, os.path.join(d, f)))
            break

ACCENT = colors.HexColor('#1f4e79')
GREY = colors.HexColor('#f2f4f7')
LINE = colors.HexColor('#c9ced6')
S = {
    'title': ParagraphStyle('title', fontName='Sans-Bold', fontSize=20, leading=24, textColor=ACCENT, spaceAfter=4),
    'sub': ParagraphStyle('sub', fontName='Sans', fontSize=10, leading=13, textColor=colors.HexColor('#555555')),
    'h1': ParagraphStyle('h1', fontName='Sans-Bold', fontSize=13.5, leading=17, textColor=ACCENT, spaceBefore=10,
                         spaceAfter=5),
    'h2': ParagraphStyle('h2', fontName='Sans-Bold', fontSize=10.5, leading=14, spaceBefore=6, spaceAfter=3),
    'p': ParagraphStyle('p', fontName='Sans', fontSize=9.3, leading=12.6, alignment=TA_LEFT, spaceAfter=4),
    'cell': ParagraphStyle('cell', fontName='Sans', fontSize=8.3, leading=10.6),
    'cellb': ParagraphStyle('cellb', fontName='Sans-Bold', fontSize=8.3, leading=10.6),
    'code': ParagraphStyle('code', fontName='Mono', fontSize=8.2, leading=10.6, backColor=GREY, borderPadding=5,
                           leftIndent=5, rightIndent=5, spaceBefore=3, spaceAfter=8),
    'cap': ParagraphStyle('cap', fontName='Sans', fontSize=8, leading=10, textColor=colors.HexColor('#555555'),
                          spaceAfter=8),
    'note': ParagraphStyle('note', fontName='Sans', fontSize=9, leading=12, backColor=colors.HexColor('#fff7e6'),
                           borderColor=colors.HexColor('#f0b429'), borderWidth=0.6, borderPadding=6, leftIndent=6,
                           rightIndent=6, spaceBefore=4, spaceAfter=10),
}
W = A4[0] - 36 * mm


def P(t, s='p'):
    return Paragraph(t, S[s])


def code(t):
    return Preformatted(t.strip('\n'), S['code'])


def table(rows, widths, head=True):
    data = [[Paragraph(str(c), S['cellb' if head and i == 0 else 'cell']) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * W for w in widths], repeatRows=1 if head else 0)
    st = [('GRID', (0, 0), (-1, -1), 0.4, LINE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
          ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
    if head:
        st += [('BACKGROUND', (0, 0), (-1, 0), GREY)]
    t.setStyle(TableStyle(st))
    return t


def picture(path, width):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(path).getSize()
    return Image(path, width=width, height=width * ih / iw)


def footer(c, doc):
    c.saveState()
    c.setFont('Sans', 7.5)
    c.setFillColor(colors.HexColor('#777777'))
    c.drawString(18 * mm, 10 * mm, 'EDM cutting plans – user guide')
    c.drawRightString(A4[0] - 18 * mm, 10 * mm, 'page %d' % doc.page)
    c.restoreState()


def build():
    tmp = tempfile.mkdtemp()
    subprocess.run(['pdftoppm', '-r', '110', '-png', '-f', '1', '-l', '1', os.path.join(RUN, 'notice.pdf'),
                    os.path.join(tmp, 'notice')], check=True)
    notice_png = glob.glob(os.path.join(tmp, 'notice*.png'))[0]
    from PIL import Image as PILImage, ImageOps                 # crop the white border of the notice page
    im = PILImage.open(notice_png).convert('RGB')
    bbox = ImageOps.invert(im).getbbox()
    im.crop((max(0, bbox[0] - 15), max(0, bbox[1] - 15), bbox[2] + 15, bbox[3] + 15)).save(notice_png)
    st = []
    st += [P('EDM cutting plans', 'title'),
           P('User guide of the cutting-plan tool (<font name="Mono">cutting-sheets/</font>) – version of %s'
             % datetime.date.today().strftime('%d %B %Y'), 'sub'), Spacer(1, 8)]

    st += [P('1. What the tool does', 'h1'),
           P('You write a short <b>order</b> (a text file: which specimens, how many, at which angle to the rolling '
             'direction, on which sheet). The tool then, without any manual step:'),
           table([['Step', 'What happens'],
                  ['1. Order and templates', 'reads and checks the order; takes the template of each specimen type '
                                             'from the lab catalogue'],
                  ['2. Specimens', 'turns each specimen to its angle, adds its notch code (angle + index) and its 2 Mikrosteg recesses'],
                  ['3. Placement', 'places all the specimens on as few sheets as possible: 5 mm gap, inside the '
                                   'effective area of the machine, never mirrored'],
                  ['4. DXF', 'writes the cutting plan (mm, colours = EDM quality Q3 / Q4 / Q5)'],
                  ['5. Checks', 'reads the final DXF back and checks contours, gaps, margins, outlines and codes'],
                  ['6. Notice and registry', 'writes the notice for the workshop and the specimen registry']],
                 [0.27, 0.73]),
           Spacer(1, 4),
           P('Typical durations: shear plan (24 specimens) about 30 s; plans of 64–66 specimens about 4 min.')]

    st += [P('2. Installation (once per PC)', 'h1'),
           P('The tool runs on Windows with Python 3.10 to 3.14 (64 bit) and Git Bash. Open Git Bash and check the '
             'Python version:'),
           code('py --version'),
           P('Then install the Python modules:'),
           code('py -m pip install ezdxf shapely matplotlib scipy pyyaml spyrrow==0.9.0 packingsolver'),
           P('Get the repository the first time (then <font name="Mono">git pull</font> is enough to update it):'),
           code('cd ~/Documents\ngit clone https://github.com/josselindavion/eth.git'),
           P('If <font name="Mono">py</font> starts an old Python (for example 3.7, 32 bit), spyrrow cannot be '
             'installed: install a recent Python 3 (64 bit) from python.org and run <font name="Mono">py -0p</font> '
             'to list the installed versions.', 'note')]

    st += [P('3. Running an order', 'h1'),
           P('Always from the repository root:'),
           code('cd ~/Documents/eth\ngit pull\npy cutting-sheets/scripts/make_plan.py cutting-sheets/orders/ETH_450x380mm_ShearEDM_v20250520.yaml'),
           table([['Option', 'Effect'],
                  ['(none)', 'results in <font name="Mono">cutting-sheets/runs/&lt;name&gt;/</font>; this folder is '
                             'ignored by git, so runs can be repeated freely'],
                  ['<font name="Mono">--final</font>', 'results in <font name="Mono">cutting-sheets/output/&lt;name&gt;/'
                                                      '</font> (kept by git): use it for the plan sent to the '
                                                      'workshop, then <font name="Mono">git add</font>, '
                                                      '<font name="Mono">git commit</font>, '
                                                      '<font name="Mono">git push</font>'],
                  ['<font name="Mono">--time 5</font>', 'replaces <font name="Mono">time</font> of the order '
                                                       '(seconds of compaction per sheet)']],
                 [0.2, 0.8]),
           Spacer(1, 6),
           P('The terminal shows the 6 steps, progress bars with the remaining time, the specimens moved between '
             'sheets, and the table of checks. A good run ends with:'),
           code('DONE, all checks OK, in 28 s\n'
                '    Plan    : .../runs/ETH_450x380mm_ShearEDM_v20250520_EDM/ETH_..._EDM.dxf\n'
                '    Notice  : .../notice.pdf\n    Registry: .../registry.csv\n    Preview : .../preview.png')]

    st += [PageBreak(), P('4. Writing an order', 'h1'),
           P('Copy <font name="Mono">cutting-sheets/orders/ETH_450x380mm_ShearEDM_v20250520.yaml</font> under a new name and edit it with any '
             'text editor. Every field is explained by a comment in the file. Text after # is a comment. Keep the '
             'indentation (spaces, no tabs).'),
           code("""name: ETH_300x400mm_SHEET_v20261103_UT30   # plan name: output folder, DXF, notice
sheet: 300x400                     # complete sheet, RD x TD (rolling direction first)
clamping: {left: 40, bottom: 40}   # L-shaped clamping
machine_area: 250x350              # wire travel of the EDM (CUT E 350), RD x TD
placement_margin: 5                # tolerance on the position of the sheet in the machine
edge_margin: 5                     # distance to a free edge of the sheet
gap: 5                             # distance between two specimens
specimens:
  - {type: UT40, angle: 30, count: 5}
  - {type: NT20, angle: 45, count: 3, first_index: 1}"""),
           P('4.1 The sheet on the machine', 'h2'),
           table([['Field', 'Meaning', 'Default'],
                  ['sheet', 'complete sheet in mm, rolling direction first: RDxTD (600x500 = 600 mm along the rolling '
                            'direction × 500 mm across)', 'required'],
                  ['clamping', 'bands held by the clamps, per side (left, bottom, right, top); '
                               '{left: 40, bottom: 40} = L-shaped clamping', 'none'],
                  ['machine_area', 'area the wire can reach, RD × TD (CUT E 350: 250x350 = Y × X travel); leave it out '
                                   'for the waterjet', 'whole sheet'],
                  ['machine_position', 'where the machine area starts on the sheet, {left: .., bottom: ..}',
                   'inner corner of the clamping'],
                  ['placement_margin', 'nothing is placed within this distance of the machine area edge, because '
                                       'the sheet is not positioned to the mm', '5'],
                  ['edge_margin', 'minimum distance to a free (not clamped) edge of the sheet', '5'],
                  ['gap', 'minimum distance between two specimens', '5']],
                 [0.2, 0.62, 0.18]),
           Spacer(1, 4),
           P('<b>Effective area</b> (where the specimens go) = machine area minus the placement margin on each side, '
             'inside the sheet and outside the clamping. With the values above: machine area from x 40, y 40 to '
             'x 390, y 290, effective area 240 (RD) × 340 (TD) mm from x 45, y 45. The terminal, the notice and the '
             'preview show these zones and write every size rolling direction first, marked (RD) / (TD).'),
           P('4.2 Placement time', 'h2'),
           table([['Field', 'Meaning', 'Default'],
                  ['assign_time', 'seconds for PackingSolver to put all the specimens on sheets', '30'],
                  ['fill_tries', 'failed tries allowed when moving specimens to empty one sheet (0 = faster, '
                                 'maybe one sheet more)', '8'],
                  ['fill_time', 'seconds at most per try (a try that succeeds stops after 1–3 s)', '10'],
                  ['time', 'seconds at most of final compaction per sheet (0 = none)', '15'],
                  ['seed', 'random seed: change it to get another layout', '1'],
                  ['max_sheets', 'the order is rejected if it needs more sheets', '20'],
                  ['spread_distance', 'two repeats (same type and angle) closer than this (mm) are "side by side": '
                                      'swaps after the placement separate them; the pairs left are a warning '
                                      '(orange circles on the preview)', '10'],
                  ['spread_tries', 'placements tried (seed, seed + 1, ...) to keep the repeats apart; the best is '
                                   'kept (fewest sheets, then fewest pairs); time up to x tries', '1']],
                 [0.2, 0.62, 0.18]),
           P('4.3 Specimens', 'h2'),
           P('One line = <i>count</i> specimens of one <i>type</i> at one <i>angle</i>.'),
           table([['Key', 'Meaning'],
                  ['type', 'specimen type (table below)'],
                  ['angle', 'direction of the coded end from the rolling direction, counter-clockwise: 0 to 135° '
                            'in steps of 15° (written in the notch code)'],
                  ['count', 'number of specimens'],
                  ['first_index', 'index (number in the notch code) of the first specimen, then +1 each '
                                  '(default 0, max 9)']],
                 [0.2, 0.8]),
           Spacer(1, 6),
           table([['Type (lab name)', 'Older names', 'Specimen'],
                  ['UT40', 'UTUT, UT', 'uniaxial tension, 106 mm (gauge zone ≈ 40 mm)'],
                  ['NT20 / NT06', 'NT6.67 (for NT06)', 'notched tension, radius 20 / 6.67 mm, 106 mm'],
                  ['CHD48', 'CHCH, CH', 'central hole Ø 4.8 mm, 106 mm'],
                  ['UT19', 'UTST', 'short uniaxial tension, 81 mm (gauge zone ≈ 19 mm)'],
                  ['SHLD / SHMD / SHHD', '–', 'short shear, 81 mm'],
                  ['MNAK_ROUND_FULL / MNAK_ROUND_HOLE', 'MNAK_FULL / MNAK_HOLE',
                   'round Mini-Nakajima without / with 2 holes (holes at angle + 90°)'],
                  ['MNAK_RECT_FULL / MNAK_RECT_HOLE', '– / MNAK_RECT', 'rectangular Mini-Nakajima 80 × 54 mm '
                                                                       'without / with 2 holes (holes oriented as on '
                                                                       'the disc with the same angle)'],
                  ['LASER', 'TENS_FULL, STRIP', 'strip 140 × 30 mm, no code (speckle contrast)']],
                 [0.3, 0.2, 0.5]),
           Spacer(1, 4),
           P('Only the fields of this guide are accepted: an unknown field (typo, old field) stops the run with the '
             'list of allowed fields, so nothing is silently ignored.', 'note')]

    st += [P('5. Results', 'h1'),
           P('Each run writes exactly 4 files in its folder:'),
           table([['File', 'For', 'Content'],
                  ['&lt;name&gt;.dxf', 'workshop', 'the cutting plan: one frame per sheet, every specimen with its '
                                                  'notch code; mm; colour = EDM quality (3 = Q3 normal, 4 = Q4 medium, '
                                                  '5 = Q5 high)'],
                  ['notice.pdf', 'workshop', 'one page per sheet (numbered specimens, rolling direction, qualities, '
                                             'zones, Mikrostegs as red squares) and the list of specimens'],
                  ['registry.csv', 'lab', 'one line per specimen: number, sheet, type, angle, notch code, position, '
                                          'specimen ID'],
                  ['preview.png', 'you', 'all the sheets with the zones, to check the plan at a glance']],
                 [0.18, 0.12, 0.7]),
           Spacer(1, 4),
           P('<b>Mikrostegs</b>: every specimen has 2 small half-circle recesses (radius 1.5 mm) in its outline. The '
             'workshop stops the wire at the bottom of each recess (red square on the notice), so the specimen stays '
             'attached; after breaking it out, the rest of the bridge stays inside the recess.'),
           P('Send the <b>DXF and notice.pdf</b> to the workshop; keep <b>registry.csv</b> for the lab.'),
           KeepTogether([picture(os.path.join(RUN, 'preview.png'), W),
                         P('preview.png of the shear plan (orders/ETH_450x380mm_ShearEDM_v20250520.yaml). Red hatching: clamping; black dashed: machine area '
                           '(wire travel); orange band: placement margin; purple: effective area where the '
                           'specimens are placed; grey: part of the sheet out of reach of the wire. Line colours '
                           '= EDM quality.', 'cap')]),
           KeepTogether([picture(notice_png, 0.55 * W),
                         P('First page of notice.pdf (same plan); red squares = Mikrostegs.', 'cap')])]

    st += [P('6. Checks and error messages', 'h1'),
           P('After writing the DXF, the tool reads it back without any assumption. Every line must be '
             '<font name="Mono">OK</font>:'),
           table([['Check', 'What is verified'],
                  ['Units', 'the DXF is in millimetres'],
                  ['Sheets', 'one frame per sheet, of the ordered size'],
                  ['Closed contours / duplicate lines', 'every cutting contour is closed, no line twice'],
                  ['Colours = EDM quality', 'cutting lines only in colours 3 / 4 / 5'],
                  ['Overlaps / gap between pieces', 'no overlap; at least gap mm between two pieces'],
                  ['Margin to sheet edge', 'every piece inside the effective area'],
                  ['ID codes', 'every coded specimen carries a notch code; shared codes only between different '
                               'shapes'],
                  ['Specimens vs order', 'outline = template, code read back = code ordered, direction = angle '
                                         'ordered']],
                 [0.32, 0.68]),
           Spacer(1, 6),
           table([['Message', 'Meaning and what to do'],
                  ['ORDER REJECTED: unknown field(s): …', 'typo or old field in the order: use the names of '
                                                          'section 4'],
                  ['ORDER REJECTED: missing field "machine_area"', 'sheet and machine_area are required'],
                  ['ORDER REJECTED: no effective area left', 'clamping + margins leave no room: check sheet, '
                                                             'clamping, machine_area, placement_margin'],
                  ['ORDER REJECTED: … does not fit in the usable area', 'a specimen is larger than the effective '
                                                                        'area once turned: bigger sheet or smaller '
                                                                        'margins'],
                  ['ORDER REJECTED: the specimens need N sheets', 'more sheets than max_sheets: raise max_sheets '
                                                                 'or split the order'],
                  ['DONE WITH ERRORS (see above)', 'a check failed: do not send the plan; the preview circles the '
                                                   'problem in red'],
                  ['py314: command not found', 'use py (the alias py314 only existed in one terminal)']],
                 [0.42, 0.58]),
           P('7. Tips', 'h1'),
           table([['I want…', 'Do this'],
                  ['a faster run', 'lower fill_tries (0 = no try to remove a sheet) and time'],
                  ['fewer sheets', 'raise fill_tries / fill_time, or try another seed'],
                  ['a different sheet or clamping', 'change sheet, clamping, placement_margin: the preview shows the '
                                                    'new zones'],
                  ['to keep the plan sent to the workshop', 'run again with --final, then git add / commit / push']],
                 [0.32, 0.68]),
           Spacer(1, 6),
           P('More details (method, engines, notch code): <font name="Mono">cutting-sheets/README.md</font>.')]

    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title='EDM cutting plans – user guide',
                            author='cutting-sheets tool')
    doc.build(st, onFirstPage=footer, onLaterPages=footer)
    print('written:', OUT)


if __name__ == '__main__':
    build()
