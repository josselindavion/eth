# -*- coding: utf-8 -*-
"""
extract_history.py -- Extrait les courbes utiles d'un calcul (.odb) dans un petit CSV.

Lance avec le Python d'Abaqus (Python 2.7, module odbAccess), dans le dossier du calcul :
    abaqus python extract_history.py <dossier_du_calcul>
Normalement appele pour tous les calculs d'une etude par scripts/hpc/extract_study.sh (sur Euler).

Sorties, dans le dossier du calcul :
    <case_id>_history.csv        une ligne par instant de sortie "historique" (toutes les 1 us)
    <case_id>_inventory.txt      liste de toutes les sorties historiques du .odb (pour verifier)

Colonnes du CSV (demi-modele : les forces et les energies sont multipliees par 2) :
    time_s            temps (s)
    eps_gauge_in      deformation axiale LE22 de la jauge d'entree, lue COMME AU LABO : moyenne d'une
                      jauge collee en haut de la barre et d'une jauge collee en bas (la flexion s'annule).
                      Chaque "jauge" = moyenne ponderee par le volume des elements de surface de la tranche.
    sig_gauge_in      contrainte axiale S22 (MPa), meme lecture
    eps_gauge_out     idem jauge de sortie
    sig_gauge_out     idem jauge de sortie (MPa)
    F_sec_in_N        force axiale a travers la section SEC_IN (cote pusher)  = 2 x SOF2
    F_sec_out_N       force axiale a travers la section SEC_OUT (cote sortie) = 2 x SOF2
    u2_ext_in_mm      deplacement axial du noeud EXT_IN de l'extensometre
    u2_ext_out_mm     deplacement axial du noeud EXT_OUT
    eps_ext           deformation nominale de l'extensometre = (u2_in - u2_out) / L0
    ALLKE_mJ ...      energies du modele entier (x 2), dont ALLAE (hourglass)
    F_probe_<NOM>_N   seulement si le calcul a des sondes (probes = 1 dans cases.csv) : force a travers
                      une tranche de 5 mm de la barre de sortie ou de sa tete = 2 x somme(S22 x volume) / 5 mm
Les colonnes introuvables dans le .odb sont omises (un message le signale).
"""
import os
import sys

from odbAccess import openOdb

ENERGIES = ['ALLKE', 'ALLIE', 'ALLAE', 'ALLWK', 'ALLFD', 'ETOTAL']
BAR_RADIUS = 10.0          # mm
PROBE_THICKNESS = 5.0      # mm, epaisseur des tranches des sondes (scripts/pre/make_run.py)


# ============================================================
# GEOMETRIE DES ELEMENTS (volume et centre, a partir des noeuds)
# ============================================================
def tet_volume(a, b, c, d):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    w = [d[i] - a[i] for i in range(3)]
    return abs(u[0] * (v[1] * w[2] - v[2] * w[1]) - u[1] * (v[0] * w[2] - v[2] * w[0])
               + u[2] * (v[0] * w[1] - v[1] * w[0])) / 6.0


def element_geometry(inst, elements):
    """{label: (volume, (x, y, z) du centre)} ; hexaedres decoupes en 5 tetraedres, tetraedres
    (lineaires ou quadratiques) par leurs 4 sommets."""
    geo = {}
    for e in elements:
        conn = list(e.connectivity)
        corners = conn[:8] if len(conn) in (8, 20) else conn[:4]
        p = [inst.getNodeFromLabel(n).coordinates for n in corners]
        if len(p) == 8:
            vol = 0.0
            for t in ((0, 1, 3, 4), (1, 2, 3, 6), (1, 4, 5, 6), (3, 4, 6, 7), (1, 3, 4, 6)):
                vol += tet_volume(p[t[0]], p[t[1]], p[t[2]], p[t[3]])
        else:
            vol = tet_volume(p[0], p[1], p[2], p[3])
        c = tuple([sum([q[i] for q in p]) / len(p) for i in range(3)])
        geo[e.label] = (vol, c)
    return geo


