import { useEffect, useState } from 'react'
import { getPatients, getTimeline, getReport, getOverlay, timeColor, VERDICT_COLOR, VERDICT_LABEL } from './api'
import type { Timeline, Overlay } from './api'
import VolumeChart from './components/VolumeChart'
import BrainViewer from './components/BrainViewer'

function Kpi({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="flex-1 rounded-xl bg-slate-900/70 border border-slate-800 px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-2xl font-semibold mt-1" style={{ color: color || '#e6e9ef' }}>{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
    </div>
  )
}

function Toggle({ on, left, right, onChange }: { on: boolean; left: string; right: string; onChange: (v: boolean) => void }) {
  return (
    <div className="inline-flex rounded-lg border border-slate-700 overflow-hidden text-xs">
      <button onClick={() => onChange(false)} className={`px-3 py-1 ${!on ? 'bg-sky-500/20 text-sky-300' : 'text-slate-400'}`}>{left}</button>
      <button onClick={() => onChange(true)} className={`px-3 py-1 ${on ? 'bg-sky-500/20 text-sky-300' : 'text-slate-400'}`}>{right}</button>
    </div>
  )
}

export default function App() {
  const [patients, setPatients] = useState<string[]>([])
  const [current, setCurrent] = useState<string | null>(null)
  const [tl, setTl] = useState<Timeline | null>(null)
  const [sel, setSel] = useState(0)
  const [source, setSource] = useState<'custom' | 'dataset'>('custom')
  const [render3d, setRender3d] = useState(false)
  const [report, setReport] = useState('')
  const [overlay, setOverlay] = useState<Overlay | null>(null)
  const [overlayMode, setOverlayMode] = useState(false)

  useEffect(() => {
    getPatients().then((ps) => {
      setPatients(ps.map((p) => p.id))
      if (ps.length) setCurrent(ps[0].id)
    })
  }, [])

  useEffect(() => {
    if (!current) return
    getTimeline(current).then((t) => {
      setTl(t)
      setSel(Math.max(t.exams.length - 1, 0))
    })
    getOverlay(current).then(setOverlay).catch(() => setOverlay(null))
  }, [current])

  const s = tl?.summary
  const exam = tl?.exams[sel]

  const measur = overlay ? overlay.masks.filter((m) => m.vol >= 2) : []
  const layers = measur.map((m, i) => ({
    url: m.url, week: m.week,
    rgb: timeColor(measur.length > 1 ? i / (measur.length - 1) : 0) as [number, number, number],
  }))

  useEffect(() => {
    if (current && exam) getReport(current, exam.week).then((r) => setReport(r.text)).catch(() => setReport(''))
  }, [current, exam?.week])

  return (
    <div className="flex h-screen">
      <aside className="w-60 shrink-0 border-r border-slate-800 bg-slate-950 p-4 flex flex-col gap-4">
        <div>
          <div className="text-lg font-bold tracking-tight">Neuro<span className="text-sky-400">Track</span></div>
          <div className="text-[11px] text-slate-500">suivi tumoral assisté</div>
        </div>
        <div className="flex flex-col gap-1">
          <div className="text-xs uppercase text-slate-500 mb-1">Patients</div>
          {patients.map((p) => (
            <button key={p} onClick={() => setCurrent(p)}
              className={`text-left px-3 py-2 rounded-lg text-sm transition ${
                p === current ? 'bg-sky-500/15 text-sky-300 border border-sky-500/30' : 'hover:bg-slate-900 text-slate-300 border border-transparent'}`}>
              {p}
            </button>
          ))}
          {!patients.length && <div className="text-xs text-slate-600">chargement…</div>}
        </div>
      </aside>

      <main className="flex-1 flex flex-col gap-3 p-5 overflow-hidden">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">{current ?? '—'}</h1>
            <div className="text-sm text-slate-500">{s ? `${s.n_exams} examens de suivi` : ''}</div>
          </div>
          {s && (
            <div className="px-4 py-2 rounded-xl font-bold text-sm tracking-wide"
              style={{ background: (VERDICT_COLOR[s.current_verdict] || '#444') + '22', color: VERDICT_COLOR[s.current_verdict] || '#fff', border: `1px solid ${VERDICT_COLOR[s.current_verdict] || '#444'}55` }}>
              {VERDICT_LABEL[s.current_verdict] || s.current_verdict}
            </div>
          )}
        </header>

        {s && (
          <div className="flex gap-3">
            <Kpi label="volume actuel" value={`${s.current_vol} mL`} sub="tumeur rehaussante" />
            <Kpi label="variation" value={s.current_delta_pct == null ? '—' : `${s.current_delta_pct > 0 ? '+' : ''}${s.current_delta_pct}%`} sub="vs examen précédent"
              color={s.current_delta_pct != null && s.current_delta_pct > 0 ? '#ef4444' : '#22c55e'} />
            <Kpi label="vitesse" value={s.current_velocity == null ? '—' : `${s.current_velocity} mL/mois`} sub="croissance récente" />
            <Kpi label="pic" value={`${s.peak_vol} mL`} sub={s.peak_week} />
          </div>
        )}

        {tl && tl.exams.length > 0 && (
          <div className="flex items-center gap-3 rounded-xl bg-slate-900/40 border border-slate-800 px-3 py-2">
            <button onClick={() => setSel(Math.max(0, sel - 1))} disabled={sel === 0}
              className="px-2 py-1 rounded-md bg-slate-800 text-slate-200 disabled:opacity-30 text-sm">◀</button>
            <input type="range" min={0} max={tl.exams.length - 1} value={sel}
              onChange={(e) => setSel(Number(e.target.value))} className="flex-1 accent-sky-400" />
            <button onClick={() => setSel(Math.min(tl.exams.length - 1, sel + 1))} disabled={sel === tl.exams.length - 1}
              className="px-2 py-1 rounded-md bg-slate-800 text-slate-200 disabled:opacity-30 text-sm">▶</button>
            <div className="text-xs text-slate-400 w-32 text-right">{exam?.week} ({sel + 1}/{tl.exams.length})</div>
          </div>
        )}

        <div className="flex gap-3 flex-1 min-h-0">
          <div className="rounded-xl bg-slate-900/40 border border-slate-800 p-3 flex flex-col flex-[3] min-w-0">
            <div className="text-sm text-slate-400 mb-1 px-1">Trajectoire du volume tumoral rehaussant</div>
            {tl && <div className="flex-1 min-h-0"><VolumeChart exams={tl.exams} selected={sel} onSelect={setSel} /></div>}
          </div>

          <div className="rounded-xl bg-slate-900/40 border border-slate-800 p-3 flex flex-col flex-[2] min-w-0">
            <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
              <div className="text-sm text-slate-400">
                {overlayMode ? 'Cerveau — superposition (évolution)' : exam ? `Cerveau — ${exam.week}` : 'Cerveau'}
              </div>
              <div className="flex gap-2">
                <Toggle on={overlayMode} left="examen" right="superposition" onChange={setOverlayMode} />
                {!overlayMode && <Toggle on={source === 'dataset'} left="notre modèle" right="dataset" onChange={(v) => setSource(v ? 'dataset' : 'custom')} />}
                <Toggle on={render3d} left="2D" right="3D" onChange={setRender3d} />
              </div>
            </div>
            <div className="flex-1 min-h-0 rounded-lg overflow-hidden bg-black/40">
              {current && exam && (
                <BrainViewer patient={current} week={exam.week} source={source} render3d={render3d}
                  overlay={overlayMode && overlay ? { ref: overlay.ref, layers } : null} />
              )}
            </div>
            {overlayMode && layers.length > 0 && (
              <div className="mt-2 flex items-center gap-2 flex-wrap text-[10px] text-slate-400">
                <span className="text-slate-500">ancien</span>
                {layers.map((l) => (
                  <span key={l.week} className="px-1.5 py-0.5 rounded"
                    style={{ background: `rgb(${l.rgb[0]},${l.rgb[1]},${l.rgb[2]})`, color: '#000' }}>{l.week.replace('week-', 'w')}</span>
                ))}
                <span className="text-slate-500">récent</span>
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-3">
          {exam && (
            <div className="rounded-xl bg-slate-900/40 border border-slate-800 px-4 py-3 text-sm flex gap-5 items-center flex-1">
              <div><span className="text-slate-500">examen </span><b>{exam.week}</b></div>
              <div><span className="text-slate-500">volume </span><b>{exam.vol_custom} mL</b></div>
              <div><span className="text-slate-500">auto </span><b style={{ color: VERDICT_COLOR[exam.verdict_auto] }}>{exam.verdict_auto}</b></div>
              {exam.rano_expert && <div><span className="text-slate-500">expert </span><b>{exam.rano_expert}</b></div>}
              <div className="text-slate-600">{exam.n_slices} coupes</div>
            </div>
          )}
          {report && (
            <div className="rounded-xl bg-slate-900/40 border border-slate-800 px-4 py-3 text-xs text-slate-300 whitespace-pre-line flex-[2]">
              <div className="text-slate-500 uppercase text-[10px] mb-1">compte-rendu auto-généré</div>
              {report}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
