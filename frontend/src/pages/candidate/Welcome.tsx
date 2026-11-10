import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api'
import { T, type Lang } from '../../lib/i18n'
import Shell from './Shell'

export default function Welcome() {
  const { token } = useParams()
  const nav = useNavigate()
  const [info, setInfo] = useState<any>(null)
  const [lang, setLang] = useState<Lang>('fr')
  const [ok, setOk] = useState(false)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api(`/public/interview/${token}`).then(i => {
      setInfo(i); setLang(i.language)
      if (i.status === 'ended' || i.status === 'scored') nav(`/i/${token}/done`, { replace: true })
    }).catch(() => setErr('invalid'))
  }, [token])

  const t = T[lang]
  if (err) return <Shell><p className="m-auto text-slate-400">{T.fr.invalid} / {T.en.invalid}</p></Shell>
  if (!info) return null
  if (info.expired) {
    return (
      <Shell>
        <div className="m-auto text-center">
          <div className="mx-auto mb-6 grid h-16 w-16 place-items-center rounded-full bg-amber-500/15 text-3xl ring-1 ring-amber-400/30">⏳</div>
          <h1 className="text-2xl font-semibold">{t.expired}</h1>
          <p className="mx-auto mt-3 max-w-sm text-slate-300">{t.expiredText}</p>
        </div>
      </Shell>
    )
  }

  const go = async (mode: 'voice' | 'text') => {
    setBusy(true)
    try {
      await api(`/public/interview/${token}/consent`, { method: 'POST', json: { language: lang, mode } })
      nav(`/i/${token}/interview`)
    } catch (e: any) { setErr(e.message); setBusy(false) }
  }

  return (
    <Shell>
      <div className="m-auto w-full py-6">
        <div className="mb-8 flex justify-end">
          <div className="inline-flex rounded-full bg-white/5 p-1 text-xs ring-1 ring-white/10">
            {(['fr', 'en'] as Lang[]).map(l => (
              <button key={l} onClick={() => setLang(l)} className={`rounded-full px-3 py-1 uppercase ${lang === l ? 'bg-white text-slate-900' : 'text-slate-400'}`}>{l}</button>
            ))}
          </div>
        </div>
        <p className="text-[15px] font-medium text-indigo-300">{t.title} · {info.job_title}</p>
        <h1 className="mt-2 font-display text-5xl font-semibold leading-none">{t.welcome}{info.first_name ? ` ${info.first_name}` : ''} 👋</h1>
        <p className="mt-3 text-slate-300">{t.intro}</p>
        {info.expires_label && <p className="mt-2 text-sm text-amber-300">⏳ {t.validUntil} {info.expires_label}</p>}

        <ul className="mt-8 space-y-3">
          {t.points.map(([e, s]) => (
            <li key={s} className="flex gap-3 rounded-xl bg-white/5 p-3.5 text-sm text-slate-300 ring-1 ring-white/10"><span>{e}</span><span>{s}</span></li>
          ))}
        </ul>

        <label className="mt-8 flex cursor-pointer gap-3 text-sm text-slate-300">
          <input type="checkbox" checked={ok} onChange={e => setOk(e.target.checked)} className="mt-1 h-4 w-4 accent-indigo-500" />
          <span>{t.consent}</span>
        </label>

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <button disabled={!ok || busy || !info.voice_available} onClick={() => go('voice')}
            className="rounded-xl bg-indigo-500 px-5 py-3.5 font-medium text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-40">
            🎙 {t.voice}
          </button>
          <button disabled={!ok || busy} onClick={() => go('text')}
            className="rounded-xl bg-white/10 px-5 py-3.5 font-medium text-white ring-1 ring-white/15 transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-40">
            ⌨ {t.text}
          </button>
        </div>
        {info.voice_available && <p className="mt-3 text-center text-xs text-slate-500">{t.micTip}</p>}
      </div>
    </Shell>
  )
}
