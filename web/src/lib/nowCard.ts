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
  /** When the publisher first recommended this matter (ISO). Display-only. */
  firstSeen?: string
  /** The last on-demand "Still current?" check, as the publisher reports it. */
  check?: ItemCheck
}

export interface ItemCheck {
  state: 'running' | 'stands' | 'rewritten' | 'stale' | 'failed'
  startedAt?: string
  at?: string
  evidence?: string
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
  /** One tag per project with an item; `muted` = switched off on the strip. */
  groups?: { name: string; count: number; muted: boolean }[]
  /** Items a switched-off project hid — always shown, so the filter never looks like calm. */
  mutedHidden?: number
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

/** Mirrors `REASON_NOT_AGREED` in lib/set_orch/fleet/waiting.py. */
export const NOT_AGREED = 'not agreed yet'

/**
 * Every gap the reader should see on the card itself (spec: a gap is shown where
 * the reader is standing). Order: what makes the card wrong first.
 */
export function gapMarkers(p: NowPayload): Marker[] {
  const out: Marker[] = []
  // A source that is unmeasured BY DESIGN (its shape is not agreed with any project yet,
  // `REASON_NOT_AGREED` in lib/set_orch/fleet/waiting.py) is a known gap, not a failure:
  // shown quietly, so the warning colour keeps meaning "something broke".
  const notSetUp = p.sources.filter(s => s.measured === false && s.reason === NOT_AGREED)
  const unreadable = p.sources.filter(s => s.measured === false && s.reason !== NOT_AGREED)
  if (unreadable.length) {
    out.push({
      tone: 'warn',
      text: `${unreadable.length} source${unreadable.length > 1 ? 's' : ''} could not be read: ` +
        unreadable.map(s => `${s.name}${s.reason ? ` — ${s.reason}` : ''}`).join('; '),
    })
  }
  if (notSetUp.length) {
    out.push({ tone: 'info', text: `not set up: ${notSetUp.map(s => s.name).join(', ')}` })
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
  const hidden = p.mutedHidden ?? 0
  if (hidden > 0 && gaps === 0) return `Nothing in the switched-on tags — ${hidden} hidden by switched-off ones.`
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
  recheck: 'Check started',
}

/** What the feedback says: the source's own outcome, or a plain statement of the act. */
export function feedbackText(action: string, res: ActResponse): string {
  if (!res.delivered) return res.reason || 'Not delivered — the item stays.'
  return res.outcome || DEFAULT_OUTCOME[action] || 'Done'
}

/**
 * An exact clock time, for the owner's "pontos idő": "14:02" today, "yesterday 14:02",
 * otherwise "10-29 14:02". Local time — the card sits on the owner's own desktop.
 */
export function clockTime(iso: string | null | undefined, now: Date = new Date()): string | null {
  if (!iso) return null
  const t = new Date(iso)
  if (Number.isNaN(t.getTime())) return null
  const pad = (n: number) => String(n).padStart(2, '0')
  const hm = `${pad(t.getHours())}:${pad(t.getMinutes())}`
  const day = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
  if (day(t) === day(now)) return hm
  const y = new Date(now)
  y.setDate(now.getDate() - 1)
  if (day(t) === day(y)) return `yesterday ${hm}`
  return `${pad(t.getMonth() + 1)}-${pad(t.getDate())} ${hm}`
}

/** "recommended 10-29 14:02 · ranked 08:27" — whichever of the two is known. */
export function timeLine(item: NowItem, rankedAt: string | null | undefined, now: Date = new Date()): string | null {
  const parts: string[] = []
  const first = clockTime(item.firstSeen, now)
  if (first) parts.push(`recommended ${first}`)
  // Only the owner-queue's items are ranked; a framework item has its own "waiting" age.
  const ranked = item.source === 'owner-queue' ? clockTime(rankedAt, now) : null
  if (ranked) parts.push(`ranked ${ranked}`)
  return parts.length ? parts.join(' · ') : null
}

/** How a check reads on the card. `stale` and `failed` are warnings and never close themselves. */
export function checkView(c: ItemCheck | undefined, now: Date = new Date()):
  { tone: 'ok' | 'info' | 'warn'; label: string; evidence?: string } | null {
  if (!c) return null
  const at = clockTime(c.at ?? c.startedAt, now)
  const when = at ? ` · ${at}` : ''
  switch (c.state) {
    case 'running': return { tone: 'info', label: `Checking whether it is still current…${at ? ` (since ${at})` : ''}` }
    case 'stands': return { tone: 'ok', label: `Still current — checked${when}`, evidence: c.evidence }
    case 'rewritten': return { tone: 'info', label: `Reworded after a check${when}`, evidence: c.evidence }
    case 'stale': return { tone: 'warn', label: `No longer current — checked${when}`, evidence: c.evidence }
    case 'failed': return { tone: 'warn', label: `The check did not finish${when}`, evidence: c.evidence }
    default: return null
  }
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

export async function postGroups(muted: string[]): Promise<{ ok: boolean; muted: string[] }> {
  const res = await fetch('/api/fleet/now/groups', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ muted }),
  })
  if (!res.ok) throw new Error(`groups: HTTP ${res.status}`)
  return res.json()
}

