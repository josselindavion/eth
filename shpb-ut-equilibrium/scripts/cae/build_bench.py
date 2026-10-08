# -*- coding: utf-8 -*-
"""
build_bench.py -- Construit le banc SHPB complet dans Abaqus/CAE.

Refait automatiquement ce qui a ete fait a la main :
  1. importe les pieces STEP (pusher, barre de sortie, eprouvette)
  2. cree le striker et la barre d'entree (cylindres)
  3. place les 5 instances dans le repere global
  4. (option) ne garde que la moitie X >= 0 : demi-modele, symetrie au plan X = 0
  5. sauvegarde le modele .cae

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

# Demi-modele : True = on coupe tout au plan X = 0 et on garde X >= 0
# (comme le labo : Beerli et al. 2026, Roth et al. 2015)
HALF_MODEL = True

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


def make_box(model, part_name, xmin, xmax, ymin, ymax, depth):
    """Cree une boite : rectangle dans le plan XY, extrude selon +Z."""
    s = model.ConstrainedSketch(name='__profile__',
                                sheetSize=2.0 * max(abs(ymin), abs(ymax), abs(xmin), abs(xmax)))
    s.rectangle(point1=(xmin, ymin), point2=(xmax, ymax))
    p = model.Part(name=part_name, dimensionality=THREE_D, type=DEFORMABLE_BODY)
    p.BaseSolidExtrude(sketch=s, depth=depth)
    del model.sketches['__profile__']
    return p


def cut_half(model, assembly, cutter_part, full_inst_name, half_part_name, z_min):
    """Retire la moitie X < 0 d'une instance avec une boite de decoupe.

    Abaqus cree une nouvelle part (half_part_name), definie dans le repere
    global, et son instance half_part_name + '-1'. L'instance d'origine et la
    boite sont supprimees.
    """
    cutter_name = 'CUTTER_' + half_part_name
    assembly.Instance(name=cutter_name, part=cutter_part, dependent=ON)
    assembly.translate(instanceList=(cutter_name,), vector=(0.0, 0.0, z_min))
    assembly.InstanceFromBooleanCut(name=half_part_name,
                                    instanceToBeCut=assembly.instances[full_inst_name],
                                    cuttingInstances=(assembly.instances[cutter_name],),
                                    originalInstances=DELETE)


def report_x_range(model, part_names):
    """Affiche l'etendue en X de chaque part (verification du demi-modele)."""
    print('Etendue en X des parts (demi-modele : X min doit valoir 0) :')
    for n in part_names:
        xs = [v.pointOn[0][0] for v in model.parts[n].vertices]
        print('  %-11s X min = %9.4f   X max = %9.4f' % (n, min(xs), max(xs)))


# ============================================================
# CONSTRUCTION
# ============================================================
# Modele neuf (on ecrase s'il existe deja)
if MODEL_NAME in mdb.models.keys():
    del mdb.models[MODEL_NAME]
model = mdb.Model(name=MODEL_NAME, modelType=STANDARD_EXPLICIT)

# --- 1. Parts ---
# En demi-modele, les parts completes s'appellent *_FULL ; les demi-parts
# finales (creees a l'etape 3) prennent les noms definitifs.
SUFFIX = '_FULL' if HALF_MODEL else ''
pusher     = import_step_part(model, 'PUSHER' + SUFFIX,     STEP_PUSHER)
output_bar = import_step_part(model, 'OUTPUT_BAR' + SUFFIX, STEP_OUTPUT_BAR)
specimen   = import_step_part(model, 'UT19' + SUFFIX,       STEP_SPECIMEN)
striker    = make_cylinder(model, 'STRIKER' + SUFFIX,   BAR_RADIUS, STRIKER_LENGTH)
input_bar  = make_cylinder(model, 'INPUT_BAR' + SUFFIX, BAR_RADIUS, INPUT_BAR_LENGTH)

# --- 2. Assemblage ---
a = model.rootAssembly
a.DatumCsysByDefault(CARTESIAN)
X_AXIS = (1.0, 0.0, 0.0)
Z_AXIS = (0.0, 0.0, 1.0)

place(a, pusher,     'PUSHER'     + SUFFIX + '-1', X_AXIS, 90.0, None)
place(a, input_bar,  'INPUT_BAR'  + SUFFIX + '-1', X_AXIS, 90.0, (0.0, 0.0, Z_INPUT_AXIS))
place(a, output_bar, 'OUTPUT_BAR' + SUFFIX + '-1', X_AXIS, 90.0, (0.0, Y_OUTPUT_BAR, Z_OUTPUT_AXIS))
place(a, specimen,   'UT19'       + SUFFIX + '-1', Z_AXIS, 90.0, SPECIMEN_TRANSLATION)
place(a, striker,    'STRIKER'    + SUFFIX + '-1', X_AXIS, 90.0, (0.0, -INPUT_BAR_LENGTH, Z_INPUT_AXIS))

PART_NAMES = ['STRIKER', 'INPUT_BAR', 'PUSHER', 'UT19', 'OUTPUT_BAR']

# --- 3. Demi-modele : coupe au plan X = 0 ---
if HALF_MODEL:
    # Boite qui englobe toute la zone X < 0 du banc (Y de -11 200 a +400 mm, Z de -100 a +100 mm)
    CUT_Z_MIN = -100.0
    cutter = make_box(model, 'CUTTER', xmin=-200.0, xmax=0.0,
                      ymin=-INPUT_BAR_LENGTH - STRIKER_LENGTH - 200.0, ymax=400.0,
                      depth=200.0)
    for name in PART_NAMES:
        cut_half(model, a, cutter, name + '_FULL-1', name, CUT_Z_MIN)
    # Menage : les parts completes et la boite ne servent plus
    for name in PART_NAMES:
        del model.parts[name + '_FULL']
    del model.parts['CUTTER']
    report_x_range(model, PART_NAMES)

# --- 4. Sauvegarde ---
# Supprime le modele vide 'Model-1' cree par defaut, s'il est inutilise
if 'Model-1' in mdb.models.keys() and len(mdb.models['Model-1'].parts) == 0:
    del mdb.models['Model-1']
mdb.saveAs(pathName=os.path.join(os.getcwd(), CAE_NAME))
print('Banc construit et sauvegarde dans : ' + os.path.join(os.getcwd(), CAE_NAME))
