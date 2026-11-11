# -*- coding: utf-8 -*-
"""
make_campaigns_xlsx.py -- Test campaigns of one DP steel sheet (slow, medium, high rate; shear) as a workbook,
from Beerli et al. (2026), Int. J. Impact Eng. 215, 105761 (literature/papers/). User request of 11/11/2026.

    py cutting-sheets/scripts/make_campaigns_xlsx.py cutting-sheets/campaigns/DP_test_campaigns_Beerli2026.xlsx

Sheets: Overview (totals by formulas, check against the paper), one sheet per campaign (specimen, lab name,
orientation, number), Notes (assumptions and open questions). Formulas are computed when the file is opened in Excel.
"""
import sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = sys.argv[1]
SRC = 'Beerli et al. (2026), Int. J. Impact Eng. 215, 105761'

F = 'Arial'
NAVY = '1F3864'
f_title = Font(name=F, size=14, bold=True, color=NAVY)
f_sub = Font(name=F, size=10, italic=True, color='555555')
f_head = Font(name=F, size=10, bold=True, color='FFFFFF')
f_body = Font(name=F, size=10)
f_bold = Font(name=F, size=10, bold=True)
f_sec = Font(name=F, size=11, bold=True, color=NAVY)
fill_head = PatternFill('solid', fgColor=NAVY)
fill_band = PatternFill('solid', fgColor='EEF2F8')
fill_total = PatternFill('solid', fgColor='D9E1F2')
fill_inf = PatternFill('solid', fgColor='FCE4D6')     # inferred / to confirm
fill_ok = PatternFill('solid', fgColor='E2EFDA')      # stated in the paper
thin = Side(style='thin', color='BFBFBF')
box = Border(left=thin, right=thin, top=thin, bottom=thin)
wrap = Alignment(wrap_text=True, vertical='top')
center = Alignment(horizontal='center', vertical='top', wrap_text=True)

STATED, INFERRED = 'Stated in paper', 'Inferred'

# ---------------------------------------------------------------- specimen data (one material)
# paper name, lab name, test / stress state, orientations, repeats, cutting, status, source, note
SPEC = {
    'UT': ('UT', 'UT40', 'Uniaxial tension (plasticity, Lankford ratio)', 'Waterjet',
           'Gauge 40 x 10 mm (Sec. 2.2) = catalogue UT40.'),
    'sUT': ('sUT', 'UT19', 'Uniaxial tension, small (high rate: equilibrium)', 'Waterjet',
            'Paper sUT gauge 15 x 5 mm (Sec. 2.2); closest catalogue type UT19 (5 mm wide, about 16 mm parallel, '
            '19 mm between shoulders): to confirm.'),
    'NT20': ('NT20', 'NT20', 'Notched tension, notch radius 20 mm (fracture)', 'Waterjet',
             '20 mm wide gauge, 10 mm at the notch (Sec. 2.2).'),
    'NT6': ('NT6', 'NT06', 'Notched tension, notch radius 6.67 mm (fracture, near plane strain)', 'Waterjet',
            'Radius 6.77 mm in the text, 6.67 mm in Fig. 2; catalogue 6.67 mm.'),
    'CH': ('CH5 / CH8', 'CHD48', 'Central hole tension (fracture at the hole edge)', 'Waterjet + reaming',
           'CH5 (DP590-DP1000): cut at 4.8 mm (CHD48) then reamed to 5 mm. CH8 (DP1180, DP1470) has no '
           'catalogue type yet.'),
    'SH': ('SH', 'SHMD', 'Shear (fracture)', 'Wire EDM',
           'Geometry for medium-ductility materials of Roth & Mohr (2018) [49] (Sec. 2.2) = probably SHMD '
           '(LD / MD / HD = low / medium / high ductility): to confirm.'),
    'PU': ('PU', 'MNAK_RECT_FULL', 'Miniature punch (equi-biaxial tension)', 'Waterjet',
           'Roth & Mohr (2016) [58]. Lab type: Mini-Nakajima without holes (probable, to confirm).'),
    'BE': ('BE', 'MNAK_RECT_HOLE', 'Dihedral mini-Nakazima (plane strain tension)', 'Waterjet',
           'Grolleau et al. (2019) [59]. Lab type: Mini-Nakajima with 2 holes (probable, to confirm).'),
}

