import { Suspense } from 'react'
import CandidateDetail from '../../../../views/CandidateDetail'

export default function Page() {
  return <Suspense fallback={null}><CandidateDetail /></Suspense>
}
