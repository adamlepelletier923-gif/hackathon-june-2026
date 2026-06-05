import os, re, json, argparse
import numpy as np
import pandas as pd
import nibabel as nib

ap = argparse.ArgumentParser(description="Viewer IRM + segmentation, suivi longitudinal LUMIERE")
ap.add_argument("--patient", default="Patient-067")
ap.add_argument("--save", metavar="PNG", help="rend l'examen 0 dans un PNG (mode headless, pour tester)")
args = ap.parse_args()

import matplotlib
if args.save:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from remotezip import RemoteZip

ZIP_URL = "https://ndownloader.figshare.com/files/38249697"
DATA = "data"
CACHE = os.path.join(DATA, "nii_cache")
os.makedirs(CACHE, exist_ok=True)
P = args.patient

names = json.load(open(os.path.join(DATA, "namelist.json")))
weeks = sorted({n.split("/")[2] for n in names
                if n.startswith(f"Imaging/{P}/")
                and n.endswith("registered/segmentation.nii.gz")},
               key=lambda w: int(re.match(r"week-(\d+)", w).group(1)))
if not weeks:
    raise SystemExit(f"aucun examen trouve pour {P}")

rano = pd.read_csv(os.path.join(DATA, "LUMIERE-ExpertRating.csv"))
rano = rano.rename(columns={rano.columns[4]: "RANO"})
rmap = {(r.Patient, r.Date): r.RANO for r in rano.itertuples()}

def fetch(z, path):
    local = os.path.join(CACHE, path.replace("/", "__"))
    if not os.path.exists(local):
        with z.open(path) as src, open(local, "wb") as dst:
            dst.write(src.read())
    return local

print(f"{P} : {len(weeks)} examens, chargement...")
exams = []
with RemoteZip(ZIP_URL) as z:
    for w in weeks:
        base = f"Imaging/{P}/{w}/HD-GLIO-AUTO-segmentation/registered"
        m = np.asarray(nib.load(fetch(z, f"{base}/segmentation.nii.gz")).dataobj)
        seg = nib.load(fetch(z, f"{base}/segmentation.nii.gz"))
        a = np.asarray(nib.load(fetch(z, f"{base}/CT1_r2s_bet_reg.nii.gz")).dataobj).astype(float)
        vox = float(np.prod(seg.header.get_zooms()[:3]))
        ax = int(np.argmin(m.shape))                       # plan d'acquisition
        other = tuple(i for i in range(3) if i != ax)
        area = (m == 2).sum(axis=other)   # HD-GLIO: 2=rehaussant, 1=oedeme
        k0 = int(area.argmax()) if area.max() > 0 else m.shape[ax] // 2
        exams.append(dict(week=w, img=a, msk=m, ax=ax, k0=k0,
                          vmax=np.percentile(a[a > 0], 99) if (a > 0).any() else 1,
                          enh=(m == 2).sum() * vox / 1000.0,
                          rano=rmap.get((P, w), "")))

def frame(e, k):
    img = np.rot90(np.take(e["img"], k, axis=e["ax"]))
    msk = np.rot90(np.take(e["msk"], k, axis=e["ax"]))
    return img, msk

fig, ax = plt.subplots(figsize=(7.5, 8))
plt.subplots_adjust(bottom=0.17)
state = {"e": 0}

def draw():
    e = exams[state["e"]]
    k = int(round(s_slice.val * (e["img"].shape[e["ax"]] - 1)))
    img, msk = frame(e, k)
    ax.clear(); ax.axis("off")
    ax.imshow(img, cmap="gray", vmax=e["vmax"])
    ax.imshow(np.ma.masked_where(msk != 2, msk), cmap="autumn", alpha=0.55, vmin=2, vmax=2)
    ax.imshow(np.ma.masked_where(msk != 1, msk), cmap="cool", alpha=0.30, vmin=1, vmax=1)
    tag = f"  RANO: {e['rano']}" if e["rano"] else ""
    ax.set_title(f"{P}  |  {e['week']}  ({state['e']+1}/{len(exams)})\n"
                 f"tumeur rehaussante : {e['enh']:.1f} mL{tag}  |  coupe {k}", fontsize=10)
    fig.canvas.draw_idle()

ax_exam = plt.axes([0.15, 0.08, 0.7, 0.03])
ax_slice = plt.axes([0.15, 0.03, 0.7, 0.03])
s_exam = Slider(ax_exam, "examen", 0, len(exams) - 1, valinit=0, valstep=1)
s_slice = Slider(ax_slice, "coupe", 0.0, 1.0, valinit=exams[0]["k0"] / max(exams[0]["img"].shape[exams[0]["ax"]] - 1, 1))

def on_exam(v):
    state["e"] = int(v)
    e = exams[state["e"]]
    s_slice.eventson = False
    s_slice.set_val(e["k0"] / max(e["img"].shape[e["ax"]] - 1, 1))
    s_slice.eventson = True
    draw()

def on_slice(v):
    draw()

s_exam.on_changed(on_exam)
s_slice.on_changed(on_slice)

def on_key(event):
    if event.key in ("right", "left"):
        state["e"] = (state["e"] + (1 if event.key == "right" else -1)) % len(exams)
        s_exam.set_val(state["e"])
fig.canvas.mpl_connect("key_press_event", on_key)

draw()
if args.save:
    fig.savefig(args.save, dpi=110)
    print("rendu:", args.save)
else:
    print("fleches gauche/droite = changer d'examen | sliders = examen / coupe")
    plt.show()
