# -*- coding: utf-8 -*-
"""
pocket_gaps.py -- Mesure les jeux entre les dents de l'eprouvette et les logements du pusher et de la
barre de sortie, directement sur les fichiers STEP (OpenCascade), dans le placement de build_bench.py
(eprouvette centree dans les deux logements).

Resultat : les deux valeurs gap_pusher et gap_output a recopier dans SPECIMENS de build_bench.py.

  gap_pusher : de combien l'eprouvette doit reculer (-Y) pour toucher le logement du pusher.
               Negatif si, dans le placement centre, elle recouvre deja le logement (UT40 : son bout cote
               pusher est plus court que celui de l'UT19, or le placement centre se cale sur ce bout).
               C'est aussi la course du pusher (+Y) avant qu'il tire sur l'eprouvette.
  gap_output : de combien l'eprouvette doit avancer (+Y) pour toucher le logement de la barre de sortie.

Methode : on translate l'eprouvette selon Y et on cherche, par dichotomie, la plus petite translation
pour laquelle la distance entre les deux solides devient nulle. L'eprouvette est levee de 0,5 mm pendant
la mesure pour ne pas compter le contact sur le fond du logement (en Z, elle y est posee) ; les dents
sont des extrusions selon Z, donc cela ne change pas le jeu selon Y.
Le script verifie ensuite, une fois les jeux fermes, quelles faces de l'eprouvette touchent.

Usage (Python 3, pas Abaqus) :
  py -m pip install cadquery-ocp        (une seule fois, ~100 Mo)
  py shpb-ut-equilibrium/scripts/pre/pocket_gaps.py UT19
Duree : quelques minutes.
"""
import math
import os
import sys

from OCP.STEPControl import STEPControl_Reader
from OCP.gp import gp_Trsf, gp_Ax1, gp_Pnt, gp_Dir, gp_Vec
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE
from OCP.TopoDS import TopoDS
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STEP_DIR = os.path.join(ROOT, 'cad', 'step')

# Memes constantes que build_bench.py (placement centre)
SPECIMENS = {'UT19': 'XMas_UT_t1p5.step', 'UT40': 'XMas_UT40_t1p5.step', 'UT40S': 'XMas_UT40S_t1p5.step'}
STEP_PUSHER = 'Inverter_new_noM4.step'
STEP_OUTPUT_BAR = 'Stange30mm_Step2_noM4.step'
Y_SPEC_TIP_PUSHER = 201.7005
OUTPUT_BAR_TO_TIP = 31.7000
Z_SPEC_BOTTOM = 28.6
Z_OUTPUT_AXIS = 7.85 + 21.5
LIFT = 0.5          # mm, levee de l'eprouvette pendant la mesure (ignore le fond du logement)
TOL = 1.0e-7        # mm, distance consideree comme un contact


def load(name):
    r = STEPControl_Reader()
    if r.ReadFile(os.path.join(STEP_DIR, name)) != 1:
        sys.exit('Fichier STEP illisible : ' + name)
    r.TransferRoots()
    return r.OneShape()


def move(shape, axis=None, angle=0.0, vec=(0.0, 0.0, 0.0)):
    """Rotation autour d'un axe passant par l'origine, puis translation (comme dans build_bench.py)."""
    rot = gp_Trsf()
    if axis:
        rot.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(*axis)), math.radians(angle))
    t = gp_Trsf()
    t.SetTranslation(gp_Vec(*vec))
    t.Multiply(rot)
    return BRepBuilderAPI_Transform(shape, t, True).Shape()


def bbox(shape):
    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b)
    m, M = b.CornerMin(), b.CornerMax()
    return m.X(), m.Y(), m.Z(), M.X(), M.Y(), M.Z()


def crop_y(shape, y0, y1):
    """Garde la partie de la piece entre Y = y0 et y1 (la tete : calcul plus rapide)."""
    box = BRepPrimAPI_MakeBox(gp_Pnt(-100, y0, -100), gp_Pnt(100, y1, 100)).Shape()
    return BRepAlgoAPI_Common(shape, box).Shape()


def dist(a, b):
    d = BRepExtrema_DistShapeShape(a, b)
    d.Perform()
    return d.Value()


def gap(spec, other, sign):
    """Translation selon Y (sens 'sign') qui amene l'eprouvette juste au contact de 'other'.
    Positive : il y a un jeu a fermer. Negative : au depart les pieces se recouvrent deja (interpenetration),
    il faut reculer de cette valeur pour qu'elles se touchent seulement."""
    sep = lambda d: dist(move(spec, vec=(0, sign * d, 0)), other) > TOL      # separees ?
    if sep(0.0):
        lo, hi = 0.0, 0.05                     # lo : separees, hi : en contact
        while sep(hi):
            lo, hi = hi, 2.0 * hi
            if hi > 10.0:
                sys.exit('Pas de contact a moins de 10 mm : placement a verifier')
    else:
        lo, hi = -0.05, 0.0                    # deja en contact au depart : on recule jusqu'a les separer
        while not sep(lo):
            hi, lo = lo, 2.0 * lo
            if lo < -10.0:
                sys.exit('Recouvrement de plus de 10 mm : placement a verifier')
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if sep(mid):
            lo = mid
        else:
            hi = mid
    return hi


