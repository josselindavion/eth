# -*- coding: utf-8 -*-
"""
sparrow_place.py -- Placement des eprouvettes sur les toles avec sparrow, puis ecriture du DXF (utilise par make_plan.py).

Moteur : sparrow (Gardeyn, Vanden Berghe, Wauters, KU Leuven, 2025 ; licence MIT), via son interface Python spyrrow :
    py -m pip install spyrrow==0.9.0
sparrow resout le "strip packing" irregulier : une bande de hauteur fixe, longueur a minimiser. Ici la bande est la
tole couchee : sa hauteur fixe est la largeur W de la tole, et sa longueur est le sens de laminage (+Y), a minimiser.

Regles (encadrants, 29/10/2026) :
    - ecart entre pieces >= gap (5 mm) : parametre min_items_separation de sparrow (+ 0,05 mm de securite, car
      sparrow tolere ~0,01 mm de moins) ; sparrow garde aussi cet ecart avec le bord de la bande ;
    - marges au bord de la tole, une par cote (gauche, bas, droite, haut ; ex. zone de bridage en L de 40 mm a gauche
      et en bas) : la bande est placee entre x = gauche - gap et x = W - droite + gap, et commence a y = bas - gap ;
      sparrow gardant l'ecart (gap + 0,05) avec les bords de la bande, chaque piece est a >= marge + 0,05 du bord ;
      en haut, une piece n'est gardee sur la tole que si elle est a >= haut du bord ;
    - angle impose : chaque eprouvette ne peut etre posee qu'a son angle commande ou a cet angle + 180 deg ;
      sparrow ne fait jamais de miroir quand on lui donne une liste d'angles.

Plusieurs toles (voir place) : les eprouvettes sont d'abord reparties en groupes de surface egale, un par tole,
puis sparrow compacte chaque groupe sur sa tole ; si un groupe ne tient pas, on recommence avec une tole de plus.
"""
import collections
import math
import threading
import time

import ezdxf
from shapely import affinity

SAFETY = 0.05           # mm ajoutes a l'ecart demande a sparrow
SHEET_SPACING = 40.0    # mm entre deux toles dans le DXF (comme les plans du labo)


class PlacementError(Exception):
    pass


def _solve_strip(specs, polys, W, gap, m, seconds, seed, workers, on_progress):
    """Une bande : renvoie [(spec, rotation_deg, x, y, contour_place)] dans le repere de la tole (y depuis le bas).
    m : marges par cote {'gauche', 'bas', 'droite', 'haut'} en mm."""
    import spyrrow
    sep = gap + SAFETY
    x0, x1 = m['gauche'] - gap, W - m['droite'] + gap       # bords de la bande, en x sur la tole
    y0 = m['bas'] - gap                                     # debut de la bande, en y sur la tole
    strip_h = x1 - x0
    if strip_h <= 2 * sep:
        raise PlacementError('marges gauche + droite trop grandes pour une tole de %g mm de large' % W)
    groups = collections.OrderedDict()
    for s in specs:
        groups.setdefault('%s|%g' % (s['T'].kind, s['angle']), []).append(s)
    items = []
    for gid, ss in groups.items():
        g = affinity.rotate(polys[ss[0]['T'].kind], -90, origin=(0, 0))     # notre +Y = +X de la bande
        a = ss[0]['angle']
        items.append(spyrrow.Item(gid, list(g.exterior.coords)[:-1], demand=len(ss),
                                  allowed_orientations=[a, (a + 180.0) % 360.0]))
    inst = spyrrow.StripPackingInstance('plan', strip_height=strip_h, items=items)
    conf = spyrrow.StripPackingConfig(total_computation_time=int(seconds), min_items_separation=sep,
                                      num_workers=workers, seed=seed, early_termination=True)
    queue = spyrrow.ProgressQueue()
    box = {}

    def work():
        try:
            box['sol'] = inst.solve(conf, progress=queue)
        except Exception as e:              # remonte l'erreur au fil principal
            box['err'] = e
    th = threading.Thread(target=work, daemon=True)
    t0 = time.time()
    th.start()
    best = None
    while th.is_alive():
        th.join(0.25)
        for rtype, sol in queue.drain():
            if 'Feas' in str(rtype) and 'Infeas' not in str(rtype):
                top = sol.width - sep + y0
                best = top if best is None else min(best, top)
        if on_progress:
            on_progress(time.time() - t0, best)
    if 'err' in box:
        raise box['err']
    sol = box['sol']
    placed = []
    pool = {gid: list(ss) for gid, ss in groups.items()}
    # bas -> haut puis gauche -> droite, pour que les index montent dans l'ordre de lecture
    for pi in sorted(sol.placed_items, key=lambda p: (round(p.translation[0], 1), -p.translation[1])):
        s = pool[pi.id].pop(0)
        a = s['angle']                                      # angle exact : a ou a + 180 (sparrow calcule en float32)
        r = min((a % 360.0, (a + 180.0) % 360.0), key=lambda c: abs((pi.rotation - c + 180.0) % 360.0 - 180.0))
        tx, ty = pi.translation
        x, y = x1 - ty, y0 + tx                             # bande -> tole (rotation +90 deg, puis decalage)
        poly = affinity.translate(affinity.rotate(polys[s['T'].kind], r, origin=(0, 0)), x, y)
        placed.append((s, r, x, y, poly))
    return placed


