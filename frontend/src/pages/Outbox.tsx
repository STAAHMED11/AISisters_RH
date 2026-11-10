import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { Empty, PageHeader, PageSkeleton } from '../components/ui'
import { useUI } from '../lib/ui'

const KIND: Record<string, [string, string]> = {
  invite: ['Invitation', 'bg-indigo-50 text-brand'], acceptance: ['Rendez-vous', 'bg-emerald-50 text-emerald-800'], rejection: ['Refus', 'bg-rose-50 text-rose-800'],
}

function MailSetup() {
  const { toast } = useUI()
  const [st, setSt] = useState<any>(null)
  const [to, setTo] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { api('/mail-status').then(setSt).catch(() => {}) }, [])
  if (!st) return null
  const test = async () => {
    setBusy(true)
    try { const r = await api('/mail-test', { method: 'POST', json: { to } }); toast(r.transport === 'smtp' ? `E-mail de test envoyé à ${to}.` : "Test simulé : aucun serveur d'e-mail n'est configuré.", r.transport === 'smtp' ? 'success' : 'info') }
    catch (e: any) { toast(e.message, 'error') } finally { setBusy(false) }
  }
  return (
    <section className={`card flex flex-wrap items-center gap-x-8 gap-y-4 p-5 ${st.smtp ? '' : 'border-amber-300 bg-amber-50/50'}`}>
      <div className="min-w-[16rem] flex-1">
        <div className="flex items-center gap-2 font-display text-xl font-semibold">
          <span className={`h-2.5 w-2.5 rounded-full ${st.smtp ? 'bg-emerald-500' : 'bg-amber-500'}`} />
          {st.smtp ? `Envoi réel via ${st.host}` : 'Envoi simulé'}
        </div>
        <p className="mt-1 text-sm text-slate-600">
          {st.smtp
            ? <>Expéditeur : <b>{st.from || 'non précisé'}</b>. Les invitations et les réponses partent réellement chez les candidats.</>
            : <>Aucun serveur d'e-mail n'est configuré : rien ne part chez les candidats. Renseignez <code className="rounded bg-white px-1">SMTP_HOST</code>, <code className="rounded bg-white px-1">SMTP_USER</code> et <code className="rounded bg-white px-1">SMTP_PASSWORD</code> (voir le README).</>}
        </p>
        <p className="mt-1 text-sm text-slate-600">Invitations automatiques aux pré-qualifiés : <b>{st.auto_send_invites ? 'activées' : 'désactivées'}</b> <span className="text-muted">(<code>AUTO_SEND_INVITES</code>)</span></p>
      </div>
      <form className="flex items-end gap-2" onSubmit={e => { e.preventDefault(); test() }}>
        <label className="flex flex-col text-sm font-medium">Tester l'envoi
          <input className="input mt-1 w-64 font-normal" type="email" required placeholder="votre@adresse.fr" value={to} onChange={e => setTo(e.target.value)} />
        </label>
        <button className="btn-ghost" disabled={busy || !to}>{busy ? 'Envoi…' : 'Envoyer un test'}</button>
      </form>
    </section>
  )
}

