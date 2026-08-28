/**
 * What is waiting, counted across an arrangement the user made themselves.
 *
 * D-2's third requirement, and it is the constraint that produced the decision
 * rather than a decoration on it. Manual ordering has no construction that
 * keeps a waiting project visible: automatic attention-ordering puts it on top
 * by definition, a workspace filter has a fixed tab strip to hang a count on, a
 * hand-made order has neither. A project dragged to position 30 six weeks ago is
 * below the fold today and nothing will move it. So the count lives in a header
 * that does not scroll, it counts across the parked section and every collapsed
 * group, and it can jump to the first one.
 *
 * ## The dangerous half: a zero the producer cannot make
 *
 * `waiting` is task 3.8. It WAS not implemented in discovery; measured
 * 2026-08-19 (morning) on 7451, all 22 live agents came back `quiet` and the
 * envelope had no `waiting` key at all — so the header said "not reported"
 * rather than "none", because a rendered `0 vár válaszra` would have been an
 * answer nobody gave.
 *
 * **Re-measured 2026-08-19 (afternoon), same server:** the envelope now carries
 * `waiting: 1` and one agent reports `state: "waiting"` with
 * `waiting_for: "input needed"`. The header therefore counts, and it started
 * counting with no change to this function — which is what the shape-reading
 * design was for. The refuted alternative is worth keeping: `!data.waiting`
 * would read a real `waiting: 0` as "not reported", so the check is `typeof
 * === 'number'`, not truthiness.
 *
 * ## The contradiction count
 *
 * `declaration_ignored` is the producer saying *the record claimed one state and
 * the log refuted it*. The measurement wins and `state` already holds the
 * result — so nothing downstream needs this to be correct. That is exactly why
 * it is counted: a contradiction the surface never renders is one nobody ever
 * fixes, and the field costs nothing to carry and everything to drop.
 */

export interface AttentionAgent {
  pid: number
  state: string
  /** Present where the record's declared state was refuted by the log. */
  declaration_ignored?: string | null
  /**
   * Is a person needed here — the ATTENTION axis, measured from the runtime's
   * own session record rather than from the log.
   *
   * Optional because a server that predates it sends nothing, and a missing
   * field must read as *not measured* rather than as any particular class.
   */
  attention?: string | null
  /**
   * How long this session has been waiting for a person with nothing running.
   *
   * `null` is not zero. Null says nobody is waiting, or the record carried no
   * stamp; zero would say *waiting, just now* and would sort and colour with
   * the calm ones.
   */
  input_wait_seconds?: number | null
}

/**
 * What a project is waiting on a HUMAN for — task 7.14.
 *
 * Deliberately separate from the agent counts below and never summed into
 * them. `waiting` counts a LIVE agent that asked a question; this counts work
 * with nobody standing on it. Measured on this machine 2026-08-19: a project
 * held two changes marked `running` since 12 June whose processes were long
 * gone and whose state file had not been touched since 24 July — 68 days of
 * "in progress" that was not. Counted by agents, that project rendered as
 * nothing to do.
 */
export interface AttentionAwaiting {
  /** The plan declares a step no agent can take (an API key, a DNS record). */
  manual?: string[]
  /** The engine recorded the change as stalled. */
  stalled?: string[]
  /** MEASURED: marked in flight, the recorded process is gone. */
  orphaned?: string[]
  /** Marked in flight, pid alive — a pid is not an identity. Named, not counted. */
  unverifiable?: string[]
  /** No orchestration state was found. NOT the same as "nothing awaits". */
  source_missing?: boolean
  total?: number
}

export interface AttentionProject {
  name: string
  agents: AttentionAgent[]
  awaiting?: AttentionAwaiting | null
}

export const WAITING = 'waiting'
export const WORKING = 'working'
export const UNKNOWN = 'unknown'
export const QUIET = 'quiet'
/**
 * Measured — a question tool is open, so the agent is stopped in front of a
 * person. Deliberately NOT called `blocked`: the envelope already carries
 * `declared.blocked`, which is the agent's own CLAIM that something holds it
 * up. One word for a declaration and a measurement in the same payload is the
 * ambiguity this file's own comments keep refusing.
 */
export const ASKING = 'asking'

/* -------------------------------------------------------------------------- *
 * The ATTENTION axis — see `set_orch/fleet/state.py` for the measurements.
 * -------------------------------------------------------------------------- */

/** Something is running: the model's turn is in flight. */
export const ATT_WORKING = 'working'
/** The prompt is free, but a backgrounded command is still running. */
export const ATT_BACKGROUND = 'background'
/** Waiting for a PERSON with nothing running — the class a reader acts on. */
export const ATT_INPUT = 'input'
/** Stopped at a permission prompt or a worker request. */
export const ATT_PROMPT = 'prompt'
/** The record could not answer. NEVER rendered as any of the four above. */
export const ATT_UNMEASURED = 'unmeasured'