def _split(specs, polys, n, gap):
    """Repartit les eprouvettes en n groupes de surface (piece + demi-ecart) a peu pres egale : la plus grande
    eprouvette restante va dans le groupe le moins charge (methode "LPT"), ce qui melange aussi les types."""
    area = {}
    for s in specs:
        k = s['T'].kind
        if k not in area:
            area[k] = polys[k].buffer(gap / 2.0, join_style=1).area
    groups, load = [[] for _ in range(n)], [0.0] * n
    for s in sorted(specs, key=lambda s: (-area[s['T'].kind], s['block'])):
        i = load.index(min(load))
        groups[i].append(s)
        load[i] += area[s['T'].kind]
    return [g for g in groups if g]


def place(specs, polys, W, H, gap, margins, seconds, seed=1, workers=None, max_sheets=20, on_progress=None,
          log=None):
    """Toutes les eprouvettes sur des toles W x H. margins : {'gauche', 'bas', 'droite', 'haut'} en mm.

    Methode :
      1. nombre de toles de depart n = surface des pieces (+ demi-ecart) / surface utile d'une tole, arrondi au-dessus
         (c'est un minimum : on ne peut pas faire moins) ;
      2. repartition des eprouvettes en n groupes de surface egale (_split) ;
      3. sparrow compacte chaque groupe sur sa tole (temps "seconds" par tole) ;
      4. si un groupe ne tient pas dans la tole, on arrete cet essai et on recommence avec n + 1 toles.
    Renvoie une liste de toles, chacune une liste (spec, rotation_deg, x, y, contour_place).
    on_progress(libelle, secondes_ecoulees, meilleure_hauteur) ; log(message).
    """
    uw = W - margins['gauche'] - margins['droite']
    uh = H - margins['bas'] - margins['haut']
    lim = H - margins['haut'] + 1e-6
    for s in specs:                                          # chaque piece doit tenir seule dans la zone utile
        T = s['T']
        b = affinity.rotate(polys[T.kind], s['angle'], origin=(0, 0)).bounds
        if b[2] - b[0] > uw + 1e-6 or b[3] - b[1] > uh + 1e-6:
            raise PlacementError('%s a %g deg (%.0f x %.0f mm une fois tournee) ne tient pas dans la zone utile de la '
                                 'tole (%g x %g mm, marges deduites)' % (T.alias, s['angle'], b[2] - b[0], b[3] - b[1],
                                                                        uw, uh))
    total = sum(polys[s['T'].kind].buffer(gap / 2.0, join_style=1).area for s in specs)
    n = max(1, int(math.ceil(total / ((uw + gap) * (uh + gap)) - 1e-9)))
    while n <= min(max_sheets, len(specs)):
        groups = _split(specs, polys, n, gap)
        sheets = []
        for k, g in enumerate(groups, 1):
            label = '%d tole%s : %d/%d' % (n, 's' if n > 1 else '', k, len(groups))
            placed = _solve_strip(g, polys, W, gap, margins, seconds, seed, workers,
                                  (lambda t, b, label=label: on_progress(label, t, b)) if on_progress else None)
            t = max(p[4].bounds[3] for p in placed)
            if t > lim:
                if log:
                    log('tole %d sur %d : depasse de %.1f mm -> essai avec %d toles' % (k, n, t - lim, n + 1))
                sheets = None
                break
            sheets.append(placed)
        if sheets:
            return sheets
        n += 1
    raise PlacementError('les eprouvettes ne tiennent pas sur %d toles' % min(max_sheets, len(specs)))


def top(sheet):
    return max(p[4].bounds[3] for p in sheet)


def write_dxf(path, sheets, libdoc, W, H):
    """Plan DXF : un cadre par tole (couleur 7) et un bloc par eprouvette (geometrie exacte), en mm."""
    doc = ezdxf.new('R2000', setup=True)
    doc.header['$INSUNITS'] = 4
    for name, c in (('Q3_NORMAL', 3), ('Q4_MEDIUM', 4), ('Q5_HIGH', 5), ('SHEET', 7)):
        doc.layers.add(name, color=c)
    msp = doc.modelspace()
    for name in sorted(set(p[0]['block'] for s in sheets for p in s)):
        blk = doc.blocks.new(name)
        for e in libdoc.blocks.get(name):
            blk.add_foreign_entity(e, copy=True)
    rows = []
    for k, s in enumerate(sheets):
        ox = k * (W + SHEET_SPACING)
        for a, b in (((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))):
            msp.add_line((ox + a[0], a[1]), (ox + b[0], b[1]), dxfattribs={'layer': 'SHEET', 'color': 7})
        for spec, r, x, y, poly in s:
            msp.add_blockref(spec['block'], (ox + x, y), dxfattribs={'rotation': r, 'layer': '0'})
            rows.append({'sheet': k + 1, 'block': spec['block'], 'type': spec['T'].kind,
                         'orientation_to_RD_deg': '%g' % (spec['angle'] % 180), 'rotation_deg': round(r, 4),
                         'insert_x_mm': round(ox + x, 4), 'insert_y_mm': round(y, 4)})
    doc.saveas(path)
    return rows
