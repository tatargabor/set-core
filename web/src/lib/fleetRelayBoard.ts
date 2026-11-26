/**
 * The relay board — the pure half (fleet-relay-board).
 *
 * Asked for by the owner (2026-11-26), from a screenshot of four truncated relay rows:
 * „vszeg egyből kellene mutatni egy nagy ablakban táblázatban hogy ne kelljen kattintani
 * tudjak dönteni és jól olvasható legyen". So the panel shows each waiting question in full,
 * its options as controls, and the decider's reason, and one click answers. Kept pure so the
 * choice list and the one-click rule are tested without a screen.
 */

import type { WaitingQuestion } from './fleetRelay'
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

/**
 * Where one waiting call stands (fleet-relay-board, row status).
 *
 * Owner, 2026-11-26: „jo lenne latni a sorokon melyik hol tart. pl megjott, hatterellenorzes
 * fut megvan, nekem kell majd valaszolnom … hatterszin vagy jol lathato jelzesekkel, ikonok,
 * text". One status per call, in this precedence; `yours` always says why.
 */
export type RowStatusKey = 'answered' | 'permission' | 'terminal' | 'due' | 'written' | 'reading' | 'yours'

export interface RowStatus {
  key: RowStatusKey
  icon: string
  word: string
  /** Why — on `yours` always; empty otherwise unless there is something to add. */
  why: string
  /** mine: the operator must act · auto: the machine is working on it · done · muted */
  tone: 'mine' | 'auto' | 'done' | 'muted'
}

/** Seconds past the decider's own bound before "decider reading" turns into "no verdict". */
export const READING_GRACE_S = 30

const YOURS_WHY: Record<string, string> = {
  excluded: 'outward step',
  held: 'another question of this call needs you',
  'below-bar': 'not sure enough to write it',
  'no-decision': 'no source settles it',
  allowed: 'its proposal waits for you',
}
const YOURS_ORDER = ['excluded', 'no-decision', 'below-bar', 'held', 'allowed']

const yours = (why: string): RowStatus => ({ key: 'yours', icon: '✋', word: 'your answer', why, tone: 'mine' })

export function rowStatus(w: WaitingQuestion, d: RelayDetail | null, sentOk: boolean,
                          decideBound: number | null | undefined): RowStatus {
  if (sentOk) return { key: 'answered', icon: '✓', word: 'answered', why: 'sent from here; the agent continues', tone: 'done' }
  const kind = d?.kind ?? w.kind
  if (kind === 'permission')
    return { key: 'permission', icon: '🔒', word: 'permission', why: 'never answered automatically — Allow or Deny at the channel or the terminal', tone: 'mine' }
  if (d?.release_requested || w.release_requested)
    return { key: 'terminal', icon: '↩', word: 'to terminal', why: 'answer it at the agent\'s terminal', tone: 'muted' }

  const v = w.auto_answer ?? null
  const state = d?.decider?.state ?? v?.state ?? null
  const outcomes = (d?.decider?.questions ?? []).map(q => q.outcome).filter((o): o is string => !!o)
  if (outcomes.length === 0 && v?.outcome) outcomes.push(v.outcome)
  const left = d?.decider ? d.decider.seconds_left : v?.seconds_left ?? null

  if (state === 'cancelled') return yours('the automatic answer was cancelled')
  if (outcomes.length > 0) {
    const allAllowed = outcomes.every(o => o === 'allowed')
    if (allAllowed && left !== null && left !== undefined)
      return { key: 'due', icon: '⏱', word: `auto in ${Math.max(0, Math.round(left))} s`, why: 'writes its proposal unless you answer first', tone: 'auto' }
    if (allAllowed && state === 'done')
      return { key: 'written', icon: '✓', word: 'auto written', why: 'the agent continues', tone: 'done' }
    const first = YOURS_ORDER.find(o => outcomes.includes(o))
    return yours(first ? YOURS_WHY[first] : outcomes[0])
  }

  if (w.auto_on === false) return yours(w.auto_off === 'agent' ? 'auto off for this agent' : 'auto answering is off')
  if (w.auto_on === undefined) return yours('no verdict from the decider')
  const bound = (decideBound ?? 120) + READING_GRACE_S
  if (w.seconds === null || w.seconds < bound)
    return { key: 'reading', icon: '⟳', word: 'decider reading', why: 'a proposal or a reason comes within a minute or two', tone: 'auto' }
  return yours('the decider gave no verdict')
}

/** The heading's count per status, in display order, zero counts left out. */
export function statusCounts(statuses: RowStatus[]): { key: RowStatusKey; icon: string; label: string; n: number; tone: RowStatus['tone'] }[] {
  const order: [RowStatusKey, string][] = [
    ['yours', 'yours'], ['permission', 'permission'], ['reading', 'decider reading'], ['due', 'auto due'],
    ['written', 'auto written'], ['answered', 'answered'], ['terminal', 'to terminal'],
  ]
  return order
    .map(([key, label]) => {
      const hit = statuses.filter(s => s.key === key)
      return { key, label, n: hit.length, icon: hit[0]?.icon ?? '', tone: hit[0]?.tone ?? 'muted' }
    })
    .filter(c => c.n > 0)
}
