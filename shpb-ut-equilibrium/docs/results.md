# Dépouillement des calculs

Ce document explique **comment** les résultats sont calculés. Les résultats eux-mêmes sont dans
`results/<étude>/report/report.md` (en anglais, régénéré à chaque fois).

---

## 1. La chaîne

| Étape | Script | Où | Sortie |
|---|---|---|---|
| Extraction | `scripts/post/extract_history.py` (lancé par `fetch_study.py`) | Euler, Python d'Abaqus | `<case>_history.csv` : une ligne par µs |
| Livrables | `scripts/post/report_taskI.py results/<étude>` | PC, Python 3 + numpy, pandas, matplotlib, scipy | `report/` (rapport, tableau, figures) et une figure de contrôle par calcul |

Colonnes de `<case>_history.csv` (demi-modèle : forces et énergies déjà multipliées par 2) :

| Colonne | Contenu |
|---|---|
| `time_s` | temps (s) |
| `eps_gauge_in`, `sig_gauge_in` | déformation LE22 et contrainte S22 moyennes de la jauge de la barre d'entrée |
| `eps_gauge_out`, `sig_gauge_out` | idem, jauge de la barre de sortie |
| `F_sec_in_N`, `F_sec_out_N` | force dans les coupes SEC_IN (côté pusher) et SEC_OUT (côté barre de sortie) |
| `u2_ext_in_mm`, `u2_ext_out_mm`, `eps_ext` | déplacements des deux nœuds de l'extensomètre et déformation nominale |
| `ALLKE_mJ` … `ETOTAL_mJ` | énergies du modèle (cinétique, interne, hourglass, travail, frottement, total) |

---

## 2. Traitement des signaux (comme dans les essais)

| Étape | Choix | Pourquoi |
|---|---|---|
| Filtre | passe-bas Butterworth d'ordre 4, coupure **100 kHz**, sans déphasage (`filtfilt`), appliqué aux forces et à la déformation **avant** de calculer $R$ | le labo filtre la jauge de sortie à 100 kHz (Roth et al. 2015). Abaqus écrit un point par µs avec des vibrations de quelques µs que l'essai ne peut pas voir |
| Jauge virtuelle | **comme au labo : moyenne d'une jauge en haut et d'une jauge en bas de la barre** (éléments de surface de la tranche, près du plan de symétrie), ce qui annule la flexion. Depuis le 21/10/2026 ; avant : moyenne simple de toute la tranche | la barre de sortie fléchit (charge excentrée) : jusqu'à ±10 MPa entre le haut et le bas à 1 000 /s. Diagnostic : la moyenne simple, la moyenne pondérée et la paire donnent la même force (écart < 0,5 %) |
| Force « mesurée » | $F_{jauge}(t) = A\,E\,\varepsilon_{jauge}(t + \Delta t)$, $\Delta t$ = 400 mm / 4871 m/s = 82 µs | comme Beerli et al. (2026, fig. 5c) : force de la jauge « ramenée » à l'éprouvette, sans correction de dispersion |
| Déformation | extensomètre virtuel : 12 mm (UT19), 30 mm (UT40) | équivalent de la corrélation d'images |

Les vraies forces de l'éprouvette ($F_{in}$, $F_{out}$) servent à juger l'**équilibre** ; la force de la jauge sert
seulement à montrer ce que l'**essai mesurera**.

---

## 3. Indicateurs

**Équilibre.**

$$
R = \frac{F_{in} - F_{out}}{F_{moy}}, \qquad F_{moy} = \frac{F_{in} + F_{out}}{2}, \qquad \text{équilibre si } |R| < 5\ \%
$$

| Indicateur | Définition |
|---|---|
| début du chargement | premier instant où $F_{in}$ dépasse 2 % de son maximum |
| fenêtre utile | du début du chargement à 30 % de déformation (ou à la déformation maximale) |
| équilibre à partir de | déformation (et temps) à partir de laquelle $\lvert R\rvert$ < 5 % **jusqu'à la fin de la fenêtre** ; vide si jamais |
| plus long intervalle à l'équilibre | pour un équilibre partiel : de quelle à quelle déformation $\lvert R\rvert$ reste < 5 % sans interruption |
| max $\lvert R\rvert$ et max $\lvert\Delta F\rvert$ après 5 % | $R$ grossit quand la force chute (striction), $\Delta F = F_{in} - F_{out}$ non : on donne les deux |
| erreur max de la jauge après 5 % | $\max \lvert F_{jauge} - F_{out}\rvert / F_{max}$ |
| contrôles numériques | onde incidente / théorie, énergie cinétique initiale / $\tfrac12 mV^2$, dérive de l'énergie totale, hourglass / énergie interne |

**Vitesse de déformation obtenue** (une valeur par calcul) :

$$
\dot\varepsilon = \frac{\varepsilon_2 - \varepsilon_1}{t_2 - t_1}, \qquad \varepsilon_1 = 5\ \%, \qquad \varepsilon_2 = 0{,}8\,\varepsilon_{max}
$$

