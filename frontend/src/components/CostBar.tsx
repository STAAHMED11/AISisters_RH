'use client'
import { pct, usd } from '../lib/money'

// Categorical slots validated with scripts/validate_palette.js (light + dark): blue, orange, aqua, yellow.
export const GROUPS = ['cv', 'interview', 'voice', 'other'] as const
export type Group = (typeof GROUPS)[number]
export const GROUP_COLOR: Record<Group, string> = { cv: '#2a78d6', interview: '#eb6834', voice: '#1baf7a', other: '#eda100' }
export const GROUP_LABEL: Record<Group, string> = {
  cv: 'Analyse des CV', interview: 'Pré-entretien (IA)', voice: 'Voix (ElevenLabs)', other: 'Critères et courriers',
}

type Cost = Record<Group | 'total', number>

/** Thin segmented bar: 2px surface gaps, rounded data-ends, per-segment hover tooltip. No text on the bar: figures sit beside it. */
export function CostBar({ cost, height = 10 }: { cost: Cost; height?: number }) {
  const total = cost.total || GROUPS.reduce((s, g) => s + (cost[g] || 0), 0)
  if (!total) return <div className="rounded-full bg-slate-100" style={{ height }} />
  const parts = GROUPS.filter(g => cost[g] > 0)
  return (
    <div className="flex w-full gap-[2px] overflow-hidden rounded-full bg-white" style={{ height }} role="img"
      aria-label={parts.map(g => `${GROUP_LABEL[g]} ${usd(cost[g])}`).join(', ')}>
      {parts.map((g, i) => (
        <div key={g} title={`${GROUP_LABEL[g]} : ${usd(cost[g])} (${pct(cost[g], total)} %)`}
          style={{ width: `${(cost[g] / total) * 100}%`, background: GROUP_COLOR[g], borderRadius: i === 0 ? '999px 3px 3px 999px' : i === parts.length - 1 ? '3px 999px 999px 3px' : 3 }} />
      ))}
    </div>
  )
}

/** Legend rows: swatch + name + amount + share (text in ink tokens, colour only on the swatch). */
export function CostLegend({ cost }: { cost: Cost }) {
  const total = cost.total || 1
  return (
    <ul className="space-y-2.5">
      {GROUPS.map(g => (
        <li key={g} className="flex items-center gap-3 text-sm">
          <span className="h-3 w-3 shrink-0 rounded-[3px]" style={{ background: GROUP_COLOR[g] }} />
          <span className="flex-1">{GROUP_LABEL[g]}</span>
          <span className="tabular-nums text-muted">{pct(cost[g], total)} %</span>
          <span className="w-20 text-right font-medium tabular-nums">{usd(cost[g])}</span>
        </li>
      ))}
    </ul>
  )
}

export function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card p-4">
      <div className="num text-[2.2rem]">{value}</div>
      <div className="text-sm text-ink">{label}</div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </div>
  )
}
