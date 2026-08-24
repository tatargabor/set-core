/**
 * How the project column is being LOOKED at — the arrangement, or only what is live.
 *
 * The column's normal mode is the arrangement: hand-made groups, a parked
 * section, an ungrouped tail. That is where the reader put things, and it is
 * the right default. It is also, on this machine, 40-odd projects of which a
 * handful are running anything — so the question "where is work happening right
 * now" is answered by scrolling and reading, across collapsed groups.
 *
 * The live mode answers it directly: one flat list of the projects that hold a
 * live agent session, in the reader's own order.
 *
 * ## Two things this mode must not become
 *
 * **It is not a second arrangement.** It reorders nothing, saves nothing, and
 * moves no project between groups. Leaving it puts the column back exactly as
 * it was.
 *
 * **It must not be able to hide a failure.** It is compaction — the sharpest on
 * this screen, since it can drop a project entirely — so the count of what it
 * dropped travels with it, and the attention header above keeps counting the
 * WHOLE order regardless of mode. A project waiting for a human with no agent
 * running is exactly the row this view removes, and exactly the one the header
 * must still shout about.
 */

import type { FleetProject } from './fleetTypes'

export type ColumnMode = 'arrangement' | 'live'

/**
 * Discovery's projects, keyed by name — with entries that share a name MERGED.
 *
 * MEASURED on the live screen, 2026-08-24: `/api/fleet/agents` returned one
 * project TWICE, once for the checkout (5 agents) and once for a worktree of it
 * (0). A plain `set` per entry let the empty one win, and the column then read
 * `live 5` while the screen's own header said agents were running in 6 projects
 * — the same project, counted by two surfaces, disagreeing.
 *
 * The first entry wins for everything except the agents, which are concatenated:
 * the registry entry is the one that carries the project's own facts, and the
 * agents are the only field where a second entry adds rather than restates.
 */
export function mergeByName(projects: readonly FleetProject[]): Map<string, FleetProject> {
  const m = new Map<string, FleetProject>()
  for (const p of projects) {
    const prev = m.get(p.name)
    if (!prev) { m.set(p.name, p); continue }
    m.set(p.name, { ...prev, agents: [...(prev.agents ?? []), ...(p.agents ?? [])] })
  }
  return m
}

export interface ColumnRow {
  name: string
  project: FleetProject | undefined
}

export interface ColumnView {
  rows: ColumnRow[]
  /**
   * Render the flat list rather than the group tree. True in live mode, and
   * true whenever a filter is typed — a tree with most of its rows removed
   * shows the reader a shape that is no longer their arrangement.
   */
  flat: boolean
  /** Dropped for holding no live session — before the filter ran. Live mode only. */
  hiddenNoLive: number
  /** Dropped by the name filter, within whatever the mode left. */
  hiddenByFilter: number
  /** Projects with at least one live session, unfiltered — the live mode's own size. */
  totalLive: number
  /** Projects the column knows about at all, discovery-confirmed. */
  totalPresent: number
}

export interface ColumnViewInput {
  mode: ColumnMode
  query: string
}

/**
 * Build the visible list from the reading order and the discovered projects.
 *
 * `order` is the column's whole document — every group (collapsed or not), the
 * parked section, the ungrouped tail, and the orphans — so a live project
 * cannot be missing from this view because of where the reader filed it. That
 * is the entire point: the arrangement decides order, never what exists.
 *
 * Names the arrangement holds that discovery did not return are not rows here.
 * They are not projects on this machine, and one of them cannot be running an
 * agent; the column states them separately, as arranged-and-missing.
 */
export function buildColumnView(
  order: readonly string[],
  byName: ReadonlyMap<string, FleetProject>,
  { mode, query }: ColumnViewInput,
): ColumnView {
  const present = order.filter(n => byName.has(n))
  const live = present.filter(n => (byName.get(n)!.agents?.length ?? 0) > 0)

  const base = mode === 'live' ? live : present
  const q = query.trim().toLowerCase()
  const kept = q ? base.filter(n => n.toLowerCase().includes(q)) : base

  return {
    rows: kept.map(name => ({ name, project: byName.get(name) })),
    flat: mode === 'live' || q !== '',
    hiddenNoLive: mode === 'live' ? present.length - live.length : 0,
    hiddenByFilter: base.length - kept.length,
    totalLive: live.length,
    totalPresent: present.length,
  }
}
