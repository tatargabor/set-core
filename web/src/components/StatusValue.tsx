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

import { createContext, useContext, useState } from 'react'

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

function Table({ rows }: { rows: Record<string, unknown>[] }) {
  const view = useDeprecation()
  // `actions` is machinery, not data: it renders as controls, never as a JSON column.
  const dataCols = columnsOf(rows).filter(c => c !== ACTIONS_KEY)
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
                  {c in row ? <StatusValue value={row[c]} depth={2} /> : <Unknown />}
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

function KeyGrid({ obj, depth }: { obj: Record<string, unknown>; depth: number }) {
  const view = useDeprecation()
  const all = Object.keys(obj).filter(k => k !== ACTIONS_KEY)
  if (all.length === 0 && !(ACTIONS_KEY in obj)) return <Unknown label="(no fields)" />
  const { visible, hiddenCount } = partitionKeys(all, view)
  return (
    <div className="space-y-1">
      <dl className="grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1 text-xs">
        {visible.map(k => (
          <div key={k} className="contents">
            <dt className="text-neutral-500 truncate" title={k}>
              {view.names.has(k) ? <DeprecatedLabel name={k} /> : k}
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

export function StatusValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
  const view = useDeprecation()

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-neutral-500 text-xs">none <span className="text-neutral-700">(0)</span></span>
    }
    if (value.every(isPlainObject)) {
      return (
        <div className="space-y-1">
          <div className="text-[11px] text-neutral-500">{value.length} item{value.length === 1 ? '' : 's'}</div>
          <Table rows={value as Record<string, unknown>[]} />
        </div>
      )
    }
    return (
      <div className="flex flex-wrap gap-1">
        {value.map((v, i) => (
          <span key={i} className="px-1.5 py-0.5 rounded bg-neutral-800 text-[11px]">
            <StatusValue value={v} depth={depth + 1} />
          </span>
        ))}
      </div>
    )
  }

  if (isPlainObject(value)) {
    // Deep nesting is where a generic renderer stops helping and starts hiding. Past
    // this point, show the structure verbatim rather than pretending to understand it.
    if (depth >= 3) {
      // Even the verbatim dump respects the project's deprecations — otherwise a stale
      // field hidden two levels up reappears here, contradicting its replacement again.
      const shown = Object.fromEntries(
        Object.entries(value).filter(
          ([k]) => k !== ACTIONS_KEY && (view.show || !view.names.has(k)),
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
