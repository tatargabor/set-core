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
 * pid → the terminal label the OWNER last confirmed for it.
 *
 * B-30, second half. When the owner cannot be asked, every agent comes back
 * `unknown` and its `terminal_label` is `null` — the server has nowhere to get
 * it from, and inventing one there would be a false value. So the client keeps
 * the last CONFIRMED pairing instead, and uses it for one purpose only: not
 * closing a terminal that is already open.
 *
 * `ownerAnswered` decides whether this is a measurement or a memory:
 *
 *  - **answered** → the map is rebuilt from the answer. A pid the owner did not
 *    list drops out, because `foreign` and `orphaned` are statements, and a
 *    statement outranks a memory. This is what stops the memory going stale.
 *  - **not answered** → the map is returned unchanged. Rebuilding it from an
 *    answer nobody gave would empty it, which is the very absence this exists
 *    to refuse.
 */
export type LabelMemory = Readonly<Record<number, string>>

export function rememberTerminalLabels(
  prev: LabelMemory,
  agents: ReadonlyArray<Pick<FleetAgent, 'pid' | 'population' | 'terminal_label'>>,
  ownerAnswered: boolean,
): LabelMemory {
  if (!ownerAnswered) return prev
  const next: Record<number, string> = {}
  for (const a of agents) {
    if (a.population === 'started-here' && typeof a.terminal_label === 'string' && a.terminal_label) {
      next[a.pid] = a.terminal_label
    }
  }
  return next
}

/**
 * The offer, with an OPEN terminal kept open across an unanswered poll.
 *
 * Narrow on purpose, in both directions:
 *
 *  - only `unknown` is upgraded. `foreign` and `orphaned` are the owner *saying*
 *    something, and a memory must never overrule an answer;
 *  - only while the terminal is already OPEN. Offering to open one from memory
 *    would be an offer whose action may not be performable — the thing this file
 *    already refuses to do for `started-here` without a label.
 *
 * What makes this honest rather than a guess: the socket is the authority. A
 * pane kept open is not a claim that the agent is alive; it is a pane whose
 * WebSocket will say `closed` the moment it is not. The screen also states the
 * cause where the reader is standing — the header carries *the owner service is
 * not answering* for exactly this condition.
 */
