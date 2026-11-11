# -*- coding: utf-8 -*-
"""
make_campaigns_xlsx.py -- Test campaigns of one DP steel sheet, one Excel sheet per strain rate (slow, medium, high),
from Beerli et al. (2026), Int. J. Impact Eng. 215, 105761 (literature/papers/). User requests of 11/11/2026
(simplified version: one sheet per rate, nothing else).

    py cutting-sheets/scripts/make_campaigns_xlsx.py cutting-sheets/campaigns/DP_test_campaigns_Beerli2026.xlsx

Each sheet: specimen (lab name), orientations to the rolling direction, repeats, number (formula), shear in its own
block (3 geometries LD / MD / HD as recommended by Roth & Mohr 2018, 2 repeats at every rate, user
11/11/2026), totals (formulas). * = to confirm with the supervisors (repeats at medium / high rate are not stated in the
paper: 3 inferred from its 150 tests = 5 materials x 2 rates x 5 types x 3).
"""
import sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

OUT = sys.argv[1]
F = 'Arial'
NAVY = '1F3864'
f_title = Font(name=F, size=14, bold=True, color=NAVY)
f_info = Font(name=F, size=10, color='595959')
f_head = Font(name=F, size=10, bold=True, color='FFFFFF')
f_body = Font(name=F, size=11)
f_bold = Font(name=F, size=11, bold=True)
f_block = Font(name=F, size=11, bold=True, color=NAVY)
f_foot = Font(name=F, size=9, italic=True, color='595959')
fill_head = PatternFill('solid', fgColor=NAVY)
fill_block = PatternFill('solid', fgColor='DDE4F0')
fill_total = PatternFill('solid', fgColor='BDD7EE')
line = Side(style='thin', color='BFBFBF')
box = Border(left=line, right=line, top=line, bottom=line)
left = Alignment(horizontal='left', vertical='center', indent=1)
mid = Alignment(horizontal='center', vertical='center')

ALL7 = '0, 15, 30, 45, 60, 75, 90'
A3 = '0, 45, 90'
# sheet: (title, loading, tension rows, shear rows); row = (specimen, orientations, n orientations, repeats)
RATES = [
    ('Slow rate', 'Slow rate (quasi-static)',
     'UT: 0.001 /s  ·  other specimens: 6.6e-6 m/s  ·  100 kN hydraulic testing machine',
     [('UT40', ALL7, 7, 3), ('NT20', A3, 3, 3), ('NT06', A3, 3, 3), ('CHD48 (CH5)', A3, 3, 3),
      ('MNAK_RECT_FULL (punch) *', A3, 3, 3), ('MNAK_RECT_HOLE (mini-Nakazima) *', A3, 3, 3)],
     [('SHLD', A3, 3, 2), ('SHMD', A3, 3, 2), ('SHHD', A3, 3, 2)]),
    ('Medium rate', 'Medium rate (intermediate)',
     'UT: 1 /s  ·  other specimens: 6.6e-3 m/s  ·  Instron 8801 (100 kN)',
     [('UT40', '0', 1, '3 *'), ('NT20', '0', 1, '3 *'), ('NT06', '0', 1, '3 *'), ('CHD48 (CH5)', '0', 1, '3 *')],
     [('SHLD *', '0', 1, 2), ('SHMD *', '0', 1, 2), ('SHHD *', '0', 1, 2)]),
    ('High rate', 'High rate',
     'UT: 100 /s  ·  other specimens: about 1.4 m/s  ·  split Hopkinson tensile bar',
     [('UT19 (small UT)', '0', 1, '3 *'), ('NT20', '0', 1, '3 *'), ('NT06', '0', 1, '3 *'),
      ('CHD48 (CH5)', '0', 1, '3 *')],
     [('SHLD *', '0', 1, 2), ('SHMD *', '0', 1, 2), ('SHHD *', '0', 1, 2)]),
]
HEAD = ['Specimen', 'Orientations to RD (°)', 'Orientations', 'Repeats', 'Number']
WIDTH = [36, 28, 14, 12, 12]


def cell(ws, r, c, v, font=f_body, fill=None, align=mid):
    x = ws.cell(r, c, v)
    x.font, x.border, x.alignment = font, box, align
    if fill:
        x.fill = fill
    return x


def block(ws, r, label, rows):
    """Block title, its rows and its subtotal; returns (next row, subtotal cell)."""
    for c in range(1, 6):
        cell(ws, r, c, label if c == 1 else None, f_block, fill_block, left)
    r += 1
    first = r
    for spec, ori, n, rep in rows:
        cell(ws, r, 1, spec, align=left)
        cell(ws, r, 2, ori)
        cell(ws, r, 3, n)
        if isinstance(rep, str):            # '3 *': number shown with the mark, value used by the formula
            cell(ws, r, 4, int(rep.split()[0]))
            ws.cell(r, 4).number_format = '0" *"'
        else:
            cell(ws, r, 4, rep)
        cell(ws, r, 5, '=C%d*D%d' % (r, r))
        r += 1
    cell(ws, r, 1, 'Subtotal', f_bold, align=left)
    for c in (2, 3, 4):
        cell(ws, r, c, None)
    cell(ws, r, 5, '=SUM(E%d:E%d)' % (first, r - 1), f_bold)
    return r + 1, 'E%d' % r


wb = Workbook()
wb.remove(wb.active)
for name, title, loading, tension, shear in RATES:
    ws = wb.create_sheet(name)
    for i, w in enumerate(WIDTH):
        ws.column_dimensions['ABCDE'[i]].width = w
    ws['A1'] = title
    ws['A1'].font = f_title
    ws['A2'] = loading
    ws['A2'].font = f_info
    ws['A3'] = 'One material (one steel sheet)'
    ws['A3'].font = f_info
    r = 5
    for c, h in enumerate(HEAD, 1):
        cell(ws, r, c, h, f_head, fill_head)
    ws.row_dimensions[r].height = 22
    r += 1
    r, s1 = block(ws, r, 'Tension-type specimens (waterjet)', tension)
    r, s2 = block(ws, r, 'Shear (wire EDM)', shear)
    for c in range(1, 6):
        cell(ws, r, c, 'TOTAL' if c == 1 else None, f_bold, fill_total, left if c == 1 else mid)
    ws.cell(r, 5).value = '=%s+%s' % (s1, s2)
    ws.row_dimensions[r].height = 20
    r += 2
    ws.cell(r, 1, '* to confirm with the supervisors.').font = f_foot
    ws.cell(r + 1, 1, 'Source: Beerli et al. (2026), Int. J. Impact Eng. 215, 105761, sections 2.2, 4.1, 4.2.').font = \
        f_foot
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = 'portrait'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
wb.save(OUT)
print('written', OUT)
