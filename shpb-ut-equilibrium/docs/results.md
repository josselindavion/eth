# Dépouillement des calculs

Script : `scripts/post/plot_case.py` (Python 3 + numpy, pandas, matplotlib), sur le PC, après `fetch_study.py`.

```
python shpb-ut-equilibrium/scripts/post/plot_case.py shpb-ut-equilibrium/runs/_submit/<étude>_<date>
```

Sorties : `<case>/<case>_overview.png` pour chaque calcul, et `<étude>_<date>_summary.csv` (une ligne par calcul).

## 1. Les 4 graphes de `<case>_overview.png`

| Graphe | Courbes | Ce qu'on regarde |
|---|---|---|
| 1. Jauges des barres | LE22 moyenne des éléments de la jauge d'entrée et de sortie | impulsion incidente (palier, durée 2,12 ms), onde réfléchie, onde transmise |
| 2. Forces | SOF2 × 2 sur SEC_IN (côté pusher) et SEC_OUT (côté barre de sortie), S22 × aire de la jauge de sortie | les deux forces de l'éprouvette se superposent-elles ? la barre de sortie mesure-t-elle la même chose ? |
| 3. Déséquilibre | (F_in − F_out) / F_moyen, en %, lignes à ± 5 % | à partir de quand la courbe reste dans la bande |
| 4. Extensomètre | (U2_EXT_IN − U2_EXT_OUT) / L0, L0 = 12 mm, ligne à 30 % | instant où 30 % sont atteints, pente = vitesse de déformation |

La zone grisée est la **fenêtre utile** : du début du chargement à 30 % (ou à la déformation maximale si 30 % ne sont jamais atteints).

## 2. Grandeurs de `<étude>_summary.csv`

| Colonne | Définition |
|---|---|
| `t_load_ms` | début du chargement : premier instant où \|F_sec_in\| > 2 % de son maximum |
| `rate_mean` | vitesse de déformation moyenne de l'extensomètre (1/s), entre 0,5 % et min(25 %, 0,8 × `eps_max`) |
| `t30_ms` | instant où l'extensomètre atteint 30 % (vide si jamais) |
| `eps_max` | déformation maximale de l'extensomètre dans la fenêtre utile |
| `t_eq_ms` | premier instant à partir duquel \|F_in − F_out\| / F_moyen < 5 % **jusqu'à la fin de la fenêtre utile** (instants où la force est < 10 % de son max ignorés) |
| `dt_eq_ms` | `t_eq_ms − t_load_ms` : temps de mise en équilibre |
| `dF_rms_pct` | écart moyen (rms) \|F_in − F_out\| / F_moyen après `t_eq_ms`, en % |
| `F_max_kN` | force maximale dans l'éprouvette (SEC_IN, modèle complet) |
| `hourglass_pct` | ALLAE / ALLIE en fin de calcul (doit rester < ~5 %) |

## 3. Premiers résultats : étude `taskI_20261013-1127` (UT19, guidages, 4 ms simulées)

| Grandeur | 100 /s visé | 500 /s visé |
|---|---|---|
| Vitesse du striker | 1,5 m/s | 7,5 m/s |
| Palier de la jauge d'entrée | −1,50e-4 (−28,5 MPa) | −7,50e-4 (−142 MPa), = théorie |
| Début du chargement | 1,542 ms | 1,345 ms |
| Vitesse de déformation obtenue | **≈ 21 /s** | **≈ 485 /s** |
| 30 % atteints | **jamais** (max 3,5 %) | à 1,995 ms |
| Équilibre < 5 % | 0,36 ms après le début de charge | 0,60 ms après le début de charge |
| Écart rms ensuite | 0,5 % | 1,7 % |
| Force max | 7,40 kN | 7,59 kN (puis baisse : striction) |
| Hourglass | 0,6 % | 0,9 % |

### Pourquoi 100 /s ne donne que 21 /s

La vitesse du striker est estimée par V ≈ vitesse de déformation × 15 mm. Cela suppose que l'éprouvette
ne freine pas les barres. En réalité la vitesse d'allongement du LID vaut

    v_allongement ≈ 2 v_i − 2 F / (ρ c A),   avec v_i ≈ V / 2 et ρ c A = 8000 × 4871 × 3,14e-4 ≈ 12 240 N·s/m

À 1,5 m/s, la force incidente (≈ 9 kN) est à peine supérieure à la force de l'éprouvette (≈ 7,4 kN) :
2 v_i = 1,5 m/s, 2 F / (ρ c A) ≈ 1,2 m/s, il reste ≈ 0,26 m/s → ≈ 17 /s sur 15 mm, cohérent avec 21 /s.
À 500 /s la correction est relativement petite (7,5 − 1,2 = 6,3 m/s), d'où un résultat proche de la cible.

Conséquences :

- il faut ajouter la force de l'éprouvette dans le calcul de la vitesse du striker : V ≈ rate × L + 2 F / (ρ c A),
  soit ≈ 2,8 m/s pour 100 /s ;
- à 100 /s, 30 % demandent 3 ms de chargement : impossible avec l'impulsion de 2,12 ms du striker de 5 m.
