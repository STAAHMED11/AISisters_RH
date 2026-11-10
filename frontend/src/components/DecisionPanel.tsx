import { useState } from 'react'
import { api } from '../api'

const PROPOSAL: Record<string, [string, string]> = {
  accept: ['Mérite un rendez-vous', 'bg-emerald-50 text-emerald-700 ring-emerald-200'],
  reject: ['Refuser', 'bg-rose-50 text-rose-700 ring-rose-200'],
  review: ['À examiner par vous', 'bg-amber-50 text-amber-700 ring-amber-200'],
}

export default function DecisionPanel({ c, onChange }: { c: any; onChange: () => void }) {
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const [pick, setPick] = useState<'accept' | 'reject' | ''>('')
  const prop = PROPOSAL[c.ai_proposal]
  const against = (d: string) => (c.ai_proposal === 'accept' || c.ai_proposal === 'reject') && d !== c.ai_proposal

  const submit = async (d: 'accept' | 'reject') => {
    if (against(d) && comment.trim().length < 5) { setPick(d); setErr('Vous allez à l\'encontre de la proposition de l\'IA : ajoutez un commentaire.'); return }
    setBusy(d); setErr('')
    try { await api(`/candidates/${c.id}/decision`, { method: 'POST', json: { decision: d, comment } }); setComment(''); setPick(''); onChange() }
    catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }
  const last = c.decisions?.[c.decisions.length - 1]

  return (
    <section className="card p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl font-semibold">Décision</h2>
          <p className="text-sm text-muted">L'IA propose, vous décidez. Toute décision contraire à la proposition est tracée avec votre commentaire.</p>
        </div>
        <div className="text-sm">Proposition de l'IA : <span className={`badge ring-1 ring-inset ${prop[1]}`}>{prop[0]}</span></div>
      </div>

      {last && (
        <div className="mb-3 rounded-lg bg-slate-50 p-3 text-sm">
          <b>{last.actor}</b> a décidé : <b>{last.decision === 'accept' ? '✓ Retenu pour un rendez-vous' : '✕ Refusé'}</b>
          {last.override && <span className="ml-2 badge bg-amber-100 text-amber-800">Contre la proposition de l'IA</span>}
          {last.comment && <span className="text-muted"> — « {last.comment} »</span>}
          <span className="ml-2 text-xs text-muted">{new Date(last.at).toLocaleString('fr-FR')}</span>
        </div>
      )}

      <textarea className="input mb-3 h-16" placeholder={pick || against('accept') || against('reject') ? 'Commentaire (obligatoire si vous contredisez l\'IA)' : 'Commentaire (optionnel)'}
        value={comment} onChange={e => setComment(e.target.value)} />
      {err && <p className="mb-2 text-sm text-rose-600">{err}</p>}
      <div className="flex flex-wrap gap-2">
        <button className="btn-good" disabled={!!busy} onClick={() => submit('accept')}>Retenir pour un rendez-vous</button>
        <button className="btn-danger" disabled={!!busy} onClick={() => submit('reject')}>Refuser</button>
      </div>
      <p className="mt-3 text-xs text-muted">Une réponse personnalisée est préparée dans l'onglet « Courriers » : vous la relisez avant tout envoi. Le candidat peut demander un réexamen humain.</p>
    </section>
  )
}