def overlap_volume(a, b):
    """Volume commun a deux solides (mm3) : 0 si elles se touchent seulement."""
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(BRepAlgoAPI_Common(a, b).Shape(), g)
    return abs(g.Mass())


def touching_faces(spec, other, tol=1.0e-3):
    """Faces laterales de l'eprouvette au contact de 'other' (pour le controle)."""
    rows = []
    e = TopExp_Explorer(spec, TopAbs_FACE)
    while e.More():
        f = TopoDS.Face(e.Current())
        b = bbox(f)
        if b[5] - b[2] > 1.0 and b[0] > -1.0e-6 and dist(f, other) < tol:   # faces laterales, X >= 0
            rows.append(b)
        e.Next()
    return sorted(rows, key=lambda r: r[1])


def main():
    spec_name = sys.argv[1] if len(sys.argv) > 1 else 'UT19'
    if spec_name not in SPECIMENS:
        sys.exit('Eprouvette inconnue : %s (choix : %s)' % (spec_name, ', '.join(SPECIMENS)))
    spec0 = load(SPECIMENS[spec_name])
    x0, y0, z0, x1, y1, z1 = bbox(spec0)
    length = x1 - x0
    t = (round(0.5 * (y0 + y1), 4), round(Y_SPEC_TIP_PUSHER - x1, 4), round(Z_SPEC_BOTTOM - z0, 4))
    y_output_bar = round(Y_SPEC_TIP_PUSHER - length + OUTPUT_BAR_TO_TIP, 4)
    print('%s : longueur %.3f mm ; placement centre : translation (%.4f, %.4f, %.4f), barre de sortie en Y = %.4f'
          % ((spec_name, length) + t + (y_output_bar,)))

    spec = move(spec0, (0, 0, 1), 90.0, (t[0], t[1], t[2] + LIFT))
    pusher = crop_y(move(load(STEP_PUSHER), (1, 0, 0), 90.0), 150.0, 260.0)
    output = crop_y(move(load(STEP_OUTPUT_BAR), (1, 0, 0), 90.0, (0, y_output_bar, Z_OUTPUT_AXIS)),
                    y_output_bar - 60.0, y_output_bar + 10.0)

    print('Distance au repos (placement centre) : pusher %.4f mm, barre de sortie %.4f mm%s'
          % (dist(spec, pusher), dist(spec, output),
             '   -> deja en contact ou recouvrement : jeu negatif possible' if min(dist(spec, pusher), dist(spec, output)) <= TOL else ''))
    g_p = gap(spec, pusher, -1.0)
    g_o = gap(spec, output, +1.0)
    print('')
    print('Jeux dans le sens de la traction :')
    print('  gap_pusher = %.4f mm   (eprouvette vers -Y jusqu au logement du pusher)' % g_p)
    print('  gap_output = %.4f mm   (eprouvette vers +Y jusqu au logement de la barre de sortie)' % g_o)

    # Controle : jeux fermes comme dans build_bench.py (CLOSE_GAPS = True)
    spec_c = move(spec, vec=(0, -round(g_p, 4), 0))
    output_c = move(output, vec=(0, -round(g_p, 4) - round(g_o, 4), 0))
    # jeu restant de l'autre cote des dents, une fois au contact (flancs non charges) : on decolle de EPS
    # du flanc charge, puis on cherche le contact dans l'autre sens
    EPS = 1.0e-3
    print('  jeu restant de l autre cote des dents, une fois au contact : pusher %.4f mm, barre de sortie %.4f mm'
          % (EPS + gap(move(spec_c, vec=(0, +EPS, 0)), pusher, +1.0),
             EPS + gap(move(spec_c, vec=(0, -EPS, 0)), output_c, -1.0)))
    print('')
    print('Controle d interpenetration (volume commun, eprouvette levee de %.1f mm) : pusher %.4f mm3, barre de sortie %.4f mm3'
          % (LIFT, overlap_volume(spec_c, pusher), overlap_volume(spec_c, output_c)))
    for name, other in (('du pusher', pusher), ('de la barre de sortie', output_c)):
        faces = touching_faces(spec_c, other)
        print('')
        print('Jeux fermes : faces laterales de l eprouvette (X >= 0) au contact %s (< 0,001 mm) :' % name)
        for b in faces:
            print('  X %6.2f .. %6.2f   Y %7.2f .. %7.2f' % (b[0], b[3], b[1], b[4]))
    print('')
    print("A recopier dans SPECIMENS['%s'] de build_bench.py : 'gap_pusher': %.4f, 'gap_output': %.4f"
          % (spec_name, g_p, g_o))


if __name__ == '__main__':
    main()
