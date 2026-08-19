/**
 * Whether a terminal can be offered for one agent, and why not when it cannot.
 *
 * Task 8.2 in one sentence: *offer a terminal only where one can exist, and
 * where it cannot, state the reason in its place.* Both halves are load-bearing,
 * and the second is the one that is easy to get wrong in the reassuring
 * direction.
 *
 * ## Three populations, and the third is not a shade of the second
 *
 * The producer carries `population` as a fact (task 5.1) — this module never
 * infers it:
 *
 *  - `started-here` — the framework started the process and still holds its pty.
 *    A terminal exists and `terminal_label` addresses it.
 *  - `foreign` — nobody here holds it. There is no terminal and there cannot be
 *    one: adoption of a running session was measured to fail twice over (resume
 *    forks the conversation; the cross-session channel reaches but does not
 *    attach).
 *  - `unknown` — **the owner service could not be asked.** We do not know.
 *
 * Collapsing `unknown` into `foreign` is the defect this file exists to prevent,
 * and its cost is specific: while the owner service restarts, every agent it
 * holds arrives as `unknown`, and a screen that reads that as `foreign` states
 * "there is no terminal" about agents that have one — confidently, silently, and
 * only for as long as nobody is looking. That is the false-absence class, and its
 * direction is the expensive one: the reader stops looking for the thing.
 *
 * So `unknown` renders as its own outcome with its own wording, and the reason
 * comes from the envelope's `owner_reachable`, which the producer states ONCE
 * for the whole answer rather than per row.
 *
 * ## An absent field is `unknown`, never `foreign`
 *
 * An older server sends no `population` at all. The same rule applies one level
 * up: a missing key is not an answer, so it resolves to `unknown` — the outcome
 * that admits it does not know — and never to the one that makes a claim.
 */

import type { FleetAgent } from './fleetTypes'

export type TerminalOffer =
  /** A terminal exists at `label`; the surface may open it. */
  | { kind: 'available'; label: string }
  /** No terminal, and none can exist. A statement, and it is measured. */
  | { kind: 'foreign'; reason: string }
  /**
   * The framework STARTED this agent and no longer holds its terminal — task 5.5.
   *
   * A separate kind rather than a shade of `foreign`, because the two lead to
   * different actions and only one of them is recoverable. A pty master cannot
   * be reacquired from outside, so the terminal really is gone; but the scope is
   * still there, and `recover` can stop it and resume the session into a fresh
   * pty. Calling this `foreign` would say the framework did not start it — which
   * is false, and it would hide the one control that helps.
   */
  | { kind: 'orphaned'; reason: string; scope: string }
  /** We could not find out. NOT a statement that there is none. */
  | { kind: 'unknown'; reason: string }

export const FOREIGN_REASON =
  'the framework neither started nor holds it — a terminal cannot be attached to a running foreign session'

export const OWNER_DOWN_REASON =
  'the owner service did not answer, so we do not know whether it has a terminal'

export const OWNER_SILENT_REASON =
  'discovery did not say whose process this is — which is not a statement that it has no terminal'

export const ORPHANED_REASON =
  'the framework started it, but the terminal died with the owner that held it — a pty cannot be reattached, only replaced'

const NO_LABEL_REASON =
  'reported as the framework\'s own, but with no label attached — a contradiction, not an absence'

/**
 * The offer for one agent.
 *
 * `ownerReachable` is the envelope's top-level answer: `true`, `false`, or
 * `undefined` where the server does not say. It only ever changes the WORDING of
 * an `unknown`; it can never turn an `unknown` into a `foreign`, because "the
 * owner is up" is not evidence about a process the owner did not list.
 */
export function terminalOffer(
  agent: Pick<FleetAgent, 'population' | 'terminal_label'> & { scope?: string | null },
  ownerReachable?: boolean,
): TerminalOffer {
  if (agent.population === 'started-here') {
    // Measured, not assumed away: `started-here` with no label is a producer
    // contradiction. Rendering it as "no terminal" would file a bug as a fact.
    if (typeof agent.terminal_label === 'string' && agent.terminal_label !== '') {
      return { kind: 'available', label: agent.terminal_label }
    }
    return { kind: 'unknown', reason: NO_LABEL_REASON }
  }
  if (agent.population === 'orphaned') {
    // The scope is what makes recovery possible, so an `orphaned` without one
    // is a producer contradiction and must not render as a recoverable agent:
    // an offer whose action cannot be performed is worse than no offer.
    if (typeof agent.scope === 'string' && agent.scope !== '') {
      return { kind: 'orphaned', reason: ORPHANED_REASON, scope: agent.scope }
    }
    return { kind: 'unknown', reason: NO_LABEL_REASON }
  }
  if (agent.population === 'foreign') {
    return { kind: 'foreign', reason: FOREIGN_REASON }
  }
  return {
    kind: 'unknown',
    reason: ownerReachable === false ? OWNER_DOWN_REASON : OWNER_SILENT_REASON,
  }
}

/**
 * The websocket address of a terminal.
 *
 * Built from `location` rather than hard-coded, because the dev server proxies
 * `/ws` to whichever API port `SET_API_PORT` names, and a hard-coded port would
 * work in exactly one of the two setups this repo is developed in.
 */
export function terminalUrl(label: string, loc: { protocol: string; host: string } = window.location): string {
  const scheme = loc.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${scheme}//${loc.host}/ws/fleet/agents/${encodeURIComponent(label)}/terminal`
}

/** The `attached` acknowledgement, and the two ways an open can fail. */
export interface AttachedEvent {
  event: 'attached'
  attached: string
  replayed_bytes: number
  replay_truncated: boolean
  viewers: number
}

export interface RefusedEvent {
  event: 'unavailable' | 'refused'
  reason: string
}

export type TerminalEvent = AttachedEvent | RefusedEvent | { event: string; [k: string]: unknown }

/**
 * Parse one control frame.
 *
 * Returns `null` for anything that is not a JSON object with an `event` — a
 * terminal must never treat an unparseable control frame as a state change, and
 * the alternative (throwing inside a socket handler) takes the screen down.
 */
export function parseControl(text: string): TerminalEvent | null {
  try {
    const parsed: unknown = JSON.parse(text)
    if (parsed && typeof parsed === 'object' && typeof (parsed as { event?: unknown }).event === 'string') {
      return parsed as TerminalEvent
    }
  } catch {
    /* not a control frame */
  }
  return null
}
