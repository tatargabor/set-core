/**
 * The set-watchdog's state as the fleet header reads it (fleet-watchdog, D6).
 *
 * Four badge states, and STALE is not zero: a watchdog whose timer stopped must not read as
 * a calm machine. The server computes the state; this module only parses it and refuses a
 * shape it does not know, so an unreadable answer shows as unread, never as `ok`.
 */

export type WatchdogBadge = 'ok' | 'count' | 'red' | 'stale'

export interface WatchdogTriage {
  verdict: string
  owner: string | null
  brief: string
}

export interface WatchdogDispatch {
  state: string
  owner?: string | null
  reason?: string | null
  engagement?: string | null
}

export interface WatchdogFinding {
  fp: string
  probe: string
  severity: 'fail' | 'warn'
  subject: string
  summary: string
  first_seen: number
  last_seen: number
  resolved_at: number | null
  triage: WatchdogTriage | null
  untriaged: boolean
  dispatch: WatchdogDispatch | null
  muted: boolean
}

export interface WatchdogState {
  enabled: boolean
  badge: WatchdogBadge
  last_tick_at: number | null
  last_tick_age_s: number | null
  interval_s: number
  counts: { open: number; fail: number; warn: number; untriaged: number; dispatched: number; muted: number; resolved_24h: number }
  open: WatchdogFinding[]
  muted: WatchdogFinding[]
  resolved: WatchdogFinding[]
}

const BADGES: WatchdogBadge[] = ['ok', 'count', 'red', 'stale']

function finding(x: any): WatchdogFinding | null {
  if (!x || typeof x.fp !== 'string' || typeof x.probe !== 'string') return null
  return {
    fp: x.fp, probe: x.probe, severity: x.severity === 'fail' ? 'fail' : 'warn',
    subject: String(x.subject ?? ''), summary: String(x.summary ?? ''),
    first_seen: Number(x.first_seen ?? 0), last_seen: Number(x.last_seen ?? 0),
    resolved_at: typeof x.resolved_at === 'number' ? x.resolved_at : null,
    triage: x.triage && typeof x.triage.verdict === 'string'
      ? { verdict: x.triage.verdict, owner: x.triage.owner ?? null, brief: String(x.triage.brief ?? '') } : null,
    untriaged: x.triage == null,
    dispatch: x.dispatch && typeof x.dispatch.state === 'string' ? x.dispatch : null,
    muted: Boolean(x.muted),
  }
}

function list(xs: unknown): WatchdogFinding[] {
  return Array.isArray(xs) ? xs.map(finding).filter((f): f is WatchdogFinding => f !== null) : []
}

export function parseWatchdog(d: any): WatchdogState | null {
  if (!d || d.schema !== 'set-watchdog/1' || !BADGES.includes(d.badge) || !d.counts) return null
  const c = d.counts
  const n = (v: unknown) => (typeof v === 'number' ? v : 0)
  return {
    enabled: d.enabled !== false, badge: d.badge,
    last_tick_at: typeof d.last_tick_at === 'number' ? d.last_tick_at : null,
    last_tick_age_s: typeof d.last_tick_age_s === 'number' ? d.last_tick_age_s : null,
    interval_s: n(d.interval_s) || 300,
    counts: { open: n(c.open), fail: n(c.fail), warn: n(c.warn), untriaged: n(c.untriaged),
      dispatched: n(c.dispatched), muted: n(c.muted), resolved_24h: n(c.resolved_24h) },
    open: list(d.open), muted: list(d.muted), resolved: list(d.resolved),
  }
}

/** What the closed badge says in its tooltip — every state names itself, stale included. */
export function watchdogTitle(s: WatchdogState | null, error: string | null, ageText: string): string {
  if (!s) return `Watchdog: not read${error ? ` (${error})` : ''}`
  if (!s.enabled) return 'Watchdog: disabled (watchdog.enabled false)'
  if (s.badge === 'stale') {
    return s.last_tick_at === null ? 'Watchdog: STALE — it has never ticked (is set-watchdog.timer enabled?)'
      : `Watchdog: STALE — last tick ${ageText} ago, expected every ${Math.round(s.interval_s / 60)} min`
  }
  if (s.badge === 'ok') return `Watchdog: nothing open · last tick ${ageText} ago`
  return `Watchdog: ${s.counts.open} open (${s.counts.fail} fail, ${s.counts.warn} warn)`
    + `${s.counts.untriaged ? ` · ${s.counts.untriaged} untriaged` : ''} · last tick ${ageText} ago`
}

/** The verdict a row shows: the triage word, or "untriaged" — never blank. */
export function verdictLabel(f: WatchdogFinding): string {
  if (!f.triage) return 'untriaged'
  return f.triage.verdict.startsWith('known:') ? f.triage.verdict.slice(6) : f.triage.verdict
}

/** The dispatch state a row shows, with the hold reason when one applies. */
export function dispatchLabel(f: WatchdogFinding): string {
  const d = f.dispatch
  if (!d || d.state === 'none') return '—'
  if (d.state === 'held' && d.reason) return `held: ${d.reason}`
  if (d.state === 'failed') return `failed${d.reason ? `: ${d.reason}` : ''}`
  if (d.state === 'dispatched') return `sent to ${d.owner ?? '?'}`
  if (d.state === 'proposed') return `proposed → ${d.owner ?? '?'}`
  return d.state
}

/** Dispatch-now is offered for an open, triaged-real finding that is not already out. */
export function canDispatch(f: WatchdogFinding): boolean {
  return f.triage?.verdict === 'real' && f.dispatch?.state !== 'dispatched'
}
