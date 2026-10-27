/**
 * The question relay's header control — the pure half.
 *
 * The relay itself is a hook in every agent session (`set-hook-question-relay`); the
 * fleet only shows its switch, whether this machine's configuration is complete, and
 * which questions are waiting on the chat channel right now. Kept pure so the
 * wording and the "can this be turned on" rule are tested without a screen.
 */

export interface WaitingQuestion {
  session_id: string
  project: string | null
  questions: number | null
  target: string | null
  seconds: number | null
  release_requested: boolean
}

export interface RelayState {
  enabled: boolean
  target: string | null
  missing: string[]
  ready: boolean
  waiting: WaitingQuestion[]
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
      return `Question relay ON — agents' blocking questions go to ${where}. Click to turn off.`
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
  }
}
