/**
 * The Now card's data shape and the pure decisions the page makes about it
 * (fleet-now-card, section 4). Kept out of the component so each decision is
 * testable on its own: what counts as a gap, what the empty state may say, and
 * what the feedback says after an action.
 *
 * Every helper that produces text the card shows takes an optional `locale` (default
 * English, the product's language); the words live in `nowI18n.ts`. The publisher's own
 * text — reasons, outcomes, source names — passes through untranslated.
 */

import { t } from './nowI18n'
import type { Locale, MsgKey } from './nowI18n'

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
  /** The owner's "working on it" note, when the item is back after one (publisher text). */
  progressNote?: string
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
  /** Every other registered project — pickable for focus though it has no card yet. */
  focusOthers?: string[]
  /** One tag per project with an item; `muted` = switched off on the strip. */
  groups?: { name: string; count: number; muted: boolean }[]
  /** Items a switched-off project hid — always shown, so the filter never looks like calm. */
  mutedHidden?: number
  /** The card's own text language (`now.locale`); absent from a server older than the setting. */
  locale?: Locale
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
export function hoursAgo(seconds: number, locale: Locale = 'en'): string {
  const h = seconds / 3600
  if (h < 1) return t(locale, 'ago.min', { n: Math.max(1, Math.round(seconds / 60)) })
  return t(locale, 'ago.h', { n: h < 10 ? Math.round(h * 10) / 10 : Math.round(h) })
}

export interface Marker { tone: 'warn' | 'info'; text: string }

/** Mirrors `REASON_NOT_AGREED` in lib/set_orch/fleet/waiting.py. */
export const NOT_AGREED = 'not agreed yet'

/**
 * Every gap the reader should see on the card itself (spec: a gap is shown where
 * the reader is standing). Order: what makes the card wrong first.
 */
export function gapMarkers(p: NowPayload, locale: Locale = 'en'): Marker[] {
  const out: Marker[] = []
  // A source that is unmeasured BY DESIGN (its shape is not agreed with any project yet,
  // `REASON_NOT_AGREED` in lib/set_orch/fleet/waiting.py) is a known gap, not a failure:
  // shown quietly, so the warning colour keeps meaning "something broke".
  const notSetUp = p.sources.filter(s => s.measured === false && s.reason === NOT_AGREED)
  const unreadable = p.sources.filter(s => s.measured === false && s.reason !== NOT_AGREED)
  if (unreadable.length) {
    out.push({
      tone: 'warn',
      text: t(locale, 'marker.unreadable', {
        n: unreadable.length,
        list: unreadable.map(s => `${s.name}${s.reason ? ` — ${s.reason}` : ''}`).join('; '),
      }),
    })
  }
  if (notSetUp.length) {
    out.push({ tone: 'info', text: t(locale, 'marker.notSetUp', { list: notSetUp.map(s => s.name).join(', ') }) })
  }
  if (p.publisher.state === 'none') out.push({ tone: 'info', text: t(locale, 'marker.noPublisher') })
  // An ambiguous or misconfigured publisher is counted as unreadable above, with its reason.
  if (p.publisher.state === 'ok' && !p.publisher.acceptsActions) {
    out.push({ tone: 'info', text: t(locale, 'marker.noActions') })
  }
  if (p.unreadSources && p.unreadSources.length) {
    out.push({ tone: 'warn', text: t(locale, 'marker.publisherUnread', { list: p.unreadSources.join('; ') }) })
  }
  if (p.partial) out.push({ tone: 'warn', text: t(locale, 'marker.partial') })
  if (p.stale && p.rankingAgeSeconds != null) {
    out.push({ tone: 'warn', text: t(locale, 'marker.stale', { age: hoursAgo(p.rankingAgeSeconds, locale) }) })
  }
  if (p.malformed > 0) out.push({ tone: 'warn', text: t(locale, 'marker.malformed', { n: p.malformed }) })
  if (p.cue.slowed) out.push({ tone: 'info', text: t(locale, 'marker.slowed') })
  return out
}

/**
 * The empty state's sentence. "Nothing is waiting" ONLY when every source was
 * read — an empty queue with an unreadable source is not calm, it is unknown.
 */
