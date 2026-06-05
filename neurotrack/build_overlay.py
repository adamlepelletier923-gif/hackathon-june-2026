import os, re, json, argparse
import numpy as np
import nibabel as nib
from remotezip import RemoteZip

ap = argparse.ArgumentParser(description="Exporte les masques rehaussants en espace ATLAS commun (DeepBraTumIA) pour la superposition multi-dates")
ap.add_argument("--patient", default="Patient-067")
args = ap.parse_args()

DATA = "data"
CACHE = os.path.join(DATA, "nii_cache")
OUT = os.path.join(DATA, "web_nii", args.patient, "_overlay")
os.makedirs(CACHE, exist_ok=True); os.makedirs(OUT, exist_ok=True)
P = args.patient
ZIP = "https://ndownloader.figshare.com/files/38249697"
ENH_LABEL = 1   # DeepBraTumIA atlas : 1 = Enhancing_Core

names = json.load(open(os.path.join(DATA, "namelist.json")))
weeks = sorted({n.split("/")[2] for n in names
                if n.startswith(f"Imaging/{P}/")
                and n.endswith("atlas/segmentation/seg_mask.nii.gz")},
               key=lambda w: int(re.match(r"week-(\d+)", w).group(1)))

def fetch(z, path):
    loc = os.path.join(CACHE, path.replace("/", "__"))
    if not os.path.exists(loc):
        with z.open(path) as s, open(loc, "wb") as d:
            d.write(s.read())
    return loc

rows = []
ref_saved = False
with RemoteZip(ZIP) as z:
    for w in weeks:
        base = f"Imaging/{P}/{w}/DeepBraTumIA-segmentation/atlas"
        try:
            seg = nib.load(fetch(z, f"{base}/segmentation/seg_mask.nii.gz"))
        except Exception:
            continue
        m = np.asarray(seg.dataobj)
        enh = (m == ENH_LABEL).astype(np.uint8)
        vox = float(np.prod(seg.header.get_zooms()[:3]))
        vol = round(float(enh.sum()) * vox / 1000, 1)
        nib.save(nib.Nifti1Image(enh, seg.affine, seg.header), os.path.join(OUT, f"enh_{w}.nii.gz"))
        rows.append({"week": w, "wn": int(re.match(r"week-(\d+)", w).group(1)), "vol": vol})
        if not ref_saved:
            img = nib.load(fetch(z, f"{base}/skull_strip/ct1_skull_strip.nii.gz"))
            a = np.asarray(img.dataobj).astype(np.float32)
            v = a[a > 0]
            a8 = np.clip(a / (np.percentile(v, 99) if v.size else 1) * 255, 0, 255).astype(np.uint8)
            nib.save(nib.Nifti1Image(a8, img.affine, img.header), os.path.join(OUT, "ref.nii.gz"))
            ref_saved = True

json.dump(rows, open(os.path.join(OUT, "overlay.json"), "w"), indent=1)
print(f"{P} : {len(rows)} masques atlas exportes dans {OUT}")
print("volumes:", [(r["week"], r["vol"]) for r in rows])