# campaign rows: (spec key, orientation, repeats, status of the repeats, source)
S41 = 'Sec. 4.1'
S42 = 'Sec. 4.2'
slow = ([('UT', a, 3, STATED, S41) for a in (0, 15, 30, 45, 60, 75, 90)] +
        [(k, a, 3, STATED, S41) for k in ('NT20', 'NT6', 'CH') for a in (0, 45, 90)] +
        [(k, a, 3, INFERRED, S41) for k in ('PU', 'BE') for a in (0, 45, 90)])
medium = [(k, 0, 3, INFERRED, S42) for k in ('UT', 'NT20', 'NT6', 'CH')]
high = [(k, 0, 3, INFERRED, S42) for k in ('sUT', 'NT20', 'NT6', 'CH')]
sh_slow = [('SH', a, 2, STATED, S41) for a in (0, 45, 90)]
sh_medium = [('SH', 0, 3, INFERRED, S42)]
sh_high = [('SH', 0, 3, INFERRED, S42)]

CAMPAIGNS = [
    # sheet name, title, rate text, machine, rows
    ('Slow rate', 'Slow rate campaign (quasi-static), tension-type specimens',
     'UT: strain rate 0.001 /s; other specimens: v = 6.6e-6 m/s (comparable local strain rate)',
     '100 kN hydraulic universal testing machine, high-pressure grips (Sec. 2.3)', slow),
    ('Medium rate', 'Medium (intermediate) rate campaign, tension-type specimens',
     'UT: strain rate 1 /s; other specimens: v = 6.6e-3 m/s',
     '100 kN hydraulic universal testing machine Instron 8801, high-pressure clamps (Sec. 2.4)', medium),
    ('High rate', 'High rate campaign, tension-type specimens',
     'UT: strain rate 100 /s (global; locally 300-1400 /s in the neck); other specimens: v = about 1.4 m/s',
     'Split Hopkinson tensile bar with load inversion device, form-fit (fir-tree) clamping (Sec. 2.5)', high),
    ('Shear slow', 'Shear campaign, slow rate', 'v = 6.6e-6 m/s',
     '100 kN hydraulic universal testing machine (Sec. 2.3)', sh_slow),
    ('Shear medium', 'Shear campaign, medium (intermediate) rate', 'v = 6.6e-3 m/s',
     'Instron 8801 (Sec. 2.4)', sh_medium),
    ('Shear high', 'Shear campaign, high rate', 'v = about 1.4 m/s',
     'Split Hopkinson tensile bar with load inversion device (Sec. 2.5)', sh_high),
]

SHORT = {'Slow rate': 'UT 0.001 /s; others 6.6e-6 m/s', 'Medium rate': 'UT 1 /s; others 6.6e-3 m/s',
         'High rate': 'UT 100 /s; others about 1.4 m/s', 'Shear slow': '6.6e-6 m/s',
         'Shear medium': '6.6e-3 m/s', 'Shear high': 'about 1.4 m/s'}
HEAD = ['#', 'Specimen (paper)', 'Lab name (catalogue)', 'Test / stress state', 'Orientation to RD (°)',
        'Number of specimens', 'Cutting', 'Repeats', 'Source', 'Notes']
WIDTH = [5, 13, 18, 38, 13, 12, 17, 16, 11, 70]
FIRST = 6          # first data row of a campaign sheet


def set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def head_row(ws, r, labels):
    for c, v in enumerate(labels, 1):
        x = ws.cell(r, c, v)
        x.font, x.fill, x.alignment, x.border = f_head, fill_head, center, box
    ws.row_dimensions[r].height = 30


