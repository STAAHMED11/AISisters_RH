import { redirect } from 'next/navigation'

// Unknown recruiter URLs land on the offers list (same behaviour as the former SPA catch-all).
export default function NotFound() {
  redirect('/jobs')
}
