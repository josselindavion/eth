# -*- coding: utf-8 -*-
"""
make_cutting_plans_pdf.py -- PDF of the cutting plans and of the campaigns that use them (user, 12/11/2026). Page 1:
which campaign needs which plan, and for which materials each plan is cut: the same plan (one DXF, same specimens,
same codes) is reused on every sheet that needs it. Then one page per plan with its colour preview.

    py cutting-sheets/scripts/make_cutting_plans_pdf.py cutting-sheets/campaigns/cutting_plans.pdf

Plans P1 ... P6 (materials_data.PLAN_IDS); previews from output/<order>/preview.png or runs/<order>/preview.png (the
two sheets of AB_SHEETS23 are cut out of its preview). Sober page: black and greys, outlines only.
"""
import collections
import csv
import os
import sys
import tempfile

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from materials_data import MATERIALS, PLANS, PLANS_LARGE, PLAN_IDS, assign, pid, plans_of, short   # noqa: E402

ROOT = os.path.join(HERE, '..')
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
G_LINE = colors.Color(0.75, 0.75, 0.75)
PW, PH = landscape(A4)
DATE = '12/11/2026'
SHORT_NAME = {'CR1200Y1500T-MS-UNCOATED': 'CR1200Y1500T'}

# the plans in order, with their size: id -> (order, index, RD, TD)
PLAN_LIST = []
for camp in ('A', 'B', 'C'):
    for p in PLANS[camp] + PLANS_LARGE.get(camp, []):
        if (p[1], p[2]) not in [(q[0], q[1]) for q in PLAN_LIST]:
            PLAN_LIST.append((p[1], p[2], p[3], p[4]))
PLAN_LIST.sort(key=lambda q: PLAN_IDS[(q[0], q[1])])
ROWS = [('CAMPAIGN A', '4 sheets of 600 × 500', PLANS['A']),
        ('CAMPAIGN B', '3 sheets of 600 × 500', PLANS['B']),
        ('CAMPAIGN B, large sheet', '1 sheet of 900 × 1146 or more', PLANS_LARGE['B']),
        ('CAMPAIGN C', '2 sheets of 600 × 500', PLANS['C'])]


def plan_dir(order):
    for d in ('output', 'runs'):
        p = os.path.join(ROOT, d, order)
        if os.path.exists(os.path.join(p, 'preview.png')):
            return p
    raise SystemExit('no preview for order %s: run it first (make_plan.py)' % order)


def content(order, idx):
    """Counter alias -> number of pieces on sheet idx of the plan of an order."""
    with open(os.path.join(plan_dir(order), 'registry.csv'), encoding='utf-8') as f:
        return collections.Counter(r['alias'] for r in csv.DictReader(f) if int(r['sheet']) == idx + 1)


def preview(order, idx, n_sheets, tmp):
    """Path of the colour preview of sheet idx of an order (cut out of the preview when the plan has several
    sheets side by side, with the legend of the preview)."""
    path = os.path.join(plan_dir(order), 'preview.png')
    if n_sheets == 1:
        return path
    im = Image.open(path).convert('RGB')
    w, h = im.size
    cw = w // n_sheets
    sheet = im.crop((idx * cw, int(h * 0.065), (idx + 1) * cw, int(h * 0.935)))
    legend = im.crop((0, int(h * 0.935), cw + int(w * 0.03), h))
    out = Image.new('RGB', (max(sheet.size[0], legend.size[0]), sheet.size[1] + legend.size[1]), 'white')
    out.paste(sheet, (0, 0))
    out.paste(legend, (0, sheet.size[1]))
    p = os.path.join(tmp, '%s_%d.png' % (order, idx))
    out.save(p)
    return p


def usage():
    """id -> {'camps': [(campaign label, sheet label)], 'cut': [sheet ids of the materials], 'later': [...]}"""
    u = {PLAN_IDS[(q[0], q[1])]: {'camps': [], 'cut': [], 'later': []} for q in PLAN_LIST}
    for title, sub, plans in ROWS:
        for p in plans:
            u[pid(p)]['camps'].append((title.replace('CAMPAIGN ', ''), p[0]))
    for m in MATERIALS:
        name, mid, thk, camp, sheets, note, drawn = m
        nm = SHORT_NAME.get(name, name)
        if not drawn:
            for p in plans_of(m):
                u[pid(p)]['later'].append(nm)
            continue
        use, missing = assign(m)
        for i, put in use:
            for p in put:
                u[pid(p)]['cut'].append('%s (-%d)' % (nm, i + 1))
    return u


