# NeuroTrack

**Suivi tumoral cérébral assisté.** De l'IRM brute à la décision clinique, en passant par la segmentation, la courbe de volume et le verdict de réponse au traitement.

> La segmentation de tumeur cérébrale est un problème déjà résolu. La vraie valeur est ailleurs : mesurer, suivre dans le temps, et en sortir une décision. NeuroTrack fait ce dernier kilomètre.

## Démo (vidéo)

> **À regarder en premier.** GitHub ne lit pas la vidéo directement dans la page : clique sur l'image ci-dessous pour ouvrir ou télécharger le fichier `neurotrack/assets/demo.mp4`, puis lance-le.

<p align="center">
  <a href="neurotrack/assets/demo.mp4">
    <img src="neurotrack/assets/demo-poster.png" width="82%" alt="Démonstration NeuroTrack">
  </a>
  <br>
  <sub><i>▶ Clique sur l'image pour lancer la démo &middot; fichier : <code>neurotrack/assets/demo.mp4</code></i></sub>
</p>

---

## Ce que ça fait

Un radiologue mesure aujourd'hui la tumeur à la main, en 2D, sur une seule coupe, avec une forte variabilité d'un lecteur à l'autre. NeuroTrack automatise toute la chaîne et la rend lisible :

```
IRM (4 séquences)  ->  modèle pré-entraîné  ->  masque tumoral
   ->  volume rehaussant  ->  comparaison dans le temps  ->  verdict RANO  ->  compte-rendu
```

On ne réentraîne jamais la segmentation, on la récupère telle quelle. Tout le travail est l'aval : la volumétrie, le suivi longitudinal, le recalage, la règle de décision et le rapport.

## Le tableau de bord

<p align="center">
  <img src="neurotrack/assets/dashboard.png" width="90%" alt="Trajectoire du volume et ruban RANO">
</p>

Pour chaque patient, une lecture en un coup d'oeil :

| Élément | Ce qu'il montre |
| --- | --- |
| Badge de tête | Le verdict de l'examen courant (STABLE, PROGRESSION, RÉPONSE...) avec un halo de couleur |
| Volume / Variation / Vitesse / Pic | Volume rehaussant actuel, évolution depuis l'examen précédent, vitesse en mL par mois, plus haut point du suivi |
| Courbe | Trajectoire du volume rehaussant, avec les repères baseline, nadir et les apparitions de lésion |
| Ruban RANO | Un verdict par examen, coloré, cliquable, aligné sous la courbe |
| Examen sélectionné | Détail de l'examen pointé : volume, verdict et sa raison lisible, nombre de coupes |
| Compte-rendu | Rapport généré automatiquement, éditable, copiable et exportable |

Le curseur et la lecture automatique font défiler la trajectoire ; tout le panneau (KPI, badge, cerveau, rapport) suit l'examen pointé.

## Le cerveau

<table>
<tr>
<td width="50%"><img src="neurotrack/assets/viewer.png" alt="Vue multiplanaire 2D + 3D"></td>
<td width="50%"><img src="neurotrack/assets/overlay.png" alt="Superposition de l'évolution"></td>
</tr>
<tr>
<td align="center"><sub>Examen seul, vue multiplanaire 2D recentrée sur la tumeur, plus rendu 3D</sub></td>
<td align="center"><sub>Superposition de l'évolution : un masque par date, du bleu (ancien) au rouge (récent)</sub></td>
</tr>
</table>

Le viewer (NiiVue, WebGL) charge les `.nii.gz` directement dans le navigateur. Deux modes :

- **Examen** : l'IRM d'une date avec son masque par dessus. En 2D la vue se recentre sur le centroïde de la tumeur pour qu'on la voie tout de suite, en 3D un rendu volumique.
- **Superposition** : tous les masques recalés sur une référence commune, empilés avec un dégradé temporel. On choisit les dates à afficher via les pastilles. C'est la lecture qui rend l'évolution évidente.

## Les briques techniques

**Verdict RANO volumétrique.** Une règle déterministe sur le seul volume rehaussant : hausse vs nadir (progression), baisse vs baseline (réponse), passage sous le seuil mesurable (réponse complète), sinon stable. Chaque verdict affiche sa raison ("hausse de 41% sur le nadir"...). Ne lit aucune cotation externe, donc tourne tel quel sur un patient jamais coté.

