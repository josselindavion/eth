# -*- coding: utf-8 -*-
"""
build_bench.py -- Construit et maille le banc SHPB complet dans Abaqus/CAE.

Etapes :
  1. importe les pieces STEP (pusher, barre de sortie, eprouvette)
     et cree le striker et la barre d'entree (cylindres)
  2. place les pieces dans le repere global
  3. decoupe : demi-modele (on garde X >= 0) et separation des pieces complexes
     en une partie simple (hexaedres) et une tete (tetraedres) :
        PUSHER     -> PUSHER_ROD  (Y <= 125) + PUSHER_HEAD  (Y >= 125)
        OUTPUT_BAR -> OUTPUT_BAR  (Y <= 100, cylindre recree) + OUTPUT_HEAD  (Y >= 100, STEP)
     Les interfaces Y = 125 et Y = 100 seront collees par des contraintes TIE.
  4. maille toutes les pieces (Abaqus/Explicit) ; l'eprouvette est d'abord decoupee
     au debut et a la fin de la partie droite de la zone utile (grille reguliere)
  5. cree les groupes nommes : <PIECE>_ALL, XSYMM, et pour l'eprouvette SEC_IN,
     SEC_OUT (sections de mesure de force) et GAUGE_ZONE ; puis les surfaces
     d'interface : S_TIE, S_IMPACT, S_PUSH, S_SKIN (voir docs/mesh.md)
  6. sauvegarde le modele .cae

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
import mesh

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
OUTPUT_BAR_LENGTH = 6000.0    # mm, longueur totale du STEP (tete comprise)
# La partie ronde de la barre de sortie est recreee en cylindre plein : le STEP a, au bout
# eloigne, un trou taraude (diametre 8.5 x 27.5 mm) qui empeche le maillage balaye.
# Ce detail (0.08 % du volume, a 6 m de l'eprouvette) est volontairement supprime.

# Positions (voir docs/assembly.md)
Z_INPUT_AXIS  = 7.85                     # centre de la face du pusher (20 x 15.7 mm)
Z_OUTPUT_AXIS = Z_INPUT_AXIS + 21.5      # = 29.35, decalage des axes (fig. 5a)
Y_OUTPUT_BAR  = 155.713                  # avance de la barre de sortie
SPECIMEN_TRANSLATION = (356.2728, -1357.7622, 28.6)   # eprouvette centree dans les logements

# Demi-modele : True = on coupe tout au plan X = 0 et on garde X >= 0
# (comme le labo : Beerli et al. 2026, Roth et al. 2015)
HALF_MODEL = True

# Decoupe des pieces complexes (plans perpendiculaires a Y)
Y_SPLIT_PUSHER = 125.0    # corps rectangulaire du pusher : Y de 0 a 130
Y_SPLIT_OUTPUT = 100.0    # partie ronde de la barre de sortie : Y < 105.05

# Maillage des barres (Roth et al. 2015, Beerli et al. 2026) : hexaedres C3D8R balayes
BAR_SEED_AXIAL   = 5.0    # mm, taille des elements dans l'axe des barres
BAR_SEED_SECTION = 2.0    # mm, taille des elements dans la section

# Maillage de l'eprouvette (Roth et al. 2015) : 0.5 mm dans le plan, 4 elements dans l'epaisseur
SPEC_SEED_INPLANE = 0.5   # mm
SPEC_N_THICKNESS  = 4     # nombre d'elements dans l'epaisseur
# Demi-largeur de la partie droite de la zone utile (sUT : 5 mm de large, Beerli 2026 fig. 2a).
# Sert a reperer, sur la geometrie, le debut et la fin de la partie droite.
SPEC_GAUGE_HALF_WIDTH = 2.5   # mm

# Jauges virtuelles et extensometre (Beerli et al. 2026, section 2.5 et fig. 5a)
GAUGE_IN_DIST   = 400.0   # mm, jauge d'entree : distance depuis l'interface striker / barre d'entree
GAUGE_OUT_DIST  = 400.0   # mm, jauge de sortie : distance depuis le bout de la barre de sortie cote eprouvette
GAUGE_LENGTH    = 10.0    # mm, longueur de barre moyennee par une jauge virtuelle
EXT_LENGTH      = 12.0    # mm, longueur de l'extensometre virtuel (zone DIC de la sUT : 12 mm)

# Maillage des tetes (pusher, barre de sortie) : tetraedres quadratiques C3D10M
HEAD_SEED = 2.0           # mm (taille utilisee par Roth et al. 2015 pour le pusher et la barre de sortie)

# Nom du fichier .cae sauvegarde (dans le dossier de travail courant)
CAE_NAME = MODEL_NAME + '.cae'

# .inp brut ecrit par CAE (maillage + groupes), converti ensuite en .geo par scripts/pre/inp_to_geo.py
RAW_INP_NAME = MODEL_NAME + '_mesh'      # -> model/geometry/_raw/SHPB_UT19_mesh.inp

# ============================================================
# CHEMINS : on retrouve la racine du repo a partir de ce script
# ============================================================
THIS_DIR  = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
REPO_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
STEP_DIR  = os.path.join(REPO_ROOT, 'cad', 'step')
RAW_DIR   = os.path.join(REPO_ROOT, 'model', 'geometry', '_raw')

# Etendue du banc (pour les boites de decoupe)
BIG_X = 200.0
Y_LOW  = -INPUT_BAR_LENGTH - STRIKER_LENGTH - 200.0
Y_HIGH = 400.0
Z_LOW, Z_HIGH = -100.0, 100.0


# ============================================================
# FONCTIONS : GEOMETRIE
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


def add_box(model, assembly, name, xmin, xmax, ymin, ymax, zmin, zmax):
    """Cree une boite de decoupe (part + instance) aux coordonnees globales donnees."""
    s = model.ConstrainedSketch(name='__profile__',
                                sheetSize=2.0 * max(abs(xmin), abs(xmax), abs(ymin), abs(ymax)))
    s.rectangle(point1=(xmin, ymin), point2=(xmax, ymax))
    p = model.Part(name=name, dimensionality=THREE_D, type=DEFORMABLE_BODY)
    p.BaseSolidExtrude(sketch=s, depth=zmax - zmin)
    del model.sketches['__profile__']
    assembly.Instance(name=name, part=p, dependent=ON)
    assembly.translate(instanceList=(name,), vector=(0.0, 0.0, zmin))
    return name


def make_piece(model, assembly, piece_name, full_part, placement, y_min=None, y_max=None):
    """Cree une piece finale a partir d'une part complete placee dans le banc.

    On place une copie de la part complete, puis on retire avec des boites :
      - la zone X < 0 (si HALF_MODEL),
      - la zone Y < y_min et/ou Y > y_max (si demandees).
    La piece finale est une nouvelle part piece_name, definie dans le repere global,
    avec l'instance piece_name + '-1'.
    """
    rot_axis, angle, vector = placement
    tmp = piece_name + '_TMP'
    place(assembly, full_part, tmp, rot_axis, angle, vector)

    boxes = []
    if HALF_MODEL:
        boxes.append(add_box(model, assembly, 'BOX_' + piece_name + '_X',
                             -BIG_X, 0.0, Y_LOW, Y_HIGH, Z_LOW, Z_HIGH))
    if y_min is not None:
        boxes.append(add_box(model, assembly, 'BOX_' + piece_name + '_YLO',
                             -BIG_X, BIG_X, Y_LOW, y_min, Z_LOW, Z_HIGH))
    if y_max is not None:
        boxes.append(add_box(model, assembly, 'BOX_' + piece_name + '_YHI',
                             -BIG_X, BIG_X, y_max, Y_HIGH, Z_LOW, Z_HIGH))

    if boxes:
        assembly.InstanceFromBooleanCut(name=piece_name,
                                        instanceToBeCut=assembly.instances[tmp],
                                        cuttingInstances=tuple(assembly.instances[b] for b in boxes),
                                        originalInstances=DELETE)
        for b in boxes:
            del model.parts[b]
    else:
        # Rien a couper : on garde la part complete sous son nom final
        model.parts.changeKey(fromName=full_part.name, toName=piece_name)
        assembly.features.changeKey(fromName=tmp, toName=piece_name + '-1')


def report_x_range(model, part_names):
    """Affiche l'etendue en X et Y de chaque part."""
    print('Etendue des pieces (demi-modele : X min doit valoir 0) :')
    for n in part_names:
        pts = [v.pointOn[0] for v in model.parts[n].vertices]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        print('  %-12s X = %8.3f .. %8.3f    Y = %10.3f .. %9.3f'
              % (n, min(xs), max(xs), min(ys), max(ys)))


