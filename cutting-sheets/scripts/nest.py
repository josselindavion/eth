# -*- coding: utf-8 -*-
"""
nest.py -- Moteur de placement automatique des eprouvettes sur des toles (utilise par make_plan.py).

Regles (encadrants, 29/10/2026) :
    - ecart minimal entre pieces : 5 mm ; marge au bord de la tole : 5 mm (provisoire) ;
    - orientation imposee par le sens de laminage : chaque eprouvette est posee a l'angle commande, ou a cet angle
      + 180 deg (demi-tour) ; pas de miroir ;
    - pas de Mikrosteg dans le DXF (geres par l'atelier).

Moteur :
    1. chaque eprouvette est rasterisee sur une grille (0,5 mm) de facon conservative : une case est "occupee" des
       qu'un point de la piece la touche ; les pieces deja posees occupent toutes les cases a moins de `gap` d'elles ;
       une position est libre si aucune case de la piece ne tombe sur une case occupee : l'ecart reel est donc
       toujours >= gap (au prix d'au plus une demi-diagonale de case en plus) ;
    2. les positions libres d'une piece sont trouvees par correlation FFT (scipy), seulement dans les lignes utiles ;
    3. placement "en bas a gauche" : la position libre la plus basse, puis la plus a gauche, sur la premiere tole ou
       la piece tient (les deux demi-tours sont essayes) ; une nouvelle tole est ouverte si besoin ;
    4. plusieurs ordres de placement de depart, puis recuit simule sur l'ordre, plusieurs recuits en parallele ;
       critere : nombre de toles, puis hauteur occupee sur la derniere tole, puis somme des hauteurs ;
    5. le plan est ecrit en DXF (blocs, geometrie exacte, mm) ; make_plan.py le verifie ensuite.
"""
import collections
import copy
import math
import multiprocessing
import os
import random
import time

import ezdxf
import numpy as np
from matplotlib.path import Path as MplPath
from scipy.signal import fftconvolve
from shapely import affinity

SHEET_SPACING = 40.0                    # mm entre deux toles dans le DXF (comme les plans du labo)


# ============================================================
# BIBLIOTHEQUE
# ============================================================
class Item:
    """Une eprouvette a placer : contour exterieur dans le repere canonique et angles permis."""

    def __init__(self, row, poly):
        self.block = row['block']
        self.kind = row['type']
        self.orient = row['orientation_to_RD_deg']
        self.poly = poly
        base = float(row['rotation_deg'])                      # angle commande
        self.angles = (base, (base + 180.0) % 360.0)           # ou demi-tour ; jamais de miroir
        # pieces de meme contour (meme gabarit, codes differents) : un seul masque de placement
        self.shape_key = row.get('shape_key') or self.block
        self.area = poly.area


