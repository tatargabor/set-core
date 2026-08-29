/**
 * What the fleet header says about the quota that actually stops the work.
 *
 * The cache-heat marks beside these answer "what does a keystroke cost here".
 * This answers the other half — "how much is left to spend at all" — and the two
 * are deliberately different measurements: one is per session and read from a
 * transcript, this one is per ACCOUNT and read from the account service.
 *
 * ## Why the strip is per account and not per tab
 *
 * A per-tab mark would claim this agent consumed this share, and that claim
 * cannot be supported. Measured 2026-08-27: of the 40 most recent session
 * transcripts on one machine, **4 carried an owning-account identity and 36 did
 * not**, and the stored account entries carry no identifier to join on. A mark
 * on 4 tabs out of 40 does not look like a coverage gap — it looks like 36
 * agents consuming nothing.
 *
 * ## Two stripes, because one is unreadable
 *
 * 60 % consumed one hour into a five-hour window is a problem; 60 % four hours
 * in is fine. A single bar cannot tell those apart, so the elapsed share is
 * drawn under the consumed share and the comparison becomes something the eye
 * does. This is the shape the desktop Control Center has used since it shipped,
 * copied on purpose: two screens showing one fact should not teach two readings.
 *
 * ## The one thing computed here rather than server-side
 *
 * **The elapsed stripe**, from `resets_at` and the window length. Everything
 * else — consumption, severity, outcome — comes from the server, so the two
 * clocks can never disagree about whether a window is critical. Elapsed is the
 * exception because it moves every second and would otherwise be exactly as
 * stale as the last poll.
 *
 * ## Absent is not zero, and it is not one state either
 *
 * `unconfigured` (no account exists), `unreachable` (it did not answer) and
 * `unmeasured` (it answered and carried no figure) are three different facts.
 * Measured the same day, one of three live accounts was in the third state —
 * `200`, both windows `null`. Drawn as an empty bar it reads as "nothing
 * consumed", which is the most confident and least true thing the strip could
 * say.
 */

/** A window's scope, when the service reports one. Never synthesised here. */
export interface UsageScope {
  model: string | null
  surface: string | null
}

/** One rolling window as the API reports it. `utilization: null` means unknown. */
export interface UsageWindow {
  group: string
  kind: string
  utilization: number | null
  resets_at: string | null
  severity: string | null
  scope: UsageScope | null
  window_seconds: number | null
}

export interface UsageAccount {
  name: string
  kind: string
  outcome: 'measured' | 'unmeasured' | 'unreachable'
  active: boolean
  windows: UsageWindow[]
}

/** The endpoint's whole answer. `measured_at: null` means nobody has looked yet. */
export interface UsageSnapshot {
  accounts: UsageAccount[]
  measured_at: string | null
  interval_seconds: number | null
  last_error: string | null
}

/** What one window draws. `kind` is the only thing callers branch on. */
export type WindowMark =
  | { kind: 'unmeasured'; label: string; title: string }
  | {
      kind: 'measured'
      label: string
      /** 0..1 — the consumed stripe. */
      consumed: number
      /** 0..1 — how far the window itself has run. `null` when unknowable. */
      elapsed: number | null
      /** A tailwind background class for the consumed stripe. */
      tone: string
      critical: boolean
      title: string
    }

/**
 * The account-wide windows, in the order a reader expects them.
 *
 * The compact header mark carries these and nothing else: a model-scoped window
 * is a narrower fact than the quota that stops the work, and putting it in the
 * header would spend the same width on a smaller claim. It stays on the tooltip
 * and in the expanded rows.
 */
export function headlineWindows(row: AccountRow): WindowMark[] {
  return row.windows.filter(w => w.kind === 'measured' && !w.label.includes('('))
}

export interface AccountRow {
  name: string
  kind: string
  active: boolean
  state: 'measured' | 'unmeasured' | 'unreachable'
  windows: WindowMark[]
  /** Present only when the row has nothing to draw — the reason, in words. */
  note: string | null
}

export type StripState =
  | { kind: 'unavailable'; note: string }
  | { kind: 'no-accounts'; note: string }
  | {
      kind: 'ready'
      rows: AccountRow[]
      stale: boolean
      measuredAt: string
      criticalCount: number
      /** Accounts with at least one figure — the only ones the compact mark draws. */
      measuredRows: AccountRow[]
      /** Answered, and carried no figures. A count, never a bar. */
      unmeasuredCount: number
      /** Did not answer at all. A different count, for a different cause. */
      silentCount: number
    }

