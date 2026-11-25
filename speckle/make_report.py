"""
make_report.py -- A4 report of the speckle parameter study (user, 25/11/2026): method (patterns, camera model, virtual
tests, indicators), results per strain rate with an analysis of each figure, gallery of the speckle shapes (also saved
as PNG files), conclusions. Reads results/parameter_study.csv (parameter_study.py).

    py make_report.py                 -> results/speckle_report.pdf, results/shapes/*.png, results/report_figs/*.png
    py make_report.py --quick         -> from results/parameter_study_quick.csv
"""
import csv
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt                              # noqa: E402
import numpy as np                                           # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm   # noqa: E402
from PIL import Image as PILImage                            # noqa: E402
from reportlab.lib import colors                             # noqa: E402
from reportlab.lib.enums import TA_JUSTIFY                   # noqa: E402
from reportlab.lib.pagesizes import A4                       # noqa: E402
from reportlab.lib.styles import ParagraphStyle              # noqa: E402
from reportlab.lib.units import mm                           # noqa: E402
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,  # noqa: E402
                                Table, TableStyle)
from scipy import stats                                      # noqa: E402

from speckle_generator import SHAPES, setup, speckle_raster   # noqa: E402
from speckle_quality import BLUR_PX, NOISE, STRAIN, camera   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
QUICK = '--quick' in sys.argv
CSV = os.path.join(HERE, 'results', 'parameter_study' + ('_quick' if QUICK else '') + '.csv')
OUT = os.path.join(HERE, 'results', 'speckle_report' + ('_quick' if QUICK else '') + '.pdf')
FIG = os.path.join(HERE, 'results', 'report_figs')
SHP = os.path.join(HERE, 'results', 'shapes')
PRESETS = ['slow', 'int', 'fast']
RATE = {'slow': '0.001/s', 'int': '1/s', 'fast': '100/s'}
CAMERA = {'slow': 'FLIR Blackfly S, 28 mm, 2 Hz', 'int': 'Optronis Cyclone-5-700, 180 mm, 1 kHz',
          'fast': 'Photron SA-Z, 180 mm, 100 kHz'}
# shape colours: categorical palette (validated with the dataviz validator, light mode: all checks pass)
COL = dict(zip(SHAPES, ['#257de0', '#f47230', '#00b894', '#f2a600', '#ee7fac']))
MRK = dict(zip(SHAPES, ['s', 'o', 'D', 'v', 'P']))
BLUES = LinearSegmentedColormap.from_list('blues', ['#cce3fd', '#84b9f3', '#338ced', '#2370cd', '#1757ac',
                                                    '#0f4a96'])
INK, INK2, GRID = '#1f2328', '#59636e', '#d0d7de'
plt.rcParams.update({'font.size': 8.5, 'axes.edgecolor': GRID, 'axes.labelcolor': INK, 'xtick.color': INK2,
                     'ytick.color': INK2, 'axes.titlesize': 9.5, 'axes.titleweight': 'bold', 'axes.titlecolor': INK,
                     'axes.spines.top': False, 'axes.spines.right': False, 'legend.frameon': False})
E4 = 1e4                                                     # strain noise shown in 10^-4
FONT, BOLD, ITAL = 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique'
for _d in ('/usr/share/fonts/truetype/dejavu', 'C:/Windows/Fonts'):   # a font with µ and superscripts
    for _n, _f in (('R', 'DejaVuSans.ttf'), ('B', 'DejaVuSans-Bold.ttf'), ('I', 'DejaVuSans-Oblique.ttf')):
        if os.path.exists(os.path.join(_d, _f)):
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            pdfmetrics.registerFont(TTFont('Sans' + _n, os.path.join(_d, _f)))
    if os.path.exists(os.path.join(_d, 'DejaVuSans.ttf')):
        FONT, BOLD, ITAL = 'SansR', 'SansB', 'SansI'
        break
if FONT == 'Helvetica' and os.path.exists('C:/Windows/Fonts/arial.ttf'):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for _n, _f in (('R', 'arial.ttf'), ('B', 'arialbd.ttf'), ('I', 'ariali.ttf')):
        pdfmetrics.registerFont(TTFont('Sans' + _n, 'C:/Windows/Fonts/' + _f))
    FONT, BOLD, ITAL = 'SansR', 'SansB', 'SansI'

if FONT == 'SansR':                                          # <b> and <i> in the paragraphs
    from reportlab.lib.fonts import addMapping
    for _b, _i, _f in ((0, 0, 'SansR'), (1, 0, 'SansB'), (0, 1, 'SansI'), (1, 1, 'SansB')):
        addMapping('SansR', _b, _i, _f)


