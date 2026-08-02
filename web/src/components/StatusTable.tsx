/**
 * A table of rows a project reported about itself — dense, searchable, sortable.
 *
 * Everything here is a way of showing FEWER rows, or less of a row, than arrived. That is
 * the whole subject of this file, and it is why it has a spec of its own: the surface's
 * governing rule is *compacting must never hide a failure*, and a filter is the most
 * effective hiding mechanism yet invented — the reader chose it, so nobody goes looking for
 * what is missing.
 *
 * Three consequences, all load-bearing:
 *
 * - **A filter always states what it withheld**, in the same place the row count already is.
 *   Not in a tooltip, not in the control that caused it.
 * - **The delivered order is recoverable** without a reload. Row order is a decision made by
 *   the side that owns the data; a sort that cannot be undone overwrites it silently.
 * - **Nothing here is persisted.** Not `localStorage`, and not the URL — a chosen facet value
 *   IS the project's data, and the address bar reaches disk through history and sync.
 *
 * And, as everywhere on this surface: **no field name is recognised.** A column becomes
 * filterable because its values are categorical, which is a property of the values. The
 * tempting alternative — a list of names like `severity` or `status` — would work today, on
 * one project, and is exactly the coupling the renderer exists to avoid.
 */

import { useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  ACTIONS_KEY,
  ActionCtx,
  type BatchAction,
  DeprecatedLabel,
  Emphasis,
  HiddenNote,
  CELL_CLIP_CHARS,
  cellClipPxFor,
  tablePxWidth,
  META_KEYS,
  RowActions,
  Unknown,
  columnsOf,
  emphasisMatches,
  emphasisOf,
  flattenUniformObjects,
  isPlainObject,
  partitionKeys,
  useDeprecation,
} from './statusShape'

/**
 * Below this many rows the table renders exactly as it always has: full-height cells, no
 * controls. A search box over five rows is noise, and noise is how a control gets ignored
 * on the table where it matters. Small tables also have room to show their values whole,
 * which is more readable than clipping them.
 */
export const CONTROL_MIN_ROWS = 8

/**
 * How many rows render before the rest go behind a single "show all" click.
 *
 * The table no longer scrolls inside its own box — that inner scrollbar sat inside the page's
 * scrollbar, and two nested scrollbars is a worse answer than one. So the page is the only
 * vertical scroller, and a 108-row answer would otherwise make the page enormous. The cap is
 * the same bargain the chip list already strikes: show a workable slice, ALWAYS state how many
 * are held back, and keep them one click away. A cap that hid rows silently would be the
 * false-absence shape this surface refuses everywhere else.
 */
export const ROW_CAP = 25

/** Below this many rows a split reads as a broken table rather than as flowing columns. */
const MIN_ROWS_TO_FLOW = 12
/** Past three groups the eye stops knowing which column continues from which. */
const MAX_FLOW_GROUPS = 3
/** A group thinner than this stops looking like a table. */
const MIN_ROWS_PER_GROUP = 6
/** The gutter between groups, matching `gap-x-6`. */
const FLOW_GAP_PX = 24
/**
 * The widths live in `statusShape` beside the estimator that uses them, and are imported rather
 * than restated here.
 *
 * The cell's clip used to be a literal `max-w-[22rem]` in its class list — 352px, which agreed
 * with `CELL_CLIP_CHARS × PX_PER_CHAR` on the day it was typed and was invisible to anybody
 * reading the estimator. That is the second-copy drift this file already warns about where the
 * flatten rules are explained; a Tailwind literal is the worst version of it, because no rename
 * or type error can ever reach it.
 */

/** A column is categorical when it has few enough distinct values to be worth choosing between. */
export const FACET_MAX_DISTINCT = 12
/** …and few enough RELATIVE to the rows. Both bounds are needed — see below. */
export const FACET_MAX_SHARE = 0.5

type Row = Record<string, unknown>

function isScalar(v: unknown): boolean {
  return v === null || v === undefined
    || typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean'
}

/**
 * The text a cell contributes to a FACET — the value as the project gave it.
 *
 * Deliberately empty for a structured value: a facet keys on this string, and keying on a
 * flattened object would produce one chip per row. Structured columns are excluded from facets
 * by `isScalar` anyway; this keeps the two agreeing rather than relying on the caller.
 */
function cellText(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v === 'object') return ''
  return String(v)
}

/**
 * The text a cell contributes to SEARCH — every scalar leaf inside it.
 *
 * Split from `cellText` because the two answer different questions, and until this existed the
 * search answered the wrong one: `cellText` returns `''` for any object, so a structured cell
 * contributed NOTHING to the index. A project publishing a richer value — a source with a date
 * and the people in it, rather than an opaque identifier — would have watched it disappear from
 * search, and the box would have said "no rows" rather than "not indexed". The reassuring
 * direction, on the one control a reader uses to decide something is not there.
 *
 * **Leaves only: no key names, no punctuation.** Serialising the object and searching the text is
 * the obvious shortcut and it is wrong in a way that looks right — every row contains the word
 * `date` if `date` is a key, so a search for it matches everything. A control that cannot narrow
 * is what the facet bounds in this file already exist to prevent.
 * `test_searching_the_serialised_object_would_match_a_key_name` holds the refuted version.
 */
export function searchText(v: unknown): string {
  if (v === null || v === undefined) return ''
  if (typeof v !== 'object') return String(v)
  const out: string[] = []
  const walk = (x: unknown) => {
    if (x === null || x === undefined) return
    if (Array.isArray(x)) { x.forEach(walk); return }
    if (typeof x === 'object') { Object.values(x as Record<string, unknown>).forEach(walk); return }
    out.push(String(x))
  }
  walk(v)
  return out.join(' ')
}

/**
 * Which columns can be filtered, and how many rows each of their values covers.
 *
 * Both bounds matter and they fail in opposite directions. Without the absolute cap, a column
 * with 60 distinct values over 67 rows becomes a facet of 60 one-row chips — a control that
 * cannot narrow anything. Without the relative cap, a two-value column over four rows becomes
 * a facet that hides nothing. Either way the result is a control nobody uses, which is worse
 * than no control: it trains the reader to ignore the row of things above the table.
 *
 * Counts are over the delivered rows, never over a declaration — the same rule that makes the
 * deprecation count come from the data.
 */
