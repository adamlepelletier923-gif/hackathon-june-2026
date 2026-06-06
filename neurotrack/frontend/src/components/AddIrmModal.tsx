import { useState } from 'react'
import { segmentExampleSeries, segmentUpload } from '../api'
import type { SegResult } from '../api'

const SEQS = ['t1c', 't1', 't2', 'flair'] as const
type Seq = typeof SEQS[number]

export default function AddIrmModal({ onClose, onCreated }: { onClose: () => void; onCreated: (pid: string) => void }) {
  const [name, setName] = useState('')
  const [week, setWeek] = useState('')
  const [files, setFiles] = useState<Partial<Record<Seq, File>>>({})
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [res, setRes] = useState<SegResult | null>(null)

  const filesReady = SEQS.every((s) => files[s])
  const metaReady = name.trim() !== '' && week.trim() !== ''

  const run = async (fn: () => Promise<SegResult>) => {
    setBusy(true); setErr(''); setRes(null)
    try { setRes(await fn()) }
    catch (e: any) { setErr(e.message || 'erreur') }
    finally { setBusy(false) }
  }

  const runSeries = async () => {
    setBusy(true); setErr(''); setRes(null)
    const pid = name.trim() || `Demo-${Math.random().toString(36).slice(2, 6)}`
    try { const s = await segmentExampleSeries(pid); onCreated(s.patient) }
    catch (e: any) { setErr(e.message || 'erreur') }
    finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 flex flex-col gap-4"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Ajouter une IRM</h2>
            <div className="text-xs text-slate-500">segmentation par le modèle, en direct — l’examen devient un patient suivi</div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200 text-xl leading-none">×</button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1 text-xs">
            <span className="uppercase tracking-wide text-slate-400">patient</span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="ex. Dupont-J"
              className="bg-slate-950/60 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200 outline-none focus:border-sky-500/50" />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="uppercase tracking-wide text-slate-400">semaine de suivi</span>
            <input value={week} onChange={(e) => setWeek(e.target.value.replace(/[^0-9]/g, ''))} placeholder="ex. 0, 12, 24…" inputMode="numeric"
              className="bg-slate-950/60 border border-slate-700 rounded px-2 py-1.5 text-sm text-slate-200 outline-none focus:border-sky-500/50" />
          </label>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {SEQS.map((s) => (
            <label key={s} className="flex flex-col gap-1 text-xs">
              <span className="uppercase tracking-wide text-slate-400">{s} <span className="text-slate-600">(.nii.gz)</span></span>
              <input type="file" accept=".nii,.nii.gz,.gz"
                onChange={(e) => setFiles((f) => ({ ...f, [s]: e.target.files?.[0] }))}
                className="text-xs text-slate-300 file:mr-2 file:px-2 file:py-1 file:rounded file:border-0 file:bg-slate-800 file:text-slate-200" />
            </label>
          ))}
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <button disabled={!filesReady || !metaReady || busy} onClick={() => run(() => segmentUpload(name, Number(week), files as any))}
            className="px-4 py-2 rounded-lg bg-sky-500/20 text-sky-200 border border-sky-500/30 text-sm font-medium disabled:opacity-30">
            Segmenter et ajouter
          </button>
          <span className="text-xs text-slate-600">ou</span>
          <button disabled={busy} onClick={runSeries}
            className="px-3 py-2 rounded-lg bg-slate-800 text-slate-300 border border-slate-700 text-sm disabled:opacity-30">
            segmenter un exemple (suivi complet)
          </button>
          {busy && <span className="text-xs text-sky-300 animate-pulse">segmentation en cours… (le suivi complet prend ~30s)</span>}
          {err && <span className="text-xs text-red-400">{err}</span>}
        </div>
        <div className="text-[11px] text-slate-600">pour un upload : renseigne un nom et une semaine, puis les 4 séquences. L’exemple (suivi complet) réutilise des IRM existantes pour la démo et crée un patient distinct (nom auto si vide) — supprimable ensuite.</div>

        {res && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 flex items-center justify-between gap-3">
            <div className="text-sm text-emerald-200">
              ✓ <b>{res.patient}</b> — examen {res.week} ajouté · volume rehaussant <b>{res.vol} mL</b>
              <span className="text-emerald-300/70"> · {res.n_exams} examen{res.n_exams > 1 ? 's' : ''} au total</span>
            </div>
            <button onClick={() => onCreated(res.patient)}
              className="px-3 py-1.5 rounded-lg bg-sky-500/20 text-sky-200 border border-sky-500/30 text-sm whitespace-nowrap">voir le patient</button>
          </div>
        )}
      </div>
    </div>
  )
}
