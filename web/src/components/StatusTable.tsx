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

import { useMemo, useState, type ReactNode } from 'react'
import {
  ACTIONS_KEY,
  DeprecatedLabel,
  Emphasis,
  HiddenNote,
  META_KEYS,
  RowActions,
  Unknown,
  columnsOf,
  emphasisMatches,
  emphasisOf,
  flattenUniformObjects,
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

interface SortState { col: string; dir: 'asc' | 'desc' }

/** The cell as it appears in a dense row: one line, clipped, with the whole value in reach. */
function Cell({ children, text }: { children: ReactNode; text: string }) {
  return (
    <div className="truncate max-w-[22rem]" title={text || undefined}>
      {children}
    </div>
  )
}

export function StatusTable(
  { rows: rawRows, renderValue }: {
    rows: Row[]
    renderValue: (value: unknown, depth: number) => ReactNode
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

  const controls = rows.length >= CONTROL_MIN_ROWS
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
  const capped = indices.length - visibleIndices.length

  return (
    <div className="space-y-1">
      {/* The count line. Unfiltered it says exactly what it always said — a count of ROWS,
          never of "items", because the key above it names someone else's domain. Filtered,
          it is the one place that has to state what is NOT on screen. */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[11px]">
        <span className="text-neutral-500" title="rows as delivered — set-core counts them, it does not interpret them">
          {filtering
            ? `${indices.length} of ${rows.length} rows shown`
            : `${rows.length} row${rows.length === 1 ? '' : 's'}`}
        </span>
        {filtering && hidden > 0 && (
          <span className="text-amber-500/90" title="rows the answer contained and this view is not showing">
            {hidden} hidden by filters
          </span>
        )}
        {filtering && (
          <button
            onClick={clearAll}
            className="text-neutral-400 hover:text-neutral-200 underline decoration-dotted"
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

      {controls && (
        <div className="flex flex-wrap items-center gap-2 pb-1">
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="search rows…"
            aria-label="search rows"
            className="bg-neutral-900 border border-neutral-800 rounded px-2 py-1 text-xs text-neutral-200 placeholder:text-neutral-600 w-56 focus:outline-none focus:border-neutral-600"
          />
          {[...facets.entries()].map(([col, counts]) => {
            const chosen = picked[col] ?? []
            return (
              <details key={col} className="relative">
                <summary
                  className={`cursor-pointer list-none px-2 py-1 rounded border text-xs ${
                    chosen.length
                      ? 'border-sky-700 bg-sky-950/40 text-sky-300'
                      : 'border-neutral-800 bg-neutral-900 text-neutral-400 hover:text-neutral-200'
                  }`}
                >
                  {col}{chosen.length > 0 && ` (${chosen.length})`} {'▾'}
                </summary>
                <div className="absolute z-20 mt-1 p-2 rounded border border-neutral-700 bg-neutral-900 shadow-xl max-h-72 overflow-auto min-w-[12rem]">
                  {[...counts.entries()].map(([value, count]) => (
                    <label
                      key={value}
                      className="flex items-center gap-2 px-1 py-0.5 text-xs text-neutral-300 hover:bg-neutral-800 rounded cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={chosen.includes(value)}
                        onChange={() => toggleFacet(col, value)}
                        className="accent-sky-600"
                      />
                      <span className="truncate max-w-[16rem]" title={value}>{value}</span>
                      <span className="ml-auto text-neutral-600 tabular-nums">{count}</span>
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
      <div className="overflow-x-auto rounded border border-neutral-800">
        <table className="w-full text-sm tabular-nums">
          <thead>
            <tr className="bg-neutral-900 text-neutral-500 border-b border-neutral-800">
              {controls && <th className="w-6 px-2 py-2" />}
              {cols.map(c => (
                <th
                  key={c}
                  onClick={controls ? () => cycleSort(c) : undefined}
                  aria-sort={sort?.col === c ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}
                  className={`text-left font-medium px-3 py-2 whitespace-nowrap ${
                    controls ? 'cursor-pointer select-none hover:text-neutral-200' : ''
                  }`}
                >
                  {view.names.has(c) ? <DeprecatedLabel name={c} /> : c}
                  {sort?.col === c && (
                    <span className="ml-1 text-sky-400">{sort.dir === 'asc' ? '↑' : '↓'}</span>
                  )}
                </th>
              ))}
              {hasActions && <th className="text-left font-medium px-3 py-2" />}
            </tr>
          </thead>
          <tbody>
            {visibleIndices.map(i => {
              const row = rows[i]
              const isOpen = open.has(i)
              return [
                <tr
                  key={`r${i}`}
                  className={`border-b border-neutral-800/50 align-top ${
                    controls ? 'hover:bg-neutral-900/50' : ''
                  }`}
                >
                  {controls && (
                    <td
                      role="button"
                      tabIndex={0}
                      aria-expanded={isOpen}
                      aria-label={isOpen ? 'hide the whole record' : 'show the whole record'}
                      onClick={() => toggleRow(i)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleRow(i) }
                      }}
                      className="px-2 py-2 text-neutral-600 hover:text-neutral-200 cursor-pointer select-none"
                    >
                      {isOpen ? '▾' : '▸'}
                    </td>
                  )}
                  {cols.map(c => {
                    const content = !(c in row)
                      ? <Unknown />
                      : emphasisMatches(c, emphasised[i] ?? new Set())
                        ? <Emphasis>{renderValue(row[c], 2)}</Emphasis>
                        : renderValue(row[c], 2)
                    return (
                      <td key={c} className={controls ? 'px-3 py-2' : 'px-3 py-2 max-w-[26rem]'}>
                        {controls ? <Cell text={cellText(row[c])}>{content}</Cell> : content}
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
                  <tr key={`d${i}`} className="bg-neutral-950/60">
                    <td colSpan={cols.length + 1 + (hasActions ? 1 : 0)} className="px-3 py-2">
                      {renderValue(rawRows[i] ?? row, 1)}
                    </td>
                  </tr>
                ),
              ]
            })}
          </tbody>
        </table>
      </div>

      {/* The cap, stated and reversible — never a silent truncation. Once expanded, the same
          control folds it back so the delivered slice is recoverable without a reload. */}
      {(capped > 0 || showAll) && indices.length > ROW_CAP && (
        <button
          onClick={() => setShowAll(v => !v)}
          className="text-xs text-neutral-400 hover:text-neutral-200 underline decoration-dotted"
        >
          {showAll
            ? `show fewer — first ${ROW_CAP} of ${indices.length}`
            : `show all ${indices.length} rows — ${capped} more`}
        </button>
      )}

      {/* A filter that matches nothing must say so. An empty table reads as an empty
          answer, which is the false-absence shape with the reader's own click behind it. */}
      {filtering && indices.length === 0 && (
        <div className="text-[11px] text-amber-500/90">
          No row matches these filters — {rows.length} row{rows.length === 1 ? '' : 's'} are
          hidden, not absent.
        </div>
      )}

      <HiddenNote count={hiddenCount} />
    </div>
  )
}

export default StatusTable
