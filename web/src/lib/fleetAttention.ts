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

/**
 * What a project is waiting on a HUMAN for — task 7.14.
 *
 * Deliberately separate from the agent counts below and never summed into
 * them. `waiting` counts a LIVE agent that asked a question; this counts work
 * with nobody standing on it. Measured on this machine 2026-08-19: a project
 * held two changes marked `running` since 12 June whose processes were long
 * gone and whose state file had not been touched since 24 July — 68 days of
 * "in progress" that was not. Counted by agents, that project rendered as
 * nothing to do.
 */
export interface AttentionAwaiting {
  /** The plan declares a step no agent can take (an API key, a DNS record). */
  manual?: string[]
  /** The engine recorded the change as stalled. */
  stalled?: string[]
  /** MEASURED: marked in flight, the recorded process is gone. */
  orphaned?: string[]
  /** Marked in flight, pid alive — a pid is not an identity. Named, not counted. */
  unverifiable?: string[]
  /** No orchestration state was found. NOT the same as "nothing awaits". */
  source_missing?: boolean
  total?: number
}

export interface AttentionProject {
  name: string
  agents: AttentionAgent[]
  awaiting?: AttentionAwaiting | null
}

export const WAITING = 'waiting'
export const WORKING = 'working'
export const UNKNOWN = 'unknown'
export const QUIET = 'quiet'
/**
 * Measured — a question tool is open, so the agent is stopped in front of a
 * person. Deliberately NOT called `blocked`: the envelope already carries
 * `declared.blocked`, which is the agent's own CLAIM that something holds it
 * up. One word for a declaration and a measurement in the same payload is the
 * ambiguity this file's own comments keep refusing.
 */
export const ASKING = 'asking'

export interface Tally {
  agents: number
  working: number
  unknown: number
  waiting: number
  /** Measured: a question tool is outstanding — see `ASKING`. */
  asking: number
  /** The turn ended and nothing is outstanding. Counted, never called idle. */
  quiet: number
  /**
   * Agents holding a state NO bucket above counts.
   *
   * The reason this exists rather than a silent fall-through: when `asking`
   * was added, every counter here was an `else if` chain with no final
   * branch, so a new state would have made agents vanish from the header
   * while `agents` still counted them — false absence, failing toward a calm
   * screen. This number is what makes the next new state visible instead.
   */
  unbucketed: number
  /** Agents whose declared state the log refuted — see the header of this file. */
  conflicts: number
  /** Work awaiting a human, with or without an agent — task 7.14. */
  awaiting: number
  /** Projects whose orchestration state could not be read at all. */
  unmeasured: number
}

export const EMPTY_TALLY: Tally = { agents: 0, working: 0, unknown: 0, waiting: 0, asking: 0, quiet: 0, unbucketed: 0, conflicts: 0, awaiting: 0, unmeasured: 0 }

export function tally(projects: readonly AttentionProject[]): Tally {
  let agents = 0, working = 0, unknown = 0, waiting = 0, asking = 0, quiet = 0, unbucketed = 0
  let conflicts = 0, awaiting = 0, unmeasured = 0
  for (const p of projects) {
    // Counted from the DATA, like everything else here: `total` is what the
    // producer computed from its own lists, and `source_missing` is the only
    // thing that makes a zero readable. A project with no state file adds
    // nothing to `awaiting` and one to `unmeasured` — never a silent zero.
    const aw = p.awaiting
    if (aw) {
      if (typeof aw.total === 'number') awaiting += aw.total
      if (aw.source_missing === true) unmeasured += 1
    }
    for (const a of p.agents) {
      agents += 1
      if (a.state === WORKING) working += 1
      else if (a.state === UNKNOWN) unknown += 1
      else if (a.state === WAITING) waiting += 1
      else if (a.state === ASKING) asking += 1
      else if (a.state === QUIET) quiet += 1
      // The branch that did not exist, and whose absence is the defect this
      // chain shipped with: anything unrecognised was counted nowhere at all.
      else unbucketed += 1
      // Counted from the DATA, never from a declaration that conflicts exist.
      // An empty string is not a conflict; a missing key is not one either.
      if (typeof a.declaration_ignored === 'string' && a.declaration_ignored !== '') conflicts += 1
    }
  }
  return { agents, working, unknown, waiting, asking, quiet, unbucketed, conflicts, awaiting, unmeasured }
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

/**
 * The first project awaiting a human — task 7.14's jump target.
 *
 * It cannot reuse `firstMatching`, and that is the whole point of this
 * function existing: that one looks for an AGENT satisfying a predicate, and
 * the case here is a project with no agents at all. A jump built on agents
 * would skip exactly the projects this count exists to reach.
 */
export function firstAwaiting(
  order: readonly string[],
  byName: ReadonlyMap<string, AttentionProject>,
): string | null {
  for (const name of order) {
    const total = byName.get(name)?.awaiting?.total
    if (typeof total === 'number' && total > 0) return name
  }
  return null
}

/** Is this agent's declared state one the log refuted? */
export function hasConflict(agent: AttentionAgent): boolean {
  return typeof agent.declaration_ignored === 'string' && agent.declaration_ignored !== ''
}
