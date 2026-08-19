/**
 * The fleet screen's ARRANGEMENT, on the client side — groups, order, parked.
 *
 * Decided by the user 2026-08-19 (review-findings D-2): the project column is
 * ordered by hand, in TWO levels. Groups are ordered and render as blocks; a
 * project moves only inside its own group; assignment to a group is a separate,
 * explicit act rather than a cross-group drag, because "reorder" and "regroup"
 * are different results from the same gesture and only the first was asked for.
 *
 * Everything here is a pure function over the document the API returns, kept
 * out of the component for one reason: a drag cannot be asserted in jsdom (it
 * needs a layout engine), but the *result* of one can. So the moves are
 * testable without a browser, and the browser pass is left to prove that the
 * gesture reaches them.
 *
 * ## Three properties this module exists to hold, all of them failure-directional
 *
 * **1. A save must not silently forget a `missing` project.** `GET
 * /api/fleet/layout` joins the stored arrangement to what discovery found, and
 * splits each group into `projects` (found) and `missing` (arranged, no longer
 * discovered). `PUT` replaces the WHOLE document. So a client that sends back
 * only `projects` erases every missing name — the user's arrangement quietly
 * loses the entry that was the one piece of information worth showing them.
 * `toPutBody` merges them back. This is the one thing in this file that can
 * destroy data, and it fails in the reassuring direction: the screen looks
 * tidier afterwards.
 *
 * **The merge is no longer a merge — 2026-08-19.** The API now returns each
 * group's stored list VERBATIM as `order`, plus `parked_order`, plus a
 * `parked_missing` it states rather than leaves to subtraction. So `order` is
 * what the client holds, renders and sends back, and the known loss the earlier
 * version documented — a missing member re-appended at the END of its group on
 * every save, because the join reported *which* were missing and not *where*
 * they sat — is gone rather than mitigated. The old shape is still read (an
 * `order`-less answer falls back to `[...projects, ...missing]`), because a
 * client that crashes on the previous server is a worse failure than a drift.
 *
 * The ungrouped block gained the same thing from the other side: `GET` returns
 * `ungrouped` ALREADY in the stored order, and `PUT` accepts `ungrouped_order`.
 * That is what lifts the limit this file used to have to print on the screen —
 * "sorrendjük a felderítésé" — so the ungrouped block is now drag-orderable
 * like any group.
 *
 * **2. Membership is a stored fact, never a name rule.** `seedFromPrefix` is a
 * one-time bulk act whose result the user can see, and what is persisted is the
 * membership it produced. Nothing re-evaluates a prefix afterwards, so renaming
 * a project cannot move it between groups behind the user's back.
 *
 * **3. A project appears exactly once.** Assignment removes before it adds,
 * across every group AND the parked list. A project listed twice would render
 * twice and its position would depend on iteration order.
 */

export interface FleetGroup {
  id: string
  name: string
  collapsed: boolean
  /** Members discovery found, in stored order. Derived from `order`. */
  projects: string[]
  /** Members discovery no longer finds, in stored order. Derived from `order`. */
  missing: string[]
  /**
   * The stored membership list, verbatim and in one piece — found and missing
   * interleaved exactly as the user arranged them. This is the authority: the
   * other two are views of it, so a missing member keeps its POSITION through a
   * save instead of drifting to the end.
   */
  order: string[]
}

export interface FleetArrangement {
  version: number
  groups: FleetGroup[]
  /** Parked members discovery found. */
  parked: string[]
  /** Parked members discovery no longer finds. */
  parkedMissing: string[]
  /** The stored parked list verbatim — same role as a group's `order`. */
  parkedOrder: string[]
  /**
   * Discovered projects nobody grouped, in the order the API resolved: the
   * user's own `ungrouped_order` first, then anything they never ordered, in
   * discovery's order. This list IS the order — `PUT` takes it back as
   * `ungrouped_order`.
   */
  ungrouped: string[]
}

/** The shape `GET /api/fleet/layout` actually returns. */
export interface LayoutResponse {
  version?: number
  groups?: {
    id?: string; name?: string; collapsed?: boolean
    projects?: string[]; missing?: string[]
    /** Added 2026-08-19 — the stored list verbatim. */
    order?: string[]
  }[]
  parked?: string[]
  /** Added 2026-08-19 — stated rather than derived by subtraction. */
  parked_missing?: string[]
  /** Added 2026-08-19 — the stored parked list verbatim. */
  parked_order?: string[]
  ungrouped?: string[]
  missing?: string[]
}