# ============================================================
# FONCTIONS : MAILLAGE
# ============================================================
def y_range(part):
    """Y min et Y max des sommets d'une part (axe des barres)."""
    ys = [v.pointOn[0][1] for v in part.vertices]
    return min(ys), max(ys)


def set_c3d8r(part):
    """Hexaedres lineaires C3D8R (Explicit).

    setElementType attend toujours un triplet (hexaedre, prisme, tetraedre) ;
    Abaqus applique a chaque element le type de sa forme.
    """
    et_hex = mesh.ElemType(elemCode=C3D8R, elemLibrary=EXPLICIT,
                           kinematicSplit=AVERAGE_STRAIN, hourglassControl=DEFAULT,
                           distortionControl=DEFAULT)
    et_wedge = mesh.ElemType(elemCode=C3D6, elemLibrary=EXPLICIT)
    et_tet = mesh.ElemType(elemCode=C3D4, elemLibrary=EXPLICIT)
    part.setElementType(regions=(part.cells,), elemTypes=(et_hex, et_wedge, et_tet))


def set_c3d10m(part):
    """Tetraedres quadratiques modifies C3D10M (Explicit).

    Syntaxe reprise telle quelle du journal abaqus.rpy (Mesh > Element Type,
    Explicit, Quadratic) : en quadratique, la bibliotheque Explicit n'a ni
    hexaedre ni prisme, d'ou UNKNOWN_HEX et UNKNOWN_WEDGE. On ne peut pas
    mettre un C3D8R (lineaire) dans le meme triplet.
    """
    et_hex = mesh.ElemType(elemCode=UNKNOWN_HEX, elemLibrary=EXPLICIT)
    et_wedge = mesh.ElemType(elemCode=UNKNOWN_WEDGE, elemLibrary=EXPLICIT)
    et_tet = mesh.ElemType(elemCode=C3D10M, elemLibrary=EXPLICIT,
                           secondOrderAccuracy=OFF, distortionControl=DEFAULT)
    part.setElementType(regions=(part.cells,), elemTypes=(et_hex, et_wedge, et_tet))


