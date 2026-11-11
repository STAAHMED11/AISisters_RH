'use client'
import { useState } from 'react'
import { api } from '../api'

export default function Login({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('')
    try { await api('/login', { method: 'POST', json: { name, password } }); onDone() }
    catch (e: any) { setErr(e.message); setBusy(false) }
  }
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-[#08293a] p-12 text-white lg:flex lg:flex-col lg:justify-between">
        {/* the sorting lanes, enlarged: the only decoration */}
        <svg className="absolute -right-24 bottom-10 w-[34rem] opacity-90" viewBox="0 0 320 120" aria-hidden>
          <rect x="0" y="0" width="300" height="26" rx="13" fill="#fff" fillOpacity=".92" />
          <rect x="0" y="47" width="210" height="26" rx="13" fill="#FFE45C" />
          <rect x="0" y="94" width="130" height="26" rx="13" fill="#fff" fillOpacity=".4" />
        </svg>
        <div className="font-display text-2xl font-semibold tracking-wide">Orvane <span className="text-base font-medium text-white/60">Recrutement</span></div>
        <div className="relative max-w-lg">
          <h1 className="font-display text-6xl font-semibold leading-[0.95]">Recrutez sur preuves.</h1>
          <ul className="mt-8 space-y-2 text-[17px] text-white/80">
            <li>Chaque CV lu, chaque verdict cité.</li>
            <li>Un pré-entretien à toute heure.</li>
            <li>La décision reste la vôtre.</li>
          </ul>
        </div>
        <div className="relative text-sm text-white/50">Groupe Orvane · outil interne</div>
      </section>
      <section className="grid place-items-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="mb-8 lg:hidden font-display text-3xl font-semibold text-brand">Orvane</div>
          <h2 className="font-display text-4xl font-semibold">Connexion</h2>
          <p className="mb-6 mt-1 text-[15px] text-muted">Espace réservé aux recruteurs.</p>
          <label className="mb-1 block text-sm font-medium" htmlFor="name">Votre prénom</label>
          <input id="name" className="input mb-4" autoComplete="given-name" value={name} onChange={e => setName(e.target.value)} placeholder="Sylvie" />
          <label className="mb-1 block text-sm font-medium" htmlFor="pw">Mot de passe</label>
          <input id="pw" className="input" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} />
          {err && <p role="alert" className="mt-3 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-800">{err}</p>}
          <button className="btn-primary mt-6 w-full !py-2.5" disabled={busy || !password}>{busy ? 'Connexion…' : 'Se connecter'}</button>
        </form>
      </section>
    </div>
  )
}