def gauge_pair(geo):
    """Elements de surface en haut et en bas de la tranche de jauge, pres du plan de symetrie X = 0 :
    l'equivalent de deux jauges collees de part et d'autre de la barre."""
    z0 = sum([g[1][2] for g in geo.values()]) / len(geo)          # axe de la barre
    top, bot = [], []
    for lab, (v, c) in geo.items():
        dz = c[2] - z0
        r = (c[0] ** 2 + dz ** 2) ** 0.5
        if r > 0.75 * BAR_RADIUS and abs(c[0]) < 0.35 * BAR_RADIUS:
            (top if dz > 0 else bot).append(lab)
    return top, bot


def wmean(labels, geo, data, i):
    v = sum([geo[l][0] for l in labels])
    return sum([geo[l][0] * data[l][i][1] for l in labels]) / v


def main():
    case_dir = os.path.abspath(sys.argv[-1])
    case = os.path.basename(case_dir.rstrip(os.sep))
    spec = case.split('_')[0]                                  # ex. UT19
    odb = openOdb(os.path.join(case_dir, case + '.odb'), readOnly=True)
    step = odb.steps[odb.steps.keys()[-1]]
    inst = odb.rootAssembly.instances[odb.rootAssembly.instances.keys()[0]]

    # Avec un .inp "a plat" (sans *Part), Abaqus range les groupes dans l'instance PART-1-1 ;
    # par securite on cherche aussi au niveau de l'assemblage.
    def elements_of(name):
        if name in inst.elementSets.keys():
            return inst.elementSets[name].elements
        groups = odb.rootAssembly.elementSets[name].elements      # une liste par instance
        return [e for g in groups for e in g]

    def node(name):
        if name in inst.nodeSets.keys():
            return inst.nodeSets[name].nodes[0]
        return odb.rootAssembly.nodeSets[name].nodes[0][0]

    all_sets = list(inst.elementSets.keys()) + list(odb.rootAssembly.elementSets.keys())
    gauges = {}
    for side, name in (('in', 'INPUT_BAR_GAUGE_IN'), ('out', 'OUTPUT_BAR_GAUGE_OUT')):
        geo = element_geometry(inst, elements_of(name))
        top, bot = gauge_pair(geo)
        gauges[side] = (geo, top, bot)
    probes = {}
    for name in sorted(set([s for s in all_sets if s.upper().startswith('PROBE_')])):
        els = elements_of(name)
        geo = element_geometry(inst, els)
        if all([len(e.connectivity) == 8 for e in els]):          # une couche d'hexaedres
            ys = [inst.getNodeFromLabel(nd).coordinates[1] for e in els for nd in e.connectivity]
            h = max(ys) - min(ys)
        else:
            h = PROBE_THICKNESS
        probes[name.upper()[len('PROBE_'):]] = (geo, h)
    n_ext_in, n_ext_out = node(spec + '_EXT_IN'), node(spec + '_EXT_OUT')
    L0 = abs(n_ext_in.coordinates[1] - n_ext_out.coordinates[1])  # longueur de l'extensometre (mm)

    # --- Inventaire de toutes les sorties historiques (ecrit d'abord : utile si la suite echoue)
    inventory = []
    for rname, reg in step.historyRegions.items():
        for key, ho in reg.historyOutputs.items():
            inventory.append('%-60s %-12s %6d points' % (rname, key, len(ho.data)))
    with open(os.path.join(case_dir, case + '_inventory.txt'), 'w') as f:
        f.write('\n'.join(sorted(inventory)) + '\n')

    def label_of(rname):
        """'Element PART-1-1.2000123 Int Point 1' -> 2000123 ; 'Node PART-1-1.5000203' -> 5000203."""
        try:
            return int(rname.split('.')[-1].split()[0])
        except (ValueError, IndexError):
            return None

    # --- Tri des sorties utiles
    elem_data = {'LE22': {}, 'S22': {}}                         # {cle: {label: [(t, v), ...]}}
    cols = {}
    for rname, reg in step.historyRegions.items():
        up = rname.upper()
        for key, ho in reg.historyOutputs.items():
            data = ho.data
            # Sections de force : region 'ElementSet  PIBATCH', cle 'SOF2  on surface SECTION_IN'
            where = (up + ' ' + key.upper())
            if key.upper().startswith('SOF2') and 'SECTION_IN' in where:
                cols['F_sec_in_N'] = [(t, 2.0 * v) for t, v in data]
            elif key.upper().startswith('SOF2') and 'SECTION_OUT' in where:
                cols['F_sec_out_N'] = [(t, 2.0 * v) for t, v in data]
            elif up.startswith('ELEMENT ') and key in ('LE22', 'S22'):
                label = label_of(rname)
                if label is not None:
                    elem_data[key][label] = data
            elif up.startswith('NODE ') and key == 'U2':
                label = label_of(rname)
                if label == n_ext_in.label:
                    cols['u2_ext_in_mm'] = data
                elif label == n_ext_out.label:
                    cols['u2_ext_out_mm'] = data
            elif up.startswith('ASSEMBLY') and key in ENERGIES:
                cols[key + '_mJ'] = [(t, 2.0 * v) for t, v in data]

    # --- Jauges : moyenne d'une jauge en haut et d'une jauge en bas (comme au labo)
    for side in ('in', 'out'):
        geo, top, bot = gauges[side]
        for key, name in (('LE22', 'eps_gauge_' + side), ('S22', 'sig_gauge_' + side)):
            d = elem_data[key]
            if top and bot and all([l in d for l in top + bot]):
                n = min([len(d[l]) for l in top + bot])
                cols[name] = [(d[top[0]][i][0], 0.5 * (wmean(top, geo, d, i) + wmean(bot, geo, d, i)))
                              for i in range(n)]
    # --- Sondes : force a travers chaque tranche = 2 x somme(S22 x volume) / epaisseur de la tranche
    #     (hexaedres : une couche, epaisseur lue sur les noeuds ; tetraedres : tranche de 5 mm)
    for pname, (geo, h) in probes.items():
        d = elem_data['S22']
        labs = [l for l in geo if l in d]
        if labs:
            n = min([len(d[l]) for l in labs])
            cols['F_probe_%s_N' % pname] = [
                (d[labs[0]][i][0], 2.0 * sum([geo[l][0] * d[l][i][1] for l in labs]) / h)
                for i in range(n)]
    if 'u2_ext_in_mm' in cols and 'u2_ext_out_mm' in cols:
        cols['eps_ext'] = [(a[0], (a[1] - b[1]) / L0)
                           for a, b in zip(cols['u2_ext_in_mm'], cols['u2_ext_out_mm'])]

    order = ['eps_gauge_in', 'sig_gauge_in', 'eps_gauge_out', 'sig_gauge_out',
             'F_sec_in_N', 'F_sec_out_N', 'u2_ext_in_mm', 'u2_ext_out_mm', 'eps_ext'] + \
            [e + '_mJ' for e in ENERGIES] + sorted([c for c in cols if c.startswith('F_probe_')])
    present = [c for c in order if c in cols]
    missing = [c for c in order if c not in cols]
    n = min([len(cols[c]) for c in present])
    time = [cols[present[0]][i][0] for i in range(n)]

    probe_y = ', '.join(['%s=%.2f' % (p, sum([g[1][1] for g in gh[0].values()]) / len(gh[0]))
                         for p, gh in sorted(probes.items())])
    with open(os.path.join(case_dir, case + '_history.csv'), 'w') as f:
        f.write('# %s -- extrait de %s.odb par scripts/post/extract_history.py\n' % (case, case))
        f.write('# demi-modele : forces et energies x 2 ; jauges = moyenne haut + bas (%d + %d elements a '
                'l entree, %d + %d a la sortie) ; extensometre L0 = %.3f mm\n'
                % (len(gauges['in'][1]), len(gauges['in'][2]), len(gauges['out'][1]), len(gauges['out'][2]), L0))
        if probes:
            y_gauge = sum([g[1][1] for g in gauges['out'][0].values()]) / len(gauges['out'][0])
            f.write('# sondes (Y moyen des tranches, mm) : %s, GAUGE_OUT=%.2f\n' % (probe_y, y_gauge))
        f.write(','.join(['time_s'] + present) + '\n')
        for i in range(n):
            f.write(','.join(['%.6e' % time[i]] + ['%.6e' % cols[c][i][1] for c in present]) + '\n')
    odb.close()

    print('%-15s %d instants (t = %.3e .. %.3e s), %d colonnes%s'
          % (case, n, time[0], time[-1], len(present),
             ('' if not missing else ' -- MANQUANT : ' + ', '.join(missing))))


if __name__ == '__main__':
    main()
