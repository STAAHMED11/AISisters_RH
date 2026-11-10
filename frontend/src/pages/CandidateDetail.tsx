import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import DecisionBar from '../components/DecisionBar'
import DecisionPanel from '../components/DecisionPanel'
import InterviewPanel from '../components/InterviewPanel'
import { Avatar, Empty, PageSkeleton, PrequalBadge, ScoreBar, VerdictChip, isBusy } from '../components/ui'
import { describeEvent } from '../lib/events'

function Highlighted({ text, evals, active }: { text: string; evals: any[]; active: number | null }) {
  const parts = useMemo(() => {
    const spans = evals.filter(e => e.span).map(e => ({ s: e.span[0], e: e.span[1], id: e.criterion_id })).sort((a, b) => a.s - b.s)
    const out: { t: string; id?: number }[] = []
    let pos = 0
    for (const sp of spans) {
      if (sp.s < pos) continue
      if (sp.s > pos) out.push({ t: text.slice(pos, sp.s) })
      out.push({ t: text.slice(sp.s, sp.e), id: sp.id })
      pos = sp.e
    }
    out.push({ t: text.slice(pos) })
    return out
  }, [text, evals])
  return (
    <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
      {parts.map((p, i) => p.id
        ? <mark key={i} id={`q-${p.id}`} className={`rounded-sm px-0.5 text-ink ${active === p.id ? 'bg-mark' : 'bg-mark/45'}`}>{p.t}</mark>
        : <span key={i}>{p.t}</span>)}
    </pre>
  )
}

const DOT: Record<string, string> = { neutral: 'bg-slate-300', good: 'bg-emerald-500', bad: 'bg-rose-500', warn: 'bg-amber-500', info: 'bg-indigo-400' }
const ACTOR: Record<string, string> = { ia: 'IA', candidate: 'Candidat', system: 'Système' }