def mesh_bar(part, seed_axial, seed_section):
    """Maille une barre d'axe Y en hexaedres balayes (sweep) le long de l'axe.

    - graine globale = seed_axial (taille dans l'axe, sur les grandes aretes)
    - graine locale = seed_section sur les aretes des deux faces d'extremite,
      qui fixent le maillage de la section
    """
    part.setMeshControls(regions=part.cells, elemShape=HEX, technique=SWEEP,
                         algorithm=ADVANCING_FRONT)
    part.seedPart(size=seed_axial, deviationFactor=0.1, minSizeFactor=0.1)
    y0, y1 = y_range(part)
    big = 1.0e4
    for y in (y0, y1):
        end_edges = part.edges.getByBoundingBox(-big, y - 0.5, -big, big, y + 0.5, big)
        part.seedEdgeBySize(edges=end_edges, size=seed_section,
                            deviationFactor=0.1, constraint=FINER)
    set_c3d8r(part)
    part.generateMesh()


def thickness_edges(part, tol=1.0e-6):
    """Aretes droites paralleles a Z (dans l'epaisseur de la tole)."""
    pts = []
    for e in part.edges:
        iv = e.getVertices()
        if len(iv) != 2:
            continue
        a = part.vertices[iv[0]].pointOn[0]
        b = part.vertices[iv[1]].pointOn[0]
        if abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol and abs(a[2] - b[2]) > tol:
            pts.append((e.pointOn[0],))
    return part.edges.findAt(*pts)


