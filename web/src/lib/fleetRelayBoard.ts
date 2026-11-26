/**
 * The relay board — the pure half (fleet-relay-board).
 *
 * Asked for by the owner (2026-11-26), from a screenshot of four truncated relay rows:
 * „vszeg egyből kellene mutatni egy nagy ablakban táblázatban hogy ne kelljen kattintani
 * tudjak dönteni és jól olvasható legyen". So the panel shows each waiting question in full,
 * its options as controls, and the decider's reason, and one click answers. Kept pure so the
 * choice list and the one-click rule are tested without a screen.
 */

import type { DetailQuestion, RelayDetail } from './fleetRelayTeach'

export interface BoardChoice {
  /** What is sent — exactly the option text, so the agent sees its own option back. */
  value: string
  /** What is shown: a continuation's `→ ` mark dropped. */
  label: string
  proposed: boolean
  recommended: boolean
}

const MARK = /^\s*(?:→|->)\s*/
const strip = (s: string): string => s.replace(MARK, '').trim()

/** The question's options, plus the decider's proposal when it is not one of them. */
export function boardChoices(q: DetailQuestion): BoardChoice[] {
  const proposal = q.choice && q.choice.trim() ? q.choice : null
  const out: BoardChoice[] = q.options.map(o => ({
    value: o,
    label: strip(o),
    proposed: proposal !== null && strip(o) === strip(proposal),
    recommended: /\(recommended\)/i.test(o),
  }))
  if (proposal !== null && !out.some(c => c.proposed)) {
    out.push({ value: strip(proposal), label: strip(proposal), proposed: true, recommended: false })
  }
  return out
}

/** Whether a choice on this call answers the agent at once. */
export function oneClick(d: RelayDetail): boolean {
  return d.kind !== 'permission' && !d.release_requested && (d.decider?.questions.length ?? 0) === 1
}

/** Whether the board offers any answer control for the call. */
export function answerable(d: RelayDetail): boolean {
  return d.kind !== 'permission' && !d.release_requested
}

/** A several-question call is sent once every question holds an answer. */
export function readyToSend(picks: (string | undefined)[], count: number): boolean {
  return count > 0 && picks.length >= count && picks.slice(0, count).every(p => !!p && p.trim().length > 0)
}

/** The decider's verdict on one question, as a sentence a reader decides from. */
export function verdictSentence(q: DetailQuestion, secondsLeft: number | null): { text: string; tone: 'due' | 'held' | 'muted' } {
  const choice = q.choice ? `«${strip(q.choice)}»` : null
  const why = q.reason ? q.reason.replace(/^abstained:\s*/, '') : ''
  switch (q.outcome) {
    case null:
    case undefined:
      return { text: 'The decider is still reading it.', tone: 'muted' }
    case 'allowed':
      return secondsLeft !== null
        ? { text: `Writes ${choice ?? 'its answer'} in ${Math.max(0, Math.round(secondsLeft))} s unless you answer first.`, tone: 'due' }
        : { text: `Proposed ${choice ?? 'an answer'}.`, tone: 'due' }
    case 'excluded':
      return { text: `Proposed ${choice ?? 'an answer'}, not written: ${why || 'an outward step'}.`, tone: 'held' }
    case 'below-bar':
      return { text: `Proposed ${choice ?? 'an answer'}, not sure enough to write it (${why || 'below the bar'}).`, tone: 'held' }
    case 'held':
      return { text: `Proposed ${choice ?? 'an answer'}; another question of this call needs you.`, tone: 'held' }
    case 'no-decision':
      return { text: why ? `No proposal: ${why}` : 'No proposal: the sources do not settle it.', tone: 'muted' }
    default:
      return { text: `${q.outcome}${why ? `: ${why}` : ''}`, tone: 'muted' }
  }
}

/**
 * The answer one question sends: the picked option, a note written beside it, or both.
 * Owner, 2026-11-26: „a választás mellé … de csak felülírni tudom" — a note no longer
 * replaces the option; it travels with it.
 */
export function composeAnswer(pick: string | undefined, note: string | undefined): string {
  const p = (pick ?? '').trim()
  const n = (note ?? '').trim()
  if (p && n) return `${p} — ${n}`
  return p || n
}

export interface TaughtResult {
  written: boolean
  project: string
  rules_file: string
  commit: { sha: string; branch: string; reason: string }
}

/** The teach half of an answer's result, in one line; `ok` is false when the rule did not land. */
export function taughtLine(t: TaughtResult | null | undefined, count: number): { text: string; ok: boolean } | null {
  if (!t || count === 0) return null
  const what = count === 1 ? 'Rule' : `${count} rules`
  if (!t.written) return { text: `${what} not written: ${t.commit.reason || 'unknown reason'}`, ok: false }
  if (t.commit.sha) return { text: `${what} committed in ${t.project} (${t.commit.branch}) as ${t.commit.sha}. Not pushed.`, ok: true }
  return { text: `${what} written to ${t.project}/${t.rules_file}, not committed: ${t.commit.reason || 'unknown reason'}`, ok: false }
}