/** How long each window group runs, when the server did not say. */
const FALLBACK_SECONDS: Record<string, number> = { session: 5 * 3600, weekly: 7 * 24 * 3600 }

/** Short names for the two windows a reader recognises. */
const WINDOW_LABEL: Record<string, string> = { session: '5h', weekly: '7d' }

/**
 * A label for a window whose group is not in the table, derived from the
 * length the server reported — so an upstream that adds a window shape does
 * not have its label render as a raw group string. `null` when the length is
 * unknown too: then there is nothing honest to print short.
 */
function labelFromSeconds(seconds: number | null): string | null {
  if (!seconds) return null
  if (seconds % (7 * 24 * 3600) === 0) return `${seconds / (7 * 24 * 3600)}w`
  if (seconds % 3600 === 0) return `${seconds / 3600}h`
  if (seconds % 60 === 0) return `${seconds / 60}m`
  return `${seconds}s`
}

/**
 * Severity → colour, and the mapping is one-way on purpose.
 *
 * The percentage does NOT get a vote: the measurement already banded these
 * figures — by the service where the service states a band, and at measurement
 * for the source that states none (see `glm-usage-source`) — and a second
 * threshold chosen here would be a third opinion. Measured 2026-08-27, a 96 %
 * weekly window arrived labelled `critical` without anybody in this repo
 * picking 96.
 *
 * ⚠ `bg-red-400` is this strip's critical colour and is spent on nothing else
 * here — no border, no hover, no decoration.
 */
export function toneFor(severity: string | null): string {
  if (severity === 'critical') return 'bg-red-400'
  if (severity === 'warning') return 'bg-amber-400'
  return 'bg-sky-400'
}

/** `18%`, `2%` — whole percent, because the bar carries the precision. */
function percent(value: number): string {
  return `${Math.round(value)}%`
}

/**
 * How far into its window a quota is, from the reset time.
 *
 * `null` when the reset time or the window length is missing — the caller draws
 * no elapsed stripe rather than one anchored to a guess. A guessed elapsed
 * stripe is worse than none: it is the half of the comparison that makes the
 * consumed stripe mean something.
 */
export function elapsedFraction(
  window: UsageWindow,
  now: number,
): number | null {
  const seconds = window.window_seconds ?? FALLBACK_SECONDS[window.group] ?? null
  if (!window.resets_at || !seconds) return null
  const resets = Date.parse(window.resets_at)
  if (Number.isNaN(resets)) return null
  const remaining = (resets - now) / 1000
  return Math.max(0, Math.min(1, (seconds - remaining) / seconds))
}

function scopeSuffix(window: UsageWindow): string {
  const model = window.scope?.model
  return model ? ` (${model})` : ''
}

function windowLabel(window: UsageWindow): string {
  const known = WINDOW_LABEL[window.group]
    ?? labelFromSeconds(window.window_seconds)
    ?? window.group
  return `${known}${scopeSuffix(window)}`
}

/** What one window draws. A window with no figure is marked, never filled. */
export function markWindow(window: UsageWindow, now: number): WindowMark {
  const label = windowLabel(window)
  if (window.utilization === null || window.utilization === undefined) {
    return {
      kind: 'unmeasured',
      label,
      title: `${label}: the account answered and carried no figure for this window — `
        + 'not measured, which is not the same as nothing consumed',
    }
  }

  const consumed = Math.max(0, Math.min(1, window.utilization / 100))
  const elapsed = elapsedFraction(window, now)
  const critical = window.severity === 'critical'
  const pace = elapsed === null
    ? ''
    : ` · ${Math.round(elapsed * 100)}% of the window has run`
  const resets = window.resets_at ? ` · resets ${new Date(window.resets_at).toLocaleString()}` : ''

  return {
    kind: 'measured',
    label,
    consumed,
    elapsed,
    tone: toneFor(window.severity),
    critical,
    title: `${label}: ${percent(window.utilization)} consumed${pace}${resets}`
      + (window.severity ? ` · ${window.severity}` : ''),
  }
}

