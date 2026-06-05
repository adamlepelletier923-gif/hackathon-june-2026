# NeuroTrack — plan d'action app web de suivi tumoral (nom provisoire)

## Vision en une phrase
Une app web qui prend les IRM de suivi d'un patient, fait tourner NOTRE modèle de
segmentation, et transforme ça en un tableau de bord clinique : courbe de volume
tumoral dans le temps, verdict RANO automatique (le traitement marche / ne marche pas),
cerveau 3D avec la tumeur, et compte-rendu pret a signer. Le dernier kilometre, pas le
masque brut.

## Le principe directeur
Chaque phase doit etre DEMONTRABLE seule. Si la 3D plante a H40, le dashboard suffit a
gagner. On construit du plus utile (coeur clinique) vers le plus sexy (3D), jamais
l'inverse.

---

## Stack technique (choisie pour aller vite ET que ce soit beau)

Frontend
- React + Vite + TypeScript
- Tailwind + shadcn/ui (look moderne propre sans CSS a la main)
- ECharts pour les graphes (animations fluides, zones colorees, stylé)
- NiiVue pour la visu medicale (charge les .nii.gz directement dans le navigateur,
  overlay du masque, rendu 3D volumique, rotation) — colle parfaitement a nos donnees

Backend
- FastAPI (Python) — reutilise DIRECTEMENT notre pipeline MONAI existant (segment.py)
- sert : liste patients, timeline (volumes + RANO + verdict), fichiers .nii.gz pour
  NiiVue, compte-rendu genere
- (stretch) endpoint /segment : upload d'une IRM neuve -> notre modele -> masque (le
  "mode client")

Donnees
- on s'appuie sur le cache deja construit (data/cmp_cache : volumes par examen) et on
  etend precompute_seg.py pour exporter aussi les .nii.gz (image + masque custom +
  masque dataset) que NiiVue consomme.

---

## Architecture

```
  navigateur (React)
     │  REST/JSON + fichiers .nii.gz
  FastAPI
     ├── lit data/cmp_cache/<patient>/  (manifeste volumes + verdicts)
     ├── sert les .nii.gz (image, seg custom, seg dataset)
     ├── calcule le verdict RANO (regle volumetrique)
     └── genere le compte-rendu
        │
   pipeline MONAI (notre modele pre-entraine) — deja fait dans segment.py
```

---

## Les features, triees par valeur

### Coeur UTILE (must-have, c'est le projet)
1. Selecteur de patient + timeline des examens.
2. Courbe du volume tumoral rehaussant (mL) dans le temps, avec marqueurs RANO experts.
3. VERDICT RANO AUTOMATIQUE entre examens consecutifs (variation de volume -> PD/SD/PR/CR).
4. Cartes KPI : volume actuel, variation depuis le dernier examen, vitesse (mL/mois),
   badge statut (gros badge colore PROGRESSION / STABLE / REPONSE).
5. Comparaison baseline vs examen courant (cote a cote, delta volume + %).
6. Compte-rendu structure auto-genere (type BT-RADS), editable.

### Sexy (le waouh du pitch)
7. Cerveau 3D (NiiVue) avec la tumeur en couleur, rotatable.
8. Scrubber temporel : on glisse dans le temps, la tumeur grossit/retrecit en 3D ET sur
   la courbe en meme temps.
