import os, re, json, argparse
import numpy as np
import nibabel as nib
import torch
from monai.inferers import sliding_window_inference
from monai.transforms import (Compose, LoadImaged, EnsureChannelFirstd,
                              Orientationd, Spacingd, NormalizeIntensityd)
from remotezip import RemoteZip

ap = argparse.ArgumentParser(description="Segmentation par modele pre-entraine (MONAI BraTS) + comparaison a LUMIERE")
ap.add_argument("--patient", default="Patient-067")
ap.add_argument("--week", default=None, help="ex: week-156 ; par defaut l'examen au plus gros volume tumoral")
args = ap.parse_args()

DATA = "data"
CACHE = os.path.join(DATA, "nii_cache")
os.makedirs(CACHE, exist_ok=True)
MODEL = "models/brats_mri_segmentation/models/model.ts"
P = args.patient
device = "cuda" if torch.cuda.is_available() else "cpu"

names = json.load(open(os.path.join(DATA, "namelist.json")))
weeks = sorted({n.split("/")[2] for n in names
                if n.startswith(f"Imaging/{P}/")
                and n.endswith("registered/segmentation.nii.gz")},
               key=lambda w: int(re.match(r"week-(\d+)", w).group(1)))

def fetch(z, path):
    local = os.path.join(CACHE, path.replace("/", "__"))
    if not os.path.exists(local):
        with z.open(path) as src, open(local, "wb") as dst:
            dst.write(src.read())
    return local

def gt_enh_volume(path):
    seg = nib.load(path)
    m = np.asarray(seg.dataobj)
    vox = float(np.prod(seg.header.get_zooms()[:3]))
    return (m == 2).sum() * vox / 1000.0

# choisir l'examen (par defaut le plus gros volume rehaussant)
with RemoteZip("https://ndownloader.figshare.com/files/38249697") as z:
    if args.week:
        week = args.week
    else:
        best, week = -1, weeks[0]
        for w in weeks:
            p = fetch(z, f"Imaging/{P}/{w}/HD-GLIO-AUTO-segmentation/registered/segmentation.nii.gz")
            v = gt_enh_volume(p)
            if v > best:
                best, week = v, w
    base = f"Imaging/{P}/{week}/HD-GLIO-AUTO-segmentation/registered"
    files = {
        "t1c":   fetch(z, f"{base}/CT1_r2s_bet_reg.nii.gz"),
        "t1":    fetch(z, f"{base}/T1_r2s_bet_reg.nii.gz"),
        "t2":    fetch(z, f"{base}/T2_r2s_bet_reg.nii.gz"),
        "flair": fetch(z, f"{base}/FLAIR_r2s_bet_reg.nii.gz"),
        "gt":    fetch(z, f"{base}/segmentation.nii.gz"),
    }
print(f"{P} / {week}  (device={device})")

# preprocessing identique cote image (4 canaux: T1c,T1,T2,FLAIR) et label
tf = Compose([
    LoadImaged(keys=["image", "label"]),
    EnsureChannelFirstd(keys=["image", "label"]),
    Orientationd(keys=["image", "label"], axcodes="RAS"),
    Spacingd(keys=["image", "label"], pixdim=(1, 1, 1), mode=("bilinear", "nearest")),
    NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
])
data = tf({"image": [files["t1c"], files["t1"], files["t2"], files["flair"]],
           "label": files["gt"]})
img = data["image"].unsqueeze(0).to(device)          # [1,4,H,W,D]
gt = np.asarray(data["label"][0])                    # labels LUMIERE sur la meme grille 1mm

# inference du modele pre-entraine
model = torch.jit.load(MODEL, map_location=device).eval()
with torch.no_grad():
    logits = sliding_window_inference(img, roi_size=(128, 128, 128), sw_batch_size=1,
                                      predictor=model, overlap=0.5, mode="gaussian")
    prob = torch.sigmoid(logits)[0].cpu().numpy()    # [3,H,W,D] : TC, WT, ET
our_et = prob[2] > 0.5                                # notre tumeur rehaussante
gt_et = gt == 2                                      # rehaussant cote LUMIERE (HD-GLIO: 2=rehaussant, 1=oedeme)

vox_ml = 1.0 / 1000.0                                 # 1mm iso -> 1 mm3 -> mL
inter = np.logical_and(our_et, gt_et).sum()
dice = 2 * inter / (our_et.sum() + gt_et.sum() + 1e-8)
print(f"volume rehaussant  LUMIERE: {gt_et.sum()*vox_ml:6.1f} mL")
print(f"volume rehaussant  notre modele: {our_et.sum()*vox_ml:6.1f} mL")
print(f"Dice (notre masque vs LUMIERE): {dice:.3f}")

# figure de comparaison
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
ax_thin = int(np.argmin(gt_et.shape))
other = tuple(i for i in range(3) if i != ax_thin)
area = gt_et.sum(axis=other) + our_et.sum(axis=other)
k = int(area.argmax())
t1c = np.asarray(data["image"][0])
def sl(a): return np.rot90(np.take(a, k, axis=ax_thin))
fig, axes = plt.subplots(1, 2, figsize=(10, 5.5))
for a in axes:
    a.axis("off"); a.imshow(sl(t1c), cmap="gray")
axes[0].imshow(np.ma.masked_where(~sl(gt_et), sl(gt_et)), cmap="autumn", alpha=0.55)
axes[0].set_title(f"reference LUMIERE\n{gt_et.sum()*vox_ml:.1f} mL", fontsize=11)
axes[1].imshow(np.ma.masked_where(~sl(our_et), sl(our_et)), cmap="winter", alpha=0.55)
axes[1].set_title(f"notre modele pre-entraine (MONAI)\n{our_et.sum()*vox_ml:.1f} mL  |  Dice {dice:.2f}", fontsize=11)
fig.suptitle(f"{P} / {week} — tumeur rehaussante : modele pulle vs reference", fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.95])
out = os.path.join(DATA, f"seg_compare_{P}_{week}.png")
fig.savefig(out, dpi=110)
print("figure:", out)
