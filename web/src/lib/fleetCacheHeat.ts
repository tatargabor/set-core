/**
 * What a tab says about the cost of typing into it.
 *
 * A fleet tab reports whether an agent is running. It said nothing about what a
 * keystroke costs there — and that swings by a factor of twenty: a live prompt
 * cache is read at 0.1x the base input price, an expired one is rewritten at 2x.
 * Measured 2026-08-27, live sessions on one machine held between 15 044 and
 * 195 889 tokens, so the same keystroke cost between $0.008 and $1.96.
 *
 * ## The marks, and why each channel carries what it carries
 *
 * - **Bar LENGTH** fills with the cooling — empty when fresh, full at expiry,
 *   and it STAYS full. Filling rather than draining is what keeps a healthy tab
 *   silent: the mark's presence already means something. A draining countdown
 *   spent its whole visual budget on the healthy state and then vanished exactly
 *   when the tab became expensive, leaving cold and unmeasured identical.
 * - **Bar COLOUR** is the same fraction in three bands, so the state reads
 *   without hovering or comparing.
 * - **Bar THICKNESS** is the stake. Length is already spoken for, and time alone
 *   is not the decision: two tabs equally far along can differ thirteenfold in
 *   what they lose.
 * - **The name** turns red once cold, and **the price** appears beside it.
 *
 * ## One condition, not four
 *
 * `mark()` derives every cold-ward mark from a single `cold` flag, which comes
 * from the server. Four expressions would be four chances to disagree, and a tab
 * whose bar is full while its name is not leaves the reader unable to tell which
 * mark to believe.
 *
 * The server computes `cooled` and `cold` for the same reason: they are a
 * function of a clock, and a browser's clock is not the machine's. A tab
 * deriving its own expiry could disagree with the ordering PM mode does from the
 * same record.
 *
 * ## Absent is not cold
 *
 * A seat with no transcript has NO cache field. Rendered as cold it would tell
 * the reader to avoid a tab for a cost nobody computed; rendered as live it
 * invites a bill nobody predicted. It gets its own mark — the same `?` this
 * strip already uses for *withheld or unknown*.
 */

/** The cache state the fleet API attaches to an agent, when it measured one. */
export interface CacheState {
  /** When the last request STARTED — what the lifetime is measured from. */
  started_at: string
  /** cache_read + cache_creation of that request. */
  tokens: number
  ttl_seconds: number
  model: string | null
  /** `null` when the model is not in the price table — show tokens instead. */
  rewrite_usd: number | null
  seconds_remaining: number
  /** 0 at the request, 1 at expiry. Computed server-side, off one clock. */
  cooled: number
  cold: boolean
}

/** What the tab should draw. `kind` is the only thing callers branch on. */
export type CacheMark =
  | { kind: 'unmeasured' }
  | {
      kind: 'live' | 'cold'
      /** 0..1 — how much of the bar is drawn. */
      fill: number
      /** A tailwind background class. */
      colour: string
      /** Bar height in px, carrying the stake. */
      thickness: number
      /** The price to show beside the name, or null while live / unpriced. */
      price: string | null
      title: string
    }

/**
 * The thickness scale, in tokens — LOGARITHMIC, and the floor and ceiling are
 * both real numbers rather than round ones.
 *
 * ## The linear version was measured dead on a real fleet
 *
 * First build: linear against a 200 000-token ceiling. Looked right in the unit
 * tests (15 044 draws thinner than 195 889) and was useless on the screen —
 * measured 2026-08-27 against fourteen live sessions, every one of them held
 * between 190 994 and 554 959 tokens, so ALL FIVE tabs rendered at the maximum
 * thickness and the channel carried nothing. The tests could not see it because
 * they compare two numbers this repo's real sessions do not sit between.
 *
 * That is the check-verifies-the-mechanism shape: `thickness` did vary with
 * `tokens`, exactly as asserted, over a range no seat occupies.
 *
 * ## Why logarithmic, and why these two bounds
 *
 * Cache sizes move in orders of magnitude — the same fleet spans 15k to 555k —
 * and a linear scale spends most of its range on distinctions nobody has.
 *
 * The ceiling is the model's CONTEXT WINDOW: a session cannot cache more than
 * it can hold, so a bar at full thickness means "as large as this can get"
 * rather than "larger than a number somebody picked". The floor is where the
 * stake stops mattering — 20 000 tokens is about twenty cents to rewrite, and
 * below that the difference between two seats is not a difference anybody acts
 * on.
 *
 * Both bounds were then CHECKED against the real fleet rather than only
 * reasoned about: across the fourteen live sessions measured on 2026-08-27 they
 * produce four distinct thicknesses. A 10k floor produced three, and the linear
 * scale they replaced produced one.
 *
 * Scaled against a fixed range rather than against the current fleet's largest
 * seat: scaling to the fleet would make one tab's thickness change because a
 * DIFFERENT tab changed, which is a mark that moves without its subject moving.
 */
