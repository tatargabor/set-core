/**
 * Shape-level machinery shared by the status renderer and the status table.
 *
 * Extracted from `StatusValue.tsx` when the table grew controls of its own. The split is
 * along one line and it is worth stating, because the next person will be tempted to move
 * something across it: **nothing in this file knows a domain name.** It knows shapes
 * (scalar, uniform object, list of rows) and the three framework-level envelope keys, which
 * belong to the contract rather than to anyone's vocabulary.
 *
 * The direction of the dependency is also deliberate. This file imports neither of the two
 * renderers; they import it. A cycle between a renderer and its table would work in this
 * bundler and fail in the next one, and the failure looks like an undefined component at
 * render time — a long way from its cause.
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

export function RowActions({ value }: { value: unknown }) {
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
export const META_KEYS: ReadonlySet<string> = new Set([ACTIONS_KEY, EMPHASIS_KEY])

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
export function emphasisMatches(col: string, emphasised: ReadonlySet<string>): boolean {
  if (emphasised.has(col)) return true
  const dot = col.indexOf('.')
  return dot > 0 && emphasised.has(col.slice(0, dot))
}

/** The project's marking, drawn as weight — deliberately not in the colour that means broken. */
export function Emphasis({ children }: { children: ReactNode }) {
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
export function partitionKeys(keys: string[], view: DeprecationView) {
  if (view.names.size === 0) return { visible: keys, hiddenCount: 0 }
  const deprecated = keys.filter(k => view.names.has(k))
  if (view.show) return { visible: keys, hiddenCount: 0 }
  return {
    visible: keys.filter(k => !view.names.has(k)),
    hiddenCount: deprecated.length,
  }
}

export function HiddenNote({ count }: { count: number }) {
  if (count === 0) return null
  return (
    <div className="text-[11px] text-neutral-600 italic">
      {count} deprecated field{count === 1 ? '' : 's'} hidden
    </div>
  )
}

/** A deprecated field, when the reader asked to see it: visibly not to be relied on. */
export function DeprecatedLabel({ name }: { name: string }) {
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
export function Unknown({ label = '—' }: { label?: string }) {
  return (
    <span className="text-amber-500/80" title="no value — the project did not say what this means">
      {label}
    </span>
  )
}

/** Column order: first-seen across the rows, so the project's own ordering survives. */
export function columnsOf(rows: Record<string, unknown>[]): string[] {
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
export function flattenUniformObjects(
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
