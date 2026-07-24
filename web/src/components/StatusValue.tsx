/**
 * Renders a value a project reported about itself — by SHAPE, never by name.
 *
 * No field name appears anywhere in this file, and that is the point. set-core does not
 * know what a project calls its releases, and the next project to publish a contract
 * will call them something else. A renderer that special-cases a known key becomes
 * coupled to one project's vocabulary and quietly stops working for the second one.
 *
 * Two rules survive from the reader side, because they are about honesty, not layout:
 *
 * **Null is not zero and not success.** A missing value renders amber with a dash, never
 * as `0`, never as a green tick. "We don't know" and "there are none" look identical in
 * JSON and must never look identical on screen — that is the difference between a calm
 * dashboard and a true one.
 *
 * **Nothing is promoted.** A field is shown where it sits, with the name the project gave
 * it. Lifting one number into a headline would mean deciding it is the important one,
 * which is a judgement about someone else's domain.
 *
 * One consequence of showing everything had to be handled, and it was found on a live
 * screen rather than reasoned about: a field the project has replaced but still emits
 * ends up rendered NEXT TO its replacement, contradicting it. The fix keeps the rule —
 * the project declares which of its fields are deprecated, in the envelope, and this
 * renderer hides those by default behind a count. set-core still knows no field name.
 */

import { createContext, useContext, useState, type ReactNode } from 'react'

export function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/**
 * Field names the project declared deprecated, and whether the reader has chosen to see
 * them anyway. Carried by context rather than by prop so that nesting — a table cell
 * inside a row inside a list — does not have to thread it through every level and
 * silently lose it at one.
 */
export interface DeprecationView {
  names: ReadonlySet<string>
  show: boolean
}

const DeprecationCtx = createContext<DeprecationView>({ names: new Set(), show: false })

export const DeprecationProvider = DeprecationCtx.Provider

export function useDeprecation(): DeprecationView {
  return useContext(DeprecationCtx)
}

/**
 * Which of the declared-deprecated names actually appear in this answer.
 *
 * A declaration is a claim about the data, and a claim can be wrong. If the project
 * marks a field it no longer sends, a count taken from the declaration would announce
 * "1 deprecated field hidden" about something that was never there — a false *absence*,
 * which is the mirror image of the false value this whole mechanism exists to prevent.
 * So the count comes from the data, and the declaration only decides what to look for.
 */
export function presentDeprecations(value: unknown, names: ReadonlySet<string>): Set<string> {
  const found = new Set<string>()
  if (names.size === 0) return found

  const walk = (v: unknown) => {
    if (Array.isArray(v)) { v.forEach(walk); return }
    if (!isPlainObject(v)) return
    for (const [k, child] of Object.entries(v)) {
      if (names.has(k)) found.add(k)
      walk(child)
    }
  }
  walk(value)
  return found
}

/**
 * An action the PROJECT attached to a row: a write it says can be performed here.
 *
 * `actions` is a framework-level key, like `deprecated` — one of the few names this
 * renderer may know, because it belongs to the envelope rather than to anyone's domain.
 * Everything inside it is the project's: which command, what it is called, and the
 * arguments already computed. set-core does not derive the arguments from the row,
 * deliberately: a path language (`$.release`) fails SILENTLY when a path is wrong —
 * undefined argument, missing flag, "why doesn't the button work" — and both sides
 * would have to maintain it. The side holding the data does the deriving.
 */
export interface RowAction {
  command: string
  label?: string
  args?: Record<string, unknown>
  /** Argument → the options the reader must pick from. Absent means nothing to choose. */
  choose?: Record<string, string[]>
}

export const ACTIONS_KEY = 'actions'

export type ActionRunner = (
  command: string,
  args: Record<string, unknown>,
) => Promise<{ ok: boolean; error?: string | null }>

const ActionCtx = createContext<ActionRunner | null>(null)
export const ActionProvider = ActionCtx.Provider

function parseActions(value: unknown): RowAction[] {
  if (!Array.isArray(value)) return []
  return value.filter(
    (a): a is RowAction => isPlainObject(a) && typeof a.command === 'string',
  )
}