const THINNEST_AT_TOKENS = 20_000
const THICKEST_AT_TOKENS = 1_000_000

const MIN_THICKNESS = 1
const MAX_THICKNESS = 5

/**
 * Three bands, from the repo's own status palette.
 *
 * ⚠ These hues are RESERVED elsewhere on this surface: emerald means *running*,
 * red means *failed*. Spending them here was chosen by the user on 2026-08-27,
 * looking at a rendered twelve-tab strip where seven names were red. Recorded
 * rather than absorbed: if it grates in use, the exits are a dimmed name or a
 * muted red, and neither touches the geometry or the data.
 */
function band(cooled: number): string {
  if (cooled < 0.5) return 'bg-emerald-400'
  if (cooled < 0.75) return 'bg-amber-400'
  return 'bg-red-400'
}

/**
 * `$1.96`, `$.15` — narrow, because it shares a tab with a name.
 *
 * The leading zero is dropped from the ROUNDED string, never on the strength of
 * the raw number. Asking `usd < 1` and then slicing `toFixed(2)` are two
 * questions about two different values, and they disagree across [0.995, 1):
 * $0.9969 became `$.00`, a dollar of stake rendered as nothing.
 */
export function money(usd: number): string {
  const fixed = usd.toFixed(2)
  return `$${fixed.startsWith('0.') ? fixed.slice(1) : fixed}`
}

/**
 * The thousands separator: a NARROW NO-BREAK SPACE.
 *
 * Not a plain space, which would let `195 889` wrap across two lines in a
 * tooltip, and not a comma, which competes with the `·` this strip already uses
 * to join tooltip clauses.
 */
export const GROUP_SEPARATOR = '\u202f'

/**
 * `195 889` — grouped, because the eye reads a magnitude, not the digits.
 *
 * Grouped by hand rather than with `toLocaleString`. Measured 2026-08-27: under
 * this Node's ICU, `(195889).toLocaleString('en-US')` separates the digits with
 * U+202F rather than with commas, so the obvious-looking `replace(/,/g, ...)`
 * that followed it never matched anything and the separator it was meant to
 * install never appeared. What that function returns is a property of the
 * runtime's ICU build and the viewer's locale — neither of which this repo
 * controls — and a display string nobody can predict is one no test can hold.
 */
export function tokens(n: number): string {
  const digits = String(Math.round(Math.abs(n)))
  let out = ''
  for (let i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 === 0) out += GROUP_SEPARATOR
    out += digits[i]
  }
  return n < 0 ? `-${out}` : out
}

function minutes(seconds: number): string {
  const m = Math.round(seconds / 60)
  if (m >= 60) {
    const h = Math.floor(m / 60)
    return `${h}h ${m - h * 60}m`
  }
  return `${m}m`
}

/**
 * Bar thickness for a cache size, on the logarithmic scale above.
 *
 * Exported so a test can assert the SPREAD across sizes this repo actually
 * produces, rather than only that big beats small.
 */
export function thicknessFor(tokens: number): number {
  const span = Math.log(THICKEST_AT_TOKENS / THINNEST_AT_TOKENS)
  const position = Math.log(Math.max(1, tokens) / THINNEST_AT_TOKENS) / span
  return Math.max(MIN_THICKNESS, Math.min(MAX_THICKNESS,
    MIN_THICKNESS + Math.round((MAX_THICKNESS - MIN_THICKNESS) * position)))
}

/**
 * What to draw for one agent's cache state.
 *
 * `undefined` in means unmeasured out — the API omits the key entirely rather
 * than sending a null, so there is no convention to remember and no zero to
 * mistake for a measurement.
 */
export function mark(cache: CacheState | null | undefined): CacheMark {
  if (!cache) return { kind: 'unmeasured' }

  const fill = Math.max(0, Math.min(1, cache.cooled))
  const thickness = thicknessFor(cache.tokens)

  // The price is what rewriting this cache costs. Shown only once cold, because
  // only then does it decide anything: while the cache lives, its read cost is
  // what the reader pays whatever they do.
  const priced = cache.rewrite_usd !== null ? money(cache.rewrite_usd) : null

  const size = `${tokens(cache.tokens)} tokens`
  const cost = priced ? `, then ${priced} to rewrite` : ' (model not priced)'
  const title = cache.cold
    ? `prompt cache expired — ${size}${priced ? `, ${priced} to rewrite` : ', model not priced'}`
    : `prompt cache warm for ${minutes(cache.seconds_remaining)} — ${size}${cost}`

  return {
    kind: cache.cold ? 'cold' : 'live',
    fill: cache.cold ? 1 : fill,
    colour: band(fill),
    thickness,
    price: cache.cold ? priced : null,
    title,
  }
}

/** The title for a seat nothing was measured on — an absence, said out loud. */
export const UNMEASURED_TITLE =
  'prompt cache not measured — this seat has no transcript to read'
