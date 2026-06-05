import os, re, json, argparse
import numpy as np
import pandas as pd

ap = argparse.ArgumentParser(description="Viewer comparatif : IRM brute | seg dataset | seg custom, sur les examens d'un patient")
ap.add_argument("--patient", default="Patient-067")
ap.add_argument("--save", metavar="PNG", help="rend l'examen au plus gros volume en PNG (test headless)")
args = ap.parse_args()

import matplotlib
if args.save:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

DATA = "data"
P = args.patient
OUT = os.path.join(DATA, "cmp_cache", P)
if not os.path.exists(os.path.join(OUT, "manifest.json")):
    raise SystemExit(f"pas de cache pour {P}. Lance d'abord : ./.venv/bin/python precompute_seg.py --patient {P}")
manifest = json.load(open(os.path.join(OUT, "manifest.json")))
weeks = sorted(manifest, key=lambda w: int(re.match(r"week-(\d+)", w).group(1)))

rano = pd.read_csv(os.path.join(DATA, "LUMIERE-ExpertRating.csv"))
rano = rano.rename(columns={rano.columns[4]: "RANO"})
rmap = {(r.Patient, r.Date): r.RANO for r in rano.itertuples()}

exams = []
for w in weeks:
    d = np.load(os.path.join(OUT, f"{w}.npz"))
    t1c, gt, our = d["t1c"], d["gt"], d["our"]
    area = gt.sum(axis=(0, 1)) + our.sum(axis=(0, 1))
    k0 = int(area.argmax()) if area.max() > 0 else t1c.shape[2] // 2
    exams.append(dict(week=w, t1c=t1c, gt=gt, our=our, k0=k0,
                      vg=manifest[w]["vol_gt"], vo=manifest[w]["vol_our"],
                      rano=rmap.get((P, w), "")))
print(f"{P} : {len(exams)} examens charges")

fig, axes = plt.subplots(1, 3, figsize=(13, 5.5))
plt.subplots_adjust(bottom=0.18, top=0.86)
state = {"e": 0}

def draw():
    e = exams[state["e"]]
    Z = e["t1c"].shape[2]
    k = int(round(s_slice.val * (Z - 1)))
    base = np.rot90(e["t1c"][:, :, k])
    gt = np.rot90(e["gt"][:, :, k])
    our = np.rot90(e["our"][:, :, k])
    for a in axes:
        a.clear(); a.axis("off"); a.imshow(base, cmap="gray")
    axes[1].imshow(np.ma.masked_where(gt == 0, gt), cmap="autumn", alpha=0.55)
    axes[2].imshow(np.ma.masked_where(our == 0, our), cmap="winter", alpha=0.55)
    axes[0].set_title("avant seg (IRM injectee)", fontsize=11)
    axes[1].set_title(f"seg DATASET (LUMIERE)\n{e['vg']} mL", fontsize=11)
    axes[2].set_title(f"seg CUSTOM (notre modele)\n{e['vo']} mL", fontsize=11)
    tag = f"  |  RANO: {e['rano']}" if e["rano"] else ""
    fig.suptitle(f"{P}  —  {e['week']}  ({state['e']+1}/{len(exams)})  —  coupe {k+1}/{Z}{tag}",
                 fontsize=13)
    fig.canvas.draw_idle()

ax_exam = plt.axes([0.15, 0.08, 0.7, 0.03])
ax_slice = plt.axes([0.15, 0.03, 0.7, 0.03])
s_exam = Slider(ax_exam, "examen", 0, len(exams) - 1, valinit=0, valstep=1)
s_slice = Slider(ax_slice, "coupe", 0.0, 1.0, valinit=exams[0]["k0"] / max(exams[0]["t1c"].shape[2] - 1, 1))

def on_exam(v):
    state["e"] = int(v)
    e = exams[state["e"]]
    s_slice.eventson = False
    s_slice.set_val(e["k0"] / max(e["t1c"].shape[2] - 1, 1))
    s_slice.eventson = True
    draw()

s_exam.on_changed(on_exam)
s_slice.on_changed(lambda v: draw())

def on_key(ev):
    if ev.key in ("right", "left"):
        state["e"] = (state["e"] + (1 if ev.key == "right" else -1)) % len(exams)
        s_exam.set_val(state["e"])
fig.canvas.mpl_connect("key_press_event", on_key)

if args.save:
    state["e"] = max(range(len(exams)), key=lambda i: exams[i]["vg"])
    s_slice.set_val(exams[state["e"]]["k0"] / max(exams[state["e"]]["t1c"].shape[2] - 1, 1))
    draw()
    fig.savefig(args.save, dpi=110)
    print("rendu:", args.save)
else:
    draw()
    print("fleches gauche/droite = examen | sliders = examen / coupe")
    plt.show()