**Segmentation in-app.** Le modèle MONAI `brats_mri_segmentation` tourne dans le backend, chargé à la demande. Le bouton "Ajouter une IRM" téléverse 4 séquences (T1c, T1, T2, FLAIR), segmente, et l'examen devient un patient suivi. On garde le canal rehaussant, celui que RANO mesure.

**Recalage et détection de nouvelle lésion, in-app.** Les examens d'un même patient ne sont pas dans le même espace. Le backend les recale (rigide, SimpleITK) sur la référence la mieux couverte, applique la transformation aux masques, puis cherche par composantes connexes les foyers qui apparaissent là où il n'y avait rien. Une nouvelle lésion force un verdict de progression, critère RANO indépendant du volume. Même résultat pour un patient du cache ou ajouté à la main.

**Compte-rendu.** Texte clinique généré depuis les chiffres : volume, variation, catégorie de suivi, conduite suggérée. Éditable et exportable.

## Stack

```
Backend    FastAPI (Python)            timeline, verdict RANO, overlay, compte-rendu, segmentation
ML         MONAI BraTS (TorchScript)   segmentation rehaussant, récupéré tel quel, jamais réentraîné
           SimpleITK                   recalage rigide inter-examens
           scipy.ndimage               composantes connexes (nouvelle lésion)
Frontend   React + Vite + TypeScript   tout en TypeScript
           Tailwind                    style
           ECharts                     courbe de volume et ruban RANO
           NiiVue                      cerveau 2D multiplanaire et 3D
Données    LUMIERE (public)            gliomes, IRM longitudinales, cotations RANO
Stockage   fichiers (pas de base)      manifest.json par patient + .nii.gz
```

## Lancer (rapide, sans GPU)

Les données de démo de plusieurs patients sont incluses, l'app tourne directement.

Prérequis : Python 3.11+ et Node 20+.

```bash
cd neurotrack
python -m venv .venv
.venv/bin/pip install -r requirements.txt

cd frontend && npm install && cd ..

./run.sh
```

`run.sh` lance le backend (FastAPI, port 8077) et le frontend (Vite). Ouvre l'URL affichée par Vite (http://localhost:5173). Ctrl-C arrête les deux.

Dans l'app : choisir un patient, parcourir les examens (curseur ou flèches) ou lancer la lecture automatique, lire le ruban RANO et ses raisons, basculer 2D / 3D, activer la superposition pour voir la tumeur évoluer, relire et exporter le compte-rendu.

## Ajouter une IRM (segmentation in-app)

Le bouton "Ajouter une IRM" téléverse 4 séquences (T1c, T1, T2, FLAIR) déjà recalées et skull-strippées ; le backend lance le modèle à la demande et l'examen devient un patient suivi (manifest + nii, visible dans la liste). Réajouter le même nom avec une autre semaine ajoute un point à sa timeline.

Cela demande les dépendances ML côté backend :

```bash
.venv/bin/pip install -r requirements-ml.txt
```

Sans elles, les patients déjà en cache marchent ; `/api/segment` renvoie une erreur. Le modèle attend des images prétraitées comme LUMIERE, un DICOM brut non recalé ne marchera pas tel quel.

## Structure

```
neurotrack/backend/app.py        API FastAPI (timeline, verdict RANO, overlay, compte-rendu, segmentation) + sert les .nii.gz
neurotrack/backend/seg.py        segmentation par le modèle MONAI, chargement paresseux, à la demande
neurotrack/backend/overlay.py    recalage inter-examens + superposition + détection de nouvelle lésion
neurotrack/frontend/             app React (Vite + Tailwind + ECharts + NiiVue)
neurotrack/assets/               captures et vidéo de démo
neurotrack/data/                 données de démo LUMIERE : CSV cotations + nii de plusieurs patients
```

## Limites honnêtes

- Le verdict RANO ne suit que le volume rehaussant. Il colle sur les progressions franches mais diverge de l'expert au milieu du suivi, là où RANO s'appuie aussi sur le FLAIR, les nouvelles lésions et la clinique. Decision-support, pas diagnostic.
- On ne distingue pas vraie progression et pseudoprogression (hors scope).
- Le recalage inter-examens est rigide : il suffit pour des examens du même patient mais ne corrige pas les déformations locales des tissus.
- La segmentation est un modèle pré-entraîné généraliste, pas validé cliniquement.
