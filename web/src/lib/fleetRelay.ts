/**
 * The question relay's header control — the pure half.
 *
 * The relay itself is a hook in every agent session (`set-hook-question-relay`); the
 * fleet only shows its switch, whether this machine's configuration is complete, and
 * which questions are waiting on the chat channel right now. Kept pure so the
 * wording and the "can this be turned on" rule are tested without a screen.
 */

export interface WaitingQuestion {
  /** The relayed call's id — what the send-the-proposal button posts to. */
  id?: string | null
  session_id: string
  project: string | null
  questions: number | null
  target: string | null
  seconds: number | null
  release_requested: boolean
  /** question | permission | continuation — absent on an older server. */
  kind?: string | null
  /** fleet-auto-answer: the decider's verdict on this call; absent when it has none. */
  auto_answer?: AutoVerdict | null
}

export interface AutoVerdict {
  state: string | null
  outcome: string | null
  reason: string
  choice: string | null
  tier: string | null
  seconds_left: number | null
}

/** The verdict in a few words, and its tone. `null` when the decider has no record. */
export function verdictLine(v: AutoVerdict | null | undefined): { text: string; tone: 'due' | 'held' | 'muted' } | null {
  if (!v) return null
  const choice = v.choice ? `«${v.choice.replace(/^\s*(?:→|->)\s*/, '')}»` : null
  if (v.state === 'cancelled') return { text: 'auto: cancelled — waits for you', tone: 'muted' }
  if (v.outcome === 'allowed' && v.seconds_left !== null)
    return { text: `auto: writes ${choice ?? 'its answer'} in ${Math.max(0, Math.round(v.seconds_left))}s`, tone: 'due' }
  if (v.outcome === 'excluded')
    return { text: `auto: not written — ${v.reason || 'outward step'}${choice ? `; it proposed ${choice}` : ''}`, tone: 'held' }
  if (v.outcome === 'below-bar')
    return { text: `auto: below the bar${choice ? ` — ${choice}` : ''}`, tone: 'muted' }
  if (v.outcome === 'no-decision') return { text: 'auto: no decision — the sources do not settle it', tone: 'muted' }
  if (v.outcome === 'permission') return { text: 'auto: permissions are never answered', tone: 'muted' }
  return { text: `auto: ${v.outcome ?? v.state ?? 'deciding'}`, tone: 'muted' }
}

/** A registered project whose settings do not wire one or both relay hooks (B-182). */
export interface UnwiredProject {
  project: string
  missing: string[]
}

export interface RelayState {
  enabled: boolean
  target: string | null
  missing: string[]
  ready: boolean
  waiting: WaitingQuestion[]
  /** Projects whose sessions bypass the relay — their questions stay in the terminal. */
  unwired: UnwiredProject[]
}

export type RelayMode = 'on' | 'off' | 'not-ready' | 'on-not-ready'

/**
 * `on-not-ready` is real: the switch is a local config key a person can set by hand
 * while a required key is missing. The hook then releases every question, and the
 * header must say so rather than show a calm "on".
 */
export function relayMode(state: RelayState): RelayMode {
  if (state.enabled) return state.ready ? 'on' : 'on-not-ready'
  return state.ready ? 'off' : 'not-ready'
}

/** Clicking the switch flips it — except turning ON an incomplete relay, which opens the detail. */
export function canFlip(state: RelayState): boolean {
  return state.enabled || state.ready
}

export function relayTitle(state: RelayState): string {
  const where = state.target === 'webhook'
    ? 'a chat webhook (notify only — answers stay at the terminal)'
    : state.target === 'command'
      ? 'the chat bridge (two-way — the answer comes back to the agent)'
      : 'no outbound'
  switch (relayMode(state)) {
    case 'on':
      return state.unwired.length > 0
        ? `Question relay ON — but ${state.unwired.length} project(s) are not wired, and their questions stay in the terminal. Click to turn off.`
        : `Question relay ON — agents' blocking questions go to ${where}. Click to turn off.`
    case 'off':
      return `Question relay off — questions are answered at the terminal. Click to send them to ${where}.`
    case 'not-ready':
      return `Question relay not configured — missing ${state.missing.join(', ')}. Click for how to set it.`
    case 'on-not-ready':
      return `Question relay is ON but not configured — missing ${state.missing.join(', ')}; every question is released to the terminal.`
  }
}

/** The `set-config` lines that complete this machine's configuration. */
export function setupCommands(state: RelayState): string[] {
  const hint: Record<string, string> = {
    'question_relay.target': 'set-config set question_relay.target command   # or: webhook',
    'question_relay.command': 'set-config set question_relay.command "<bridge> be --json -"',
    'question_relay.audience': 'set-config set question_relay.audience <the audience your bridge forwards>',
    'question_relay.webhook_url': 'set-config set question_relay.webhook_url <https://…webhook URL>',
  }
  return state.missing.map(k => hint[k] ?? `set-config set ${k} <value>`)
}

/** Longest-waiting first: that is the one somebody has been away from longest. */
export function orderWaiting(waiting: WaitingQuestion[]): WaitingQuestion[] {
  return [...waiting].sort((a, b) => (b.seconds ?? -1) - (a.seconds ?? -1))
}

/**
 * The route's answer, or null when it does not have the shape this control renders.
 *
 * Measured: the Fleet page's render tests mock `fetch` for the whole page, and a
 * payload without `waiting` crashed the ENTIRE screen (187 tests) from inside this one
 * header control. A widget on the landing screen must degrade to "unreadable" on its
 * own, never take the page down with it.
 */
export function parseRelayState(d: unknown): RelayState | null {
  if (!d || typeof d !== 'object') return null
  const o = d as Record<string, unknown>
  if (typeof o.enabled !== 'boolean' || typeof o.ready !== 'boolean') return null
  if (!Array.isArray(o.missing) || !Array.isArray(o.waiting)) return null
  const waiting = (o.waiting as unknown[]).filter(
    (w): w is WaitingQuestion => !!w && typeof w === 'object' && typeof (w as WaitingQuestion).session_id === 'string')
  return {
    enabled: o.enabled,
    ready: o.ready,
    target: typeof o.target === 'string' ? o.target : null,
    missing: (o.missing as unknown[]).filter((m): m is string => typeof m === 'string'),
    waiting,
    // Absent on an older server: an empty list, never a crash (see above).
    unwired: Array.isArray(o.unwired)
      ? (o.unwired as unknown[]).filter((u): u is UnwiredProject =>
          !!u && typeof u === 'object' && typeof (u as UnwiredProject).project === 'string'
          && Array.isArray((u as UnwiredProject).missing))
      : [],
  }
}

/**
 * Whether the closed header must carry the unwired marker: only while the relay is ON.
 * Off, nothing is relayed anywhere, so an unwired project changes nothing.
 */
export function showUnwired(state: RelayState): boolean {
  return state.enabled && state.unwired.length > 0
}

/** The proposal the operator can send as their own answer with one click, or null. */
export function sendable(w: WaitingQuestion): { id: string; choice: string; label: string } | null {
  const v = w.auto_answer
  if (!v || !w.id || !v.choice || !v.choice.trim() || v.state === 'done' || w.release_requested) return null
  const choice = v.choice.replace(/^\s*(?:→|->)\s*/, '')
  return { id: w.id, choice, label: v.outcome === 'allowed' && v.seconds_left !== null ? 'send now' : 'send it' }
}
