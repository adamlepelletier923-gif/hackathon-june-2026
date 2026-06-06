export type Exam = {
  week: string
  wn: number
  vol_custom: number
  vol_dataset: number
  n_slices: number | null
  rano_expert: string
  verdict_auto: string
  verdict_why: string
  new_lesion: boolean
  new_vol: number | null
  ref_baseline: number
  ref_nadir: number | null
  is_baseline: boolean
  is_nadir: boolean
  delta_pct: number | null
  velocity: number | null
  has_nii: boolean
}

export type Summary = {
  current_vol: number
  current_verdict: string
  current_delta_pct: number | null
  current_velocity: number | null
  peak_vol: number
  peak_week: string
  n_exams: number
  rano_expert: string
}

export type Timeline = { patient: string; summary: Summary | null; exams: Exam[] }

export const VERDICT_COLOR: Record<string, string> = {
  PD: '#ef4444', SD: '#f59e0b', PR: '#22c55e', CR: '#3b82f6',
}
export const VERDICT_LABEL: Record<string, string> = {
  PD: 'PROGRESSION', SD: 'STABLE', PR: 'RÉPONSE PARTIELLE', CR: 'RÉPONSE COMPLÈTE',
}

export async function getPatients(): Promise<{ id: string }[]> {
  const r = await fetch('/api/patients')
  return r.json()
}

export async function getTimeline(id: string): Promise<Timeline> {
  const r = await fetch(`/api/patients/${id}/timeline`)
  return r.json()
}

export type OverlayMask = { week: string; wn: number; vol: number; url: string }
export type Overlay = { patient: string; ref: string; masks: OverlayMask[] }

export async function getOverlay(id: string): Promise<Overlay> {
  const r = await fetch(`/api/patients/${id}/overlay`)
  if (!r.ok) throw new Error('no overlay')
  return r.json()
}

// gradient temps -> couleur (bleu = ancien, rouge = recent)
export function timeColor(t: number): [number, number, number] {
  const h = (1 - t) * 220 // 220=bleu -> 0=rouge
  const s = 0.85, l = 0.55
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = l - c / 2
  let r = 0, g = 0, b = 0
  if (h < 60) { r = c; g = x } else if (h < 120) { r = x; g = c }
  else if (h < 180) { g = c; b = x } else if (h < 240) { g = x; b = c }
  else if (h < 300) { r = x; b = c } else { r = c; b = x }
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)]
}

export async function getReport(id: string, week: string): Promise<{ text: string }> {
  const r = await fetch(`/api/patients/${id}/report/${week}`)
  return r.json()
}

export type SegResult = { patient: string; week: string; n_exams: number; vol: number; n_slices: number }

export async function segmentExample(patient: string, week: number): Promise<SegResult> {
  const r = await fetch('/api/segment/example', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patient, week }),
  })
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'segmentation impossible')
  return r.json()
}

export type SeriesResult = { patient: string; n_exams: number; weeks: string[] }

export async function segmentExampleSeries(patient?: string): Promise<SeriesResult> {
  const r = await fetch('/api/segment/example_series', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patient ? { patient } : {}),
  })
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'segmentation impossible')
  return r.json()
}

export async function segmentUpload(patient: string, week: number, files: { t1c: File; t1: File; t2: File; flair: File }): Promise<SegResult> {
  const fd = new FormData()
  fd.append('patient', patient); fd.append('week', String(week))
  fd.append('t1c', files.t1c); fd.append('t1', files.t1); fd.append('t2', files.t2); fd.append('flair', files.flair)
  const r = await fetch('/api/segment', { method: 'POST', body: fd })
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'segmentation impossible')
  return r.json()
}
