'use client'
import { type ReactNode, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter, useParams, useSearchParams } from 'next/navigation'
import { useSetParams } from '../lib/nav'
import { api } from '../api'
import { Avatar, Empty, PageHeader, PrequalBadge, ScoreBar, Skeleton, TH, isBusy, laneClass } from '../components/ui'
import { useUI } from '../lib/ui'

type Row = any
const FILTERS: Record<string, { label: string; test: (c: Row) => boolean }> = {
  all: { label: 'Tous', test: () => true },
  pass: { label: 'Pré-qualifiés', test: c => c.prequal === 'pass' },
  review: { label: 'À examiner', test: c => c.prequal === 'review' },
  todecide: { label: 'À décider', test: c => c.interview_status === 'scored' && !c.decision },
  waiting: { label: 'En attente du candidat', test: c => c.has_interview && ['pending', 'started'].includes(c.interview_status) && !c.decision && c.invite_state === 'sent' },
  fail: { label: 'Ne passent pas', test: c => c.prequal === 'fail' },
  // reachable from the offer page, not shown as tabs
  interviewed: { label: 'Entretiens faits', test: c => ['ended', 'scored'].includes(c.interview_status) },
  accepted: { label: 'Retenus', test: c => c.decision === 'accepted' },
  failed: { label: 'CV en erreur', test: c => c.status === 'failed' },
}
const TABS = ['all', 'pass', 'review', 'todecide', 'waiting', 'fail']

