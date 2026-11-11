'use client'
import { useEffect, useState } from 'react'
import dynamic from 'next/dynamic'
import { useRouter, useParams } from 'next/navigation'
import { api } from '../../api'
import Shell from './Shell'
import TextInterview from './TextInterview'
// Browser-only (microphone, WebSocket): never rendered on the server, loaded on demand.
const VoiceInterview = dynamic(() => import('./VoiceInterview'), { ssr: false })

export default function Interview() {
  const { token } = useParams<{ token: string }>()
  const nav = useRouter()
  const [info, setInfo] = useState<any>(null)
  const [mode, setMode] = useState<'voice' | 'text' | ''>('')

  useEffect(() => {
    api(`/public/interview/${token}`).then(i => {
      if (!i.consented) nav.replace(`/i/${token}`)
      else if (i.status === 'ended' || i.status === 'scored') nav.replace(`/i/${token}/done`)
      else { setInfo(i); setMode(i.mode === 'voice' && i.voice_available ? 'voice' : 'text') }
    }).catch(() => nav.replace(`/i/${token}`))
  }, [token])
  if (!info) return null
  const done = () => nav.replace(`/i/${token}/done`)
  return (
    <Shell wide>
      {mode === 'voice'
        ? <VoiceInterview token={token!} lang={info.language} onDone={done} onFallbackText={() => setMode('text')} />
        : <TextInterview token={token!} lang={info.language} onDone={done} />}
    </Shell>
  )
}