La vitesse n'est pas constante pendant l'essai : un chiffre unique doit dire sur quelle partie il est pris. Il sert
à vérifier la formule de la vitesse du striker (section 4), qui décrit un **régime établi** (onde incidente
constante, force de l'éprouvette à peu près constante). La fenêtre couvre ce régime :

| Borne | Raison |
|---|---|
| 5 % | avant : démarrage (montée de l'impulsion ≈ 40–60 µs, épaulements qui se calent dans les logements avec rebond, force qui monte de 0 à son maximum). Le maximum de force est atteint vers 5 % (5,0 / 5,8 / 7,6 % à 500 / 100 / 1 000 /s) |
| 0,8 × déformation max | s'arrêter avant la fin, où la vitesse retombe quand l'impulsion s'arrête : 24 % quand 30 % sont atteints ; 14,8 % à 100 /s, où l'impulsion s'arrête à 18,5 %. (Jusqu'au 21/10 la formule était min(25 %, 0,8 × déformation max), qui donne exactement les mêmes valeurs : la borne de 25 % ne servait jamais) |

Les points étant équidistants en temps, c'est exactement la **déformation gagnée divisée par le temps mis**. Le
rapport donne aussi d'autres définitions (valeur au maximum de force, valeur nominale = déformation finale / durée
totale, plage de variation avant et après le maximum de force).

---

## 4. Vitesse du striker et durée simulée (`make_run.py`)

Vitesse d'allongement du LID : l'onde incidente pousse le pusher, l'éprouvette le freine et pousse la barre de sortie.

$$
v \approx 2\,v_i - \frac{2F}{\rho c A}, \qquad v_i = K\,V_{striker}, \qquad K = \frac{Z_{striker}}{Z_{striker}+Z_{barre}} = 0{,}487
$$

Avec $v = \dot\varepsilon\,L_{eff}$ :

$$
V_{striker} = \frac{\dot\varepsilon\,L_{eff} + 2F/(\rho c A)}{2K}, \qquad \rho c A = 8000 \times 4871 \times \pi \times 0{,}01^2 = 12\,242\ \text{N·s/m}
$$

| Éprouvette | $L_{eff}$ | $F$ | Origine | Vitesses du striker à 100 / 500 / 1 000 /s |
|---|---|---|---|---|
| UT19 | 12,7 mm | 7 kN | calées sur un premier calcul à 500 /s (485 /s obtenus ; force moyenne 6,4–6,8 kN) | 2,48 / 7,69 / 14,20 m/s |
| UT40, UT40S | 30,1 mm | 10,4 kN | calées le 23/10 sur les calculs UT40 à 100 et 500 /s de `taskI_20261023-1140` (138 /s à 6,00 m/s, 590 /s à 19,95 m/s : deux équations, deux inconnues). Valeurs de départ estimées : 34 mm et 15 kN. La force efficace est basse car la force chute fortement pendant la striction | 4,83 / 17,2 / 32,6 m/s |

