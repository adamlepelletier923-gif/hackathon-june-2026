import os
import numpy as np
import nibabel as nib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "models", "brats_mri_segmentation", "models", "model.ts")

_model = None
_device = None
_tf = None

def _lazy():
    # le modele et torch ne sont charges qu'au premier appel : l'app reste legere au demarrage
    global _model, _device, _tf
    if _model is not None:
        return
    import torch
    from monai.inferers import sliding_window_inference  # noqa: F401
    from monai.transforms import (Compose, LoadImaged, EnsureChannelFirstd,
                                  Orientationd, Spacingd, NormalizeIntensityd)
    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _tf = Compose([
        LoadImaged(keys=["image"]),
        EnsureChannelFirstd(keys=["image"]),
        Orientationd(keys=["image"], axcodes="RAS"),
        Spacingd(keys=["image"], pixdim=(1, 1, 1), mode="bilinear"),
        NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
    ])
    _model = torch.jit.load(MODEL, map_location=_device).eval()

def _bbox(mask, pad=4):
    idx = np.where(mask)
    sl = []
    for d in range(3):
        lo, hi = idx[d].min(), idx[d].max()
        sl.append(slice(max(lo - pad, 0), min(hi + pad + 1, mask.shape[d])))
    return tuple(sl)

def available():
    return os.path.exists(MODEL)

def segment(t1c, t1, t2, flair, out_dir):
    # 4 sequences recalees -> masque rehaussant + volume, ecrit image.nii.gz et seg_custom.nii.gz
    import torch
    from monai.inferers import sliding_window_inference
    _lazy()
    data = _tf({"image": [t1c, t1, t2, flair]})
    img = data["image"].unsqueeze(0).to(_device)
    with torch.no_grad():
        logits = sliding_window_inference(img, (128, 128, 128), 1, _model, overlap=0.25, mode="gaussian")
        prob = torch.sigmoid(logits)[0, 2].cpu().numpy()       # canal 2 = rehaussant
    vol_img = np.asarray(data["image"][0])                     # t1c normalise
    enh = (prob > 0.5).astype(np.uint8)
    bb = _bbox(vol_img > 0)
    vol_img, enh = vol_img[bb], enh[bb]
    v = vol_img[vol_img > 0]
    img8 = np.clip(vol_img / (np.percentile(v, 99) if v.size else 1) * 255, 0, 255).astype(np.uint8)
    aff = np.diag([1.0, 1.0, 1.0, 1.0])
    os.makedirs(out_dir, exist_ok=True)
    nib.save(nib.Nifti1Image(img8, aff), os.path.join(out_dir, "image.nii.gz"))
    nib.save(nib.Nifti1Image(enh, aff), os.path.join(out_dir, "seg_custom.nii.gz"))
    return {"vol": round(float(enh.sum()) / 1000, 1), "n_slices": int(img8.shape[2])}
