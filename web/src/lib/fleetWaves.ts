/**
 * Every known project's wave boards — the pure half of the fleet's header chip.
 *
 * The server reads `docs/waveboard/*.json` per project and returns summaries
 * (`GET /api/fleet/waveboards`); this orders them, totals them, and turns one
 * board's counts into the segments of its progress bar. Kept pure so the order
 * and the arithmetic are tested without a screen.
 */

export const WAVE_STATUSES = ['done', 'doing', 'blocked', 'todo', 'skipped'] as const
export type WaveStatus = typeof WAVE_STATUSES[number]

export interface ReadableBoard {
  project: string
  job: string
  title: string
  artifact_url: string | null
  counts: Record<WaveStatus, number>
  other: number
  waves: number
  current_wave: { id: string; title: string } | null
  updated: string | null
  // Staleness (change `wave-board-staleness`). Optional, so a board from a
  // server older than the change still renders — without a marker, and with
  // "not measured" in its tooltip rather than a claim that it is current.
  /** When an agent last confirmed the board's manual items, or null. */
  reviewed?: string | null
  /** Open items sync cannot move: no evidence, or blocked. */
  manual_open?: number
  /** Commits on the project's HEAD since the board last changed; null = not measured. */
  commits_since_change?: number | null
  /** Manual items are open and the repository moved on by the threshold. */
  stale?: boolean
  unreadable: false
}

export interface UnreadableBoard {
  project: string
  job: string
  unreadable: true
  reason: string
}

export type WaveBoard = ReadableBoard | UnreadableBoard

export interface WaveTotals {
  boards: number
  blocked: number
  unreadable: number
  /** Boards whose statuses the repository has moved past — their blocked count included. */
  stale: number
}

/** The selected project's boards first, then by project name, then by job. */
export function orderBoards(boards: WaveBoard[], selected: string | null): WaveBoard[] {
  return [...boards].sort((a, b) => {
    const as = a.project === selected ? 0 : 1
    const bs = b.project === selected ? 0 : 1
    if (as !== bs) return as - bs
    return a.project.localeCompare(b.project) || a.job.localeCompare(b.job)
  })
}

/** What the closed chip shows. Unreadable boards are counted, never folded into zero. */
export function totals(boards: WaveBoard[]): WaveTotals {
  let blocked = 0
  let unreadable = 0
  let stale = 0
  for (const b of boards) {
    if (b.unreadable) unreadable += 1
    else {
      blocked += b.counts.blocked ?? 0
      if (b.stale === true) stale += 1
    }
  }
  return { boards: boards.length, blocked, unreadable, stale }
}

export interface BarSegment {
  status: WaveStatus | 'other'
  count: number
  /** Share of the whole board, 0–100. */
  percent: number
}

/** The bar, in a fixed status order; empty statuses are left out. */
export function barSegments(board: ReadableBoard): BarSegment[] {
  const parts: Array<[WaveStatus | 'other', number]> = [
    ...WAVE_STATUSES.map(s => [s, board.counts[s] ?? 0] as [WaveStatus, number]),
    ['other', board.other ?? 0],
  ]
  const total = parts.reduce((n, [, c]) => n + c, 0)
  if (total === 0) return []
  return parts
    .filter(([, c]) => c > 0)
    .map(([status, count]) => ({ status, count, percent: (count / total) * 100 }))
}

/** Items on the board, every status included. */
export function itemTotal(board: ReadableBoard): number {
  return WAVE_STATUSES.reduce((n, s) => n + (board.counts[s] ?? 0), 0) + (board.other ?? 0)
}

/** Seconds since an ISO timestamp, or null when there is none or it does not parse. */
export function secondsSince(iso: string | null, now: number): number | null {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : Math.max(0, (now - t) / 1000)
}

/**
 * The route's boards, keeping only entries with the shape this list renders.
 *
 * Same reason as the relay control's parser: a header widget fed an unexpected payload
 * must show less, never crash the screen it sits on.
 */
export function parseBoards(d: unknown): WaveBoard[] {
  const raw = d && typeof d === 'object' ? (d as { boards?: unknown }).boards : null
  if (!Array.isArray(raw)) return []
  return raw.filter((b): b is WaveBoard => {
    if (!b || typeof b !== 'object') return false
    const o = b as Record<string, unknown>
    if (typeof o.project !== 'string' || typeof o.job !== 'string') return false
    return o.unreadable === true || (!!o.counts && typeof o.counts === 'object')
  })
}
