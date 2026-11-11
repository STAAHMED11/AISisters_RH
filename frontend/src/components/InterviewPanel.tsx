'use client'
import { useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { api } from '../api'
import { useUI } from '../lib/ui'

const STATUS: Record<string, string> = {
  pending: 'Lien prêt — en attente du candidat', started: 'Entretien en cours', ended: 'Terminé — analyse en cours…', scored: 'Analysé',
}
const RECO: Record<string, [string, string]> = {
  invite: ['Mérite un rendez-vous', 'bg-emerald-50 text-emerald-700 ring-emerald-200'],
  hold: ['À examiner', 'bg-amber-50 text-amber-700 ring-amber-200'],
  decline: ['Ne correspond pas', 'bg-rose-50 text-rose-700 ring-rose-200'],
}
const GRADE_CLS = ['bg-rose-100 text-rose-700', 'bg-amber-100 text-amber-700', 'bg-sky-100 text-sky-700', 'bg-emerald-100 text-emerald-700']

function Quote({ q }: { q: string }) {
  return q ? <blockquote className="mt-1 border-l-2 border-yellow-300 pl-2.5 text-sm italic text-slate-700">« {q} » <span className="not-italic text-emerald-600" title="Citation vérifiée dans la transcription">✓</span></blockquote> : null
}

export default function InterviewPanel({ cid, iv, canInvite, email, onChange }: { cid: number; iv: any; canInvite: boolean; email?: string; onChange: () => void }) {
  const { confirm, toast } = useUI()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [copied, setCopied] = useState(false)
  const [showTr, setShowTr] = useState(false)
  const [showPlan, setShowPlan] = useState(false)
  const [sending, setSending] = useState(false)
  const sendInvite = async (extend: boolean) => {
    setSending(true); setErr('')
    try {
      const r = await api(`/candidates/${cid}/invite/send`, { method: 'POST', json: { extend } })
      toast(r.invite?.transport === 'mock' ? "Invitation préparée (envoi simulé : aucun serveur d'e-mail configuré)." : `Invitation envoyée à ${r.invite?.to ?? 'le candidat'}.`, r.invite?.transport === 'mock' ? 'info' : 'success')
      onChange()
    } catch (e: any) { setErr(e.message); toast(e.message, 'error') } finally { setSending(false) }
  }
  const emailNow = async () => {
    if (!(await confirm({ title: "Envoyer l'invitation ?", text: `Le lien du pré-entretien est envoyé à ${email || 'ce candidat'}, avec sa date limite.`, confirmLabel: 'Envoyer' }))) return
    sendInvite(false)
  }

  const invite = async () => {
    setBusy(true); setErr('')
    try { await api(`/candidates/${cid}/invite`, { method: 'POST' }); onChange(); toast('Lien généré. Copiez-le ou envoyez-le par e-mail.', 'success') }
    catch (e: any) { setErr(e.message); toast(e.message, 'error') } finally { setBusy(false) }
  }
  const copy = async () => { await navigator.clipboard.writeText(iv.link); setCopied(true); toast('Lien copié.', 'success'); setTimeout(() => setCopied(false), 1500) }

  if (!iv) {
    return (
      <section className="card flex flex-wrap items-center justify-between gap-5 p-5">
        <div className="min-w-[16rem] flex-1">
          <h2 className="font-display text-2xl font-semibold">Pré-entretien</h2>
          <p className="max-w-xl text-[15px] text-muted">Le candidat répond à l'oral ou à l'écrit, quand il veut. Le lien est prêt tout de suite ; le plan de questions se prépare pendant ce temps. Choisissez comment lui donner accès.</p>
          {err && <p className="mt-1 text-sm text-rose-700">{err}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost" onClick={invite} disabled={busy || sending || !canInvite}>{busy ? 'Génération…' : 'Générer le lien'}</button>
          <button className="btn-primary" onClick={emailNow} disabled={busy || sending || !canInvite || !email} title={email ? undefined : "Aucune adresse e-mail trouvée dans le CV"}>{sending ? 'Envoi…' : "Envoyer l'invitation par e-mail"}</button>
        </div>
      </section>
    )
  }

  const s = iv.synthesis ?? {}
  const sc = iv.scores ?? {}
  const reco = RECO[s.recommendation]
  return (
    <section className="card space-y-5 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-2xl font-semibold">Pré-entretien</h2>
          <p className="text-sm text-muted">{STATUS[iv.status] ?? iv.status}{iv.mode ? ` · ${iv.mode === 'voice' ? 'vocal' : 'écrit'}` : ''} · {iv.language === 'en' ? 'English' : 'français'}</p>
        </div>
        {iv.status === 'scored' && (
          <div className="flex items-center gap-3">
            {reco && <span className={`badge ring-1 ring-inset ${reco[1]}`}>{reco[0]}</span>}
            <div className="text-right">
              {sc.note != null
                ? <div className="num text-[2.6rem]">{sc.note.toFixed(1)}<span className="text-base text-muted">/10</span></div>
                : <div className="num text-[2.6rem] text-muted">—</div>}
              <div className="text-xs text-muted">
                {sc.coverage ? `${sc.coverage.assessed} critère${sc.coverage.assessed > 1 ? 's' : ''} sur ${sc.coverage.total} évalué${sc.coverage.assessed > 1 ? 's' : ''}` : "note d'entretien"}
              </div>
            </div>
          </div>
        )}
      </div>

      {!iv.plan_ready && iv.status === 'pending' && <div className="animate-pulse text-sm text-brand">Plan de questions en préparation…</div>}
      {iv.plan?.questions?.length > 0 && (
        <div>
          <button className="text-sm text-brand hover:underline" onClick={() => setShowPlan(!showPlan)}>
            {showPlan ? 'Masquer' : 'Voir'} les questions préparées par l'IA ({iv.plan.questions.length})
          </button>
          {showPlan && (
            <ol className="mt-3 space-y-2 rounded-lg bg-slate-50 p-4 text-sm">
              {iv.plan.questions.map((q: any, i: number) => (
                <li key={i} className="flex gap-3">
                  <span className="mt-0.5 w-5 shrink-0 text-muted">{i + 1}.</span>
                  <div><span className="mr-2 badge bg-white ring-1 ring-line">{({ logistics: 'logistique', verify: 'vérifier le CV', probe: 'zone d\'ombre', closing: 'clôture' } as any)[q.kind] ?? q.kind}</span>{q.question}
                    <div className="text-xs text-muted">À écouter : {q.listen_for}</div></div>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}

      {iv.status !== 'scored' && iv.status !== 'ended' && iv.invite && (
        <div className={`rounded-lg border p-3 text-sm ${iv.expired ? 'border-rose-300 bg-rose-50' : 'border-line'}`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-medium">✉ Invitation par e-mail {iv.expired && <span className="ml-2 badge bg-rose-100 text-rose-700">Lien expiré</span>}</div>
              <div className="text-muted">
                {iv.invite.state === 'sent'
                  ? <>Envoyée à <b>{iv.invite.to}</b> le {new Date(iv.invite.sent_at).toLocaleString('fr-FR')}{iv.invite.transport === 'mock' && ' (simulée)'}</>
                  : <>À envoyer à <b>{iv.invite.to || '— aucune adresse trouvée dans le CV'}</b></>}
                {iv.expires_label && <> · lien valable jusqu'au <b>{iv.expires_label}</b></>}
              </div>
            </div>
            <div className="flex gap-2">
              {iv.invite.state !== 'sent' && <button className="btn-primary" disabled={sending || !iv.invite.to} onClick={() => sendInvite(false)}>{sending ? 'Envoi…' : "✉ Envoyer l'invitation"}</button>}
              {(iv.invite.state === 'sent' || iv.expired) && <button className="btn-ghost" disabled={sending || !iv.invite.to} onClick={() => sendInvite(true)}>↻ Renvoyer et prolonger</button>}
            </div>
          </div>
          {!iv.invite.smtp && <div className="mt-2 text-xs text-amber-700">⚠ Aucun serveur d'e-mail configuré (SMTP_* dans .env) : l'envoi est simulé. Le lien reste copiable ci-dessous.</div>}
          {err && <div className="mt-2 text-xs text-rose-600">{err}</div>}
        </div>
      )}

      {iv.status !== 'scored' && iv.status !== 'ended' && (
        <div className="flex flex-wrap items-center gap-5 rounded-lg bg-slate-50 p-4">
          <div className="rounded-lg bg-white p-2 ring-1 ring-line"><QRCodeSVG value={iv.link} size={92} /></div>
          <div className="min-w-0 flex-1 space-y-2">
            <div className="text-sm font-medium">Lien unique du candidat (sans compte)</div>
            <div className="flex gap-2"><input readOnly value={iv.link} className="input font-mono text-xs" onFocus={e => e.target.select()} /><button className="btn-ghost" onClick={copy}>{copied ? 'Copié ✓' : 'Copier'}</button><a className="btn-ghost" href={iv.link} target="_blank">Ouvrir</a></div>
            <div className="text-xs text-muted">Scannez le QR code pour passer l'entretien sur mobile. Le lien peut aussi être envoyé depuis l'onglet Courriers.</div>
          </div>
        </div>
      )}
      {iv.status === 'ended' && !s.error && !s.empty && <div className="animate-pulse text-sm text-brand">Analyse de la transcription en cours…</div>}
      {(s.error || s.empty) && (
        <div className="flex items-center justify-between rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
          <span>{s.empty ? 'Le candidat n\'a rien répondu.' : 'Analyse impossible : ' + s.error}</span>
          {!s.empty && <button className="btn-ghost" onClick={async () => { await api(`/candidates/${cid}/rescore`, { method: 'POST' }); onChange() }}>Relancer</button>}
        </div>
      )}

      {iv.status === 'scored' && (
        <>
          {s.manipulation && <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">⚠️ Le candidat a tenté de manipuler l'assistante pendant l'échange. Les notes n'en tiennent pas compte, et l'IA ne propose pas de le retenir : c'est à vous de juger.</div>}
          {sc.note == null && sc.coverage && <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">Entretien trop court pour une note fiable : {sc.coverage.assessed} critère(s) évalué(s) sur {sc.coverage.total}. Lisez la transcription, ou renvoyez une invitation.</div>}
          <p className="text-[15px] leading-relaxed">{s.headline}</p>

          {(s.blockers?.length > 0 || s.discrepancies?.length > 0) && (
            <div className="space-y-2">
              {s.blockers.map((b: string, i: number) => <div key={i} className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800"><b>Point bloquant ·</b> {b}</div>)}
              {s.discrepancies.map((b: string, i: number) => <div key={i} className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900"><b>Écart CV / entretien ·</b> {b}</div>)}
            </div>
          )}

          <div className="grid gap-5 md:grid-cols-2">
            <div><h3 className="mb-2 text-sm font-semibold text-emerald-700">Points forts</h3>
              <ul className="space-y-2">{s.strengths.map((x: any, i: number) => <li key={i} className="text-sm">{x.text}<Quote q={x.quote} /></li>)}</ul></div>
            <div><h3 className="mb-2 text-sm font-semibold text-amber-700">Doutes</h3>
              <ul className="space-y-2">{s.doubts.map((x: any, i: number) => <li key={i} className="text-sm">{x.text}<Quote q={x.quote} /></li>)}</ul></div>
          </div>
          <div><h3 className="mb-2 text-sm font-semibold">À creuser avec le manager</h3>
            <ul className="list-disc space-y-1 pl-5 text-sm">{s.probes.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></div>

          <div><h3 className="mb-2 text-sm font-semibold">Fiche logistique</h3>
            <div className="divide-y divide-line rounded-lg border border-line text-sm">
              {s.logistics.map((l: any, i: number) => <div key={i} className="grid grid-cols-[180px_1fr] gap-3 px-3 py-2"><span className="text-muted">{l.label}</span><span>{l.answer}</span></div>)}
            </div></div>

          <div><h3 className="mb-2 text-sm font-semibold">Notes par critère (0–3)</h3>
            <div className="space-y-2">
              {sc.grades.map((g: any) => (
                <div key={g.criterion_id} className="rounded-lg border border-line p-3">
                  <div className="flex items-center justify-between gap-3"><span className="text-sm font-medium">{g.label}</span>
                    {g.grade < 0 ? <span className="badge bg-slate-100 text-slate-500">Non abordé</span> : <span className={`badge ${GRADE_CLS[g.grade]}`}>{g.grade}/3</span>}</div>
                  <Quote q={g.quote} />
                  <p className="mt-1 text-sm text-slate-600">{g.rationale}</p>
                </div>
              ))}
            </div></div>
        </>
      )}

      {iv.transcript?.length > 0 && (
        <div>
          <button className="text-sm text-brand hover:underline" onClick={() => setShowTr(!showTr)}>{showTr ? 'Masquer' : 'Voir'} la transcription ({iv.transcript.length} messages)</button>
          {showTr && (
            <div className="mt-3 max-h-96 space-y-2 overflow-auto rounded-lg bg-slate-50 p-4 text-sm">
              {iv.transcript.map((t: any, i: number) => (
                <p key={i}><b className={t.role === 'agent' ? 'text-brand' : 'text-slate-800'}>{t.role === 'agent' ? 'Camille' : 'Candidat'} · </b>{t.text}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
