import { useEffect, useRef } from 'react'
import { Niivue } from '@niivue/niivue'

export type Layer = { url: string; rgb: [number, number, number]; week: string }

type Props = {
  patient: string
  week: string
  source: 'custom' | 'dataset'
  render3d: boolean
  overlay?: { ref: string; layers: Layer[] } | null
  src?: { image: string; seg: string } | null
}

export default function BrainViewer({ patient, week, source, render3d, overlay, src }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const nv = useRef<Niivue | null>(null)

  useEffect(() => {
    if (!canvas.current) return
    const n = new Niivue({ backColor: [0.04, 0.05, 0.09, 1], show3Dcrosshair: true, crosshairColor: [0.9, 0.9, 0.9, 0.4] })
    n.attachToCanvas(canvas.current)
    n.opts.multiplanarShowRender = 1            // SHOW_RENDER.ALWAYS : la 3D reste visible meme en mode coupes
    n.opts.multiplanarEqualSize = true          // tuiles de meme taille -> vues alignees
    n.setMultiplanarLayout(2)                   // MULTIPLANAR_TYPE.GRID : 2x2 propre
    nv.current = n
  }, [])

  const overlaySig = overlay ? overlay.ref + '|' + overlay.layers.map((l) => l.week).join(',') : ''

  useEffect(() => {
    const n = nv.current
    if (!n) return

    if (overlay && overlay.layers.length) {
      overlay.layers.forEach((l, i) => {
        const [r, g, b] = l.rgb
        n.addColormap(`ev${i}`, { R: [r, r], G: [g, g], B: [b, b], A: [0, 255], I: [0, 255] })
      })
      const vols = [
        { url: overlay.ref },
        ...overlay.layers.map((l, i) => ({ url: l.url, colormap: `ev${i}`, opacity: 0.5, cal_min: 0.5, cal_max: 1 })),
      ]
      n.loadVolumes(vols).then(() => n.setSliceType(render3d ? n.sliceTypeRender : n.sliceTypeMultiplanar)).catch(() => {})
      return
    }

    const base = src ? src.image : (week ? `/nii/${patient}/${week}/image.nii.gz` : '')
    const seg = src ? src.seg : (week ? `/nii/${patient}/${week}/seg_${source}.nii.gz` : '')
    if (!base) return
    n.loadVolumes([
      { url: base },
      { url: seg, colormap: src || source === 'custom' ? 'blue' : 'red', opacity: 0.6, cal_min: 0.5, cal_max: 1 },
    ]).then(() => n.setSliceType(render3d ? n.sliceTypeRender : n.sliceTypeMultiplanar)).catch(() => {})
  }, [patient, week, source, overlaySig, src?.image])

  useEffect(() => {
    const n = nv.current
    if (!n) return
    n.setSliceType(render3d ? n.sliceTypeRender : n.sliceTypeMultiplanar)
  }, [render3d])

  return <canvas ref={canvas} style={{ width: '100%', height: '100%' }} />
}
