/**
 * The recorded fleet — what was here before the machine went down.
 *
 * Pure functions over the two roster answers, kept out of the components for
 * the reason the rest of this screen keeps them out: a restore cannot be
 * asserted in jsdom without an owner service and real processes, but the way
 * its RESULT is summarised can be, and that summary is where this feature's
 * most likely defect lives.
 *
 * ## The one rule this file exists to hold
 *
 * **A restore that did not start everything must not summarise as one that
 * did.** Nine entries of which three started is a partial result. The tempting
 * summary — "Restored 3 agents" — is true and reads as complete, which is the
 * marker-outranks-the-body defect in its most ordinary form: the count is the
 * part that gets read, and it says nothing about the six that did not come.
 *
 * So `summarise` never returns a bare success. It returns the three counts and
 * a `complete` flag taken from the SERVER's own field rather than recomputed
 * here — a second definition of "complete" would drift from the first, and the
 * copy that drifts is always the one being read.
 */

export interface RosterEntry {
  key: string
  session_id: string | null
  label: string | null
  cwd: string
  project: string | null
  kind: string
  first_seen: number
  last_seen: number
  session_log: string | null
  resumable: boolean
  not_resumable_reason: string | null
  /**
   * Whether a live process is on this session RIGHT NOW. `null` means it could
   * not be asked — never `false`, because a zero here is the number the offer
   * below subtracts, and subtracting an unmeasured zero overstates the act.
   */
  running?: boolean | null
  /**
   * Whether this entry was still being seen when the fleet was last observed —
   * which is what "was open" means for a record that consults nothing live.
   *
   * `null` is *we cannot tell* (the record carries no observation), and it is
   * NOT `false`, which would mean *this agent was not open*. The surface renders
   * the two differently on purpose: an unknown composition falls back to the
   * whole list and says so, where a known-empty one says nothing was open.
   * `undefined` is an older server and reads the same as `null`.
   */
  in_last_round?: boolean | null
}

export interface RosterAnswer {
  project: string
  entries: RosterEntry[]
  /** `false` means never recorded. Not the same as recorded-and-empty. */
  record_exists: boolean
  unreadable: boolean
  /** False when liveness could not be asked. Then every `running` is `null`. */
  liveness_known?: boolean
  /**
   * When the fleet was last observed, in epoch seconds — the stamp every entry
   * seen in that round carries. `null` or absent means the record cannot say.
   */
  last_round_at?: number | null
}

export interface RosterProject {
  project: string
  entries: number
  last_seen: number
}

export interface RestoreOutcome {
  key: string
  session_id: string | null
  label: string | null
  cwd: string
  last_seen: number
  status: 'started' | 'skipped' | 'failed'
  reason: string | null
  label_used?: string
  renamed?: boolean
  /**
   * Where the name came from — `restored` (the recorded one was free),
   * `renamed` (it was taken, so a variant was derived) or `derived` (nothing
   * was recorded, so the framework invented it).
   *
   * Read as three, never collapsed into "started": the question a person has
   * when they look at a restored fleet is whether these are the names they
   * gave, and a derived name shown as a restored one is a false value in the
   * one place they look to recognise their own work.
   */
  name_source?: 'restored' | 'renamed' | 'derived'
  wanted_label?: string
  pid?: number
}

export interface RestoreResult {
  project: string
  attempted: number
  started: RestoreOutcome[]
  skipped: RestoreOutcome[]
  failed: RestoreOutcome[]
  record_exists: boolean
  complete: boolean
}

export interface RestoreSummary {
  attempted: number
  started: number
  skipped: number
  failed: number
  /** Straight from the server. Never recomputed — see the module note. */
  complete: boolean
  /** Everything that did not start, in one list, each carrying its reason. */
  unfinished: RestoreOutcome[]
  /** One line for a person. Never says "restored" unless everything came back. */
  headline: string
  /**
   * The agents that came back under a name nobody chose — renamed around a
   * collision, or invented because none was recorded.
   *
   * Separate from `unfinished`: these DID start, so they are not a failure and
   * must not be marked as one. They are the entries whose name is not the
   * answer to "is this the one I called X".
   */
  unnamed: RestoreOutcome[]
}

export function summarise(result: RestoreResult): RestoreSummary {
  // Same shape check as `entriesOf`, and for the same reason: a body that is
  // not the one this route promises must not throw inside a render.
  const list = (x: unknown): RestoreOutcome[] => (Array.isArray(x) ? x as RestoreOutcome[] : [])
  const startedList = list(result?.started)
  const skippedList = list(result?.skipped)
  const failedList = list(result?.failed)
  const started = startedList.length
  const skipped = skippedList.length
  const failed = failedList.length
  const unfinished = [...skippedList, ...failedList]
  const attempted = typeof result?.attempted === 'number' ? result.attempted : 0
  let headline: string
  if (attempted === 0) {
    headline = 'Nothing was recorded for this project — nothing was attempted.'
  } else if (result.complete === true) {
    headline = `All ${started} restored.`
  } else if (started === 0) {
    headline = `None of the ${attempted} started — see the reason on each.`
  } else {
    headline = `${started} of ${attempted} restored; ${unfinished.length} did not start.`
  }
  // An outcome from an older server carries no `name_source` at all. Absent is
  // not `derived`: claiming a name was invented when the server never said so
  // would put a warning on a screen with nothing behind it.
  const unnamed = startedList.filter(o => o.name_source === 'renamed' || o.name_source === 'derived')
  return { attempted, started, skipped, failed,
           complete: result.complete === true, unfinished, headline, unnamed }
}

