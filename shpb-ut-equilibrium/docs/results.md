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
| UT40 | 34 mm | 15 kN | **estimées** : même rapport $L_{eff}$ / partie droite que l'UT19 (40 × 12,7 / 15), force × 2 (section 15 mm² au lieu de 7,5) ; à recaler sur le premier calcul | 6,0 / 19,9 / 37,4 m/s |

- $L_{eff}$ est plus court que la partie droite (12,7 contre 15 mm pour l'UT19) car l'extensomètre voit la zone la
  plus déformée.
- À 100 /s, le terme $2F/\rho c A$ (1,14 m/s) pèse autant que le terme utile (1,27 m/s) : 10 % d'erreur sur $F$
  donne environ 10 % d'erreur sur la vitesse de déformation.
- Première estimation sans le terme de force ($V = \dot\varepsilon \times$ 15 mm) : 21 /s au lieu de 100 /s.
- UT40 à 1 000 /s : 37,4 m/s donnent environ 710 MPa dans les barres (élastique pour du maraging) ; **la vitesse
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
