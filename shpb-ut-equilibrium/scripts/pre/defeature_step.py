# -*- coding: utf-8 -*-
"""
defeature_step.py -- Supprime les trous M4 inutiles des fichiers STEP du banc.

Les tetes du pusher et de la barre de sortie ont chacune un trou M4 (percage diam. 3,3 mm)
au fond du logement de l'eprouvette, perce sur le plan de symetrie X = 0. Ces trous ne
servent pas pendant l'essai, mais ils creaient ~130 tetraedres deformes (datacheck du
12/10/2026). On les supprime directement dans la geometrie, AVANT Abaqus :

    cad/step/Inverter_new.step       -> cad/step/Inverter_new_noM4.step
    cad/step/Stange30mm_Step2.step   -> cad/step/Stange30mm_Step2_noM4.step

Outil : OpenCascade (BRepAlgoAPI_Defeaturing). Il retire les faces du trou et prolonge les
faces voisines ; le resultat reste UN solide ferme et valide (controle ci-dessous).
(Dans Abaqus/CAE, "Geometry Edit > Remove faces" faisait perdre le volume de la piece.)

Faces supprimees : cylindres de rayon 1,65 mm (paroi du trou) et cones de rayon 1,65 mm
(pointe de foret) -- ce sont les seules faces de ce rayon dans ces deux pieces.

Lancement (Python 3, depuis la racine du repo) :
    pip install cadquery-ocp        (une seule fois : bibliotheque OpenCascade)
    python shpb-ut-equilibrium/scripts/pre/defeature_step.py
Les fichiers _noM4.step sont versionnes : il n'est utile de relancer ce script que si
les STEP d'origine changent.
"""
import os

from OCP.STEPControl import STEPControl_Reader, STEPControl_Writer, STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID
from OCP.TopoDS import TopoDS
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Cone
from OCP.BRepAlgoAPI import BRepAlgoAPI_Defeaturing
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.Interface import Interface_Static

# ============================================================
# PARAMETRES
# ============================================================
HOLE_RADIUS = 1.65      # mm, rayon de percage d'un taraudage M4
TOL = 1.0e-3            # mm, tolerance sur le rayon
FILES = [               # (STEP d'origine, STEP sans trou, nb de faces attendues)
    ('Inverter_new.step',     'Inverter_new_noM4.step',     4),   # 2 demi-cylindres + 2 demi-cones
    ('Stange30mm_Step2.step', 'Stange30mm_Step2_noM4.step', 2),   # trou debouchant : 2 demi-cylindres
]

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
STEP_DIR = os.path.abspath(os.path.join(THIS_DIR, '..', '..', 'cad', 'step'))


# ============================================================
# FONCTIONS
# ============================================================
def read_step(path):
    r = STEPControl_Reader()
    if r.ReadFile(path) != IFSelect_RetDone:
        raise IOError('Lecture impossible : ' + path)
    r.TransferRoots()
    return r.OneShape()


def write_step(shape, path):
    Interface_Static.SetCVal_s('write.step.unit', 'MM')
    Interface_Static.SetCVal_s('write.step.schema', 'AP214IS')
    w = STEPControl_Writer()
    w.Transfer(shape, STEPControl_AsIs)
    if w.Write(path) != IFSelect_RetDone:
        raise IOError('Ecriture impossible : ' + path)


def count(shape, kind):
    e, n = TopExp_Explorer(shape, kind), 0
    while e.More():
        n += 1
        e.Next()
    return n


def volume(shape):
    p = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, p)
    return p.Mass()


def hole_faces(shape):
    """Faces cylindriques ou coniques de rayon HOLE_RADIUS."""
    faces = []
    e = TopExp_Explorer(shape, TopAbs_FACE)
    while e.More():
        f = TopoDS.Face(e.Current())
        s = BRepAdaptor_Surface(f)
        if s.GetType() == GeomAbs_Cylinder and abs(s.Cylinder().Radius() - HOLE_RADIUS) < TOL:
            faces.append(f)
        elif s.GetType() == GeomAbs_Cone and abs(s.Cone().RefRadius() - HOLE_RADIUS) < TOL:
            faces.append(f)
        e.Next()
    return faces


# ============================================================
# TRAITEMENT
# ============================================================
print('%-28s %6s %8s %12s %12s %10s  %s' % ('fichier', 'faces', 'solides', 'vol. avant', 'vol. apres',
                                              'ajoute', 'valide'))
for src, dst, expected in FILES:
    shape = read_step(os.path.join(STEP_DIR, src))
    faces = hole_faces(shape)
    if len(faces) != expected:
        raise RuntimeError('%s : %d faces de trou trouvees, %d attendues' % (src, len(faces), expected))

    d = BRepAlgoAPI_Defeaturing()
    d.SetShape(shape)
    for f in faces:
        d.AddFaceToRemove(f)
    d.SetRunParallel(False)
    d.Build()
    if not d.IsDone():
        raise RuntimeError(src + ' : echec du defeaturing')
    out = d.Shape()

    # Controles : un seul solide, valide, et un volume qui augmente du volume du trou
    if count(out, TopAbs_SOLID) != 1 or not BRepCheck_Analyzer(out).IsValid():
        raise RuntimeError(src + ' : le resultat n\'est pas un solide valide')
    path = os.path.join(STEP_DIR, dst)
    write_step(out, path)
    back = read_step(path)                       # relecture du fichier ecrit
    print('%-28s %6d %8d %12.2f %12.2f %10.2f  %s' % (
        dst, len(faces), count(back, TopAbs_SOLID), volume(shape), volume(back),
        volume(back) - volume(shape), BRepCheck_Analyzer(back).IsValid()))
print('Volume ajoute attendu : pusher ~101 mm3 (cylindre 11,5 mm + cone), barre ~62 mm3 (7,25 mm)')