export async function postFocus(projects: string[], notes: Record<string, string>): Promise<FocusResponse> {
  const res = await fetch('/api/fleet/now/focus', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ projects, notes }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// --------------------------------------------------------------------------- Goals tab
// The `owner-goals` answer (spec owner-goals-contract) as GET /api/fleet/now/goals serves it.

export interface GoalProgress { text: string; done?: number; total?: number }
export interface GoalEvidence { label: string; link?: string }

export interface Goal {
  id: string
  title: string
  status: 'proposed' | 'confirmed'
  why?: string
  serves?: string
  deadline?: string
  progress?: GoalProgress
  projects: string[]
  evidence: GoalEvidence[]
  openItems?: number
}

export interface GoalAdvice {
  id: string
  kind: 'add' | 'drop' | 'merge' | 'reorder' | 'neglected' | 'other'
  sentence: string
  why: string
  goalId?: string
}

export interface GoalsPayload {
  publisher: { state: string; project: string | null; candidates: string[]; reason: string | null; acceptsActions: boolean }
  /** `null` = no project declares `owner-goals` — not a failure, not a zero. */
  measured: boolean | null
  reason: string | null
  goals: Goal[]
  advice: GoalAdvice[]
  malformedGoals: number
  malformedAdvice: number
  partial: boolean
  unreadSources: string[]
  synthesizedAt: string | null
  ageSeconds: number | null
  stale: boolean
  acceptsVerdicts: boolean
  proposedCount: number
}

export type GoalAction = 'keep' | 'drop' | 'rename' | 'accept' | 'decline'

export interface GoalActBody { id: string; action: GoalAction; text?: string }

export interface GoalActResponse {
  delivered: boolean
  outcome: string | null
  reason: string | null
  errorClass: string | null
}

/**
 * Why the Goals tab is not showing a trustworthy answer, or null. A publisher that is
 * not declared at all is NOT a failure (it is the "No goals are published" state); an
 * ambiguous or misconfigured one is, because the owner has something to fix.
 */
export function goalsFailure(p: GoalsPayload | null, loadError: string | null): string | null {
  if (loadError) return `Goals could not load: ${loadError}`
  if (!p || p.measured !== false) return null
  return `Goals could not be read${p.reason ? `: ${p.reason}` : ''}`
}

/** The muted notes above the goals list: everything incomplete about the answer. */
export function goalsNotes(p: GoalsPayload): string[] {
  const out: string[] = []
  if (p.partial) {
    out.push(p.unreadSources.length
      ? `partial — the publisher could not read: ${p.unreadSources.join('; ')}`
      : 'partial — the publisher says this list is incomplete')
  } else if (p.unreadSources.length) {
    out.push(`the publisher could not read: ${p.unreadSources.join('; ')}`)
  }
  if (p.stale && p.ageSeconds != null) out.push(`synthesised ${hoursAgo(p.ageSeconds)} ago`)
  const bad: string[] = []
  if (p.malformedGoals > 0) bad.push(`${p.malformedGoals} goal${p.malformedGoals > 1 ? 's' : ''}`)
  if (p.malformedAdvice > 0) bad.push(`${p.malformedAdvice} suggestion${p.malformedAdvice > 1 ? 's' : ''}`)
  if (bad.length) out.push(`${bad.join(' and ')} unreadable, skipped`)
  return out
}

const DEFAULT_GOAL_OUTCOME: Record<GoalAction, string> = {
  keep: 'Goal kept',
  drop: 'Not a goal — sent',
  rename: 'Goal renamed',
  accept: 'Suggestion accepted',
  decline: 'Suggestion declined',
}

export function goalFeedbackText(action: GoalAction, res: GoalActResponse): string {
  if (!res.delivered) return res.reason || 'Not delivered — nothing changed.'
  return res.outcome || DEFAULT_GOAL_OUTCOME[action]
}

/** A progress bar's fill in percent, or null when the publisher gave no usable counts. */
export function progressPercent(p: GoalProgress | undefined): number | null {
  if (!p || p.total == null || p.done == null || p.total <= 0) return null
  return Math.max(0, Math.min(100, Math.round((p.done / p.total) * 100)))
}

/**
 * Where an evidence link goes: an absolute file path is a local document handed to the
 * desktop opener (as on the Now card), a dashboard path opens in the fleet window, any
 * other link opens as a page.
 */
export function evidenceTarget(link: string): { kind: 'file' | 'link'; href: string } {
  if (link.startsWith('/') && !link.startsWith('/?') && !link.startsWith('/p/')) return { kind: 'file', href: link }
  return { kind: 'link', href: link }
}

export async function fetchGoals(refresh = false): Promise<GoalsPayload> {
  const res = await fetch(`/api/fleet/now/goals${refresh ? '?refresh=true' : ''}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const type = res.headers?.get?.('content-type') ?? ''
  if (type && !type.includes('json')) {
    throw new Error('the server answered with a page, not goals — its dashboard service predates the Goals tab and needs a restart')
  }
  return res.json()
}

/** POST a verdict. An HTTP refusal is turned into a not-delivered answer carrying its detail. */
export async function postGoalAct(body: GoalActBody): Promise<GoalActResponse> {
  const res = await fetch('/api/fleet/now/goals/act', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { detail = (await res.json()).detail ?? detail } catch { /* keep the status */ }
    return { delivered: false, outcome: null, reason: String(detail), errorClass: 'http' }
  }
  return res.json()
}
