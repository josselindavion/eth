# -*- coding: utf-8 -*-
"""
inp_to_geo.py -- Convertit le .inp ecrit par Abaqus/CAE en fichiers .geo "a plat",
un par piece (convention du labo, comme NT20.geo).

Entree : le .inp brut ecrit par build_bench.py (format Part / Assembly / Instance).
Sortie : model/geometry/<PIECE>.geo pour chaque instance qui contient un maillage :
    - noeuds et elements, renumerotes avec un decalage propre a chaque piece
      (piece n -> labels a partir de n * 1 000 000) pour qu'ils ne se chevauchent pas ;
    - groupes (*Nset, *Elset) et surfaces (*Surface), renommes avec le nom de la piece
      en prefixe (XSYMM -> UT19_XSYMM, S_TIE -> PUSHER_ROD_S_TIE ; UT19_ALL reste UT19_ALL).
Les .geo ne contiennent ni *Part, ni *Assembly, ni section : ils sont inclus dans le .inp
principal par *INCLUDE, qui definit materiaux, sections, contacts, etc.

Lancement (Python 3, depuis la racine du repo) :
    python shpb-ut-equilibrium/scripts/pre/inp_to_geo.py
    python shpb-ut-equilibrium/scripts/pre/inp_to_geo.py chemin/vers/brut.inp  [dossier_sortie]
"""
import math
import os
import re
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, '..', '..'))
DEFAULT_INP = os.path.join(PROJECT_ROOT, 'model', 'geometry', '_raw', 'SHPB_UT19_mesh.inp')
DEFAULT_OUT = os.path.join(PROJECT_ROOT, 'model', 'geometry')
LABEL_OFFSET = 1000000      # piece n -> labels a partir de n * LABEL_OFFSET
PER_LINE = 16               # Abaqus : 16 valeurs max par ligne de donnees


# ============================================================
# LECTURE DU .inp
# ============================================================
def parse_keyword_line(line):
    """'*Nset, nset=A, generate' -> ('nset', {'nset': 'A', 'generate': True})"""
    parts = [p.strip() for p in line[1:].split(',')]
    kw = parts[0].lower()
    params = {}
    for p in parts[1:]:
        if not p:
            continue
        if '=' in p:
            k, v = p.split('=', 1)
            params[k.strip().lower()] = v.strip()
        else:
            params[p.lower()] = True
    return kw, params


def read_blocks(path):
    """Liste de (mot-cle, parametres, lignes de donnees), commentaires retires."""
    blocks = []
    with open(path) as f:
        for raw in f:
            line = raw.rstrip('\n').rstrip('\r')
            if line.startswith('**') or not line.strip():
                continue
            if line.startswith('*'):
                kw, params = parse_keyword_line(line)
                blocks.append([kw, params, []])
            elif blocks:
                blocks[-1][2].append(line)
    return blocks


def ints(lines):
    """Toutes les valeurs entieres de lignes 'a, b, c,'."""
    out = []
    for l in lines:
        out += [int(v) for v in l.replace(' ', '').split(',') if v]
    return out


class Mesh(object):
    """Contenu maille d'une part (ou d'une instance)."""
    def __init__(self, name):
        self.name = name
        self.nodes = []          # (label, x, y, z)
        self.elements = []       # (type, [(label, [noeuds]), ...])
        self.nsets = []          # (nom, params, [labels] ou (debut, fin, pas))
        self.elsets = []
        self.surfaces = []       # (nom, params, [(elset, face)])


def parse_model(blocks):
    """Renvoie (parts, instances, assembly_sets).
    instances = [(nom, part, translation, rotation)] ;
    assembly_sets = groupes et surfaces definis au niveau de l'assemblage (hors instance)."""
    parts, instances = {}, []
    assembly_sets = []
    cur = None                   # Mesh courant (dans *Part)
    in_instance = None
    in_assembly = False
    for kw, params, data in blocks:
        if kw == 'part':
            cur = Mesh(params['name']); parts[cur.name] = cur
        elif kw == 'end part':
            cur = None
        elif kw == 'assembly':
            in_assembly = True
        elif kw == 'end assembly':
            in_assembly = False
        elif kw == 'instance':
            tr = rot = None
            if len(data) >= 1:
                tr = [float(v) for v in data[0].split(',') if v.strip()]
            if len(data) >= 2:
                rot = [float(v) for v in data[1].split(',') if v.strip()]
            in_instance = params['name']
            instances.append((params['name'], params['part'], tr, rot))
        elif kw == 'end instance':
            in_instance = None
        elif in_instance is not None:
            # Contenu propre a une instance (ex. noeud de reference d'un rigide analytique) : ignore
            if kw in ('node', 'element'):
                print('  (ignore : *%s dans l\'instance %s)' % (kw, in_instance))
        elif cur is not None:
            add_block(cur, kw, params, data)
        elif in_assembly and kw in ('nset', 'elset', 'surface'):
            assembly_sets.append((kw, params, data))
    return parts, instances, assembly_sets