wb = Workbook()
ov = wb.active
ov.title = 'Overview'
totals = {}        # sheet -> total cell reference
for name, title, rate, machine, rows in CAMPAIGNS:
    ws = wb.create_sheet(name)
    set_widths(ws, WIDTH)
    ws['A1'] = title
    ws['A1'].font = f_title
    ws['A2'] = 'Loading: ' + rate
    ws['A3'] = 'Machine: ' + machine
    ws['A4'] = 'Per material (one sheet of steel). Source: ' + SRC + '. Orange = inferred, see sheet "Notes".'
    for a in ('A2', 'A3', 'A4'):
        ws[a].font = f_sub
    head_row(ws, 5, HEAD)
    r = FIRST
    prev = None
    band = False
    for i, (key, ang, rep, status, src) in enumerate(rows, 1):
        pname, lab, test, cut, note = SPEC[key]
        if key != prev:
            band = not band
        vals = [i, pname, lab, test, ang, rep, cut, status, src, note if key != prev else '']
        for c, v in enumerate(vals, 1):
            x = ws.cell(r, c, v)
            x.font, x.border = f_body, box
            x.alignment = center if c in (1, 5, 6, 8, 9) else wrap
            if band:
                x.fill = fill_band
        ws.cell(r, 8).fill = fill_inf if status == INFERRED else fill_ok
        if key in ('sUT', 'SH', 'PU', 'BE'):
            ws.cell(r, 3).fill = fill_inf
        prev = key
        r += 1
    last = r - 1
    ws.cell(r, 1, 'Total')
    ws.cell(r, 6, '=SUM(F%d:F%d)' % (FIRST, last))
    for c in range(1, len(HEAD) + 1):
        x = ws.cell(r, c)
        x.font, x.fill, x.border = f_bold, fill_total, box
        x.alignment = center if c in (1, 6) else wrap
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    ws.freeze_panes = 'A6'
    ws.sheet_view.zoomScale = 110
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    totals[name] = (FIRST, last, r)

# ---------------------------------------------------------------- overview
set_widths(ov, [30, 34, 14, 14, 14, 14, 14, 14, 14, 14])
ov['A1'] = 'Testing campaigns, DP steel sheet (one material)'
ov['A1'].font = f_title
ov['A2'] = ('Source: ' + SRC + ', Sec. 2 and 4. Thomas Beerli is the first author; "Thomas et al. [53]" in that '
            'paper is only cited for the fir-tree clamp idea.')
ov['A3'] = ('All numbers per material and computed from the campaign sheets (formulas). Orange = inferred from the '
            'paper, not stated: see sheet "Notes".')
for a in ('A2', 'A3'):
    ov[a].font = f_sub

ov['A5'] = '1. Campaigns'
ov['A5'].font = f_sec
head_row(ov, 6, ['Campaign', 'Loading', 'Specimens per material', 'x 5 materials (as in the paper)', '', '', '', '', '', ''])
ov.row_dimensions[6].height = 42
for c in range(5, 11):
    ov.cell(6, c).fill = PatternFill(fill_type=None)
    ov.cell(6, c).border = Border()
r = 7
rows_ov = {}
for name, title, rate, machine, rows in CAMPAIGNS:
    a, b, t = totals[name]
    q = "'%s'" % name
    vals = [name, SHORT[name], '=%s!F%d' % (q, t), '=C%d*5' % r]
    for c, v in enumerate(vals, 1):
        x = ov.cell(r, c, v)
        x.font, x.border = f_body, box
        x.alignment = center if c >= 3 else wrap
    rows_ov[name] = r
    r += 1
ov.cell(r, 1, 'Total')
ov.cell(r, 3, '=SUM(C7:C%d)' % (r - 1))
ov.cell(r, 4, '=SUM(D7:D%d)' % (r - 1))
for c in range(1, 5):
    x = ov.cell(r, c)
    x.font, x.fill, x.border, x.alignment = f_bold, fill_total, box, (center if c >= 3 else wrap)
tot_row = r

r += 2
ov.cell(r, 1, '2. Check against the totals given in the paper (5 materials)').font = f_sec
r += 1
head_row(ov, r, ['Rate', 'Paper (Sec. 4)', 'This workbook', 'Difference', '', '', '', '', '', ''])
for c in range(5, 11):
    ov.cell(r, c).fill = PatternFill(fill_type=None)
    ov.cell(r, c).border = Border()
r += 1
chk = [('Slow (tension-type + shear)', 378, '=D%d+D%d' % (rows_ov['Slow rate'], rows_ov['Shear slow'])),
       ('Medium + high (tension-type + shear)', 150, '=D%d+D%d+D%d+D%d' % (
           rows_ov['Medium rate'], rows_ov['High rate'], rows_ov['Shear medium'], rows_ov['Shear high']))]