function ActionButton({ action }: { action: RowAction }) {
  const run = useContext(ActionCtx)
  const chooseKeys = Object.keys(action.choose ?? {})
  const [picked, setPicked] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!run) return null

  const missing = chooseKeys.filter(k => !picked[k])
  const options = (k: string) => action.choose?.[k] ?? []

  const go = async () => {
    // The project's own warning, passed straight to the person clicking: this records
    // a HUMAN ASSERTION, not a measurement. Their side already produced a stray record
    // for a check nobody had performed, so the confirmation is not ceremony.
    const what = Object.entries({ ...(action.args ?? {}), ...picked })
      .map(([k, v]) => `${k}=${v}`).join(', ')
    if (!window.confirm(
      `${action.label ?? action.command} — ${what}\n\n` +
      `This records YOUR statement that this was done. It is not a measurement, and ` +
      `nothing verifies it. Continue?`
    )) return

    setBusy(true); setError(null)
    try {
      const res = await run(action.command, { ...(action.args ?? {}), ...picked })
      if (res.ok) setDone(true)
      else setError(res.error || 'the project refused the write')
    } catch (e) {
      setError(String((e as Error)?.message ?? e))
    } finally {
      setBusy(false)
    }
  }

  if (done) return <span className="text-[11px] text-emerald-400">recorded</span>

  return (
    <div className="flex flex-wrap items-center gap-1">
      {chooseKeys.map(k => (
        <select
          key={k}
          value={picked[k] ?? ''}
          onChange={e => setPicked(p => ({ ...p, [k]: e.target.value }))}
          className="bg-neutral-800 border border-neutral-700 rounded text-[11px] px-1 py-0.5 text-neutral-200"
          aria-label={k}
        >
          <option value="">{k}…</option>
          {options(k).map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      ))}
      <button
        onClick={go}
        disabled={busy || missing.length > 0}
        data-action={action.command}
        title={missing.length ? `choose ${missing.join(', ')} first` : undefined}
        className="px-2 py-0.5 text-[11px] rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
      >
        {busy ? '…' : (action.label ?? action.command)}
      </button>
      {error && <span className="text-[11px] text-red-400" title={error}>failed</span>}
    </div>
  )
}

function RowActions({ value }: { value: unknown }) {
  const actions = parseActions(value)
  if (actions.length === 0) return null
  return (
    <div className="flex flex-col gap-1">
      {actions.map((a, i) => <ActionButton key={`${a.command}-${i}`} action={a} />)}
    </div>
  )
}

/**
 * The project's own marking of which of ITS fields matters most here.
 *
 * A framework-level key, like `actions` and `deprecated`, and that distinction is the whole
 * reason it exists. The consumer asked for one field of theirs to be given extra weight on
 * screen; doing that directly would mean this file recognising a DOMAIN name, which is the
 * one thing it must never do. So the weight travels in the contract instead: the project
 * names the key, and this renderer honours a marking it cannot interpret.
 *
 * The alternative both sides rejected was field ORDER — put the important one first. It is
 * free and it is a silent contract: an innocent reordering breaks it and nothing says so.
 * The same reasoning already put an explicit `primary` in the manifest instead of trusting
 * the order of `commands`.
 */
export const EMPHASIS_KEY = '_emphasis'

/** Framework-level keys — the only names this renderer knows, none of them a domain name. */
const META_KEYS: ReadonlySet<string> = new Set([ACTIONS_KEY, EMPHASIS_KEY])

/**
 * Which marked names are actually present on this object.
 *
 * The presence filter is the load-bearing part, not a nicety. A declaration is a claim
 * about the data and a claim can be wrong; marking a key that is not there would have this
 * renderer draw attention to nothing at all — the false-absence shape, arriving through the
 * one channel we built specifically to carry intent. So the marking says what to LOOK for,
 * and the data decides what is drawn.
 *
 * An emphasised key whose value is empty is still emphasised: the existing rendering says
 * "none (0)" plainly, and a marking silently dropped here would be this side deviating from
 * a declaration without telling anyone. Visibly odd beats silently different.
 */
export function emphasisOf(obj: Record<string, unknown>): Set<string> {
  const declared = obj[EMPHASIS_KEY]
  if (!Array.isArray(declared)) return new Set()
  return new Set(
    declared.filter((n): n is string => typeof n === 'string' && n in obj && !META_KEYS.has(n)),
  )
}

