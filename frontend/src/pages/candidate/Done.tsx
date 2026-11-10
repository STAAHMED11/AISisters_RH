import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../../api'
import { T } from '../../lib/i18n'
import Shell from './Shell'

export default function Done() {
  const { token } = useParams()
  const [lang, setLang] = useState<'fr' | 'en'>('fr')
  useEffect(() => { api(`/public/interview/${token}`).then(i => setLang(i.language)).catch(() => {}) }, [token])
  const t = T[lang]
  return (
    <Shell>
      <div className="m-auto text-center">
        <div className="mx-auto mb-6 grid h-16 w-16 place-items-center rounded-full bg-emerald-500/15 text-3xl ring-1 ring-emerald-400/30">✓</div>
        <h1 className="font-display text-4xl font-semibold">{t.doneTitle}</h1>
        <p className="mx-auto mt-3 max-w-sm text-slate-300">{t.doneText}</p>
      </div>
    </Shell>
  )
}
