/**
 * The daily auto-close of long-idle agents, as the fleet header shows it.
 *
 * The server answers `GET /api/fleet/idle-close`: whether the daily timer is on, the threshold,
 * when it runs next, which agents that run will close, and which ones it (or the owner) closed.
 * A closed agent stays in the roster, so each closed row can be brought back.
 */

export interface IdleTimer {
  known: boolean
  installed: boolean | null
  enabled: boolean | null
  /** epoch seconds, or null when systemd reports none */
  next_run: number | null
  last_run: number | null
}

export interface IdleRow {
  label: string | null
  project: string | null
  session_id: string
  idle_hours: number | null
  /** upcoming only: a tool is running right now, so it closes only if idle when the run comes */
  busy?: boolean
  /** closed only: when it was closed (ISO) */
  ts?: string
  /** closed only: the session is running again; null when liveness could not be asked */
  running?: boolean | null
  manual?: boolean
}

export interface IdleCloseState {
  threshold_hours: number
  threshold_error: string | null
  timer: IdleTimer
  upcoming: IdleRow[]
  closed: IdleRow[]
  liveness_known: boolean
}

/** What the threshold picker offers. A configured value outside it is still shown as itself. */
export const THRESHOLD_CHOICES = [24, 48, 72, 168]

function rows(v: unknown): IdleRow[] {
  if (!Array.isArray(v)) return []
  return v.filter((r): r is IdleRow =>
    !!r && typeof r === 'object' && typeof (r as IdleRow).session_id === 'string')
}

export function parseIdleClose(d: unknown): IdleCloseState | null {
  if (!d || typeof d !== 'object') return null
  const o = d as Record<string, unknown>
  const t = o.timer as Record<string, unknown> | undefined
  if (typeof o.threshold_hours !== 'number' || !t || typeof t !== 'object') return null
  const num = (x: unknown) => (typeof x === 'number' ? x : null)
  const bool = (x: unknown) => (typeof x === 'boolean' ? x : null)
  return {
    threshold_hours: o.threshold_hours,
    threshold_error: typeof o.threshold_error === 'string' ? o.threshold_error : null,
    timer: {
      known: t.known === true,
      installed: bool(t.installed),
      enabled: bool(t.enabled),
      next_run: num(t.next_run),
      last_run: num(t.last_run),
    },
    upcoming: rows(o.upcoming),
    closed: rows(o.closed),
    liveness_known: o.liveness_known === true,
  }
}

/** on · off · unknown — unknown when systemctl could not be asked, never shown as off. */
export function idleMode(s: IdleCloseState): 'on' | 'off' | 'unknown' {
  if (!s.timer.known || s.timer.enabled === null) return 'unknown'
  return s.timer.enabled ? 'on' : 'off'
}

/** `48 h`, `3 days`, `1 week` — the threshold as a person says it. */
export function thresholdLabel(hours: number): string {
  if (hours === 168) return '1 week'
  if (hours >= 48 && hours % 24 === 0) return `${hours / 24} days`
  return `${hours} h`
}

/** `today 04:00`, `tomorrow 04:00`, or a date — the next run, in local time. */
export function whenLabel(epochS: number | null, now: Date = new Date()): string {
  if (epochS === null) return '—'
  const d = new Date(epochS * 1000)
  const hm = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const day = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diff = Math.round((day(d) - day(now)) / 86_400_000)
  if (diff === 0) return `today ${hm}`
  if (diff === 1) return `tomorrow ${hm}`
  if (diff === -1) return `yesterday ${hm}`
  return `${d.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${hm}`
}

/** A closed row can be brought back when its session is known NOT to be running. */
export function canBringBack(r: IdleRow): boolean {
  return r.running === false && !!r.project
}

/** The header's tooltip for the closed switch. */
export function idleTitle(s: IdleCloseState): string {
  const mode = idleMode(s)
  if (mode === 'unknown') return 'Auto-close of idle agents: the timer could not be read'
  if (mode === 'off') return 'Auto-close of idle agents is off — click for details'
  const n = s.upcoming.length
  return `Auto-close: agents with no input from you for ${thresholdLabel(s.threshold_hours)} are closed daily, next ${
    whenLabel(s.timer.next_run)}${n ? ` — ${n} will close then` : ''}`
}