/**
 * Whether a restore control may be offered at all.
 *
 * A control that would do nothing is worse than an absent one: it invites the
 * click that teaches the reader the screen is lying about having something.
 */
export function canRestore(answer: RosterAnswer | null): boolean {
  return entriesOf(answer).length > 0
}

/**
 * The entries an answer carries, or none — **checked, not assumed.**
 *
 * Found by the existing fleet suite, 2026-08-21: their fetch mocks answer every
 * `/api/fleet` URL with the agent-listing payload, which has no `entries` at
 * all. `answer.entries.length` threw and took the whole screen down with it.
 *
 * The tests were incidentally right about something real. A body of the wrong
 * shape is what an older server, a proxy, an error page or a rewritten route
 * hands back, and none of those may cost the reader their screen. So the shape
 * is verified rather than trusted, and a body that does not carry a list reads
 * as "nothing recorded" — the same as a project nobody has seen, which is the
 * honest reading when no record can be read.
 */
function entriesOf(answer: RosterAnswer | null | undefined): RosterEntry[] {
  return answer && Array.isArray(answer.entries) ? answer.entries : []
}

/**
 * What the control says BEFORE it is pressed.
 *
 * The count of what would actually be attempted is not the entry count: an
 * entry with no transcript will be skipped, and promising to restore it is a
 * promise the act cannot keep. Both numbers are stated, because the difference
 * is the information — "6 recorded, 4 can be resumed" tells the reader two of
 * their agents are gone, which is the fact a single number would hide.
 */
export interface RestoreOffer {
  total: number; resumable: number; running: number; restorable: number
  label: string; actionable: boolean
  /** The keys the act would attempt — exactly the restorable ones, in order. */
  keys: string[]
}

export function restoreOffer(answer: RosterAnswer): RestoreOffer {
  return offerFor(entriesOf(answer))
}

/**
 * The same offer, over an arbitrary subset of a project's entries.
 *
 * Split out when the surface gained a second offer (2026-08-26): the primary one
 * over the last composition, the secondary over a hand-picked selection. One
 * function rather than two, because two would drift, and the half that drifts is
 * always the one being read — the label states a count somebody acts on.
 */
export function offerFor(entries: readonly RosterEntry[]): RestoreOffer {
  const total = entries.length
  const resumable = entries.filter(e => e.resumable).length
  // `running === true` only. `null` is "could not ask" and `undefined` is an
  // older server; neither may be counted as running, because a count here is
  // SUBTRACTED from what the button promises.
  const running = entries.filter(e => e.running === true).length
  const restorable = entries.filter(e => e.resumable && e.running !== true).length

  let label: string
  if (total === 0) {
    label = 'Nothing recorded'
  } else if (restorable === 0 && running === total) {
    label = `All ${total} already running`
  } else if (restorable === total) {
    label = `Restore ${total} agent${total === 1 ? '' : 's'}`
  } else {
    const parts: string[] = []
    if (running) parts.push(`${running} already running`)
    if (total - resumable) parts.push(`${total - resumable} cannot be resumed`)
    label = `Restore ${restorable} of ${total} — ${parts.join(', ')}`
  }
  return {
    total, resumable, running, restorable, label, actionable: restorable > 0,
    // Exactly what the label promises. Derived here rather than at the call
    // site so the number the reader sees and the set the request carries cannot
    // come apart — the defect that would look like a restore doing more than it
    // said, which is the direction that acts.
    keys: entries.filter(e => e.resumable && e.running !== true).map(e => e.key),
  }
}

/**
 * What was open when the fleet was last observed, and what merely sits in the
 * record — the split the primary restore offer is built from.
 *
 * Three states, not two, and collapsing them is the defect this exists to avoid:
 *
 *  - **known, non-empty** — those entries were open; offer them.
 *  - **known, empty** — the fleet WAS observed and nothing was open here. Say
 *    that. Never fall back to an earlier round: presenting agents the user had
 *    already closed as "what was open" is a false value in the acting direction.
 *  - **unknown** — the record carries no observation (an older document, or one
 *    written by a partial pass). Then the whole list is offered *with the reason
 *    stated*, because a whole-list offer wearing a composition's label is the
 *    same lie by a quieter route.
 */
export interface Composition {
  known: boolean
  /** Present only when `known` is false — why the composition cannot be given. */
  reason: string | null
  observedAt: number | null
  /** In the last round. Empty when known-and-nothing-was-open. */
  entries: RosterEntry[]
  /** Recorded, but not in the last round. The whole record when unknown. */
  rest: RosterEntry[]
}

export function composition(answer: RosterAnswer | null): Composition {
  const entries = entriesOf(answer)
  // `undefined` is an older server and reads as `null`: both mean the record
  // cannot say, and neither may be read as `false`.
  const known = entries.length > 0 && entries.every(e => e.in_last_round === true || e.in_last_round === false)
  if (!known) {
    return {
      known: false,
      reason: 'the record does not say which of these were open when the fleet was last seen',
      observedAt: null,
      entries: [],
      rest: entries,
    }
  }
  const at = answer && typeof answer.last_round_at === 'number' ? answer.last_round_at : null
  return {
    known: true,
    reason: null,
    observedAt: at,
    entries: entries.filter(e => e.in_last_round === true),
    rest: entries.filter(e => e.in_last_round !== true),
  }
}

/** Human-readable age. Shared so the tile and the empty screen cannot disagree. */
export function ageLabel(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return 'unknown'
  if (seconds < 90) return `${Math.round(seconds)}s`
  if (seconds < 5400) return `${Math.round(seconds / 60)}m`
  if (seconds < 172800) return `${(seconds / 3600).toFixed(1)}h`
  return `${(seconds / 86400).toFixed(1)}d`
}
