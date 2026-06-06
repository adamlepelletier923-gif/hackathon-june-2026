import os, json, argparse
import numpy as np
import nibabel as nib
from scipy import ndimage

ap = argparse.ArgumentParser(description="Detecte l'apparition de nouvelles lesions rehaussantes (critere RANO) dans le temps, en espace atlas commun")
ap.add_argument("--patient", default="Patient-067")
ap.add_argument("--min-vol", type=float, default=0.5, help="taille mini d'une lesion pour la juger mesurable (mL)")
ap.add_argument("--margin", type=int, default=2, help="dilatation du territoire connu (voxels) pour tolerer le recalage")
args = ap.parse_args()

OVL = os.path.join("data", "web_nii", args.patient, "_overlay")
rows = json.load(open(os.path.join(OVL, "overlay.json")))

def load(week):
    img = nib.load(os.path.join(OVL, f"enh_{week}.nii.gz"))
    m = np.asarray(img.dataobj) > 0
    vox = float(np.prod(img.header.get_zooms()[:3])) / 1000.0   # mL / voxel
    return m, vox

known = None
out = {}
for r in rows:
    w = r["week"]
    m, vox = load(w)
    new_vol = 0.0
    n_new = 0
    known_vol = 0.0 if known is None else float(known.sum()) * vox
    if known_vol >= args.min_vol and m.any():
        ref = ndimage.binary_dilation(known, iterations=args.margin)
        lab, n = ndimage.label(m)
        for i in range(1, n + 1):
            comp = lab == i
            v = comp.sum() * vox
            if v < args.min_vol:
                continue
            overlap = np.logical_and(comp, ref).sum() / comp.sum()
            if overlap < 0.1:                       # lesion quasi absente du territoire connu
                n_new += 1
                new_vol += v
    out[w] = {"new_lesion": n_new > 0, "n_new": int(n_new), "new_vol": round(float(new_vol), 1)}
    known = m if known is None else np.logical_or(known, m)

json.dump(out, open(os.path.join(OVL, "new_lesions.json"), "w"), indent=1)
flagged = [w for w, d in out.items() if d["new_lesion"]]
print(f"{args.patient} : {len(flagged)} examen(s) avec nouvelle lesion -> {flagged}")
for w in flagged:
    print(" ", w, out[w])
