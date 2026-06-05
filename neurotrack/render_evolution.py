import os, re, json
import numpy as np
import pandas as pd
import nibabel as nib
import matplotlib.pyplot as plt
from remotezip import RemoteZip

ZIP_URL = "https://ndownloader.figshare.com/files/38249697"
DATA = "data"
NII_DIR = os.path.join(DATA, "evolution_P067_nii")   # volumes pour NiiVue
os.makedirs(NII_DIR, exist_ok=True)
PATIENT = "Patient-067"

names = json.load(open(os.path.join(DATA, "namelist.json")))
weeks = sorted({n.split("/")[2] for n in names
                if n.startswith(f"Imaging/{PATIENT}/")
                and n.endswith("registered/segmentation.nii.gz")},
               key=lambda w: int(re.match(r"week-(\d+)", w).group(1)))
print(PATIENT, "->", len(weeks), "examens")

rano = pd.read_csv(os.path.join(DATA, "LUMIERE-ExpertRating.csv"))
rano = rano.rename(columns={rano.columns[4]: "RANO"})
rmap = {(r.Patient, r.Date): r.RANO for r in rano.itertuples()}

def fetch(z, path):
    local = os.path.join(NII_DIR, path.replace("/", "__"))
    if not os.path.exists(local):
        with z.open(path) as src, open(local, "wb") as dst:
            dst.write(src.read())
    return local

def bbox2d(mask2d, pad, shape):
    ys, xs = np.where(mask2d > 0)
    if len(ys) == 0:
        return slice(0, shape[0]), slice(0, shape[1])
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, shape[1])
    return slice(y0, y1), slice(x0, x1)

rows = []
with RemoteZip(ZIP_URL) as z:
    for w in weeks:
        base = f"Imaging/{PATIENT}/{w}/HD-GLIO-AUTO-segmentation/registered"
        seg = nib.load(fetch(z, f"{base}/segmentation.nii.gz"))
        img = nib.load(fetch(z, f"{base}/CT1_r2s_bet_reg.nii.gz"))
        m = np.asarray(seg.dataobj)
        a = np.asarray(img.dataobj).astype(float)
        vox = float(np.prod(seg.header.get_zooms()[:3]))
        enh = (m == 2).sum() * vox / 1000.0   # HD-GLIO: 2=rehaussant, 1=oedeme
        # on coupe le long de l'axe le plus fin = plan d'acquisition, grande vue garantie
        ax = int(np.argmin(m.shape))
        other = tuple(i for i in range(3) if i != ax)
        area = (m == 2).sum(axis=other)
        brain = (a > 0).sum(axis=other)
        k = int(area.argmax()) if area.max() > 0 else int(brain.argmax())
        img2d = np.take(a, k, axis=ax)
        msk2d = np.take(m, k, axis=ax)
        ys, xs = bbox2d((img2d > 0).astype(int), 6, img2d.shape)
        rows.append(dict(week=w, wn=int(re.match(r"week-(\d+)", w).group(1)),
                         enh=enh, rano=rmap.get((PATIENT, w), ""),
                         img=img2d[ys, xs], msk=msk2d[ys, xs]))

n = len(rows)
cols = 5
nrow = (n + cols - 1) // cols
fig, axes = plt.subplots(nrow, cols, figsize=(cols * 2.6, nrow * 2.6))
axes = np.array(axes).reshape(-1)
for ax in axes:
    ax.axis("off")
for i, r in enumerate(rows):
    ax = axes[i]
    base = np.rot90(r["img"])
    mask = np.rot90(r["msk"])
    ax.imshow(base, cmap="gray", vmax=np.percentile(base[base > 0], 99) if (base > 0).any() else None)
    enh_overlay = np.ma.masked_where(mask != 2, mask)
    ax.imshow(enh_overlay, cmap="autumn", alpha=0.55, vmin=1, vmax=1)
    tag = f" {r['rano']}" if r["rano"] else ""
    ax.set_title(f"{r['week']} | {r['enh']:.1f} mL{tag}", fontsize=8)

fig.suptitle(f"{PATIENT} — evolution de la tumeur rehaussante sur {n} IRM "
             f"(masque rouge sur IRM injectee)", fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.97])
out = os.path.join(DATA, "evolution_P067.png")
fig.savefig(out, dpi=110)
print("planche:", out)
print("volumes nii.gz pour NiiVue dans:", NII_DIR)
