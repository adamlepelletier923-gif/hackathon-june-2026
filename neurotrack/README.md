# NeuroTrack — suivi tumoral cerebral assiste

App web qui transforme les IRM de suivi d'un patient (gliome) en un tableau de bord
clinique : courbe du volume tumoral dans le temps, verdict de reponse au traitement
(RANO) automatique, cerveau 3D avec la tumeur, superposition des segmentations dans le
temps, et compte-rendu pret a relire.

## Pourquoi ce projet

La segmentation de tumeur cerebrale est un probleme deja resolu par des modeles
pre-entraines (HD-GLIO, nnU-Net, MONAI). Refaire un segmentateur n'a aucun interet.
La vraie valeur, le "dernier kilometre", c'est ce qu'on fait APRES le masque :
mesurer le volume, le suivre dans le temps, et en sortir une DECISION (le traitement
marche, oui ou non).

Aujourd'hui un radiologue mesure ca a la main, en 2D, sur une seule coupe, avec une
forte variabilite. NeuroTrack automatise la chaine : IRM brute -> segmentation par un
modele pre-entraine -> volume -> verdict RANO volumetrique -> compte-rendu.

On ne reentraine jamais la segmentation, on la pulle. Notre travail est l'aval.

## Comment ca marche (pipeline)

```
IRM (4 sequences) --> modele pre-entraine (MONAI BraTS) --> masque tumoral
   --> volume rehaussant --> comparaison dans le temps --> verdict RANO --> compte-rendu
```

- Segmentation : modele MONAI `brats_mri_segmentation` (pulle, jamais reentraine).
- Donnees de demonstration : dataset public LUMIERE (gliomes, IRM longitudinales avec
  cotation RANO experte). On valide notre segmentation contre les masques de reference
  du dataset (Dice ~0.87).
- Verdict RANO volumetrique simplifie sur le volume rehaussant (PD/SD/PR/CR).

## Lancer l'app web (rapide, sans GPU)

Les donnees de demonstration d'un patient sont deja incluses, l'app tourne directement.

Prerequis : Python 3.11+ et Node 20+.

```bash
cd neurotrack
python -m venv .venv
.venv/bin/pip install -r requirements.txt

cd frontend && npm install && cd ..

./run.sh
```

`run.sh` lance le backend (FastAPI, port 8077) et le frontend (Vite). Ouvre l'URL
affichee par Vite (http://localhost:5173). Ctrl-C arrete les deux.

Dans l'app : choisir un patient, parcourir les examens (slider / fleches), basculer le
cerveau en 2D/3D, comparer notre modele au dataset, et activer le mode "superposition"
pour voir la tumeur evoluer dans le temps (couleurs bleu=ancien -> rouge=recent).

## Regenerer les donnees / ajouter un patient (necessite GPU + telechargement)

Le pipeline complet (segmentation par le modele) demande les dependances lourdes :

```bash
.venv/bin/pip install -r requirements-ml.txt
```

Puis, pour un patient du dataset LUMIERE :

```bash
.venv/bin/python precompute_seg.py --patient Patient-031   # segmente chaque examen (GPU)
.venv/bin/python export_nii.py     --patient Patient-031   # exporte les nii pour le viewer
.venv/bin/python build_overlay.py  --patient Patient-031   # masques atlas pour la superposition
```

Les images sont tirees a la demande du dataset LUMIERE (range requests, pas de
telechargement des 32 Go).

## Structure

```
backend/app.py        API FastAPI (timeline, verdict RANO, overlay, compte-rendu) + sert les .nii.gz
frontend/             app React (Vite + Tailwind + ECharts + NiiVue)
segment.py            segmentation par modele pre-entraine + comparaison a la reference
precompute_seg.py     segmente tous les examens d'un patient et met en cache
export_nii.py         exporte les .nii.gz consommes par le viewer 3D
build_overlay.py      masques en espace atlas commun pour la superposition multi-dates
visualize.py          viewer local IRM + masque (matplotlib)
compare_viewer.py     viewer local IRM | seg dataset | seg custom
suivi_5_patients.ipynb notebook d'exploration du suivi longitudinal
PLAN.md               plan d'action du projet
data/                 donnees de demo (LUMIERE) : CSV cotations + nii d'un patient
```

## Limites honnetes

- Le verdict RANO ne suit que le volume REHAUSSANT. Il colle sur les progressions
  franches mais diverge de l'expert au milieu du suivi, la ou RANO s'appuie aussi sur
  le FLAIR, les nouvelles lesions et la clinique. Decision-support, pas diagnostic.
- On ne distingue pas vraie progression et pseudoprogression (hors scope).
- La superposition multi-dates utilise les masques du dataset en espace atlas commun
  (deja co-registres). Superposer NOS masques demanderait un recalage inter-examens.
- La segmentation est un modele pre-entraine generaliste, pas valide cliniquement.
```