def partition_specimen_gauge(part, half_width, tol=1.0e-3):
    """Decoupe l'eprouvette par deux plans Y = cte au debut et a la fin de la partie droite.

    Les positions sont lues sur la geometrie : ce sont les Y extremes des sommets
    situes sur le bord droit de la zone utile (|X| = half_width).
    Renvoie (y_out, y_in) : Y bas (cote barre de sortie) et Y haut (cote pusher).
    """
    ys = [v.pointOn[0][1] for v in part.vertices
          if abs(abs(v.pointOn[0][0]) - half_width) < tol]
    if len(ys) < 2:
        raise ValueError('Partie droite de la zone utile introuvable (|X| = %g)' % half_width)
    y_out, y_in = min(ys), max(ys)
    for y in (y_out, y_in):
        dp = part.DatumPlaneByPrincipalPlane(principalPlane=XZPLANE, offset=y)
        part.PartitionCellByDatumPlane(datumPlane=part.datums[dp.id], cells=part.cells)
    return y_out, y_in


def mesh_specimen(part, seed_inplane, n_thickness, y_out, y_in):
    """Maille l'eprouvette decoupee : partie droite en grille reguliere (STRUCTURED),
    tetes balayees dans l'epaisseur (SWEEP). 4 elements dans l'epaisseur partout."""
    big = 1.0e4
    part.setMeshControls(regions=part.cells, elemShape=HEX, technique=SWEEP,
                         algorithm=ADVANCING_FRONT)
    gauge = part.cells.getByBoundingBox(-big, y_out - 1.0e-3, -big, big, y_in + 1.0e-3, big)
    part.setMeshControls(regions=gauge, elemShape=HEX, technique=STRUCTURED)
    part.seedPart(size=seed_inplane, deviationFactor=0.1, minSizeFactor=0.1)
    part.seedEdgeByNumber(edges=thickness_edges(part), number=n_thickness, constraint=FIXED)
    set_c3d8r(part)
    part.generateMesh()


def make_basic_sets(model, part_names, tol=1.0e-4):
    """Groupes de base de chaque piece :
      <PIECE>_ALL : tous les elements (pour *SOLID SECTION)
      XSYMM       : faces en X = 0 (symetrie du demi-modele)"""
    big = 1.0e5
    for n in part_names:
        p = model.parts[n]
        p.Set(name=n + '_ALL', cells=p.cells)
        if HALF_MODEL:
            p.Set(name='XSYMM', faces=p.faces.getByBoundingBox(-tol, -big, -big, tol, big, big))


def make_specimen_sets(part, y_out, y_in, tol=1.0e-4):
    """Groupes de l'eprouvette :
      SEC_OUT (surface) : section en Y = y_out, debut de la partie droite cote barre de sortie
      SEC_IN  (surface) : section en Y = y_in, fin de la partie droite cote pusher
      GAUGE_ZONE (set)  : elements de la partie droite"""
    big = 1.0e5
    for name, y in (('SEC_OUT', y_out), ('SEC_IN', y_in)):
        faces = part.faces.getByBoundingBox(-big, y - tol, -big, big, y + tol, big)
        part.Surface(name=name, side1Faces=faces)
    part.Set(name='GAUGE_ZONE',
             cells=part.cells.getByBoundingBox(-big, y_out - tol, -big, big, y_in + tol, big))


def faces_at_y(part, y, tol=1.0e-4):
    """Faces planes situees dans le plan Y = y."""
    big = 1.0e5
    return part.faces.getByBoundingBox(-big, y - tol, -big, big, y + tol, big)


def skin_faces(part, tol=1.0e-6):
    """Peau exterieure d'une piece, pour le contact :
    - sans les faces internes (creees par les decoupes, partagees par 2 volumes)
    - sans les faces du plan de symetrie X = 0"""
    pts = []
    for f in part.faces:
        if len(f.getCells()) != 1:
            continue                                   # face interne
        xs = [part.vertices[i].pointOn[0][0] for i in f.getVertices()]
        if xs and max(abs(x) for x in xs) < tol:
            continue                                   # face du plan X = 0
        pts.append((f.pointOn[0],))
    return part.faces.findAt(*pts)