def assembly_items_for(assembly_sets, inst_name):
    """Groupes et surfaces de l'assemblage qui portent sur l'instance inst_name.
    Une surface d'assemblage est rattachee a l'instance de ses elsets ; si elle couvre
    plusieurs instances, chaque piece recoit sa partie, sous le meme nom."""
    sets = [s for s in assembly_sets if s[0] != 'surface' and s[1].get('instance') == inst_name]
    elsets_here = set(s[1]['elset'] for s in sets if s[0] == 'elset')
    surfaces = []
    for kw, params, data in assembly_sets:
        if kw != 'surface':
            continue
        rows = []
        for l in data:
            v = [x.strip() for x in l.split(',') if x.strip()]
            ref, face = v[0], (v[1] if len(v) > 1 else '')
            if '.' in ref:                                  # reference 'instance.elset'
                inst, ref = ref.split('.', 1)
                if inst != inst_name:
                    continue
            elif ref not in elsets_here:
                continue
            rows.append((ref, face))
        if rows:
            surfaces.append((params['name'], params, rows))
    return sets, surfaces


def add_block(mesh, kw, params, data):
    if kw == 'node':
        for l in data:
            v = [s.strip() for s in l.split(',')]
            mesh.nodes.append((int(v[0]), float(v[1]), float(v[2]), float(v[3]) if len(v) > 3 and v[3] else 0.0))
    elif kw == 'element':
        elems, buf = [], []
        for l in data:
            buf += [int(v) for v in l.replace(' ', '').split(',') if v]
            if not l.rstrip().endswith(','):          # fin de l'element (pas de continuation)
                elems.append((buf[0], buf[1:])); buf = []
        if buf:
            elems.append((buf[0], buf[1:]))
        mesh.elements.append((params['type'], elems))
    elif kw in ('nset', 'elset'):
        name = params.get(kw)
        vals = ints(data)
        target = mesh.nsets if kw == 'nset' else mesh.elsets
        target.append((name, params, vals))
    elif kw == 'surface':
        rows = []
        for l in data:
            v = [s.strip() for s in l.split(',') if s.strip()]
            rows.append((v[0], v[1] if len(v) > 1 else ''))
        mesh.surfaces.append((params['name'], params, rows))


# ============================================================
# TRANSFORMATION DES INSTANCES
# ============================================================
def transform(xyz, tr, rot):
    """Translation, puis rotation (axe A->B, angle en degres), convention Abaqus."""
    x, y, z = xyz
    if tr:
        x, y, z = x + tr[0], y + tr[1], z + tr[2]
    if rot and abs(rot[6]) > 0.0:
        a, b = rot[0:3], rot[3:6]
        u = [b[i] - a[i] for i in range(3)]
        nu = math.sqrt(sum(c * c for c in u)); u = [c / nu for c in u]
        p = [x - a[0], y - a[1], z - a[2]]
        t = math.radians(rot[6]); c, s = math.cos(t), math.sin(t)
        dot = sum(u[i] * p[i] for i in range(3))
        cross = [u[1] * p[2] - u[2] * p[1], u[2] * p[0] - u[0] * p[2], u[0] * p[1] - u[1] * p[0]]
        p = [p[i] * c + cross[i] * s + u[i] * dot * (1 - c) for i in range(3)]
        x, y, z = p[0] + a[0], p[1] + a[1], p[2] + a[2]
    return tuple(0.0 if abs(v) < 1e-9 else v for v in (x, y, z))   # retire le bruit du type 6e-17


# ============================================================
# ECRITURE DES .geo
# ============================================================
def new_name(name, piece):
    """Prefixe le nom par la piece, sauf s'il l'est deja (UT19_ALL reste UT19_ALL)."""
    if name.upper().startswith(piece.upper() + '_'):
        return name
    if name.startswith('_'):                         # elset interne de surface : _S_TIE_S3
        return '_' + piece + name
    return piece + '_' + name


def chunks(vals, n=PER_LINE):
    for i in range(0, len(vals), n):
        yield ', '.join(str(v) for v in vals[i:i + n])