export default function CandidateDetail() {
  const { id } = useParams()
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') ?? 'synthese'
  const [c, setC] = useState<any>(null)
  const [active, setActive] = useState<number | null>(null)
  const [showAnon, setShowAnon] = useState(false)
  const timer = useRef<any>(undefined)

  const load = async () => {
    const d = await api(`/candidates/${id}`)
    setC(d)
    const iv = d.interview
    const ivBusy = iv && (iv.status === 'started' || (iv.status === 'ended' && !iv.synthesis?.error && !iv.synthesis?.empty && !iv.scores?.grades) || (iv.status === 'pending' && !iv.consented) || !iv.plan_ready)
    if (isBusy(d.status) || ivBusy) timer.current = setTimeout(load, 3000)
  }
  useEffect(() => { load(); return () => clearTimeout(timer.current) }, [id])

  if (!c) return <PageSkeleton />
  const reprocess = async () => { await api(`/candidates/${id}/reprocess`, { method: 'POST' }); load() }
  const go = (t: string) => setParams(t === 'synthese' ? {} : { tab: t }, { replace: true })
  const pick = (cid: number) => {
    setActive(cid)
    document.getElementById(`q-${cid}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
  const p = c.profile ?? {}
  const money = (v: number) => `$${v < 0.01 ? v.toFixed(4) : v.toFixed(3)}`
  const TABS: [string, string][] = [['synthese', 'Synthèse'], ['criteres', 'Critères et CV'], ['historique', `Historique (${c.history?.length ?? 0})`]]

  return (
    <div className={`space-y-5 ${c.status === 'screened' && !c.decision ? 'pb-24' : ''}`}>
      <Link to={`/jobs/${c.job.id}/candidates`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><span aria-hidden>←</span> Candidats · {c.job.title}</Link>

      <section className="card p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="flex min-w-0 items-start gap-4">
            <Avatar name={c.name} size={56} />
            <div className="min-w-0">
              <h1 className="font-display text-[2rem] font-semibold leading-none sm:text-4xl">{c.name}</h1>
              <p className="mt-1.5 text-[15px] text-muted">{p.headline || p.current_title}</p>
              <div className="mt-2.5 flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-600">
                {c.email && <a className="hover:text-brand" href={`mailto:${c.email}`}>{c.email}</a>}
                {c.phone && <a className="hover:text-brand" href={`tel:${c.phone}`}>{c.phone}</a>}
                {c.city && <span>{c.city}</span>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div><div className="mb-1 text-xs text-muted">Score CV</div><ScoreBar value={c.cv_score} /></div>
            {c.interview_note != null && <div><div className="mb-1 text-xs text-muted">Entretien</div><div className="num text-[22px]">{c.interview_note.toFixed(1)}<span className="text-sm text-muted">/10</span></div></div>}
            {c.cost && c.cost.total > 0 && (
              <Link to={`/costs/${c.job.id}`} title="Coût IA mesuré pour ce candidat (analyse du CV, pré-entretien, voix, courriers)" className="hidden sm:block">
                <div className="mb-1 text-xs text-muted">Coût IA</div><div className="num text-[22px]">{money(c.cost.total)}</div>
              </Link>
            )}
            <PrequalBadge prequal={c.prequal} status={c.status} />
          </div>
        </div>
      </section>

      {c.status === 'failed' && (
        <div className="card flex items-center justify-between gap-4 border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
          <span><b>Ce CV n'a pas pu être analysé.</b> {c.error}</span><button className="btn-ghost" onClick={reprocess}>Relancer l'analyse</button>
        </div>
      )}
      {c.injection_flag && (
        <div className="card border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
          <b>Ce CV contient une tentative de manipulation.</b> Le passage ci-dessous s'adresse à un système automatisé : il a été ignoré par l'évaluation et ne peut pas faire passer le candidat. À vous d'en juger.
          <ul className="mt-2 list-disc space-y-1 pl-5 italic">{c.injection_evidence.map((e: string, i: number) => <li key={i}>« {e} »</li>)}</ul>
          {c.hidden_text.length > 0 && <div className="mt-1.5 text-xs">Ce texte était invisible dans le fichier (blanc ou minuscule).</div>}
        </div>
      )}

      <div role="tablist" className="flex gap-1 border-b border-line">
        {TABS.map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => go(k)}
            className={`-mb-px border-b-2 px-4 py-2.5 text-[15px] font-medium transition-colors ${tab === k ? 'border-brand text-brand' : 'border-transparent text-muted hover:text-ink'}`}>{l}</button>
        ))}
      </div>

      {tab === 'synthese' && (
        <div className="space-y-5">
          {c.summary && (
            <section className="card p-5">
              <h2 className="mb-1.5 font-display text-xl font-semibold">Ce que l'IA retient du CV</h2>
              <p className="max-w-3xl text-[15px] leading-relaxed">{c.summary}</p>
              {c.interview_criteria.length > 0 && !c.interview && (
                <div className="mt-4 flex flex-wrap items-center gap-1.5 text-sm"><span className="text-muted">À vérifier en pré-entretien :</span>
                  {c.interview_criteria.map((k: any) => <span key={k.id} className="badge bg-slate-100 text-slate-700">{k.label}</span>)}</div>
              )}
            </section>
          )}
          {c.status === 'screened' && <InterviewPanel cid={c.id} iv={c.interview} canInvite email={c.email} onChange={load} />}
          {c.status === 'screened' && c.decisions?.length > 0 && <DecisionPanel c={c} onChange={load} />}
        </div>
      )}

      {tab === 'criteres' && (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
          <section className="card p-5">
            <h2 className="font-display text-xl font-semibold">Critères et preuves</h2>
            <p className="mb-4 text-sm text-muted">Chaque verdict cite le CV, et le code vérifie que la citation existe. Cliquez pour la retrouver dans le CV.</p>
            <div className="space-y-2.5">
              {c.evaluations.map((e: any) => (
                <button key={e.criterion_id} onClick={() => e.span && pick(e.criterion_id)}
                  className={`block w-full rounded-lg border p-3.5 text-left transition-colors ${active === e.criterion_id ? 'border-brand bg-indigo-50/60' : 'border-line hover:border-slate-300'}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-semibold">{e.label} <span className="ml-1 text-xs font-normal text-muted">{e.kind === 'must' ? 'indispensable' : 'souhaité'}</span></div>
                      <div className="text-xs text-muted">{e.description}</div>
                    </div>
                    <VerdictChip v={e.verdict} />
                  </div>
                  {e.quote && (
                    <blockquote className="mt-2.5 border-l-[3px] border-mark pl-3 text-sm italic text-slate-700">
                      « {e.quote} » {e.quote_verified && <span title="Citation vérifiée dans le CV" className="not-italic text-emerald-600">✓</span>}
                    </blockquote>
                  )}
                  <p className="mt-1.5 text-sm text-slate-600">{e.rationale}</p>
                </button>
              ))}
            </div>
            {c.interview_criteria.length > 0 && (
              <div className="mt-5 rounded-lg bg-slate-50 p-3.5 text-sm">
                <div className="mb-1.5 font-medium">Vérifiés à l'oral, pas au tri</div>
                <div className="flex flex-wrap gap-1.5">{c.interview_criteria.map((k: any) => <span key={k.id} className="badge bg-white ring-1 ring-line">{k.label}</span>)}</div>
              </div>
            )}
          </section>
          <section className="card p-5 lg:sticky lg:top-6 lg:self-start">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="font-display text-xl font-semibold">CV</h2>
              <button className="text-sm text-brand hover:underline" onClick={() => setShowAnon(!showAnon)}>{showAnon ? 'Voir le CV original' : "Voir ce que l'IA a lu"}</button>
            </div>
            {showAnon && <p className="mb-2 rounded-md bg-indigo-50 p-2.5 text-xs text-brand">Version anonymisée : nom, contacts, âge et adresse sont retirés avant l'évaluation.</p>}
            <div className="max-h-[72vh] overflow-auto rounded-lg bg-slate-50 p-4">
              {showAnon ? <pre className="whitespace-pre-wrap font-sans text-sm">{c.text_anon}</pre> : <Highlighted text={c.text} evals={c.evaluations} active={active} />}
            </div>
          </section>
        </div>
      )}

      {tab === 'historique' && (
        <section className="card p-5">
          <h2 className="font-display text-xl font-semibold">Historique du dossier</h2>
          <p className="mb-4 text-sm text-muted">Tout ce que l'IA, les recruteurs et le candidat ont fait sur ce dossier. Rien ne s'efface.</p>
          {!c.history?.length ? <Empty icon="🕘" title="Rien pour l'instant">Les actions apparaîtront ici dès qu'il y en aura.</Empty> : (
            <ol className="relative ml-2 space-y-1 border-l border-line pl-6">
              {c.history.map((e: any) => {
                const d = describeEvent(e)
                return (
                  <li key={e.id} className={`relative rounded-lg px-3 py-2 ${d.hot ? 'bg-amber-50 ring-1 ring-amber-200' : ''}`}>
                    <span className={`absolute -left-[31px] top-4 h-2.5 w-2.5 rounded-full ring-4 ring-white ${DOT[d.tone]}`} />
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                      <span className="w-28 shrink-0 text-xs tabular-nums text-muted">{new Date(e.ts).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                      <span className="badge bg-slate-100 text-slate-600">{ACTOR[e.actor_type] ?? e.actor}</span>
                      <span className="min-w-0 flex-1">{d.text}</span>
                    </div>
                  </li>
                )
              })}
            </ol>
          )}
        </section>
      )}

      {c.status === 'screened' && !c.decision && <DecisionBar c={c} onChange={load} />}
    </div>
  )
}
