import { lazy, Suspense, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api'
import Shell from './Shell'
import TextInterview from './TextInterview'
const VoiceInterview = lazy(() => import('./VoiceInterview'))

export default function Interview() {
  const { token } = useParams()
  const nav = useNavigate()
  const [info, setInfo] = useState<any>(null)
  const [mode, setMode] = useState<'voice' | 'text' | ''>('')

  useEffect(() => {
    api(`/public/interview/${token}`).then(i => {
      if (!i.consented) nav(`/i/${token}`, { replace: true })
      else if (i.status === 'ended' || i.status === 'scored') nav(`/i/${token}/done`, { replace: true })
      else { setInfo(i); setMode(i.mode === 'voice' && i.voice_available ? 'voice' : 'text') }
    }).catch(() => nav(`/i/${token}`, { replace: true }))
  }, [token])
  if (!info) return null
  const done = () => nav(`/i/${token}/done`, { replace: true })
  return (
    <Shell wide>
      {mode === 'voice'
        ? <Suspense fallback={null}><VoiceInterview token={token!} lang={info.language} onDone={done} onFallbackText={() => setMode('text')} /></Suspense>
        : <TextInterview token={token!} lang={info.language} onDone={done} />}
    </Shell>
  )
}