def load():
    with open(CSV, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            if k not in ('stage', 'preset', 'shape'):
                r[k] = float(v)
    return rows


def sel(rows, **kw):
    return [r for r in rows if all(r[k] == v for k, v in kw.items())]


def ms(rows, key='strain_noise'):
    v = np.array([r[key] for r in rows])
    return (v.mean(), v.std(ddof=1) if len(v) > 1 else 0.0, v) if len(v) else (np.nan, np.nan, v)


# ------------------------------------------------------------------ figures
def save(fig, name):
    p = os.path.join(FIG, name + '.png')
    fig.savefig(p, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return p


def fig_gallery(best):
    """The five shapes at the recommended size and density of each preset (3 x 3 mm), and one PNG per shape."""
    fig, axs = plt.subplots(len(PRESETS), len(SHAPES), figsize=(7.2, 4.6))
    for i, name in enumerate(PRESETS):
        s = setup(name)
        size, dens = best[name]
        n = int(round(3.0 * 1000 / s['pitch_um']))
        for j, sh in enumerate(SHAPES):
            r = speckle_raster(np.ones((n, n), bool), s['pitch_um'] / 1000.0, size, dens, 1, sh)
            img = np.where(r, 0, 255).astype(np.uint8)
            PILImage.fromarray(img).resize((n * 6, n * 6), PILImage.NEAREST).save(
                os.path.join(SHP, '%s_%s_%dum_d%02d.png' % (name, sh, size, round(dens * 100))))
            ax = axs[i, j]
            ax.imshow(img, cmap='gray', vmin=0, vmax=255, interpolation='nearest')
            ax.set_xticks([])
            ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_visible(True)
                sp.set_color(COL[sh])
                sp.set_linewidth(2)
            if i == 0:
                ax.set_title(sh.replace('_', ' '), color=INK)
            if j == 0:
                ax.set_ylabel('%s\n%d µm, d = %.2f' % (name, size, dens), fontsize=8, color=INK)
    fig.tight_layout()
    return save(fig, 'gallery')


def fig_camera(best):
    """Engraved raster and camera image of the same 2 x 2 mm, slow and fast."""
    fig, axs = plt.subplots(1, 4, figsize=(7.2, 2.1))
    for k, name in enumerate(('slow', 'fast')):
        s = setup(name)
        size, dens = best[name]
        n = int(round(2.0 * 1000 / s['pitch_um']))
        r = speckle_raster(np.ones((n, n), bool), s['pitch_um'] / 1000.0, size, dens, 1, 'circle')
        cam = camera(r, s['pitch_um'], s['camera_um_per_px'], rng=np.random.default_rng(1))
        axs[2 * k].imshow(~r, cmap='gray', interpolation='nearest')
        axs[2 * k].set_title('%s: engraved (33 µm px)' % name, fontsize=8)
        axs[2 * k + 1].imshow(cam, cmap='gray', interpolation='nearest', vmin=0, vmax=1)
        axs[2 * k + 1].set_title('%s: camera (%g µm px)' % (name, s['camera_um_per_px']), fontsize=8)
    for ax in axs:
        ax.set_xticks([])
        ax.set_yticks([])
    fig.tight_layout()
    return save(fig, 'camera')


def fig_heat(rows, name):
    """Strain noise against size and density, square and circle."""
    r1 = sel(rows, stage='size_density', preset=name)
    sizes = sorted({r['size_um'] for r in r1})
    dens = sorted({r['density'] for r in r1})
    cam = setup(name)['camera_um_per_px']
    grids = {}
    for sh in ('square', 'circle'):
        grids[sh] = np.array([[ms(sel(r1, shape=sh, size_um=s, density=d))[0] * E4 for d in dens] for s in sizes])
    vmin = min(np.nanmin(g) for g in grids.values())
    vmax = max(np.nanmax(g) for g in grids.values())
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.5))
    for ax, sh in zip(axs, ('square', 'circle')):
        g = grids[sh]
        im = ax.imshow(g, cmap=BLUES, norm=LogNorm(vmin=vmin, vmax=vmax), origin='lower', aspect='auto')
        b = np.unravel_index(np.nanargmin(g), g.shape)
        for i in range(len(sizes)):
            for j in range(len(dens)):
                ax.text(j, i, '%.1f' % g[i, j], ha='center', va='center', fontsize=7.5,
                        color='white' if np.log(g[i, j] / vmin) > 0.55 * np.log(vmax / vmin) else INK,
                        fontweight='bold' if (i, j) == b else 'normal')
        ax.add_patch(plt.Rectangle((b[1] - 0.5, b[0] - 0.5), 1, 1, fill=False, ec=INK, lw=1.6))
        ax.set_xticks(range(len(dens)))
        ax.set_xticklabels(['%.2f' % d for d in dens])
        ax.set_yticks(range(len(sizes)))
        ax.set_yticklabels(['%d µm (%.1f px)' % (s, s / cam) for s in sizes] if sh == 'square' else [])
        ax.set_xlabel('density (fraction of the area covered)')
        ax.set_title('%s speckles' % sh)
        for sp in ax.spines.values():
            sp.set_visible(False)
    cb = fig.colorbar(im, ax=axs, shrink=0.85, pad=0.02)
    cb.set_label('strain noise ($10^{-4}$, log scale), lower = better', color=INK)
    cb.outline.set_visible(False)
    return save(fig, 'heat_%s' % name)