def make_interface_surfaces(model, y_impact, y_push, y_tie_pusher, y_tie_output):
    """Surfaces des interfaces entre pieces.

    TIE (collage), meme nom des deux cotes, qualifie par l'instance dans le .inp :
      PUSHER_ROD.S_TIE / PUSHER_HEAD.S_TIE   en Y = y_tie_pusher
      OUTPUT_BAR.S_TIE / OUTPUT_HEAD.S_TIE   en Y = y_tie_output
    Contact bout a bout :
      STRIKER.S_IMPACT / INPUT_BAR.S_IMPACT  en Y = y_impact (impact du striker)
      INPUT_BAR.S_PUSH / PUSHER_ROD.S_PUSH   en Y = y_push   (barre d'entree -> pusher)
    Contact eprouvette / logements (peau exterieure) :
      UT19.S_SKIN, PUSHER_HEAD.S_SKIN, OUTPUT_HEAD.S_SKIN
    """
    P = model.parts
    for name, y in (('PUSHER_ROD', y_tie_pusher), ('PUSHER_HEAD', y_tie_pusher),
                    ('OUTPUT_BAR', y_tie_output), ('OUTPUT_HEAD', y_tie_output)):
        P[name].Surface(name='S_TIE', side1Faces=faces_at_y(P[name], y))
    for name in ('STRIKER', 'INPUT_BAR'):
        P[name].Surface(name='S_IMPACT', side1Faces=faces_at_y(P[name], y_impact))
    for name in ('INPUT_BAR', 'PUSHER_ROD'):
        P[name].Surface(name='S_PUSH', side1Faces=faces_at_y(P[name], y_push))
    for name in ('UT19', 'PUSHER_HEAD', 'OUTPUT_HEAD'):
        P[name].Surface(name='S_SKIN', side1Faces=skin_faces(P[name]))


def report_surfaces(model, part_names):
    """Bilan des surfaces : nombre de faces geometriques et de facettes d'elements."""
    print('Surfaces :')
    for n in part_names:
        p = model.parts[n]
        for s in sorted(p.surfaces.keys()):
            surf = p.surfaces[s]
            print('  %-12s %-9s %4d faces  %6d facettes d\'elements'
                  % (n, s, len(surf.faces), len(surf.elements)))


def element_set_near_y(part, set_name, y_target, length):
    """Set des elements dont le centre est a moins de length/2 du plan Y = y_target."""
    labels = []
    for e in part.elements:
        ys = [n.coordinates[1] for n in e.getNodes()]
        if abs(sum(ys) / len(ys) - y_target) <= 0.5 * length:
            labels.append(e.label)
    if not labels:
        raise ValueError('Aucun element pres de Y = %g dans %s' % (y_target, part.name))
    part.SetFromElementLabels(name=set_name, elementLabels=labels)
    return len(labels)


def node_set_at(part, set_name, point, tol=1.0e-3):
    """Set d'un seul noeud : celui situe au point donne (a tol pres)."""
    nodes = part.nodes.getByBoundingSphere(center=point, radius=tol)
    if len(nodes) != 1:
        raise ValueError('%d noeud(s) trouve(s) en %s pour %s' % (len(nodes), str(point), set_name))
    part.SetFromNodeLabels(name=set_name, nodeLabels=(nodes[0].label,))
    return nodes[0].label


def make_measurement_sets(model, y_gauge_in, y_gauge_out, y_sec_out, y_sec_in):
    """Jauges virtuelles (GAUGE_IN, GAUGE_OUT) et extensometre (EXT_OUT, EXT_IN)."""
    print('Mesures virtuelles :')
    n = element_set_near_y(model.parts['INPUT_BAR'], 'GAUGE_IN', y_gauge_in, GAUGE_LENGTH)
    print('  GAUGE_IN   INPUT_BAR   Y = %9.3f   %4d elements' % (y_gauge_in, n))
    n = element_set_near_y(model.parts['OUTPUT_BAR'], 'GAUGE_OUT', y_gauge_out, GAUGE_LENGTH)
    print('  GAUGE_OUT  OUTPUT_BAR  Y = %9.3f   %4d elements' % (y_gauge_out, n))
    # Extensometre : sur le dessus de l'eprouvette, au milieu de la largeur (X = 0),
    # centre sur la partie droite de la zone utile
    spec = model.parts['UT19']
    z_top = max(v.pointOn[0][2] for v in spec.vertices)
    y_mid = 0.5 * (y_sec_out + y_sec_in)
    for name, y in (('EXT_OUT', y_mid - 0.5 * EXT_LENGTH), ('EXT_IN', y_mid + 0.5 * EXT_LENGTH)):
        label = node_set_at(spec, name, (0.0, y, z_top))
        print('  %-9s  UT19        Y = %9.3f   noeud %d' % (name, y, label))