export function facetColumns(rows: Row[], cols: string[]): Map<string, Map<string, number>> {
  const facets = new Map<string, Map<string, number>>()
  const maxDistinct = Math.min(FACET_MAX_DISTINCT, Math.floor(rows.length * FACET_MAX_SHARE))
  for (const col of cols) {
    const values = rows.map(r => r[col])
    if (!values.every(isScalar)) continue
    const counts = new Map<string, number>()
    for (const v of values) {
      const text = cellText(v)
      if (text === '') continue
      counts.set(text, (counts.get(text) ?? 0) + 1)
    }
    // One value is not a choice, and zero is not a column worth offering.
    if (counts.size < 2 || counts.size > maxDistinct) continue
    facets.set(col, counts)
  }
  return facets
}

/**
 * How many distinct values a column may hold and still be worth tinting.
 *
 * Six is the token layer's palette size, and past it a colour code stops being readable — the
 * reader would be matching seven near-hues instead of scanning. A column beyond the cap renders
 * plain, which is the honest outcome: no tint at all is better than a tint that means nothing.
 */
const TINT_MAX_DISTINCT = 6

/**
 * The tint classes, written out one by one — never built as `text-cat-${i}`.
 *
 * Tailwind emits a utility only when it finds the class name as a LITERAL in the source, so the
 * interpolated version compiled to nothing: the map was populated, the class landed on the cell,
 * and the stylesheet contained zero `text-cat-*` rules. `grep -c text-cat- dist/assets/*.css`
 * returned 0. Every part of the mechanism worked and the screen was unchanged — the failure mode
 * this repo keeps meeting, where a check on the mechanism passes and says nothing about the result.
 *
 * The descendant variant is deliberate too: the value renderer sets its own `text-fg-strong`, and
 * a colour on the cell alone loses to it. Tinting the cell's spans is what actually reaches the
 * text a reader sees.
 */
const CAT_CLASS = [
  '[&_span]:text-cat-1',
  '[&_span]:text-cat-2',
  '[&_span]:text-cat-3',
  '[&_span]:text-cat-4',
  '[&_span]:text-cat-5',
  '[&_span]:text-cat-6',
] as const

/** Beyond this length a value is prose, not a category, and a hue on it reads as decoration. */
const TINT_MAX_CHARS = 16

/**
 * A stable hue per distinct value, for columns that behave like a small set of categories.
 *
 * Measured against the sibling screen: the orchestration view carries 2.14 % hued pixels and this
 * one 0.15 %, almost all of it a single button. The difference is not taste — that view knows what
 * its own states mean and can colour them, and this one must not learn any project's vocabulary.
 *
 * So the colour comes from CARDINALITY, which needs no vocabulary at all: a column holding a few
 * repeating values gets one hue per value, and rows sharing a value become scannable as a group.
 * The renderer still cannot say which value is good.
 *
 * Two properties do the safety work. The assignment is by SORTED ORDER, so a value keeps its hue
 * across sorting, filtering and refreshes — a colour that moved would be worse than none. And the
 * palette deliberately excludes every hue this surface has given a meaning: amber (withheld),
 * emerald (true), red (failed), blue (an action). A tint can therefore distinguish, and cannot
 * imply a verdict it did not measure.
 */
export function categoryTints(rows: Row[], cols: string[]): Map<string, Map<string, string>> {
  const tints = new Map<string, Map<string, string>>()
  for (const col of cols) {
    const distinct = new Set<string>()
    let tintable = true
    for (const r of rows) {
      const v = r[col]
      if (isMissing(v)) continue
      // Numbers are excluded, and this was found by looking rather than reasoned about: a `count`
      // column of 25 / 9 / 27 passed every cardinality test and came out in three hues, as if the
      // quantities were three groups. A tint says "these rows share a value"; on a quantity that
      // reads as a scale, and the palette carries no scale — so it would imply an ordering it
      // cannot have measured. Booleans are excluded for the opposite reason: they already have a
      // meaning-bearing colour, and a second one would fight it.
      if (!isScalar(v) || typeof v === 'boolean' || typeof v === 'number') { tintable = false; break }
      const text = cellText(v)
      if (text.length > TINT_MAX_CHARS) { tintable = false; break }
      distinct.add(text)
      if (distinct.size > TINT_MAX_DISTINCT) { tintable = false; break }
    }
    // One value is not a distinction worth a colour, and a column of unique values is a list of
    // identifiers — tinting every row differently would be noise wearing a code's clothes.
    if (!tintable || distinct.size < 2 || distinct.size === rows.length) continue
    const map = new Map<string, string>()
    ;[...distinct].sort().forEach((v, i) => map.set(v, CAT_CLASS[i]))
    tints.set(col, map)
  }
  return tints
}

/**
 * Order two cells of one column.
 *
 * Absent values sort last in BOTH directions, deliberately. Sorting them to the top in one
 * direction would put "we don't know" where a reader scans first and read as a value — the
 * same false-absence shape this surface spends its whole existence refusing.
 */
export function isMissing(v: unknown): boolean {
  return v === null || v === undefined || v === ''
}

export function compareValues(a: unknown, b: unknown): number {
  const aMissing = isMissing(a)
  const bMissing = isMissing(b)
  if (aMissing && bMissing) return 0
  if (aMissing) return 1
  if (bMissing) return -1
  if (typeof a === 'number' && typeof b === 'number') return a - b
  return String(a).localeCompare(String(b), undefined, { numeric: true })
}

/**
 * The column whose values identify a row — chosen from the VALUES, never from a name.
 *
 * A selection has to survive sorting and filtering, so it cannot be a set of row indices: after a
 * sort, index 3 is a different row than the one that was clicked, and the selection would silently
 * point at rows nobody chose. So a selected row is remembered by its identifying value.
 *
 * The framework may not recognise `id`, `key` or any other domain name — the surface's first
 * requirement forbids it, and the first producer that names its identifier differently would break
 * it. Instead: the first column that is scalar, present in every row, and unique across all of
 * them. That is a property of the data, so it holds for a producer writing in any language.
 *
 * Returns null when no column qualifies. The caller then falls back to row position AND SAYS SO —
 * a fallback that is silent would let a sort reselect different rows, which is the exact defect
 * this function exists to prevent.
 */
export function identityColumn(rows: Row[], cols: string[]): string | null {
  if (rows.length === 0) return null
  for (const col of cols) {
    const seen = new Set<string>()
    for (const r of rows) {
      const v = r[col]
      if (!isScalar(v) || isMissing(v)) break
      const text = String(v)
      if (seen.has(text)) break
      seen.add(text)
    }
    if (seen.size === rows.length) return col
  }
  return null
}

interface SortState { col: string; dir: 'asc' | 'desc' }

