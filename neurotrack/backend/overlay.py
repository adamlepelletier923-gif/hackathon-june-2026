import os, re, json
import numpy as np
import nibabel as nib

MIN_VOL = 2.0
AFF = np.diag([1.0, 1.0, 1.0, 1.0])

def _wn(w):
    m = re.match(r"week-(\d+)", w)
    return int(m.group(1)) if m else -1

def _load(p):
    return np.asarray(nib.load(p).dataobj)

def _register_mask(fixed_arr, moving_arr, mask_arr):
    # recalage rigide moving -> fixed, applique au masque (plus proche voisin)
    import SimpleITK as sitk
    fixed = sitk.GetImageFromArray(fixed_arr.astype(np.float32))
    moving = sitk.GetImageFromArray(moving_arr.astype(np.float32))
    R = sitk.ImageRegistrationMethod()
    R.SetMetricAsMattesMutualInformation(32)
    R.SetMetricSamplingStrategy(R.RANDOM)
    R.SetMetricSamplingPercentage(0.1, seed=1)
    R.SetOptimizerAsRegularStepGradientDescent(2.0, 1e-4, 120)
    R.SetOptimizerScalesFromPhysicalShift()
    R.SetInitialTransform(sitk.CenteredTransformInitializer(
        fixed, moving, sitk.Euler3DTransform(), sitk.CenteredTransformInitializerFilter.GEOMETRY))
    R.SetInterpolator(sitk.sitkLinear)
    R.SetShrinkFactorsPerLevel([4, 2])
    R.SetSmoothingSigmasPerLevel([2, 1])
    R.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()
    tx = R.Execute(fixed, moving)
    msk = sitk.GetImageFromArray(mask_arr.astype(np.float32))
    out = sitk.Resample(msk, fixed, tx, sitk.sitkNearestNeighbor, 0.0)
    return (sitk.GetArrayFromImage(out) > 0.5).astype(np.uint8)

def build(pid, nii_dir, cmp_dir, min_vol=MIN_VOL):
    # construit la superposition en espace commun A PARTIR DE NOS MASQUES, dans l'app
    man = json.load(open(os.path.join(cmp_dir, pid, "manifest.json")))
    weeks = [w for w in sorted(man, key=_wn) if man[w].get("vol_our", 0) >= min_vol
             and os.path.exists(os.path.join(nii_dir, pid, w, "image.nii.gz"))]
    out = os.path.join(nii_dir, pid, "_overlay_our")
    os.makedirs(out, exist_ok=True)
    if len(weeks) < 1:
        json.dump([], open(os.path.join(out, "overlay.json"), "w"))
        open(os.path.join(out, ".done"), "w").close()
        return 0
    imgs = {w: _load(os.path.join(nii_dir, pid, w, "image.nii.gz")) for w in weeks}
    masks = {w: _load(os.path.join(nii_dir, pid, w, "seg_custom.nii.gz")) for w in weeks}
    ref_w = max(weeks, key=lambda w: int((imgs[w] > 0).sum()))   # cerveau le mieux couvert
    fixed = imgs[ref_w]
    nib.save(nib.Nifti1Image(fixed.astype(np.uint8), AFF), os.path.join(out, "ref.nii.gz"))
    rows = []
    aligned_all = {}
    for w in weeks:
        aligned = masks[w].astype(np.uint8) if w == ref_w else _register_mask(fixed, imgs[w], masks[w])
        aligned_all[w] = aligned
        nib.save(nib.Nifti1Image(aligned, AFF), os.path.join(out, f"enh_{w}.nii.gz"))
        rows.append({"week": w, "wn": _wn(w), "vol": man[w]["vol_our"]})
    json.dump(rows, open(os.path.join(out, "overlay.json"), "w"), indent=1)
    _detect_new_lesions(aligned_all, weeks, out)
    open(os.path.join(out, ".done"), "w").close()
    return len(rows)

def _detect_new_lesions(aligned, weeks, out, min_lesion=0.5, margin=2):
    # apparition d'un foyer rehaussant la ou il n'y en avait pas avant (sur masques recales, in-app)
    from scipy import ndimage
    known = None
    res = {}
    for w in weeks:
        m = aligned[w] > 0
        n_new, new_vol = 0, 0.0
        known_vol = 0.0 if known is None else float(known.sum()) / 1000.0
        if known_vol >= min_lesion and m.any():
            ref = ndimage.binary_dilation(known, iterations=margin)
            lab, n = ndimage.label(m)
            for i in range(1, n + 1):
                comp = lab == i
                v = comp.sum() / 1000.0
                if v < min_lesion:
                    continue
                if np.logical_and(comp, ref).sum() / comp.sum() < 0.1:
                    n_new += 1
                    new_vol += v
        res[w] = {"new_lesion": n_new > 0, "n_new": int(n_new), "new_vol": round(float(new_vol), 1)}
        known = m if known is None else np.logical_or(known, m)
    json.dump(res, open(os.path.join(out, "new_lesions.json"), "w"), indent=1)

def ensure(pid, nii_dir, cmp_dir):
    if os.path.exists(os.path.join(nii_dir, pid, "_overlay_our", ".done")):
        return
    build(pid, nii_dir, cmp_dir)
