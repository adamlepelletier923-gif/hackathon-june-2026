import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import type { Exam } from '../api'
import { VERDICT_COLOR } from '../api'

type Props = {
  exams: Exam[]
  selected: number
  onSelect: (i: number) => void
}

export default function VolumeChart({ exams, selected, onSelect }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  useEffect(() => {
    if (!ref.current) return
    chart.current = echarts.init(ref.current, undefined, { renderer: 'canvas' })
    const onResize = () => chart.current?.resize()
    window.addEventListener('resize', onResize)
    const ro = new ResizeObserver(onResize)
    ro.observe(ref.current)
    chart.current.on('click', (p: any) => {
      if (typeof p.dataIndex === 'number') onSelectRef.current(p.dataIndex)
    })
    return () => { window.removeEventListener('resize', onResize); ro.disconnect(); chart.current?.dispose() }
  }, [])

  useEffect(() => {
    if (!chart.current) return
    const x = exams.map((e) => e.wn)
    const custom = exams.map((e) => e.vol_custom)
    const dataset = exams.map((e) => e.vol_dataset)
    const refPoints: any[] = []
    const bi = exams.findIndex((e) => e.is_baseline)
    const ni = exams.findIndex((e) => e.is_nadir)
    if (bi >= 0) refPoints.push({ name: 'baseline', xAxis: bi, yAxis: exams[bi].vol_custom, value: 'baseline',
      itemStyle: { color: '#64748b' }, label: { color: '#cbd5e1', fontSize: 10 } })
    if (ni >= 0 && ni !== bi) refPoints.push({ name: 'nadir', xAxis: ni, yAxis: exams[ni].vol_custom, value: 'nadir',
      itemStyle: { color: '#22c55e' }, label: { color: '#86efac', fontSize: 10 } })
    const newLesions = exams
      .map((e, i) => ({ e, i }))
      .filter(({ e }) => e.new_lesion)
      .map(({ e, i }) => ({ name: 'nouvelle lésion', symbol: 'triangle', symbolSize: 16, xAxis: i, yAxis: e.vol_custom, value: 'lésion',
        itemStyle: { color: '#ef4444' }, label: { color: '#fca5a5', fontSize: 10, position: 'bottom' } }))
    chart.current.setOption({
      backgroundColor: 'transparent',
      grid: { left: 60, right: 24, top: 28, bottom: 40 },
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#111827', borderColor: '#374151', textStyle: { color: '#e5e7eb' },
        formatter: (ps: any) => {
          const i = ps[0].dataIndex
          const e = exams[i]
          return `<b>${e.week}</b> (sem. ${e.wn})<br/>` +
            `notre modèle : <b>${e.vol_custom} mL</b><br/>` +
            `dataset : ${e.vol_dataset} mL<br/>` +
            `verdict auto : <b style="color:${VERDICT_COLOR[e.verdict_auto] || '#aaa'}">${e.verdict_auto}</b>` +
            (e.verdict_why ? `<br/><span style="color:#94a3b8">${e.verdict_why}</span>` : '')
        },
      },
      xAxis: {
        type: 'category', data: x, name: 'semaines',
        axisLine: { lineStyle: { color: '#4b5563' } }, axisLabel: { color: '#9ca3af' },
      },
      yAxis: {
        type: 'value', name: 'mL (rehaussant)',
        splitLine: { lineStyle: { color: '#1f2937' } },
        axisLabel: { color: '#9ca3af' }, nameTextStyle: { color: '#9ca3af' },
      },
      series: [
        {
          name: 'dataset', type: 'line', data: dataset, smooth: true,
          lineStyle: { color: '#3f3f5a', width: 1, type: 'dashed' },
          itemStyle: { color: '#3f3f5a' }, symbol: 'none', z: 1,
        },
        {
          name: 'notre modèle', type: 'line', data: custom, smooth: true,
          lineStyle: { color: '#38bdf8', width: 3 },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(56,189,248,0.35)' }, { offset: 1, color: 'rgba(56,189,248,0.02)' }]) },
          symbol: 'circle', symbolSize: 9, z: 3,
          itemStyle: {
            color: (p: any) => VERDICT_COLOR[exams[p.dataIndex].verdict_auto] || '#38bdf8',
            borderColor: (p: any) => (p.dataIndex === selected ? '#fff' : 'transparent'),
            borderWidth: 2,
          },
          markPoint: {
            symbol: 'pin', symbolSize: 38, data: [...refPoints, ...newLesions],
            label: { formatter: (p: any) => p.data.value, position: 'top' },
          },
        },
      ],
    })
  }, [exams, selected])

  return <div ref={ref} style={{ width: '100%', height: '100%' }} />
}
