// Pure scheduling logic of the feed-watch pane: no `$`, so the tests call it directly.
// Lifted from a consumer's first version; the only structural change is that the opt-in
// and the slot state are keyed by PROJECT ROOT, because set-core serves many projects.

/** One project's entry in `<set-core config dir>/feed-watch.json` → `projects[<root>]`. Never committed. */
export type Entry = {
  enabled: boolean
  /** The Claude account e-mail that opted in; the pane stays off for every other account. */
  account: string
  /** Local "HH:MM" times. */
  times: string[]
}

/** One project's slot state in `feed-watch.state.json` → `projects[<root>]`, shared by the user's sessions. */
export type SlotState = {
  /** slot ("YYYY-MM-DD HH:MM") -> "run" | "skip" */
  handled: Record<string, string>
  snoozeUntil?: number
  /** "YYYY-MM-DD": no more prompts that day. */
  skipDate?: string
  /** Which session shows the pane now, so two open sessions do not both ask. */
  shown?: { slot: string; by: string; at: number }
}

export const DEFAULT_TIMES = ['08:30', '18:30']
export const SNOOZE_MS = 60 * 60 * 1000
export const LEASE_MS = 30 * 60 * 1000

const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/

type Doc = { projects?: Record<string, unknown> }

function projectsOf(text: string | undefined): Record<string, unknown> {
  try {
    const raw = text ? (JSON.parse(text) as Doc) : {}
    return raw.projects && typeof raw.projects === 'object' ? raw.projects : {}
  } catch {
    return {}
  }
}

export function parseEntry(text: string | undefined, root: string): Entry | null {
  const raw = projectsOf(text)[root] as Partial<Entry> | undefined
  if (!raw || typeof raw !== 'object') return null
  const times = Array.isArray(raw.times) ? raw.times.filter(t => typeof t === 'string' && HHMM.test(t)) : []
  return {
    enabled: raw.enabled === true,
    account: typeof raw.account === 'string' ? raw.account.trim() : '',
    times: (times.length > 0 ? times : DEFAULT_TIMES).slice().sort(),
  }
}

/** The whole opt-in document with one project's `enabled` switched off; other projects untouched. */
export function disabled(text: string | undefined, root: string): string {
  let doc: Doc = {}
  try {
    doc = text ? (JSON.parse(text) as Doc) : {}
  } catch {
    doc = {}
  }
  const projects = { ...projectsOf(text) }
  projects[root] = { ...((projects[root] as object) ?? {}), enabled: false }
  return JSON.stringify({ ...doc, projects }, null, 2)
}

export function parseState(text: string | undefined, root: string): SlotState {
  const raw = projectsOf(text)[root] as Partial<SlotState> | undefined
  if (!raw || typeof raw !== 'object') return { handled: {} }
  return { ...raw, handled: raw.handled && typeof raw.handled === 'object' ? raw.handled : {} }
}

/** The whole state document with one project's state replaced; other projects untouched. */
export function withState(text: string | undefined, root: string, st: SlotState): string {
  return JSON.stringify({ projects: { ...projectsOf(text), [root]: st } }, null, 2)
}

/** `.oauthAccount.emailAddress` of `~/.claude.json`: the account this session runs as. */
export function accountEmail(claudeJson: string | undefined): string {
  try {
    const email = (JSON.parse(claudeJson ?? '') as { oauthAccount?: { emailAddress?: unknown } }).oauthAccount?.emailAddress
    return typeof email === 'string' ? email.trim() : ''
  } catch {
    return ''
  }
}

/** On only when the entry is enabled AND it was made by the account running this session. */
export function isActive(e: Entry | null, email: string): boolean {
  return e !== null && e.enabled && e.account !== '' && email !== '' && e.account.toLowerCase() === email.toLowerCase()
}

/** The slot to ask about now, or null. A missed slot stays due until the next declared time replaces it. */
export function dueSlot(date: string, hhmm: string, times: string[], st: SlotState, nowMs: number): string | null {
  const passed = times.filter(t => t <= hhmm)
  if (passed.length === 0) return null
  const slot = `${date} ${passed[passed.length - 1]}`
  if (st.skipDate === date) return null
  if (st.handled[slot]) return null
  if (st.snoozeUntil !== undefined && nowMs < st.snoozeUntil) return null
  return slot
}

/** Another live session already shows this slot's pane. */
export function heldByOther(st: SlotState, slot: string, me: string, nowMs: number): boolean {
  return st.shown !== undefined && st.shown.slot === slot && st.shown.by !== me && nowMs - st.shown.at < LEASE_MS
}

export function slotLabel(slot: string): string {
  const hh = Number(slot.slice(11, 13))
  const t = slot.slice(11)
  return hh < 12 ? `morning (${t})` : hh < 17 ? `afternoon (${t})` : `evening (${t})`
}

export type Answer = 'run' | 'snooze' | 'tomorrow'

export function answer(st: SlotState, slot: string, a: Answer, nowMs: number): SlotState {
  const date = slot.slice(0, 10)
  const base: SlotState = { ...st, handled: { ...st.handled }, shown: undefined }
  // keep only the last 14 days of handled slots
  for (const k of Object.keys(base.handled)) if (k.slice(0, 10) < shiftDate(date, -14)) delete base.handled[k]
  if (a === 'run') base.handled[slot] = 'run'
  if (a === 'snooze') base.snoozeUntil = nowMs + SNOOZE_MS
  if (a === 'tomorrow') {
    base.handled[slot] = 'skip'
    base.skipDate = date
  }
  return base
}

function shiftDate(date: string, days: number): string {
  const d = new Date(`${date}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}
