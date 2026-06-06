import os, re, json, uuid, tempfile
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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
    # renvoie (code, raison lisible) ; aucune dependance a une cotation externe
    measurable_before = nadir is not None and nadir >= NONMEAS
    if vol < NONMEAS:
        if measurable_before and vol <= 0.05:
            return "CR", "plus de maladie rehaussante mesurable"
        return "SD", f"volume sous le seuil mesurable ({NONMEAS} mL)"
    if nadir is None:
        return "SD", "examen de reference, pas de comparaison possible"
    if nadir < NONMEAS:
        return "PD", "apparition d'une maladie rehaussante mesurable"
    if vol >= 1.4 * nadir and (vol - nadir) >= 2.0:
        up = round((vol - nadir) / nadir * 100)
        return "PD", f"hausse de {up}% sur le nadir ({nadir} mL)"
    if baseline and baseline >= NONMEAS and vol <= 0.35 * baseline:
        down = round((baseline - vol) / baseline * 100)
        return "PR", f"baisse de {down}% vs baseline ({baseline} mL)"
    return "SD", "variation sous les seuils de reponse ou de progression"

def load_new_lesions(pid):
    p = os.path.join(NII, pid, "_overlay", "new_lesions.json")
    return json.load(open(p)) if os.path.exists(p) else {}

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
    newles = load_new_lesions(pid)

    rows = []
    baseline = man[weeks[0]]["vol_our"] if weeks else 0.0
    nadir = None
    nadir_week = None
    prev = None
    for w in weeks:
        vol = man[w]["vol_our"]          # mesure = notre modele
        vd, why = verdict(vol, baseline, nadir)
        nl = newles.get(w, {})
        if nl.get("new_lesion"):         # nouvelle lesion = progression (critere RANO)
            vd, why = "PD", f"nouvelle lesion rehaussante ({nl.get('new_vol')} mL)"
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
            "verdict_auto": vd, "verdict_why": why,
            "new_lesion": bool(nl.get("new_lesion")), "new_vol": nl.get("new_vol"),
            "ref_baseline": baseline, "ref_nadir": nadir,
            "is_baseline": w == weeks[0],
            "delta_pct": delta_pct, "velocity": velocity,
            "has_nii": has_nii,
        })
        if nadir is None or vol < nadir:
            nadir, nadir_week = vol, w
        prev = {"vol": vol, "wn": wnum(w)}

    for r in rows:
        r["is_nadir"] = r["week"] == nadir_week

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

SEQ = ["CT1_r2s_bet_reg.nii.gz", "T1_r2s_bet_reg.nii.gz", "T2_r2s_bet_reg.nii.gz", "FLAIR_r2s_bet_reg.nii.gz"]

def _safe_id(s):
    s = re.sub(r"[^A-Za-z0-9_-]", "", (s or "").strip().replace(" ", "-"))
    return s

def _src_paths(src, wk):
    cache = os.path.join(DATA, "nii_cache")
    return [os.path.join(cache, f"Imaging/{src}/{wk}/HD-GLIO-AUTO-segmentation/registered/{n}".replace("/", "__")) for n in SEQ]

def _persist_seg(pid, week_key, paths):
    # segmente et ecrit les fichiers (nii + manifest) pour que l'examen devienne un vrai patient
    from backend import seg
    if not seg.available():
        raise HTTPException(503, "modele de segmentation indisponible")
    pid = _safe_id(pid)
    if not pid:
        raise HTTPException(400, "nom de patient invalide")
    wd = os.path.join(NII, pid, week_key)
    res = seg.segment(*paths, out_dir=wd)
    md = os.path.join(CMP, pid)
    os.makedirs(md, exist_ok=True)
    mpath = os.path.join(md, "manifest.json")
    man = json.load(open(mpath)) if os.path.exists(mpath) else {}
    man[week_key] = {"week": week_key, "n_slices": res["n_slices"], "vol_our": res["vol"], "vol_gt": 0.0}
    json.dump(man, open(mpath, "w"), indent=1)
    return {"patient": pid, "week": week_key, "n_exams": len(man), **res}

def _week_key(week):
    try:
        return f"week-{int(week):03d}"
    except (TypeError, ValueError):
        raise HTTPException(400, "semaine invalide")

@app.post("/api/segment")
async def segment_upload(patient: str = Form(...), week: int = Form(...),
                         t1c: UploadFile = File(...), t1: UploadFile = File(...),
                         t2: UploadFile = File(...), flair: UploadFile = File(...)):
    tmp = tempfile.mkdtemp()
    paths = []
    for f in (t1c, t1, t2, flair):
        p = os.path.join(tmp, f.filename or f"{uuid.uuid4().hex}.nii.gz")
        with open(p, "wb") as out:
            out.write(await f.read())
        paths.append(p)
    return _persist_seg(patient, _week_key(week), paths)

@app.post("/api/segment/example")
def segment_example(payload: dict):
    # demo : segmente en direct un examen deja telecharge (sequences brutes du cache LUMIERE)
    src_p, src_w = payload.get("src_patient", "Patient-029"), payload.get("src_week", "week-255")
    paths = _src_paths(src_p, src_w)
    if not all(os.path.exists(p) for p in paths):
        raise HTTPException(404, "sequences non disponibles en cache pour cet examen")
    return _persist_seg(payload.get("patient"), _week_key(payload.get("week")), paths)

@app.post("/api/segment/example_series")
def segment_example_series(payload: dict):
    # demo : segmente en direct TOUTE une trajectoire (plusieurs examens d'un patient LUMIERE)
    import glob
    src = payload.get("src_patient", "Patient-029")
    pid = payload.get("patient") or "Exemple-029"
    limit = int(payload.get("limit", 8))
    cache = os.path.join(DATA, "nii_cache")
    found = glob.glob(os.path.join(cache, f"Imaging__{src}__*__HD-GLIO-AUTO-segmentation__registered__CT1_r2s_bet_reg.nii.gz"))
    weeks = []
    for f in found:
        wk = os.path.basename(f).split("__")[2]
        paths = _src_paths(src, wk)
        if all(os.path.exists(p) for p in paths):
            weeks.append((wk, paths))
    if not weeks:
        raise HTTPException(404, "aucun examen en cache pour ce patient source")
    weeks.sort(key=lambda t: wnum(t[0]))
    if limit and len(weeks) > limit:
        idx = sorted({round(j * (len(weeks) - 1) / (limit - 1)) for j in range(limit)})
        weeks = [weeks[i] for i in idx]
    out = None
    for wk, paths in weeks:
        out = _persist_seg(pid, wk, paths)
    return {"patient": _safe_id(pid), "n_exams": out["n_exams"], "weeks": [w for w, _ in weeks]}

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
    txt += f"Categorie de suivi (RANO volumetrique simplifie) : {label.get(cur['verdict_auto'], cur['verdict_auto'])}"
    txt += f" ({cur['verdict_why']}).\n" if cur.get("verdict_why") else ".\n"
    txt += "Conduite suggeree : avis RCP neuro-oncologie." if cur["verdict_auto"] == "PD" else "Conduite suggeree : poursuite de la surveillance."
    return {"patient": pid, "week": week, "text": txt}
