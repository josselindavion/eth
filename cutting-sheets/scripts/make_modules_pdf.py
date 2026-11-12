# -*- coding: utf-8 -*-
"""
make_modules_pdf.py -- PDF of the modules (modular strategy, user 12/11/2026): page 1 = the modules (campaign, rate,
content, sheets) and the campaigns as combinations of modules; then one page per sheet of each module with its colour
preview (runs/MOD_<NAME>_600x500mm_WATERJET/preview.png; run the module orders first).

    py cutting-sheets/scripts/make_modules_pdf.py cutting-sheets/campaigns/modules.pdf

Sober page: black and greys; the previews keep their colours (EDM quality).
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
from make_module_orders import MODULES   # noqa: E402

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
G_LINE = colors.Color(0.80, 0.80, 0.80)
G_HEAD = colors.Color(0.20, 0.20, 0.20)
PW, PH = landscape(A4)
DATE = '12/11/2026'
CAMPAIGNS = [('A', ['SLOW78', 'MEDIUM66', 'HIGH66']), ('B', ['SLOW70', 'MEDIUM54', 'HIGH54']),
             ('C', ['SLOW70', 'MH18'])]
ALIAS_ORDER = ['UT40', 'UT19', 'NT20', 'NT06', 'CHD48', 'MNAK_RECT_FULL', 'MNAK_RECT_HOLE', 'SHLD', 'SHMD', 'SHHD',
               'LASER']


def run_dir(name):
    return os.path.join(ROOT, 'runs', 'MOD_%s_600x500mm_WATERJET' % name)


def registry(name):
    with open(os.path.join(run_dir(name), 'registry.csv'), encoding='utf-8') as f:
        return list(csv.DictReader(f))


def preview(name, idx, n, tmp):
    """Colour preview of sheet idx of a module (cut out of the preview when it has n > 1 sheets side by side)."""
    path = os.path.join(run_dir(name), 'preview.png')
    if n == 1:
        return path
    im = Image.open(path).convert('RGB')
    w, h = im.size
    cw = w // n
    sheet = im.crop((idx * cw, int(h * 0.065), (idx + 1) * cw, int(h * 0.935)))
    legend = im.crop((0, int(h * 0.935), cw + int(w * 0.03), h))
    out = Image.new('RGB', (max(sheet.size[0], legend.size[0]), sheet.size[1] + legend.size[1]), 'white')
    out.paste(sheet, (0, 0))
    out.paste(legend, (0, sheet.size[1]))
    p = os.path.join(tmp, '%s_%d.png' % (name, idx))
    out.save(p)
    return p


def fmt(cnt):
    return ', '.join('%s %d' % (a, cnt[a]) for a in ALIAS_ORDER + sorted(set(cnt) - set(ALIAS_ORDER)) if cnt.get(a))


def footer(c, page):
    c.setFont(FONT, 7)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, 8 * mm, 'Mohr lab, ETH Zurich  ·  %s  ·  modules on sheets of 600 (RD) × 500 (TD) mm, '
                 'waterjet' % DATE)
    c.drawRightString(PW - 15 * mm, 8 * mm, 'page %d' % page)


def page_overview(c, info):
    c.setFillColor(BLACK)
    c.setFont(BOLD, 16)
    c.drawString(15 * mm, PH - 18 * mm, 'MODULES')
    c.setFont(FONT, 8.5)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, PH - 24.5 * mm, 'A module = the specimens of one campaign at one strain rate, cut on its own '
                 'sheet(s), the same plan every time. A material gets a combination of modules.')
    c.drawString(15 * mm, PH - 29 * mm, 'Medium and high rate are separate modules (codes 4-6 / 7-9, UT40 / UT19); '
                 'MH18 = medium 18 + high 18 of campaign C on one sheet, a module of its own.')
    cols = [15, 40, 108, 133, 150]
    y = PH - 42 * mm
    c.setFillColor(G_HEAD)
    c.rect(15 * mm, y - 2 * mm, PW - 30 * mm, 6.5 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(BOLD, 7.5)
    for x, t in zip(cols, ('MODULE', 'CONTENT', 'SPECIMENS', 'SHEETS', 'DETAIL (type and number)')):
        c.drawString(x * mm, y, t)
    y -= 8 * mm
    for name, (title, rows, n_laser, n) in MODULES.items():
        reg, ns = info[name]
        cnt = collections.Counter(r['alias'] for r in reg)
        c.setFillColor(BLACK)
        c.setFont(BOLD, 10)
        c.drawString(cols[0] * mm, y, name)
        c.setFont(FONT, 8)
        c.drawString(cols[1] * mm, y, title)
        c.drawString(cols[2] * mm, y, '%d' % n + (' + %d LASER' % n_laser if n_laser else ''))
        c.setFont(BOLD, 10)
        c.drawString(cols[3] * mm, y, '%d' % ns)
        c.setFont(FONT, 6.1)
        c.setFillColor(G_TEXT)
        c.drawString(cols[4] * mm, y, fmt(cnt))
        c.setStrokeColor(G_LINE)
        c.setLineWidth(0.3)
        c.line(15 * mm, y - 2.6 * mm, PW - 15 * mm, y - 2.6 * mm)
        y -= 8 * mm
    y -= 8 * mm
    c.setFillColor(BLACK)
    c.setFont(BOLD, 11)
    c.drawString(15 * mm, y, 'CAMPAIGNS = COMBINATIONS OF MODULES')
    y -= 8 * mm
    for camp, mods in CAMPAIGNS:
        total = sum(info[m][1] for m in mods)
        c.setFont(BOLD, 10)
        c.setFillColor(BLACK)
        c.drawString(15 * mm, y, 'Campaign %s' % camp)
        x = 50 * mm
        k = 1
        for m in mods:                                     # one box per sheet, labelled with the module
            for s in range(info[m][1]):
                c.setStrokeColor(BLACK)
                c.setLineWidth(0.8)
                c.rect(x, y - 3 * mm, 30 * mm, 8 * mm, fill=0, stroke=1)
                c.setFont(BOLD, 7.5)
                c.drawCentredString(x + 15 * mm, y + 1.6 * mm, m + (' (%d/%d)' % (s + 1, info[m][1])
                                                                   if info[m][1] > 1 else ''))
                c.setFont(FONT, 6.5)
                c.setFillColor(G_TEXT)
                c.drawCentredString(x + 15 * mm, y - 1.6 * mm, 'sheet %d' % k)
                c.setFillColor(BLACK)
                x += 33 * mm
                k += 1
        c.setFont(FONT, 8)
        c.setFillColor(G_TEXT)
        c.drawString(x + 3 * mm, y, '= %d sheets' % total)
        y -= 12 * mm
    c.setFont(FONT, 7.5)
    c.setFillColor(G_TEXT)
    for k, t in enumerate(('Index of the notch code = strain rate: slow 1-3, medium 4-6, high 7-9 (shear 1-2, 4-5, 7-8). '
                           'SLOW70 is the same module for B and C.',
                           'LASER: 4 per material, on the slow module (to confirm). Orders: '
                           'cutting-sheets/orders/modules/MOD_<MODULE>_600x500mm_WATERJET.yaml.')):
        c.drawString(15 * mm, 17 * mm - k * 4.2 * mm, t)


def page_sheet(c, name, idx, info, tmp):
    title, rows, n_laser, n = MODULES[name]
    reg, ns = info[name]
    cnt = collections.Counter(r['alias'] for r in reg if int(r['sheet']) == idx + 1)
    c.setFillColor(BLACK)
    c.setFont(BOLD, 16)
    c.drawString(15 * mm, PH - 17 * mm, 'MODULE %s' % name + ('  ·  sheet %d of %d' % (idx + 1, ns) if ns > 1 else ''))
    c.setFont(FONT, 8.5)
    c.drawString(15 * mm, PH - 23.5 * mm, '%s  ·  %d specimens%s on %d sheet%s  ·  this sheet: %d pieces' % (
        title, n, ' + %d LASER' % n_laser if n_laser else '', ns, '' if ns == 1 else 's', sum(cnt.values())))
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, PH - 28 * mm, 'this sheet: ' + fmt(cnt))
    used = [camp for camp, mods in CAMPAIGNS if name in mods]
    c.drawString(15 * mm, PH - 32.5 * mm, 'used in campaign %s  ·  order MOD_%s_600x500mm_WATERJET' % (
        ' and '.join(used), name))
    img = preview(name, idx, ns, tmp)
    iw, ih = Image.open(img).size
    bw, bh = PW - 30 * mm, PH - 50 * mm
    sc = min(bw / iw, bh / ih)
    c.drawImage(ImageReader(img), (PW - iw * sc) / 2, 14 * mm + (bh - ih * sc) / 2, iw * sc, ih * sc)


OUT = sys.argv[1]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
info = {}
for name in MODULES:
    reg = registry(name)
    info[name] = (reg, max(int(r['sheet']) for r in reg))
cv = canvas.Canvas(OUT, pagesize=landscape(A4))
cv.setTitle('Modules')
cv.setAuthor('Mohr lab, ETH Zurich')
page_overview(cv, info)
footer(cv, 1)
cv.showPage()
page = 2
with tempfile.TemporaryDirectory() as tmp:
    for name in MODULES:
        for idx in range(info[name][1]):
            page_sheet(cv, name, idx, info, tmp)
            footer(cv, page)
            cv.showPage()
            page += 1
    cv.save()
print('written %s (%d pages)' % (OUT, page - 1))