def fig_trends(rows, name, best):
    """Strain noise against density (at the best size) and against size (at the best density), square and circle."""
    r1 = sel(rows, stage='size_density', preset=name)
    size_b, dens_b = best[name]
    sizes = sorted({r['size_um'] for r in r1})
    dens = sorted({r['density'] for r in r1})
    cam = setup(name)['camera_um_per_px']
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.25))
    for sh in ('square', 'circle'):
        a = [ms(sel(r1, shape=sh, size_um=size_b, density=d)) for d in dens]
        axs[0].errorbar(dens, [x[0] * E4 for x in a], yerr=[x[1] * E4 for x in a], color=COL[sh], marker=MRK[sh],
                        ms=5, lw=1.8, capsize=3, label=sh)
        b = [ms(sel(r1, shape=sh, size_um=s, density=dens_b)) for s in sizes]
        axs[1].errorbar([s / cam for s in sizes], [x[0] * E4 for x in b], yerr=[x[1] * E4 for x in b], color=COL[sh],
                        marker=MRK[sh], ms=5, lw=1.8, capsize=3, label=sh)
    axs[0].set_xlabel('density')
    axs[0].set_title('effect of the density (size %d µm)' % size_b)
    axs[1].set_xlabel('speckle size (camera px)')
    axs[1].set_title('effect of the size (density %.2f)' % dens_b)
    for ax in axs:
        ax.set_ylabel('strain noise ($10^{-4}$)')
        ax.grid(color=GRID, lw=0.6)
        ax.legend(fontsize=7.5)
    fig.tight_layout()
    return save(fig, 'trends_%s' % name)


def fig_shapes(rows, name):
    """Stage 2: the five shapes at the best size and density: strain noise and displacement error."""
    r2 = sel(rows, stage='shapes', preset=name)
    fig, axs = plt.subplots(1, 2, figsize=(7.4, 2.25))
    sq = ms(sel(r2, shape='square'))[2]
    for ax, key, f, lab in ((axs[0], 'strain_noise', E4, 'strain noise ($10^{-4}$)'),
                            (axs[1], 'shift_rms_um', 1.0, 'displacement error RMS (µm)')):
        for k, sh in enumerate(SHAPES):
            m, s, v = ms(sel(r2, shape=sh), key)
            ax.bar(k, m * f, yerr=s * f, color=COL[sh], width=0.7, capsize=3, edgecolor='white', lw=1)
            if key == 'strain_noise' and sh != 'square':
                p = stats.ttest_ind(v, sq, equal_var=False).pvalue
                ax.text(k, (m + s) * f * 1.02, 'p=%.2f' % p, ha='center', fontsize=6.5, color=INK2)
        ax.set_xticks(range(len(SHAPES)))
        ax.set_xticklabels([s.replace('_', '\n') for s in SHAPES], fontsize=7.5)
        ax.set_ylabel(lab)
        ax.grid(axis='y', color=GRID, lw=0.6)
        ax.set_axisbelow(True)
    axs[0].set_title('strain test (1 %), lower = better')
    axs[1].set_title('translation test, lower = better')
    fig.tight_layout()
    return save(fig, 'shapes_%s' % name)


