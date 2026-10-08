# -*- coding: utf-8 -*-
"""
build_bench.py -- Construit le banc SHPB complet dans Abaqus/CAE.

Refait automatiquement ce qui a ete fait a la main :
  1. importe les pieces STEP (pusher, barre de sortie, eprouvette)
  2. cree le striker et la barre d'entree (cylindres)
  3. place les 5 instances dans le repere global
  4. sauvegarde le modele .cae

Repere global : Y = axe des barres / traction, Z = vers le haut,
                X = largeur de l'eprouvette. Unites : mm.

Lancement (depuis le dossier de travail Abaqus) :
  - dans CAE   : File > Run Script... > choisir ce fichier
  - sans GUI   : abaqus cae noGUI=<chemin>/scripts/cae/build_bench.py

ATTENTION : Abaqus 2023 utilise Python 2.7 -> pas de f-strings.
"""
from abaqus import *
from abaqusConstants import *
import os
import inspect

# ============================================================
# PARAMETRES  (le seul endroit a modifier)
# ============================================================
MODEL_NAME = 'SHPB_UT19'

# Fichiers STEP (dans <repo>/cad/step/)
STEP_PUSHER     = 'Inverter_new.step'
STEP_OUTPUT_BAR = 'Stange30mm_Step2.step'
STEP_SPECIMEN   = 'XMas_UT_t1p5.step'

# Barres cylindriques (Beerli et al. 2026, section 2.5)
BAR_RADIUS        = 10.0      # mm  (diametre 20 mm)
STRIKER_LENGTH    = 5000.0    # mm
INPUT_BAR_LENGTH  = 6010.0    # mm

# Positions (voir docs/assembly.md)
Z_INPUT_AXIS  = 7.85                     # centre de la face du pusher (20 x 15.7 mm)
Z_OUTPUT_AXIS = Z_INPUT_AXIS + 21.5      # = 29.35, decalage des axes (fig. 5a)
Y_OUTPUT_BAR  = 155.713                  # avance de la barre de sortie
SPECIMEN_TRANSLATION = (356.2728, -1357.7622, 28.6)   # eprouvette centree dans les logements

# Nom du fichier .cae sauvegarde (dans le dossier de travail courant)
CAE_NAME = MODEL_NAME + '.cae'

# ============================================================
# CHEMINS : on retrouve la racine du repo a partir de ce script
# ============================================================
THIS_DIR  = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
STEP_DIR  = os.path.join(REPO_ROOT, 'cad', 'step')


# ============================================================
# FONCTIONS
# ============================================================
def import_step_part(model, part_name, step_file):
    """Importe un fichier STEP comme part deformable 3D."""
    path = os.path.join(STEP_DIR, step_file)
    if not os.path.exists(path):
        raise IOError('Fichier STEP introuvable : ' + path)
    geom = mdb.openStep(path, scaleFromFile=OFF)
    return model.PartFromGeometryFile(name=part_name, geometryFile=geom,
                                      combine=False, dimensionality=THREE_D,
                                      type=DEFORMABLE_BODY)


def make_cylinder(model, part_name, radius, length):
    """Cree un cylindre plein : cercle dans le plan XY, extrude selon +Z."""
    s = model.ConstrainedSketch(name='__profile__', sheetSize=4.0 * radius)
    s.CircleByCenterPerimeter(center=(0.0, 0.0), point1=(radius, 0.0))
    p = model.Part(name=part_name, dimensionality=THREE_D, type=DEFORMABLE_BODY)
    p.BaseSolidExtrude(sketch=s, depth=length)
    del model.sketches['__profile__']
    return p


def place(assembly, part, inst_name, rot_axis=None, angle=0.0, vector=None):
    """Cree une instance, la tourne autour d'un axe passant par l'origine, puis la translate."""
    assembly.Instance(name=inst_name, part=part, dependent=ON)
    if rot_axis is not None:
        assembly.rotate(instanceList=(inst_name,), axisPoint=(0.0, 0.0, 0.0),
                        axisDirection=rot_axis, angle=angle)
    if vector is not None:
        assembly.translate(instanceList=(inst_name,), vector=vector)


# ============================================================
# CONSTRUCTION
# ============================================================
# Modele neuf (on ecrase s'il existe deja)
if MODEL_NAME in mdb.models.keys():
    del mdb.models[MODEL_NAME]
model = mdb.Model(name=MODEL_NAME, modelType=STANDARD_EXPLICIT)

# --- 1. Parts ---
pusher     = import_step_part(model, 'PUSHER',     STEP_PUSHER)
output_bar = import_step_part(model, 'OUTPUT_BAR', STEP_OUTPUT_BAR)
specimen   = import_step_part(model, 'UT19',       STEP_SPECIMEN)
striker    = make_cylinder(model, 'STRIKER',   BAR_RADIUS, STRIKER_LENGTH)
input_bar  = make_cylinder(model, 'INPUT_BAR', BAR_RADIUS, INPUT_BAR_LENGTH)

# --- 2. Assemblage ---
a = model.rootAssembly
a.DatumCsysByDefault(CARTESIAN)
X_AXIS = (1.0, 0.0, 0.0)
Z_AXIS = (0.0, 0.0, 1.0)

place(a, pusher,     'PUSHER-1',     X_AXIS, 90.0, None)
place(a, input_bar,  'INPUT_BAR-1',  X_AXIS, 90.0, (0.0, 0.0, Z_INPUT_AXIS))
place(a, output_bar, 'OUTPUT_BAR-1', X_AXIS, 90.0, (0.0, Y_OUTPUT_BAR, Z_OUTPUT_AXIS))
place(a, specimen,   'UT19-1',       Z_AXIS, 90.0, SPECIMEN_TRANSLATION)
place(a, striker,    'STRIKER-1',    X_AXIS, 90.0, (0.0, -INPUT_BAR_LENGTH, Z_INPUT_AXIS))

# --- 3. Sauvegarde ---
# Supprime le modele vide 'Model-1' cree par defaut, s'il est inutilise
if 'Model-1' in mdb.models.keys() and len(mdb.models['Model-1'].parts) == 0:
    del mdb.models['Model-1']
mdb.saveAs(pathName=os.path.join(os.getcwd(), CAE_NAME))
print('Banc construit et sauvegarde dans : ' + os.path.join(os.getcwd(), CAE_NAME))
