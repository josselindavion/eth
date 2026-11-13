# -*- coding: utf-8 -*-
"""
make_module_templates_pdf.py -- PDF of every template (one sheet of a module; modular strategy, user 12/11/2026):
page 1 = list of the templates (module, content, pieces, materials that use it); then one page per template with its
name, its content (strain rate, specimen type, angles, number, notch-code index; a module on 2 sheets, SLOW78 and
SLOW70, on one page) and the cutting plan in colour
(preview of the plan, EDM quality colours).

    py cutting-sheets/scripts/make_module_templates_pdf.py cutting-sheets/campaigns/module_templates.pdf

Previews and registries from runs/MOD_<NAME>_<size>mm_WATERJET/ (run the module orders first, make_module_orders.py).
"""
import collections
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
from make_module_orders import LARGE, MODULES                        # noqa: E402
from materials_data import MATERIALS, MODULE_ORDERS, assign, base_tid, dxf_name, pieces, plan_dir, templates   # noqa: E402

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
G_ROW = colors.Color(0.85, 0.85, 0.85)
G_HEAD = colors.Color(0.20, 0.20, 0.20)
PW, PH = landscape(A4)
DATE = '13/11/2026'
ALL = dict(list(MODULES.items()) + list(LARGE.items()))
ORDER_ALIAS = ['UT40', 'UT19', 'NT20', 'NT06', 'CHD48', 'MNAK_RECT_FULL', 'MNAK_RECT_HOLE', 'SHLD', 'SHMD', 'SHHD',
               'LASER']
RATE = {i: 'slow' for i in (1, 2, 3)}
RATE.update({i: 'medium' for i in (4, 5, 6)})
RATE.update({i: 'high' for i in (7, 8, 9)})


def preview(order, idx, n, tmp):
    """Colour preview of sheet idx of a plan (cut out of the preview when it has n > 1 sheets side by side)."""
    path = os.path.join(plan_dir(order), 'preview.png')
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
    p = os.path.join(tmp, '%s_%d.png' % (order, idx))
    out.save(p)
    return p


def content(rows):
    """[(rate, alias, angles, count per angle or None, total, indices)] of the pieces of a template."""
    g = collections.OrderedDict()
    for r in rows:
        rate = RATE.get(int(r['index']), '–') if r['index'] else '–'
        g.setdefault((rate, r['alias']), []).append(r)
    out = []
    for rate in ('slow', 'medium', 'high', '–'):
        for a in ORDER_ALIAS + sorted({k[1] for k in g} - set(ORDER_ALIAS)):
            rr = g.get((rate, a))
            if not rr:
                continue
            per = collections.Counter(int(float(r['angle_deg'])) for r in rr)
            idx = sorted({int(r['index']) for r in rr if r['index']})
            out.append((rate, a, per, len(rr), idx))
    return out


def users():
    """template id -> ['material (sheet)']"""
    u = collections.defaultdict(list)
    for m in MATERIALS:
        use, missing = assign(m)
        for i, put in use:
            for p in put:
                u[base_tid(p[0])].append('%s %s-%d' % ({'CR1200Y1500T-MS-UNCOATED': 'CR1200Y1500T'}.get(m[0], m[0]),
                                                       m[1], i + 1) + (' (%s)' % p[0].split(' · ')[1]
                                                                       if ' · ' in p[0] else ''))
    return u


def footer(c, page):
    c.setFont(FONT, 7)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, 8 * mm, 'Mohr lab, ETH Zurich  ·  %s  ·  sizes RD × TD in mm, waterjet' % DATE)
    c.drawRightString(PW - 15 * mm, 8 * mm, 'page %d' % page)


