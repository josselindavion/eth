# Dépouillement des calculs

Script : `scripts/post/plot_case.py` (Python 3 + numpy, pandas, matplotlib), sur le PC, après `fetch_study.py`.

```
python shpb-ut-equilibrium/scripts/post/plot_case.py shpb-ut-equilibrium/results/<étude>_<date>
```

Graphes de contrôle (un par calcul, pour vérifier). Sorties : `<case>/<case>_overview.png` pour chaque calcul, et `<étude>_<date>_summary.csv` (une ligne par calcul).

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
  fait dans `make_run.py`, voir section 4 (2,48 m/s pour 100 /s) ;
- à 100 /s, 30 % demandent 3 ms de chargement : impossible avec l'impulsion de 2,12 ms du striker de 5 m.

## 4. Vitesse du striker et durée simulée (`make_run.py`, depuis le 13/10/2026)

    V_striker = (vitesse de déformation × L_eff + 2 F / Z) / (2 K)

| Terme | Valeur | Origine |
|---|---|---|
| K = v_i / V_striker | 0,487 | impédances striker / barre (même diamètre 20 mm) : Z_s / (Z_s + Z_b) ; vérifié sur la jauge d'entrée (7,5e-4 à 7,5 m/s) |
| Z = ρ c A des barres | 12 242 N·s/m | maraging, 8000 kg/m³, 4871 m/s, Ø 20 mm |
| F (UT19) | 7 000 N | force moyenne de l'éprouvette pendant l'essai : 6,4 à 6,8 kN, max 7,4 à 7,6 kN |
| L_eff (UT19) | 12,7 mm | calée sur UT19 à 500 /s (485 /s obtenus) ; plus courte que la partie droite (15 mm) car l'extensomètre (12 mm) voit la zone la plus déformée |