def report_sets(model, part_names):
    """Bilan des groupes crees."""
    print('Groupes :')
    for n in part_names:
        p = model.parts[n]
        line = '  %-12s %s_ALL : %6d elements' % (n, n, len(p.sets[n + '_ALL'].elements))
        if 'XSYMM' in p.sets.keys():
            line += '   XSYMM : %5d noeuds' % len(p.sets['XSYMM'].nodes)
        print(line)


def mesh_tet(part, seed):
    """Maille une piece de forme complexe en tetraedres quadratiques (maillage libre)."""
    part.setMeshControls(regions=part.cells, elemShape=TET, technique=FREE)
    part.seedPart(size=seed, deviationFactor=0.1, minSizeFactor=0.1)
    set_c3d10m(part)
    part.generateMesh()


def report_mesh(model, part_names):
    """Affiche le nombre de noeuds et d'elements de chaque part."""
    print('Maillage :')
    total = 0
    for n in part_names:
        p = model.parts[n]
        total += len(p.elements)
        types = sorted(set(str(e.type) for e in p.elements))
        print('  %-12s %8d elements  %8d noeuds   type : %s'
              % (n, len(p.elements), len(p.nodes), ', '.join(types)))
    print('  %-12s %8d elements' % ('TOTAL', total))


# ============================================================
# CONSTRUCTION
# ============================================================
# Modele neuf (on ecrase s'il existe deja)
if MODEL_NAME in mdb.models.keys():
    del mdb.models[MODEL_NAME]
model = mdb.Model(name=MODEL_NAME, modelType=STANDARD_EXPLICIT)
a = model.rootAssembly
a.DatumCsysByDefault(CARTESIAN)

# --- 1. Parts completes ---
full = {
    'PUSHER':     import_step_part(model, 'PUSHER_FULL',     STEP_PUSHER),
    'OUTPUT_BAR': import_step_part(model, 'OUTPUT_BAR_FULL', STEP_OUTPUT_BAR),
    'UT19':       import_step_part(model, 'UT19_FULL',       STEP_SPECIMEN),
    'STRIKER':    make_cylinder(model, 'STRIKER_FULL',   BAR_RADIUS, STRIKER_LENGTH),
    'INPUT_BAR':  make_cylinder(model, 'INPUT_BAR_FULL', BAR_RADIUS, INPUT_BAR_LENGTH),
    'OUTPUT_ROD': make_cylinder(model, 'OUTPUT_ROD_FULL', BAR_RADIUS, OUTPUT_BAR_LENGTH),
}

# --- 2. Placement : (axe de rotation, angle, translation) ---
X_AXIS = (1.0, 0.0, 0.0)
Z_AXIS = (0.0, 0.0, 1.0)
placement = {
    'STRIKER':    (X_AXIS, 90.0, (0.0, -INPUT_BAR_LENGTH, Z_INPUT_AXIS)),
    'INPUT_BAR':  (X_AXIS, 90.0, (0.0, 0.0, Z_INPUT_AXIS)),
    'PUSHER':     (X_AXIS, 90.0, None),
    'UT19':       (Z_AXIS, 90.0, SPECIMEN_TRANSLATION),
    'OUTPUT_BAR': (X_AXIS, 90.0, (0.0, Y_OUTPUT_BAR, Z_OUTPUT_AXIS)),
    'OUTPUT_ROD': (X_AXIS, 90.0, (0.0, Y_OUTPUT_BAR, Z_OUTPUT_AXIS)),   # meme axe que la barre du STEP
}

# --- 3. Pieces finales : (nom, part complete, Y min garde, Y max garde) ---
PIECES = [
    ('STRIKER',     'STRIKER',    None,           None),
    ('INPUT_BAR',   'INPUT_BAR',  None,           None),
    ('PUSHER_ROD',  'PUSHER',     None,           Y_SPLIT_PUSHER),
    ('PUSHER_HEAD', 'PUSHER',     Y_SPLIT_PUSHER, None),
    ('UT19',        'UT19',       None,           None),
    ('OUTPUT_BAR',  'OUTPUT_ROD', None,           Y_SPLIT_OUTPUT),   # cylindre plein, sans le trou taraude
    ('OUTPUT_HEAD', 'OUTPUT_BAR', Y_SPLIT_OUTPUT, None),
]
for piece_name, src, y_min, y_max in PIECES:
    make_piece(model, a, piece_name, full[src], placement[src], y_min, y_max)

