# Matériaux

Les fichiers `model/materials/*.dat` sont **générés** par `scripts/pre/make_materials.py`.
On ne les modifie pas à la main : on change les paramètres du script et on le relance.

```bash
python shpb-ut-equilibrium/scripts/pre/make_materials.py
```

Convention du labo : un `.dat` ne contient que les mots-clés du matériau. Il est inclus dans le `.inp` principal :

```
*MATERIAL, NAME=DP1000
*INCLUDE, INPUT=DP1000.dat
*SOLID SECTION, ELSET=UT19_ALL, MATERIAL=DP1000
```

Unités : **mm, N, s, MPa, t/mm³** (1 kg/m³ = 1e-12 t/mm³).

## Affectation

| Pièce | Matériau | Fichier |
|---|---|---|
| INPUT_BAR, OUTPUT_BAR, PUSHER | acier maraging | `MARAGING.dat` |
| STRIKER | acier | `STRIKER_STEEL.dat` |
| UT19 / UT40 | DP1000 | `DP1000.dat` |

## Données et sources

**Barres, pusher, striker : élastiques linéaires.** E est déduit de la vitesse des ondes mesurée sur le banc,
E = ρc² (Beerli et al. 2026, section 2.5) :

| Matériau | c [m/s] | ρ [kg/m³] | E [MPa] | ν |
|---|---|---|---|---|
| MARAGING | 4871 (barre d'entrée) | 8000 *(hypothèse)* | 189 813 | 0.3 |
| STRIKER_STEEL | 4720 | 7850 *(hypothèse)* | 174 885 | 0.3 |

- Le pusher est en maraging traité (Beerli 2026). L'ancien fichier CAO indique de l'acier à outils A2 : à confirmer.
- La barre de sortie est en « même maraging » que la barre d'entrée (Beerli 2026), sans vitesse mesurée propre.
- Option à tester : Roth et al. (2015) prennent ν = 0 dans la barre d'entrée pour supprimer la dispersion géométrique.

**Éprouvette : DP1000** (Beerli et al. 2026, tableau 4). C'est le matériau utilisé dans leur propre validation
numérique du banc (tôle de 1,5 mm, von Mises, écrouissage isotrope, indépendant de la vitesse).

- E = 195 GPa, ν = 0.33, ρ = 7850 kg/m³
- Écrouissage Swift-Voce :
  k(εp) = α·A·(εp + ε0)ⁿ + (1 − α)·(k0 + Q·(1 − e^(−β·εp)))
  avec A = 1395 MPa, ε0 = 1e-6, n = 0.0892, k0 = 739 MPa, Q = 301 MPa, β = 102, α = 0.5
- Tabulé de εp = 0 à 2 (80 points, espacement logarithmique). Au-delà, Abaqus garde la dernière valeur.
- Contrôle : k(0) = 573 MPa, k(0,002) = 798 MPa, k(0,1) = 1088 MPa, k(1) = 1218 MPa.

**À confirmer avec le maître de stage :** le matériau d'éprouvette à utiliser pour la Task I, les densités des barres,
et le matériau réel du pusher.
