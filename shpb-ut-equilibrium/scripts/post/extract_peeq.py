# -*- coding: utf-8 -*-
"""
extract_peeq.py -- Deformation plastique equivalente (PEEQ) maximale dans l'eprouvette, a chaque image
de sortie "champ" du calcul (.odb) -> <case_id>_peeq.csv.

But (27/10/2026) : le modele n'a pas de critere de rupture. Quand la striction devient trop forte, quelques
elements au centre de la striction s'ecrasent (PEEQ qui saute de ~1 a ~9 en 40 us dans l'UT40 a 500 /s) et
les forces s'effondrent : ce n'est plus un essai realiste. Ce fichier permet de savoir, pour chaque calcul,
jusqu'ou les resultats sont representatifs.

Lance avec le Python d'Abaqus (Python 2.7, module odbAccess), dans le dossier du calcul :
    abaqus python extract_peeq.py <dossier_du_calcul>
Normalement appele par scripts/hpc/extract_study.sh (sur Euler).

Colonnes :
    time_s          temps de l'image (s)
    peeq_max        PEEQ maximale sur toute l'eprouvette (points d'integration)
    peeq_max_gauge  PEEQ maximale dans la partie droite (groupe GAUGE_ZONE)
    label_max       numero de l'element ou se trouve le maximum
    y_max_mm        position Y (axe des barres) du centre de cet element, dans la geometrie initiale (mm)
"""
import os
import sys

from odbAccess import openOdb


def main():
    run_dir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')
    case = os.path.basename(run_dir.rstrip(os.sep))
    spec = case.split('_')[0]
    odb = openOdb(os.path.join(run_dir, case + '.odb'), readOnly=True)
    inst = odb.rootAssembly.instances[odb.rootAssembly.instances.keys()[0]]

    def elset(name):
        if name in inst.elementSets.keys():
            return inst.elementSets[name]
        return odb.rootAssembly.elementSets[name]

    spec_set = elset(spec + '_ALL')
    gauge_labels = set(e.label for e in elset(spec + '_GAUGE_ZONE').elements) \
        if (spec + '_GAUGE_ZONE') in list(inst.elementSets.keys()) + list(odb.rootAssembly.elementSets.keys()) else set()
    # Y du centre de chaque element de l'eprouvette (geometrie initiale), pour situer le maximum
    elems = spec_set.elements
    if len(elems) and not hasattr(elems[0], 'label'):       # groupe d'assemblage : une liste par instance
        elems = elems[0]
    y_of = {}
    for e in elems:
        ys = [inst.getNodeFromLabel(n).coordinates[1] for n in e.connectivity[:8]]
        y_of[e.label] = sum(ys) / len(ys)

    step = odb.steps[odb.steps.keys()[-1]]
    rows = []
    for fr in step.frames:
        if 'PEEQ' not in fr.fieldOutputs.keys():
            continue
        vals = fr.fieldOutputs['PEEQ'].getSubset(region=spec_set).values
        best, lab, best_g = 0.0, 0, 0.0
        for v in vals:
            if v.data > best:
                best, lab = v.data, v.elementLabel
            if v.elementLabel in gauge_labels and v.data > best_g:
                best_g = v.data
        rows.append((fr.frameValue, best, best_g, lab, y_of.get(lab, float('nan'))))
    odb.close()

    out = os.path.join(run_dir, case + '_peeq.csv')
    with open(out, 'w') as f:
        f.write('# %s -- PEEQ max dans l eprouvette, par image de sortie champ (scripts/post/extract_peeq.py)\n'
                % case)
        f.write('time_s,peeq_max,peeq_max_gauge,label_max,y_max_mm\n')
        for r in rows:
            f.write('%.6e,%.5f,%.5f,%d,%.3f\n' % r)
    print('%s : %d images, PEEQ max finale %.3f (element %d, Y = %.1f mm)'
          % (case, len(rows), rows[-1][1] if rows else 0.0, rows[-1][3] if rows else 0,
             rows[-1][4] if rows else 0.0))


if __name__ == '__main__':
    main()