# ============================================================
# RASTER
# ============================================================
class Raster:
    """Masques rasterises (conservatifs) d'une piece pour chaque angle, a une resolution donnee."""

    def __init__(self, items, res, gap):
        self.res, self.gap = res, gap
        self.hd = res * math.sqrt(2) / 2           # demi-diagonale d'une case
        self.masks, self.flipped, self.stamps = {}, {}, {}
        for it in items:
            for a in it.angles:
                key = (it.shape_key, a)
                if key not in self.masks:
                    self.masks[key] = self._mask(affinity.rotate(it.poly, a, origin=(0, 0)))
                    self.flipped[key] = np.ascontiguousarray(self.masks[key][0][::-1, ::-1])
                    self.stamps[key] = self._stamp(key)

    def _cells(self, geom, x0, y0, nx, ny):
        xs = x0 + (np.arange(nx) + 0.5) * self.res
        ys = y0 + (np.arange(ny) + 0.5) * self.res
        X, Y = np.meshgrid(xs, ys)
        pts = np.column_stack([X.ravel(), Y.ravel()])
        inside = np.zeros(len(pts), bool)
        for g in getattr(geom, 'geoms', [geom]):
            inside |= MplPath(np.asarray(g.exterior.coords)).contains_points(pts)
            for h in g.interiors:
                pass                                # trous ignores : on ne place rien dans les trous
        return inside.reshape(ny, nx)

    def _mask(self, poly):
        """Cases touchees par la piece : centre a moins d'une demi-diagonale de la piece."""
        g = poly.buffer(self.hd, join_style=2)
        x0 = math.floor(poly.bounds[0] / self.res) * self.res - self.res
        y0 = math.floor(poly.bounds[1] / self.res) * self.res - self.res
        nx = int(math.ceil((poly.bounds[2] - x0) / self.res)) + 2
        ny = int(math.ceil((poly.bounds[3] - y0) / self.res)) + 2
        m = self._cells(g, x0, y0, nx, ny)
        # rogne les bords vides
        rows, cols = np.where(m)
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        return m[r0:r1, c0:c1].astype(np.float32), (x0 + c0 * self.res, y0 + r0 * self.res), poly

    def _stamp(self, key):
        """Cases interdites autour de la piece (forme, angle) posee en case (0, 0) : centre a moins de
        gap + demi-diagonale. Une piece posee en case (J, I) interdit le meme motif decale de (J, I) : calcule une
        seule fois par forme et par angle."""
        mask, (x0, y0), poly = self.masks[key]
        g = affinity.translate(poly, -x0, -y0).buffer(self.gap + self.hd, join_style=1)
        b = g.bounds
        c0, r0 = int(math.floor(b[0] / self.res)), int(math.floor(b[1] / self.res))
        c1, r1 = int(math.ceil(b[2] / self.res)) + 1, int(math.ceil(b[3] / self.res)) + 1
        return r0, c0, self._cells(g, c0 * self.res, r0 * self.res, c1 - c0, r1 - r0).astype(np.float32)

    def block(self, sheet, key, J, I):
        """Marque sur la tole les cases interdites par la piece (forme, angle) posee en case (J, I)."""
        r0, c0, sub = self.stamps[key]
        ny, nx = sheet.occ.shape
        R0, C0 = J + r0, I + c0
        R1, C1 = R0 + sub.shape[0], C0 + sub.shape[1]
        a0, b0 = max(0, R0), max(0, C0)
        a1, b1 = min(ny, R1), min(nx, C1)
        if a1 > a0 and b1 > b0:
            win = sheet.occ[a0:a1, b0:b1]
            np.maximum(win, sub[a0 - R0:a1 - R0, b0 - C0:b1 - C0], out=win)
            sheet.top_row = max(sheet.top_row, a1)


class Sheet:
    def __init__(self, W, H, margin, res):
        self.W, self.H = W, H
        nx, ny = int(round(W / res)), int(round(H / res))
        self.occ = np.zeros((ny, nx), np.float32)
        # bande de marge : cases dont une partie sort du rectangle utile
        k0 = int(math.ceil(margin / res))
        self.occ[:k0, :] = 1
        self.occ[:, :k0] = 1
        self.occ[ny - k0:, :] = 1
        self.occ[:, nx - k0:] = 1
        self.placed = []                         # (item, angle, tx, ty, polygone place)
        self.top_row = k0                        # premiere ligne au-dessus de la marge du bas et des cases interdites par des pieces
        self.jmin = {}                           # (forme, angle) -> ligne la plus basse encore possible (None : ne tient plus)

    def top(self):
        return max((p[4].bounds[3] for p in self.placed), default=0.0)


def try_place(sheet, raster, item):
    """Meilleure position (en bas a gauche) de l'item sur la tole, en essayant les angles permis.

    Recherche limitee aux lignes utiles (meme resultat qu'une recherche sur toute la tole) :
      - les cases interdites ne font qu'augmenter, donc la position libre la plus basse d'une forme ne peut que
        monter : on repart de la derniere trouvee (sheet.jmin) ;
      - au-dessus de sheet.top_row il n'y a que la marge : si la piece n'est pas libre a la ligne top_row, elle ne
        l'est nulle part plus haut ; on cherche donc entre jmin et top_row ;
      - une forme qui ne tient plus sur la tole est retenue (jmin = None) et n'est plus essayee.
    """
    best = None
    ny, nx = sheet.occ.shape
    for a in item.angles:
        key = (item.shape_key, a)
        j0 = sheet.jmin.get(key, 0)
        if j0 is None:
            continue
        mask, (x0, y0), poly = raster.masks[key]
        h, w = mask.shape
        if best is not None and j0 > best[0]:
            continue                                            # ne peut pas etre plus bas que le meilleur
        j1 = min(ny, max(sheet.top_row, j0) + h)
        if h > ny or w > nx or j1 - j0 < h:
            sheet.jmin[key] = None
            continue
        ok = fftconvolve(sheet.occ[j0:j1], raster.flipped[key], mode='valid') < 0.5
        rows = ok.any(axis=1)
        if not rows.any():
            sheet.jmin[key] = None
            continue
        jj = int(rows.argmax())
        J, I = j0 + jj, int(ok[jj].argmax())                    # plus bas, puis plus a gauche
        sheet.jmin[key] = J
        if best is None or (J, I) < (best[0], best[1]):
            best = (J, I, a, key, x0, y0, poly)
    if best is None:
        return None
    J, I, a, key, x0, y0, poly = best
    tx, ty = I * raster.res - x0, J * raster.res - y0
    return a, tx, ty, affinity.translate(poly, tx, ty), (key, J, I)