| Vitesse visée | V_striker (ancienne formule) | V_striker (nouvelle) | Durée simulée |
|---|---|---|---|
| 100 /s | 1,5 m/s | 2,48 m/s | 3,65 ms (plafonnée : fin de l'impulsion) |
| 500 /s | 7,5 m/s | 7,69 m/s | 2,13 ms |
| 1 000 /s | 15 m/s | 14,20 m/s | 1,83 ms |

À 100 /s, 2F/Z (1,14 m/s) pèse autant que le terme utile (1,27 m/s) : une erreur de 10 % sur F donne
≈ 10 % d'erreur sur la vitesse de déformation. Les nouvelles valeurs sont à vérifier sur l'étude relancée.

Durée simulée = 1,234 ms (arrivée de l'onde au pusher) + 0,30 / vitesse de déformation + 0,3 ms de marge,
plafonnée à 1,234 + 2,119 + 0,3 ms. La marge est passée de 0,2 à 0,3 ms : à 500 /s, les 30 % étaient atteints
à 1,995 ms pour 2,034 ms simulées.

### UT40 : valeurs estimées en attendant la géométrie (21/10/2026)

| Terme | UT40 | Raisonnement |
|---|---|---|
| L_eff | 34 mm | même rapport longueur efficace / partie droite que l'UT19 : 40 × 12,7 / 15 |
| F | 15 kN | section 10 × 1,5 = 15 mm², deux fois celle de l'UT19, donc deux fois sa force (≈ 1 000 MPa) |
| Vitesse du striker | 6,0 / 19,9 / 37,4 m/s à 100 / 500 / 1 000 /s | formule ci-dessus |
| Onde incidente à 37,4 m/s | contrainte ≈ 0,487 × 37,4 × 8000 × 4871 ≈ 710 MPa dans les barres | élastique pour du maraging, mais **à confirmer : vitesse max du lanceur** |

Les deux premières valeurs sont à recaler sur le premier calcul UT40, comme pour l'UT19.

## 5. Livrables de la Task I (`report_taskI.py`)

```
python shpb-ut-equilibrium/scripts/post/report_taskI.py shpb-ut-equilibrium/results/<étude>_<date>
```

Sorties dans `results/<étude>_<date>/report/` : `T1_conditions.csv`, `F1_equilibrium`, `F2_forces_<SPEC>`,
`F3_stress_strain`, `F4_strain_rate`, `F5_striker_velocity` (chacune en `.pdf` pour le rapport et `.png`),
et `report.md` (texte en anglais, chiffres calculés automatiquement, à reprendre dans le rapport PDF).

Chaque figure et chaque tableau a une légende complète : ce qui est tracé, d'où vient le signal, comment le lire.
Les titres de sections ne sont pas numérotés (l'outil de conversion en PDF les numérote).

Plan de `report.md` : 1. Model and assumptions ; 2. Signal processing and definitions ; 3. Task I answers
(3.1 équilibre : F1, F1b = zoom sur la mise en équilibre (F_in et F_out en fonction du temps), T2 = effet du filtre ; 3.2 vitesses de chargement : F4, T3 = vitesse de déformation selon
plusieurs définitions, F5, limite des 30 %) ; 4. What the experiment will measure (F2, F3) ; 5. Numerical quality
(onde incidente / théorie, énergie cinétique initiale, dérive de l'énergie totale, hourglass) ; 6. Limitations ;
7. Conclusions (tableau de réponses).

### Traitement des signaux, comme dans les essais

| Étape | Choix | Pourquoi |
|---|---|---|
| Filtre | passe-bas Butterworth d'ordre 4, coupure **100 kHz**, sans déphasage (`filtfilt`), appliqué aux forces et à la déformation **avant** de calculer R | le labo filtre la jauge de sortie à 100 kHz : on compare simulation et essai avec la même « finesse ». Abaqus sort un point par µs (1 MHz) avec des vibrations de quelques µs que l'essai ne peut pas voir |
| Force « mesurée » | S22 de la jauge de sortie × aire de la barre, décalée de 400 mm / 4871 m/s = 82 µs | comme Beerli et al. (2026, fig. 5c) : la force de la jauge « ramenée » à l'éprouvette, comparée aux coupes SEC_IN et SEC_OUT |
| Déformation | extensomètre virtuel de 12 mm | équivalent de la corrélation d'images |

### Indicateurs (colonnes de T1)

| Colonne | Définition |
|---|---|
| achieved rate | pente de la déformation de l'extensomètre entre 5 % et min(25 %, 0,8 × déformation max) = déformation gagnée sur cet intervalle / temps mis (voir ci-dessous) |
| time to 30 % | du début du chargement (\|F_in\| > 2 % du max) à 30 % ; vide si jamais atteint |
| equilibrium from strain / after | déformation (et temps depuis le début du chargement) à partir de laquelle \|R\| < 5 % jusqu'à 30 % ; vide si jamais |
| max \|R\| after 5 % | plus grand \|R\| filtré entre 5 % et 30 % |
| max \|dF\| after 5 % | plus grand \|F_in − F_out\| (kN) au même moment : R grossit quand la force chute (striction), dF non |
| max gauge error after 5 % | plus grand \|F_jauge − F_out\| / F_max : écart entre ce que mesure la jauge et la vraie force dans l'éprouvette |

### Pourquoi la vitesse de déformation « obtenue » est prise entre 5 % et 25 %

La vitesse de déformation n'est pas constante pendant l'essai (F4) : un seul chiffre par calcul doit donc dire
**sur quelle partie** de l'essai il est pris. Ce chiffre sert à vérifier la formule de la vitesse du striker
(`make_run.py`), qui décrit un **régime établi** : onde incidente constante et force de l'éprouvette à peu près
constante (F ≈ 7 kN dans le terme 2F/ρcA). La fenêtre est choisie pour couvrir ce régime :

| Borne | Valeur | Raison |
|---|---|---|
| basse | 5 % | avant : démarrage. Montée de l'impulsion incidente (≈ 40–60 µs), mise en place des épaulements dans les logements (rebond : la vitesse devient même négative), et force de l'éprouvette qui monte de 0 à son maximum, donc terme de freinage 2F/ρcA qui change. Le maximum de force est atteint à 5,0 / 5,8 / 7,6 % de déformation (500 / 100 / 1 000 /s) : à partir de là le chargement est établi |
| haute | min(25 %, 0,8 × déformation max) | s'arrêter avant la fin de la fenêtre utile. Pour 500 et 1 000 /s (30 % atteints) : 0,8 × 30 % = 24 %. Pour 100 /s, l'impulsion s'arrête à 18,5 % : borne à 14,8 %, pour exclure le déchargement |

Comme les points sont équidistants en temps, la moyenne de la pente sur la fenêtre est exactement la **sécante** :
déformation gagnée / temps mis.

| Cas | Fenêtre | Temps | Vitesse obtenue |
|---|---|---|---|
| 100 /s | 5 → 14,8 % | 2,205 → 3,144 ms | 105 /s |
| 500 /s | 5 → 24 % | 1,523 → 1,872 ms | 546 /s |
| 1 000 /s | 5 → 24 % | 1,417 → 1,595 ms | 1 074 /s |

Dans la fenêtre, la vitesse n'est pas parfaitement constante : elle monte un peu (529 → 582 /s à 500 /s) car la
force baisse pendant la striction. Valeurs complémentaires (même signal filtré) :

| Cas | ε̇ au maximum de force | ε̇ nominale = ε_fin / durée du chargement | ε̇ avant le max de force (10e–90e percentile) |
|---|---|---|---|
| 100 /s | 100 /s (à 5,8 %) | 87 /s | 51 à 120 /s |
| 500 /s | 516 /s (à 5,0 %) | 475 /s | −147 à 531 /s |
| 1 000 /s | 1 010 /s (à 7,6 %) | 915 /s | −114 à 1 201 /s |

La dernière colonne montre qu'à 500 et 1 000 /s, la phase d'écrouissage uniforme (avant le maximum de force) se
fait à une vitesse qui n'est pas encore stable.

### Premiers livrables : étude `taskI_20261013-1554` (UT19, nouvelle vitesse du striker)

| Vitesse visée | Obtenue | 30 % | Équilibre (\|R\| < 5 %) | \|R\| max après 5 % | Erreur max de la jauge |
|---|---|---|---|---|---|
| 100 /s | 105 /s | non, 18,5 % max | dès 0,9 % | 0,9 % | 3 % |
| 500 /s | 546 /s | en 0,63 ms | dès 2,5 % | 3,8 % | 15 % |
| 1 000 /s | 1 073 /s | en 0,33 ms | **jamais durablement** | 13 % (dF ≤ 0,6 kN) | 39 % |
