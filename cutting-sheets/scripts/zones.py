# -*- coding: utf-8 -*-
"""
zones.py -- Zones of a sheet on the cutting machine (EDM or waterjet), and their drawing (used by make_plan.py and check_sheet.py).

All in mm, in sheet coordinates (origin = bottom-left corner of the sheet, y = rolling direction):
    sheet       the complete sheet (sheet: W x H)
    clamping    the bands held by the clamps (clamping: {left: 40, bottom: 40} = L-shaped clamping)
    machine     the area the cutting head can reach (machine_area: 350 x 250 for the CUT E 350), placed from the inner corner
                of the clamping (or machine_position: {left, bottom})
    placement   band of placement_margin mm inside the machine area: the sheet is not positioned to the mm in the
                machine, so nothing is placed there
    effective   the area where the specimens are placed = machine area minus placement margin, inside the sheet,
                outside the clamping, and at least edge_margin mm from a free edge of the sheet
    clamps      single clamps (clamps: [{side: left, at: 175, width: 50, depth: 40}, ...]): rectangle of width x depth
                mm on that edge, centred at "at" mm from the bottom-left corner; nothing is placed within
                clamp_margin + placement_margin mm of a clamp (keep-out zones, inside the effective area)
    forbidden   OPTIONAL (partly used sheet): union of rectangles where nothing may be cut (part of the sheet already
                used); nothing is placed within forbidden_margin mm of it (z['forbidden_keepouts'], one polygon per
                separate zone). Without it, z['forbidden'] is None and z['forbidden_keepouts'] is [].
Without machine_area (waterjet: the whole sheet can be cut), the machine area is the sheet minus edge_margin on the
free edges, so that the effective area is edge_margin + placement_margin from the edges.

The placement engine and the checks use the margins per side = distance from each sheet edge to the effective area
(margins_from_zones), plus the keep-out zones of the single clamps (z['keepouts'], list of polygons).
"""
from shapely.geometry import box, Polygon
from shapely.ops import unary_union
from matplotlib.patches import Patch, PathPatch
from matplotlib.path import Path

SIDES = ('left', 'bottom', 'right', 'top')
COLOURS = {'clamping': '#dc2626', 'machine': '#111827', 'placement': '#f59e0b', 'effective': '#7c3aed',
           'unreachable': '#9ca3af', 'forbidden': '#4b5563'}


def clamp_box(cl, W, H):
    """Rectangle of one single clamp {side, at, width, depth} on a sheet W x H."""
    side, at, w, d = cl['side'], float(cl['at']), float(cl['width']), float(cl['depth'])
    if side == 'left':
        return box(0, at - w / 2, d, at + w / 2)
    if side == 'right':
        return box(W - d, at - w / 2, W, at + w / 2)
    if side == 'bottom':
        return box(at - w / 2, 0, at + w / 2, d)
    if side == 'top':
        return box(at - w / 2, H - d, at + w / 2, H)
    raise ValueError('clamp side "%s": expected left, bottom, right or top' % side)