def place_all(order, items, raster, W, H, margin, max_sheets):
    sheets = []
    for k in order:
        it = items[k]
        done = False
        for sh in sheets:
            r = try_place(sh, raster, it)
            if r:
                done = True
                break
        if not done:
            if len(sheets) >= max_sheets:
                return None
            sh = Sheet(W, H, margin, raster.res)
            sheets.append(sh)
            r = try_place(sh, raster, it)
            if r is None:
                raise SystemExit('Piece %s trop grande pour la tole %gx%g mm' % (it.block, W, H))
        a, tx, ty, placed, (key, J, I) = r
        raster.block(sh, key, J, I)
        sh.placed.append((it, a, tx, ty, placed))
    return sheets


def score(sheets):
    if sheets is None:
        return (math.inf, math.inf, math.inf)
    return (len(sheets), round(sheets[-1].top(), 1), round(sum(s.top() for s in sheets), 1))


# ============================================================
# ORDRES ET RECUIT
# ============================================================
def initial_orders(items):
    idx = list(range(len(items)))
    h = lambda k: affinity.rotate(items[k].poly, items[k].angles[0], origin=(0, 0)).bounds   # noqa: E731
    by_type = collections.defaultdict(list)
    for k in idx:
        by_type[items[k].kind].append(k)
    grouped = [k for t in sorted(by_type, key=lambda t: -items[by_type[t][0]].area) for k in
               sorted(by_type[t], key=lambda k: (items[k].orient, items[k].block))]
    return {
        'area': sorted(idx, key=lambda k: -items[k].area),
        'height': sorted(idx, key=lambda k: -(h(k)[3] - h(k)[1])),
        'width': sorted(idx, key=lambda k: -(h(k)[2] - h(k)[0])),
        'type': grouped,
    }


def anneal(order, items, raster, W, H, margin, max_sheets, n_iter, seed=1, log=None, progress=None):
    """Recuit simule sur l'ordre de placement. progress(k) est appele apres chaque iteration k = 1..n_iter."""
    rnd = random.Random(seed)
    cur = list(order)
    cur_s = score(place_all(cur, items, raster, W, H, margin, max_sheets))
    best, best_s = list(cur), cur_s
    f = lambda s: s[0] * 1e5 + s[1] + 1e-3 * s[2]          # noqa: E731
    T0, T1 = 30.0, 0.5
    for it in range(n_iter):
        T = T0 * (T1 / T0) ** (it / max(1, n_iter - 1))
        cand = list(cur)
        if rnd.random() < 0.5:
            i, j = rnd.sample(range(len(cand)), 2)
            cand[i], cand[j] = cand[j], cand[i]
        else:                                               # deplace un bloc d'elements
            i = rnd.randrange(len(cand))
            k = cand.pop(i)
            cand.insert(rnd.randrange(len(cand) + 1), k)
        s = score(place_all(cand, items, raster, W, H, margin, max_sheets))
        if f(s) <= f(cur_s) or rnd.random() < math.exp(-(f(s) - f(cur_s)) / T):
            cur, cur_s = cand, s
            if f(s) < f(best_s):
                best, best_s = list(cand), s
                if log:
                    log('   recuit %4d/%d : %d tole(s), hauteur derniere tole %.1f mm'
                        % (it + 1, n_iter, s[0], s[1]))
        if progress:
            progress(it + 1)
    return best, best_s


def default_procs():
    """Nombre de recuits en parallele : tous les coeurs du PC sauf un (au moins 1)."""
    return max(1, (os.cpu_count() or 2) - 1)


_WORKER = {}


def _init_worker(items, raster, args, counter):
    _WORKER.update(items=items, raster=raster, args=args, counter=counter)


def _tick(_k=None):
    """Compteur partage entre les processus : une iteration (ou un ordre) de plus."""
    c = _WORKER['counter']
    with c.get_lock():
        c.value += 1


def _chain(job):
    order, n_iter, seed = job
    W, H, margin, max_sheets = _WORKER['args']
    t = time.time()
    best, best_s = anneal(order, _WORKER['items'], _WORKER['raster'], W, H, margin, max_sheets, n_iter, seed,
                          progress=_tick)
    return best, best_s, seed, time.time() - t


