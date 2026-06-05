import os, re, json, argparse, time
import numpy as np
import nibabel as nib
import torch
from monai.inferers import sliding_window_inference
from monai.transforms import (Compose, LoadImaged, EnsureChannelFirstd,
                              Orientationd, Spacingd, NormalizeIntensityd)
from remotezip import RemoteZip

ap = argparse.ArgumentParser(description="Precalcule, par examen, IRM + seg dataset + seg custom (1mm RAS) et met en cache")
ap.add_argument("--patient", default="Patient-067")
ap.add_argument("--limit", type=int, default=0, help="ne traiter que les N premiers examens (0 = tous)")
args = ap.parse_args()

DATA = "data"
CACHE = os.path.join(DATA, "nii_cache")
OUT = os.path.join(DATA, "cmp_cache", args.patient)
os.makedirs(CACHE, exist_ok=True); os.makedirs(OUT, exist_ok=True)
MODEL = "models/brats_mri_segmentation/models/model.ts"
P = args.patient
ZIP = "https://ndownloader.figshare.com/files/38249697"
device = "cuda" if torch.cuda.is_available() else "cpu"

names = json.load(open(os.path.join(DATA, "namelist.json")))
weeks = sorted({n.split("/")[2] for n in names
                if n.startswith(f"Imaging/{P}/")
                and n.endswith("registered/segmentation.nii.gz")},
               key=lambda w: int(re.match(r"week-(\d+)", w).group(1)))
if args.limit:
    weeks = weeks[:args.limit]

def fetch(z, path):
    loc = os.path.join(CACHE, path.replace("/", "__"))
    if not os.path.exists(loc):
        with z.open(path) as s, open(loc, "wb") as d:
            d.write(s.read())
    return loc

tf = Compose([
    LoadImaged(keys=["image", "label"]),
    EnsureChannelFirstd(keys=["image", "label"]),
    Orientationd(keys=["image", "label"], axcodes="RAS"),
    Spacingd(keys=["image", "label"], pixdim=(1, 1, 1), mode=("bilinear", "nearest")),
    NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
])
model = torch.jit.load(MODEL, map_location=device).eval()

def bbox(mask, pad=4):
    idx = np.where(mask)
    sl = []
    for d in range(3):
        lo, hi = idx[d].min(), idx[d].max()
        sl.append(slice(max(lo - pad, 0), min(hi + pad + 1, mask.shape[d])))
    return tuple(sl)

manifest = {}
with RemoteZip(ZIP) as z:
    for i, w in enumerate(weeks):
        out = os.path.join(OUT, f"{w}.npz")
        base = f"Imaging/{P}/{w}/HD-GLIO-AUTO-segmentation/registered"
        files = {k: fetch(z, f"{base}/{n}") for k, n in
                 [("t1c", "CT1_r2s_bet_reg.nii.gz"), ("t1", "T1_r2s_bet_reg.nii.gz"),
                  ("t2", "T2_r2s_bet_reg.nii.gz"), ("flair", "FLAIR_r2s_bet_reg.nii.gz"),
                  ("gt", "segmentation.nii.gz")]}
        if os.path.exists(out):
            manifest[w] = json.load(open(out + ".json"))
            print(f"[{i+1}/{len(weeks)}] {w}  (cache)")
            continue
        t0 = time.time()
        data = tf({"image": [files["t1c"], files["t1"], files["t2"], files["flair"]],
                   "label": files["gt"]})
        img = data["image"].unsqueeze(0).to(device)
        gt = np.asarray(data["label"][0])
        with torch.no_grad():
            logits = sliding_window_inference(img, (128, 128, 128), 1, model, overlap=0.25, mode="gaussian")
            prob = torch.sigmoid(logits)[0, 2].cpu().numpy()
        t1c = np.asarray(data["image"][0])
        gt_enh = (gt == 2).astype(np.uint8)          # HD-GLIO: 2 = rehaussant
        our_enh = (prob > 0.5).astype(np.uint8)
        # crop sur le cerveau pour alleger
        bb = bbox(t1c > 0)
        t1c, gt_enh, our_enh = t1c[bb], gt_enh[bb], our_enh[bb]
        v = t1c[t1c > 0]
        t8 = np.clip(t1c / (np.percentile(v, 99) if v.size else 1) * 255, 0, 255).astype(np.uint8)
        np.savez_compressed(out, t1c=t8, gt=gt_enh, our=our_enh)
        meta = {"week": w, "n_slices": int(t8.shape[2]),
                "vol_gt": round(float(gt_enh.sum()) / 1000, 1),
                "vol_our": round(float(our_enh.sum()) / 1000, 1)}
        json.dump(meta, open(out + ".json", "w"))
        manifest[w] = meta
        print(f"[{i+1}/{len(weeks)}] {w}  gt={meta['vol_gt']}mL  custom={meta['vol_our']}mL  ({time.time()-t0:.0f}s)")

json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
print("cache:", OUT)
