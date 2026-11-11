'use client'
import { usePathname, useRouter } from 'next/navigation'

/** Replace the query string of the current page (Next's useSearchParams is read-only). */
export function useSetParams() {
  const router = useRouter()
  const pathname = usePathname()
  return (next: Record<string, string>, opts: { replace?: boolean } = {}) => {
    const qs = new URLSearchParams(next).toString()
    const url = qs ? `${pathname}?${qs}` : pathname
    if (opts.replace) router.replace(url, { scroll: false })
    else router.push(url, { scroll: false })
  }
}