/**
 * When an input wait starts being marked, and when it turns loud.
 *
 * These two numbers also live in `set_orch/fleet/state.py`, which sends them in
 * the envelope (`input_wait_thresholds`). These constants are the FALLBACK for
 * a server that does not send them, and a unit test asserts the two sides carry
 * the same values — a threshold written twice is two thresholds, and they drift
 * without anything failing.
 */
export const INPUT_WAIT_AMBER_SECONDS = 15
export const INPUT_WAIT_RED_SECONDS = 180
/**
 * Past this, a wait is ABANDONED rather than urgent — see `tone_for` in
 * `set_orch/fleet/state.py` for the measurement. The escalation rises to red
 * and then goes cold, because a monotonic one hands the loudest mark to the
 * most neglected session permanently: a project whose oldest agent has waited
 * two hours renders red forever, and the forty-second wait the reader is
 * actually working with never surfaces.
 */
export const INPUT_WAIT_PARKED_SECONDS = 900

export type InputWaitTone = 'plain' | 'amber' | 'red' | 'parked'

export interface InputWaitThresholds {
  amber_seconds?: number | null
  red_seconds?: number | null
  parked_seconds?: number | null
}

/**
 * Which band an input wait falls in — resolved on every render, not at fetch.
 *
 * The wait grows between polls. A tone computed on the server would sit stale on
 * screen for exactly as long as the poll interval, and on the three-minute
 * threshold that is where it matters most.
 *
 * `null` in, `null` out. A missing duration has no tone; substituting zero would
 * put an unmeasured wait in the calmest band, which is the false-absence
 * direction this screen refuses everywhere.
 */
export function inputWaitTone(
  seconds: number | null | undefined,
  thresholds?: InputWaitThresholds | null,
): InputWaitTone | null {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds)) return null
  const amber = typeof thresholds?.amber_seconds === 'number'
    ? thresholds.amber_seconds : INPUT_WAIT_AMBER_SECONDS
  const red = typeof thresholds?.red_seconds === 'number'
    ? thresholds.red_seconds : INPUT_WAIT_RED_SECONDS
  const parked = typeof thresholds?.parked_seconds === 'number'
    ? thresholds.parked_seconds : INPUT_WAIT_PARKED_SECONDS
  if (seconds >= parked) return 'parked'
  if (seconds >= red) return 'red'
  if (seconds >= amber) return 'amber'
  return 'plain'
}

/**
 * The tone a whole set of agents deserves — the STRONGEST one present.
 *
 * The user's rule, 2026-08-28: *"ha egy várakozó is van akkor kell a szín, a
 * legerősebb szín, azaz ha van piros az, ha sárga az"*. So the maximum wait
 * decides, and one waiting agent is enough — a project is never left uncoloured
 * because its other agents are busy.
 *
 * The case worth naming is a wait whose AGE was not measured: the record said
 * the prompt is free but carried no stamp. It resolves to **amber**, never to
 * nothing. Somebody is waiting either way, and silence is the one answer that
 * is certainly wrong.
 */
export function escalationTone(
  t: Pick<Tally, 'input' | 'prompt' | 'worstInputWaitSeconds'>,
  thresholds?: InputWaitThresholds | null,
): InputWaitTone | null {
  if (t.input + t.prompt === 0) return null
  if (t.worstInputWaitSeconds === null) return 'amber'
  return inputWaitTone(t.worstInputWaitSeconds, thresholds)
}

/**
 * Does this agent's class mean a person is being waited for?
 *
 * `background` is deliberately excluded and it is the whole point of the axis:
 * a session whose turn ended while a command runs in the background looks idle
 * from the log and is waiting for nobody.
 */
export function waitsForAPerson(agent: AttentionAgent): boolean {
  return agent.attention === ATT_INPUT || agent.attention === ATT_PROMPT
}

/**
 * The LONGEST wait in a set of agents, or null when nobody is waiting.
 *
 * The maximum rather than an average or the freshest: one busy agent must not
 * vouch for a project whose others have stopped, and the mean of a four-minute
 * wait and a five-second one is a number nobody is waiting.
 */
export function worstInputWait(
  agents: readonly AttentionAgent[],
  thresholds?: InputWaitThresholds | null,
): number | null {
  const parked = typeof thresholds?.parked_seconds === 'number'
    ? thresholds.parked_seconds : INPUT_WAIT_PARKED_SECONDS
  let worst: number | null = null
  for (const a of agents) {
    if (!waitsForAPerson(a)) continue
    const w = a.input_wait_seconds
    if (typeof w !== 'number' || !Number.isFinite(w)) continue
    // A parked wait is left out by construction. Letting it in is precisely
    // what made the oldest session own the row's colour forever.
    if (w >= parked) continue
    if (worst === null || w > worst) worst = w
  }
  return worst
}

