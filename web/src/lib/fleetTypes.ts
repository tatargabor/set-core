/**
 * The shapes `/api/fleet/agents` answers with.
 *
 * In their own file because two components now read them — the screen and the
 * project column — and a second copy of a shape drifts at the moment it is
 * written.
 */

/**
 * Which population an agent belongs to — a CARRIED fact, never inferred here.
 *
 * Four values, and neither the third nor the fourth is a shade of the second:
 *
 *  - `started-here` — the framework started it and still holds the pty, so a
 *    terminal exists and `terminal_label` addresses it;
 *  - `orphaned` — the framework STARTED it and no longer holds the terminal
 *    (task 5.5). The scope survived; the pty did not, and a pty master cannot be
 *    reacquired from outside. Distinct from `foreign` because it is recoverable
 *    and because calling it foreign would say the framework did not start it;
 *  - `foreign` — nobody here holds it; there is no terminal and there cannot be;
 *  - `unknown` — **the owner could not be asked.** Not "no terminal": we do not
 *    know. Rendering it as `foreign` would state "no terminal" about agents that
 *    have one, for exactly as long as the owner service takes to come back —
 *    which is the false-absence class this whole screen exists against. The
 *    envelope's `owner_reachable` carries the reason once, not per row.
 */
export type Population = 'started-here' | 'orphaned' | 'foreign' | 'unknown'

import type { AttentionAwaiting } from './fleetAttention'

import type { CapabilityReport } from './fleetInstall'

export interface FleetAgent {
  pid: number
  name: string | null
  project: string | null
  branch: string | null
  session_id: string | null
  binding_confirmed: boolean
  sources: string[]
  kind: string
  /** `working` | `quiet` | `waiting` | `unknown`, and anything the producer adds later. */
  state: string
  tool: string | null
  tool_elapsed_seconds: number | null
  other_tools: string[]
  last_movement_seconds: number | null
  unknown_reason: string | null
  /**
   * What it is waiting for. `null` where the runtime did not write one down —
   * the STATE is still `waiting`, so this must never be read as a reason to
   * doubt it.
   */
  waiting_for?: string | null
  /**
   * A state the record DECLARED that the log refuted. The measurement wins and
   * `state` already holds it; this is the contradiction itself, and it is
   * rendered rather than swallowed — a contradiction the surface never shows is
   * one nobody ever fixes.
   */
  declaration_ignored?: string | null
  /** See `Population`. Absent on an older server, which is `unknown`, not `foreign`. */
  population?: Population | string | null
  /** The framework scope, present only for `orphaned` — what `recover` stops. */
  scope?: string | null
  /**
   * What the framework may CLAIM this agent survives — today only
   * `web-service-restart`. Measured: a pty-attached agent dies with its pty
   * holder, so it does NOT survive the owner's death, and a surface promising
   * more than this word promises something measured not to happen.
   */
  survives?: string | null
  /** The terminal's address. Non-null only for `started-here`. */
  terminal_label?: string | null
  /**
   * The last thing said in this session — task 7.3, so the tile answers "what
   * is going on" without being opened.
   *
   * `null`/absent means nothing was said RECENTLY (a tail of pure tool
   * traffic), which is not the same as an empty session — so the surface must
   * say which, rather than rendering a blank line for both.
   */
  excerpt?: string | null
  /** `agent` or `user`. Carried, because the same sentence means two things. */
  excerpt_from?: 'agent' | 'user' | null
  /**
   * Who started this agent — task 7.8, and it is deliberately not a string.
   *
   * `source: "recorded"` is the owner's own note of who ASKED for the start;
   * `source: "ancestry"` is measured from the process tree. They answer
   * different questions and can disagree, so the surface marks which one it is
   * showing rather than flattening them into one "parent".
   *
   * `pid_without_seat` exists because an ancestor with no session record has no
   * seat name at all; reporting nothing there would lose the relation entirely,
   * which is a false absence.
   */
  parent?: {
    seat?: string | null
    session_id?: string | null
    source: 'recorded' | 'ancestry'
    pid_without_seat?: number | null
  } | null
  /**
   * Who runs UNDER this agent — task 7.18.
   *
   * `known: false` means there was no key to look it up by, and a `0` there
   * would state "nothing runs under it" about an agent that may have started
   * five. `live_only` bounds the number: it counts recorded starts that are
   * still running, so a child that has already exited is not in it — and a
   * count shown without that sentence is a claim nobody measured.
   */
  descendants?: {
    known: boolean
    live?: number
    pids?: number[]
    live_only?: boolean
    reason?: string
  } | null
  /**
   * Whether this agent can be addressed at all — task 4.4 — and why not when it
   * cannot. The reason is a sentence for the reader, and the surface puts it
   * WHERE THE INPUT WOULD BE: dropping the agent would hide running work, and
   * showing an input that silently goes nowhere is worse than both.
   */
  instructable?: boolean
  reason?: string | null
  /** The bus address, when there is one. Shown as identity, never typed by hand. */
  seat?: string | null
  /**
   * What the agent SAID about itself — tasks 3.4 and 3.5, kept apart from what
   * was measured.
   *
   * ⚠ **CONFIDENTIALITY.** `focus` is a sentence an agent wrote about work that
   * may be a consumer's, and `files` are that project's own paths. Measured on
   * the live roster: one focus named a partner company and an unpaid invoice.
   * Displaying them is allowed — that is the whole point of the abstraction —
   * but they must never be written down: not to `localStorage`, not to a log,
   * not to a cache, not into any state that outlives the render.
   *
   * `known: false` means the bus could not be asked. That is NOT an agent that
   * declared nothing, and the two must not render alike: one is "this agent
   * says nothing about itself", the other is "we could not find out".
   *
   * `blocked` does not contradict `state`. An agent can be measured `working`
   * and declare itself blocked in the same moment — a detour while an answer is
   * outstanding — and that pair is the case worth showing. Measured live:
   * `state: quiet` beside `blocked: true`, which today's tile renders as calm.
   */
  declared?: {
    known: boolean
    focus?: string | null
    phase?: string | null
    blocked?: boolean
    files?: string[]
    declared_at?: string | null
  } | null
  /**
   * What this agent is working TOWARDS — task 3.9, from the engine's own record.
   *
   * `null` where there is no record, which on a machine with no engine running
   * is every agent (measured: 13 of 13). The surface states that absence rather
   * than drawing an empty progress bar, and `progress.measured` is why
   * `fraction` is nullable: a `0.0` for an unmeasured change draws identically
   * to a change nobody has started.
   */
  purpose?: {
    change: string
    unit_id?: string
    group?: string | null
    kind?: string | null
    lens?: string | null
    seat?: string | null
    pid?: number
    started_at?: string | null
    /** `finished` | `running` | `stale` — the third is a record whose process is gone. */
    status?: string
    verdict?: unknown
    pid_unverified?: boolean
    progress?: {
      done: number
      total: number
      partial: number
      measured: boolean
      fraction: number | null
    }
  } | null
}

