/**
 * What is waiting, counted across an arrangement the user made themselves.
 *
 * D-2's third requirement, and it is the constraint that produced the decision
 * rather than a decoration on it. Manual ordering has no construction that
 * keeps a waiting project visible: automatic attention-ordering puts it on top
 * by definition, a workspace filter has a fixed tab strip to hang a count on, a
 * hand-made order has neither. A project dragged to position 30 six weeks ago is
 * below the fold today and nothing will move it. So the count lives in a header
 * that does not scroll, it counts across the parked section and every collapsed
 * group, and it can jump to the first one.
 *
 * ## The dangerous half: a zero the producer cannot make
 *
 * `waiting` is task 3.8. It WAS not implemented in discovery; measured
 * 2026-08-19 (morning) on 7451, all 22 live agents came back `quiet` and the
 * envelope had no `waiting` key at all — so the header said "not reported"
 * rather than "none", because a rendered `0 vár válaszra` would have been an
 * answer nobody gave.
 *
 * **Re-measured 2026-08-19 (afternoon), same server:** the envelope now carries
 * `waiting: 1` and one agent reports `state: "waiting"` with
 * `waiting_for: "input needed"`. The header therefore counts, and it started
 * counting with no change to this function — which is what the shape-reading
 * design was for. The refuted alternative is worth keeping: `!data.waiting`
 * would read a real `waiting: 0` as "not reported", so the check is `typeof
 * === 'number'`, not truthiness.
 *
 * ## The contradiction count
 *
 * `declaration_ignored` is the producer saying *the record claimed one state and
 * the log refuted it*. The measurement wins and `state` already holds the
 * result — so nothing downstream needs this to be correct. That is exactly why
 * it is counted: a contradiction the surface never renders is one nobody ever
 * fixes, and the field costs nothing to carry and everything to drop.
 */

export interface AttentionAgent {
  pid: number
  state: string
  /** Present where the record's declared state was refuted by the log. */
  declaration_ignored?: string | null
}

export interface AttentionProject {
  name: string
  agents: AttentionAgent[]
}

export const WAITING = 'waiting'
export const WORKING = 'working'
export const UNKNOWN = 'unknown'

export interface Tally {
  agents: number
  working: number
  unknown: number
  waiting: number
  /** Agents whose declared state the log refuted — see the header of this file. */
  conflicts: number
}

export const EMPTY_TALLY: Tally = { agents: 0, working: 0, unknown: 0, waiting: 0, conflicts: 0 }

export function tally(projects: readonly AttentionProject[]): Tally {
  let agents = 0, working = 0, unknown = 0, waiting = 0, conflicts = 0
  for (const p of projects) {
    for (const a of p.agents) {
      agents += 1
      if (a.state === WORKING) working += 1
      else if (a.state === UNKNOWN) unknown += 1
      else if (a.state === WAITING) waiting += 1
      // Counted from the DATA, never from a declaration that conflicts exist.
      // An empty string is not a conflict; a missing key is not one either.
      if (typeof a.declaration_ignored === 'string' && a.declaration_ignored !== '') conflicts += 1
    }
  }
  return { agents, working, unknown, waiting, conflicts }
}

export function tallyOf(names: readonly string[], byName: ReadonlyMap<string, AttentionProject>): Tally {
  return tally(names.map(n => byName.get(n)).filter((p): p is AttentionProject => Boolean(p)))
}

/**
 * Does the producer report a waiting state at all?
 *
 * Two independent signals, either of which is proof, and neither of which is a
 * declaration the producer makes about itself:
 *
 *  - the envelope carries a `waiting` key — an absent key is not a zero, so
 *    `typeof` rather than truthiness (a real `waiting: 0` must count as
 *    reported, and `!data.waiting` would read it as absent);
 *  - some agent is actually in that state, which settles it whatever the
 *    envelope says.
 *
 * Nothing here asks the API whether it supports the field. A declaration is not
 * data, and this is the same rule applied one layer up.
 */
export function waitingReported(envelope: unknown, projects: readonly AttentionProject[]): boolean {
  if (envelope && typeof envelope === 'object' && typeof (envelope as Record<string, unknown>).waiting === 'number') {
    return true
  }
  return projects.some(p => p.agents.some(a => a.state === WAITING))
}

/**
 * The first project, in the order the reader sees, holding an agent in one of
 * the given states. `null` when there is none — never the first project as a
 * fallback, because jumping somewhere irrelevant teaches the reader the marker
 * is noise.
 *
 * `order` must be the FULL reading order including parked and collapsed groups:
 * the whole point is to reach the ones that are out of sight.
 */
export function firstWith(
  order: readonly string[],
  byName: ReadonlyMap<string, AttentionProject>,
  states: readonly string[],
): string | null {
  return firstMatching(order, byName, a => states.includes(a.state))
}

/** The same jump, for something that is not a state — a refuted declaration. */
export function firstMatching(
  order: readonly string[],
  byName: ReadonlyMap<string, AttentionProject>,
  predicate: (agent: AttentionAgent) => boolean,
): string | null {
  for (const name of order) {
    const project = byName.get(name)
    if (project?.agents.some(predicate)) return name
  }
  return null
}

/** Is this agent's declared state one the log refuted? */
export function hasConflict(agent: AttentionAgent): boolean {
  return typeof agent.declaration_ignored === 'string' && agent.declaration_ignored !== ''
}
