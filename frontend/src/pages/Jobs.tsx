import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Empty, PageHeader, Skeleton } from '../components/ui'
import { useUI } from '../lib/ui'

/** Yes / maybe / no as three lanes: the share of each outcome at a glance. */
function Lanes({ c }: { c: { yes: number; maybe: number; no: number } }) {
  const t = c.yes + c.maybe + c.no
  if (!t) return <div className="h-2 rounded-full bg-slate-100" />
  return (
    <div className="flex h-2 gap-[2px] overflow-hidden rounded-full bg-white" role="img" aria-label={`${c.yes} pré-qualifiés, ${c.maybe} à examiner, ${c.no} ne passent pas`}>
      {c.yes > 0 && <div className="bg-emerald-500" style={{ width: `${(c.yes / t) * 100}%` }} title={`${c.yes} pré-qualifiés`} />}
      {c.maybe > 0 && <div className="bg-amber-400" style={{ width: `${(c.maybe / t) * 100}%` }} title={`${c.maybe} à examiner`} />}
      {c.no > 0 && <div className="bg-rose-400" style={{ width: `${(c.no / t) * 100}%` }} title={`${c.no} ne passent pas`} />}
    </div>
  )
}

export default function Jobs() {
  const [jobs, setJobs] = useState<any[] | null>(null)
  const [open, setOpen] = useState(false)
  const [desc, setDesc] = useState('')
  const [busy, setBusy] = useState(false)
  const nav = useNavigate()
  const { toast } = useUI()
  useEffect(() => { api('/jobs').then(setJobs) }, [])

  const create = async () => {
    setBusy(true)
    try { const j = await api('/jobs', { method: 'POST', json: { description: desc } }); nav(`/jobs/${j.id}`) }
    catch (e: any) { toast(e.message, 'error'); setBusy(false) }
  }

  return (
    <div>
      <PageHeader title="Offres" subtitle="Collez une fiche de poste : l'IA en tire les critères, vous les ajustez, puis vous déposez les CV."
        actions={<button className="btn-primary" onClick={() => setOpen(true)}>Nouvelle offre</button>} />

      {!jobs ? (
        <div className="grid gap-4 md:grid-cols-2">{[0, 1].map(i => <Skeleton key={i} className="h-44" />)}</div>
      ) : jobs.length === 0 ? (
        <div className="card"><Empty icon="📋" title="Aucune offre pour l'instant">Créez votre première offre en collant la fiche de poste : les critères sont extraits en quelques secondes.
          <div className="mt-4"><button className="btn-primary" onClick={() => setOpen(true)}>Créer une offre</button></div></Empty></div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {jobs.map(j => (
            <Link key={j.id} to={`/jobs/${j.id}`} className="card group flex flex-col gap-4 p-5 transition-colors hover:border-brand/60">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm text-muted">{j.ref || 'Sans référence'}</div>
                  <h2 className="font-display text-[1.65rem] font-semibold leading-tight group-hover:text-brand">{j.title}</h2>
                </div>
                {j.todo_count > 0
                  ? <span className="badge shrink-0 bg-amber-100 text-amber-900">{j.todo_count} à traiter</span>
                  : j.candidates > 0 ? <span className="badge shrink-0 bg-emerald-50 text-emerald-800">À jour</span> : null}
              </div>
              <Lanes c={j.counts} />
              <div className="flex items-end justify-between text-sm text-muted">
                <span><span className="num text-[26px] text-ink">{j.candidates}</span> candidature{j.candidates > 1 ? 's' : ''}</span>
                <span className="flex gap-3 text-xs">
                  <span><b className="text-emerald-700">{j.counts.yes}</b> pré-qualifiés</span>
                  <span><b className="text-amber-700">{j.counts.maybe}</b> à examiner</span>
                  <span><b className="text-rose-700">{j.counts.no}</b> refus proposés</span>
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {open && (
        <div className="anim-fade fixed inset-0 z-40 grid place-items-center bg-ink/45 p-4" onMouseDown={e => { if (e.target === e.currentTarget && !busy) setOpen(false) }}>
          <div role="dialog" aria-modal="true" aria-label="Nouvelle offre" className="anim-rise float-shadow w-full max-w-2xl rounded-2xl bg-white p-6">
            <h2 className="font-display text-2xl font-semibold">Nouvelle offre</h2>
            <p className="mb-3 mt-1 text-sm text-muted">Collez la fiche de poste complète. Les critères seront extraits automatiquement et vous pourrez les modifier.</p>
            <textarea className="input h-72 text-[13px] leading-relaxed" autoFocus placeholder="Titre, missions, profil recherché…" value={desc} onChange={e => setDesc(e.target.value)} />
            <div className="mt-4 flex items-center justify-between">
              <span className="text-xs text-muted">{desc.trim().length < 40 ? 'Au moins 40 caractères.' : `${desc.trim().length} caractères`}</span>
              <div className="flex gap-2">
                <button className="btn-ghost" onClick={() => setOpen(false)} disabled={busy}>Annuler</button>
                <button className="btn-primary" onClick={create} disabled={busy || desc.trim().length < 40}>{busy ? 'Analyse en cours…' : 'Extraire les critères'}</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
