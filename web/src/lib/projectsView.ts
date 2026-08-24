/**
 * What the projects screen shows, and what it is not showing.
 *
 * The screen used to have exactly one answer: every registered project, in
 * `last_updated` order. Measured 2026-08-24 on the running dashboard, that is 39
 * rows of which 6 hold a live agent session — and the column a reader would use
 * to tell them apart, `status`, is the orchestration record that was already
 * caught reporting "Stopped, 24 days ago" over six working agents.
 *
 * So liveness here is never inferred from a project's own status. It is counted
 * from the fleet's `agents` array, which is a measurement of live processes.
 *
 * The model lives apart from the render for one reason: the numbers that keep
 * this screen honest — how many rows the view hid, how many the filter hid — are
 * the part worth testing, and a DOM is not needed to test them.
 */

import type { ProjectInfo } from './api'
import type { FleetResponse } from './fleetTypes'

export type ProjectsViewMode = 'all' | 'live'

export interface ProjectRow {
  name: string
  /**
   * The registry entry, or `null` for a project the FLEET measured as live that
   * the projects endpoint never returned. Measured: 2 of the fleet's 52 arrive
   * with `sources: ["messaging"]` and no registry entry, so dropping them would
   * hide live work from the screen that claims to list projects.
   */
  project: ProjectInfo | null
  /** `false` for exactly those rows. They carry no link — the route does not resolve. */
  registered: boolean
  /**
   * Live agent sessions the fleet measured — `null` means UNMEASURED, and it is
   * reachable only when the fleet answer itself is missing. A fleet outage that
   * rendered zeros would be more convincing than the screen this replaced.
   */
  liveSessions: number | null
}

export interface ProjectsView {
  rows: ProjectRow[]
  /** Rows the VIEW dropped (live-only), before the filter ran. */
  hiddenByView: number
  /** Rows the name filter dropped, within the current view. */
  hiddenByFilter: number
  /** How many rows each view holds, unfiltered — so the control can state both sizes. */
  totalAll: number
  totalLive: number
  /** `false` when the fleet answer is missing: every count on screen is unmeasured. */
  liveMeasured: boolean
}

export interface ProjectsViewInput {
  mode: ProjectsViewMode
  query: string
}

/**
 * Live session counts by project name, or `null` when the fleet did not answer.
 *
 * Kept separate from `buildProjectsView` so the "unmeasured" state has exactly
 * one origin: a `null` fleet response. There is no path that turns a present
 * answer into an unmeasured row.
 */
function liveCounts(fleet: FleetResponse | null): Map<string, number> | null {
  if (!fleet || !Array.isArray(fleet.projects)) return null
  const counts = new Map<string, number>()
  for (const p of fleet.projects) {
    // SUMMED, not assigned. Measured 2026-08-24 on the running dashboard: the
    // fleet returned ONE PROJECT TWICE — once for the checkout (5 agents)
    // and once for a worktree of it (0) — and a `set` let the second entry
    // overwrite the first. The project with five live sessions then failed to
    // appear in the live view at all, which is the exact false absence this
    // column exists to remove, arriving through the column itself.
    const n = Array.isArray(p.agents) ? p.agents.length : 0
    counts.set(p.name, (counts.get(p.name) ?? 0) + n)
  }
  return counts
}

function matches(name: string, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return name.toLowerCase().includes(q)
}

/**
 * Turn the two payloads plus the reader's choices into rows and the counts that
 * say what is missing from them.
 *
 * The view narrows first and the filter second, deliberately: the two hidden
 * counts then answer different questions ("projects without a session" vs "names
 * that do not match"), and a reader can undo the one they meant.
 */
export function buildProjectsView(
  projects: ProjectInfo[],
  fleet: FleetResponse | null,
  { mode, query }: ProjectsViewInput,
): ProjectsView {
  const counts = liveCounts(fleet)
  const liveMeasured = counts !== null

  const registered: ProjectRow[] = projects.map(p => ({
    name: p.name,
    project: p,
    registered: true,
    liveSessions: counts ? (counts.get(p.name) ?? 0) : null,
  }))

  // Live in the fleet's measurement, absent from the registry. Only reachable
  // when there IS a measurement — an unmeasured fleet cannot claim these exist.
  const unregistered: ProjectRow[] = []
  if (counts) {
    const known = new Set(projects.map(p => p.name))
    for (const [name, n] of counts) {
      if (n > 0 && !known.has(name)) {
        unregistered.push({ name, project: null, registered: false, liveSessions: n })
      }
    }
    unregistered.sort((a, b) => (b.liveSessions! - a.liveSessions!) || a.name.localeCompare(b.name))
  }

  const totalAll = registered.length
  // Unmeasured means the live view has no population to state a size for — 0
  // here would read as "measured: nothing is live". The caller renders the
  // absence from `liveMeasured`, and never from this number.
  const totalLive = counts
    ? registered.filter(r => (r.liveSessions ?? 0) > 0).length + unregistered.length
    : 0

  const inView = mode === 'live'
    ? [...registered.filter(r => (r.liveSessions ?? 0) > 0), ...unregistered]
    : registered

  const rows = inView.filter(r => matches(r.name, query))

  return {
    rows,
    // The live view drops registered rows; the unregistered ones it ADDS are not
    // hidden from anything, so they are excluded from what the view hid.
    hiddenByView: mode === 'live' ? totalAll - registered.filter(r => (r.liveSessions ?? 0) > 0).length : 0,
    hiddenByFilter: inView.length - rows.length,
    totalAll,
    totalLive,
    liveMeasured,
  }
}
