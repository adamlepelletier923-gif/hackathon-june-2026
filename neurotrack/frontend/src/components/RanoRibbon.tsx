import type { Exam } from '../api'
import { VERDICT_COLOR } from '../api'

type Props = {
  exams: Exam[]
  selected: number
  onSelect: (i: number) => void
}

export default function RanoRibbon({ exams, selected, onSelect }: Props) {
  const legend: [string, string][] = [['PD', 'progression'], ['SD', 'stable'], ['PR', 'réponse part.'], ['CR', 'réponse compl.']]
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-stretch h-7">
        <div className="w-[60px] shrink-0 self-center text-right pr-2 text-[10px] uppercase tracking-wide text-slate-500">RANO</div>
        <div className="flex-1 flex gap-px pr-6">
          {exams.map((e, i) => (
            <button key={e.week} onClick={() => onSelect(i)} title={`${e.week} · ${e.verdict_auto}`}
              className="flex-1 rounded-[2px] transition"
              style={{
                background: VERDICT_COLOR[e.verdict_auto] ?? '#1e293b',
                opacity: i === selected ? 1 : 0.8,
                outline: i === selected ? '2px solid #e2e8f0' : 'none',
                outlineOffset: -1,
              }} />
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3 pl-[60px] pr-6 mt-1 text-[10px] text-slate-500">
        {legend.map(([k, lbl]) => (
          <span key={k} className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: VERDICT_COLOR[k] }} />{lbl}
          </span>
        ))}
      </div>
    </div>
  )
}