# Menage : les parts completes ne servent plus (sauf si renommees directement)
for name in list(model.parts.keys()):
    if name.endswith('_FULL'):
        del model.parts[name]

PIECE_NAMES = [pc[0] for pc in PIECES]
report_x_range(model, PIECE_NAMES)

# --- 4. Maillage ---
for name in ['STRIKER', 'INPUT_BAR', 'PUSHER_ROD', 'OUTPUT_BAR']:
    mesh_bar(model.parts[name], BAR_SEED_AXIAL, BAR_SEED_SECTION)
spec = model.parts['UT19']
y_sec_out, y_sec_in = partition_specimen_gauge(spec, SPEC_GAUGE_HALF_WIDTH)
mesh_specimen(spec, SPEC_SEED_INPLANE, SPEC_N_THICKNESS, y_sec_out, y_sec_in)
for name in ['PUSHER_HEAD', 'OUTPUT_HEAD']:
    mesh_tet(model.parts[name], HEAD_SEED)
report_mesh(model, PIECE_NAMES)

# --- 5. Groupes nommes ---
make_basic_sets(model, PIECE_NAMES)
make_specimen_sets(spec, y_sec_out, y_sec_in)
make_interface_surfaces(model, y_impact=-INPUT_BAR_LENGTH, y_push=0.0,
                        y_tie_pusher=Y_SPLIT_PUSHER, y_tie_output=Y_SPLIT_OUTPUT)
report_sets(model, PIECE_NAMES)
report_surfaces(model, PIECE_NAMES)
make_measurement_sets(model,
                      y_gauge_in=-INPUT_BAR_LENGTH + GAUGE_IN_DIST,
                      y_gauge_out=Y_OUTPUT_BAR - GAUGE_OUT_DIST,
                      y_sec_out=y_sec_out, y_sec_in=y_sec_in)
print('Eprouvette : partie droite de Y = %.3f (SEC_OUT) a Y = %.3f (SEC_IN), longueur %.3f mm, '
      '%d elements dans GAUGE_ZONE'
      % (y_sec_out, y_sec_in, y_sec_in - y_sec_out, len(spec.sets['GAUGE_ZONE'].elements)))

# --- 6. Sauvegarde ---
# Supprime le modele vide 'Model-1' cree par defaut, s'il est inutilise
if 'Model-1' in mdb.models.keys() and len(mdb.models['Model-1'].parts) == 0:
    del mdb.models['Model-1']
mdb.saveAs(pathName=os.path.join(os.getcwd(), CAE_NAME))
print('Banc construit et sauvegarde dans : ' + os.path.join(os.getcwd(), CAE_NAME))

# ============================================================
# EXPORT DU .inp BRUT (maillage + groupes + surfaces)
# ============================================================
# writeInput ecrit le .inp dans le dossier courant : on se place temporairement dans _raw.
# consistencyChecking=OFF : le modele n'a encore ni section, ni step, ni CL (ils seront
# dans le .inp principal du labo), donc on ne demande pas a CAE de verifier la coherence.
if not os.path.isdir(RAW_DIR):
    os.makedirs(RAW_DIR)
old_cwd = os.getcwd()
try:
    os.chdir(RAW_DIR)
    if RAW_INP_NAME in mdb.jobs.keys():
        del mdb.jobs[RAW_INP_NAME]
    job = mdb.Job(name=RAW_INP_NAME, model=MODEL_NAME)
    job.writeInput(consistencyChecking=OFF)
    del mdb.jobs[RAW_INP_NAME]
finally:
    os.chdir(old_cwd)
print('.inp brut ecrit : ' + os.path.join(RAW_DIR, RAW_INP_NAME + '.inp'))
print('Etape suivante (Python 3, racine du repo) : python shpb-ut-equilibrium/scripts/pre/inp_to_geo.py')