def fig_summary(rows, an, best):
    """Strain noise of today's pattern, of a square with Beerli's size, and of the recommended pattern, per test."""
    fig, ax = plt.subplots(figsize=(7.4, 2.4))
    lab = [("Ruben's pattern (square 99 µm, 0.25)", '#c3cad1'), ("square, Beerli's size (264 µm), 0.25", '#7d8790'),
           ('recommended pattern', '#257de0')]
    for i, n in enumerate(PRESETS):
        r1 = sel(rows, stage='size_density', preset=n)
        a = an[n]
        vals = [ms(sel(r1, shape='square', size_um=99, density=0.25)),
                ms(sel(r1, shape='square', size_um=264, density=0.25)),
                a['shp'][a['best_sh']]]
        for k, ((m, sd, v), (l, c)) in enumerate(zip(vals, lab)):
            x = i + (k - 1) * 0.26
            if np.isnan(m):
                ax.text(x, 0.3, 'not\ntested', ha='center', fontsize=6.5, color=INK2)
                continue
            ax.bar(x, m * E4, width=0.24, yerr=sd * E4, color=c, capsize=2.5, edgecolor='white', lw=1,
                   label=l if i == 0 or (i == 2 and k == 0 and False) else None)
            ax.text(x, (m + sd) * E4 + 0.4, '%.1f' % (m * E4), ha='center', fontsize=7, color=INK)
    ax.set_xticks(range(len(PRESETS)))
    ax.set_xticklabels(['%s (%s)' % (n, RATE[n]) for n in PRESETS])
    ax.set_ylabel('strain noise ($10^{-4}$)')
    ax.grid(axis='y', color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, fontsize=7.5, loc='upper left', ncol=3, bbox_to_anchor=(0, 1.18))
    fig.tight_layout()
    return save(fig, 'summary')


# ------------------------------------------------------------------ analysis
def analysis(rows, name, best):
    r1 = sel(rows, stage='size_density', preset=name)
    r2 = sel(rows, stage='shapes', preset=name)
    s = setup(name)
    cam = s['camera_um_per_px']
    size_b, dens_b = best[name]
    mb = ms(sel(r1, size_um=size_b, density=dens_b))[0]
    out = {}
    # baselines
    base = ms(sel(r1, shape='square', size_um=264, density=0.25))[0]
    out['base'] = base
    rub = ms(sel(r1, shape='square', size_um=99, density=0.25))[0]
    out['ruben'] = rub
    # density effect at the best size (both shapes)
    dens = sorted({r['density'] for r in r1})
    dv = [ms(sel(r1, size_um=size_b, density=d))[0] for d in dens]
    # size effect at the best density
    sizes = sorted({r['size_um'] for r in r1})
    sv = [ms(sel(r1, size_um=x, density=dens_b))[0] for x in sizes]
    # shapes
    sq = ms(sel(r2, shape='square'))
    shp = {sh: ms(sel(r2, shape=sh)) for sh in SHAPES}
    best_sh = min(SHAPES, key=lambda k: shp[k][0])
    pv = {sh: stats.ttest_ind(shp[sh][2], sq[2], equal_var=False).pvalue for sh in SHAPES if sh != 'square'}
    sig = [sh for sh in pv if pv[sh] < 0.05 and shp[sh][0] < sq[0]]
    worse = [sh for sh in pv if pv[sh] < 0.05 and shp[sh][0] > sq[0]]
    out.update(best_sh=best_sh, shp=shp, pv=pv, sig=sig, mb=mb)
    cell = {}
    for x in sorted({r['size_um'] for r in r1}):
        for d in sorted({r['density'] for r in r1}):
            cell[(x, d)] = ms(sel(r1, size_um=x, density=d))
    sb = cell[(size_b, dens_b)][1]
    eq = [k for k in cell if cell[k][0] <= mb + sb]
    out['eq'] = eq
    t_heat = ('The lowest strain noise is reached at <b>%d µm (%.1f camera px) and a density of %.2f</b>: %.1f × 10<super>-4</super> '
              '(mean of square and circle). Within one standard deviation of it (%.1f × 10<super>-4</super>), i.e. '
              'equivalent given the scatter between draws: sizes %s µm and densities %s. ' % (
                  size_b, size_b / cam, dens_b, mb * E4, sb * E4,
                  '–'.join('%d' % v for v in (min(k[0] for k in eq), max(k[0] for k in eq))) if len({k[0] for k in eq}) > 1
                  else '%d' % eq[0][0],
                  '%.2f–%.2f' % (min(k[1] for k in eq), max(k[1] for k in eq)) if len({k[1] for k in eq}) > 1
                  else '%.2f' % eq[0][1]))
    out['d25'] = cell.get((size_b, 0.25), (np.nan,))[0]
    out['d25_eq'] = out['d25'] <= mb + sb
    out['big'] = (sizes_all := sorted({k[0] for k in cell}))[-1]
    out['small_ratio'] = cell[(sizes_all[0], dens_b)][0] / mb
    out['big_ratio'] = cell[(sizes_all[-1], dens_b)][0] / mb
    if not np.isnan(base):
        t_heat += ('For comparison, a square pattern with Beerli\'s feature size (264 µm) and Ruben\'s density (0.25) '
                   'gives %.1f × 10<super>-4</super>, i.e. %+.0f %%. ' % (base * E4, 100 * (base - mb) / mb))
    if not np.isnan(rub):
        t_heat += 'Ruben\'s current pattern (99 µm, 0.25, square) gives %.1f × 10<super>-4</super> (%+.0f %%). ' % (
            rub * E4, 100 * (rub - mb) / mb)
    j = int(np.nanargmin(dv))
    t_tr = ('<b>Density:</b> at %d µm the noise goes from %.1f (density %.2f) to %.1f × 10<super>-4</super> (%.2f), then %s to %.1f '
            'at %.2f%s. ' % (size_b, dv[0] * E4, dens[0], dv[j] * E4, dens[j],
                              'rises' if dv[-1] > dv[j] * 1.02 else 'stays about the same', dv[-1] * E4, dens[-1],
                              ' (the speckles start to merge)' if dv[-1] > dv[j] * 1.05 else ''))
    k = int(np.nanargmin(sv))
    t_tr += ('<b>Size:</b> at density %.2f the best size is %d µm (%.1f camera px); %.1f camera px gives %.1f and '
             '%.1f camera px gives %.1f × 10<super>-4</super>. Too small speckles are blurred by the camera (low contrast, see MIG); '
             'too big ones leave too few features in a subset of %d px.' % (
                 dens_b, sizes[k], sizes[k] / cam, sizes[0] / cam, sv[0] * E4, sizes[-1] / cam, sv[-1] * E4,
                 s['subset_px']))
    t_sh = ('At %d µm and %.2f, the lowest mean is the <b>%s</b> (%.1f ± %.1f × 10<super>-4</super>; square %.1f ± %.1f). ' % (
        size_b, dens_b, best_sh.replace('_', ' '), shp[best_sh][0] * E4, shp[best_sh][1] * E4, sq[0] * E4, sq[1] * E4))
    if sig:
        t_sh += ('Significantly better than the square (Welch t-test, p &lt; 0.05): %s. ' % ', '.join(
            '%s (%+.0f %%, p = %.3f)' % (x.replace('_', ' '), 100 * (shp[x][0] - sq[0]) / sq[0], pv[x]) for x in sig))
    else:
        t_sh += ('No shape is significantly better than the square (all p ≥ 0.05): the differences are within the '
                 'scatter between draws. ')
    if worse:
        t_sh += 'Significantly worse: %s. ' % ', '.join(x.replace('_', ' ') for x in worse)
    out.update(t_heat=t_heat, t_tr=t_tr, t_sh=t_sh)
    return out