/** Is this agent's wait past the point where nobody is coming for it? */
export function isParked(
  agent: AttentionAgent,
  thresholds?: InputWaitThresholds | null,
): boolean {
  if (!waitsForAPerson(agent)) return false
  const w = agent.input_wait_seconds
  if (typeof w !== 'number' || !Number.isFinite(w)) return false
  const parked = typeof thresholds?.parked_seconds === 'number'
    ? thresholds.parked_seconds : INPUT_WAIT_PARKED_SECONDS
  return w >= parked
}

export interface Tally {
  agents: number
  working: number
  unknown: number
  waiting: number
  /** Measured: a question tool is outstanding — see `ASKING`. */
  asking: number
  /** The turn ended and nothing is outstanding. Counted, never called idle. */
  quiet: number
  /**
   * Agents holding a state NO bucket above counts.
   *
   * The reason this exists rather than a silent fall-through: when `asking`
   * was added, every counter here was an `else if` chain with no final
   * branch, so a new state would have made agents vanish from the header
   * while `agents` still counted them — false absence, failing toward a calm
   * screen. This number is what makes the next new state visible instead.
   */
  unbucketed: number
  /** Agents whose declared state the log refuted — see the header of this file. */
  conflicts: number
  /** Work awaiting a human, with or without an agent — task 7.14. */
  awaiting: number
  /** Projects whose orchestration state could not be read at all. */
  unmeasured: number
  /* --- the ATTENTION axis, counted beside `state` and never mixed into it --- */
  /** Waiting for a person with nothing running. */
  input: number
  /** Stopped at a permission prompt or a worker request. */
  prompt: number
  /** The prompt is free, but a backgrounded command is running. */
  background: number
  /** An attention class no counter above knows — the same guard as `unbucketed`. */
  attentionUnbucketed: number
  /**
   * The session's loop is RUNNING, measured from the runtime's record.
   *
   * Kept apart from `working`, which counts `state === 'working'` — an
   * outstanding tool call in the LOG. The two are not the same set, and the gap
   * between them is what made this counter necessary: measured 2026-08-28, two
   * live sessions were `busy` in the record and `quiet` in the log at the same
   * instant, because the runtime flushes a turn's entries in batches. Counted by
   * `state` alone, a working project rendered with NO counter at all — no green,
   * no tone — which reads as "nothing is happening here".
   */
  attWorking: number
  /** Agents whose class could not be measured at all. */
  attUnmeasured: number
  /**
   * Did ANY agent carry an attention class? A server that predates the axis
   * sends none, and then the state counters are the only truth there is.
   * Without this the row would silently render zeros for every class.
   */
  attentionReported: boolean
  /** The longest LIVE input wait in this set — parked ones excluded. */
  worstInputWaitSeconds: number | null
  /**
   * Waits nobody is coming for — past `INPUT_WAIT_PARKED_SECONDS`.
   *
   * Counted apart from `input`/`prompt` and never summed into them: it is a
   * different fact, and mixing the two is what made a two-hour-old question
   * outshout the forty-second one the reader was working with.
   */
  parked: number
}

export const EMPTY_TALLY: Tally = {
  agents: 0, working: 0, unknown: 0, waiting: 0, asking: 0, quiet: 0, unbucketed: 0,
  conflicts: 0, awaiting: 0, unmeasured: 0,
  input: 0, prompt: 0, background: 0, attentionUnbucketed: 0, worstInputWaitSeconds: null,
  attWorking: 0, attUnmeasured: 0, attentionReported: false, parked: 0,
}