/**
 * True when a column carries emphasis — including one this renderer itself created.
 *
 * `flattenUniformObjects` turns `health` into `health.up` / `health.ms`, so a marked key
 * can lose its own name to a transformation on THIS side. Carrying the marking across the
 * dot is not name recognition; it is refusing to drop a declaration because of something
 * we did to it.
 */
function emphasisMatches(col: string, emphasised: ReadonlySet<string>): boolean {
  if (emphasised.has(col)) return true
  const dot = col.indexOf('.')
  return dot > 0 && emphasised.has(col.slice(0, dot))
}

/** The project's marking, drawn as weight — deliberately not in the colour that means broken. */
function Emphasis({ children }: { children: ReactNode }) {
  return (
    <span
      data-emphasis="true"
      className="inline-block border-l-2 border-sky-500/70 pl-1.5 font-medium text-neutral-50"
      title="the project marked this as the field to act on"
    >
      {children}
    </span>
  )
}

/** Keys to render, and how many were withheld — so a hidden field is never silent. */
function partitionKeys(keys: string[], view: DeprecationView) {
  if (view.names.size === 0) return { visible: keys, hiddenCount: 0 }
  const deprecated = keys.filter(k => view.names.has(k))
  if (view.show) return { visible: keys, hiddenCount: 0 }
  return {
    visible: keys.filter(k => !view.names.has(k)),
    hiddenCount: deprecated.length,
  }
}

function HiddenNote({ count }: { count: number }) {
  if (count === 0) return null
  return (
    <div className="text-[11px] text-neutral-600 italic">
      {count} deprecated field{count === 1 ? '' : 's'} hidden
    </div>
  )
}

/** A deprecated field, when the reader asked to see it: visibly not to be relied on. */
function DeprecatedLabel({ name }: { name: string }) {
  return (
    <span className="line-through decoration-neutral-600" title="the project no longer stands behind this field">
      {name}
    </span>
  )
}

/**
 * No value — never a zero, never a tick.
 *
 * The wording is deliberately silent about WHY. An earlier version said "not provided by
 * the project", which is set-core asserting a reason it cannot know: a null may mean
 * "we could not find out" or "this does not apply here", and the consumer's contract
 * uses it for both. Explaining someone else's absence is the same overreach as inventing
 * their value. The colour still says "look at this"; the tooltip no longer says what it
 * means.
 */
function Unknown({ label = '—' }: { label?: string }) {
  return (
    <span className="text-amber-500/80" title="no value — the project did not say what this means">
      {label}
    </span>
  )
}

function Scalar({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <Unknown />
  if (typeof value === 'boolean') {
    return value
      ? <span className="text-emerald-400">yes</span>
      : <span className="text-neutral-500">no</span>
  }
  if (typeof value === 'number') {
    return <span className="font-mono text-neutral-100">{value.toLocaleString()}</span>
  }
  const text = String(value)
  if (text === '') return <Unknown label="(empty)" />
  return <span className="text-neutral-200 break-words">{text}</span>
}

/** Column order: first-seen across the rows, so the project's own ordering survives. */
function columnsOf(rows: Record<string, unknown>[]): string[] {
  const cols: string[] = []
  for (const row of rows) {
    for (const key of Object.keys(row)) if (!cols.includes(key)) cols.push(key)
  }
  return cols
}

/** How many nested keys are still worth spreading into columns rather than stacking. */
const FLATTEN_MAX_KEYS = 8

/**
 * Spread a uniform one-level nested object into columns: `{health: {up, ms}}` becomes
 * `health.up` and `health.ms`.
 *
 * Why this is worth doing rather than rendering the object in its cell: a nested object
 * stacks its keys vertically, so each row becomes a tall block and comparing two rows
 * means reading two blocks instead of scanning a column. The rows ARE comparable — that
 * is what makes them rows — and a table is the right shape for comparable things.
 *
 * Only when every row agrees on the nested keys. A ragged shape flattened would invent
 * columns most rows do not have, and every gap would render as "unknown" — manufacturing
 * absences out of a rendering choice, which is the one thing this renderer must never do.
 */
function flattenUniformObjects(
  rows: Record<string, unknown>[],
): Record<string, unknown>[] {
  const cols = columnsOf(rows).filter(c => !META_KEYS.has(c))
  const spreadable = cols.filter(col => {
    const values = rows.map(r => r[col])
    if (!values.every(isPlainObject)) return false
    const shapes = values.map(v => Object.keys(v as object).join('\u0000'))
    if (new Set(shapes).size !== 1) return false
    const width = Object.keys(values[0] as object).length
    return width > 0 && width <= FLATTEN_MAX_KEYS
  })
  if (spreadable.length === 0) return rows

  return rows.map(row => {
    const out: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(row)) {
      if (spreadable.includes(key) && isPlainObject(value)) {
        for (const [k, v] of Object.entries(value)) out[`${key}.${k}`] = v
      } else {
        out[key] = value
      }
    }
    return out
  })
}

