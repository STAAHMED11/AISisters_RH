import { Suspense } from 'react'
import Candidates from '../../../../../views/Candidates'

export default function Page() {
  return <Suspense fallback={null}><Candidates /></Suspense>
}