export function tally(
  projects: readonly AttentionProject[],
  thresholds?: InputWaitThresholds | null,
): Tally {
  let agents = 0, working = 0, unknown = 0, waiting = 0, asking = 0, quiet = 0, unbucketed = 0
  let conflicts = 0, awaiting = 0, unmeasured = 0
  let input = 0, prompt = 0, background = 0, attentionUnbucketed = 0
  let attWorking = 0, attUnmeasured = 0, attentionReported = false
  let worstInputWaitSeconds: number | null = null
  let parked = 0
  for (const p of projects) {
    // Counted from the DATA, like everything else here: `total` is what the
    // producer computed from its own lists, and `source_missing` is the only
    // thing that makes a zero readable. A project with no state file adds
    // nothing to `awaiting` and one to `unmeasured` — never a silent zero.
    const aw = p.awaiting
    if (aw) {
      if (typeof aw.total === 'number') awaiting += aw.total
      if (aw.source_missing === true) unmeasured += 1
    }
    for (const a of p.agents) {
      agents += 1
      if (a.state === WORKING) working += 1
      else if (a.state === UNKNOWN) unknown += 1
      else if (a.state === WAITING) waiting += 1
      else if (a.state === ASKING) asking += 1
      else if (a.state === QUIET) quiet += 1
      // The branch that did not exist, and whose absence is the defect this
      // chain shipped with: anything unrecognised was counted nowhere at all.
      else unbucketed += 1
      // Counted from the DATA, never from a declaration that conflicts exist.
      // An empty string is not a conflict; a missing key is not one either.
      if (typeof a.declaration_ignored === 'string' && a.declaration_ignored !== '') conflicts += 1
      // The attention axis. A server that does not send the field contributes
      // to nothing here — an absent class is not `unmeasured`, it is silence,
      // and counting silence as a measurement is what makes a zero unreadable.
      if (typeof a.attention === 'string' && a.attention !== '') attentionReported = true
      const asleep = isParked(a, thresholds)
      if (asleep) parked += 1
      if (a.attention === ATT_INPUT) { if (!asleep) input += 1 }
      else if (a.attention === ATT_PROMPT) { if (!asleep) prompt += 1 }
      else if (a.attention === ATT_BACKGROUND) background += 1
      else if (a.attention === ATT_WORKING) attWorking += 1
      else if (a.attention === ATT_UNMEASURED) attUnmeasured += 1
      else if (typeof a.attention === 'string' && a.attention !== '') attentionUnbucketed += 1
      const w = worstInputWait([a], thresholds)
      if (w !== null && (worstInputWaitSeconds === null || w > worstInputWaitSeconds)) {
        worstInputWaitSeconds = w
      }
    }
  }
  return {
    agents, working, unknown, waiting, asking, quiet, unbucketed, conflicts, awaiting, unmeasured,
    input, prompt, background, attentionUnbucketed, worstInputWaitSeconds,
    attWorking, attUnmeasured, attentionReported, parked,
  }
}

export function tallyOf(
  names: readonly string[],
  byName: ReadonlyMap<string, AttentionProject>,
  thresholds?: InputWaitThresholds | null,
): Tally {
  return tally(
    names.map(n => byName.get(n)).filter((p): p is AttentionProject => Boolean(p)),
    thresholds,
  )
}

/**
 * Does the producer report a waiting state at all?
 *
 * Two independent signals, either of which is proof, and neither of which is a
 * declaration the producer makes about itself:
 *
 *  - the envelope carries a `waiting` key — an absent key is not a zero, so
 *    `typeof` rather than truthiness (a real `waiting: 0` must count as
 *    reported, and `!data.waiting` would read it as absent);
 *  - some agent is actually in that state, which settles it whatever the
 *    envelope says.
 *
 * Nothing here asks the API whether it supports the field. A declaration is not
 * data, and this is the same rule applied one layer up.
 */
export function waitingReported(envelope: unknown, projects: readonly AttentionProject[]): boolean {
  if (envelope && typeof envelope === 'object' && typeof (envelope as Record<string, unknown>).waiting === 'number') {
    return true
  }
  return projects.some(p => p.agents.some(a => a.state === WAITING))
}

/**
 * The first project, in the order the reader sees, holding an agent in one of
 * the given states. `null` when there is none — never the first project as a
 * fallback, because jumping somewhere irrelevant teaches the reader the marker
 * is noise.
 *
 * `order` must be the FULL reading order including parked and collapsed groups:
 * the whole point is to reach the ones that are out of sight.
 */
export function firstWith(
  order: readonly string[],
  byName: ReadonlyMap<string, AttentionProject>,
  states: readonly string[],
): string | null {
  return firstMatching(order, byName, a => states.includes(a.state))
}

/** The same jump, for something that is not a state — a refuted declaration. */
export function firstMatching(
  order: readonly string[],
  byName: ReadonlyMap<string, AttentionProject>,
  predicate: (agent: AttentionAgent) => boolean,
): string | null {
  for (const name of order) {
    const project = byName.get(name)
    if (project?.agents.some(predicate)) return name
  }
  return null
}

/**
 * The first project awaiting a human — task 7.14's jump target.
 *
 * It cannot reuse `firstMatching`, and that is the whole point of this
 * function existing: that one looks for an AGENT satisfying a predicate, and
 * the case here is a project with no agents at all. A jump built on agents
 * would skip exactly the projects this count exists to reach.
 */
export function firstAwaiting(
  order: readonly string[],
  byName: ReadonlyMap<string, AttentionProject>,
): string | null {
  for (const name of order) {
    const total = byName.get(name)?.awaiting?.total
    if (typeof total === 'number' && total > 0) return name
  }
  return null
}

/** Is this agent's declared state one the log refuted? */
export function hasConflict(agent: AttentionAgent): boolean {
  return typeof agent.declaration_ignored === 'string' && agent.declaration_ignored !== ''
}