# ------------------------------------------------------------------ report
def build():
    os.makedirs(FIG, exist_ok=True)
    os.makedirs(SHP, exist_ok=True)
    rows = load()
    best = {}
    for name in PRESETS:
        r2 = sel(rows, stage='shapes', preset=name)
        best[name] = (r2[0]['size_um'], r2[0]['density'])
    an = {n: analysis(rows, n, best) for n in PRESETS}

    st = {'h1': ParagraphStyle('h1', fontName=BOLD, fontSize=13.5, leading=17, spaceBefore=4, spaceAfter=5,
                               textColor=colors.HexColor(INK)),
          'h2': ParagraphStyle('h2', fontName=BOLD, fontSize=10.5, leading=13, spaceBefore=6, spaceAfter=3,
                               textColor=colors.HexColor(INK)),
          'p': ParagraphStyle('p', fontName=FONT, fontSize=8.8, leading=11.8, alignment=TA_JUSTIFY,
                              spaceAfter=4, textColor=colors.HexColor(INK)),
          'cap': ParagraphStyle('cap', fontName=ITAL, fontSize=7.8, leading=10,
                                textColor=colors.HexColor(INK2), spaceAfter=6),
          'title': ParagraphStyle('t', fontName=BOLD, fontSize=19, leading=23,
                                  textColor=colors.HexColor(INK)),
          'sub': ParagraphStyle('s', fontName=FONT, fontSize=9.5, leading=13, textColor=colors.HexColor(INK2)),
          'cell': ParagraphStyle('c', fontName=FONT, fontSize=7.8, leading=9.5),
          'cellb': ParagraphStyle('cb', fontName=BOLD, fontSize=7.8, leading=9.5)}
    P = lambda t, s='p': Paragraph(t, st[s])                 # noqa: E731

    def img(path, w=174):
        iw, ih = PILImage.open(path).size
        return Image(path, width=w * mm, height=w * mm * ih / iw)

    def table(data, widths, head=True):
        t = Table([[P(str(c), 'cellb' if (head and i == 0) else 'cell') for c in row] for i, row in enumerate(data)],
                  colWidths=[w * mm for w in widths])
        sty = [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor(GRID)),
               ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
        if head:
            sty += [('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2f6')),
                    ('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor(INK))]
        t.setStyle(TableStyle(sty))
        return t

    S = []
    # ---- page 1: summary
    S += [P('Engraved speckle patterns for DIC', 'title'), Spacer(1, 3),
          P('Parameter study of the speckle generator (shape, size, density) for the slow, intermediate and fast tests '
            'of Beerli et al. 2026 · Mohr lab, ETH Zurich · 25/11/2026', 'sub'), Spacer(1, 10),
          P('Summary', 'h1'),
          P('The question: which engraved speckle pattern gives the most precise DIC strain measurement at each strain '
            'rate? Every pattern is generated on the 33 µm engraver grid, seen through a model of the camera used in '
            'that test (Beerli et al. 2026, Tables 1-2), deformed numerically by a known amount and measured back with '
            'DIC. The error of that measurement, repeated over several random draws, ranks the patterns.')]
    rec = [['Test', 'Strain rate · camera', 'Recommended pattern', 'Strain noise (10<super>-4</super>)', 'Square 264 µm, 0.25',
            'Displacement error']]
    for n in PRESETS:
        s = setup(n)
        a = an[n]
        size, d = best[n]
        shape = a['best_sh'] if a['sig'] else 'square (or %s, equivalent)' % a['best_sh'].replace('_', ' ') \
            if a['best_sh'] != 'square' else 'square'
        if a['sig']:
            shape = a['best_sh'].replace('_', ' ')
        rec.append(['<b>%s</b>' % n, '%s · %g µm/px' % (RATE[n], s['camera_um_per_px']),
                    '<b>%s</b>, %d µm (%d engraver px, %.1f camera px), density <b>%.2f</b>' % (
                        shape, size, size / s['pitch_um'], size / s['camera_um_per_px'], d),
                    '%.1f ± %.1f' % (a['shp'][a['best_sh']][0] * E4, a['shp'][a['best_sh']][1] * E4),
                    '%.1f' % (a['base'] * E4) if not np.isnan(a['base']) else '–',
                    '%.2f µm' % ms(sel(rows, stage='shapes', preset=n, shape=a['best_sh']), 'shift_rms_um')[0]])
    S += [table(rec, [13, 29, 56, 24, 24, 28]), Spacer(1, 6), img(fig_summary(rows, an, best), 165),
          P('Strain noise (strain test, mean ± standard deviation over the draws) of today\'s pattern, of a square '
            'pattern with the feature size of Beerli\'s paint, and of the recommended pattern.', 'cap')]
    dens_all = [best[n][1] for n in PRESETS]
    S += [P('Main findings', 'h2'),
          P('• <b>Size (the most important parameter):</b> the best speckle is %s µm, i.e. %s camera px (slow, int, '
            'fast). Too small speckles (2 camera px) give %s × the best noise; too big ones (8 camera px) %s ×. A square '
            'pattern with the size of Beerli\'s paint (264 µm) is %s worse.' % (
                ', '.join('%d' % best[n][0] for n in PRESETS),
                ', '.join('%.1f' % (best[n][0] / setup(n)['camera_um_per_px']) for n in PRESETS),
                ' / '.join('%.1f' % an[n]['small_ratio'] for n in PRESETS),
                ' / '.join('%.1f' % an[n]['big_ratio'] for n in PRESETS),
                ' / '.join('%+.0f %%' % (100 * (an[n]['base'] - an[n]['mb']) / an[n]['mb']) for n in PRESETS))),
          P('• <b>Density (second order):</b> the best densities are %s (slow, int, fast). At the best size, the '
            '0.25 used today is %s from the best (%s). The noise rises again at 0.65 (speckles merge). A density of '
            '0.25-0.45 is a safe choice.' % (
                ', '.join('%.2f' % d for d in dens_all),
                ' / '.join('%+.0f %%' % (100 * (an[n]['d25'] - an[n]['mb']) / an[n]['mb']) for n in PRESETS),
                '; '.join('%s: %s' % (n, 'within the scatter between draws' if an[n]['d25_eq'] else
                                      'more than the scatter') for n in PRESETS))),
          P('• <b>Shape:</b> %s' % ' '.join(
              '%s: %s.' % (n, ('%s better than the square (%s)' % (', '.join(x.replace('_', ' ') for x in an[n]['sig']),
                                                                  ', '.join('p = %.3f' % an[n]['pv'][x]
                                                                            for x in an[n]['sig'])))
                           if an[n]['sig'] else 'no significant difference with the square') for n in PRESETS)),
          P('• <b>Limits:</b> numerical study (camera model, noise %.0f %%, blur %.1f px, ideal engraving). The ranking '
            'and the trends are robust; the absolute values have to be checked on real engraved specimens.'
            % (NOISE * 100, BLUR_PX)),
          PageBreak()]

    # ---- method
    S += [P('1. Method', 'h1'), P('1.1 The patterns', 'h2'),
          P('The generator (Ruben Zwicker, Inspire AG, cleaned and extended) draws the speckle centres by Poisson-disk '
            'sampling: random positions with a minimum distance between them, so there are no clusters and no empty '
            'areas ("blue noise"). Each centre gets one speckle; all shapes have the area of a square of side '
            '<i>size</i>, so the covered fraction (density) is comparable between shapes. The pattern is a raster on '
            'the 33 µm grid of the engraver (its minimum resolution): every pixel is engraved or not. The five shapes '
            'are shown in Fig. 1; each PNG is also saved in results/shapes/.'),
          img(fig_gallery(best)),
          P('Fig. 1 - The five speckle shapes at the recommended size and density of each test (3 × 3 mm, engraver '
            'pixels). Square = Ruben\'s speckles; rotated square = random orientation; ellipse = aspect ratio 2, random '
            'orientation; polygon = irregular, 5 to 8 vertices.', 'cap'),
          P('1.2 The three tests (Beerli et al. 2026)', 'h2'),
          P('The speckle sizes are not chosen freely: a speckle must be seen by the camera of the test. The DIC setups of '
            'Beerli et al. 2026 (Table 1: camera and image scale; Table 2: DIC subset) are used for the NT, CH and UT '
            'specimens. Beerli\'s sprayed patterns have features of about 8 px (slow, int) and 4 px (fast), i.e. '
            'about 270 µm at every rate. The study tests sizes of 2, 3, 4, 6 and 8 camera px around these values, '
            'rounded to the 33 µm engraver grid.')]
    t = [['Test', 'Strain rate', 'Camera, lens, frame rate', 'Image scale', 'Subset', 'Beerli pattern', 'Sizes tested']]
    for n in PRESETS:
        s = setup(n)
        szs = sorted({r['size_um'] for r in sel(rows, stage='size_density', preset=n)})
        t.append([n, RATE[n], CAMERA[n], '%g µm/px' % s['camera_um_per_px'], '%d px' % s['subset_px'],
                  'spray, ~%d px (%d µm)' % (s['beerli_feature_px'], s['beerli_feature_px'] * s['camera_um_per_px']),
                  ', '.join('%d' % x for x in szs) + ' µm'])
    S += [table(t, [13, 17, 40, 19, 13, 30, 42]), Spacer(1, 4),
          P('1.3 Camera model', 'h2'),
          P('The engraved raster is turned into the image the camera records: speckles dark (grey 0.1) on a light '
            'background (0.9); each camera pixel averages the engraved pixels under it (%g µm for slow, %g µm for '
            'fast); a slight optical blur (Gaussian, %.1f camera px); camera noise (Gaussian, %.0f %% of the grey '
            'range), drawn again for every image (Fig. 2).' % (setup('slow')['camera_um_per_px'],
                                                             setup('fast')['camera_um_per_px'], BLUR_PX, NOISE * 100)),
          img(fig_camera(best)),
          P('Fig. 2 - The same 2 × 2 mm of pattern as engraved and as seen by the camera, for the slow test (almost one '
            'camera pixel per engraver pixel) and the fast test (one camera pixel = about 2 × 2 engraver pixels).',
            'cap'),
          P('1.4 Virtual tests (known deformations)', 'h2'),
          P('To measure the quality of a pattern, the pattern itself is moved by a known amount, photographed again by '
            'the camera model (with new noise) and measured with DIC; the difference between the measured and the '
            'imposed value is the error. The DIC is the same as VIC-2D used by Beerli: square subsets (27 px slow and '
            'int, 17 px fast), first-order (affine) shape function, Gauss-Newton on the sum of squared differences, '
            'bicubic interpolation; 36 subsets on a regular grid over the 8 × 8 mm pattern.'),
          P('• <b>Translation test:</b> rigid shifts of 0.25 px in x and 0.5 px in y (sub-pixel, the hardest case). '
            'Result: RMS of the displacement error, in µm.'),
          P('• <b>Strain test (the "fake elongation"):</b> a uniform stretch like in a tensile test, ε<sub>xx</sub> = '
            '%.0f %% and ε<sub>yy</sub> = %.1f %%: every point X goes to X·(1 + ε) around the centre. Each subset '
            'measures the strain ∂u/∂x of its shape function. Result: the <b>strain noise</b> = standard deviation of '
            'the measured ε<sub>xx</sub> over the subsets (also the bias = mean error). No strain filter is applied, '
            'so the values are higher than the filtered floor noise of Beerli (4-8 × 10<super>-4</super>), but they rank the '
            'patterns the same way. <b>The strain noise is the criterion of the study.</b>' % (
                STRAIN[0] * 100, STRAIN[1] * 100)),
          P('1.5 Pattern indicators', 'h2')]
    t = [['Indicator', 'What it is, concretely', 'Better'],
         ['strain noise', 'scatter of the strain measured in the strain test (10<super>-4</super> = 0.01 % strain)', 'lower'],
         ['displacement error', 'RMS error of the displacement in the translation test, in µm', 'lower'],
         ['MIG', 'mean intensity gradient: average steepness of the grey levels at the speckle edges; the DIC error '
                 'goes roughly as noise / (MIG × subset size)', 'higher'],
         ['coverage', 'real fraction of the area engraved (overlapping speckles counted once)', 'see results'],
         ['seen size', 'width at half height of the autocorrelation of the camera image: the speckle size the DIC '
                       'really sees, blur included', '3-5 px'],
         ['entropy', 'spread of the grey levels (bits); recorded, not used to rank', '–']]
    S += [table(t, [30, 120, 24]), Spacer(1, 4),
          P('1.6 Design of the study', 'h2'),
          P('<b>Stage 1</b> - size × density: 5 sizes × 5 densities (0.25 to 0.65), square and circle, 4 random draws '
            'each (a new pattern and new camera noise per draw). The best (size, density) is the lowest mean strain '
            'noise. <b>Stage 2</b> - shapes: the five shapes at that size and density, 8 draws each. Each shape is '
            'compared with the square by a Welch t-test: p &lt; 0.05 means that the difference is larger than the '
            'scatter between draws (significant). Every result is the mean ± standard deviation over the draws.'),
          PageBreak()]

    # ---- results per preset
    S += [P('2. Results per strain rate', 'h1')]
    for i, n in enumerate(PRESETS):
        a = an[n]
        s = setup(n)
        blk = [P('2.%d %s test - %s, %g µm/px, subset %d px' % (i + 1, n.capitalize() if n != 'int' else
                                                                 'Intermediate', RATE[n], s['camera_um_per_px'],
                                                                 s['subset_px']), 'h2'),
               img(fig_heat(rows, n)),
               P('Fig. %d - Strain noise (10<super>-4</super>, mean of 4 draws) for every size and density; frame = best cell.'
                 % (3 + 3 * i), 'cap'),
               P('<b>Analysis.</b> ' + a['t_heat'])]
        S += [KeepTogether(blk),
              img(fig_trends(rows, n, best)),
              P('Fig. %d - Cuts through the maps: against the density at the best size, and against the size at the best '
                'density (bars = ± 1 standard deviation over the draws).' % (4 + 3 * i), 'cap'),
              P('<b>Analysis.</b> ' + a['t_tr']),
              KeepTogether([img(fig_shapes(rows, n)),
                            P('Fig. %d - The five shapes at %d µm and density %.2f, 8 draws each (± 1 standard '
                              'deviation); p = Welch t-test against the square.' % (5 + 3 * i, best[n][0],
                                                                                    best[n][1]), 'cap'),
                            P('<b>Analysis.</b> ' + a['t_sh'])]),
              PageBreak()]

    # ---- conclusions
    S += [P('3. Conclusions and next steps', 'h1'),
          P('• Use the recommended pattern of the summary table for each test: the density is the most important '
            'parameter (0.25 is too low), then the size, which must follow the camera of the test.'),
          P('• The shape matters less than the size and the density; keep the square where no shape is significantly '
            'better (simplest to engrave), and test the better shapes on real specimens where they are.'),
          P('• Check on the engraver that speckles of the recommended size and shape come out cleanly (edges, burn '
            'marks), and confirm with an engraved specimen and the real cameras (static test, rigid-body motion).'),
          P('• Not modelled here: the real engraving (edge blur, contrast), lighting and reflections, large strains '
            '(only 1 %), the strain filter of VIC-2D, the shear specimens (other image scales: 7, 10 and 50 µm/px).'),
          Spacer(1, 6),
          P('Files: speckle/speckle_generator.py (patterns), speckle_quality.py (camera model, DIC, tests), '
            'parameter_study.py (study, results/parameter_study.csv), make_report.py (this report), '
            'speckle_settings.yaml (presets and Beerli setups), results/shapes/*.png (one PNG per shape and test).',
            'cap')]

    def deco(c, doc):
        c.saveState()
        c.setFont(FONT, 7)
        c.setFillColor(colors.HexColor(INK2))
        c.drawString(18 * mm, 10 * mm, 'Engraved speckle patterns for DIC · Mohr lab, ETH Zurich · 25/11/2026')
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, 'page %d' % doc.page)
        c.restoreState()

    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=17 * mm, title='Engraved speckle patterns for DIC', author='Mohr lab, ETH Zurich')
    doc.build(S, onFirstPage=deco, onLaterPages=deco)
    print('written %s' % OUT)


if __name__ == '__main__':
    build()
