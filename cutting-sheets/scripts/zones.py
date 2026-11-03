# -*- coding: utf-8 -*-
"""
zones.py -- Zones of a sheet on the EDM machine, and their drawing (used by make_plan.py and check_sheet.py).

All in mm, in sheet coordinates (origin = bottom-left corner of the sheet, y = rolling direction):
    sheet       the complete sheet (sheet: W x H)
    clamping    the bands held by the clamps (clamping: {left: 40, bottom: 40} = L-shaped clamping)
    machine     the area the wire can reach (machine_area: 350 x 250 for the CUT E 350), placed from the inner corner
                of the clamping (or machine_position: {left, bottom})
    placement   band of placement_margin mm inside the machine area: the sheet is not positioned to the mm in the
                machine, so nothing is placed there
    effective   the area where the specimens are placed = machine area minus placement margin, inside the sheet,
                outside the clamping, and at least edge_margin mm from a free edge of the sheet

The placement engine and the checks only need the margins per side = distance from each sheet edge to the effective
area (margins_from_zones).
"""
from shapely.geometry import box
from matplotlib.patches import Patch, PathPatch
from matplotlib.path import Path

SIDES = ('left', 'bottom', 'right', 'top')
COLOURS = {'clamping': '#dc2626', 'machine': '#111827', 'placement': '#f59e0b', 'effective': '#7c3aed',
           'unreachable': '#9ca3af'}


def compute(W, H, clamping, machine_area, placement_margin, edge_margin, machine_position=None):
    """Zones of a sheet W x H (see the module docstring). clamping: {side: width}; machine_area: (w, h).
    Returns a dict of shapely polygons + the numbers used; raises ValueError if the effective area is empty."""
    c = {k: float(clamping.get(k, 0.0)) for k in SIDES}
    mw, mh = machine_area
    pos = machine_position or {}
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
    reach = machine.intersection(sheet)
    clamp_union = sheet.intersection(clamps[0]) if clamps else None
    for b in clamps[1:]:
        clamp_union = clamp_union.union(b)
    placement = reach.difference(eff)
    unreachable = sheet.difference(reach)
    if clamp_union is not None:
        placement = placement.difference(clamp_union)
        unreachable = unreachable.difference(clamp_union)
    return {'sheet': sheet, 'clamping': clamp_union, 'machine': machine, 'placement': placement,
            'unreachable': unreachable, 'effective': eff,
            'numbers': {'W': W, 'H': H, 'clamping': c, 'machine_area': (mw, mh), 'machine_position': (mx, my),
                        'placement_margin': placement_margin, 'edge_margin': edge_margin}}


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
    patch(z['effective'], fill=False, ec=COLOURS['effective'], lw=1.0, zorder=1)


def legend_handles(z):
    n = z['numbers']
    c = ', '.join('%s %g' % (k, v) for k, v in n['clamping'].items() if v) or 'none'
    h = [Patch(fill=False, hatch='////', ec=COLOURS['clamping'], label='clamping (%s mm)' % c),
         Patch(fill=False, ec=COLOURS['machine'], ls='--', label='machine area %g x %g mm (wire travel)'
               % n['machine_area']),
         Patch(fc=COLOURS['placement'], alpha=0.35, ec='none', label='placement margin %g mm' % n['placement_margin']),
         Patch(fill=False, ec=COLOURS['effective'], label='effective area %.0f x %.0f mm (specimens)'
               % _size(z['effective']))]
    if not z['unreachable'].is_empty:
        h.append(Patch(fc=COLOURS['unreachable'], alpha=0.3, ec='none', label='sheet out of reach of the wire'))
    return h


def _size(g):
    x0, y0, x1, y1 = g.bounds
    return x1 - x0, y1 - y0
