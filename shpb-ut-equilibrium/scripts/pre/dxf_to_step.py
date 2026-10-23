# -*- coding: utf-8 -*-
"""
dxf_to_step.py -- Contour 2D d'une eprouvette (fichier DXF de decoupe : lignes + arcs formant une seule boucle
fermee) -> solide STEP de la tole, extrude de t mm selon +Z.

Repere de sortie, comme les autres STEP d'eprouvettes : longueur selon X (de 0 a L), largeur centree sur Y = 0,
z de 0 a t. build_bench.py place ensuite l'eprouvette automatiquement.

Usage (Python 3, pas Abaqus), racine du repo :
    py -m pip install ezdxf cadquery-ocp        (une seule fois)
    py shpb-ut-equilibrium/scripts/pre/dxf_to_step.py shpb-ut-equilibrium/cad/dxf/Xmas_UT40.dxf ^
       shpb-ut-equilibrium/cad/step/XMas_UT40_t1p5.step 1.5
Unites : le DXF est suppose en mm (verifier les dimensions affichees).
"""
import sys, math, ezdxf
from OCP.gp import gp_Pnt, gp_Vec
from OCP.GC import GC_MakeArcOfCircle, GC_MakeSegment
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.Interface import Interface_Static
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
src, dst, t = sys.argv[1], sys.argv[2], float(sys.argv[3])
msp = ezdxf.readfile(src).modelspace()
ents = []
for e in msp:
    if e.dxftype() == 'LINE':
        ents.append(('L', [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]))
    elif e.dxftype() == 'ARC':
        c, r, a0, a1 = e.dxf.center, e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle
        a1 = a1 if a1 > a0 else a1 + 360.0
        am = 0.5 * (a0 + a1)
        ents.append(('A', [(c.x + r * math.cos(math.radians(a)), c.y + r * math.sin(math.radians(a))) for a in (a0, am, a1)]))
xs = [p[0] for _, ps in ents for p in ps]; ys = [p[1] for _, ps in ents for p in ps]
xc, y0 = 0.5 * (min(xs) + max(xs)), min(ys)
# DXF : longueur selon y -> STEP : longueur selon X ; (x, y) -> (X, Y) = (y - ymin, -(x - xc))
P = lambda p: gp_Pnt(p[1] - y0, -(p[0] - xc), 0.0)
mw = BRepBuilderAPI_MakeWire()
# ordonner les aretes en boucle
key = lambda p: (round(p[0], 5), round(p[1], 5))
left = list(range(len(ents))); order = [left.pop(0)]; cur = key(ents[order[0]][1][-1])
while left:
    j = next(j for j in left if key(ents[j][1][0]) == cur or key(ents[j][1][-1]) == cur)
    left.remove(j)
    if key(ents[j][1][-1]) == cur:
        ents[j] = (ents[j][0], ents[j][1][::-1])
    order.append(j); cur = key(ents[j][1][-1])
for j in order:
    typ, ps = ents[j]
    if typ == 'L':
        crv = GC_MakeSegment(P(ps[0]), P(ps[1])).Value()
    else:
        crv = GC_MakeArcOfCircle(P(ps[0]), P(ps[1]), P(ps[2])).Value()
    mw.Add(BRepBuilderAPI_MakeEdge(crv).Edge())
assert mw.IsDone(), 'contour non ferme'
face = BRepBuilderAPI_MakeFace(mw.Wire()).Face()
solid = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, t)).Shape()
g = GProp_GProps(); BRepGProp.VolumeProperties_s(solid, g)
print('contour : %d aretes ; longueur %.4f mm, largeur %.4f mm' % (len(order), max(ys) - min(ys), max(xs) - min(xs)))
print('solide valide :', BRepCheck_Analyzer(solid).IsValid(), ' volume %.2f mm3' % abs(g.Mass()))
w = STEPControl_Writer(); Interface_Static.SetCVal_s('write.step.schema', 'AP214IS'); Interface_Static.SetCVal_s('write.step.unit', 'MM')
w.Transfer(solid, STEPControl_AsIs); w.Write(dst); print('ecrit :', dst)