for lab, paper, f in chk:
    vals = [lab, paper, f, '=C%d-B%d' % (r, r)]
    for c, v in enumerate(vals, 1):
        x = ov.cell(r, c, v)
        x.font, x.border = f_body, box
        x.alignment = center if c >= 2 else wrap
    ov.cell(r, 2).font = Font(name=F, size=10, color='0000FF')
    r += 1
ov.cell(r, 1, ('Slow: the paper gives 378 tests for 5 materials (75.6 per material, not a whole number); the matrix '
               'stated in Sec. 4.1 gives 72 per material (360). The 18 missing tests are not explained in the paper. '
               'Elevated rates: 150 = 5 materials x 2 rates x 5 specimen types x 3 repeats, which is how the repeats '
               'at elevated rates (not stated) are inferred.'))
ov.cell(r, 1).font = f_sub
ov.cell(r, 1).alignment = wrap
ov.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
ov.row_dimensions[r].height = 54

r += 2
ov.cell(r, 1, '3. Specimens per lab type and campaign (per material)').font = f_sec
r += 1
cols = [c[0] for c in CAMPAIGNS]
head_row(ov, r, ['Lab name (catalogue)', 'Specimen (paper)'] + cols + ['Total', ''])
ov.cell(r, 10).fill = PatternFill(fill_type=None)
ov.cell(r, 10).border = Border()
r += 1
labs = []
for k in ('UT', 'sUT', 'NT20', 'NT6', 'CH', 'SH', 'PU', 'BE'):
    labs.append((SPEC[k][1], SPEC[k][0]))
m0 = r
for lab, pname in labs:
    ov.cell(r, 1, lab)
    ov.cell(r, 2, pname)
    for j, name in enumerate(cols):
        a, b, t = totals[name]
        q = "'%s'" % name
        ov.cell(r, 3 + j, '=SUMIFS(%s!$F$%d:$F$%d,%s!$C$%d:$C$%d,$A%d)' % (q, a, b, q, a, b, r))
    ov.cell(r, 3 + len(cols), '=SUM(C%d:%s%d)' % (r, get_column_letter(2 + len(cols)), r))
    for c in range(1, 4 + len(cols)):
        x = ov.cell(r, c)
        x.font, x.border = f_body, box
        x.alignment = center if c >= 3 else wrap
    ov.cell(r, 3 + len(cols)).font = f_bold
    r += 1
ov.cell(r, 1, 'Total')
for c in range(3, 4 + len(cols)):
    L = get_column_letter(c)
    ov.cell(r, c, '=SUM(%s%d:%s%d)' % (L, m0, L, r - 1))
for c in range(1, 4 + len(cols)):
    x = ov.cell(r, c)
    x.font, x.fill, x.border, x.alignment = f_bold, fill_total, box, (center if c >= 3 else wrap)
mat_total = r
r += 1
ov.cell(r, 1, 'Check: equals the campaign total above')
ov.cell(r, 3 + len(cols), '=IF(%s%d=C%d,"OK","CHECK")' % (get_column_letter(3 + len(cols)), mat_total, tot_row))
ov.cell(r, 1).font = f_sub
ov.cell(r, 3 + len(cols)).font = f_bold
ov.cell(r, 3 + len(cols)).alignment = center

r += 2
ov.cell(r, 1, 'Legend').font = f_sec
r += 1
for fill, txt in ((fill_ok, 'Stated in the paper'), (fill_inf, 'Inferred or to confirm (see sheet "Notes")'),
                  (fill_total, 'Totals (formulas)')):
    ov.cell(r, 1).fill = fill
    ov.cell(r, 1).border = box
    ov.cell(r, 2, txt).font = f_body
    r += 1
x = ov.cell(r, 1, 'Blue numbers: totals copied from the paper (inputs).')
x.font = Font(name=F, size=10, color='0000FF')
ov.freeze_panes = 'A5'