export const UNGROUPED_ID = '__ungrouped__'
export const PARKED_ID = '__parked__'

export type Target =
  | { kind: 'group'; id: string }
  | { kind: 'ungrouped' }
  | { kind: 'parked' }

export function emptyArrangement(): FleetArrangement {
  return { version: 0, groups: [], parked: [], parkedMissing: [], parkedOrder: [], ungrouped: [] }
}

/**
 * Re-derive a group's two views from its `order` and the set of names discovery
 * found.
 *
 * One function so the three lists cannot drift: every mutator below goes through
 * it, and the found-set is read off the CURRENT `projects` rather than recomputed
 * from anything — the client never learns which names discovery found except by
 * being told, and inventing that answer here would be the declaration-is-not-data
 * defect one layer down.
 */
function reorder(g: FleetGroup, order: readonly string[]): FleetGroup {
  const found = new Set(g.projects)
  const next = [...order]
  return {
    ...g,
    order: next,
    projects: next.filter(n => found.has(n)),
    missing: next.filter(n => !found.has(n)),
  }
}

/**
 * Read the API's answer into the client model.
 *
 * The parked half of `missing` is not reported separately by the API: the
 * top-level `missing` is every group's missing entries followed by the parked
 * ones. So the parked remainder is what is left after subtracting what the
 * groups already accounted for — derived from the data rather than guessed, and
 * the subtraction is by name because names are unique across the document.
 */
export function fromResponse(raw: LayoutResponse | null | undefined): FleetArrangement {
  if (!raw || typeof raw !== 'object') return emptyArrangement()
  const groups: FleetGroup[] = (raw.groups ?? []).map((g, i) => {
    const projects = [...(g.projects ?? [])]
    const missing = [...(g.missing ?? [])]
    // `order` is authoritative where the server sends it. Where it does not —
    // an older server — the concatenation is the same list with the missing
    // members flattened to the end, which is exactly the loss `order` removes.
    const order = g.order ? [...g.order] : [...projects, ...missing]
    return reorder(
      {
        id: String(g.id ?? g.name ?? `g-${i}`),
        name: String(g.name ?? g.id ?? `csoport ${i + 1}`),
        collapsed: Boolean(g.collapsed),
        projects,
        missing,
        order,
      },
      order,
    )
  })
  const parked = [...(raw.parked ?? [])]
  // Stated where the server states it. The subtraction below is the fallback,
  // kept rather than deleted because it is the only thing an older server can
  // answer — and it is an INFERENCE, so the explicit key wins whenever there is
  // one. `parked_missing: []` is a real answer and must not fall through to the
  // subtraction, hence a key test rather than a truthiness test.
  const accountedFor = new Set(groups.flatMap(g => g.missing))
  const parkedMissing = Array.isArray(raw.parked_missing)
    ? [...raw.parked_missing]
    : (raw.missing ?? []).filter(name => !accountedFor.has(name))
  const parkedOrder = Array.isArray(raw.parked_order)
    ? [...raw.parked_order]
    : [...parked, ...parkedMissing]
  return {
    version: Number(raw.version ?? 0),
    groups,
    parked,
    parkedMissing,
    parkedOrder,
    ungrouped: [...(raw.ungrouped ?? [])],
  }
}

/**
 * The body of a `PUT /api/fleet/layout`.
 *
 * `base_version` is the version that was READ. The API answers 409 when it no
 * longer matches, which is the only thing standing between two open tabs and an
 * arrangement nobody made.
 *
 * The stored list goes back VERBATIM — `order`, not `projects` and not a
 * hand-made merge of the two. The API added it on 2026-08-19 for exactly this:
 * the earlier concatenation re-appended every missing member at the end of its
 * group on every single save, so a name the user could see was slowly walking
 * down their arrangement each time they dragged anything.
 */