/** The cell as it appears in a dense row: one line, clipped, with the whole value in reach. */
function Cell(
  { children, text, clipPx, lines }:
  { children: ReactNode; text: string; clipPx: number; lines: 1 | 2 },
) {
  // Two lines are only ever offered to a SHORT table — see `cellLines`. The clamp still ends in
  // an ellipsis, so nothing becomes silent by gaining a second line.
  //
  // The clamp is set INLINE rather than with the utility class, and that is a measurement, not a
  // preference: with `line-clamp-2` alone the computed style came back `-webkit-line-clamp: 2`
  // and `display: flow-root`, and the clamp does nothing without `-webkit-box`. A 327-character
  // cell rendered 100px tall — five lines — while every class-level check said the clamp was
  // applied. The property was present and the effect was absent.
  // A HEIGHT bound, not a line-clamp, and that is a measurement rather than a style preference.
  // With the clamp set inline the element carried `display: -webkit-box` in its style attribute
  // and reported `display: flow-root` as its computed value, so the clamp did nothing: a
  // 327-character cell rendered 100px tall — five lines — while every check short of measuring
  // the rendered box agreed the clamp was applied. A max-height cannot be quietly ignored.
  //
  // The reader still reaches the rest: the row expands, and the cell keeps its `title`.
  const clamp = lines === 2
    ? { maxHeight: `${TWO_LINES_EM}em`, overflow: 'hidden' as const }
    : {}
  return (
    <div
      className={lines === 2 ? 'whitespace-normal' : 'truncate'}
      style={{ maxWidth: clipPx, ...clamp }}
      title={text || undefined}
    >
      {children}
    </div>
  )
}

/**
 * How many lines a clipped cell may use.
 *
 * One, except in a table short enough that a second line costs nothing. The case that prompted
 * it: a two-row table whose one long column carried an open human decision, cut mid-sentence at
 * `…prisma migrate deploy` + `prisma` — a reader could see that a decision was waiting and not
 * what it was about. Sixty percent of the sentence was on screen and the rest needed a click.
 *
 * The bound is rows, not characters, because the cost of a second line is paid per row: at
 * twenty-five rows it doubles the table's height and the density that makes a table worth
 * reading is gone. At two rows it is free. `FEW_ROWS` is deliberately well under `ROW_CAP`.
 *
 * The expander stays either way. Two lines is more of the sentence, not all of it.
 */
const FEW_ROWS = 6

/** Two lines of the table's own leading, plus the sliver that keeps a descender from being cut. */
const TWO_LINES_EM = 2.9

function cellLines(rowCount: number, groups: number): 1 | 2 {
  return groups === 1 && rowCount <= FEW_ROWS ? 2 : 1
}

/**
 * Is this value one that a table cell cannot hold at its own size?
 *
 * Objects, lists of objects, and lists of more than two scalars.
 *
 * That last clause replaces the opposite rule, and the correction is worth keeping because the
 * reasoning behind it sounded right. A chip list already compacts itself and states what it
 * withheld — `+4 more` — so displacing one looked like taking a working control away. Measured
 * after the objects were displaced: it is not the chip list's CAP that fails in a cell, it is
 * its WRAP. Five chips at roughly 70px in a 90px column stack five rows deep, and that residual
 * stack was the whole of the remaining tower — max row 154px against a 37px median.
 *
 * So the bound is the line, not the item count: a value that cannot occupy one line in a cell
 * does not belong in the cell. Two chips fit; more do not.
 */
const INLINE_CHIP_MAX = 2

/**
 * Roughly the number of monospace characters that fit the cell's 22rem clip before the ellipsis.
 * Approximate on purpose: it decides whether a row can be OPENED, and erring toward offering the
 * expander costs a chevron, while erring the other way leaves text with no way to reach it.
 */


function isComplexCellValue(v: unknown): boolean {
  if (isPlainObject(v)) return true
  if (!Array.isArray(v)) return false
  return v.some(isPlainObject) || v.length > INLINE_CHIP_MAX
}

/**
 * What a cell shows in place of a structure it cannot hold.
 *
 * The finding this answers was measured twice, and the second measurement overturned the first
 * remedy. Nesting — not length — decides a cell's width: the same value renders comfortably at
 * top level and collapses inside a cell, because a nested object's label column alone wants
 * 8rem and whatever is left goes to the value. The obvious fix was to drop the minimum width
 * that `StatusValue` applies to nested objects. It is the wrong fix, and the code there says
 * so in its own comment: without the minimum, the value column falls to roughly one character
 * per line and the row gets TALLER. Removing a symptom's brace is not the same as removing the
 * cause.
 *
 * So the structure does not render in the cell at all. It moves to the row detail, which
 * already existed and already renders the record exactly as delivered, and the cell keeps a
 * summary saying what moved and how much of it there is.
 *
 * The count is taken from the DATA, never from a declaration — a summary that announced
 * "4 fields" for an object that has three would be the false-absence shape this surface
 * refuses everywhere else, just wearing a smaller number.
 */
/**
 * A column header, with a flattened object's prefix dimmed rather than removed.
 *
 * `flattenUniformObjects` spreads a uniform nested object into `health.reachable`,
 * `health.httpStatus`, and so on. The prefix is load-bearing — it is what keeps two objects'
 * `status` fields apart — but repeating it across seven adjacent headers spends the width
 * seven times on the one part of the name every one of them shares, and it is the part that
 * distinguishes nothing.
 *
 * So it stays in the DOM, in the accessible name, and in any test matching on the column key;
 * it simply stops competing for the reader's attention. Deleting it would be the tempting
 * version and it fails the moment a project sends two objects with a field in common.
 */
function ColumnLabel({ name }: { name: string }) {
  const dot = name.indexOf('.')
  if (dot < 0) return <>{name}</>
  return (
    <>
      <span className="text-fg-ghost">{name.slice(0, dot + 1)}</span>
      {name.slice(dot + 1)}
    </>
  )
}

function Displaced({ value }: { value: unknown }) {
  const label = Array.isArray(value)
    ? `${value.length} ${value.length === 1 ? 'row' : 'rows'}`
    : `${Object.keys(value as Record<string, unknown>).filter(k => !META_KEYS.has(k)).length} fields`
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap text-fg-faint">
      <span aria-hidden>▤</span>
      <span className="underline decoration-dotted underline-offset-2">{label}</span>
    </span>
  )
}

