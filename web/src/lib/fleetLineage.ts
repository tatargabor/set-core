/**
 * Who started this agent, and who runs under it — tasks 7.8 (upwards) and 7.18
 * (downwards), as decisions rather than as JSX.
 *
 * The two directions share a mechanism (find that agent on this screen and go
 * to it) and differ in what they are allowed to CLAIM, which is the whole
 * content of this file:
 *
 * **Upwards, two sources are two claims.** `recorded` is the owner's own note
 * of who asked for the start; `ancestry` is a walk up the process tree. They
 * answer different questions, they can disagree, and a screen that picked one
 * silently would report the disagreement as a fact. The measurement and the
 * inference therefore never get the same weight — the screen is the last place
 * where they can still be told apart.
 *
 * **Downwards, the count is bounded and says so.** `live_only` is carried by
 * the producer and it is always true today: the count comes from RECORDED
 * starts that are still running, so an agent started with `claude -p` that has
 * already exited is not in it. A bare `2` under a tile reads as *this agent has
 * two children*, which is a claim nobody measured — the same false-absence
 * class as a zero that means "we did not look".
 *
 * And `known: false` is not zero. Without a seat there is no key to look the
 * agent up by, so nothing can be said at all — a `0` there would state *nothing
 * runs under it* about an agent that may have started five.
 */

import type { FleetAgent } from './fleetTypes'

export type ParentClaim =
  | { kind: 'none' }
  | {
      kind: 'parent'
      /** What to show: the seat name, or the bare pid when there is no seat. */
      label: string
      seat: string | null
      /** True for the owner's record, false for the process-tree walk. */
      measured: boolean
      /** The sentence that says which KIND of claim this is. */
      note: string
    }

export const RECORDED_NOTE =
  'the owner wrote down who asked for this agent to be started — a record, not an inference'
export const ANCESTRY_NOTE =
  'measured from the process tree: the nearest agent ancestor. Not the same as who asked — the two can disagree'

export function parentClaim(agent: Pick<FleetAgent, 'parent'>): ParentClaim {
  const p = agent.parent
  if (!p) return { kind: 'none' }
  // A pid with no session record has no seat name. Saying "unknown parent"
  // there would be a false absence: the RELATION is known and only the name is
  // missing, so the pid stands in for it.
  const label = p.seat ?? (p.pid_without_seat != null ? `pid ${p.pid_without_seat}` : null)
  if (!label) return { kind: 'none' }
  const measured = p.source === 'recorded'
  return {
    kind: 'parent',
    label,
    seat: p.seat ?? null,
    measured,
    note: measured ? RECORDED_NOTE : ANCESTRY_NOTE,
  }
}

export type DescendantStanding =
  /** No seat, so nothing could be looked up. NOT "none run under it". */
  | { kind: 'unknown'; reason: string }
  /** Looked up, and nothing recorded is running under it. */
  | { kind: 'none'; caveat: string | null }
  | {
      kind: 'some'
      live: number
      pids: number[]
      /**
       * The limit of the count, carried from the producer. Present whenever the
       * number is bounded — which is always, today — so the surface can never
       * show the figure without it.
       */
      caveat: string | null
    }

const DEFAULT_CAVEAT =
  'counted from recorded starts that are still running; a child that has already exited is not here'

export function descendantStanding(agent: Pick<FleetAgent, 'descendants'>): DescendantStanding {
  const d = agent.descendants
  if (!d || d.known === false) {
    return {
      kind: 'unknown',
      reason: d?.reason || 'this agent has no seat, so nothing can be looked up by it',
    }
  }
  const pids = Array.isArray(d.pids) ? d.pids.filter(p => typeof p === 'number') : []
  // Counted from the LIST, not from the reported number: a count and its own
  // breakdown disagreeing is the shape that turns a zero into a proof.
  const live = pids.length > 0 ? pids.length : (typeof d.live === 'number' ? d.live : 0)
  const caveat = d.live_only === false ? null : (d.reason || DEFAULT_CAVEAT)
  if (live === 0) return { kind: 'none', caveat }
  return { kind: 'some', live, pids, caveat }
}

/**
 * Whether a descendant count may be shown without its caveat.
 *
 * Never, while `live_only` holds — which is the only state the producer emits
 * today. Kept as a function so the day the producer can see exited children,
 * the surface stops apologising on its own rather than by someone remembering
 * to delete a sentence.
 */
export function countIsComplete(standing: DescendantStanding): boolean {
  return standing.kind !== 'unknown' && standing.caveat === null
}