export function emptyMessage(p: NowPayload, locale: Locale = 'en'): string {
  const gaps = p.unmeasured + (p.unreadSources?.length ?? 0)
  const hidden = p.mutedHidden ?? 0
  if (hidden > 0 && gaps === 0) return t(locale, 'empty.mutedOnly', { n: hidden })
  if (gaps === 0) return t(locale, 'empty.calm')
  return t(locale, 'empty.unknown', { n: gaps })
}

/** The default sentence per action, when the source names no outcome of its own. */
const DEFAULT_OUTCOME: Record<string, MsgKey> = {
  answer: 'outcome.answer',
  done: 'outcome.done',
  delegate: 'outcome.delegate',
  later: 'outcome.later',
  'park-idea': 'outcome.park-idea',
  'resume-note': 'outcome.resume-note',
  'wind-down-handoff': 'outcome.wind-down-handoff',
  recheck: 'outcome.recheck',
}

/** What the feedback says: the source's own outcome (untranslated), or a plain statement of the act. */
export function feedbackText(action: string, res: ActResponse, locale: Locale = 'en'): string {
  if (!res.delivered) return res.reason || t(locale, 'outcome.notDelivered')
  return res.outcome || t(locale, DEFAULT_OUTCOME[action] ?? 'outcome.fallback')
}

/**
 * An exact clock time, for the owner's "pontos idő": "14:02" today, "yesterday 14:02",
 * otherwise "10-29 14:02". Local time — the card sits on the owner's own desktop.
 */
export function clockTime(iso: string | null | undefined, now: Date = new Date(), locale: Locale = 'en'): string | null {
  if (!iso) return null
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return null
  const pad = (n: number) => String(n).padStart(2, '0')
  const hm = `${pad(at.getHours())}:${pad(at.getMinutes())}`
  const day = (d: Date) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
  if (day(at) === day(now)) return hm
  const y = new Date(now)
  y.setDate(now.getDate() - 1)
  if (day(at) === day(y)) return t(locale, 'clock.yesterday', { time: hm })
  return `${pad(at.getMonth() + 1)}-${pad(at.getDate())} ${hm}`
}

/** "recommended 10-29 14:02 · ranked 08:27" — whichever of the two is known. */
export function timeLine(item: NowItem, rankedAt: string | null | undefined, now: Date = new Date(),
  locale: Locale = 'en'): string | null {
  const parts: string[] = []
  const first = clockTime(item.firstSeen, now, locale)
  if (first) parts.push(t(locale, 'time.recommended', { time: first }))
  // Only the owner-queue's items are ranked; a framework item has its own "waiting" age.
  const ranked = item.source === 'owner-queue' ? clockTime(rankedAt, now, locale) : null
  if (ranked) parts.push(t(locale, 'time.ranked', { time: ranked }))
  return parts.length ? parts.join(' · ') : null
}

/** How a check reads on the card. `stale` and `failed` are warnings and never close themselves. */
export function checkView(c: ItemCheck | undefined, now: Date = new Date(), locale: Locale = 'en'):
  { tone: 'ok' | 'info' | 'warn'; label: string; evidence?: string } | null {
  if (!c) return null
  const at = clockTime(c.at ?? c.startedAt, now, locale)
  const when = at ? ` · ${at}` : ''
  // The evidence is the publisher's sentence: shown as it arrives, never translated.
  switch (c.state) {
    case 'running': return { tone: 'info', label: t(locale, 'check.running') + (at ? t(locale, 'check.since', { time: at }) : '') }
    case 'stands': return { tone: 'ok', label: t(locale, 'check.stands') + when, evidence: c.evidence }
    case 'rewritten': return { tone: 'info', label: t(locale, 'check.rewritten') + when, evidence: c.evidence }
    case 'stale': return { tone: 'warn', label: t(locale, 'check.stale') + when, evidence: c.evidence }
    case 'failed': return { tone: 'warn', label: t(locale, 'check.failed') + when, evidence: c.evidence }
    default: return null
  }
}

/** "Later" choices, in seconds. The last one returns the item tomorrow at 08:00. */
export function laterChoices(now: Date, locale: Locale = 'en'): { label: string; seconds: number }[] {
  const tomorrow = new Date(now)
  tomorrow.setDate(now.getDate() + 1)
  tomorrow.setHours(8, 0, 0, 0)
  return [
    { label: t(locale, 'later.15m'), seconds: 15 * 60 },
    { label: t(locale, 'later.1h'), seconds: 3600 },
    { label: t(locale, 'later.2h'), seconds: 7200 },
    { label: t(locale, 'later.4h'), seconds: 4 * 3600 },
    { label: t(locale, 'later.tomorrow'), seconds: Math.round((tomorrow.getTime() - now.getTime()) / 1000) },
  ]
}