def compute(W, H, clamping, machine_area, placement_margin, edge_margin, machine_position=None, clamps=None,
            clamp_margin=5.0, forbidden=None, forbidden_margin=5.0):
    """Zones of a sheet W x H (see the module docstring). clamping: {side: width}; machine_area: (w, h) or None;
    clamps: list of single clamps; forbidden: optional list of shapely rectangles (sheet coordinates) where nothing
    may be cut. Returns a dict of shapely polygons + the numbers used; raises ValueError if the effective area is
    empty, a clamp is outside the sheet or a forbidden rectangle is outside the sheet."""
    c = {k: float(clamping.get(k, 0.0)) for k in SIDES}
    clamps_cfg = list(clamps or [])
    pos = machine_position or {}
    if machine_area is None:                                # whole sheet reachable (waterjet)
        x0, y0 = c['left'] or edge_margin, c['bottom'] or edge_margin
        mw, mh = W - (c['right'] or edge_margin) - x0, H - (c['top'] or edge_margin) - y0
        mx, my = float(pos.get('left', x0)), float(pos.get('bottom', y0))
    else:
        mw, mh = machine_area
        mx = float(pos.get('left', c['left']))
        my = float(pos.get('bottom', c['bottom']))
    sheet = box(0, 0, W, H)
    clamps = [b for b in (box(0, 0, c['left'], H) if c['left'] > 0 else None,
                          box(0, 0, W, c['bottom']) if c['bottom'] > 0 else None,
                          box(W - c['right'], 0, W, H) if c['right'] > 0 else None,
                          box(0, H - c['top'], W, H) if c['top'] > 0 else None) if b is not None]
    machine = box(mx, my, mx + mw, my + mh)
    # free part of the sheet: outside the clamps, and edge_margin from the free edges
    free = box(c['left'] or edge_margin, c['bottom'] or edge_margin,
               W - (c['right'] or edge_margin), H - (c['top'] or edge_margin))
    inner = box(mx + placement_margin, my + placement_margin,
                mx + mw - placement_margin, my + mh - placement_margin)
    eff = inner.intersection(free)
    if eff.is_empty or eff.area <= 0:
        raise ValueError('no effective area left: check sheet, clamping, machine_area, machine_position and margins')
    pads = [clamp_box(cl, W, H) for cl in clamps_cfg]
    for cl, b in zip(clamps_cfg, pads):
        if not sheet.buffer(1e-6).contains(b):
            raise ValueError('clamp %s at %g mm is outside the sheet' % (cl['side'], float(cl['at'])))
    grow = clamp_margin + placement_margin
    keepouts = [b.buffer(grow, join_style=2).intersection(eff) for b in pads]
    keepouts = [k for k in keepouts if not k.is_empty and k.area > 0]
    shape = eff.difference(unary_union(keepouts)) if keepouts else eff
    reach = machine.intersection(sheet)
    clamps = [b for b in clamps if b is not None] + pads
    clamp_union = unary_union(clamps).intersection(sheet) if clamps else None
    placement = reach.difference(eff)
    unreachable = sheet.difference(reach)
    if clamp_union is not None:
        placement = placement.difference(clamp_union)
        unreachable = unreachable.difference(clamp_union)
    placement = placement.union(unary_union(keepouts)) if keepouts else placement
    if clamp_union is not None:
        placement = placement.difference(clamp_union)
    # optional forbidden zone (partly used sheet): union of the rectangles, + forbidden_margin, inside the effective area
    fzone, fkeep = None, []
    if forbidden:
        for b in forbidden:
            if not sheet.buffer(1e-6).contains(b):
                x0, y0, x1, y1 = b.bounds
                raise ValueError('forbidden rectangle rd [%g, %g], td [%g, %g] is outside the sheet' % (y0, y1, x0, x1))
        fzone = unary_union(forbidden)
        grown = fzone.buffer(forbidden_margin, join_style=2).intersection(eff)
        fkeep = [g for g in (grown.geoms if hasattr(grown, 'geoms') else [grown])
                 if g.geom_type == 'Polygon' and g.area > 0]
        fkeep = [Polygon(g.exterior) for g in fkeep]        # a hole inside a forbidden zone cannot be reached
        shape = shape.difference(unary_union(fkeep))
        placement = placement.union(unary_union(fkeep).difference(fzone))
    return {'sheet': sheet, 'clamping': clamp_union, 'machine': machine, 'placement': placement,
            'unreachable': unreachable, 'effective': eff, 'keepouts': keepouts, 'shape': shape,
            'forbidden': fzone, 'forbidden_keepouts': fkeep,
            'numbers': {'W': W, 'H': H, 'clamping': c, 'machine_area': (mw, mh), 'machine_position': (mx, my),
                        'placement_margin': placement_margin, 'edge_margin': edge_margin,
                        'clamps': clamps_cfg, 'n_clamps': len(pads),
                        'clamp_size': ((float(clamps_cfg[0]['width']), float(clamps_cfg[0]['depth']))
                                       if clamps_cfg else None),
                        'clamp_margin': clamp_margin, 'whole_sheet': machine_area is None,
                        'forbidden_margin': forbidden_margin if forbidden else None,
                        'forbidden_area': fzone.area if fzone is not None else 0.0}}


