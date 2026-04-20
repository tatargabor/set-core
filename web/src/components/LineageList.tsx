/**
 * LineageList sidebar section (Section 14.1–14.3, 14.7–14.9).
 *
 * Fetches `/api/<project>/lineages`, renders "All lineages" first, then
 * one row per lineage.  A green dot marks the `is_live` entry.  Clicking
 * a row sets the selection in `SelectedLineageProvider`, which triggers
 * refetches in every tab that reads the context.
 */

import { useEffect, useState } from 'react'
import { getLineages, type LineageMeta, type StateData } from '../lib/api'
import { ALL_LINEAGES, useSelectedLineage } from '../lib/lineage'

interface Props {
  project: string
  sidebarState: StateData | null
}

export default function LineageList({ project, sidebarState }: Props) {
  const { lineageId, setLineageId } = useSelectedLineage()
  const [lineages, setLineages] = useState<LineageMeta[]>([])
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Refetch on mount and whenever the live state's lineage or status changes
  // — so a new sentinel session or a replan surfaces the new lineage entry
  // without a manual reload.
  useEffect(() => {
    let cancelled = false
    getLineages(project).then((resp) => {
      if (cancelled) return
      setLineages(resp.lineages)
      setError(null)
      setLoaded(true)

      // Default-selection rule (Section 14.7):
      //   - if exactly one lineage has is_live=true and no selection yet,
      //     pick it;
      //   - else pick the lineage with the newest last_seen_at.
      // Selections stored in localStorage win unless the stored id is not
      // present in the fresh list.
      const knownIds = new Set(resp.lineages.map(l => l.id))
      // `__all__` is no longer exposed in the UI — if a stored selection
      // still references it, fall through so the default-selection rule
      // replaces it with a concrete lineage on the next render.
      if (lineageId != null && lineageId !== ALL_LINEAGES && !knownIds.has(lineageId)) {
        setLineageId(null)
        return
      }
      if (lineageId === ALL_LINEAGES) {
        setLineageId(null)
        return
      }
      if (lineageId == null && resp.lineages.length > 0) {
        const live = resp.lineages.find(l => l.is_live)
        if (live) {
          setLineageId(live.id)
        } else {
          const newest = [...resp.lineages].sort((a, b) =>
            (b.last_seen_at || '').localeCompare(a.last_seen_at || '')
          )[0]
          if (newest) setLineageId(newest.id)
        }
      }
    }).catch((err: unknown) => {
      if (cancelled) return
      setError(err instanceof Error ? err.message : String(err))
      setLoaded(true)
    })
    return () => { cancelled = true }
    // Re-run when the live lineage or sentinel status changes — both
    // signals that the lineage list may have a new entry or flipped
    // is_live bits.
  }, [project, sidebarState?.spec_lineage_id, sidebarState?.status])

  if (!loaded) {
    return (
      <div className="px-4 py-2 border-b border-neutral-800">
        <span className="text-xs text-neutral-500 uppercase tracking-wider">Lineages</span>
        <div className="mt-1 text-xs text-neutral-600">Loading…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 py-2 border-b border-neutral-800">
        <span className="text-xs text-neutral-500 uppercase tracking-wider">Lineages</span>
        <div className="mt-1 text-xs text-amber-400" title={error}>Unavailable</div>
      </div>
    )
  }

  if (lineages.length === 0) return null

  // Sort: live first, then by last_seen_at desc, then by id.
  const sorted = [...lineages].sort((a, b) => {
    if (a.is_live !== b.is_live) return a.is_live ? -1 : 1
    const ta = a.last_seen_at || ''
    const tb = b.last_seen_at || ''
    if (ta !== tb) return tb.localeCompare(ta)
    return a.id.localeCompare(b.id)
  })

  return (
    <div className="px-2 py-2 border-b border-neutral-800">
      <div className="px-2 pb-1 text-xs text-neutral-500 uppercase tracking-wider">Lineages</div>
      {sorted.map((l) => (
        <button
          key={l.id}
          type="button"
          onClick={() => setLineageId(l.id)}
          title={l.diagnostic || undefined}
          data-lineage={l.id}
          className={`w-full flex items-center gap-2 px-2 py-1 rounded text-sm transition-colors ${
            lineageId === l.id
              ? 'bg-neutral-800 text-neutral-100'
              : 'text-neutral-400 hover:bg-neutral-800/50 hover:text-neutral-300'
          }`}
        >
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${
              l.is_live ? 'bg-green-400' : 'bg-neutral-700'
            }`}
            aria-label={l.is_live ? 'live' : undefined}
          />
          <span className="flex-1 text-left truncate" title={l.display_name}>{l.display_name}</span>
          {l.diagnostic && (
            <span className="text-xs text-amber-400" title={l.diagnostic}>?</span>
          )}
        </button>
      ))}
    </div>
  )
}