export function toPutBody(a: FleetArrangement): {
  groups: { id: string; name: string; collapsed: boolean; projects: string[] }[]
  parked: string[]
  ungrouped_order: string[]
  base_version: number
} {
  return {
    groups: a.groups.map(g => ({
      id: g.id,
      name: g.name,
      collapsed: g.collapsed,
      projects: [...g.order],
    })),
    parked: [...a.parkedOrder],
    // The ungrouped block's own order — a preference, not a membership. The
    // server drops any name here that has since joined a group or vanished, so
    // sending the whole list cannot create a second home for anything.
    ungrouped_order: [...a.ungrouped],
    base_version: a.version,
  }
}

/**
 * Move one element of a list, by index.
 *
 * Out-of-range indices return the list unchanged rather than throwing: this is
 * driven by a pointer whose hit-test can land anywhere, and a drag that ends
 * outside the list must be a no-op, not a crash on the landing screen.
 */
export function moveWithin<T>(list: readonly T[], from: number, to: number): T[] {
  const next = [...list]
  if (from < 0 || from >= next.length) return next
  if (to < 0 || to >= next.length) return next
  if (from === to) return next
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  return next
}

export function moveGroup(a: FleetArrangement, from: number, to: number): FleetArrangement {
  return { ...a, groups: moveWithin(a.groups, from, to) }
}

/**
 * Reorder inside ONE group. A project never leaves its group by dragging.
 *
 * The indices are positions in `order`, which is what the group renders — found
 * and missing rows in one list. Reordering `projects` instead would mean the
 * index the pointer landed on and the index being moved were counted over two
 * different lists, and they diverge the moment a group has a missing member.
 */
export function moveProject(a: FleetArrangement, groupId: string, from: number, to: number): FleetArrangement {
  return {
    ...a,
    groups: a.groups.map(g => (g.id === groupId ? reorder(g, moveWithin(g.order, from, to)) : g)),
  }
}

/** Reorder the parked section, whose stored list is `parkedOrder`. */
export function moveParked(a: FleetArrangement, from: number, to: number): FleetArrangement {
  const parkedOrder = moveWithin(a.parkedOrder, from, to)
  const found = new Set(a.parked)
  return {
    ...a,
    parkedOrder,
    parked: parkedOrder.filter(n => found.has(n)),
    parkedMissing: parkedOrder.filter(n => !found.has(n)),
  }
}

/**
 * Reorder the ungrouped block — possible only since the API started storing
 * `ungrouped_order` (2026-08-19). Before that this list was discovery's order
 * and a drag had nothing to persist into, which the screen had to say out loud.
 */
export function moveUngrouped(a: FleetArrangement, from: number, to: number): FleetArrangement {
  return { ...a, ungrouped: moveWithin(a.ungrouped, from, to) }
}

/** Strip a project from every list it could be in. Assignment's first half. */
function detach(a: FleetArrangement, project: string): FleetArrangement {
  return {
    ...a,
    groups: a.groups.map(g => ({
      ...g,
      order: g.order.filter(p => p !== project),
      projects: g.projects.filter(p => p !== project),
      missing: g.missing.filter(p => p !== project),
    })),
    parked: a.parked.filter(p => p !== project),
    parkedMissing: a.parkedMissing.filter(p => p !== project),
    parkedOrder: a.parkedOrder.filter(p => p !== project),
    ungrouped: a.ungrouped.filter(p => p !== project),
  }
}

/**
 * Put a project somewhere, explicitly — the separate control D-2 asked for.
 *
 * Removes first, everywhere, so no project can end up in two places. A target
 * group that does not exist leaves the project ungrouped rather than dropping
 * it off the screen.
 */
export function assign(a: FleetArrangement, project: string, target: Target): FleetArrangement {
  const base = detach(a, project)
  if (target.kind === 'parked') {
    return { ...base, parked: [...base.parked, project], parkedOrder: [...base.parkedOrder, project] }
  }
  if (target.kind === 'group') {
    const exists = base.groups.some(g => g.id === target.id)
    if (!exists) return { ...base, ungrouped: [...base.ungrouped, project] }
    return {
      ...base,
      groups: base.groups.map(g => (
        g.id === target.id
          ? { ...g, projects: [...g.projects, project], order: [...g.order, project] }
          : g
      )),
    }
  }
  return { ...base, ungrouped: [...base.ungrouped, project] }
}