# ---------------------------------------------------------------- notes
nt = wb.create_sheet('Notes')
set_widths(nt, [5, 34, 100])
nt['A1'] = 'Assumptions, open questions and sources'
nt['A1'].font = f_title
head_row(nt, 3, ['#', 'Topic', 'What the paper says / what is assumed here'])
notes = [
    ('Orientations', 'Slow rate: UT in 7 orientations (0, 15, ..., 90°); NT6, NT20, CH5/8 and SH in 0, 45, 90° '
                     'to the rolling direction (Sec. 4.1). Elevated rates: "the same experiments ... in the rolling '
                     '(0°) orientation" (Sec. 4.2).'),
    ('Repeats, slow', 'Three repeats for all tests, two for shear "as these specimens needed to be extracted using '
                      'wire EDM" (Sec. 4.1).'),
    ('Repeats, medium and high', 'Not stated. Inferred: 3 repeats for UT, NT20, NT6, CH and SH, because the paper '
                                 'gives 150 tests at elevated rates for 5 materials = 5 x 2 rates x 5 types x 3.'),
    ('Punch (PU) and mini-Nakazima (BE)', 'Slow rate only, "performed in three orientations" (Sec. 4.1). Assumed '
                                          'here: 0, 45, 90° and 3 repeats (the general rule). Not tested at '
                                          'elevated rates (Fig. 9-10 show UT, NT20, NT6, CH, SH only). The current '
                                          'order CAMPAIGN_600x500mm_WATERJET has MNAK_RECT_FULL at 0° only (3), '
                                          'not 0/45/90° (9).'),
    ('Total slow tests', 'Paper: 378 tests at 0.001 /s for 5 materials, i.e. 75.6 per material. The stated matrix '
                         'gives 72 per material (360): 18 tests not explained (maybe extra repeats).'),
    ('High rate UT specimen', 'A smaller UT (sUT, gauge 15 x 5 mm) is used at high rate for quasi-static '
                              'equilibrium (Sec. 2.2). Closest catalogue type: UT19. To confirm.'),
    ('Central hole', 'CH5 (5 mm hole) for DP590, DP780, DP1000; CH8 (8 mm) for DP1180 and DP1470 to limit the '
                     'force in the clamps (Sec. 2.2, Fig. 10). The hole is reamed to its final size. Catalogue '
                     'CHD48 = 4.8 mm cut, for CH5. No CH8 type in the catalogue.'),
    ('Shear geometry', 'One shear geometry in the paper: the one "for medium ductility materials" of Roth & Mohr '
                       '(2018) [49] (Sec. 2.2), so probably SHMD. The 2025 lab shear plan had SHLD, SHMD, SHHD at '
                       '0, 45, 90 and 135°, 2 each (24): more than the paper (6 at slow rate). Question sent to the '
                       'supervisors (pre-cut blanks, number per geometry).'),
    ('Cutting', 'All specimens except SH cut by waterjet; SH contour by wire EDM (Sec. 2.2).'),
    ('Clamping ends', 'The clamping section differs per rate in the paper (Fig. 2f-h: slow, intermediate, fast; '
                      'fir-tree form-fit clamp for the fast tests). The lab catalogue specimens all have the fir-tree '
                      'ends: to confirm that the same ends are used at all rates.'),
    ('Speckle strips', 'The LASER strips (speckle contrast tests) are not test specimens and are not in the paper.'),
    ('Loading speeds', 'UT: 0.001 /s, 1 /s, 100 /s. Other specimens: v = 6.6e-6 m/s, 6.6e-3 m/s, about 1.4 m/s, '
                       'chosen for comparable local strain rates (Sec. 4.2).'),
    ('Source', SRC + ': T. Beerli, C. C. Roth, X. Li, V. Grolleau, D. Mohr, "Rate-dependent plasticity and fracture of '
               'five DP-steels: static and dynamic high-throughput experiments and neural network modeling". File: '
               'literature/papers/Rate_dependent_plasticity_and_fracture_of_five_DP_steels_....pdf'),
    ('Lab names', 'Catalogue names of 10/11/2026 (UT40, UT19, NT20, NT06, CHD48, SHLD/SHMD/SHHD, MNAK_RECT_*).'),
]
for i, (t, txt) in enumerate(notes, 1):
    vals = [i, t, txt]
    for c, v in enumerate(vals, 1):
        x = nt.cell(3 + i, c, v)
        x.font, x.border, x.alignment = (f_bold if c == 2 else f_body), box, (center if c == 1 else wrap)
nt.freeze_panes = 'A4'

for ws in wb.worksheets:
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
wb.save(OUT)
print('written', OUT)