export function offerWithRemembered(
  offer: TerminalOffer,
  remembered: string | undefined,
  open: boolean,
): TerminalOffer {
  if (offer.kind !== 'unknown' || !open || !remembered) return offer
  return { kind: 'available', label: remembered }
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

/**
 * The address a link in the terminal output should open, or `null` for one that
 * must not be opened at all — asked for on 2026-08-20: *"terminal ablakban URL
 * nyitható legyen uj lapon"*.
 *
 * A pure function rather than a closure inside the component, so the one part
 * that can be wrong without looking wrong — WHICH schemes are followed — is
 * testable without a browser. The opening itself (a new tab, `noopener`) is the
 * component's job and is a browser fact.
 *
 * **The terminal's text is data, not an instruction.** It is written by whatever
 * the agent ran, so a scheme that can execute something in the dashboard's own
 * origin — `javascript:`, `data:`, `file:`, a custom app scheme — is refused.
 * Only `http` and `https` survive, and the decision is made by parsing the URL
 * rather than by testing a prefix of a string the agent chose: `http:evil` and
 * a leading-whitespace `  javascript:` both defeat a prefix test.
 */
export function terminalLinkTarget(uri: string): string | null {
  let parsed: URL
  try {
    parsed = new URL(uri)
  } catch {
    return null
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null
  return parsed.href
}

/** The `attached` acknowledgement, and the two ways an open can fail. */
export interface AttachedEvent {
  event: 'attached'
  attached: string
  replayed_bytes: number
  replay_truncated: boolean
  viewers: number
  /**
   * The pty's geometry at the moment of attaching — B-16.
   *
   * The buffered screen is bytes a program laid out for a specific number of
   * columns, and a terminal is a fixed-grid device: rendering that tail at a
   * different width destroys the layout instead of adapting it, silently,
   * because the result still looks like a terminal.
   *
   * `null` where the owner could not read the fd. The viewer then leaves its
   * own size alone rather than applying a guess.
   */
  rows: number | null
  cols: number | null
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

/**
 * Whether a keystroke is asking for the SELECTION to be copied.
 *
 * `Ctrl+C` is deliberately not it, and that is the decision rather than an
 * omission: in a terminal `Ctrl+C` is `SIGINT`, and the agents on this screen are
 * long-running sessions for which an accidental interrupt costs real work. So the
 * copy key is the one every Linux terminal emulator already uses for it —
 * `Ctrl+Shift+C` — plus `Ctrl+Insert`, which is the same act on a keyboard that
 * has the key.
 *
 * Measured 2026-08-22, and it is why this exists at all: nothing in the terminal
 * copied. xterm's own `copy` listener needs a browser-initiated copy, and the core
 * swallows `Ctrl+C` into the pty before the browser ever gets there
 * (`evaluateKeyboardEvent` → `triggerDataEvent` → `preventDefault`). So the
 * keystroke has to be intercepted ahead of the emulator, which is what
 * `attachCustomKeyEventHandler` is for.
 */
export function isCopyRequest(e: Pick<KeyboardEvent, 'type' | 'ctrlKey' | 'shiftKey' | 'metaKey' | 'key'>): boolean {
  if (e.type !== 'keydown') return false
  const mod = e.ctrlKey || e.metaKey
  if (!mod) return false
  if (e.shiftKey && (e.key === 'C' || e.key === 'c')) return true
  return !e.shiftKey && e.key === 'Insert'
}

/**
 * Whether the agent's program has taken the mouse — and therefore whether the
 * reader has to hold Shift to select anything.
 *
 * Read from xterm's OWN class rather than tracked here: the emulator sets
 * `enable-mouse-events` on its root element exactly while an application-level
 * mouse protocol is active, so this is the state itself and not a second copy of
 * it. Measured on a live agent 2026-08-22 — the class was present, a plain drag
 * selected nothing (`.xterm-selection` empty), and a shift+triple-click selected
 * the line. Without the hint that reads as a broken terminal, which is what was
 * reported.
 */
export const MOUSE_TRACKING_CLASS = 'enable-mouse-events'

export function mouseIsTakenByAgent(el: Element | null | undefined): boolean {
  return !!el?.classList.contains(MOUSE_TRACKING_CLASS)
}

/** What a copy attempt did. `null` is "nothing was selected", not a failure. */
export type CopyOutcome = { ok: true; chars: number } | { ok: false; reason: string } | null

/**
 * Put the selection on the clipboard, and SAY what happened.
 *
 * The outcome is returned rather than swallowed because a clipboard write can be
 * refused — an unfocused document, a browser policy — and a copy that silently
 * did nothing is the false-absence shape: the reader pastes the PREVIOUS
 * clipboard content somewhere and finds out much later.
 */
export async function copySelection(
  text: string,
  write: (t: string) => Promise<void> = t => navigator.clipboard.writeText(t),
  timeoutMs = CLIPBOARD_TIMEOUT_MS,
  later: (fn: () => void, ms: number) => unknown = (fn, ms) => setTimeout(fn, ms),
): Promise<CopyOutcome> {
  if (!text) return null
  try {
    // A clipboard write that NEVER SETTLES is the worst of the three outcomes,
    // and it is not hypothetical: measured 2026-08-22, `writeText` called from a
    // context the browser did not consider focused hung for 45 s and returned
    // nothing at all. An unsettled promise announces nothing, so the screen would
    // sit silent — which is exactly the false absence this function exists to
    // refuse. A race turns "no answer" into an answer.
    await Promise.race([
      write(text),
      new Promise<never>((_, reject) => later(() => reject(new Error('the clipboard did not answer')), timeoutMs)),
    ])
    return { ok: true, chars: text.length }
  } catch (e) {
    return { ok: false, reason: String((e as Error)?.message ?? e) }
  }
}

/** Long enough for a real write, short enough that the reader is not left waiting. */
export const CLIPBOARD_TIMEOUT_MS = 2000
