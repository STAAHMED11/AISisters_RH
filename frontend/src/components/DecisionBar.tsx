'use client'
import { useState } from 'react'
import { api } from '../api'

const PROPOSAL: Record<string, [string, string]> = {
  accept: ['Mérite un rendez-vous', 'bg-emerald-50 text-emerald-700 ring-emerald-200'],
  reject: ['Refuser', 'bg-rose-50 text-rose-700 ring-rose-200'],
  review: ['À vous de juger', 'bg-amber-50 text-amber-700 ring-amber-200'],
}

/** Always-visible decision bar: the recruiter reads the evidence and decides without scrolling back down. */
export default function DecisionBar({ c, onChange }: { c: any; onChange: () => void }) {
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const prop = PROPOSAL[c.ai_proposal] ?? PROPOSAL.review
  const against = (d: string) => (c.ai_proposal === 'accept' || c.ai_proposal === 'reject') && d !== c.ai_proposal

  const submit = async (d: 'accept' | 'reject') => {
    if (against(d) && comment.trim().length < 5) { setErr("Vous contredisez la proposition de l'IA : un commentaire est obligatoire."); return }
    setBusy(d); setErr('')
    try { await api(`/candidates/${c.id}/decision`, { method: 'POST', json: { decision: d, comment } }); onChange() }
    catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }
  return (
    <div className="fixed inset-x-0 bottom-0 z-20 float-shadow border-t border-line bg-white/95 backdrop-blur lg:left-60">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-6 py-3">
        <div className="text-sm"><span className="text-muted">IA :</span> <span className={`badge ring-1 ring-inset ${prop[1]}`}>{prop[0]}</span></div>
        <div className="min-w-[220px] flex-1">
          <input className="input" placeholder="Commentaire (obligatoire si vous contredisez l'IA)" value={comment} onChange={e => { setComment(e.target.value); setErr('') }} />
          {err && <div className="mt-1 text-xs text-rose-600">{err}</div>}
        </div>
        <button className="btn-good" disabled={!!busy} onClick={() => submit('accept')}>Retenir pour un rendez-vous</button>
        <button className="btn-danger" disabled={!!busy} onClick={() => submit('reject')}>Refuser</button>
      </div>
    </div>
  )
}
