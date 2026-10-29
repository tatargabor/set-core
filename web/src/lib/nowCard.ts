/**
 * The Now card's data shape and the pure decisions the page makes about it
 * (fleet-now-card, section 4). Kept out of the component so each decision is
 * testable on its own: what counts as a gap, what the empty state may say, and
 * what the feedback says after an action.
 */

export interface NowOption { id: string; label: string }

export interface NowItem {
  source: string
  id: string
  project: string | null
  sentence: string | null
  why: string | null
  estimateMinutes?: number
  deadline?: string
  unblocks?: string
  options: NowOption[]
  acceptsText: boolean
  delegable: boolean
  link?: string
  sessionId?: string | null
  kind?: string | null
  since?: number | string | null
  relay?: boolean
  actions: string[]
  goThere: { kind: string; href: string } | null
  resumeNote?: string
}

export interface NowSource {
  name: string
  /** `null` = not applicable (no publisher declared) — not a failure, not a zero. */
  measured: boolean | null
  reason: string | null
  count: number | null
}

export interface NowCue {
  play: boolean
  reason: string | null
  variant: number | null
  slowed: boolean
  intervalSeconds: number
}

export interface NowPayload {
  item: NowItem | null
  following: number
  heldBack: number
  sources: NowSource[]
  unmeasured: number
  publisher: { state: string; project: string | null; candidates: string[]; reason: string | null; acceptsActions: boolean }
  partial: boolean
  malformed: number
  /** The publisher's own inputs it could not read — its queue is missing them. */
  unreadSources?: string[]
  rankedAt: string | null
  rankingAgeSeconds: number | null
  stale: boolean
  closedToday: number
  parkedIdeas: number
  cue: NowCue
  windDown: { active: boolean; hour: number; delegableIds: string[] }
  tomorrowNote: string | null
  focus: string[]
  focusMax: number
  focusSetToday: boolean
  focusCandidates: string[]
  generatedAt: string
}

export interface ActBody {
  id: string
  source: string
  action: string
  option?: string
  text?: string
  reasons?: string[]
  laterSeconds?: number
  sessionId?: string | null
  project?: string | null
}

export interface ActResponse {
  delivered: boolean
  sent: boolean
  outcome: string | null
  reason: string | null
  errorClass: string | null
  closedToday: number
  parkedIdeas: number
}

/** Hours, rounded to one decimal below ten — "ranked 6 h ago", "ranked 1.5 h ago". */
export function hoursAgo(seconds: number): string {
  const h = seconds / 3600
  if (h < 1) return `${Math.max(1, Math.round(seconds / 60))} min`
  return `${h < 10 ? Math.round(h * 10) / 10 : Math.round(h)} h`
}

export interface Marker { tone: 'warn' | 'info'; text: string }

/**
 * Every gap the reader should see on the card itself (spec: a gap is shown where
 * the reader is standing). Order: what makes the card wrong first.
 */
export function gapMarkers(p: NowPayload): Marker[] {
  const out: Marker[] = []
  const unreadable = p.sources.filter(s => s.measured === false)
  if (unreadable.length) {
    out.push({
      tone: 'warn',
      text: `${unreadable.length} source${unreadable.length > 1 ? 's' : ''} could not be read: ` +
        unreadable.map(s => `${s.name}${s.reason ? ` — ${s.reason}` : ''}`).join('; '),
    })
  }
  if (p.publisher.state === 'none') out.push({ tone: 'info', text: 'No ranked queue is published' })
  // An ambiguous or misconfigured publisher is counted as unreadable above, with its reason.
  if (p.publisher.state === 'ok' && !p.publisher.acceptsActions) {
    out.push({ tone: 'info', text: 'The publisher accepts no actions' })
  }
  if (p.unreadSources && p.unreadSources.length) {
    out.push({ tone: 'warn', text: `Publisher could not read: ${p.unreadSources.join('; ')}` })
  }
  if (p.partial) out.push({ tone: 'warn', text: 'Queue is partial' })
  if (p.stale && p.rankingAgeSeconds != null) {
    out.push({ tone: 'warn', text: `ranked ${hoursAgo(p.rankingAgeSeconds)} ago` })
  }
  if (p.malformed > 0) out.push({ tone: 'warn', text: `${p.malformed} item(s) unreadable, skipped` })
  if (p.cue.slowed) out.push({ tone: 'info', text: 'cues slowed' })
  return out
}

/**
 * The empty state's sentence. "Nothing is waiting" ONLY when every source was
 * read — an empty queue with an unreadable source is not calm, it is unknown.
 */
export function emptyMessage(p: NowPayload): string {
  const gaps = p.unmeasured + (p.unreadSources?.length ?? 0)
  if (gaps === 0) return 'Nothing is waiting.'
  return `Nothing to show — but ${gaps} source${gaps > 1 ? 's' : ''} could not be read.`
}

const DEFAULT_OUTCOME: Record<string, string> = {
  answer: 'Answer delivered',
  done: 'Marked done',
  delegate: 'Handed off',
  later: 'Snoozed',
  'park-idea': 'Idea parked',
  'resume-note': 'Note kept',
  'wind-down-handoff': 'Handed off for tonight',
}

/** What the feedback says: the source's own outcome, or a plain statement of the act. */
export function feedbackText(action: string, res: ActResponse): string {
  if (!res.delivered) return res.reason || 'Not delivered — the item stays.'
  return res.outcome || DEFAULT_OUTCOME[action] || 'Done'
}

/** "Later" choices, in seconds. The last one returns the item tomorrow at 08:00. */
export function laterChoices(now: Date): { label: string; seconds: number }[] {
  const tomorrow = new Date(now)
  tomorrow.setDate(now.getDate() + 1)
  tomorrow.setHours(8, 0, 0, 0)
  return [
    { label: '15 min', seconds: 15 * 60 },
    { label: '1 h', seconds: 3600 },
    { label: '2 h', seconds: 7200 },
    { label: '4 h', seconds: 4 * 3600 },
    { label: 'Tomorrow', seconds: Math.round((tomorrow.getTime() - now.getTime()) / 1000) },
  ]
}

/** Whether keeping this item (Done, or an answer) must ask for reasons first. */
export function needsReasons(item: NowItem, action: string): boolean {
  return item.delegable && (action === 'done' || action === 'answer')
}

export async function fetchNow(): Promise<NowPayload> {
  const res = await fetch('/api/fleet/now')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  // A dashboard older than this card answers the path with its HTML page, status 200.
  // Say that, rather than surfacing a JSON parse error.
  const type = res.headers?.get?.('content-type') ?? ''
  if (type && !type.includes('json')) {
    throw new Error('the server answered with a page, not card data — its dashboard service predates the Now card and needs a restart')
  }
  return res.json()
}

/** POST an action. An HTTP refusal is turned into a not-delivered answer carrying its detail. */
export async function postAct(body: ActBody): Promise<ActResponse> {
  const res = await fetch('/api/fleet/now/act', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { detail = (await res.json()).detail ?? detail } catch { /* keep the status */ }
    return { delivered: false, sent: false, outcome: null, reason: String(detail), errorClass: 'http', closedToday: -1, parkedIdeas: -1 }
  }
  return res.json()
}

export interface FocusResponse {
  ok: boolean
  swap: boolean
  focus: string[]
  reason?: string
  removed?: string[]
}

export async function postFocus(projects: string[], notes: Record<string, string>): Promise<FocusResponse> {
  const res = await fetch('/api/fleet/now/focus', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ projects, notes }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