def margins_from_zones(z):
    """Distance from each sheet edge to the effective area (what the engine and the checks use)."""
    x0, y0, x1, y1 = z['effective'].bounds
    W, H = z['numbers']['W'], z['numbers']['H']
    return {'left': x0, 'bottom': y0, 'right': W - x1, 'top': H - y1}


def _polys(g):
    if g is None or g.is_empty:
        return []
    return list(g.geoms) if hasattr(g, 'geoms') else [g]


def draw(ax, z, ox=0.0, oy=0.0):
    """Draws the zones of one sheet whose bottom-left corner is at (ox, oy), below the specimens."""
    def patch(g, **kw):
        for p in _polys(g):
            if p.geom_type != 'Polygon':
                continue
            rings = [p.exterior] + list(p.interiors)        # holes kept (e.g. placement band around the effective area)
            path = Path.make_compound_path(*[Path([(x + ox, y + oy) for x, y in r.coords], closed=True)
                                             for r in rings])
            ax.add_patch(PathPatch(path, **kw))
    patch(z['unreachable'], fill=True, fc=COLOURS['unreachable'], alpha=0.18, ec='none', zorder=0)
    patch(z['clamping'], fill=False, hatch='////', ec=COLOURS['clamping'], lw=0, alpha=0.6, zorder=0)
    patch(z['placement'], fill=True, fc=COLOURS['placement'], alpha=0.22, ec='none', zorder=0)
    patch(z['machine'], fill=False, ec=COLOURS['machine'], lw=1.0, ls='--', zorder=1)
    patch(z.get('shape', z['effective']), fill=False, ec=COLOURS['effective'], lw=1.0, zorder=1)
    if z.get('forbidden') is not None:                      # optional: part of the sheet already used
        patch(z['forbidden'], fill=True, fc=COLOURS['forbidden'], alpha=0.25, hatch='xx', ec=COLOURS['forbidden'],
              lw=1.0, zorder=1)


def legend_handles(z):
    n = z['numbers']
    c = ', '.join('%s %g' % (k, v) for k, v in n['clamping'].items() if v)
    if n.get('n_clamps'):
        c = (c + '; ' if c else '') + '%d clamps %g along the edge x %g deep' % ((n['n_clamps'],) + n['clamp_size'])
    h = [Patch(fill=False, hatch='////', ec=COLOURS['clamping'], label='clamping (%s mm)' % (c or 'none')),
         Patch(fill=False, ec=COLOURS['machine'], ls='--',
               label=('usable area %g (RD) x %g (TD) mm' if n.get('whole_sheet')
                      else 'machine area %g (RD) x %g (TD) mm (wire travel)') % n['machine_area'][::-1]),
         Patch(fc=COLOURS['placement'], alpha=0.35, ec='none',
               label='placement margin %g mm' % n['placement_margin'] +
                     (' (+ clamp margin %g mm)' % n['clamp_margin'] if n.get('n_clamps') else '')),
         Patch(fill=False, ec=COLOURS['effective'], label='effective area %.0f (RD) x %.0f (TD) mm (specimens)'
               % _size(z['effective'])[::-1])]
    if z.get('forbidden') is not None:
        h.append(Patch(fc=COLOURS['forbidden'], alpha=0.35, hatch='xx', ec=COLOURS['forbidden'],
                       label='forbidden zone %.0f mm² (sheet already used), margin %g mm'
                       % (n['forbidden_area'], n['forbidden_margin'])))
    if not z['unreachable'].is_empty:
        h.append(Patch(fc=COLOURS['unreachable'], alpha=0.3, ec='none',
                       label='edge margin %g mm' % n['edge_margin'] if n.get('whole_sheet')
                       else 'sheet out of reach of the wire'))
    return h


def _size(g):
    x0, y0, x1, y1 = g.bounds
    return x1 - x0, y1 - y0