def footer(c, page):
    c.setFont(FONT, 7)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, 8 * mm, 'Mohr lab, ETH Zurich  ·  %s  ·  sizes RD × TD in mm' % DATE)
    c.drawRightString(PW - 15 * mm, 8 * mm, 'page %d' % page)


def page_matrix(c, u, counts):
    c.setFillColor(BLACK)
    c.setFont(BOLD, 16)
    c.drawString(15 * mm, PH - 18 * mm, 'CUTTING PLANS AND CAMPAIGNS')
    c.setFont(FONT, 8.5)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, PH - 24.5 * mm, '6 cutting plans. Each plan is one DXF, cut the same way on every sheet that '
                 'uses it: same specimens, same notch codes. A campaign = a set of plans.')
    c.drawString(15 * mm, PH - 29 * mm, 'The campaigns are nested (C inside B inside A), so they reuse the same plans: '
                 'P1 is in every campaign, P2 and P3 in A and B.')
    x0, lab, cw = 15 * mm, 64 * mm, 34.5 * mm
    xs = [x0 + lab + k * cw for k in range(len(PLAN_LIST))]
    # plan cards: outline drawn to scale, id, order, size, pieces
    yc = PH - 40 * mm
    s = 0.034 * mm                                             # 1:29 roughly
    for x, (order, idx, rd, td) in zip(xs, PLAN_LIST):
        i = PLAN_IDS[(order, idx)]
        w, h = td * s, rd * s
        c.setStrokeColor(BLACK)
        c.setLineWidth(0.9)
        c.rect(x + (cw - w) / 2 - 2 * mm, yc - 2 * mm - 31 * mm + (31 * mm - h), w, h, fill=0, stroke=1)
        c.setFillColor(BLACK)
        c.setFont(BOLD, 14)
        c.drawCentredString(x + cw / 2 - 2 * mm, yc - 2 * mm - 31 * mm + (31 * mm - h) + h / 2 - 2 * mm, i)
        c.setFont(BOLD, 7)
        n2 = sum(1 for q in PLAN_LIST if q[0] == order)
        c.drawCentredString(x + cw / 2 - 2 * mm, yc - 37.5 * mm, short(order) + (' (%d/%d)' % (idx + 1, n2)
                                                                                 if n2 > 1 else ''))
        c.setFont(FONT, 7)
        c.setFillColor(G_TEXT)
        c.drawCentredString(x + cw / 2 - 2 * mm, yc - 41 * mm, '%d × %d · %d pieces' % (rd, td, counts[i]))
    # rows: campaigns
    y = yc - 50 * mm
    rh = 13 * mm
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.8)
    c.line(x0, y + 3 * mm, xs[-1] + cw, y + 3 * mm)
    for title, sub, plans in ROWS:
        c.setFillColor(BLACK)
        c.setFont(BOLD, 10)
        c.drawString(x0, y - 4 * mm, title)
        c.setFont(FONT, 7.5)
        c.setFillColor(G_TEXT)
        c.drawString(x0, y - 8 * mm, sub + ': ' + ' + '.join(pid(p) for p in plans))
        used = {pid(p): p[0] for p in plans}
        for x, q in zip(xs, PLAN_LIST):
            i = PLAN_IDS[(q[0], q[1])]
            cx, cy = x + cw / 2 - 2 * mm, y - 5.5 * mm
            if i in used:
                c.setStrokeColor(BLACK)
                c.setLineWidth(1.1)
                c.circle(cx, cy + 1 * mm, 4.2 * mm, fill=0, stroke=1)
                c.setFillColor(BLACK)
                c.setFont(BOLD, 9)
                c.drawCentredString(cx, cy, used[i].split()[1] if used[i].startswith('sheet ') else '1')
            else:
                c.setFillColor(G_LINE)
                c.setFont(FONT, 9)
                c.drawCentredString(cx, cy, '–')
        c.setStrokeColor(G_LINE)
        c.setLineWidth(0.4)
        c.line(x0, y - rh + 3 * mm, xs[-1] + cw, y - rh + 3 * mm)
        y -= rh
    # row: materials for which each plan is cut
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.8)
    c.line(x0, y + 3 * mm, xs[-1] + cw, y + 3 * mm)
    c.setFillColor(BLACK)
    c.setFont(BOLD, 10)
    c.drawString(x0, y - 4 * mm, 'CUT FOR (material, sheet)')
    c.setFont(FONT, 7.5)
    c.setFillColor(G_TEXT)
    c.drawString(x0, y - 8 * mm, 'the same plan on every sheet listed')
    for x, q in zip(xs, PLAN_LIST):
        i = PLAN_IDS[(q[0], q[1])]
        lines = u[i]['cut'] + ['%s (later)' % m for m in u[i]['later']]
        c.setFont(BOLD, 8.5)
        c.setFillColor(BLACK)
        c.drawString(x + 1 * mm, y - 4 * mm, '× %d' % len(u[i]['cut']) + (' (+%d later)' % len(u[i]['later'])
                                                                        if u[i]['later'] else ''))
        c.setFont(FONT, 6.8)
        c.setFillColor(G_TEXT)
        for k, t in enumerate(lines):
            c.drawString(x + 1 * mm, y - 8 * mm - k * 3.3 * mm, t)
    # legend
    c.setFont(FONT, 7.5)
    c.setFillColor(G_TEXT)
    for k, t in enumerate(('Circle = the plan is in the campaign; number = the sheet of the campaign it is '
                           '(order of cutting). Index of the notch code = strain rate: slow 1-3, medium 4-6, high 7-9 '
                           '(shear 1-2, 4-5, 7-8).',
                           'P6 = P1 + P2 + P3 on one large sheet (the same 190 pieces and codes); the 600 × 500 plans '
                           'stay for the 600 × 500 sheets. Orders in cutting-sheets/orders/<order>.yaml.')):
        c.drawString(x0, 17 * mm - k * 4.2 * mm, t)


