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
 * Three values, and the third is not a shade of the second:
 *
 *  - `started-here` — the framework started it and still holds the pty, so a
 *    terminal exists and `terminal_label` addresses it;
 *  - `foreign` — nobody here holds it; there is no terminal and there cannot be;
 *  - `unknown` — **the owner could not be asked.** Not "no terminal": we do not
 *    know. Rendering it as `foreign` would state "no terminal" about agents that
 *    have one, for exactly as long as the owner service takes to come back —
 *    which is the false-absence class this whole screen exists against. The
 *    envelope's `owner_reachable` carries the reason once, not per row.
 */
export type Population = 'started-here' | 'foreign' | 'unknown'

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
  /** The terminal's address. Non-null only for `started-here`. */
  terminal_label?: string | null
}

export interface FleetProject {
  name: string
  root: string
  sources: string[]
  archived: boolean
  agents: FleetAgent[]
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
