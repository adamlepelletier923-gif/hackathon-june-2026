import os, re, json
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
CMP = os.path.join(DATA, "cmp_cache")
NII = os.path.join(DATA, "web_nii")

app = FastAPI(title="NeuroTrack API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
if os.path.isdir(NII):
    app.mount("/nii", StaticFiles(directory=NII), name="nii")

_rano = pd.read_csv(os.path.join(DATA, "LUMIERE-ExpertRating.csv"))
_rano = _rano.rename(columns={_rano.columns[4]: "RANO"})
RANO = {(r.Patient, r.Date): (r.RANO if isinstance(r.RANO, str) else "") for r in _rano.itertuples()}

def wnum(w):
    m = re.match(r"week-(\d+)", w)
    return int(m.group(1)) if m else -1

NONMEAS = 2.0   # mL, en dessous = pas de maladie rehaussante mesurable

def verdict(vol, baseline, nadir):
    # regle RANO volumetrique simplifiee (sur le seul volume rehaussant)
    measurable_before = nadir is not None and nadir >= NONMEAS
    if vol < NONMEAS:
        return "CR" if (measurable_before and vol <= 0.05) else "SD"
    if nadir is None:
        return "SD"
    if nadir < NONMEAS:                                   # apparition d'une maladie mesurable
        return "PD"
    if vol >= 1.4 * nadir and (vol - nadir) >= 2.0:       # hausse >= 40% sur le nadir
        return "PD"
    if baseline and baseline >= NONMEAS and vol <= 0.35 * baseline:  # baisse >= 65% vs baseline
        return "PR"
    return "SD"

def list_patients():
    if not os.path.isdir(CMP):
        return []
    return sorted(d for d in os.listdir(CMP) if os.path.isfile(os.path.join(CMP, d, "manifest.json")))

@app.get("/api/patients")
def patients():
    return [{"id": p} for p in list_patients()]

@app.get("/api/patients/{pid}/timeline")
def timeline(pid: str):
    man_path = os.path.join(CMP, pid, "manifest.json")
    if not os.path.exists(man_path):
        raise HTTPException(404, "patient inconnu")
    man = json.load(open(man_path))
    weeks = sorted(man, key=wnum)
    has_nii = os.path.isdir(os.path.join(NII, pid))

    rows = []
    baseline = man[weeks[0]]["vol_our"] if weeks else 0.0
    nadir = None
    prev = None
    for w in weeks:
        vol = man[w]["vol_our"]          # mesure = notre modele
        vd = verdict(vol, baseline, nadir)
        delta_pct = None if prev is None or prev["vol"] <= 0.05 else round((vol - prev["vol"]) / prev["vol"] * 100, 1)
        if prev is not None:
            dw = max(wnum(w) - prev["wn"], 1)
            velocity = round((vol - prev["vol"]) / dw * 4.345, 2)   # mL / mois
        else:
            velocity = None
        rows.append({
            "week": w, "wn": wnum(w),
            "vol_custom": vol, "vol_dataset": man[w]["vol_gt"],
            "n_slices": man[w].get("n_slices"),
            "rano_expert": RANO.get((pid, w), ""),
            "verdict_auto": vd,
            "delta_pct": delta_pct, "velocity": velocity,
            "has_nii": has_nii,
        })
        nadir = vol if nadir is None else min(nadir, vol)
        prev = {"vol": vol, "wn": wnum(w)}

    last = rows[-1] if rows else None
    summary = None
    if last:
        peak = max(rows, key=lambda r: r["vol_custom"])
        summary = {
            "current_vol": last["vol_custom"],
            "current_verdict": last["verdict_auto"],
            "current_delta_pct": last["delta_pct"],
            "current_velocity": last["velocity"],
            "peak_vol": peak["vol_custom"], "peak_week": peak["week"],
            "n_exams": len(rows),
            "rano_expert": last["rano_expert"],
        }
    return {"patient": pid, "summary": summary, "exams": rows}

@app.get("/api/patients/{pid}/overlay")
def overlay(pid: str):
    p = os.path.join(NII, pid, "_overlay", "overlay.json")
    if not os.path.exists(p):
        raise HTTPException(404, "pas de superposition pour ce patient")
    rows = json.load(open(p))
    return {
        "patient": pid,
        "ref": f"/nii/{pid}/_overlay/ref.nii.gz",
        "masks": [{"week": r["week"], "wn": r["wn"], "vol": r["vol"],
                   "url": f"/nii/{pid}/_overlay/enh_{r['week']}.nii.gz"} for r in rows],
    }

@app.get("/api/patients/{pid}/report/{week}")
def report(pid: str, week: str):
    man = json.load(open(os.path.join(CMP, pid, "manifest.json")))
    if week not in man:
        raise HTTPException(404, "examen inconnu")
    tl = timeline(pid)["exams"]
    cur = next(e for e in tl if e["week"] == week)
    txt = (f"Patient {pid} — IRM de suivi {week}.\n"
           f"Volume tumoral rehaussant mesure (segmentation automatique) : {cur['vol_custom']} mL.\n")
    if cur["delta_pct"] is not None:
        sens = "augmentation" if cur["delta_pct"] > 0 else "diminution"
        txt += f"Variation par rapport a l'examen precedent : {sens} de {abs(cur['delta_pct'])}%.\n"
    label = {"PD": "progression", "SD": "stabilite", "PR": "reponse partielle", "CR": "reponse complete"}
    txt += f"Categorie de suivi (RANO volumetrique simplifie) : {label.get(cur['verdict_auto'], cur['verdict_auto'])}.\n"
    txt += "Conduite suggeree : avis RCP neuro-oncologie." if cur["verdict_auto"] == "PD" else "Conduite suggeree : poursuite de la surveillance."
    return {"patient": pid, "week": week, "text": txt}