/**
 * What became of one instruction — task 7.7, and the three fields are three
 * facts rather than one.
 *
 * An HTTP 200 here means *the send was made and answered*, which is compatible
 * with the message reaching nobody. So `accepted` (it went and came back),
 * `outcome` (what the channel said) and `delivered_to_agent` (the agent has it)
 * are separate, and no two of them may be collapsed.
 */
export type InstructOutcome =
  | 'arrives-now' | 'at-turn-end' | 'sits-unread' | 'wakes-nobody'
  | 'held' | 'expired' | 'unknown' | 'refused' | 'not-instructable'

export interface InstructReport {
  outcome: InstructOutcome | string
  accepted: boolean
  delivered_to_agent: boolean
  /**
   * Whether anything further is expected. **`held` is never settled** — it has
   * a clock and expires on its own, so a surface that renders it once and stops
   * is showing "held" for a message that is already dead.
   */
  settled: boolean
  seat?: string | null
  room?: string | null
  /** Who the channel says it wakes. `null` is an admission; `[]` is a measurement. */
  wakes?: string[] | null
  /** Live waiters for that session at send time. A zero is where the remedy goes. */
  waiters?: number
  waiters_here?: number
  /** The channel's own notices, verbatim. Shown, never parsed for a verdict. */
  notices?: string[]
  reason?: string | null
  /** Set when a later notice replaced this outcome (a hold that lapsed). */
  superseded?: string | null
  pid?: number
  session_id?: string | null
  /** Only on a 409 body. */
  error?: string
}

/** One waiter process — task 7.13. */
export interface Waiter {
  pid: number
  session_id?: string | null
  cwd?: string | null
  rooms?: string[]
  /**
   * `orphaned` may be removed, `live` must not be, and `undeterminable` is a
   * waiter whose session could not be read — treated as live, listed, never
   * offered. Collapsing the third into either of the others is the only way to
   * get this wrong, and one direction of that mistake kills a live waiter.
   */
  status: 'orphaned' | 'live' | 'undeterminable' | string
  removable: boolean
}

export interface WaitersResponse {
  /**
   * `false` means we could not look — the process table or session liveness was
   * unreadable. **That is not an empty list.** "No orphans" invites installing
   * another waiter; "we could not look" does not.
   */
  measured: boolean
  reason?: string | null
  waiters: Waiter[]
  orphaned?: number[]
  orphaned_count?: number
}

export interface FleetProject {
  /**
   * Work awaiting a HUMAN in this project — task 7.14, independent of who is
   * running. Optional because an older server does not send it, and an absent
   * key must stay distinguishable from a measured zero.
   */
  awaiting?: AttentionAwaiting | null
  name: string
  root: string
  sources: string[]
  archived: boolean
  agents: FleetAgent[]
  /**
   * What set-core modules this project has — the capability report (task 7.9,
   * and the namespace task 7.15 installs from). Optional because an older
   * server does not send it, and an absent report is not a project with no
   * modules: `fleetInstall.moduleStanding` reads the shape rather than the
   * numbers, so the two stay distinguishable on screen.
   */
  capabilities?: CapabilityReport | null
}

export interface FleetResponse {
  agents: number
  working: number
  unknown: number
  /**
   * Measured present 2026-08-19 on the trial server (`waiting: 1`). Still typed
   * optional, because the reason the key matters is that an ABSENT key is not a
   * zero — see `fleetAttention.waitingReported`, which reads the shape rather
   * than the value.
   */
  waiting?: number
  /**
   * MEASURED that a person is being asked — a question tool is outstanding.
   * Optional for the same reason as `waiting`: an absent key is an older
   * server, not a zero.
   */
  asking?: number
  quiet?: number
  /**
   * Agents whose state no bucket counted. Zero on a healthy server; carried
   * rather than merely logged, because the screen is where somebody notices.
   */
  unbucketed?: number
  projects: FleetProject[]
  quiet_means: string
  /**
   * Whether the owner service answered at all. Stated once at the top rather
   * than per row: a screen that can offer no terminal ANYWHERE has one cause,
   * and naming it once is the difference between "no terminals here" and "we
   * could not ask". Absent on an older server → unknown, so the surface must
   * not read `false` out of a missing key.
   */
  owner_reachable?: boolean
}