export default function Outbox() {
  const { id } = useParams()
  const { confirm, toast } = useUI()
  const [data, setData] = useState<any>(null)
  const [open, setOpen] = useState<number | null>(null)
  const [edit, setEdit] = useState<{ subject: string; body: string }>({ subject: '', body: '' })
  const [busy, setBusy] = useState(false)

  const load = () => api(`/jobs/${id}/outbox`).then(setData)
  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t) }, [id])
  if (!data) return <PageSkeleton />
  const drafts = data.messages.filter((m: any) => m.status !== 'sent')
  const sent = data.messages.filter((m: any) => m.status === 'sent')
  const s = data.stats

  const send = async (m: any) => {
    setBusy(true)
    try {
      if (open === m.id) await api(`/messages/${m.id}`, { method: 'PUT', json: edit })
      const r = await api(`/messages/${m.id}/send`, { method: 'POST' })
      setOpen(null); toast(r.transport === 'mock' ? `Courrier à ${m.name} marqué comme envoyé (simulé).` : `Courrier envoyé à ${m.name}.`, 'success')
    } catch (e: any) { toast(`${m.name} : ${e.message}`, 'error') }
    setBusy(false); load()
  }
  const sendAll = async () => {
    if (!(await confirm({ title: `Envoyer ${drafts.length} courrier${drafts.length > 1 ? 's' : ''} ?`, text: 'Chaque message est approuvé puis envoyé tel que vous le voyez dans la liste.', confirmLabel: 'Approuver et envoyer' }))) return
    setBusy(true)
    const r = await api(`/jobs/${id}/outbox/send-all`, { method: 'POST' })
    setBusy(false)
    if (r.failed?.length) toast(`${r.sent} envoyé(s), ${r.failed.length} échec(s) : ` + r.failed.map((f: any) => `${f.name} (${f.error})`).join(' ; '), 'error')
    else toast(`${r.sent} courrier(s) envoyé(s).`, 'success')
    load()
  }
  const del = async (m: any) => { await api(`/messages/${m.id}`, { method: 'DELETE' }); toast('Brouillon supprimé.', 'info'); load() }
  const toggle = (m: any) => { if (open === m.id) setOpen(null); else { setOpen(m.id); setEdit({ subject: m.subject, body: m.body }) } }

  return (
    <div className="space-y-6">
      <PageHeader back={{ to: `/jobs/${id}`, label: 'Offre' }} title="Courriers"
        subtitle="Chaque candidat reçoit une réponse personnalisée. Vous la relisez avant tout envoi."
        actions={<button className="btn-primary" disabled={!drafts.length || busy} onClick={sendAll}>Tout approuver et envoyer ({drafts.length})</button>} />

      <MailSetup />

      <div className="grid gap-3 sm:grid-cols-4">
        {[['Candidats', s.candidates, ''], ['Décisions prises', s.decided, ''], ['Réponses envoyées', s.replied, 'text-emerald-700'], ['Décidés, sans réponse', s.awaiting_reply, s.awaiting_reply ? 'text-amber-700' : '']].map(([l, v, c]) => (
          <div key={l as string} className="card px-5 py-4"><div className={`num text-[2.4rem] ${c}`}>{v}</div><div className="mt-1 text-sm text-muted">{l}</div></div>
        ))}
      </div>
      {s.rejections_to_validate > 0 && <div className="card border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">{s.rejections_to_validate} refus proposés par l'IA attendent votre validation dans la liste des <Link className="font-medium underline" to={`/jobs/${id}/candidates?filter=fail`}>candidats</Link>.</div>}

      <section>
        <h2 className="mb-3 font-display text-2xl font-semibold">À relire et envoyer ({drafts.length})</h2>
        <div className="space-y-2.5">
          {drafts.map((m: any) => (
            <div key={m.id} className="card p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <button className="flex min-w-0 flex-1 items-center gap-3 text-left" onClick={() => toggle(m)}>
                  <span className={`badge ${KIND[m.kind]?.[1]}`}>{KIND[m.kind]?.[0]}</span>
                  <span className="whitespace-nowrap font-semibold">{m.name}</span>
                  <span className="truncate text-sm text-muted">{m.subject}</span>
                </button>
                <div className="flex shrink-0 gap-2">
                  <button className="btn-ghost !px-3 !py-1.5" onClick={() => toggle(m)}>{open === m.id ? 'Fermer' : 'Relire ou modifier'}</button>
                  <button className="btn-primary !px-3 !py-1.5" disabled={busy} onClick={() => send(m)}>Approuver et envoyer</button>
                </div>
              </div>
              {open === m.id && (
                <div className="mt-3 space-y-2 border-t border-line pt-3">
                  <div className="text-xs text-muted">À : {m.email || 'aucune adresse trouvée dans le CV'} · langue : {m.language}</div>
                  <input className="input font-semibold" value={edit.subject} onChange={e => setEdit({ ...edit, subject: e.target.value })} aria-label="Objet" />
                  <textarea className="input h-56 leading-relaxed" value={edit.body} onChange={e => setEdit({ ...edit, body: e.target.value })} aria-label="Message" />
                  <button className="text-sm text-rose-700 hover:underline" onClick={() => del(m)}>Supprimer ce brouillon</button>
                </div>
              )}
            </div>
          ))}
          {!drafts.length && <div className="card"><Empty icon="✉️" title="Aucun courrier en attente">Les invitations et les réponses aux candidats apparaissent ici dès qu'elles sont préparées.</Empty></div>}
        </div>
      </section>

      {sent.length > 0 && (
        <section>
          <h2 className="mb-3 font-display text-2xl font-semibold">Envoyés ({sent.length})</h2>
          <div className="card divide-y divide-line text-sm">
            {sent.map((m: any) => (
              <div key={m.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                <span className={`badge ${KIND[m.kind]?.[1]}`}>{KIND[m.kind]?.[0]}</span>
                <span className="font-semibold">{m.name}</span><span className="min-w-0 flex-1 truncate text-muted">{m.subject}</span>
                <span className={`badge ${m.transport === 'mock' ? 'bg-slate-100 text-slate-600' : 'bg-emerald-50 text-emerald-800'}`}>{m.transport === 'mock' ? 'simulé' : 'envoyé'}</span>
                <span className="whitespace-nowrap text-xs text-muted">{m.sent_at && new Date(m.sent_at).toLocaleString('fr-FR')}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
