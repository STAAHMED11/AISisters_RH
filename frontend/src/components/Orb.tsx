'use client'
import { useEffect, useRef } from 'react'

export type OrbState = 'idle' | 'connecting' | 'listening' | 'thinking' | 'speaking'

const PALETTE: Record<OrbState, [number[], number[]]> = {
  idle: [[27, 111, 149], [120, 177, 203]],
  connecting: [[27, 111, 149], [255, 228, 92]],
  listening: [[45, 190, 170], [140, 230, 205]],
  thinking: [[120, 177, 203], [186, 160, 235]],
  speaking: [[255, 176, 70], [255, 120, 100]],
}
const rgb = (c: number[], a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`

/** Canvas orb: breathes at rest, swells with the mic level (listening) or the agent's voice (speaking). */
export default function Orb({ state, getInput, getOutput, size = 380 }: {
  state: OrbState; getInput: () => number; getOutput: () => number; size?: number
}) {
  const ref = useRef<HTMLCanvasElement>(null)
  const st = useRef(state)
  st.current = state
  const fns = useRef({ getInput, getOutput })
  fns.current = { getInput, getOutput }

  useEffect(() => {
    const cv = ref.current!
    const ctx = cv.getContext('2d')!
    const dpr = window.devicePixelRatio || 1
    cv.width = size * dpr; cv.height = size * dpr
    ctx.scale(dpr, dpr)
    let raf = 0, t = 0, level = 0
    let c1 = [...PALETTE.idle[0]], c2 = [...PALETTE.idle[1]]
    const cx = size / 2, cy = size / 2

    const draw = () => {
      t += 0.016
      const s = st.current
      let target = 0
      try { target = s === 'speaking' ? fns.current.getOutput() : s === 'listening' ? fns.current.getInput() : 0 } catch { /* not connected */ }
      level += (Math.min(1, target * 1.6) - level) * 0.2
      const [t1, t2] = PALETTE[s]
      for (let i = 0; i < 3; i++) { c1[i] += (t1[i] - c1[i]) * 0.06; c2[i] += (t2[i] - c2[i]) * 0.06 }
      const breathe = s === 'idle' || s === 'connecting' ? Math.sin(t * 1.6) * 3 : s === 'thinking' ? Math.sin(t * 4) * 5 : Math.sin(t * 1.2) * 2
      const r = size * 0.2 + breathe + level * size * 0.1

      ctx.clearRect(0, 0, size, size)
      // outer glow
      const glow = ctx.createRadialGradient(cx, cy, r * 0.6, cx, cy, size / 2)
      glow.addColorStop(0, rgb(c1, 0.35 + level * 0.3)); glow.addColorStop(1, rgb(c1, 0))
      ctx.fillStyle = glow; ctx.fillRect(0, 0, size, size)
      // ripple rings driven by level
      for (let k = 0; k < 2; k++) {
        const p = ((t * 0.5 + k * 0.5) % 1)
        ctx.beginPath(); ctx.arc(cx, cy, r * (1 + p * 0.7), 0, Math.PI * 2)
        ctx.strokeStyle = rgb(c2, (1 - p) * (0.08 + level * 0.35)); ctx.lineWidth = 2; ctx.stroke()
      }
      // wobbly body
      ctx.save()
      ctx.beginPath()
      const wob = 0.035 + level * 0.1
      for (let a = 0; a <= Math.PI * 2 + 0.05; a += 0.05) {
        const rr = r * (1 + wob * Math.sin(3 * a + t * 2) + wob * 0.7 * Math.sin(5 * a - t * 1.7) + wob * 0.5 * Math.sin(7 * a + t * 3.1))
        const x = cx + Math.cos(a) * rr, y = cy + Math.sin(a) * rr
        a === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
      }
      ctx.closePath(); ctx.clip()
      const body = ctx.createLinearGradient(cx - r, cy - r, cx + r, cy + r)
      body.addColorStop(0, rgb(c1)); body.addColorStop(1, rgb(c2))
      ctx.fillStyle = body; ctx.fillRect(0, 0, size, size)
      ctx.globalCompositeOperation = 'lighter'
      for (let i = 0; i < 4; i++) {
        const ang = t * (0.5 + i * 0.27) + i * 1.9
        const bx = cx + Math.cos(ang) * r * 0.45, by = cy + Math.sin(ang * 1.1) * r * 0.45
        const g = ctx.createRadialGradient(bx, by, 0, bx, by, r * 0.85)
        g.addColorStop(0, `rgba(255,255,255,${0.28 + level * 0.25})`); g.addColorStop(1, 'rgba(255,255,255,0)')
        ctx.fillStyle = g; ctx.fillRect(0, 0, size, size)
      }
      ctx.restore()
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(raf)
  }, [size])

  return <canvas ref={ref} style={{ width: size, height: size }} aria-hidden />
}
