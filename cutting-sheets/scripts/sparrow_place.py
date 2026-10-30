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
    - marge au bord de la tole >= margin : la bande est elargie ou retrecie de (margin - gap) de chaque cote ;
    - angle impose : chaque eprouvette ne peut etre posee qu'a son angle commande ou a cet angle + 180 deg ;
      sparrow ne fait jamais de miroir quand on lui donne une liste d'angles.

Plusieurs toles : si la bande depasse la hauteur de la tole, les eprouvettes entierement contenues dans la tole
forment la tole 1 (leur placement reste valable), et les autres sont replacees sur une nouvelle tole, etc.
"""
import collections
import threading
import time

import ezdxf
from shapely import affinity

SAFETY = 0.05           # mm ajoutes a l'ecart demande a sparrow
SHEET_SPACING = 40.0    # mm entre deux toles dans le DXF (comme les plans du labo)


class PlacementError(Exception):
    pass


def _solve_strip(specs, polys, W, gap, margin, seconds, seed, workers, on_progress):
    """Une bande : renvoie [(spec, rotation_deg, x, y, contour_place)] dans le repere de la tole (y depuis le bas)."""
    import spyrrow
    sep = gap + SAFETY
    off = margin - gap                      # decalage entre le bord de la bande et le bord de la tole
    strip_h = W - 2 * off
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
                top = sol.width - sep + off
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
        x, y = strip_h - ty + off, tx + off                 # bande -> tole (rotation +90 deg, puis decalage)
        poly = affinity.translate(affinity.rotate(polys[s['T'].kind], r, origin=(0, 0)), x, y)
        placed.append((s, r, x, y, poly))
    return placed


def place(specs, polys, W, H, gap, margin, seconds, seed=1, workers=None, max_sheets=20, on_progress=None):
    """Toutes les eprouvettes sur des toles W x H. Renvoie une liste de toles, chacune une liste
    (spec, rotation_deg, x, y, contour_place). on_progress(k_tole, secondes_ecoulees, meilleure_hauteur)."""
    sheets, remaining = [], list(specs)
    while remaining:
        if len(sheets) >= max_sheets:
            raise PlacementError('les eprouvettes ne tiennent pas sur %d toles' % max_sheets)
        k = len(sheets) + 1
        placed = _solve_strip(remaining, polys, W, gap, margin, seconds, seed, workers,
                              (lambda t, b: on_progress(k, t, b)) if on_progress else None)
        inside = [p for p in placed if p[4].bounds[3] <= H - margin + 1e-6]
        if not inside:
            raise PlacementError('aucune eprouvette ne tient sur une tole de %g x %g mm' % (W, H))
        sheets.append(inside)
        done = set(id(p[0]) for p in inside)
        remaining = [s for s in remaining if id(s) not in done]
    return sheets


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