export default function Candidates() {
  const { id } = useParams<{ id: string }>()
  const nav = useRouter()
  const { confirm, toast } = useUI()
  const params = useSearchParams()
  const setParams = useSetParams()
  const filter = FILTERS[params.get('filter') ?? ''] ? (params.get('filter') as string) : 'all'
  const [rows, setRows] = useState<Row[] | null>(null)
  const [job, setJob] = useState<any>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  useEffect(() => { api(`/jobs/${id}`).then(setJob) }, [id])
  const load = async () => { const r = await api(`/jobs/${id}/candidates`); setRows(r); return r }
  useEffect(() => {
    let stop = false
    const tick = async () => { const r = await load(); if (!stop && r.some((c: Row) => isBusy(c.status))) setTimeout(tick, 2500) }
    tick()
    return () => { stop = true }
  }, [id])

  const counts = useMemo(() => Object.fromEntries(Object.entries(FILTERS).map(([k, f]) => [k, (rows ?? []).filter(f.test).length])), [rows])
  const shown = (rows ?? []).filter(FILTERS[filter].test)
  const toValidate = (rows ?? []).filter(c => c.status === 'screened' && c.triage === 'no' && !c.decision).length

  const act = async (c: Row, fn: () => Promise<any>, done?: string) => {
    setBusyId(c.id)
    try { await fn(); await load(); if (done) toast(done, 'success') } catch (e: any) { toast(e.message, 'error') } finally { setBusyId(null) }
  }
  const batchReject = async () => {
    if (!(await confirm({ title: `Valider ${toValidate} refus ?`, text: 'Un courrier personnalisé est préparé pour chaque candidat. Vous le relisez avant tout envoi.', confirmLabel: 'Valider les refus', tone: 'danger' }))) return
    await api(`/jobs/${id}/reject-batch`, { method: 'POST' }); await load(); toast(`${toValidate} refus validés ; les courriers sont à relire.`, 'success')
  }
  const rescreen = async () => { await api(`/jobs/${id}/rescreen`, { method: 'POST' }); setJob({ ...job, stale: 0 }); load() }

  /** The single most useful next step for this candidate, as a button where it can be done in place. */
  const nextAction = (c: Row): ReactNode => {
    const send = async (extend: boolean) => {
      if (!(await confirm({ title: "Envoyer l'invitation ?", text: `Le lien du pré-entretien est envoyé à ${c.email || 'ce candidat'}.`, confirmLabel: 'Envoyer' }))) return
      act(c, () => api(`/candidates/${c.id}/invite/send`, { method: 'POST', json: extend ? { extend: true } : {} }), 'Invitation envoyée.')
    }
    const btn = (label: string, onClick: () => void, primary = false) => (
      <button className={`${primary ? 'btn-primary' : 'btn-ghost'} !px-3 !py-1.5 whitespace-nowrap`} disabled={busyId === c.id}
        onClick={e => { e.stopPropagation(); onClick() }}>{busyId === c.id ? '…' : label}</button>
    )
    const go = (label: string, primary = false) => <Link href={`/candidates/${c.id}`} onClick={e => e.stopPropagation()} className={`${primary ? 'btn-primary' : 'btn-ghost'} !px-3 !py-1.5 whitespace-nowrap`}>{label}</Link>
    if (c.status === 'failed') return btn("Relancer l'analyse", () => act(c, () => api(`/candidates/${c.id}/reprocess`, { method: 'POST' })))
    if (isBusy(c.status)) return <span className="text-sm text-muted">Analyse en cours…</span>
    if (c.decision) return <span className={`text-sm font-medium ${c.decision === 'accepted' ? 'text-emerald-700' : 'text-rose-700'}`}>{c.decision === 'accepted' ? 'Retenu' : 'Refusé'}</span>
    if (c.interview_status === 'scored') return go('Lire et décider', true)
    if (c.interview_status === 'ended') return <span className="animate-pulse text-sm text-brand">Analyse de l'entretien…</span>
    if (c.interview_expired) return btn('Renvoyer le lien', () => send(true), true)
    if (c.interview_status === 'started') return <span className="text-sm text-indigo-700">Entretien en cours</span>
    if (c.has_interview && c.invite_state !== 'sent') return btn("Envoyer l'invitation", () => send(false), true)
    if (c.has_interview) return <span className="text-sm text-muted">En attente du candidat</span>
    if (c.triage === 'maybe') return btn('Inviter', () => send(false))
    if (c.triage === 'no') return go('Voir le refus')
    return go('Ouvrir')
  }

  return (
    <div className="space-y-5">
      <PageHeader back={{ to: `/jobs/${id}`, label: job?.title ?? 'Offre' }} title="Candidats"
        subtitle={`${rows?.length ?? 0} candidature${(rows?.length ?? 0) > 1 ? 's' : ''}. Cliquez sur une ligne pour ouvrir le dossier.`}
        actions={<>
          {toValidate > 0 && <button className="btn-danger" onClick={batchReject}>Valider {toValidate} refus proposés</button>}
          <Link href={`/jobs/${id}/outbox`} className="btn-ghost">Courriers</Link>
          <Link href={`/jobs/${id}`} className="btn-primary">Déposer des CV</Link>
        </>} />

      {job?.stale > 0 && (
        <div className="card flex flex-wrap items-center justify-between gap-4 border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          <span>Les critères ont changé : <b>{job.stale} CV</b> sont à ré-analyser pour que les verdicts soient à jour.</span>
          <button className="btn-primary" onClick={rescreen}>Ré-analyser</button>
        </div>
      )}

      <div className="sticky top-14 z-10 -mx-1 flex flex-wrap gap-1.5 bg-canvas/95 px-1 py-2 backdrop-blur lg:top-0" role="tablist">
        {[...TABS, ...(TABS.includes(filter) ? [] : [filter])].map(k => (
          <button key={k} role="tab" aria-selected={filter === k} onClick={() => setParams(k === 'all' ? {} : { filter: k })}
            className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${filter === k ? 'bg-brand text-white' : 'bg-white text-slate-600 ring-1 ring-line hover:text-ink'}`}>
            {FILTERS[k].label} <span className={`num ml-1 text-[15px] ${filter === k ? 'text-white/80' : 'text-slate-400'}`}>{counts[k] ?? 0}</span>
          </button>
        ))}
      </div>

      {!rows ? (
        <div className="space-y-2">{[0, 1, 2, 3].map(i => <Skeleton key={i} className="h-16" />)}</div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-slate-50 text-left text-xs font-medium text-muted">
              <tr>
                {['Candidat', 'Poste actuel', 'Parcours', 'Score CV', 'Entretien', 'Pré-qualification', 'Prochaine action'].map(h => (
                  <th key={h} className="px-3 py-3 first:pl-5" title={h === 'Score CV' ? `Trait vertical : seuil de pré-qualification (${Math.round(TH.yes * 100)}/100). Aucun critère indispensable ne doit être non satisfait.` : undefined}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map(c => (
                <tr key={c.id} onClick={() => nav.push(`/candidates/${c.id}`)} className="cursor-pointer border-t border-line align-middle transition-colors hover:bg-slate-50/80">
                  <td className={`border-l-4 py-3 pl-4 pr-3 ${laneClass(c)}`}>
                    <div className="flex items-center gap-3">
                      <Avatar name={c.name} size={36} />
                      <div className="min-w-0">
                        <div className="font-semibold text-ink">{c.name}{c.injection_flag && <span title="Tentative de manipulation détectée" className="ml-1.5 cursor-help text-amber-600">⚠</span>}</div>
                        <div className="truncate text-xs text-muted">{c.city || '—'}{c.email ? ` · ${c.email}` : ''}</div>
                        {c.status === 'failed' && <div className="max-w-[220px] text-xs text-rose-700">{c.error}</div>}
                      </div>
                    </div>
                  </td>
                  <td className="max-w-[150px] px-3 py-3">{c.title || '—'}</td>
                  <td className="px-3 py-3 text-xs"><div className="whitespace-nowrap">{c.years_experience ? `${Math.round(c.years_experience)} ans d'exp.` : '—'}</div><div className="text-muted">{c.education_level || '—'}</div></td>
                  <td className="px-3 py-3"><ScoreBar value={c.cv_score} label="Score CV" /></td>
                  <td className="whitespace-nowrap px-3 py-3">{c.interview_note != null ? <span className="num text-[19px]">{c.interview_note.toFixed(1)}<span className="text-xs text-muted">/10</span></span> : <span className="text-muted">—</span>}</td>
                  <td className="px-3 py-3"><PrequalBadge prequal={c.prequal} status={c.status} /></td>
                  <td className="px-3 py-3 pr-5">{nextAction(c)}</td>
                </tr>
              ))}
              {!shown.length && <tr><td colSpan={7}><Empty icon="🔍" title="Personne dans cette vue">{filter !== 'all' ? <button className="font-medium text-brand hover:underline" onClick={() => setParams({})}>Afficher tous les candidats</button> : 'Déposez des CV depuis la page de l\'offre.'}</Empty></td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
