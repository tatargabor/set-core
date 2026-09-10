/**
 * How full each live agent's context window is, as marks for the fleet header.
 *
 * The decisions live here as pure functions rather than inside the component,
 * so each can be asserted in both directions — the same shape `fleetUsageBars`
 * and `fleetCacheHeat` use, for the same reason.
 *
 * ## This is per agent where the quota strip is per account
 *
 * `fleet-usage-bars` forbids attaching a quota mark to an agent, and the reason
 * is a measurement: account quota has no per-seat identity to join on, so a
 * per-tab quota mark would render most agents as consuming nothing. Context
 * inverts every term of that argument — it is read from the agent's OWN
 * transcript, so it needs no join and has no attribution gap.
 *
 * ## Nothing here derives a fraction
 *
 * The fill and the window arrive from the server already computed. This module
 * must never hold a model→window table or divide tokens by a window: two tables
 * are two chances to disagree, and a header contradicting the payload leaves the
 * reader unable to tell which to believe. Percentages below are FORMATTING of a
 * fraction the server stated, never a re-derivation of it.
 */

/** The `context` block the fleet API attaches to an agent. Always present. */
export interface AgentContext {
  /** `measured` is the only state carrying figures. */
  state: 'measured' | 'unmeasured'
  tokens?: number
  window?: number
  /** 0..1, from the server. NOT clamped — over 1 means the proxy over-counted. */
  fill?: number
  model?: string
  band?: 'normal' | 'warning' | 'critical'
  /** Why there are no figures. Present on `unmeasured`. */
  reason?: string
}

/**
 * The little of an agent this module needs.
 *
 * `pid` rather than the name is the identity: a name is `string | null` on a
 * real agent, so two unnamed agents would collide as one mark and the header
 * would draw a fleet smaller than it is.
 */
export interface ContextAgent {
  pid: number
  name: string | null
  context?: AgentContext | null
}

/** What to call an agent that has no name. Never an empty label. */
export function agentLabel(a: ContextAgent): string {
  return a.name && a.name.trim() ? a.name : `pid ${a.pid}`
}

export type ContextMark =
  | {
      kind: 'measured'
      /** Stable identity for a React key — a name may be null or repeated. */
      pid: number
      name: string
      /** 0..1 as the server stated it. */
      fill: number
      /** How much bar to draw: the fill, clamped for LAYOUT only. */
      drawn: number
      /** True when fill exceeded the window — the bar cannot show it, so the mark says it. */
      over: boolean
      tone: string
      title: string
    }
  | { kind: 'unmeasured'; pid: number; name: string; title: string }

export interface ContextStripState {
  /** Fullest first, capped. */
  marks: ContextMark[]
  /** Measured agents the cap did not draw. Every one is emptier than every drawn mark. */
  overflow: number
  /** Agents whose fill could not be measured at all. */
  unmeasured: number
  /** Live agents considered, measured or not. */
  total: number
}

/**
 * How many bars the header draws before it starts counting instead.
 *
 * A layout number, chosen by looking at the real header rather than reasoned
 * about: see the task that fixes it. The cap is only safe because the marks are
 * ordered by fullness — see `contextStrip`.
 */
export const MAX_MARKS = 6

/** Band → the bar's colour. One mapping, so no two marks disagree. */
const TONES: Record<string, string> = {
  normal: 'bg-emerald-500',
  warning: 'bg-amber-400',
  critical: 'bg-red-500',
}

function thousands(n: number): string {
  return n.toLocaleString('en-US')
}

/**
 * The sentence a drawn mark carries.
 *
 * It names the tokens, the window and the model — and states that the count is
 * a PROXY. The figure is the cache read plus cache creation of the last
 * request: it tracks context closely enough to draw and is not the same
 * quantity, and a screen implying otherwise invites a decision the measurement
 * does not support.
 */
export function markTitle(name: string, c: AgentContext): string {
  const pct = Math.round((c.fill ?? 0) * 100)
  const over = (c.fill ?? 0) > 1
  return (
    `${name}: ${thousands(c.tokens ?? 0)} of ${thousands(c.window ?? 0)} tokens (${pct}%)`
    + ` · ${c.model ?? 'model not named'}`
    + (over ? ' — over its window: the proxy counted more than the window holds.' : '')
    + ' The token figure is a PROXY for context size: it is the cache read plus cache'
    + ' creation of the last request, not a context measurement the runtime published.'
  )
}

/** The sentence an unmeasured mark carries — it names why, never a number. */
export function unmeasuredTitle(name: string, c: AgentContext | null | undefined): string {
  return (
    `${name}: context fill not measured — ${c?.reason ?? 'this agent carries no context record'}.`
    + ' Not measured is not the same as nothing consumed, so no bar is drawn.'
  )
}

/**
 * The header's marks, capped, with everything the cap left out still counted.
 *
 * ⚠ The ordering is what makes the cap safe rather than merely tidy. Marks are
 * drawn FULLEST FIRST, so every agent hidden behind the overflow count is
 * emptier than every agent shown — which is what lets a reader conclude from the
 * visible marks alone that nothing worse is hidden. A cap ordered by name or by
 * start time would let the fullest agent be the hidden one, which is exactly the
 * place a failure sits while the screen looks calm.
 *
 * Unmeasured agents are COUNTED, never dropped: an agent silently omitted is
 * indistinguishable from an agent that does not exist.
 */
export function contextStrip(
  agents: ContextAgent[] | null | undefined,
  cap: number = MAX_MARKS,
): ContextStripState {
  const live = agents ?? []
  const measured: Array<{ agent: ContextAgent; c: AgentContext }> = []
  let unmeasured = 0

  for (const a of live) {
    const c = a.context
    if (c && c.state === 'measured' && typeof c.fill === 'number') {
      measured.push({ agent: a, c })
    } else {
      unmeasured += 1
    }
  }

  measured.sort((x, y) => (y.c.fill ?? 0) - (x.c.fill ?? 0))
  const drawn = measured.slice(0, Math.max(0, cap))

  const marks: ContextMark[] = drawn.map(({ agent, c }) => {
    const fill = c.fill ?? 0
    return {
      kind: 'measured' as const,
      pid: agent.pid,
      name: agentLabel(agent),
      fill,
      // Clamped for LAYOUT only — a bar cannot be wider than its track. The
      // `over` flag keeps the fact that the figure exceeded the window, which
      // clamping alone would silently swallow.
      drawn: Math.max(0, Math.min(1, fill)),
      over: fill > 1,
      tone: TONES[c.band ?? 'normal'] ?? TONES.normal,
      title: markTitle(agentLabel(agent), c),
    }
  })

  return {
    marks,
    overflow: measured.length - drawn.length,
    unmeasured,
    total: live.length,
  }
}

/** The overflow count's sentence — it must say the hidden ones are emptier. */
export function overflowTitle(n: number): string {
  return (
    `${n} more agent${n > 1 ? 's' : ''} with a measured context fill, not drawn.`
    + ' The marks shown are the fullest, so every agent behind this count is emptier'
    + ' than every one displayed.'
  )
}
