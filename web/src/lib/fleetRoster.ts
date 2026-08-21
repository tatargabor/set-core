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
}

export interface RosterAnswer {
  project: string
  entries: RosterEntry[]
  /** `false` means never recorded. Not the same as recorded-and-empty. */
  record_exists: boolean
  unreadable: boolean
  /** False when liveness could not be asked. Then every `running` is `null`. */
  liveness_known?: boolean
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
  return { attempted, started, skipped, failed,
           complete: result.complete === true, unfinished, headline }
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
export function restoreOffer(answer: RosterAnswer): {
  total: number; resumable: number; running: number; restorable: number
  label: string; actionable: boolean
} {
  const entries = entriesOf(answer)
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
  return { total, resumable, running, restorable, label, actionable: restorable > 0 }
}

/** Human-readable age. Shared so the tile and the empty screen cannot disagree. */
export function ageLabel(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return 'unknown'
  if (seconds < 90) return `${Math.round(seconds)}s`
  if (seconds < 5400) return `${Math.round(seconds / 60)}m`
  if (seconds < 172800) return `${(seconds / 3600).toFixed(1)}h`
  return `${(seconds / 86400).toFixed(1)}d`
}
