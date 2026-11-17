import { useEffect, useRef, useState } from 'react'

/**
 * One file listing per checkout, fetched ONCE — B-180.
 *
 * The listing used to be fetched from an effect that depended on the listings
 * it had already received, and whose cleanup marked EVERY in-flight request as
 * dead. Each arriving listing re-ran the effect, so the replies still in flight
 * were thrown away and requested again; the root set re-memoising on every
 * fleet poll did the same. Measured 2026-11-17 on a fresh load: 93 requests
 * over 8 roots (~26 MB) in the first 30 s, where 8 were needed.
 *
 * Now a root is requested only when it is neither known nor already in flight,
 * and a reply is dropped only when the component itself has gone away — a
 * re-render is not a reason to discard an answer. A failed request leaves the
 * root unknown, so the next change of the root set asks again, which is the
 * retry the old code had.
 */
export function useFileListings(roots: readonly string[], enabled: boolean): Record<string, ReadonlySet<string>> {
  const [known, setKnown] = useState<Record<string, ReadonlySet<string>>>({})
  const inFlight = useRef<Set<string>>(new Set())
  const alive = useRef(true)

  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])

  useEffect(() => {
    if (!enabled) return
    for (const root of roots) {
      if (known[root] || inFlight.current.has(root)) continue
      inFlight.current.add(root)
      void fetch(`/api/fleet/files?root=${encodeURIComponent(root)}`)
        .then(r => (r.ok ? r.json() : null))
        .then(body => {
          if (!alive.current || !body) return
          setKnown(prev => ({ ...prev, [root]: new Set<string>(body.files ?? []) }))
        })
        .catch(() => {
          // A listing that cannot be fetched means no file links for that
          // checkout, which is the correct degradation: `fileReference` refuses
          // everything without a known set, so nothing is offered that cannot
          // be opened. Silent on purpose — the terminal itself is unaffected.
        })
        .finally(() => { inFlight.current.delete(root) })
    }
  }, [roots, enabled, known])

  return known
}
