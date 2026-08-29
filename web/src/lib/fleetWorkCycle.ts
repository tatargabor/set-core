/**
 * What the work-cycle engine's recorded runs MEAN on a screen.
 *
 * The classification lives here rather than in the component for the reason the
 * rest of this directory exists: a decision made inside a render is a decision
 * with no test, and every one of the distinctions below is a distinction the
 * screen has previously been measured flattening.
 *
 * ## The three states that are NOT the same, however similar they look
 *
 * - **Set aside** and **failed** produce the identical shape on disk — no gate,
 *   no commit — and only `set_aside` tells them apart. A unit waiting for a
 *   person is not a broken one, and rendering it as broken sends somebody to
 *   debug an answer they were supposed to give.
 * - **Stale** and **running**. A record claiming progress whose process is gone
 *   is not a slow run. The engine already decides this; the screen must not
 *   re-derive it.
 * - **Unconfirmed** and **running**. A pid is recycled, so "a process holds that
 *   number" is a different answer from "your run is alive" — and the payload says
 *   which question was answered. Collapsing the two is how a screen reports
 *   liveness nobody measured.
 *
 * ## `null` is not `false`
 *
 * `runnable` and `adopted` arrive as `boolean | null`, and `null` means *nobody
 * could ask*. Rendering that as "not runnable" or "not adopted" states something
 * about the project that was never measured — the class this repository calls a
 * false value, and the direction that reads as reassuring.
 */

/** One recorded run, as `GET /api/fleet/work-cycle` returns it. */
export interface WorkRun {
  unit_id: string
  change: string
  group?: string | null
  seat?: string | null
  status: string
  pid?: number
  pid_unverified?: boolean
  started_at?: string | null
  started_by?: string | null
  origin_is_claim?: boolean
  session_id?: string | null
  verdict?: { outcome?: string; summary?: string } | null
  gate?: { state?: string; failures?: string[]; attribution?: string; detail?: string } | null
  commit?: { committed?: boolean; sha?: string; reason?: string } | null
  set_aside?: { kind?: string; question?: string; task?: string } | null
  reading?: { declared?: boolean; missing?: string[]; refused?: string[];
              reached_nothing?: boolean } | null
}

export type RunState =
  | 'waiting'      // set aside for a person — NOT a failure
  | 'failed'       // a red gate, or a verdict that could not proceed
  | 'stale'        // the record claims progress; the process is gone
  | 'unconfirmed'  // claims live, and the pid could not be confirmed to be the agent
  | 'running'
  | 'unreported'   // ended without ever reporting a verdict — its own state
  | 'done'

/** What one run IS. Derived once, here, so no two places derive it differently. */
export function runState(run: WorkRun): RunState {
  if (run.set_aside) return 'waiting'
  if (run.status === 'stale') return 'stale'
  if (run.status === 'running') return run.pid_unverified ? 'unconfirmed' : 'running'
  if (run.gate && run.gate.state === 'failed') return 'failed'
  if (!run.verdict) return 'unreported'
  const outcome = (run.verdict.outcome || '').toUpperCase()
  if (outcome === 'BLOCKED') return 'failed'
  return 'done'
}

/** The states a reader has to be told about even when they are behind a tab. */
export const ATTENTION_STATES: readonly RunState[] = ['failed', 'waiting', 'stale', 'unreported']

export function needsAttention(run: WorkRun): boolean {
  return ATTENTION_STATES.includes(runState(run))
}

/**
 * What a collapsed container must show.
 *
 * `measured` is the half that is easy to drop and expensive to be wrong about:
 * a zero from a list that could not be read is indistinguishable from a zero
 * from a list with nothing wrong in it, and only one of them means "all well".
 */
export interface AttentionMark {
  count: number
  measured: boolean
  byState: Record<string, number>
}

export function attentionMark(runs: WorkRun[] | null | undefined): AttentionMark {
  if (!runs) return { count: 0, measured: false, byState: {} }
  const byState: Record<string, number> = {}
  for (const run of runs) {
    if (!needsAttention(run)) continue
    const s = runState(run)
    byState[s] = (byState[s] || 0) + 1
  }
  const count = Object.values(byState).reduce((a, b) => a + b, 0)
  return { count, measured: true, byState }
}

/** The sentence a collapsed band carries. Empty when there is nothing to say. */
export function attentionLabel(mark: AttentionMark): string {
  if (!mark.measured) return 'could not read this project’s runs'
  if (mark.count === 0) return ''
  const parts = Object.entries(mark.byState)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([state, n]) => `${n} ${state}`)
  return parts.join(', ')
}

/**
 * How to render whether a change can be run.
 *
 * Three outcomes, and the third is the one a boolean cannot carry.
 */
export function runnableLabel(
  change: { runnable: boolean | null; selected?: string | null;
            reasons?: Record<string, string>; available?: boolean; reason?: string },
): { tone: 'ready' | 'blocked' | 'unknown'; text: string; detail?: string } {
  if (change.runnable === null || change.runnable === undefined) {
    return { tone: 'unknown', text: change.reason || 'could not be asked' }
  }
  if (change.runnable) {
    return { tone: 'ready', text: change.selected ? `group ${change.selected}` : 'runnable' }
  }
  const reasons = Object.entries(change.reasons || {})
  if (reasons.length === 0) return { tone: 'blocked', text: 'nothing runnable' }
  // ⚠ Summarised, not truncated, when every group says the same thing. Seen on
  // the real screen: a finished change rendered as
  // `1: complete · 2: complete · … · acceptance-criteria…: complete` — a wall of
  // text that says one thing, in the widest possible way, and pushed the start
  // control off the visible area. The per-group detail is still available; it is
  // simply not the headline.
  const distinct = new Set(reasons.map(([, why]) => why))
  const detail = reasons.map(([g, why]) => `${g}: ${why}`).join(' · ')
  // Only worth summarising when there is more than one: "all 1 group(s) blocked
  // by 1" is longer AND less informative than naming the group, which the
  // existing single-reason test caught.
  if (distinct.size === 1 && reasons.length > 1) {
    return { tone: 'blocked', text: `all ${reasons.length} groups ${reasons[0][1]}`, detail }
  }
  return { tone: 'blocked', text: detail, detail }
}

/** The origin, rendered as what it is: a claim nothing verified. */
export function originLabel(run: WorkRun): string {
  if (!run.started_by) return 'nobody said who asked'
  return run.origin_is_claim === false
    ? run.started_by
    : `${run.started_by} (claimed)`
}
