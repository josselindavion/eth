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
    eps_gauge_in      deformation axiale LE22 moyenne des elements de la jauge d'entree
    sig_gauge_in      contrainte axiale S22 moyenne (MPa), idem
    eps_gauge_out     idem jauge de sortie
    sig_gauge_out     idem jauge de sortie (MPa)
    F_sec_in_N        force axiale a travers la section SEC_IN (cote pusher)  = 2 x SOF2
    F_sec_out_N       force axiale a travers la section SEC_OUT (cote sortie) = 2 x SOF2
    u2_ext_in_mm      deplacement axial du noeud EXT_IN de l'extensometre
    u2_ext_out_mm     deplacement axial du noeud EXT_OUT
    eps_ext           deformation nominale de l'extensometre = (u2_in - u2_out) / L0
    ALLKE_mJ ...      energies du modele entier (x 2), dont ALLAE (hourglass)
Les colonnes introuvables dans le .odb sont omises (un message le signale).
"""
import os
import sys

from odbAccess import openOdb

ENERGIES = ['ALLKE', 'ALLIE', 'ALLAE', 'ALLWK', 'ALLFD', 'ETOTAL']


def mean_series(series_list):
    """Moyenne point par point d'une liste de series [(t, v), ...] de meme echantillonnage."""
    n = min([len(s) for s in series_list])
    out = []
    for i in range(n):
        tot = 0.0
        for s in series_list:
            tot += s[i][1]
        out.append((series_list[0][i][0], tot / len(series_list)))
    return out


def main():
    case_dir = os.path.abspath(sys.argv[-1])
    case = os.path.basename(case_dir.rstrip(os.sep))
    spec = case.split('_')[0]                                  # ex. UT19
    odb = openOdb(os.path.join(case_dir, case + '.odb'), readOnly=True)
    step = odb.steps[odb.steps.keys()[-1]]
    inst = odb.rootAssembly.instances[odb.rootAssembly.instances.keys()[0]]

    # Avec un .inp "a plat" (sans *Part), Abaqus range les groupes dans l'instance PART-1-1 ;
    # par securite on cherche aussi au niveau de l'assemblage.
    def elset(name):
        if name in inst.elementSets.keys():
            return set([e.label for e in inst.elementSets[name].elements])
        groups = odb.rootAssembly.elementSets[name].elements      # une liste par instance
        return set([e.label for g in groups for e in g])

    def node(name):
        if name in inst.nodeSets.keys():
            return inst.nodeSets[name].nodes[0]
        return odb.rootAssembly.nodeSets[name].nodes[0][0]

    gauge_in = elset('INPUT_BAR_GAUGE_IN')
    gauge_out = elset('OUTPUT_BAR_GAUGE_OUT')
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
    raw = {'LE22_in': [], 'S22_in': [], 'LE22_out': [], 'S22_out': []}
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
                side = 'in' if label in gauge_in else ('out' if label in gauge_out else None)
                if side:
                    raw[key + '_' + side].append(data)
            elif up.startswith('NODE ') and key == 'U2':
                label = label_of(rname)
                if label == n_ext_in.label:
                    cols['u2_ext_in_mm'] = data
                elif label == n_ext_out.label:
                    cols['u2_ext_out_mm'] = data
            elif up.startswith('ASSEMBLY') and key in ENERGIES:
                cols[key + '_mJ'] = [(t, 2.0 * v) for t, v in data]

    for k, name in (('LE22_in', 'eps_gauge_in'), ('S22_in', 'sig_gauge_in'),
                    ('LE22_out', 'eps_gauge_out'), ('S22_out', 'sig_gauge_out')):
        if raw[k]:
            cols[name] = mean_series(raw[k])
    if 'u2_ext_in_mm' in cols and 'u2_ext_out_mm' in cols:
        cols['eps_ext'] = [(a[0], (a[1] - b[1]) / L0)
                           for a, b in zip(cols['u2_ext_in_mm'], cols['u2_ext_out_mm'])]

    order = ['eps_gauge_in', 'sig_gauge_in', 'eps_gauge_out', 'sig_gauge_out',
             'F_sec_in_N', 'F_sec_out_N', 'u2_ext_in_mm', 'u2_ext_out_mm', 'eps_ext'] + \
            [e + '_mJ' for e in ENERGIES]
    present = [c for c in order if c in cols]
    missing = [c for c in order if c not in cols]
    n = min([len(cols[c]) for c in present])
    time = [cols[present[0]][i][0] for i in range(n)]

    with open(os.path.join(case_dir, case + '_history.csv'), 'w') as f:
        f.write('# %s -- extrait de %s.odb par scripts/post/extract_history.py\n' % (case, case))
        f.write('# demi-modele : forces et energies x 2 ; jauges = moyenne de %d / %d elements ;'
                ' extensometre L0 = %.3f mm\n' % (len(raw['LE22_in']), len(raw['LE22_out']), L0))
        f.write(','.join(['time_s'] + present) + '\n')
        for i in range(n):
            f.write(','.join(['%.6e' % time[i]] + ['%.6e' % cols[c][i][1] for c in present]) + '\n')
    odb.close()

    print('%-15s %d instants (t = %.3e .. %.3e s), %d colonnes%s'
          % (case, n, time[0], time[-1], len(present),
             ('' if not missing else ' -- MANQUANT : ' + ', '.join(missing))))


if __name__ == '__main__':
    main()