9. Theme sombre, jauge de vitesse de croissance, transitions animees.
10. Toggle source de seg : NOTRE modele vs reference dataset (montre qu'on valide).

---

## Decoupage en etapes d'action

### Phase 0 — Setup & tuyauterie donnees (H0–H3)
- [ ] structure repo : /backend (FastAPI), /frontend (Vite React)
- [ ] front : init Vite + Tailwind + shadcn + installer niivue et echarts
- [ ] back : squelette FastAPI + CORS + endpoint /patients (lit cmp_cache)
- [ ] ETENDRE precompute_seg.py : exporter par examen image_1mm.nii.gz,
      seg_custom.nii.gz, seg_dataset.nii.gz (pour NiiVue)
- [ ] endpoint qui sert ces .nii.gz
LIVRABLE : le front liste les patients depuis l'API.

### Phase 1 — Dashboard coeur (H3–H12)  [le plus important]
- [ ] back : endpoint /patients/{id}/timeline -> [{week, semaine, vol_enh, rano,
      verdict_auto, delta_pct, velocity}]
- [ ] back : implementer la regle RANO volumetrique (voir section dediee)
- [ ] front : VolumeTimelineChart (ECharts) — courbe + zones colorees RANO + marqueurs
- [ ] front : 4 cartes KPI + gros badge statut
LIVRABLE : on ouvre un patient, on voit sa trajectoire + le verdict. Demontrable seul.

### Phase 2 — Visu 2D + comparaison (H12–H20)
- [ ] front : viewer de coupes (NiiVue en mode 2D ou canvas) avec overlay masque
- [ ] front : toggle seg custom / dataset
- [ ] front : panneau comparaison baseline vs courant (2 coupes, delta)
LIVRABLE : on voit l'image + le masque + on compare deux dates.

### Phase 3 — Cerveau 3D (H20–H30)  [le centerpiece sexy]
- [ ] front : BrainViewer3D avec NiiVue (rendu volumique image + overlay seg)
- [ ] front : scrubber temporel synchronise avec la courbe (changer d'examen met a jour
      la 3D et le graphe ensemble)
- [ ] stretch : glass brain (cerveau translucide) + tumeur en mesh plein (marching cubes)
LIVRABLE : la tumeur en 3D qui evolue quand on scrub le temps.

### Phase 4 — Compte-rendu + polish (H30–H40)
- [ ] back : generation du compte-rendu structure (chiffres mesures -> texte, gabarit
      strict, pas d'invention)
- [ ] front : ReportPanel editable + bouton exporter
- [ ] polish : theme sombre, animations, transitions, responsive
LIVRABLE : du masque au brouillon de CR signable.

### Phase 5 — Prepa demo (H40–H48)
- [ ] choisir LE patient demo (Patient-067 : belle histoire resection -> recidive PD)
- [ ] precalculer son cache + tous ses .nii.gz
- [ ] ecrire le script du pitch (3 min)
- [ ] cas de secours figes (captures/GIF si le live foire)

---

## La regle RANO a coder (volumetrique simplifiee)

On suit le volume tumoral REHAUSSANT (label 2 HD-GLIO / canal ET de notre modele).
Reference = nadir (plus petit volume post-baseline).

- CR (reponse complete) : volume rehaussant = 0
- PR (reponse partielle) : baisse >= 65% vs baseline
- PD (progression)       : hausse >= 40% vs nadir, OU nouvelle lesion
- SD (stable)            : entre les deux

Note honnete : seuils volumetriques approximes (RANO 2.0 : +40% volume = PD ; le -65%
est l'equivalent volumetrique du -50% bidimensionnel). On NE gere PAS la pseudoprogression
(demande confirmation a 12 semaines / perfusion). A afficher comme limite.

---

## Roles (a adapter selon la taille de l'equipe)
- Dev A (dataviz/front) : timeline chart, KPI, theme, animations
- Dev B (3D/front) : NiiVue 2D puis 3D, scrubber synchronise
- Dev C (back/ML) : FastAPI, export .nii.gz, regle RANO, compte-rendu
Les trois tracks avancent en parallele apres la Phase 0.

---

## Risques & plans B
- NiiVue 3D / courbe d'apprentissage -> plan B : montage 2D + GIF rotatif pre-rendu
- "mode client" (upload IRM neuve) lourd a securiser -> rester en stretch, demo sur cache
- regle RANO cas limites -> simplifier, assumer les seuils
- perf navigateur sur gros volumes -> servir des .nii.gz cropes/downsamples (deja crope
  dans le cache)

---

## Le script de demo (3 min, ce qu'on montre au jury)
1. On ouvre un patient. Le dashboard charge : badge "PROGRESSION", vitesse de croissance,
   variation depuis le dernier examen.
2. On glisse le scrubber temporel : la tumeur grossit en 3D pendant que la courbe se
   trace. "On voit le traitement echouer en direct."
3. On montre le verdict RANO auto en regard de la cotation experte du dataset : ca colle.
4. On bascule seg custom / reference : notre modele retrouve la tumeur (Dice ~0.87).
5. On affiche le compte-rendu auto-genere, on corrige un mot, on signe.
Punchline : "de l'IRM brute au verdict signable, sans intervention manuelle, en quelques
secondes."
```