def _score_order(job):
    name, order = job
    W, H, margin, max_sheets = _WORKER['args']
    sc = score(place_all(order, _WORKER['items'], _WORKER['raster'], W, H, margin, max_sheets))
    _tick()
    return name, sc


def _lite(items):
    """Copie des items avec seulement ce qu'il faut pour placer (rien d'ezdxf), pour les processus paralleles."""
    out = []
    for it in items:
        x = copy.copy(it)
        x.__dict__.pop('spec', None)
        out.append(x)
    return out


def _run_pool(procs, items, raster, W, H, margin, max_sheets, func, jobs, total, on_progress):
    """Lance func sur jobs dans procs processus ; on_progress(fait, total) est appele pendant l'attente, d'apres un
    compteur partage que les processus incrementent."""
    ctx = multiprocessing.get_context('spawn')          # meme comportement sous Windows et Linux
    counter = ctx.Value('i', 0)
    with ctx.Pool(procs, initializer=_init_worker,
                  initargs=(_lite(items), raster, (W, H, margin, max_sheets), counter)) as pool:
        res = pool.map_async(func, jobs)
        while not res.ready():
            if on_progress:
                on_progress(counter.value, total)
            res.wait(0.25)
        out = res.get()
    if on_progress:
        on_progress(total, total)
    return out


def score_orders(orders, items, raster, W, H, margin, max_sheets, procs=None, on_progress=None):
    """Score de chaque ordre de depart ({nom: ordre} -> {nom: score}), en parallele si plusieurs coeurs."""
    procs = min(procs or default_procs(), len(orders))
    if procs <= 1:
        out = {}
        for k, (nm, o) in enumerate(orders.items(), 1):
            out[nm] = score(place_all(o, items, raster, W, H, margin, max_sheets))
            if on_progress:
                on_progress(k, len(orders))
        return out
    return dict(_run_pool(procs, items, raster, W, H, margin, max_sheets, _score_order, list(orders.items()),
                          len(orders), on_progress))


def anneal_parallel(order, items, raster, W, H, margin, max_sheets, n_iter, seed=1, procs=None, on_progress=None):
    """Plusieurs recuits independants en parallele (un par coeur, graines seed, seed + 1...), meme ordre de
    depart et meme nombre d'iterations chacun ; on garde le meilleur. procs = 1 : recuit simple.
    on_progress(fait, total) : total = procs x n_iter iterations."""
    procs = procs or default_procs()
    if procs <= 1:
        return anneal(order, items, raster, W, H, margin, max_sheets, n_iter, seed,
                      progress=(lambda k: on_progress(k, n_iter)) if on_progress else None)
    res = _run_pool(procs, items, raster, W, H, margin, max_sheets, _chain,
                    [(list(order), n_iter, seed + k) for k in range(procs)], procs * n_iter, on_progress)
    f = lambda s: s[0] * 1e5 + s[1] + 1e-3 * s[2]      # noqa: E731
    best, s, sd, dt = min(res, key=lambda r: f(r[1]))
    return best, s


# ============================================================
# SORTIES
# ============================================================
def write_dxf(path, sheets, libdoc, W, H):
    doc = ezdxf.new('R2000', setup=True)
    doc.header['$INSUNITS'] = 4
    for name, c in (('Q3_NORMAL', 3), ('Q4_MEDIUM', 4), ('Q5_HIGH', 5), ('SHEET', 7)):
        doc.layers.add(name, color=c)
    msp = doc.modelspace()
    used = sorted(set(p[0].block for s in sheets for p in s.placed))
    for name in used:
        blk = doc.blocks.new(name)
        for e in libdoc.blocks.get(name):
            blk.add_foreign_entity(e, copy=True)
    rows = []
    for k, s in enumerate(sheets):
        ox = k * (W + SHEET_SPACING)
        for a, b in (((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))):
            msp.add_line((ox + a[0], a[1]), (ox + b[0], b[1]), dxfattribs={'layer': 'SHEET', 'color': 7})
        for it, a, tx, ty, poly in s.placed:
            msp.add_blockref(it.block, (ox + tx, ty), dxfattribs={'rotation': a, 'layer': '0'})
            rows.append({'sheet': k + 1, 'block': it.block, 'type': it.kind, 'orientation_to_RD_deg': it.orient,
                         'rotation_deg': round(a, 3), 'insert_x_mm': round(ox + tx, 3), 'insert_y_mm': round(ty, 3)})
    doc.saveas(path)
    return rows