- $L_{eff}$ est plus court que la partie droite (12,7 contre 15 mm pour l'UT19) car l'extensomètre voit la zone la
  plus déformée.
- À 100 /s, le terme $2F/\rho c A$ (1,14 m/s) pèse autant que le terme utile (1,27 m/s) : 10 % d'erreur sur $F$
  donne environ 10 % d'erreur sur la vitesse de déformation.
- Première estimation sans le terme de force ($V = \dot\varepsilon \times$ 15 mm) : 21 /s au lieu de 100 /s.
- UT40 à 1 000 /s : 32,6 m/s donnent environ 620 MPa dans les barres (élastique pour du maraging) ; **la vitesse
  maximale du lanceur est à confirmer**.

**Durée simulée** :

$$
T = \underbrace{1{,}234\ \text{ms}}_{\text{arrivée de l'onde}} + \frac{0{,}30}{\dot\varepsilon} + \underbrace{0{,}3\ \text{ms}}_{\text{marge}}, \qquad
\text{plafonnée à } 1{,}234 + 2{,}119 + 0{,}3\ \text{ms (fin de l'impulsion)}
$$

soit 3,65 / 2,13 / 1,83 ms à 100 / 500 / 1 000 /s. Une colonne `t_step_ms` dans `cases.csv` peut l'imposer.

**Limite des 30 %** : l'impulsion du striker de 5 m dure 2 × 5 m / 4720 m/s = 2,12 ms, donc 30 % demandent au moins
0,30 / 2,12 ms ≈ 142 /s. À 100 /s on s'arrête à 18,5 % (UT19).

---

## 5. Historique des études

| Étude | Changement | Constat |
|---|---|---|
| `taskI_20261012-1811` | premier lancement, 4 ms simulées | le pusher bascule sous la charge excentrée → guidages (U3 = 0) |
| `taskI_20261013-1127` | guidages ; striker $V = \dot\varepsilon \times$ 15 mm | 100 /s ne donne que 21 /s → formule avec la force de l'éprouvette |
| `taskI_20261013-1554` | nouvelle formule, durée par cas | 105 / 546 / 1 073 /s ; résultats dans `results/taskI_20261013-1554/` |
| `diag_20261021-1626` | sondes de force le long de la sortie (1 000 /s) | les oscillations naissent avant la tête : l'éprouvette traverse le jeu et frappe la tête de sortie |
| `taskI_20261022-1138` | **mise en contact initiale** (jeux fermés, `CLOSE_GAPS`) ; sondes à 1 000 /s | équilibre dès le début aux 3 vitesses ; erreur de la jauge 1,5 / 3,9 / 4,8 % (au lieu de 3 / 15 / 39 %) ; **étude de référence** |
| `taskI_20261023-1140` | UT40 (géométrie du DXF), vitesses du striker estimées | 138 / 590 / 770 /s ; équilibre complet seulement à 100 /s ; à 1 000 /s striction au bout côté pusher, **hors de l'extensomètre** (bloqué à 12,6 %) ; formule recalée |
| `taskI_20261023-1518` | UT40 avec la formule recalée + UT40S (partie droite parfaitement droite) | 82 / 498 / 940 /s ; UT40 = UT40S (le rétrécissement ne joue pas) ; 30 % atteints à 1 000 /s ; à 500 /s, chute brutale des forces vers 19 % de déformation (cause à identifier) |

---

## 6. Diagnostic des oscillations de la jauge de sortie

| Outil | Ce qu'il fait |
|---|---|
| `scripts/post/diag_gauge.py <calcul>` (Python d'Abaqus, sur un `.odb`) | compare trois lectures de la jauge (moyenne simple, moyenne pondérée, paire haut + bas) et la flexion |
| étude `studies/diag/` (`probes = 1`) | calcul avec des **sondes** : force à travers 5 tranches du chemin tête de sortie → collage → barre |
| `scripts/post/plot_probes.py <calcul>` | trace la force à chaque sonde contre la vraie force de l'éprouvette, et l'écart à chaque endroit |

Sondes (positions définies dans `make_run.py`, `PROBES`) : `HEAD_MID` (tête, 14 mm au-dessus du collage),
`HEAD_TIE` (tête, 4 mm au-dessus), `BAR_TIE` (barre, première couche sous le collage), `BAR_100` et `BAR_250`
(barre, à 100 et 250 mm du bout). Force d'une tranche = somme de S22 × volume des éléments / épaisseur
(une couche d'hexaèdres dans la barre ; une tranche de 5 mm de tétraèdres dans la tête).

Résultat (étude `diag_20261021-1626`, UT19 à 1 000 /s, détails dans `journal/2026-10-22.md`) : toutes les sondes
montrent la même oscillation que la jauge (écart 45–46 %, jauge 42 %). Elle naît avant le collage : l'éprouvette,
centrée dans les logements, parcourt ≈ 0,3 mm avant de tirer sur la tête de sortie, la **frappe** (pic de 15 kN,
deux fois la force de l'éprouvette) et la tête vibre ensuite à ≈ 40 kHz pendant ≈ 0,25 ms.

Décision (encadrants, 22/10) : au labo, tout est au contact avant l'essai. Les jeux sont fermés dans le modèle
(`CLOSE_GAPS`, voir `docs/assembly.md`, « Mise en contact initiale ») ; les calculs sont à relancer.
Comparaison avant / après : `py shpb-ut-equilibrium/scripts/post/compare_studies.py <étude avant> <étude après>
"<nom avant>" "<nom après>"` (même traitement que le rapport ; figures C1–C3 et tableau dans
`results/<étude après>/compare_<étude avant>/compare.md`).

---

## 7. Validité : striction, localisation, rupture (depuis le 27/10/2026)

Le matériau de l'éprouvette n'a **pas de critère de rupture**. Après la striction, la matière continue de s'étirer
jusqu'à ce que quelques éléments au centre de la striction s'écrasent (PEEQ qui passe d'environ 1 à 9 en 40 µs dans
l'UT40 à 500 /s, vu dans Abaqus/Viewer) : les deux forces de l'éprouvette chutent alors en ≈ 10 µs. Ce n'est pas un
effet de l'essai.

| Indicateur (rapport, tableau T7 et figure F6) | Définition |
|---|---|
| localisation brutale | première chute de la force moyenne (brute) de plus de 20 % de la force max en 10 µs, après le maximum de force |
| PEEQ max | plus grande déformation plastique équivalente de l'éprouvette à chaque image de sortie champ (`extract_peeq.py`) |
| rupture du DP1000 | 11 % de déformation nominale en traction quasi statique sur l'éprouvette UT de 40 × 10 mm (Beerli et al. 2026, § 4.1.1, fig. 7a) |

Les résultats au-delà de la rupture ne représentent pas un essai. Pour le DP1000, 30 % de déformation nominale ne sont
très probablement pas atteignables avec l'UT40 ; matériau et critère de rupture à décider avec les encadrants.
