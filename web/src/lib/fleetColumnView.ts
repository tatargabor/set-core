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
 * **It is not a second arrangement.** It saves nothing and moves no project
 * between groups; leaving it puts the column back exactly as it was. It may be
 * re-ordered — see `ColumnSort` — but only the flat list, only while the reader
 * asks for it, and never in a way that reaches the stored arrangement.
 *
 * **It must not be able to hide a failure.** It is compaction — the sharpest on
 * this screen, since it can drop a project entirely — so the count of what it
 * dropped travels with it, and the attention header above keeps counting the
 * WHOLE order regardless of mode. A project waiting for a human with no agent
 * running is exactly the row this view removes, and exactly the one the header
 * must still shout about.
 */

import { ageKey, freshestSeconds } from './fleetAge'
import type { FleetProject } from './fleetTypes'

export type ColumnMode = 'arrangement' | 'live'

/**
 * The order the flat list is read in.
 *
 * `order` is the reader's own — the arrangement, narrowed. `recent` answers a
 * different question, and the one the reader actually asked for: *put the
 * projects I am working in right now at the top*.
 *
 * It sorts on the FRESHEST movement in each project, never on the registry's
 * `last_updated` — that field is a state-file mtime, and it is the one this
 * screen has already caught reporting "Stopped, 24 days ago" over six working
 * agents. `last_movement_seconds` is a measurement of a session log that
 * changed.
 *
 * It applies to the FLAT list only. The group tree is where the reader put
 * things by hand; re-sorting it would either shuffle rows inside groups or
 * flatten the arrangement, and this mode reorders a way of looking, never the
 * arrangement itself.
 *
 * ## The key is the number the row DISPLAYS
 *
 * Two projects both being worked in read `1s` and `1s` on screen while their
 * raw seconds differ in the third decimal; the fleet polls every couple of
 * seconds, so sorting on the raw value swaps the top of the list under the
 * pointer, beneath two identical numbers. That looks broken rather than live.
 *
 * The first attempt at fixing it bucketed by whole minutes, and bought a worse
 * defect — measured on the running dashboard: four projects all inside one
 * minute, and `3s` rendered BELOW `32s`. An order the reader cannot explain
 * from the rows is an order they stop trusting, and they are right to.
 *
 * So the key is `ageKey` — the displayed value at `age`'s own resolution. Equal
 * text means an equal key, and ties keep the reader's own order; different text
 * always sorts the way it reads. The list can only reorder when a number on it
 * visibly changes.
 */
export type ColumnSort = 'order' | 'recent'

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
  /**
   * Whether the recency order actually applied. `false` while the tree renders,
   * so the control can say the sort is not in force instead of claiming an
   * order the rows are not in.
   */
  sorted: boolean
  /**
   * Rows in the CURRENT list with no movement measurement at all — no agent, or
   * none that reported one. They are not "oldest": nobody looked. So they sit
   * at the end, in the reader's own order, and this number lets the screen say
   * so rather than leaving a run of `—` to be read as stale.
   */
  unmeasured: number
}

export interface ColumnViewInput {
  mode: ColumnMode
  query: string
  /** Defaults to `order` — the arrangement's own, which is what it was before. */
  sort?: ColumnSort
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
  { mode, query, sort = 'order' }: ColumnViewInput,
): ColumnView {
  const present = order.filter(n => byName.has(n))
  const live = present.filter(n => (byName.get(n)!.agents?.length ?? 0) > 0)

  const base = mode === 'live' ? live : present
  const q = query.trim().toLowerCase()
  const kept = q ? base.filter(n => n.toLowerCase().includes(q)) : base

  const flat = mode === 'live' || q !== ''
  const sorted = flat && sort === 'recent'
  const fresh = new Map(kept.map(n => {
    const s = freshestSeconds(byName.get(n))
    // The DISPLAYED value — see the note on `ColumnSort`. `null` stays `null`:
    // a project nobody measured must not collapse into the same bucket as one
    // that moved this second.
    return [n, s === null ? null : ageKey(s)] as const
  }))
  const unmeasured = kept.filter(n => fresh.get(n) === null).length

  // Stable by specification (ES2019), and that is load-bearing: two projects
  // whose rows show the same age share a key, and keep the reader's own order
  // rather than swapping on every poll. The unmeasured rows are ranked
  // below every measured one — including one that moved an hour ago — because
  // "we did not look" is not a time, and interleaving it would state one.
  const rows = sorted
    ? [...kept].sort((a, b) => {
      const fa = fresh.get(a) ?? null
      const fb = fresh.get(b) ?? null
      if (fa === null && fb === null) return 0
      if (fa === null) return 1
      if (fb === null) return -1
      return fa - fb
    })
    : kept

  return {
    rows: rows.map(name => ({ name, project: byName.get(name) })),
    flat,
    hiddenNoLive: mode === 'live' ? present.length - live.length : 0,
    hiddenByFilter: base.length - kept.length,
    totalLive: live.length,
    totalPresent: present.length,
    sorted,
    unmeasured,
  }
}
