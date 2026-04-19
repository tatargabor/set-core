/**
 * Selected lineage context (Section 14.4).
 *
 * Tabs read `useSelectedLineage()` to learn which lineage filter to apply
 * to their data fetches.  The provider persists the selection under
 * `set-lineage-<project>` in localStorage and restores it on mount.
 */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export const ALL_LINEAGES = '__all__'

export interface SelectedLineageCtx {
  /**
   * The currently selected lineage id, or `ALL_LINEAGES` for the union
   * view, or `null` when the caller has not yet resolved a default.
   * Consumers should treat `null` the same as "use API default" — the
   * lineage filter is simply omitted from the query string.
   */
  lineageId: string | null
  setLineageId: (id: string | null) => void
  /** True when `lineageId === ALL_LINEAGES`. */
  isAll: boolean
  /**
   * Append the `lineage` query-string parameter to a path.  Returns the
   * path unchanged when no lineage is selected.  When the caller wants
   * explicit `__all__`, the provider forwards it.
   */
  withLineage(path: string): string
}

const Ctx = createContext<SelectedLineageCtx | null>(null)

interface Props {
  project: string | null
  children: ReactNode
}

function storageKey(project: string | null): string | null {
  return project ? `set-lineage-${project}` : null
}

export function SelectedLineageProvider({ project, children }: Props) {
  const [lineageId, setLineageIdState] = useState<string | null>(() => {
    const key = storageKey(project)
    if (!key) return null
    try {
      return window.localStorage.getItem(key)
    } catch {
      return null
    }
  })

  // Re-read on project change so navigating between projects restores
  // the per-project selection instead of leaking the previous one.
  useEffect(() => {
    const key = storageKey(project)
    if (!key) {
      setLineageIdState(null)
      return
    }
    try {
      setLineageIdState(window.localStorage.getItem(key))
    } catch {
      setLineageIdState(null)
    }
  }, [project])

  const setLineageId = (id: string | null) => {
    setLineageIdState(id)
    const key = storageKey(project)
    if (!key) return
    try {
      if (id == null) window.localStorage.removeItem(key)
      else window.localStorage.setItem(key, id)
    } catch {
      // localStorage unavailable — the in-memory state is still coherent.
    }
  }

  const value = useMemo<SelectedLineageCtx>(() => ({
    lineageId,
    setLineageId,
    isAll: lineageId === ALL_LINEAGES,
    withLineage(path: string): string {
      if (lineageId == null) return path
      const sep = path.includes('?') ? '&' : '?'
      return `${path}${sep}lineage=${encodeURIComponent(lineageId)}`
    },
  }), [lineageId, project])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useSelectedLineage(): SelectedLineageCtx {
  const ctx = useContext(Ctx)
  if (!ctx) {
    // Safe fallback for components rendered outside a project layout
    // (e.g., global routes).  Equivalent to "no lineage filter".
    return {
      lineageId: null,
      setLineageId: () => {},
      isAll: false,
      withLineage: (p: string) => p,
    }
  }
  return ctx
}