/**
 * When an "I'm working on it" card comes back. Tomorrow morning first — the common case is
 * "I'm on it today, ask me again tomorrow" — and it is the publisher's default too.
 */
export function progressChoices(now: Date, locale: Locale = 'en'): { label: string; seconds: number; primary?: boolean }[] {
  const tomorrow = new Date(now)
  tomorrow.setDate(now.getDate() + 1)
  tomorrow.setHours(8, 0, 0, 0)
  return [
    { label: t(locale, 'later.tomorrow'), seconds: Math.round((tomorrow.getTime() - now.getTime()) / 1000), primary: true },
    { label: t(locale, 'later.2h'), seconds: 7200 },
    { label: t(locale, 'later.4h'), seconds: 4 * 3600 },
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
  /** Whether the publisher heard the focus, and its answer; absent from an older server. */
  publisher?: { delivered: boolean; outcome?: string | null; reason?: string | null }
}

/** Squash a name for matching: "a-cme", "A Cme" and "acme" all read as "acme". */
const squash = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '')

/**
 * Projects matching what the owner typed, best first: a name that starts with the query, then
 * one that contains it. Separators are ignored both ways, so "a-cme" finds "acme-web".
 */
export function matchProjects(query: string, names: string[], limit = 6): string[] {
  const q = squash(query)
  if (!q) return []
  const starts: string[] = []
  const contains: string[] = []
  for (const n of names) {
    const s = squash(n)
    if (s.startsWith(q)) starts.push(n)
    else if (s.includes(q)) contains.push(n)
  }
  return [...starts, ...contains].slice(0, limit)
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
  /** The card's own text language (`now.locale`); absent from a server older than the setting. */
  locale?: Locale
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
export function goalsFailure(p: GoalsPayload | null, loadError: string | null, locale: Locale = 'en'): string | null {
  if (loadError) return t(locale, 'goals.loadError', { error: loadError })
  if (!p || p.measured !== false) return null
  return p.reason ? t(locale, 'goals.readErrorReason', { reason: p.reason }) : t(locale, 'goals.readError')
}

/** The muted notes above the goals list: everything incomplete about the answer. */
export function goalsNotes(p: GoalsPayload, locale: Locale = 'en'): string[] {
  const out: string[] = []
  if (p.partial) {
    out.push(p.unreadSources.length
      ? t(locale, 'goals.partialUnread', { list: p.unreadSources.join('; ') })
      : t(locale, 'goals.partial'))
  } else if (p.unreadSources.length) {
    out.push(t(locale, 'goals.unread', { list: p.unreadSources.join('; ') }))
  }
  if (p.stale && p.ageSeconds != null) out.push(t(locale, 'goals.stale', { age: hoursAgo(p.ageSeconds, locale) }))
  const bad: string[] = []
  if (p.malformedGoals > 0) bad.push(t(locale, 'goals.badGoals', { n: p.malformedGoals }))
  if (p.malformedAdvice > 0) bad.push(t(locale, 'goals.badAdvice', { n: p.malformedAdvice }))
  if (bad.length) out.push(t(locale, 'goals.unreadable', { what: bad.join(t(locale, 'goals.and')) }))
  return out
}

const DEFAULT_GOAL_OUTCOME: Record<GoalAction, MsgKey> = {
  keep: 'goalOutcome.keep',
  drop: 'goalOutcome.drop',
  rename: 'goalOutcome.rename',
  accept: 'goalOutcome.accept',
  decline: 'goalOutcome.decline',
}

export function goalFeedbackText(action: GoalAction, res: GoalActResponse, locale: Locale = 'en'): string {
  if (!res.delivered) return res.reason || t(locale, 'goalOutcome.notDelivered')
  return res.outcome || t(locale, DEFAULT_GOAL_OUTCOME[action])
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

// --------------------------------------------------------------------------- Calls tab
// The `owner-calls` answer (spec owner-calls-contract) as GET /api/fleet/now/calls serves it.

export type CallKind = 'promised' | 'retry' | 'missed' | 'follow-up'
export const CALL_KINDS: readonly CallKind[] = ['promised', 'retry', 'missed', 'follow-up']

export interface Call {
  id: string
  who: string
  about: string
  kind: CallKind
  phone?: string
  due?: string
  project?: string
  attempts?: number
  lastAttempt?: string
  firstSeen?: string
  evidence: GoalEvidence[]
  /** Computed by the server: the due time (a bare date: the end of that day) has passed. */
  overdue: boolean
}

export interface CallsPayload {
  publisher: { state: string; project: string | null; candidates: string[]; reason: string | null; acceptsActions: boolean }
  /** `null` = no project declares `owner-calls` — not a failure, not a zero. */
  measured: boolean | null
  reason: string | null
  calls: Call[]
  malformed: number
  partial: boolean
  unreadSources: string[]
  rankedAt: string | null
  ageSeconds: number | null
  stale: boolean
  acceptsActions: boolean
  overdueCount: number
  locale?: Locale
}

export type CallAction = 'called' | 'no-answer' | 'later' | 'not-needed'

export interface CallActBody { id: string; action: CallAction; text?: string; until?: string }

export type CallActResponse = GoalActResponse

/** Why the Calls tab is not showing a trustworthy answer, or null (an undeclared publisher is not a failure). */
export function callsFailure(p: CallsPayload | null, loadError: string | null, locale: Locale = 'en'): string | null {
  if (loadError) return t(locale, 'calls.loadError', { error: loadError })
  if (!p || p.measured !== false) return null
  return p.reason ? t(locale, 'calls.readErrorReason', { reason: p.reason }) : t(locale, 'calls.readError')
}

/** The muted notes above the calls list: everything incomplete about the answer. */
export function callsNotes(p: CallsPayload, locale: Locale = 'en'): string[] {
  const out: string[] = []
  if (p.partial) {
    out.push(p.unreadSources.length
      ? t(locale, 'calls.partialUnread', { list: p.unreadSources.join('; ') })
      : t(locale, 'calls.partial'))
  } else if (p.unreadSources.length) {
    out.push(t(locale, 'calls.unread', { list: p.unreadSources.join('; ') }))
  }
  if (p.stale && p.ageSeconds != null) out.push(t(locale, 'calls.stale', { age: hoursAgo(p.ageSeconds, locale) }))
  if (p.malformed > 0) out.push(t(locale, 'calls.bad', { n: p.malformed }))
  return out
}

/** What the tab label counts: calls still to make, and how many of them are overdue. */
export function callsCount(p: CallsPayload | null): { open: number; overdue: number } {
  if (!p || !p.measured) return { open: 0, overdue: 0 }
  return { open: p.calls.length, overdue: p.calls.filter(c => c.overdue).length }
}

/** A due value for the chip, in the card's clock format: "11-02" for a bare date, else "14:00" / "11-02 14:00". */
export function dueLabel(due: string, now: Date = new Date(), locale: Locale = 'en'): string {
  const d = due.trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(d)) return d.slice(5)
  return clockTime(d, now, locale) ?? d
}

const DEFAULT_CALL_OUTCOME: Record<CallAction, MsgKey> = {
  called: 'callOutcome.called',
  'no-answer': 'callOutcome.no-answer',
  later: 'callOutcome.later',
  'not-needed': 'callOutcome.not-needed',
}

export function callFeedbackText(action: CallAction, res: CallActResponse, locale: Locale = 'en'): string {
  if (!res.delivered) return res.reason || t(locale, 'callOutcome.notDelivered')
  return res.outcome || t(locale, DEFAULT_CALL_OUTCOME[action])
}

export async function fetchCalls(refresh = false): Promise<CallsPayload> {
  const res = await fetch(`/api/fleet/now/calls${refresh ? '?refresh=true' : ''}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const type = res.headers?.get?.('content-type') ?? ''
  if (type && !type.includes('json')) {
    throw new Error('the server answered with a page, not calls — its dashboard service predates the Calls tab and needs a restart')
  }
  return res.json()
}

/** POST an answer on a call. An HTTP refusal is turned into a not-delivered answer carrying its detail. */
export async function postCallAct(body: CallActBody): Promise<CallActResponse> {
  const res = await fetch('/api/fleet/now/calls/act', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { detail = (await res.json()).detail ?? detail } catch { /* keep the status */ }
    return { delivered: false, outcome: null, reason: String(detail), errorClass: 'http' }
  }
  return res.json()
}