function rowFor(account: UsageAccount, now: number): AccountRow {
  const base = {
    name: account.name,
    kind: account.kind,
    active: account.active,
    state: account.outcome,
  }
  if (account.outcome === 'unreachable') {
    return {
      ...base,
      windows: [],
      note: 'did not answer — its credential may have expired',
    }
  }
  const windows = account.windows.map((w) => markWindow(w, now))
  const anyMeasured = windows.some((w) => w.kind === 'measured')
  return {
    ...base,
    windows,
    note: anyMeasured ? null : 'answered, and carried no figures',
  }
}

/**
 * The few characters that go before an account's compact bars, so the pairs can
 * be told apart without opening the detail.
 *
 * The 2026-08-27 request was bars only, and it stands for words and numbers —
 * but three same-shaped pairs are three facts the reader cannot attribute, and
 * on 2026-08-29 the user asked for a word, an icon or a letter before them.
 * For an email, the domain's first label is what actually distinguishes
 * accounts (`gmail`, `itline`); the shared local part distinguishes nothing.
 * Anything else is the name itself, capped.
 */
export function shortLabel(name: string): string {
  const at = name.lastIndexOf('@')
  if (at >= 0 && at < name.length - 1) {
    return name
      .slice(at + 1)
      .split('.')[0]
      .slice(0, 12)
  }
  return name.slice(0, 12)
}

/**
 * One line naming everything about an account, for the compact mark's tooltip.
 *
 * The name has to go SOMEWHERE. Compacting to icons and numbers was asked for by
 * the user (2026-08-27, on the built screen: *"ez nagyon sok helyet elvisz … csak
 * a mukodo statusz barokat … szovegek nem kellenek"*), and the same request the
 * header's chips already answer — but a mark whose subject cannot be recovered
 * at all is a different thing from a compact one.
 */
export function rowTitle(row: AccountRow): string {
  const windows = row.windows.map(w =>
    w.kind === 'measured'
      ? `${w.label}: ${Math.round(w.consumed * 100)}%`
        + (w.elapsed === null ? '' : ` of a window ${Math.round(w.elapsed * 100)}% run`)
        + (w.critical ? ' — critical' : '')
      : `${w.label}: not measured`)
  return [row.name, ...windows, row.note].filter(Boolean).join('\n')
}

/** How many windows the measurement reported critical. Drives the collapsed mark. */
export function criticalCount(snapshot: UsageSnapshot | null | undefined): number {
  if (!snapshot) return 0
  return snapshot.accounts.reduce(
    (total, account) => total + account.windows.filter((w) => w.severity === 'critical').length,
    0,
  )
}

/**
 * The whole strip, in one value.
 *
 * `unavailable` covers both "the request failed" and "no measurement has
 * completed yet" — from the reader's side those are the same sentence, and the
 * screen must render either way. The header is never allowed to wait for this.
 */
export function stripState(
  snapshot: UsageSnapshot | null | undefined,
  now: number,
): StripState {
  if (!snapshot || !snapshot.measured_at) {
    return {
      kind: 'unavailable',
      note: snapshot?.last_error
        ? `usage could not be measured (${snapshot.last_error})`
        : 'usage has not been measured yet',
    }
  }
  if (snapshot.accounts.length === 0) {
    return { kind: 'no-accounts', note: 'no account is configured for usage' }
  }

  const measured = Date.parse(snapshot.measured_at)
  const interval = (snapshot.interval_seconds ?? 60) * 1000
  // Stale means "older than one poll", not "old" — the interval is the only
  // honest yardstick, and it comes from the server that owns the clock.
  const stale = Number.isNaN(measured) ? true : now - measured > interval

  const rows = snapshot.accounts.map((a) => rowFor(a, now))

  // The three groups are counted here rather than in the component, so the
  // compact mark and the expanded rows cannot disagree about which account is in
  // which state. An account that answered nothing gets a NUMBER, not a bar:
  // drawing it would be the empty-bar reading this module exists to prevent, and
  // dropping it entirely would hide a failure behind a tidier header.
  return {
    kind: 'ready',
    rows,
    stale,
    measuredAt: snapshot.measured_at,
    criticalCount: criticalCount(snapshot),
    measuredRows: rows.filter(r => r.state === 'measured'),
    unmeasuredCount: rows.filter(r => r.state === 'unmeasured').length,
    silentCount: rows.filter(r => r.state === 'unreachable').length,
  }
}