/**
 * What a sideways-scrolling table is not showing, counted from the DOM.
 *
 * A wide table already scrolled — the box has `overflow-x-auto` — but nothing SAID so, and the
 * columns simply ended at the panel edge mid-word. Measured on the landing tab: two tables lost
 * their last column that way, and the screen looked complete. This surface's rule is that
 * anything hidden is marked where the reader is standing, so the count goes on the row-count
 * line, beside "N rows", not somewhere down at the scrollbar.
 *
 * Counted from the header cells' geometry rather than from a column list, because the question
 * is which columns are OFF THE VIEWPORT — a fact about layout that only the browser knows. It
 * re-counts on scroll and on resize; a figure taken once would be wrong the moment either moved.
 */
function useSideScroll(ref: React.RefObject<HTMLDivElement | null>) {
  const [state, setState] = useState({ hiddenCols: 0, atEnd: true })
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => {
      const max = el.scrollWidth - el.clientWidth
      if (max <= 1) { setState({ hiddenCols: 0, atEnd: true }); return }
      const right = el.scrollLeft + el.clientWidth
      const ths = Array.from(el.querySelectorAll<HTMLElement>('thead th'))
      const hiddenCols = ths.filter(th => th.offsetLeft + th.offsetWidth > right + 1).length
      setState({ hiddenCols, atEnd: el.scrollLeft >= max - 1 })
    }
    update()
    el.addEventListener('scroll', update, { passive: true })
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => { el.removeEventListener('scroll', update); ro.disconnect() }
  }, [ref])
  return state
}

/**
 * The one control that acts on a selection — rendered only where the project declared it.
 *
 * The confirmation says what the event IS, not only how many rows it covers. A queue hands the
 * list over and the project consumes it one at a time, so a reader told "act on 13 rows" would
 * expect thirteen outcomes, get one, and wait. That distinction came from the producer measuring
 * their own engine, and it is carried by `kind` rather than guessed here.
 */
function BatchButton({ action, ids }: { action: BatchAction; ids: string[] }) {
  const run = useContext(ActionCtx)
  const chooseKeys = Object.keys(action.choose ?? {})
  const [picked, setPicked] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!run) return null
  const missing = chooseKeys.filter(k => !picked[k])
  const blocked = busy || ids.length === 0 || missing.length > 0

  const go = async () => {
    const queue = (action.kind ?? 'queue') === 'queue'
    const what = Object.entries(picked).map(([k, v]) => `${k}=${v}`).join(', ')
    if (!window.confirm(
      `${action.label ?? action.command} — ${ids.length} row${ids.length === 1 ? '' : 's'}` +
      `${what ? ` · ${what}` : ''}\n\n` +
      (queue
        ? `These are handed to the project as a LIST. It processes them ONE AT A TIME — you `
          + `will not get ${ids.length} results back now.\n\n`
        : `This applies as ONE operation to all ${ids.length}.\n\n`) +
      `Continue?`,
    )) return

    setBusy(true); setError(null)
    try {
      const res = await run(action.command, { ...(action.args ?? {}), ...picked, ids })
      if (res.ok) setDone(`${ids.length} handed over`)
      else setError(res.error || 'the project refused it')
    } catch (e) {
      setError(String((e as Error)?.message ?? e))
    } finally {
      setBusy(false)
    }
  }

  if (done) return <span className="text-emerald-400" data-testid="batch-done">{done}</span>

  return (
    <span className="inline-flex items-center gap-1">
      {chooseKeys.map(k => (
        <select
          key={k}
          value={picked[k] ?? ''}
          onChange={e => setPicked(p => ({ ...p, [k]: e.target.value }))}
          aria-label={k}
          className="bg-surface-raised border border-surface-edge rounded text-xs px-1 py-0.5 text-fg-strong"
        >
          <option value="">{k}…</option>
          {(action.choose?.[k] ?? []).map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      ))}
      <button
        onClick={go}
        disabled={blocked}
        data-testid="batch-action"
        data-action={action.command}
        // A disabled control must say WHY, here as much as anywhere: an unstated reason reads
        // as a broken button, which is the same thing as no explanation at all.
        title={
          ids.length === 0
            ? 'no selected row carries the identifier this action needs'
            : missing.length
              ? `choose ${missing.join(', ')} first`
              : undefined
        }
        className="px-2 py-0.5 text-xs rounded bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
      >
        {busy ? '…' : `${action.label ?? action.command} (${ids.length})`}
      </button>
      {error && <span className="text-red-400" title={error}>failed</span>}
    </span>
  )
}

