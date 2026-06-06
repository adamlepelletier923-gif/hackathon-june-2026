import { useEffect, useState } from 'react'
import { getPatients, getTimeline, getReport, getOverlay, deletePatient, timeColor, VERDICT_COLOR, VERDICT_LABEL } from './api'
import type { Timeline, Overlay } from './api'
import VolumeChart from './components/VolumeChart'
import BrainViewer from './components/BrainViewer'
import RanoRibbon from './components/RanoRibbon'
import AddIrmModal from './components/AddIrmModal'

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

function Card({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl bg-slate-900/50 backdrop-blur-sm border border-white/5 ring-1 ring-black/20 shadow-xl shadow-black/30 p-4">
      <div className="flex items-center justify-between mb-3 gap-2 flex-wrap">
        <h2 className="text-sm font-medium text-slate-300">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  )
}

export default function App() {
  const [patients, setPatients] = useState<string[]>([])
  const [current, setCurrent] = useState<string | null>(null)
  const [tl, setTl] = useState<Timeline | null>(null)
  const [sel, setSel] = useState(0)
  const [render3d, setRender3d] = useState(false)
  const [report, setReport] = useState('')
  const [overlay, setOverlay] = useState<Overlay | null>(null)
  const [overlayMode, setOverlayMode] = useState(false)
  const [overlayLoading, setOverlayLoading] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [edited, setEdited] = useState(false)
  const [copied, setCopied] = useState(false)
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [showAdd, setShowAdd] = useState(false)

  useEffect(() => {
    getPatients().then((ps) => {
      setPatients(ps.map((p) => p.id))
      if (ps.length) setCurrent(ps[0].id)
    })
  }, [])

  useEffect(() => {
    if (!current) return
    setPlaying(false)
    setOverlayMode(false)
    setOverlay(null)
    getTimeline(current).then((t) => {
      setTl(t)
      setSel(Math.max(t.exams.length - 1, 0))
    })
  }, [current])

  useEffect(() => {
    if (!overlayMode || !current || overlay) return
    setOverlayLoading(true)
    getOverlay(current).then(setOverlay).catch(() => setOverlay(null)).finally(() => setOverlayLoading(false))
  }, [overlayMode, current, overlay])

  useEffect(() => {
    if (!playing || !tl) return
    if (sel >= tl.exams.length - 1) { setPlaying(false); return }
    const id = setTimeout(() => setSel((i) => i + 1), 1100)
    return () => clearTimeout(id)
  }, [playing, sel, tl])

  const togglePlay = () => {
    if (!tl) return
    if (!playing && sel >= tl.exams.length - 1) setSel(0)
    setPlaying((p) => !p)
  }
  const stepTo = (i: number) => { setPlaying(false); setSel(i) }

  const removePatient = async (pid: string) => {
    if (!window.confirm(`Supprimer définitivement ${pid} ? Cette action est irréversible.`)) return
    await deletePatient(pid).catch(() => {})
    const ps = await getPatients()
    const ids = ps.map((p) => p.id)
    setPatients(ids)
    if (current === pid) {
      const next = ids[0] ?? null
      setCurrent(next)
      if (!next) { setTl(null); setReport('') }
    }
  }

  const s = tl?.summary
  const exam = tl?.exams[sel]

  const measur = overlay ? overlay.masks.filter((m) => m.vol >= 2) : []

  useEffect(() => {
    if (!measur.length) { setPicked(new Set()); return }
    const k = Math.min(5, measur.length)
    const idxs = Array.from({ length: k }, (_, j) => Math.round((j * (measur.length - 1)) / (k - 1 || 1)))
    setPicked(new Set(idxs.map((j) => measur[j].week)))
  }, [overlay])

  const toggleWeek = (w: string) =>
    setPicked((prev) => { const n = new Set(prev); n.has(w) ? n.delete(w) : n.add(w); return n })

  const layers = measur
    .map((m, i) => ({ m, i }))
    .filter(({ m }) => picked.has(m.week))
    .map(({ m, i }) => ({
      url: m.url, week: m.week,
      rgb: timeColor(measur.length > 1 ? i / (measur.length - 1) : 0) as [number, number, number],
    }))

  useEffect(() => {
    if (current && exam) getReport(current, exam.week).then((r) => { setReport(r.text); setEdited(false) }).catch(() => setReport(''))
  }, [current, exam?.week])

  const copyReport = () => {
    navigator.clipboard?.writeText(report)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }
  const downloadReport = () => {
    const blob = new Blob([report], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `CR_${current}_${exam?.week ?? ''}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const vd = exam?.verdict_auto
  return (
    <div className="flex h-screen text-slate-100 bg-slate-950"
      style={{ background: 'radial-gradient(1200px 600px at 78% -8%, rgba(56,189,248,0.10), transparent 60%), radial-gradient(900px 500px at 0% 100%, rgba(99,102,241,0.10), transparent 55%), #060912' }}>
      <aside className="w-60 shrink-0 border-r border-white/5 bg-slate-950/60 backdrop-blur-sm p-4 flex flex-col gap-4">
        <div>
          <div className="text-lg font-bold tracking-tight">Neuro<span className="text-sky-400">Track</span></div>
          <div className="text-[11px] text-slate-500">suivi tumoral assisté</div>
        </div>
        <div className="flex flex-col gap-1">
          <div className="text-xs uppercase text-slate-500 mb-1">Patients</div>
          {patients.map((p) => (
            <div key={p} className="group flex items-center gap-1">
              <button onClick={() => setCurrent(p)}
                className={`flex-1 text-left px-3 py-2 rounded-lg text-sm transition ${
                  p === current ? 'bg-sky-500/15 text-sky-300 border border-sky-500/30' : 'hover:bg-slate-900 text-slate-300 border border-transparent'}`}>
                {p}
              </button>
              <button onClick={() => removePatient(p)} title="supprimer définitivement"
                className="shrink-0 px-1.5 py-1 rounded-md text-slate-600 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition">🗑</button>
            </div>
          ))}
          {!patients.length && <div className="text-xs text-slate-600">chargement…</div>}
        </div>
        <button onClick={() => setShowAdd(true)}
          className="mt-auto px-3 py-2 rounded-lg text-sm bg-sky-500/15 text-sky-300 border border-sky-500/30 hover:bg-sky-500/25">
          + Ajouter une IRM
        </button>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-[1500px] mx-auto p-6 flex flex-col gap-5">
          <header className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold">{current ?? '—'}</h1>
              <div className="text-sm text-slate-500">{s ? `${s.n_exams} examens de suivi` : ''}{exam ? ` · examen ${exam.week}` : ''}</div>
            </div>
            {vd && (
              <div className="px-5 py-2.5 rounded-xl font-bold tracking-wide transition-all"
                style={{
                  background: `linear-gradient(135deg, ${VERDICT_COLOR[vd] || '#444'}33, ${VERDICT_COLOR[vd] || '#444'}14)`,
                  color: VERDICT_COLOR[vd] || '#fff',
                  border: `1px solid ${VERDICT_COLOR[vd] || '#444'}66`,
                  boxShadow: `0 0 22px ${VERDICT_COLOR[vd] || '#444'}55, inset 0 0 12px ${VERDICT_COLOR[vd] || '#444'}22`,
                }}>
                {VERDICT_LABEL[vd] || vd}
              </div>
            )}
          </header>

          {exam && (
            <div className="flex gap-4">
              <Kpi label="volume" value={`${exam.vol_custom} mL`} sub="tumeur rehaussante" />
              <Kpi label="variation" value={exam.delta_pct == null ? '—' : `${exam.delta_pct > 0 ? '+' : ''}${exam.delta_pct}%`} sub="vs examen précédent"
                color={exam.delta_pct != null && exam.delta_pct > 0 ? VERDICT_COLOR.PD : exam.delta_pct != null ? VERDICT_COLOR.PR : undefined} />
              <Kpi label="vitesse" value={exam.velocity == null ? '—' : `${exam.velocity} mL/mois`} sub="croissance récente" />
              <Kpi label="pic du suivi" value={s ? `${s.peak_vol} mL` : '—'} sub={s?.peak_week} />
            </div>
          )}

          {tl && tl.exams.length > 0 && (
            <div className="flex items-center gap-3 rounded-xl bg-slate-900/60 border border-slate-800 px-4 py-2.5">
              <button onClick={togglePlay}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium transition-all ${
                  playing ? 'bg-sky-400/30 text-sky-100 border-sky-300/50 shadow-[0_0_18px_rgba(56,189,248,0.6)] animate-pulse'
                          : 'bg-sky-500/20 text-sky-200 border-sky-500/30 hover:bg-sky-500/30'}`}>
                <span className="text-xs">{playing ? '❚❚' : '▶'}</span>{playing ? 'Pause' : 'Lecture'}
              </button>
              <button onClick={() => stepTo(Math.max(0, sel - 1))} disabled={sel === 0}
                className="px-2 py-1 rounded-md bg-slate-800 text-slate-200 disabled:opacity-30 text-sm">◀</button>
              <input type="range" min={0} max={tl.exams.length - 1} value={sel}
                onChange={(e) => stepTo(Number(e.target.value))} className="flex-1 accent-sky-400" />
              <button onClick={() => stepTo(Math.min(tl.exams.length - 1, sel + 1))} disabled={sel === tl.exams.length - 1}
                className="px-2 py-1 rounded-md bg-slate-800 text-slate-200 disabled:opacity-30 text-sm">▶</button>
              <div className="text-xs text-slate-400 w-32 text-right tabular-nums">{exam?.week} ({sel + 1}/{tl.exams.length})</div>
            </div>
          )}

          <Card
            title={overlayMode ? 'Cerveau — superposition de l’évolution' : exam ? `Cerveau — ${exam.week}` : 'Cerveau'}
            right={
              <div className="flex gap-2">
                <Toggle on={overlayMode} left="examen" right="superposition" onChange={setOverlayMode} />
                <Toggle on={render3d} left="2D" right="3D" onChange={setRender3d} />
              </div>
            }>
            <div className="h-[520px] rounded-lg overflow-hidden bg-black/40 ring-1 ring-white/5 relative">
              {current && exam && (
                <BrainViewer patient={current} week={exam.week} source="custom" render3d={render3d}
                  overlay={overlayMode && overlay ? { ref: overlay.ref, layers } : null} />
              )}
              {overlayMode && overlayLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/60 text-sky-200 text-sm animate-pulse">
                  recalage des examens et superposition en cours…
                </div>
              )}
            </div>
            {overlayMode && measur.length > 0 && (
              <div className="mt-3">
                <div className="text-[10px] text-slate-500 mb-1">examens superposés — clic pour activer/désactiver · ancien → récent</div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {measur.map((m, i) => {
                    const [r, g, b] = timeColor(measur.length > 1 ? i / (measur.length - 1) : 0) as [number, number, number]
                    const on = picked.has(m.week)
                    return (
                      <button key={m.week} onClick={() => toggleWeek(m.week)}
                        className="px-1.5 py-0.5 rounded text-[10px] border transition"
                        style={on
                          ? { background: `rgb(${r},${g},${b})`, color: '#000', borderColor: `rgb(${r},${g},${b})` }
                          : { background: 'transparent', color: `rgb(${r},${g},${b})`, borderColor: `rgba(${r},${g},${b},0.45)` }}>
                        {m.week.replace('week-', 'w')}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </Card>

          <Card title="Trajectoire du volume tumoral rehaussant et réponse RANO">
            {tl && (
              <>
                <div className="h-[340px]"><VolumeChart exams={tl.exams} selected={sel} onSelect={stepTo} /></div>
                <div className="mt-2"><RanoRibbon exams={tl.exams} selected={sel} onSelect={stepTo} /></div>
              </>
            )}
          </Card>

          {exam && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <Card title="Examen sélectionné">
                <div className="flex flex-col gap-2 text-sm">
                  <div className="flex items-center justify-between"><span className="text-slate-500">semaine</span><b>{exam.week}</b></div>
                  <div className="flex items-center justify-between"><span className="text-slate-500">volume rehaussant</span><b>{exam.vol_custom} mL</b></div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-slate-500">verdict auto</span>
                    <b style={{ color: VERDICT_COLOR[exam.verdict_auto] }}>{exam.verdict_auto}</b>
                  </div>
                  {exam.verdict_why && <div className="text-xs text-slate-400 italic -mt-1">{exam.verdict_why}</div>}
                  {exam.new_lesion && (
                    <div className="self-start px-2 py-0.5 rounded-md text-xs font-semibold bg-red-500/15 text-red-300 border border-red-500/30">
                      nouvelle lésion · {exam.new_vol} mL
                    </div>
                  )}
                  <div className="flex items-center justify-between text-slate-600"><span>coupes</span><span>{exam.n_slices}</span></div>
                </div>
              </Card>

              <Card title="Compte-rendu" right={
                <div className="flex items-center gap-2">
                  {edited && <span className="text-[10px] text-amber-400/80">modifié</span>}
                  <span className="text-[10px] text-slate-500">éditable</span>
                  <button onClick={copyReport} className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px]">{copied ? 'copié' : 'copier'}</button>
                  <button onClick={downloadReport} className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px]">exporter</button>
                </div>
              }>
                <textarea value={report} onChange={(e) => { setReport(e.target.value); setEdited(true) }}
                  spellCheck={false}
                  className="w-full min-h-[150px] resize-y bg-slate-950/60 text-slate-200 text-sm leading-relaxed outline-none border border-slate-700 focus:border-sky-500/50 rounded-lg p-3" />
              </Card>
            </div>
          )}
        </div>
      </main>

      {showAdd && <AddIrmModal onClose={() => setShowAdd(false)}
        onCreated={(pid) => {
          getPatients().then((ps) => { setPatients(ps.map((p) => p.id)); setCurrent(pid) })
          setShowAdd(false)
        }} />}
    </div>
  )
}