def page_plan(c, i, q, u, cnt, tmp):
    order, idx, rd, td = q
    n2 = sum(1 for r in PLAN_LIST if r[0] == order)
    c.setFillColor(BLACK)
    c.setFont(BOLD, 16)
    c.drawString(15 * mm, PH - 17 * mm, '%s  ·  %s' % (i, order) + ('  (sheet %d of %d)' % (idx + 1, n2) if n2 > 1
                                                                      else ''))
    c.setFont(FONT, 8.5)
    c.setFillColor(BLACK)
    c.drawString(15 * mm, PH - 23.5 * mm, '%d (RD) × %d (TD) mm  ·  %d pieces  ·  used in: %s' % (
        rd, td, sum(cnt.values()), ', '.join('campaign %s: %s' % (a, b) for a, b in u['camps'])))
    c.setFillColor(G_TEXT)
    cut = u['cut'] + ['%s (later)' % m for m in u['later']]
    c.drawString(15 * mm, PH - 28 * mm, 'cut for: ' + ', '.join(cut) + '  (%d sheet%s)' % (
        len(u['cut']), '' if len(u['cut']) == 1 else 's'))
    order_alias = ['UT40', 'UT19', 'NT20', 'NT06', 'CHD48', 'MNAK_RECT_FULL', 'MNAK_RECT_HOLE', 'SHLD', 'SHMD',
                   'SHHD', 'LASER']
    c.drawString(15 * mm, PH - 32.5 * mm, 'content: ' + ', '.join(
        '%s %d' % (a, cnt[a]) for a in order_alias + sorted(set(cnt) - set(order_alias)) if cnt.get(a)))
    img = preview(order, idx, n2, tmp)
    iw, ih = Image.open(img).size
    bw, bh = PW - 30 * mm, PH - 50 * mm
    sc = min(bw / iw, bh / ih)
    c.drawImage(ImageReader(img), (PW - iw * sc) / 2, 14 * mm + (bh - ih * sc) / 2, iw * sc, ih * sc)


OUT = sys.argv[1]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
u = usage()
counts, cnts = {}, {}
for q in PLAN_LIST:
    i = PLAN_IDS[(q[0], q[1])]
    cnts[i] = content(q[0], q[1])
    counts[i] = sum(cnts[i].values())
cv = canvas.Canvas(OUT, pagesize=landscape(A4))
cv.setTitle('Cutting plans and campaigns')
cv.setAuthor('Mohr lab, ETH Zurich')
page_matrix(cv, u, counts)
footer(cv, 1)
cv.showPage()
with tempfile.TemporaryDirectory() as tmp:
    for k, q in enumerate(PLAN_LIST, 2):
        i = PLAN_IDS[(q[0], q[1])]
        page_plan(cv, i, q, u[i], cnts[i], tmp)
        footer(cv, k)
        cv.showPage()
    cv.save()
print('written %s (%d pages)' % (OUT, len(PLAN_LIST) + 1))
