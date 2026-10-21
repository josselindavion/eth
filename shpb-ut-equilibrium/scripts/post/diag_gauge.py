# -*- coding: utf-8 -*-
"""
diag_gauge.py -- Diagnostic de la jauge virtuelle de la barre de sortie (oscillations).

Question : les fortes oscillations de la force lue par la jauge de sortie (15 a 39 % a 500 et
1000 /s) viennent-elles de notre facon de calculer la jauge, ou de la flexion de la barre ?

Pour chaque instant, a partir des ~100 elements de la tranche OUTPUT_BAR_GAUGE_OUT (10 mm de barre) :
    F_simple     moyenne simple de S22 x aire de la barre      (ce que fait extract_history.py)
    F_weighted   moyenne de S22 ponderee par le volume x aire  (= vraie force axiale dans la barre)
    F_pair       2 jauges collees dessus et dessous, comme au labo : A x E x (LE22_haut + LE22_bas) / 2
    S22_top, S22_bottom   contrainte moyenne dans le quart haut et le quart bas de la section (flexion)
    M_bend       moment de flexion (N.mm) autour de l'axe horizontal de la barre
    F_sec_out    force dans la section SEC_OUT de l'eprouvette (reference, NON decalee dans le temps)

Lancement (Python d'Abaqus, Python 2.7), avec le chemin du dossier du calcul qui contient le .odb :
    abq2023 python <repo>/shpb-ut-equilibrium/scripts/post/diag_gauge.py <dossier_du_calcul>
Sortie : <dossier_du_calcul>/<calcul>_gauge_diag.csv  (+ un resume a l'ecran)
"""
import os
import sys

from odbAccess import openOdb

BAR_RADIUS = 10.0           # mm
Z_AXIS = 29.35              # mm, axe de la barre de sortie
E_BAR = 189813.0            # MPa (maraging, E = rho c^2)
A_BAR = 3.14159265 * BAR_RADIUS ** 2   # mm2, section complete (demi-modele : moyennes = section complete)


def tet_volume(a, b, c, d):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    w = [d[i] - a[i] for i in range(3)]
    det = (u[0] * (v[1] * w[2] - v[2] * w[1]) - u[1] * (v[0] * w[2] - v[2] * w[0])
           + u[2] * (v[0] * w[1] - v[1] * w[0]))
    return abs(det) / 6.0


def hex_volume(p):
    """Volume d'un hexaedre (ordre Abaqus : 4 noeuds en bas, 4 en haut) decoupe en 5 tetraedres."""
    tets = ((0, 1, 3, 4), (1, 2, 3, 6), (1, 4, 5, 6), (3, 4, 6, 7), (1, 3, 4, 6))
    tot = 0.0
    for t in tets:
        tot += tet_volume(p[t[0]], p[t[1]], p[t[2]], p[t[3]])
    return tot


def main():
    case_dir = os.path.abspath(sys.argv[-1])
    case = os.path.basename(case_dir.rstrip(os.sep))
    odb = openOdb(os.path.join(case_dir, case + '.odb'), readOnly=True)
    step = odb.steps[odb.steps.keys()[-1]]
    inst = odb.rootAssembly.instances[odb.rootAssembly.instances.keys()[0]]

    name = 'OUTPUT_BAR_GAUGE_OUT'
    if name in inst.elementSets.keys():
        elems = inst.elementSets[name].elements
    else:
        elems = odb.rootAssembly.elementSets[name].elements[0]

    # Geometrie de chaque element : volume, centre
    geo = {}
    for e in elems:
        pts = [inst.getNodeFromLabel(n).coordinates for n in e.connectivity]
        c = [sum([q[i] for q in pts]) / len(pts) for i in range(3)]
        geo[e.label] = (hex_volume(pts) if len(pts) == 8 else 0.0, c)
    vtot = sum([g[0] for g in geo.values()])
    y_slice = [g[1][1] for g in geo.values()]
    length = max(y_slice) - min(y_slice) + 5.0          # tranche : 2 couches de 5 mm environ

    # Histoires S22 et LE22 de ces elements, et force de la section SEC_OUT
    s22, le22, sof = {}, {}, None
    for rname, reg in step.historyRegions.items():
        up = rname.upper()
        for key, ho in reg.historyOutputs.items():
            if key.upper().startswith('SOF2') and 'SECTION_OUT' in (up + ' ' + key.upper()):
                sof = [(t, 2.0 * v) for t, v in ho.data]
            elif up.startswith('ELEMENT ') and key in ('S22', 'LE22'):
                try:
                    lab = int(rname.split('.')[-1].split()[0])
                except (ValueError, IndexError):
                    continue
                if lab in geo:
                    (s22 if key == 'S22' else le22)[lab] = ho.data

    labels = sorted(s22.keys())
    n = min([len(s22[l]) for l in labels])
    # Quarts haut et bas de la section, et elements de surface en haut et en bas (pres du plan X = 0)
    top = [l for l in labels if geo[l][1][2] - Z_AXIS > 0.5 * BAR_RADIUS]
    bot = [l for l in labels if geo[l][1][2] - Z_AXIS < -0.5 * BAR_RADIUS]
    rad = lambda l: ((geo[l][1][0]) ** 2 + (geo[l][1][2] - Z_AXIS) ** 2) ** 0.5
    surf_top = [l for l in top if rad(l) > 0.75 * BAR_RADIUS and geo[l][1][0] < 0.35 * BAR_RADIUS]
    surf_bot = [l for l in bot if rad(l) > 0.75 * BAR_RADIUS and geo[l][1][0] < 0.35 * BAR_RADIUS]
    vols = [geo[l][0] for l in labels]
    print('%s : %d elements dans la tranche de jauge, volume %.1f mm3 (attendu ~ %.1f), '
          'volumes de %.2f a %.2f mm3' % (case, len(labels), vtot, 0.5 * A_BAR * length, min(vols), max(vols)))
    print('  quart haut %d elements, quart bas %d ; jauges de surface : %d en haut, %d en bas'
          % (len(top), len(bot), len(surf_top), len(surf_bot)))

    def wmean(ls, i, d):
        v = sum([geo[l][0] for l in ls])
        return sum([geo[l][0] * d[l][i][1] for l in ls]) / v if v > 0 else 0.0

    out = os.path.join(case_dir, case + '_gauge_diag.csv')
    with open(out, 'w') as f:
        f.write('time_s,F_simple_N,F_weighted_N,F_pair_N,S22_top_MPa,S22_bottom_MPa,M_bend_Nmm,F_sec_out_N\n')
        for i in range(n):
            t = s22[labels[0]][i][0]
            simple = sum([s22[l][i][1] for l in labels]) / len(labels)
            weighted = wmean(labels, i, s22)
            pair = 0.5 * (sum([le22[l][i][1] for l in surf_top]) / max(len(surf_top), 1)
                          + sum([le22[l][i][1] for l in surf_bot]) / max(len(surf_bot), 1))
            moment = sum([geo[l][0] * s22[l][i][1] * (geo[l][1][2] - Z_AXIS) for l in labels]) / length * 2.0
            f.write('%.6e,%.6e,%.6e,%.6e,%.6e,%.6e,%.6e,%.6e\n' % (
                t, simple * A_BAR, weighted * A_BAR, pair * E_BAR * A_BAR, wmean(top, i, s22),
                wmean(bot, i, s22), moment, sof[i][1] if sof and i < len(sof) else 0.0))
    odb.close()
    print('Ecrit : ' + out)


if __name__ == '__main__':
    main()