/** A group id that cannot collide with an existing one, derived from the name. */
export function groupId(name: string, taken: readonly string[]): string {
  const base = 'g-' + (name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'csoport')
  if (!taken.includes(base)) return base
  let n = 2
  while (taken.includes(`${base}-${n}`)) n += 1
  return `${base}-${n}`
}

/**
 * Which discovered projects a prefix would seed a group with, right now.
 *
 * Shown to the user BEFORE the group is created, because the whole point of
 * allowing a prefix is that it is a one-time act whose result is visible. The
 * membership it produces is what persists; the prefix itself is not stored and
 * never re-evaluated.
 */
export function seedCandidates(a: FleetArrangement, prefix: string): string[] {
  const p = prefix.trim()
  if (!p) return []
  const all = [...a.groups.flatMap(g => g.projects), ...a.parked, ...a.ungrouped]
  return all.filter(name => name.startsWith(p))
}

export function createGroup(a: FleetArrangement, name: string, seed: readonly string[] = []): FleetArrangement {
  const id = groupId(name, a.groups.map(g => g.id))
  const withGroup: FleetArrangement = {
    ...a,
    groups: [...a.groups, { id, name: name.trim(), collapsed: false, projects: [], missing: [], order: [] }],
  }
  return seed.reduce((acc, project) => assign(acc, project, { kind: 'group', id }), withGroup)
}

/**
 * Delete a group; its members become ungrouped.
 *
 * Never silently: the members are moved rather than dropped, including the
 * missing ones, which land in the ungrouped-missing tail so a deletion cannot
 * be a back door to the data loss `toPutBody` exists to prevent.
 */
export function removeGroup(a: FleetArrangement, id: string): FleetArrangement {
  const target = a.groups.find(g => g.id === id)
  if (!target) return a
  return {
    ...a,
    groups: a.groups.filter(g => g.id !== id),
    ungrouped: [...a.ungrouped, ...target.projects],
    // A missing member of a deleted group would have nowhere to go; parking it
    // keeps it in the document, and the parked section is where the user is
    // already being asked to look at things they set aside.
    parkedMissing: [...a.parkedMissing, ...target.missing],
    parkedOrder: [...a.parkedOrder, ...target.missing],
  }
}

export function setCollapsed(a: FleetArrangement, id: string, collapsed: boolean): FleetArrangement {
  return { ...a, groups: a.groups.map(g => (g.id === id ? { ...g, collapsed } : g)) }
}

export function renameGroup(a: FleetArrangement, id: string, name: string): FleetArrangement {
  const trimmed = name.trim()
  if (!trimmed) return a
  return { ...a, groups: a.groups.map(g => (g.id === id ? { ...g, name: trimmed } : g)) }
}

/** Forget an arranged project discovery no longer finds — the user's decision, never automatic. */
export function forgetMissing(a: FleetArrangement, project: string): FleetArrangement {
  const gone = (g: FleetGroup) => g.missing.includes(project)
  return {
    ...a,
    groups: a.groups.map(g => (gone(g)
      ? { ...g, missing: g.missing.filter(p => p !== project), order: g.order.filter(p => p !== project) }
      : g)),
    parkedMissing: a.parkedMissing.filter(p => p !== project),
    parkedOrder: a.parkedMissing.includes(project)
      ? a.parkedOrder.filter(p => p !== project)
      : a.parkedOrder,
  }
}

/** Every project name the arrangement places, present or missing. */
export function arrangedNames(a: FleetArrangement): string[] {
  // Reading order, which is now literally the stored order: the attention
  // header's jump searches this list, so it has to match what the eye walks.
  return [
    ...a.groups.flatMap(g => g.order),
    ...a.parkedOrder,
    ...a.ungrouped,
  ]
}

/**
 * Discovered projects the arrangement does not place anywhere.
 *
 * Should always be empty — the API derives `ungrouped` from the same discovery
 * pass — so this exists because "should" is not a measurement. The two answers
 * are fetched separately and can disagree across a refresh, and the direction
 * of that disagreement is a project with a running agent rendering nowhere:
 * the exact false absence this whole screen was built against.
 */
export function orphans(a: FleetArrangement, discovered: readonly string[]): string[] {
  const placed = new Set(arrangedNames(a))
  return discovered.filter(name => !placed.has(name))
}
