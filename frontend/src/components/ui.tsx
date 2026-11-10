import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export const VERDICT: Record<string, { label: string; cls: string; dot: string }> = {
  met: { label: 'Satisfait', cls: 'bg-emerald-50 text-emerald-800 ring-emerald-200', dot: 'bg-emerald-500' },
  partial: { label: 'Partiel', cls: 'bg-amber-50 text-amber-800 ring-amber-200', dot: 'bg-amber-500' },
  not_met: { label: 'Non satisfait', cls: 'bg-rose-50 text-rose-800 ring-rose-200', dot: 'bg-rose-500' },
  not_evidenced: { label: 'Non établi', cls: 'bg-slate-100 text-slate-600 ring-slate-200', dot: 'bg-slate-400' },
}

export function VerdictChip({ v }: { v: string }) {
  const x = VERDICT[v] ?? VERDICT.not_evidenced
  return <span className={`badge ring-1 ring-inset ${x.cls}`}><span className={`h-1.5 w-1.5 rounded-full ${x.dot}`} />{x.label}</span>
}

/** Triage outcome. The same colours drive the lane stripe on the candidates table. */
export function PrequalBadge({ prequal, status }: { prequal: string; status: string }) {
  if (status === 'failed') return <span className="badge bg-rose-50 text-rose-800 ring-1 ring-inset ring-rose-200"><span className="h-1.5 w-1.5 rounded-full bg-rose-500" />Échec</span>
  if (isBusy(status)) return <span className="badge animate-pulse bg-indigo-50 text-brand ring-1 ring-inset ring-indigo-200"><span className="h-1.5 w-1.5 rounded-full bg-brand" />Analyse…</span>
  const m: Record<string, [string, string, string]> = {
    pass: ['Pré-qualifié', 'bg-emerald-50 text-emerald-800 ring-emerald-200', 'bg-emerald-500'],
    review: ['À examiner', 'bg-amber-50 text-amber-800 ring-amber-200', 'bg-amber-500'],
    fail: ['Ne passe pas', 'bg-rose-50 text-rose-800 ring-rose-200', 'bg-rose-500'],
  }
  const [l, c, d] = m[prequal] ?? ['—', 'bg-slate-100 text-slate-500 ring-slate-200', 'bg-slate-400']
  return <span className={`badge whitespace-nowrap ring-1 ring-inset ${c}`}><span className={`h-1.5 w-1.5 rounded-full ${d}`} />{l}</span>
}

/** Colour of the sorting lane for a candidate row. */
export function laneClass(c: { status: string; prequal: string }): string {
  if (c.status === 'failed') return 'border-l-rose-500'
  if (isBusy(c.status)) return 'border-l-indigo-300'
  return ({ pass: 'border-l-emerald-500', review: 'border-l-amber-400', fail: 'border-l-rose-400' } as Record<string, string>)[c.prequal] ?? 'border-l-slate-300'
}

export const TH = { yes: 0.7, maybe: 0.45 } // overwritten from /api/health at startup

export function ScoreBar({ value, label }: { value: number | null | undefined; label?: string }) {
  if (value == null) return <span className="text-muted">—</span>
  const pct = Math.round(value * 100)
  const col = value >= TH.yes ? 'bg-emerald-500' : value >= TH.maybe ? 'bg-amber-500' : 'bg-rose-500'
  return (
    <div className="flex items-center gap-2" title={`${label ?? 'Score'} : ${pct}/100 — pré-qualifié dès ${Math.round(TH.yes * 100)} (et aucun critère indispensable non satisfait) ; à examiner dès ${Math.round(TH.maybe * 100)}`}>
      <span className="num w-7 text-right text-[17px]">{pct}</span>
      <div className="relative h-1.5 w-16 overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full rounded-full ${col}`} style={{ width: `${pct}%` }} />
        <span className="absolute top-0 h-full w-px bg-ink/40" style={{ left: `${TH.yes * 100}%` }} aria-hidden />
      </div>
    </div>
  )
}

export const isBusy = (s: string) => ['uploaded', 'parsing', 'screening'].includes(s)

const AVATAR = ['#0b4f6c', '#2f6f5e', '#7a4e2d', '#5b4b8a', '#8a3b4c', '#3d5a80', '#6b6b2f']
export function Avatar({ name, size = 36 }: { name: string; size?: number }) {
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]?.toUpperCase()).join('') || '?'
  const bg = AVATAR[[...name].reduce((a, ch) => a + ch.charCodeAt(0), 0) % AVATAR.length]
  return <span className="grid shrink-0 place-items-center rounded-full font-semibold text-white" style={{ width: size, height: size, background: bg, fontSize: size * 0.38 }} aria-hidden>{initials}</span>
}

export function PageHeader({ title, subtitle, back, actions }: { title: ReactNode; subtitle?: ReactNode; back?: { to: string; label: string }; actions?: ReactNode }) {
  return (
    <header className="mb-7 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        {back && <Link to={back.to} className="mb-1 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><span aria-hidden>←</span> {back.label}</Link>}
        <h1 className="font-display text-[2rem] font-semibold leading-tight sm:text-4xl">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-[15px] text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />
}

export function PageSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Chargement">
      <Skeleton className="h-10 w-72" />
      <Skeleton className="h-4 w-96" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}

export function Empty({ icon = '📭', title, children }: { icon?: string; title: string; children?: ReactNode }) {
  return (
    <div className="grid place-items-center px-6 py-14 text-center">
      <div className="mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-slate-100 text-2xl">{icon}</div>
      <div className="font-display text-xl font-semibold">{title}</div>
      {children && <div className="mt-1 max-w-sm text-sm text-muted">{children}</div>}
    </div>
  )
}