def page_list(c, tlist, u):
    c.setFillColor(BLACK)
    c.setFont(BOLD, 16)
    c.drawString(15 * mm, PH - 18 * mm, 'TEMPLATES')
    c.setFont(FONT, 8.5)
    c.setFillColor(G_TEXT)
    c.drawString(15 * mm, PH - 24.5 * mm, 'A module = the specimens of one campaign at one strain rate; a template = one '
                 'sheet of a module, always cut the same way (one DXF sheet).')
    c.drawString(15 * mm, PH - 29 * mm, 'Index of the notch code = strain rate: slow 1-3, medium 4-6, high 7-9 (shear '
                 '1-2, 4-5, 7-8). UT40 at every rate since 12/11/2026.')
    c.drawString(15 * mm, PH - 33.5 * mm, 'MEDHIGH = one template for medium and high (cut twice, codes 4-6 on both); '
                 'MH18 = medium + high of campaign C on one sheet (codes 4-6 and 7-9).')
    cols = [15, 46, 132, 152, 168]
    y = PH - 44 * mm
    c.setFillColor(G_HEAD)
    c.rect(15 * mm, y - 2 * mm, PW - 30 * mm, 6.5 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(BOLD, 7.5)
    for x, t in zip(cols, ('TEMPLATE', 'MODULE CONTENT', 'SIZE', 'PIECES', 'USED FOR (material, sheet)')):
        c.drawString(x * mm, y, t)
    y -= 8 * mm
    for t in tlist:
        tid, order, idx, rd, td, mod = t
        c.setFillColor(BLACK)
        c.setFont(BOLD, 10)
        c.drawString(cols[0] * mm, y, tid)
        c.setFont(FONT, 7.8)
        c.drawString(cols[1] * mm, y, ALL[mod][0].split(' (')[0] + (' (sheet %d of %d)' % (idx + 1, len(templates(mod)))
                                                     if len(templates(mod)) > 1 else ''))
        c.drawString(cols[2] * mm, y, '%d × %d' % (rd, td))
        c.setFont(BOLD, 9)
        c.drawString(cols[3] * mm, y, '%d' % len(pieces(order, idx)))
        c.setFont(FONT, 7)
        c.setFillColor(G_TEXT if u.get(tid) else G_ROW)
        txt = u.get(tid) or ['not used yet']
        for k in range(0, len(txt), 2):
            c.drawString(cols[4] * mm, y - (k // 2) * 3.2 * mm, ', '.join(txt[k:k + 2]))
        nl = max(1, (len(txt) + 1) // 2)
        c.setStrokeColor(G_ROW)
        c.setLineWidth(0.3)
        c.line(15 * mm, y - 2.6 * mm - (nl - 1) * 3.2 * mm, PW - 15 * mm, y - 2.6 * mm - (nl - 1) * 3.2 * mm)
        y -= 7.5 * mm + (nl - 1) * 3.2 * mm
    c.setFont(FONT, 8)
    c.setFillColor(BLACK)
    used = [t for t in tlist if u.get(t[0])]
    c.drawString(15 * mm, y - 4 * mm, '%d templates in all (%d modules); %d of them used by the materials today.' % (
        len(tlist), len({t[5] for t in tlist}), len(used)))


def page_module(c, mod, u, tmp):
    """One page per module: a module on 2 sheets (SLOW78, SLOW70) shows its 2 templates on the same page."""
    ts = templates(mod)
    tid, order, idx, rd, td, mod = ts[0]
    n = len(ts)
    rows = [r for t in ts for r in pieces(t[1], t[2])]
    c.setFillColor(BLACK)
    c.setFont(BOLD, 18)
    c.drawString(15 * mm, PH - 18 * mm, mod if n > 1 else tid)
    c.setFont(FONT, 9)
    title = ALL[mod][0]
    if n > 1:
        sub = '%s  ·  %d sheets of %d (RD) × %d (TD) mm: %s  ·  %d pieces' % (
            title, n, rd, td, ' + '.join('%s (%d pieces)' % (t[0], len(pieces(t[1], t[2]))) for t in ts), len(rows))
        used = '; '.join('%s: %s' % (t[0], ', '.join(u.get(t[0], [])) or 'not used yet') for t in ts)
    else:
        sub = '%s  ·  %d (RD) × %d (TD) mm  ·  %d pieces' % (title, rd, td, len(rows))
        used = ', '.join(u.get(tid, [])) or 'not used yet'
    c.drawString(15 * mm, PH - 24.5 * mm, sub)
    c.setFillColor(G_TEXT)
    c.setFont(FONT, 8)
    parts = ('used for: ' + used).split(', ')
    lines = [', '.join(parts[k:k + 3]) for k in range(0, len(parts), 3)]
    lines = [t + (',' if k < len(lines) - 1 else '') for k, t in enumerate(lines)]
    lines[-1] += '  ·  DXF: %s' % ', '.join(dxf_name(t) for t in ts)
    for k, t in enumerate(lines):
        c.drawString(15 * mm, PH - 29.5 * mm - k * 3.8 * mm, t)
    # content table (left)
    x0, y = 15 * mm, PH - 40 * mm - (len(lines) - 1) * 3.8 * mm
    cols = [0, 13, 42, 70, 80]
    c.setFont(BOLD, 7)
    c.setFillColor(BLACK)
    for x, h in zip(cols[:3] + [67], ('RATE', 'TYPE', 'ANGLES (deg)', 'EACH')):
        c.drawString(x0 + x * mm, y, h)
    c.drawRightString(x0 + 85 * mm, y, 'TOTAL')
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.6)
    c.line(x0, y - 1.5 * mm, x0 + 86 * mm, y - 1.5 * mm)
    y -= 5 * mm
    last = None
    for rate, a, per, tot, idxs in content(rows):
        if last is not None and rate != last:
            c.setStrokeColor(BLACK)
            c.setLineWidth(0.4)
            c.line(x0, y + 3.3 * mm, x0 + 86 * mm, y + 3.3 * mm)
        c.setFont(BOLD if rate != last else FONT, 7.5)
        c.setFillColor(BLACK if rate != last else colors.white)
        c.drawString(x0 + cols[0] * mm, y, rate if rate != '–' else 'no code')
        last = rate
        c.setFillColor(BLACK)
        c.setFont(BOLD, 7.0)
        c.drawString(x0 + cols[1] * mm, y, a)
        each = sorted(set(per.values()), reverse=True)
        if len(each) == 1:
            c.setFont(FONT, 7.5)
            c.drawString(x0 + cols[2] * mm, y, ' '.join(str(v) for v in sorted(per)))
            c.drawString(x0 + cols[3] * mm, y, '× %d' % each[0])
        else:                                                # a module on 2 sheets: number per angle varies
            c.setFont(FONT, 6.6)
            c.drawString(x0 + cols[2] * mm, y, '   '.join('×%d: %s' % (e, ' '.join(str(v) for v in sorted(per)
                                                                              if per[v] == e)) for e in each))
        c.setFont(BOLD, 8)
        c.drawRightString(x0 + 85 * mm, y, '%d' % tot)
        c.setStrokeColor(G_ROW)
        c.setLineWidth(0.3)
        c.line(x0, y - 1.5 * mm, x0 + 86 * mm, y - 1.5 * mm)
        y -= 4.6 * mm
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.8)
    c.line(x0, y + 3 * mm, x0 + 86 * mm, y + 3 * mm)
    c.setFont(BOLD, 9)
    c.drawString(x0, y - 1 * mm, 'Total')
    c.drawRightString(x0 + 85 * mm, y - 1 * mm, '%d' % len(rows))
    c.setFont(FONT, 6.8)
    c.setFillColor(G_TEXT)
    c.drawString(x0, y - 6 * mm, 'Notch code index: slow 1-3, medium 4-6, high 7-9')
    c.drawString(x0, y - 9.3 * mm, '(shear 1-2, 4-5, 7-8); LASER: no code.')
    c.setFont(BOLD, 7.5)
    c.setFillColor(BLACK)
    c.drawString(x0, y - 22 * mm, 'Rolling direction (RD): vertical on the plan (arrow),')
    c.drawString(x0, y - 25.5 * mm, 'along the %d mm side; angles measured from RD.' % rd)
    c.setFont(FONT, 6.8)
    c.setFillColor(G_TEXT)
    if n > 1:
        c.drawString(x0, y - 12.6 * mm, 'Whole module (both sheets); plan: sheet 1 on the left,')
        c.drawString(x0, y - 15.9 * mm, 'sheet 2 on the right.')
    # preview (right)
    img = preview(order, 0, 1, tmp)            # whole preview: both sheets of a 2-sheet module
    iw, ih = Image.open(img).size
    bx, bw, bh = 106 * mm, PW - 106 * mm - 8 * mm, PH - 47 * mm - (len(lines) - 1) * 3.8 * mm
    sc = min(bw / iw, bh / ih)
    c.drawImage(ImageReader(img), bx + (bw - iw * sc) / 2, 14 * mm + (bh - ih * sc), iw * sc, ih * sc)


OUT = sys.argv[1]
os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
tlist = [t for mod in ALL for t in templates(mod) if mod in MODULE_ORDERS]
u = users()
cv = canvas.Canvas(OUT, pagesize=landscape(A4))
cv.setTitle('Templates')
cv.setAuthor('Mohr lab, ETH Zurich')
page_list(cv, tlist, u)
footer(cv, 1)
cv.showPage()
with tempfile.TemporaryDirectory() as tmp:
    mods = [m for m in ALL if m in MODULE_ORDERS]
    for k, m in enumerate(mods, 2):
        page_module(cv, m, u, tmp)
        footer(cv, k)
        cv.showPage()
    cv.save()
print('written %s (%d pages, %d templates)' % (OUT, len(mods) + 1, len(tlist)))
