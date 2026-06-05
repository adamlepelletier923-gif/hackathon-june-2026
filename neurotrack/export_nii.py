import os, json, argparse
import numpy as np
import nibabel as nib

ap = argparse.ArgumentParser(description="Convertit le cache npz en .nii.gz (image, seg custom, seg dataset) pour NiiVue")
ap.add_argument("--patient", default="Patient-067")
args = ap.parse_args()

DATA = "data"
SRC = os.path.join(DATA, "cmp_cache", args.patient)
OUT = os.path.join(DATA, "web_nii", args.patient)
os.makedirs(OUT, exist_ok=True)
aff = np.diag([1.0, 1.0, 1.0, 1.0])   # 1mm iso, image et masques partagent la grille

manifest = json.load(open(os.path.join(SRC, "manifest.json")))
for w in manifest:
    d = np.load(os.path.join(SRC, f"{w}.npz"))
    wd = os.path.join(OUT, w)
    os.makedirs(wd, exist_ok=True)
    nib.save(nib.Nifti1Image(d["t1c"].astype(np.uint8), aff), os.path.join(wd, "image.nii.gz"))
    nib.save(nib.Nifti1Image(d["gt"].astype(np.uint8), aff), os.path.join(wd, "seg_dataset.nii.gz"))
    nib.save(nib.Nifti1Image(d["our"].astype(np.uint8), aff), os.path.join(wd, "seg_custom.nii.gz"))
print("nii exportes dans", OUT, "pour", len(manifest), "examens")
