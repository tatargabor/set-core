/**
 * What an agent SAYS about itself, and what it is working towards — tasks 3.4,
 * 3.5 and 3.9, as decisions rather than as JSX.
 *
 * Two things are kept apart here that a tile would otherwise merge, and each
 * merge is a defect this repository has already paid for:
 *
 * **A declaration is not a measurement.** `state` is measured from the session
 * log; `declared.*` is a sentence the agent wrote. They can disagree, and the
 * disagreement is information — so nothing here lets a declaration overwrite,
 * soften or stand in for the measured state.
 *
 * **`blocked` does not contradict `state`.** An agent can be measured `working`
 * and declare itself blocked in the same moment — a detour while an answer is
 * outstanding. Measured live on this machine 2026-08-19: pid 1433849 was
 * `state: quiet` with `declared.blocked: true` and `phase: "blocked"`, which the
 * tile drew as a calm session. That pair is the case worth surfacing, and
 * folding the two fields into one makes it unsayable.
 *
 * **Absence has three shapes, not one.** `known: false` (the bus could not be
 * asked), a seat that declared nothing, and no seat at all are three different
 * facts. Only the middle one is a statement about the agent.
 *
 * ⚠ **CONFIDENTIALITY — this module reads, it never writes.** `focus` is a
 * sentence about work that may be a consumer's and `files` are that project's
 * paths; one live focus named a partner company and an unpaid invoice. Nothing
 * here may be put in `localStorage`, a log, a cache, or any state that outlives
 * the render — `CLAUDE.md`'s boundary is persistence, not display.
 */

import type { FleetAgent } from './fleetTypes'

export type DeclaredStanding =
  /** The bus could not be asked. NOT "the agent said nothing". */
  | { kind: 'unasked' }
  /** Asked, and this agent declares nothing about itself. A fact about it. */
  | { kind: 'silent' }
  | {
      kind: 'declared'
      focus: string | null
      phase: string | null
      blocked: boolean
      files: string[]
      at: string | null
      /** Age of the declaration in seconds, or `null` with no usable timestamp. */
      ageSeconds: number | null
    }

/**
 * How old a declaration is.
 *
 * Carried because **a declaration does not expire on its own**: an agent that
 * said "blocked, waiting on an answer" four hours ago and has said nothing
 * since is not making a claim about now. The age is what lets a reader weigh
 * it, and it is deliberately not turned into a staleness verdict here — a
 * threshold would discard true positives first, which is the trade §3.8 already
 * refused for the record's own timestamps.
 */
export function declarationAge(at: string | null | undefined, now = Date.now()): number | null {
  if (!at) return null
  const t = new Date(at).getTime()
  return Number.isNaN(t) ? null : Math.max(0, Math.round((now - t) / 1000))
}

export function declaredStanding(agent: Pick<FleetAgent, 'declared'>, now = Date.now()): DeclaredStanding {
  const d = agent.declared
  if (!d || d.known === false) return { kind: 'unasked' }
  const focus = d.focus?.trim() ? d.focus : null
  const phase = d.phase?.trim() ? d.phase : null
  const files = Array.isArray(d.files) ? d.files : []
  const blocked = d.blocked === true
  if (!focus && !phase && !blocked && files.length === 0) return { kind: 'silent' }
  return { kind: 'declared', focus, phase, blocked, files, at: d.declared_at ?? null, ageSeconds: declarationAge(d.declared_at, now) }
}

/**
 * Whether the tile must show a declared block BESIDE the measured state.
 *
 * True whenever the agent declares itself blocked — including, and especially,
 * when the measurement says something calm. The point is not to correct the
 * measurement: `state` stays exactly what it was, and this rides next to it.
 */
export function declaresBlocked(standing: DeclaredStanding): boolean {
  return standing.kind === 'declared' && standing.blocked
}

/**
 * Whether that block CONTRADICTS what was measured — the pair worth pointing at.
 *
 * `waiting` already tells the reader somebody is expected, so a declared block
 * beside it adds a reason, not a surprise. A block beside `quiet` or `working`
 * is the case a tile would otherwise render as nothing to do.
 */
export function blockUnexpectedFrom(state: string, standing: DeclaredStanding): boolean {
  return declaresBlocked(standing) && state !== 'waiting'
}

export type PurposeStanding =
  /** The engine has no record for this agent. Stated, never drawn as empty. */
  | { kind: 'no-record' }
  | {
      kind: 'purpose'
      change: string
      group: string | null
      status: string
      /** The record claims a live run whose pid is held by something else. */
      pidUnverified: boolean
      /** `null` when the task file could not be counted — never a zero. */
      progress: { done: number; total: number; fraction: number | null } | null
    }

export function purposeStanding(agent: Pick<FleetAgent, 'purpose'>): PurposeStanding {
  const p = agent.purpose
  if (!p || !p.change) return { kind: 'no-record' }
  const pr = p.progress
  return {
    kind: 'purpose',
    change: p.change,
    group: p.group ?? null,
    status: p.status ?? 'stale',
    pidUnverified: p.pid_unverified === true,
    // `measured: false` means the task file could not be counted. A `0/0` would
    // draw a progress bar for a change nobody has measured, which looks exactly
    // like a change nobody has started.
    progress: pr && pr.measured ? { done: pr.done, total: pr.total, fraction: pr.fraction } : null,
  }
}

/**
 * Whether an agent can be given an instruction, and the sentence to show where
 * the input would be when it cannot — task 4.4.
 *
 * An absent `instructable` is *unknown*, not *no*: an older server sends
 * neither field, and rendering that as a refusal would remove the input from
 * every agent on a server that simply predates the feature.
 */
export type Instructability =
  | { kind: 'yes'; seat: string | null }
  | { kind: 'no'; reason: string }
  | { kind: 'unknown' }

export function instructability(agent: Pick<FleetAgent, 'instructable' | 'reason' | 'seat'>): Instructability {
  if (agent.instructable === true) return { kind: 'yes', seat: agent.seat ?? null }
  if (agent.instructable === false) {
    return { kind: 'no', reason: agent.reason?.trim() || 'this agent has no address on the messaging bus' }
  }
  return { kind: 'unknown' }
}
