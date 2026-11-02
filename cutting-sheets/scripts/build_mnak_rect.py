# -*- coding: utf-8 -*-
"""
build_mnak_rect.py -- Catalogue complementaire : Mini-Nakajima RECTANGULAIRE, avec et sans trous (proposition d'Erik,
02/11/2026).

Lancement (depuis la racine du repo) :
    py cutting-sheets/scripts/build_mnak_rect.py

Entree  : cutting-sheets/input/RoundSample_Dual_Hole_rectange.dxf (export SolidWorks de la piece, mm, tout en couleur 7)
Sortie  : cutting-sheets/input/specimen_templates_extra_MNAK_RECT.dxf, dans le format du catalogue du labo :
          un bloc par eprouvette, nomme MNAK_RECT_HOLE_<chiffre d'angle><index> (2 trous) ou MNAK_RECT_FULL_<...>
          (sans trous), pose a son angle (0, 45, 90 deg ; index 0 a 9, comme MNAK_HOLE / MNAK_FULL), qualites par
          couleur (3 = Q3, 5 = Q5).

Repere et code (identiques au disque MNAK_HOLE du catalogue, verifie le 02/11/2026) :
    - la piece d'Erik est tournee de +90 deg : le meplat x = +27 devient le meplat y = +27, les trous (R3,9 a 9 mm
      du centre) sont alors le long de x, perpendiculaires a la direction du code, comme sur le disque ;
    - code a encoches sur ce meplat, depart en x = -7,0 mm (comme le disque), trait Q3 jusqu'au bout du meplat ;
    - angle de l'eprouvette = direction du code depuis le sens de laminage ; trous a angle + 90 deg ;
    - qualites comme le disque : contour Q3 (vert), trous Q5 (bleu), code Q5 ;
    - CHANFREIN de reperage (decide le 02/11/2026) : la piece d'Erik est symetrique ; le coin arrondi R2 en haut a
      gauche (code en haut) est remplace par un chanfrein a 45 deg de CHAMFER mm, comme le coin chanfreine des autres
      eprouvettes, pour savoir de quelle face on lit le code ;
    - version sans trous : la meme sans les deux cercles.
"""
import math
import os
import sys

import ezdxf
from ezdxf.math import Matrix44

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import notchcode as nc                   # noqa: E402

SRC = os.path.join(HERE, '..', 'input', 'RoundSample_Dual_Hole_rectange.dxf')
OUT = os.path.join(HERE, '..', 'input', 'specimen_templates_extra_MNAK_RECT.dxf')
FAMILIES = (('MNAK_RECT_HOLE', True), ('MNAK_RECT_FULL', False))     # (famille, avec trous)
CHAMFER = 4.0                            # mm, cotes du chanfrein a 45 deg du coin haut gauche
ANGLE_DIGITS = (0, 3, 6)                 # 0, 45, 90 deg, comme MNAK_HOLE dans le catalogue du labo
CODE_X0, FLAT_Y = -7.0, 27.0
LAYERS = {3: 'Normal_Quality', 5: 'High_Quality'}


def base_entities(holes=True):
    """Entites de la piece tournee de +90 deg ; le meplat du code est remplace par ses deux morceaux Q3 (ajoutes
    avec le code) ; le coin haut gauche (arc R2) devient un chanfrein ; sans trous si holes est faux."""
    doc = ezdxf.readfile(SRC)
    rot = Matrix44.z_rotate(math.radians(90))
    ents, flat, corner = [], None, None
    for e in doc.modelspace():
        x = e.copy()
        x.transform(rot)
        t = x.dxftype()
        if t == 'LINE' and abs(x.dxf.start.y - FLAT_Y) < 1e-6 and abs(x.dxf.end.y - FLAT_Y) < 1e-6:
            flat = sorted((x.dxf.start.x, x.dxf.end.x))
            continue
        if t == 'CIRCLE' and not holes:
            continue
        ents.append((x, 5 if t == 'CIRCLE' else 3))
    if flat is None:
        raise SystemExit('meplat y = %g introuvable dans %s' % (FLAT_Y, SRC))
    # coin haut gauche : arc dont le centre est le plus en haut a gauche
    arcs = [(e, c) for e, c in ents if e.dxftype() == 'ARC']
    arc, _ = min(arcs, key=lambda ec: ec[0].dxf.center.x - ec[0].dxf.center.y)
    cx, cy, r = arc.dxf.center.x, arc.dxf.center.y, arc.dxf.radius
    x0, y1 = cx - r, cy + r                         # bord gauche (x = x0) et bord haut (y = y1) de la piece
    for e, c in ents:
        if e.dxftype() != 'LINE':
            continue
        for end in ('start', 'end'):
            p = getattr(e.dxf, end)
            if abs(p.x - x0) < 1e-6 and abs(p.y - cy) < 1e-6:          # bout du bord gauche -> descend
                setattr(e.dxf, end, (x0, y1 - CHAMFER, 0))
                corner = True
            elif abs(p.x - cx) < 1e-6 and abs(p.y - y1) < 1e-6:       # bout du bord haut -> recule
                setattr(e.dxf, end, (x0 + CHAMFER, y1, 0))
    if not corner:
        raise SystemExit('coin haut gauche introuvable')
    ents = [(e, c) for e, c in ents if e is not arc]
    out = ezdxf.new('R2000')
    ents.append((out.modelspace().add_line((x0, y1 - CHAMFER), (x0 + CHAMFER, y1)), 3))
    return ents, flat


def main():
    out = ezdxf.new('R2000', setup=True)
    out.header['$INSUNITS'] = 4
    for c, name in LAYERS.items():
        out.layers.add(name, color=c)
    msp = out.modelspace()
    k = 0
    for family, holes in FAMILIES:
        ents, (fx0, fx1) = base_entities(holes)
        for a in ANGLE_DIGITS:
            for idx in range(10):
                name = '%s_%d%d' % (family, a, idx)
                blk = out.blocks.new(name)
                for e, c in ents:
                    y = e.copy()
                    y.dxf.layer, y.dxf.color = LAYERS[c], c
                    blk.add_foreign_entity(y, copy=False)
                lines, length = nc.code_lines(a, idx)
                blk.add_line((fx0, FLAT_Y), (CODE_X0, FLAT_Y), dxfattribs={'layer': LAYERS[3], 'color': 3})
                for (u0, v0), (u1, v1) in lines:
                    blk.add_line((CODE_X0 + u0, FLAT_Y + v0), (CODE_X0 + u1, FLAT_Y + v1),
                                 dxfattribs={'layer': LAYERS[5], 'color': 5})
                blk.add_line((CODE_X0 + length, FLAT_Y), (fx1, FLAT_Y), dxfattribs={'layer': LAYERS[3], 'color': 3})
                msp.add_blockref(name, (120.0 * (k % 10), -120.0 * (k // 10)), dxfattribs={'rotation': 15.0 * a})
                k += 1
    out.saveas(OUT)
    print('%d blocs (%s) -> %s' % (k, ', '.join(f for f, _ in FAMILIES), os.path.abspath(OUT)))

if __name__ == '__main__':
    main()
