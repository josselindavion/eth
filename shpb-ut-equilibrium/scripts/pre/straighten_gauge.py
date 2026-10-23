# -*- coding: utf-8 -*-
"""
straighten_gauge.py -- Copie d'un contour DXF d'eprouvette dont la partie droite est rendue PARFAITEMENT
droite, de demi-largeur donnee ; tout le reste (tetes, dents, rayons des raccords) est inchange.

Pourquoi (23/10/2026) : dans Xmas_UT40.dxf, la partie droite n'est pas tout a fait droite (10,020 mm de large
cote barre de sortie, 10,001 mm cote pusher). A 1000 /s la striction se forme au bout le plus etroit, hors de
l'extensometre. La version droite (UT40S) sert a savoir si c'est ce retrecissement ou l'effet dynamique.

Ce que fait le script, sur le contour (plan x, y du DXF, longueur selon y) :
  - les 2 plus longues lignes quasi paralleles a y (les bords de la partie droite) sont placees a
    x = xc +- demi-largeur, xc = milieu de la largeur totale ;
  - les 4 arcs de raccord qui les touchent gardent leur rayon ; leur centre est deplace selon x pour rester
    tangent au bord droit, avec des angles exacts (multiples de 90 deg) ;
  - l'autre bout de chaque arc est sur l'epaulement horizontal : le bout de la ligne d'epaulement suit.
Usage :
    py shpb-ut-equilibrium/scripts/pre/straighten_gauge.py <entree.dxf> <sortie.dxf> 5.0
"""
import math
import sys

import ezdxf

src, dst, half = sys.argv[1], sys.argv[2], float(sys.argv[3])
doc = ezdxf.readfile(src)
msp = doc.modelspace()
lines = [e for e in msp if e.dxftype() == 'LINE']
arcs = [e for e in msp if e.dxftype() == 'ARC']
pts = [(e.dxf.start.x, e.dxf.start.y) for e in lines] + [(e.dxf.end.x, e.dxf.end.y) for e in lines]
xc = 0.5 * (min(p[0] for p in pts) + max(p[0] for p in pts))

def arc_ends(a):
    c, r = a.dxf.center, a.dxf.radius
    return [(c.x + r * math.cos(math.radians(t)), c.y + r * math.sin(math.radians(t)))
            for t in (a.dxf.start_angle, a.dxf.end_angle)]

near = lambda p, q, tol=1e-2: abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol
vert = sorted([e for e in lines if abs(e.dxf.end.x - e.dxf.start.x) < 0.1 * abs(e.dxf.end.y - e.dxf.start.y)],
              key=lambda e: -abs(e.dxf.end.y - e.dxf.start.y))[:2]
print('centre de la largeur xc = %.5f' % xc)
for ln in vert:
    side = 1.0 if 0.5 * (ln.dxf.start.x + ln.dxf.end.x) > xc else -1.0
    x_new = xc + side * half
    for end in ('start', 'end'):
        p = getattr(ln.dxf, end)
        fil = [a for a in arcs if any(near((p.x, p.y), q) for q in arc_ends(a))]
        assert len(fil) == 1, 'raccord introuvable en (%.4f, %.4f)' % (p.x, p.y)
        a = fil[0]
        c, r = a.dxf.center, a.dxf.radius
        cx_new = x_new + side * r                 # raccord concave : centre a l'exterieur du bord droit
        other = [q for q in arc_ends(a) if not near(q, (p.x, p.y))][0]
        # ligne d'epaulement qui touche l'autre bout de l'arc : son bout suit le centre selon x
        sh = [(e, nm) for e in lines for nm in ('start', 'end')
              if e is not ln and near((getattr(e.dxf, nm).x, getattr(e.dxf, nm).y), other)]
        assert len(sh) == 1, 'epaulement introuvable'
        e_sh, nm = sh[0]
        q = getattr(e_sh.dxf, nm)
        y_sh = c.y + (r if other[1] > c.y else -r)
        setattr(e_sh.dxf, nm, (cx_new, y_sh, 0.0))
        # angles exacts : de la tangente au bord droit (0 ou 180 deg) a l'epaulement (90 ou 270 deg)
        t_edge = 180.0 if side > 0 else 0.0
        t_sh = 90.0 if other[1] > c.y else 270.0
        a0, a1 = sorted([t_edge, t_sh]) if abs(t_edge - t_sh) == 90.0 else (270.0, 360.0)
        if {t_edge, t_sh} == {0.0, 270.0}:
            a0, a1 = 270.0, 360.0
        print('raccord : centre (%.4f, %.4f) -> (%.4f, %.4f), angles %.0f-%.0f' % (c.x, c.y, cx_new, c.y, a0, a1))
        a.dxf.center = (cx_new, c.y, 0.0)
        a.dxf.start_angle, a.dxf.end_angle = a0, a1
        setattr(ln.dxf, end, (x_new, c.y, 0.0))
    print('bord droit : x = %.4f -> %.5f, de y = %.4f a %.4f'
          % (0.5 * (ln.dxf.start.x + ln.dxf.end.x), x_new, ln.dxf.start.y, ln.dxf.end.y))
doc.saveas(dst)
print('ecrit : ' + dst)
