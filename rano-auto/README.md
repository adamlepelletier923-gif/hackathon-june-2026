# RANO-Auto — preuve de concept suivi longitudinal

Charge le suivi de 5 patients du dataset LUMIERE (glioblastome, IRM longitudinale) et
trace le volume tumoral rehaussant dans le temps avec la cotation RANO experte en regard.

Astuce cle : on ne telecharge pas les 32 Go du dataset. Les masques de segmentation sont
tires a la demande dans le zip distant via `remotezip` (range requests), ~2 Mo au total.

## Lancer

```
python -m venv --system-site-packages .venv
.venv/bin/python -m pip install nibabel remotezip requests pandas numpy matplotlib jupyter
.venv/bin/python -m jupyter notebook suivi_5_patients.ipynb
```

Le CSV des cotations RANO est deja dans `data/`. Le notebook cree `data/seg_cache/`
(masques mis en cache) et `data/namelist.json` (index du zip) a la premiere execution.

## Fichiers

- `suivi_5_patients.ipynb` : le notebook
- `build_nb.py` : regenere le notebook
- `data/LUMIERE-ExpertRating.csv` : cotations RANO expertes
- `data/suivi_5_patients.png` : sortie de reference