export function StatusTable(
  { rows: rawRows, renderValue, batch = null }: {
    rows: Row[]
    /**
     * `owner` and `key` are passed so a cell can resolve a DECLARED field role — a paired
     * role looks its partner up among the row's own keys, and nowhere else. The renderer
     * still learns no field name; it hands both to the resolver and uses what comes back.
     */
    renderValue: (
      value: unknown, depth: number,
      owner?: Record<string, unknown>, key?: string,
    ) => ReactNode
    /** What the project declared may be done to a SELECTION of these rows, if anything. */
    batch?: BatchAction | null
  },
) {
  const view = useDeprecation()
  const rows = useMemo(() => flattenUniformObjects(rawRows), [rawRows])
  const emphasised = useMemo(() => rawRows.map(emphasisOf), [rawRows])

  const dataCols = columnsOf(rows).filter(c => !META_KEYS.has(c))
  const { visible: cols, hiddenCount } = partitionKeys(dataCols, view)
  const hasActions = rows.some(
    r => Array.isArray(r[ACTIONS_KEY]) && (r[ACTIONS_KEY] as unknown[]).length > 0,
  )

  // Every one of these is memory only. Persisting a facet selection would write the
  // project's own vocabulary into browser storage or the address bar — see the file header.
  const [search, setSearch] = useState('')
  const [picked, setPicked] = useState<Record<string, string[]>>({})
  const [sort, setSort] = useState<SortState | null>(null)
  const [open, setOpen] = useState<ReadonlySet<number>>(new Set<number>())
  const [showAll, setShowAll] = useState(false)
  // Keys, not indices — see identityColumn. Memory only, like every other control here: a
  // selection written to the address bar would carry the producer's own identifiers off the page.
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set<string>())

  const controls = rows.length >= CONTROL_MIN_ROWS

  /**
   * Does any cell hold a structure the cell cannot show?
   *
   * This is what turns the row expander on, INDEPENDENTLY of the row count. The count alone
   * was the rule, and it produced the worst screen on the surface: a four-row table, well under
   * the threshold, whose cells carried nested objects and nested tables. No controls meant no
   * expander, so the structures rendered in place and one row grew to 383px against a 117px
   * median — and there was nowhere for them to go even if the cell had refused them.
   *
   * A small table still gets no search box and no facets; those are about VOLUME, and four rows
   * genuinely do not need them. Displacement is about SHAPE, so it is decided separately.
   */
  const displaces = useMemo(
    () => rows.some(r => cols.some(c => {
      const v = r[c]
      if (isComplexCellValue(v)) return true
      // Long prose is withheld just as surely as a structure is — measured across the status
      // tabs, cells were hiding 93%, 78%, 77% and 70% of their text behind an ellipsis whose
      // only escape was a `title` tooltip. A tooltip is not an answer: it is unreachable on
      // touch, uncopyable, and this surface's own rule says what a compaction withheld must be
      // reachable where the reader is standing. The threshold is the clip width the cell uses.
      return typeof v === 'string' && v.length > CELL_CLIP_CHARS
    })),
    [rows, cols],
  )
  const expandable = controls || displaces

  /**
   * A table with one column is a LIST, and a list of short names should flow into columns.
   *
   * Left as a table it renders a ~390px strip with 1500px of nothing beside it — which the
   * sizing fix made honest but did not make useful. Flowing the rows fills the width with
   * content instead of with an explanation of why there is none.
   *
   * Only when there are enough rows to be worth it: three or four names in three columns is a
   * layout puzzle, not a list. Sorting, filtering and the row cap all still happen first, so
   * the flow is applied to whatever survived them and nothing about what is withheld changes.
   */
  const flowsAsList = cols.length === 1 && rows.length >= 12
  const tints = useMemo(() => categoryTints(rows, cols), [rows, cols])
  /**
   * The width this table has to work with, measured rather than assumed.
   *
   * Needed because the decision below is "how many copies of this table fit", and that depends on
   * the panel it landed in — which differs between a full-width block and a half-width one, and
   * changes when the window does. A constant here would be right on one screen and wrong on the
   * next; the first render sees 0 and settles on one chunk, then re-renders once with the truth.
   */
  const outerBox = useRef<HTMLDivElement>(null)
  const [availPx, setAvailPx] = useState(0)
  useEffect(() => {
    const el = outerBox.current
    if (!el) return
    const update = () => setAvailPx(el.clientWidth)
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const scrollBox = useRef<HTMLDivElement>(null)
  const { hiddenCols, atEnd } = useSideScroll(scrollBox)
  const facets = useMemo(
    () => (controls ? facetColumns(rows, cols) : new Map<string, Map<string, number>>()),
    [controls, rows, cols],
  )

  const activeFacets = Object.entries(picked).filter(([, vs]) => vs.length > 0)
  const filtering = search.trim() !== '' || activeFacets.length > 0

  const indices = useMemo(() => {
    let idx = rows.map((_, i) => i)
    if (controls) {
      const term = search.trim().toLowerCase()
      if (term) {
        idx = idx.filter(i => cols.some(c => searchText(rows[i][c]).toLowerCase().includes(term)))
      }
      for (const [col, values] of activeFacets) {
        idx = idx.filter(i => values.includes(cellText(rows[i][col])))
      }
      if (sort) {
        const dir = sort.dir === 'asc' ? 1 : -1
        idx = [...idx].sort((a, b) => {
          const av = rows[a][sort.col]
          const bv = rows[b][sort.col]
          // A missing value keeps its place at the end whichever way the column is sorted,
          // so the direction is applied to the comparison and never to the absence.
          const am = isMissing(av)
          const bm = isMissing(bv)
          if (am !== bm) return am ? 1 : -1
          if (am && bm) return 0
          return compareValues(av, bv) * dir
        })
      }
    }
    return idx
  }, [controls, rows, cols, search, picked, sort])

  const clearAll = () => { setSearch(''); setPicked({}) }

  const cycleSort = (col: string) => {
    setSort(s => {
      if (!s || s.col !== col) return { col, dir: 'asc' }
      if (s.dir === 'asc') return { col, dir: 'desc' }
      return null // back to the order the project delivered
    })
  }

  const toggleFacet = (col: string, value: string) => {
    setPicked(p => {
      const current = p[col] ?? []
      const next = current.includes(value)
        ? current.filter(v => v !== value)
        : [...current, value]
      const out = { ...p }
      if (next.length === 0) delete out[col]
      else out[col] = next
      return out
    })
  }

  const toggleRow = (i: number) => {
    setOpen(prev => {
      const next = new Set(prev)
      if (next.has(i)) next.delete(i); else next.add(i)
      return next
    })
  }

  const hidden = rows.length - indices.length
  // The rows actually rendered — the filtered/sorted set, then capped unless expanded.
  const visibleIndices = showAll ? indices : indices.slice(0, ROW_CAP)

  /**
   * Split the rows into side-by-side groups when the table is much narrower than its panel.
   *
   * Every bound has a failure it prevents. Below `MIN_ROWS_TO_FLOW` a split reads as arbitrary —
   * two groups of four is not a newspaper column, it is a table someone broke. Past three groups
   * the eye stops knowing which one continues from which. And a group must keep enough rows to
   * look like a table, so a 13-row table splits into two and not into three of four-ish.
   *
   * `flowsAsList` is left alone: a single-column table already flows, by a mechanism that packs
   * tighter than this one because it needs no repeated header.
   */
  const chunks = useMemo(() => {
    const one = [visibleIndices]
    if (flowsAsList || visibleIndices.length < MIN_ROWS_TO_FLOW || availPx <= 0) return one
    const naturalPx = tablePxWidth(rows)
    if (naturalPx <= 0) return one
    const fits = Math.floor((availPx + FLOW_GAP_PX) / (naturalPx + FLOW_GAP_PX))
    const n = Math.min(MAX_FLOW_GROUPS, fits, Math.floor(visibleIndices.length / MIN_ROWS_PER_GROUP))
    if (n < 2) return one
    const per = Math.ceil(visibleIndices.length / n)
    return Array.from({ length: n }, (_, k) => visibleIndices.slice(k * per, (k + 1) * per))
      .filter(g => g.length > 0)
  }, [flowsAsList, visibleIndices, availPx, rows])
  const capped = indices.length - visibleIndices.length

  /**
   * How wide a clipped cell may run — see `cellClipPxFor`, which owns the rule and is tested.
   *
   * The expander is unaffected on purpose: `displaces` still asks at `CELL_CLIP_CHARS`, so a value
   * that now happens to fit keeps its chevron. Erring toward offering the row costs a chevron;
   * erring the other way strands text with no way to reach it.
   */
  const cellClipPx = useMemo(
    () => cellClipPxFor(rows, availPx, chunks.length),
    [rows, availPx, chunks.length],
  )
  const cellLineCount = cellLines(visibleIndices.length, chunks.length)

  // ── Selection ───────────────────────────────────────────────────────────────────────────
  const idCol = useMemo(() => identityColumn(rows, cols), [rows, cols])
  const keyOf = useCallback(
    (i: number) => (idCol ? String(rows[i][idCol]) : `#${i}`),
    [idCol, rows],
  )
  const selectable = rows.length > 0 && controls

  // A key that matches no row in the CURRENT answer is not selected. A refreshed answer that
  // dropped a row would otherwise leave a count claiming more rows than an action could reach —
  // an overstatement in the direction that looks like nothing is wrong.
  const presentKeys = useMemo(
    () => new Set(rows.map((_, i) => keyOf(i))),
    [rows, keyOf],
  )
  const selectedCount = useMemo(
    () => [...selected].filter(k => presentKeys.has(k)).length,
    [selected, presentKeys],
  )
  const visibleKeys = useMemo(() => new Set(visibleIndices.map(keyOf)), [visibleIndices, keyOf])
  // Selected rows the reader cannot currently see — a filter, a search or the row cap. Stating
  // this is the whole point: a selection of 13 with 9 hidden reads as 4 unless it is said out
  // loud, and every later action would act on 13.
  const selectedHidden = useMemo(
    () => [...selected].filter(k => presentKeys.has(k) && !visibleKeys.has(k)).length,
    [selected, presentKeys, visibleKeys],
  )
  const allVisibleSelected = visibleIndices.length > 0
    && visibleIndices.every(i => selected.has(keyOf(i)))

  // What actually gets handed over: the identifier the PROJECT named, read from the selected
  // rows. Not the framework's own key — those two are the same value on today's producer and
  // there is no reason they must stay so, and handing over the wrong one is invisible from
  // both sides. Rows whose named field is absent are dropped here and counted below, because
  // sending an `undefined` identifier is the silent failure this whole layer refuses.
  const selectedIds = useMemo(() => {
    if (!batch) return []
    const field = batch.idField ?? idCol
    if (!field) return []
    const out: string[] = []
    for (let i = 0; i < rows.length; i++) {
      if (!selected.has(keyOf(i))) continue
      const v = rows[i][field]
      if (isMissing(v) || !isScalar(v)) continue
      out.push(String(v))
    }
    return out
  }, [batch, idCol, rows, selected, keyOf])
  const unidentified = selectedCount - selectedIds.length

  const toggleSelected = (i: number) => {
    const k = keyOf(i)
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(k)) next.delete(k); else next.add(k)
      return next
    })
  }

  // Acts on the rows SHOWING, never on the whole table. The control names that limit rather
  // than relying on the reader to guess which of the two defensible meanings it has.
  const toggleAllVisible = () => {
    setSelected(prev => {
      const next = new Set(prev)
      for (const i of visibleIndices) {
        if (allVisibleSelected) next.delete(keyOf(i)); else next.add(keyOf(i))
      }
      return next
    })
  }

  const renderBox = (slice: number[], chunk: number) => (
        <div className="relative">
        {/* The fade is the affordance; the count above is the fact. A gradient alone would say
            "there is more" without saying how much, and this surface does not report a hidden
            quantity it has not counted. */}
        {!atEnd && (
          <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-10 rounded-r bg-gradient-to-l from-surface-page to-transparent" />
        )}
        <div ref={chunk === 0 ? scrollBox : null} className="overflow-x-auto rounded border border-surface-line">
          <table
            // `w-auto`, not `w-full`. A table stretched to its container spreads its columns to
            // fill it, and the gaps land between the values a reader is comparing: measured on
            // the config tab, a 3-column table of short identifiers spread `name` to 590px for
            // values around 110px, putting 400px of nothing between a name and its state.
            //
            // Scanning a row is the whole job of a table, and horizontal distance is what makes
            // it hard. So the table takes the width its content needs; when that exceeds the
            // container it overflows as before, and when it is less the panel simply has room
            // to spare — which is honest, and much easier to read than manufactured gaps.
            // NOT `min-w-full`. The first attempt paired `w-auto` with it and the change did
            // nothing: a minimum of 100% forces the container width back on, so `w-auto` never
            // applied. A hedge added for safety cancelled the fix it was hedging.
            className={`text-sm tabular-nums ${flowsAsList ? 'w-full block [&_thead]:block [&_thead_tr]:flex [&_tbody]:grid [&_tbody]:gap-x-6 [&_tbody]:[grid-template-columns:repeat(auto-fill,minmax(22rem,1fr))] [&_tbody_tr]:flex [&_tbody_tr]:items-center' : 'w-auto'}`}
          >
            <thead>
              <tr className="bg-surface-panel text-fg-faint border-b border-surface-line">
                {selectable && (
                  <th className="w-6 px-2 py-2">
                    <input
                      type="checkbox"
                      checked={allVisibleSelected}
                      onChange={toggleAllVisible}
                      aria-label={`select the ${visibleIndices.length} rows showing`}
                      title={`select the ${visibleIndices.length} rows showing — not the whole table`}
                      className="accent-emerald-600 align-middle"
                    />
                  </th>
                )}
                {/* `expandable`, not `controls`. When the body grew an expander column driven by
                    content while this header still keyed on row count, every header sat one column
                    to the left of the values it named — on exactly the tables that displace, which
                    are the ones whose columns most need naming. */}
                {expandable && <th className="w-6 px-2 py-2" />}
                {cols.map(c => (
                  <th
                    key={c}
                    onClick={controls ? () => cycleSort(c) : undefined}
                    aria-sort={sort?.col === c ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}
                    // The identifying column holds its position while the rest scrolls under it.
                    // The tab this exists for carries twelve columns and hides 2886px past the
                    // right edge; scrolling to reach them used to take the row's identity with it,
                    // so the reader arrived at a value with nothing to say which row it belonged
                    // to. Which column identifies a row is decided from the VALUES — the first one
                    // whose entries are all present and all distinct — never from its name.
                    className={`text-left font-medium px-3 py-2 whitespace-nowrap ${
                      controls ? 'cursor-pointer select-none hover:text-fg-strong' : ''
                    } ${c === idCol ? 'sticky left-0 z-[2] bg-surface-panel' : ''}`}
                  >
                    {view.names.has(c) ? <DeprecatedLabel name={c} /> : <ColumnLabel name={c} />}
                    {sort?.col === c && (
                      <span className="ml-1 text-sky-400">{sort.dir === 'asc' ? '↑' : '↓'}</span>
                    )}
                  </th>
                ))}
                {hasActions && <th className="text-left font-medium px-3 py-2" />}
              </tr>
            </thead>
            <tbody>
              {slice.map(i => {
                const row = rows[i]
                const isOpen = open.has(i)
                return [
                  <tr
                    key={`r${i}`}
                    // The WHOLE row opens it. A 12-pixel caret is a target you have to aim at, and
                    // the thing a reader is already pointing at is the row — so the caret stays as
                    // the affordance that says "this opens" and stops being the only way in.
                    //
                    // Guarded three ways, because a row-wide handler is easy to get wrong. A click
                    // that lands on a control (the checkbox, a row action, a link) belongs to that
                    // control and must not also toggle. A click that ends a text SELECTION is
                    // someone copying a value, not opening a record — toggling there would collapse
                    // what they were reading. And the caret keeps its own handler, so keyboard
                    // users still have one focusable target per row rather than a whole row that
                    // traps tab order.
                    onClick={expandable ? (e => {
                      const t = e.target as HTMLElement
                      if (t.closest('input,button,a,label,select,textarea,summary,details')) return
                      if ((window.getSelection()?.toString() ?? '').length > 0) return
                      toggleRow(i)
                    }) : undefined}
                    className={`border-b border-surface-line/50 align-top ${
                      controls ? 'hover:bg-surface-panel/50' : ''
                    }${expandable ? ' cursor-pointer' : ''}`}
                  >
                    {selectable && (
                      <td className="px-2 py-2">
                        <input
                          type="checkbox"
                          checked={selected.has(keyOf(i))}
                          onChange={() => toggleSelected(i)}
                          aria-label="select this row"
                          className="accent-emerald-600 align-middle"
                        />
                      </td>
                    )}
                    {expandable && (
                      <td
                        role="button"
                        tabIndex={0}
                        aria-expanded={isOpen}
                        aria-label={isOpen ? 'hide the whole record' : 'show the whole record'}
                        // No onClick here: the row's handler already covers a click that lands on
                        // the caret, and a second one would toggle twice and appear to do nothing.
                        onKeyDown={e => {
                          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleRow(i) }
                        }}
                        className="px-2 py-2 text-fg-ghost hover:text-fg-strong cursor-pointer select-none"
                      >
                        {isOpen ? '▾' : '▸'}
                      </td>
                    )}
                    {cols.map(c => {
                      // A structure moves to the row detail; everything else renders in place.
                      // The emphasis wrapper stays OUTSIDE that choice on purpose: a project that
                      // declared this field important said so about the field, not about the shape
                      // its value happened to take, so a displaced value keeps its emphasis and a
                      // reader can still see which row to open.
                      const raw = row[c]
                      // The tint is applied to the CELL, not inside the value renderer: it is a
                      // property of this value's place in this column, not of the value itself, and
                      // the same string in another column may belong to a different set.
                      const tint = isMissing(raw) ? undefined : tints.get(c)?.get(cellText(raw))
                      const inner = isComplexCellValue(raw) ? <Displaced value={raw} /> : renderValue(raw, 2, row, c)
                      const content = !(c in row)
                        ? <Unknown />
                        : emphasisMatches(c, emphasised[i] ?? new Set())
                          ? <Emphasis>{inner}</Emphasis>
                          : inner
                      return (
                        <td
                          key={c}
                          // Named so a test can reach a cell by its COLUMN rather than by its
                          // position. Three tests broke the day a checkbox column was added,
                          // all of them `td:nth-child(2)` — a positional selector measures the
                          // layout, not the data, and it fails on the next column either way.
                          data-col={c}
                          className={`${expandable ? 'px-3 py-2' : 'px-3 py-2 max-w-[26rem]'} ${
                            c === idCol ? 'sticky left-0 z-[1] bg-surface-page' : ''
                          } ${tint ?? ''}`}
                        >
                          {expandable
                            ? <Cell text={cellText(row[c])} clipPx={cellClipPx} lines={cellLineCount}>{content}</Cell>
                            : content}
                        </td>
                      )
                    })}
                    {hasActions && (
                      <td className="px-3 py-2 whitespace-nowrap">
                        <RowActions value={row[ACTIONS_KEY]} />
                      </td>
                    )}
                  </tr>,
                  isOpen && (
                    // The complete record, untruncated — the other half of clipping a cell.
                    // Rendered from the row AS DELIVERED, so nothing this table did to it
                    // (flattening, clipping, column order) reaches the detail.
                    <tr
                      key={`d${i}`}
                      // In flow mode the tbody is a grid and every `<tr>` is a grid ITEM, so this
                      // detail — a sibling row, not a child — was auto-placed into the NEXT cell.
                      // Expanding the second name in a row opened a panel beside the third one.
                      // Spanning every column puts it back in reading order after its own row and
                      // makes a wrong cell impossible rather than unlikely. The record it renders
                      // names itself, so it stays identifiable even a line below its owner.
                      className={`bg-surface-page/60 ${flowsAsList ? 'col-span-full' : ''}`}
                    >
                      <td
                        colSpan={cols.length + (expandable ? 1 : 0) + (hasActions ? 1 : 0) + (selectable ? 1 : 0)}
                        className="px-3 py-2"
                      >
                        {renderValue(rawRows[i] ?? row, 1)}
                      </td>
                    </tr>
                  ),
                ]
              })}
            </tbody>
          </table>
        </div>
        </div>
  )

  return (
    <div className="space-y-1" ref={outerBox}>
      {/* The count line. Unfiltered it says exactly what it always said — a count of ROWS,
          never of "items", because the key above it names someone else's domain. Filtered,
          it is the one place that has to state what is NOT on screen. */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs">
        <span className="text-fg-faint" title="rows as delivered — set-core counts them, it does not interpret them">
          {filtering
            ? `${indices.length} of ${rows.length} rows shown`
            : `${rows.length} row${rows.length === 1 ? '' : 's'}`}
        </span>
        {filtering && hidden > 0 && (
          <span className="text-amber-500/90" title="rows the answer contained and this view is not showing">
            {hidden} hidden by filters
          </span>
        )}
        {hiddenCols > 0 && (
          <span
            className="text-fg-faint"
            title="this table is wider than the panel — scroll it sideways to reach these columns"
          >
            {hiddenCols} column{hiddenCols === 1 ? '' : 's'} off to the right &rarr;
          </span>
        )}
        {filtering && (
          <button
            onClick={clearAll}
            className="text-fg-muted hover:text-fg-strong underline decoration-dotted"
          >
            clear
          </button>
        )}
        {sort && (
          <span className="text-sky-400/80" title="not the order the project delivered">
            sorted by {sort.col} {sort.dir === 'asc' ? '↑' : '↓'} — not the project's order
          </span>
        )}
      </div>

      {/* The selection line. It exists only once something is selected, and its whole job is to
          keep the reader's set from disagreeing with what the reader can see. */}
      {selectable && selectedCount > 0 && (
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs">
          <span className="text-emerald-400/90 tabular-nums" data-testid="selection-count">
            {selectedCount} selected
          </span>
          {selectedHidden > 0 && (
            <span
              className="text-amber-500/90 tabular-nums"
              data-testid="selection-hidden"
              title="selected rows this view is not showing — an action would still act on them"
            >
              {selectedHidden} of them not shown here
            </span>
          )}
          <button
            onClick={() => setSelected(new Set<string>())}
            className="text-fg-muted hover:text-fg-strong underline decoration-dotted"
          >
            clear selection
          </button>
          {/* Nothing can be done with a selection until the project says what. Saying that is
              not decoration: a selection that can be made and then does nothing, silently, is
              indistinguishable from a control that is broken. */}
          {/* Selected rows that cannot be handed over, because the field the project named is
              absent on them. Stated, never dropped: a button reading "(11)" over a selection of
              13 is a discrepancy the reader would have to notice and explain, and the silent
              version of it hands over a shorter list than anyone chose. */}
          {batch && unidentified > 0 && (
            <span className="text-amber-500/90 tabular-nums" data-testid="selection-unidentified">
              {unidentified} cannot be handed over — no {batch.idField ?? idCol} on them
            </span>
          )}
          {batch
            ? <BatchButton action={batch} ids={selectedIds} />
            : (
              <span className="text-fg-faint" data-testid="no-batch-action">
                this project offers no action on a selection
              </span>
            )}
          {!idCol && (
            <span
              className="text-amber-500/90"
              data-testid="selection-positional"
              title="no column identifies a row uniquely, so rows are remembered by position"
            >
              sorting will invalidate this selection — no column identifies these rows
            </span>
          )}
        </div>
      )}

      {controls && (
        <div className="flex flex-wrap items-center gap-2 pb-1">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="search rows…"
            aria-label="search rows"
            className="bg-surface-panel border border-surface-line rounded px-2 py-1 text-xs text-fg-strong placeholder:text-fg-ghost w-56 focus:outline-none focus:border-surface-edge-soft"
          />
          {[...facets.entries()].map(([col, counts]) => {
            const chosen = picked[col] ?? []
            return (
              <details key={col} className="relative">
                <summary
                  className={`cursor-pointer list-none px-2 py-1 rounded border text-xs ${
                    chosen.length
                      ? 'border-sky-700 bg-sky-950/40 text-sky-300'
                      : 'border-surface-line bg-surface-panel text-fg-muted hover:text-fg-strong'
                  }`}
                >
                  {col}{chosen.length > 0 && ` (${chosen.length})`} {'▾'}
                </summary>
                <div className="absolute z-20 mt-1 p-2 rounded border border-surface-edge bg-surface-panel shadow-xl max-h-72 overflow-auto min-w-[12rem]">
                  {[...counts.entries()].map(([value, count]) => (
                    <label
                      key={value}
                      className="flex items-center gap-2 px-1 py-0.5 text-xs text-fg-normal hover:bg-surface-raised rounded cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={chosen.includes(value)}
                        onChange={() => toggleFacet(col, value)}
                        className="accent-sky-600"
                      />
                      <span className="truncate max-w-[16rem]" title={value}>{value}</span>
                      <span className="ml-auto text-fg-ghost tabular-nums">{count}</span>
                    </label>
                  ))}
                </div>
              </details>
            )
          })}
          {activeFacets.map(([col, values]) =>
            values.map(v => (
              <button
                key={`${col}:${v}`}
                onClick={() => toggleFacet(col, v)}
                className="px-1.5 py-0.5 rounded bg-sky-950/60 border border-sky-800 text-xs text-sky-300 hover:bg-sky-900/60"
                title="click to remove this filter"
              >
                {col}={v} {'×'}
              </button>
            )),
          )}
        </div>
      )}

      {/* overflow-x only: a wide table scrolls sideways within its own box, but the PAGE is
          the single vertical scroller — no inner max-height, so no second vertical scrollbar
          nested inside the page's. Matches how the orchestration change table renders. */}
      {/*
        One box per chunk. A table narrower than its panel used to leave the rest of the row
        empty — measured on the debt tab, a 3-column table drew at ~700 px inside an ~1800 px
        panel, so more than half the screen carried nothing. Stretching the columns to fill it
        was tried and rejected: the gaps land between the values a reader is comparing.

        So the ROWS flow into side-by-side groups instead, each a real table with its own
        header. The width gets used and the page gets shorter — 16 rows at 700 px becomes 8 rows
        at 1400 px — and every column stays as narrow as its content, which was the point of
        `w-auto` in the first place.
      */}
      {chunks.length === 1
        ? renderBox(chunks[0], 0)
        : (
          <div className="grid gap-x-6 items-start" style={{ gridTemplateColumns: `repeat(${chunks.length}, minmax(0, 1fr))` }}>
            {chunks.map((slice, n) => <div key={n}>{renderBox(slice, n)}</div>)}
          </div>
        )}

      {/* The cap, stated and reversible — never a silent truncation. Once expanded, the same
          control folds it back so the delivered slice is recoverable without a reload. */}
      {(capped > 0 || showAll) && indices.length > ROW_CAP && (
        <button
          onClick={() => setShowAll(v => !v)}
          className="text-xs text-fg-muted hover:text-fg-strong underline decoration-dotted"
        >
          {showAll
            ? `show fewer — first ${ROW_CAP} of ${indices.length}`
            : `show all ${indices.length} rows — ${capped} more`}
        </button>
      )}

      {/* A filter that matches nothing must say so. An empty table reads as an empty
          answer, which is the false-absence shape with the reader's own click behind it. */}
      {filtering && indices.length === 0 && (
        <div className="text-xs text-amber-500/90">
          No row matches these filters — {rows.length} row{rows.length === 1 ? '' : 's'} are
          hidden, not absent.
        </div>
      )}

      <HiddenNote count={hiddenCount} />
    </div>
  )
}

export default StatusTable