function Table({ rows: rawRows }: { rows: Record<string, unknown>[] }) {
  const view = useDeprecation()
  const rows = flattenUniformObjects(rawRows)
  // Emphasis is read from the ROW AS DELIVERED — flattening renames keys, and the presence
  // check that stops a marking pointing at nothing has to run against the real object.
  const emphasised = rawRows.map(emphasisOf)
  // Framework keys are machinery, not data: they render as controls or weight, never as
  // a JSON column.
  const dataCols = columnsOf(rows).filter(c => !META_KEYS.has(c))
  const { visible: cols, hiddenCount } = partitionKeys(dataCols, view)
  const hasActions = rows.some(r => Array.isArray(r[ACTIONS_KEY]) && (r[ACTIONS_KEY] as unknown[]).length > 0)
  return (
    <div className="space-y-1">
    <div className="overflow-x-auto rounded border border-neutral-800">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-neutral-900/80 text-neutral-400">
            {cols.map(c => (
              <th key={c} className="text-left font-medium px-2 py-1.5 whitespace-nowrap">
                {view.names.has(c) ? <DeprecatedLabel name={c} /> : c}
              </th>
            ))}
            {hasActions && <th className="text-left font-medium px-2 py-1.5" />}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-neutral-800/70 align-top">
              {cols.map(c => (
                <td key={c} className="px-2 py-1.5 max-w-[26rem]">
                  {!(c in row)
                    ? <Unknown />
                    : emphasisMatches(c, emphasised[i] ?? new Set())
                      ? <Emphasis><StatusValue value={row[c]} depth={2} /></Emphasis>
                      : <StatusValue value={row[c]} depth={2} />}
                </td>
              ))}
              {hasActions && (
                <td className="px-2 py-1.5 whitespace-nowrap">
                  <RowActions value={row[ACTIONS_KEY]} />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    <HiddenNote count={hiddenCount} />
    </div>
  )
}

/**
 * The project ranking its own top-level lists — which of them the reader should look at
 * first, and what it calls each one.
 *
 * The need was measured on the live screen: the project spent a working session moving rows
 * BETWEEN sibling arrays — from the one it calls blocking to the one it calls a warning —
 * and on screen the reclassification was invisible, because three arrays rendered as three
 * identical tables. The work was real and it did not reach the reader.
 *
 * **The weight comes from the ORDER, never from the severity word.** The contract declares
 * the list to be in descending order of weight, so position carries the ranking and this
 * file needs to understand no vocabulary at all — a project saying `critical`/`minor`, or
 * saying it in another language, renders correctly without a change here. The severity
 * string and the label are shown verbatim, as the project's words, not interpreted as
 * instructions.
 *
 * That is also why the ranking is not a number: a rank field beside an ordered list states
 * one fact twice, and a fact stored twice becomes two facts.
 */
export const SECTIONS_KEY = 'sections'

export interface SectionDecl {
  key: string
  severity?: string
  label?: string
  count?: number
}

/**
 * Read a section declaration — but only when the value really is one.
 *
 * `sections` has no reserved prefix, unlike `_emphasis`, and it is an ordinary English word
 * a project might legitimately use for its own data. So the name alone is not enough:
 * this checks the SHAPE, and further requires that at least one declared key names a
 * sibling. A project publishing its own list of document sections keeps it as data, which
 * is the failure that would otherwise be silent — metadata treatment makes data disappear.
 */
export function sectionsOf(obj: Record<string, unknown>): SectionDecl[] {
  const raw = obj[SECTIONS_KEY]
  if (!Array.isArray(raw) || raw.length === 0) return []
  const looksLikeDecl = (s: unknown): s is SectionDecl =>
    isPlainObject(s) && typeof (s as Record<string, unknown>).key === 'string'
  if (!raw.every(looksLikeDecl)) return []
  const decls = raw as unknown as SectionDecl[]
  // A declaration talks about this object. Anything else is the project's own data.
  if (!decls.some(d => d.key in obj)) return []
  return decls
}

/** Prominence by position — three steps, then flat. Weight, not hue: red stays reserved. */
function sectionStyle(index: number): { rule: string; label: string } {
  if (index === 0) return { rule: 'border-l-4 border-neutral-300', label: 'text-neutral-50 font-semibold' }
  if (index === 1) return { rule: 'border-l-2 border-neutral-500', label: 'text-neutral-300 font-medium' }
  return { rule: 'border-l border-neutral-700', label: 'text-neutral-500' }
}

/** How many rows a section's value actually holds, or null when it is not a list. */
function rowsIn(value: unknown): number | null {
  return Array.isArray(value) ? value.length : null
}

function SectionHeading(
  { decl, index, actual }: { decl: SectionDecl; index: number; actual: number | null },
) {
  const style = sectionStyle(index)
  // The count shown is the DATA's, never the declaration's. Where they disagree the
  // disagreement is the finding — a header and its rows saying different numbers is the
  // shape this whole surface exists to make impossible.
  const disagrees = typeof decl.count === 'number' && actual !== null && decl.count !== actual
  return (
    <div className="flex items-baseline gap-2">
      <span className={`text-xs ${style.label}`}>{decl.label || decl.key}</span>
      <span className="text-[10px] text-neutral-600 font-mono" title="the project's own word for this section">
        {decl.severity || decl.key}
      </span>
      {/* No row count here when the two agree: the list below states it, and a heading
          repeating it is one fact in two places — which is how two facts start. It appears
          only to name a disagreement, because THAT the list below cannot say. */}
      {disagrees && (
        <span
          className="text-[11px] text-amber-500"
          title="the project's declared count and the rows it sent do not match"
        >
          declared {decl.count}, {actual} delivered
        </span>
      )}
    </div>
  )
}

function SectionedGrid(
  { obj, depth, sections }: { obj: Record<string, unknown>; depth: number; sections: SectionDecl[] },
) {
  const view = useDeprecation()
  // A declared key that is absent draws NOTHING — not a placeholder, not a note. The
  // declaration says what to look for; the data decides what exists.
  const declared = sections.filter(d => d.key in obj && !view.names.has(d.key))
  const spoken = new Set(declared.map(d => d.key))
  // Anything the declaration did not mention is still shown. A list omitted from the
  // ranking is unranked, not hidden — hiding data because a declaration forgot it would be
  // the declaration overruling the thing it describes.
  const rest = Object.keys(obj).filter(
    k => !META_KEYS.has(k) && k !== SECTIONS_KEY && !spoken.has(k),
  )
  const { visible, hiddenCount } = partitionKeys(rest, view)

  return (
    <div className="space-y-3">
      {declared.map((decl, i) => (
        <section key={decl.key} className={`${sectionStyle(i).rule} pl-2 space-y-1`}>
          <SectionHeading decl={decl} index={i} actual={rowsIn(obj[decl.key])} />
          <StatusValue value={obj[decl.key]} depth={depth + 1} />
        </section>
      ))}
      {visible.length > 0 && (
        <dl className="grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1 text-xs pt-1">
          {visible.map(k => (
            <div key={k} className="contents">
              <dt className="text-neutral-500 truncate" title={k}>{k}</dt>
              <dd className="min-w-0"><StatusValue value={obj[k]} depth={depth + 1} /></dd>
            </div>
          ))}
        </dl>
      )}
      <HiddenNote count={hiddenCount} />
      <RowActions value={obj[ACTIONS_KEY]} />
    </div>
  )
}

function KeyGrid({ obj, depth }: { obj: Record<string, unknown>; depth: number }) {
  const view = useDeprecation()
  const sections = sectionsOf(obj)
  if (sections.length > 0) return <SectionedGrid obj={obj} depth={depth} sections={sections} />
  const all = Object.keys(obj).filter(k => !META_KEYS.has(k))
  const emphasised = emphasisOf(obj)
  if (all.length === 0 && !(ACTIONS_KEY in obj)) return <Unknown label="(no fields)" />
  const { visible, hiddenCount } = partitionKeys(all, view)
  return (
    <div className="space-y-1">
      <dl className="grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1 text-xs">
        {visible.map(k => (
          <div key={k} className="contents">
            <dt className="text-neutral-500 truncate" title={k}>
              {view.names.has(k)
                ? <DeprecatedLabel name={k} />
                : emphasised.has(k) ? <Emphasis>{k}</Emphasis> : k}
            </dt>
            <dd className="min-w-0"><StatusValue value={obj[k]} depth={depth + 1} /></dd>
          </div>
        ))}
      </dl>
      <HiddenNote count={hiddenCount} />
      <RowActions value={obj[ACTIONS_KEY]} />
    </div>
  )
}

/** How many chips are shown before the rest go behind a count. */
const CHIP_LIMIT = 5

/**
 * A list of scalars, shortened when it is long enough to swallow the row it sits in.
 *
 * Measured on the live screen: one blocker row carried three identifier lists and grew to
 * a dozen lines, pushing the other three blockers off the first screenful. A screen that
 * shows everything shows nothing — but the shortening has to obey the rule that outranks
 * it, so the number hidden is ALWAYS stated and is always one click from being shown.
 * "+2 more" is a count from the data; it can never be a silent truncation.
 */
function ChipList({ values, depth }: { values: unknown[]; depth: number }) {
  const [expanded, setExpanded] = useState(false)
  const hidden = values.length - CHIP_LIMIT
  const shown = expanded || hidden <= 0 ? values : values.slice(0, CHIP_LIMIT)

  return (
    <div className="flex flex-wrap items-center gap-1">
      {shown.map((v, i) => (
        <span key={i} className="px-1.5 py-0.5 rounded bg-neutral-800 text-[11px]">
          <StatusValue value={v} depth={depth + 1} />
        </span>
      ))}
      {hidden > 0 && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-[11px] text-neutral-500 hover:text-neutral-300 underline decoration-dotted"
        >
          {expanded ? 'show fewer' : `+${hidden} more`}
        </button>
      )}
    </div>
  )
}

export function StatusValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  const view = useDeprecation()

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-neutral-500 text-xs">none <span className="text-neutral-700">(0)</span></span>
    }
    if (value.every(isPlainObject)) {
      return (
        <div className="space-y-1">
          {/* This number is the renderer's, not the project's, and it says so. "15 items"
              under a key called `openManualTasks` reads as "15 open tasks" — and once the
              project publishes its own derived count, the two sit on one screen saying
              different things, which is the false-value shape with the misleading half
              coming from here. A count of ROWS cannot be mistaken for a claim about what
              the rows mean. Never restore domain-neutral-sounding wording like "items". */}
          <div
            className="text-[11px] text-neutral-500"
            title="rows as delivered — set-core counts them, it does not interpret them"
          >
            {value.length} row{value.length === 1 ? '' : 's'}
          </div>
          <Table rows={value as Record<string, unknown>[]} />
        </div>
      )
    }
    return <ChipList values={value} depth={depth} />
  }

  if (isPlainObject(value)) {
    // Deep nesting is where a generic renderer stops helping and starts hiding. Past
    // this point, show the structure verbatim rather than pretending to understand it.
    if (depth >= 3) {
      // Even the verbatim dump respects the project's deprecations — otherwise a stale
      // field hidden two levels up reappears here, contradicting its replacement again.
      const shown = Object.fromEntries(
        Object.entries(value).filter(
          ([k]) => !META_KEYS.has(k) && (view.show || !view.names.has(k)),
        ),
      )
      return (
        <pre className="text-[11px] text-neutral-400 bg-neutral-900 rounded p-2 overflow-x-auto">
          {JSON.stringify(shown, null, 1)}
        </pre>
      )
    }
    return (
      <div className={depth > 0 ? 'rounded border border-neutral-800 bg-neutral-900/40 p-2' : ''}>
        <KeyGrid obj={value} depth={depth} />
      </div>
    )
  }

  return <Scalar value={value} />
}

export default StatusValue
