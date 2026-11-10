import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { PageHeader, PageSkeleton } from '../components/ui'
import { useUI } from '../lib/ui'

type Crit = { id?: number; label: string; description: string; kind: 'must' | 'nice'; source: 'cv' | 'interview' }
const TONE: Record<string, string> = { warn: 'bg-amber-400', bad: 'bg-rose-500', info: 'bg-indigo-300' }

export default function JobDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const { confirm, toast } = useUI()
  const [job, setJob] = useState<any>(null)
  const [ov, setOv] = useState<any>(null)
  const [crit, setCrit] = useState<Crit[]>([])
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [drag, setDrag] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [open, setOpen] = useState<boolean | null>(null) // criteria panel: null = automatic
  const [showPost, setShowPost] = useState(false)

  const load = () => api(`/jobs/${id}`).then(j => { setJob(j); setCrit(j.criteria); setDirty(false) })
  const loadOv = () => api(`/jobs/${id}/overview`).then(setOv)
  useEffect(() => { load(); loadOv() }, [id])
  useEffect(() => {
    if (!ov?.counts?.busy) return
    const t = setTimeout(loadOv, 3000)
    return () => clearTimeout(t)
  }, [ov])

  const upload = async (files: FileList | File[]) => {
    const list = Array.from(files)
    if (!list.length) return
    setUploading(true)
    try {
      const fd = new FormData()
      list.forEach(f => fd.append('files', f))
      await api(`/jobs/${id}/candidates`, { method: 'POST', body: fd })
      nav(`/jobs/${id}/candidates`)
    } catch (e: any) { toast(e.message, 'error'); setUploading(false) }
  }

  const upd = (i: number, patch: Partial<Crit>) => { setCrit(c => c.map((x, k) => (k === i ? { ...x, ...patch } : x))); setDirty(true) }
  const save = async () => {
    setSaving(true)
    try {
      const j = await api(`/jobs/${id}/criteria`, { method: 'PUT', json: crit.map(({ id, label, description, kind, source }) => ({ id: id ?? 0, label, description, kind, source })) })
      setJob(j); setCrit(j.criteria); setDirty(false); loadOv(); toast('Critères enregistrés.', 'success')
    } catch (e: any) { toast(e.message, 'error') } finally { setSaving(false) }
  }
  const reextract = async () => {
    if (!(await confirm({ title: 'Ré-extraire les critères ?', text: 'Tous les critères actuels sont remplacés par ceux de la fiche de poste, et tous les CV sont ré-analysés.', confirmLabel: 'Ré-extraire', tone: 'danger' }))) return
    setSaving(true)
    try { const j = await api(`/jobs/${id}/re-extract`, { method: 'POST' }); setJob(j); setCrit(j.criteria); setDirty(false); loadOv(); toast('Critères ré-extraits ; les CV sont ré-analysés.', 'success') }
    catch (e: any) { toast(e.message, 'error') } finally { setSaving(false) }
  }
  const rescreen = async () => { await api(`/jobs/${id}/rescreen`, { method: 'POST' }); nav(`/jobs/${id}/candidates`) }
  const runTodo = async (t: any) => {
    if (t.action === 'reject-batch') {
      if (!(await confirm({ title: `Valider ${t.count} refus ?`, text: 'Un courrier personnalisé est préparé pour chaque candidat. Vous le relisez avant tout envoi.', confirmLabel: 'Valider les refus', tone: 'danger' }))) return
      await api(`/jobs/${id}/reject-batch`, { method: 'POST' })
      toast(`${t.count} refus validés ; les courriers sont à relire.`, 'success'); loadOv()
    } else if (t.link) nav(t.link)
  }

  if (!job) return <PageSkeleton />
  const isOpen = open ?? job.candidates === 0
  const must = crit.filter(c => c.kind === 'must').length
  const cvN = crit.filter(c => c.source === 'cv').length
  const F = ov?.funnel
  const funnel: [string, number | undefined, string][] = [
    ['Reçus', F?.received, `/jobs/${id}/candidates`],
    ['Analysés', F?.analyzed, `/jobs/${id}/candidates`],
    ['Pré-qualifiés', F?.prequalified, `/jobs/${id}/candidates?filter=pass`],
    ['Entretiens faits', F?.interviewed, `/jobs/${id}/candidates?filter=interviewed`],
    ['Retenus', F?.accepted, `/jobs/${id}/candidates?filter=accepted`],
    ['Réponses envoyées', F?.replied, `/jobs/${id}/outbox`],
  ]

  // plain render functions (not components): inputs must keep focus while typing
  const renderRow = (c: Crit, i: number) => (
    <div key={i} className="group flex items-start gap-3 rounded-lg px-3 py-2 hover:bg-slate-50">
      <div className="min-w-0 flex-1">
        <input className="w-full rounded bg-transparent px-1 py-0.5 font-semibold outline-none focus:bg-white focus:ring-2 focus:ring-brand/20" value={c.label} placeholder="Intitulé du critère" onChange={e => upd(i, { label: e.target.value })} />
        <input className="w-full rounded bg-transparent px-1 py-0.5 text-sm text-muted outline-none focus:bg-white focus:ring-2 focus:ring-brand/20" value={c.description} placeholder="Seuil ou précision (ex : 5 ans minimum, équipes de plus de 30 personnes)" onChange={e => upd(i, { description: e.target.value })} />
      </div>
      <button onClick={() => upd(i, { kind: c.kind === 'must' ? 'nice' : 'must' })}
        title={c.kind === 'must' ? 'Indispensable : un critère non satisfait empêche la pré-qualification. Cliquez pour le passer en « souhaité ».' : 'Souhaité : pèse moins dans le score. Cliquez pour le passer en « indispensable ».'}
        className={`mt-0.5 shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${c.kind === 'must' ? 'bg-rose-50 text-rose-800 ring-rose-200' : 'bg-slate-100 text-slate-600 ring-slate-200'}`}>
        {c.kind === 'must' ? 'Indispensable' : 'Souhaité'}
      </button>
      <button onClick={() => upd(i, { source: c.source === 'cv' ? 'interview' : 'cv' })} title={c.source === 'cv' ? "Déplacer vers « vérifiés à l'entretien »" : 'Déplacer vers « vérifiés sur le CV »'}
        className="mt-0.5 rounded p-1 text-muted opacity-0 transition hover:bg-slate-100 hover:text-ink focus:opacity-100 group-hover:opacity-100">⇄</button>
      <button onClick={() => { setCrit(crit.filter((_, k) => k !== i)); setDirty(true) }} title="Supprimer ce critère"
        className="mt-0.5 rounded p-1 text-muted opacity-0 transition hover:bg-rose-50 hover:text-rose-600 focus:opacity-100 group-hover:opacity-100">✕</button>
    </div>
  )
  const renderGroup = (source: 'cv' | 'interview', title: string, hint: string) => (
    <div>
      <div className="mb-1 px-3"><div className="font-display text-lg font-semibold">{title}</div><div className="text-xs text-muted">{hint}</div></div>
      {crit.map((c, i) => (c.source === source ? renderRow(c, i) : null))}
      <button className="mx-3 mt-1 text-sm font-medium text-brand hover:underline" onClick={() => { setCrit([...crit, { label: '', description: '', kind: 'nice', source }]); setDirty(true) }}>+ Ajouter un critère</button>
    </div>
  )

  return (
    <div className="space-y-6 pb-20">
      <PageHeader back={{ to: '/jobs', label: 'Offres' }} title={job.title} subtitle={`${job.ref ? job.ref + ' · ' : ''}${job.candidates} candidature${job.candidates > 1 ? 's' : ''}`}
        actions={<>
          <Link to={`/jobs/${id}/candidates`} className="btn-ghost">Candidats ({job.candidates})</Link>
          <Link to={`/jobs/${id}/outbox`} className="btn-ghost">Courriers</Link>
          <Link to={`/costs/${id}`} className="btn-ghost" title="Coût IA mesuré de cette offre">${job.cost_total != null ? (job.cost_total < 0.01 ? job.cost_total.toFixed(4) : job.cost_total.toFixed(2)) : '—'}</Link>
        </>} />

      <label onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files) }}
        className={`flex cursor-pointer flex-wrap items-center gap-4 rounded-xl border-2 border-dashed p-5 transition-colors ${drag ? 'border-brand bg-indigo-50' : 'border-slate-300 bg-white hover:border-brand/60'}`}>
        <input type="file" multiple className="hidden" accept=".pdf,.docx,.txt,.md,image/*" onChange={e => e.target.files && upload(e.target.files)} />
        <div className="grid h-12 w-12 place-items-center rounded-xl bg-indigo-50 text-2xl">📄</div>
        <div className="min-w-0 flex-1">
          <div className="font-display text-xl font-semibold">{uploading ? 'Envoi en cours…' : 'Déposer des CV'}</div>
          <div className="text-sm text-muted">Glissez un ou plusieurs CV ici (PDF, Word, texte ou image). Chacun est lu en entier et confronté aux critères en quelques secondes.</div>
        </div>
        <span className="btn-primary">Choisir des fichiers</span>
      </label>

      {F && (
        <section className="card grid grid-cols-2 divide-dashed divide-slate-300 sm:grid-cols-3 lg:grid-cols-6 lg:divide-x" aria-label="Avancement des candidatures">
          {funnel.map(([label, n, link]) => (
            <Link key={label} to={link} className="group px-5 py-4 transition-colors hover:bg-slate-50 first:rounded-l-xl last:rounded-r-xl">
              <div className="num text-[2.6rem] text-ink group-hover:text-brand">{n ?? 0}</div>
              <div className="mt-1 text-sm text-muted">{label}</div>
              {F.received > 0 && <div className="mt-0.5 text-xs text-slate-400">{Math.round(((n ?? 0) / F.received) * 100)} % des reçus</div>}
            </Link>
          ))}
        </section>
      )}

      {ov && (
        <section className="card p-5">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-2xl font-semibold">À faire</h2>
            {ov.todo_count > 0 && <span className="badge bg-amber-100 text-amber-900">{ov.todo_count} à traiter</span>}
          </div>
          {job.stale > 0 && !dirty && (
            <div className="mb-3 flex flex-wrap items-center gap-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
              <span className="min-w-0 flex-1">Les critères ont changé depuis l'analyse de <b>{job.stale} CV</b> : leurs verdicts ne sont plus à jour.</span>
              <button className="btn-primary" onClick={rescreen}>Ré-analyser {job.stale} CV</button>
            </div>
          )}
          {ov.todo.length === 0 && !job.stale ? (
            <div className="flex items-center gap-3 rounded-lg bg-emerald-50 p-4 text-[15px] text-emerald-900"><span className="grid h-7 w-7 place-items-center rounded-full bg-emerald-500 text-white" aria-hidden>✓</span> Tout est à jour. {F?.received ? '' : 'Déposez des CV pour commencer.'}</div>
          ) : (
            <ul className="divide-y divide-line">
              {ov.todo.map((t: any) => (
                <li key={t.key} className="flex items-center gap-4 py-3">
                  <span className={`h-9 w-1 shrink-0 rounded-full ${TONE[t.tone] ?? 'bg-slate-300'} ${t.key === 'busy' ? 'animate-pulse' : ''}`} />
                  <span className="num w-9 text-right text-[28px]">{t.count}</span>
                  <span className="min-w-0 flex-1 text-[15px]">{t.label}</span>
                  <button className={t.tone === 'info' ? 'btn-ghost !py-1.5' : 'btn-primary !py-1.5'} onClick={() => runTodo(t)}>{t.cta}</button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-3 p-5">
          <div>
            <h2 className="font-display text-2xl font-semibold">Critères de sélection</h2>
            <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs">
              <span className="badge bg-rose-50 text-rose-800 ring-1 ring-inset ring-rose-200">{must} indispensables</span>
              <span className="badge bg-slate-100 text-slate-600">{crit.length - must} souhaités</span>
              <span className="badge bg-white text-muted ring-1 ring-inset ring-line">{cvN} vérifiés sur le CV</span>
              <span className="badge bg-white text-muted ring-1 ring-inset ring-line">{crit.length - cvN} à l'entretien</span>
            </div>
          </div>
          <div className="flex gap-2">
            {isOpen && <button className="btn-ghost" onClick={reextract} disabled={saving}>Ré-extraire depuis la fiche</button>}
            <button className="btn-ghost" onClick={() => setOpen(!isOpen)}>{isOpen ? 'Réduire' : 'Modifier les critères'}</button>
          </div>
        </div>
        {isOpen && (
          <div className="space-y-6 border-t border-line p-3 pt-4">
            <p className="px-3 text-sm text-muted">Un critère <b className="text-ink">indispensable</b> non satisfait empêche la pré-qualification ; les critères <b className="text-ink">souhaités</b> pèsent moins dans le score. Survolez une ligne pour la déplacer (⇄) ou la supprimer.</p>
            {renderGroup('cv', 'Vérifiés sur le CV', 'Comptent dans le score de pré-qualification')}
            {renderGroup('interview', "Vérifiés à l'entretien", "Jamais pénalisés au tri : l'assistante les vérifie à l'oral")}
          </div>
        )}
      </section>

      <section className="card p-5">
        <button className="flex w-full items-center justify-between text-left" onClick={() => setShowPost(!showPost)} aria-expanded={showPost}>
          <span className="font-display text-2xl font-semibold">Fiche de poste</span><span className="text-sm font-medium text-brand">{showPost ? 'Masquer' : 'Afficher'}</span>
        </button>
        {showPost && <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-4 font-sans text-sm leading-relaxed">{job.description}</pre>}
      </section>

      {dirty && (
        <div className="anim-rise float-shadow fixed inset-x-0 bottom-5 z-30 mx-auto flex w-fit items-center gap-3 rounded-full border border-line bg-white px-5 py-2.5">
          <span className="text-sm">Modifications non enregistrées</span>
          <button className="btn-ghost !py-1" onClick={load} disabled={saving}>Annuler</button>
          <button className="btn-primary !py-1" onClick={save} disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</button>
        </div>
      )}
    </div>
  )
}