def write_set(out, kw, name, params, vals, off):
    opts = ''.join(', ' + k for k in ('internal', 'generate') if params.get(k))
    out.append('*%s, %s=%s%s' % ('Nset' if kw == 'nset' else 'Elset', kw, name, opts))
    if params.get('generate'):
        for i in range(0, len(vals), 3):
            out.append('%d, %d, %d' % (vals[i] + off, vals[i + 1] + off, vals[i + 2]))
    else:
        out += list(chunks([v + off for v in vals]))


def write_geo(path, piece, mesh, off, tr, rot, asm_sets, asm_surfaces, src):
    out = []
    n_nodes = len(mesh.nodes)
    n_elem = sum(len(e) for _, e in mesh.elements)
    out.append('** %s.geo -- genere par scripts/pre/inp_to_geo.py, NE PAS EDITER A LA MAIN' % piece)
    out.append('** Source : %s' % os.path.basename(src))
    out.append('** %d noeuds, %d elements ; labels decales de %d' % (n_nodes, n_elem, off))
    out.append('**')
    out.append('*Node, nset=%s_NALL' % piece)
    for lab, x, y, z in mesh.nodes:
        if tr or rot:
            x, y, z = transform((x, y, z), tr, rot)
        out.append('%d, %.9g, %.9g, %.9g' % (lab + off, x, y, z))
    for etype, elems in mesh.elements:
        out.append('*Element, type=%s' % etype)
        for lab, conn in elems:
            out += list(chunks([lab + off] + [c + off for c in conn]))

    # Noms deja pris (par type), pour eviter qu'un groupe d'assemblage ecrase un groupe de part
    used = {'nset': set(), 'elset': set(), 'surface': set()}
    rename = {}                                         # elset d'assemblage -> nouveau nom

    def unique(kw, name):
        if name.upper() in used[kw]:
            print('  ATTENTION : %s "%s" existe deja dans %s, renomme %s_ASM' % (kw, name, piece, name))
            name = name + '_ASM'
        used[kw].add(name.upper())
        return name

    for kw, sets in (('nset', mesh.nsets), ('elset', mesh.elsets)):
        for name, params, vals in sets:
            write_set(out, kw, unique(kw, new_name(name, piece)), params, vals, off)
    for kw, params, data in asm_sets:                   # groupes de l'assemblage
        name = unique(kw, new_name(params[kw], piece))
        if kw == 'elset':
            rename[params[kw]] = name
        write_set(out, kw, name, params, ints(data), off)

    surfaces = [(n, p, r, False) for n, p, r in mesh.surfaces] + [(n, p, r, True) for n, p, r in asm_surfaces]
    for name, params, rows, from_asm in surfaces:
        opts = ', internal' if params.get('internal') else ''
        out.append('*Surface, type=%s, name=%s%s'
                   % (params.get('type', 'ELEMENT'), unique('surface', new_name(name, piece)), opts))
        for elset, face in rows:
            ref = rename.get(elset, new_name(elset, piece)) if from_asm else new_name(elset, piece)
            out.append('%s, %s' % (ref, face) if face else ref)
    with open(path, 'w') as f:
        f.write('\n'.join(out) + '\n')
    return n_nodes, n_elem


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INP
    out_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    if not os.path.exists(src):
        sys.exit('Fichier introuvable : %s\n(lancer d\'abord build_bench.py dans Abaqus)' % src)
    os.makedirs(out_dir, exist_ok=True)
    parts, instances, assembly_sets = parse_model(read_blocks(src))
    print('Lu : %s  (%d parts, %d instances)' % (src, len(parts), len(instances)))
    print('%-12s %9s %9s  %-21s %s' % ('piece', 'noeuds', 'elements', 'labels', 'groupes / surfaces'))
    k = 0
    for inst_name, part_name, tr, rot in instances:
        mesh = parts[part_name]
        if not mesh.nodes:
            print('%-12s (pas de maillage, ignoree)' % part_name)
            continue
        k += 1
        off = k * LABEL_OFFSET
        asm_sets, asm_surfaces = assembly_items_for(assembly_sets, inst_name)
        n_n, n_e = write_geo(os.path.join(out_dir, part_name + '.geo'), part_name, mesh, off,
                             tr, rot, asm_sets, asm_surfaces, src)
        groups = mesh.nsets + mesh.elsets + [(p[s[0]], p, None) for s in asm_sets for p in [s[1]]]
        names = [new_name(g[0], part_name) for g in groups if not g[1].get('internal')]
        names += [new_name(x[0], part_name) for x in mesh.surfaces + asm_surfaces]
        print('%-12s %9d %9d  %9d..%-10d %s' % (part_name, n_n, n_e, off + 1, off + LABEL_OFFSET - 1,
                                                 ', '.join(sorted(set(names)))))
    print('Fichiers ecrits dans : %s' % out_dir)


if __name__ == '__main__':
    main()
