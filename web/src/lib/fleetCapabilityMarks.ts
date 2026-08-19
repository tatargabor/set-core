import { type CapabilityReport, moduleStanding } from './fleetInstall'

/**
 * What a project's row says about its modules and where it was found — tasks 7.9
 * and AC-8.
 *
 * ## Why this is a function and not a few ternaries in the row
 *
 * The requirement's own sentence is the whole design: *"A capability that is
 * supported but not connected SHALL be reported as not connected, distinctly
 * from one that is unknown … 'Not wired in' invites wiring it in; 'unknown' does
 * not."* Those are three states, not a boolean, and the state that must never be
 * silently produced is the fourth one — **not measured at all**.
 *
 * That fourth state is why `moduleStanding` is reused rather than re-derived. A
 * server that sent no report and a project with nothing installed both arrive as
 * "no capabilities to draw"; drawing an empty strip for either says *measured,
 * and there is nothing*, which is a gap rendered as a zero.
 */

export type MarkTone = 'connected' | 'partial' | 'not-connected' | 'unknown'

export interface CapabilityMark {
  name: string
  tone: MarkTone
  /** The sentence the reader gets on hover — the state, and its reason if one was given. */
  title: string
}

export type CapabilityStanding =
  /** Nobody looked, or the look failed. NOT the same as "no modules". */
  | { kind: 'unmeasured'; note: string }
  /** Measured, and there is genuinely nothing to draw. */
  | { kind: 'none' }
  | { kind: 'marks'; marks: CapabilityMark[]; notConnected: number; unknown: number }

const KNOWN: Record<string, MarkTone> = {
  connected: 'connected',
  partial: 'partial',
  'not-connected': 'not-connected',
  unknown: 'unknown',
}

/**
 * A state the producer sends that this screen does not know becomes `unknown`,
 * never `connected`. The fail direction is the point: an unrecognised state
 * drawn as connected stops offering a capability the project could have, and
 * does it silently.
 */
export function toneOf(state: string): MarkTone {
  return KNOWN[state] ?? 'unknown'
}

export function capabilityStanding(report: CapabilityReport | null | undefined): CapabilityStanding {
  const standing = moduleStanding(report)
  if (standing.kind === 'unmeasured') return { kind: 'unmeasured', note: standing.note }
  const caps = report?.capabilities ?? []
  if (caps.length === 0) return { kind: 'none' }
  const marks = caps.map(c => {
    const tone = toneOf(String(c.state))
    const counted = typeof c.present === 'number' && typeof c.total === 'number'
      ? ` ${c.present}/${c.total} file(s)`
      : ''
    // The producer's own reason, verbatim where it gave one. It is the half that
    // says what to do about the state — an inference marked as an inference, a
    // version the project expects and does not have.
    const why = typeof c.reason === 'string' && c.reason.trim() ? ` — ${c.reason.trim()}` : ''
    return { name: c.name, tone, title: `${c.name}: ${String(c.state).replace('-', ' ')}${counted}${why}` }
  })
  return {
    kind: 'marks',
    marks,
    notConnected: marks.filter(m => m.tone === 'not-connected').length,
    unknown: marks.filter(m => m.tone === 'unknown').length,
  }
}

/**
 * Readable short names, because the obvious `slice(0, 3)` produced `mes` for
 * `messaging` — a rendered abbreviation nobody can expand is a label that costs
 * space and gives nothing back. An unknown source still falls back to a slice
 * rather than being dropped: a source this screen does not recognise is exactly
 * the one worth naming.
 */
const SHORT: Record<string, string> = {
  registry: 'reg',
  messaging: 'msg',
  process: 'live',
}

export function shortSource(name: string): string {
  return SHORT[name] ?? name.slice(0, 4)
}

/**
 * The sources that knew about a project — AC-8.
 *
 * Returned only when there is more than one, because that is what the criterion
 * asks for and because a single source on every row is noise that makes the
 * interesting rows harder to find. The list is NOT merged or ranked: the point
 * of the union is that a project known to the registry and to a live process is
 * a different fact from one known to only one of them.
 */
export function extraSources(sources: readonly string[] | undefined): string[] {
  const seen = Array.isArray(sources) ? sources.filter(s => typeof s === 'string' && s.trim()) : []
  const unique = [...new Set(seen)]
  return unique.length > 1 ? unique : []
}
