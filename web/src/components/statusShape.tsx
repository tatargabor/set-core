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
 * The command-level caveat's key. It qualifies the COMMAND, not a field, so it is never
 * looked for in the data — a walker that did would report it absent for every project that
 * declares one, and the diagnostics list would then accuse every correct producer of a typo.
 */
export const COMMAND_LEVEL_CAVEAT = '*'

/**
 * Caveats that apply to the values being rendered.
 *
 * A caveat says a value is CORRECT and means something narrower than its name suggests — a
 * count describing the producer's own register rather than the world, a total that is a known
 * lower bound. Distinct from `deprecated`, which says the opposite: that the field is present
 * and nobody stands behind it.
 *
 * `perField` holds only the keys actually FOUND in the answer — see `presentCaveats`. The `"*"`
 * sentence is not in here: it is rendered once in the section header, so putting it in the
 * per-field map would repeat it beside every value.
 */
export interface CaveatView {
  perField: ReadonlyMap<string, string>
}

const CaveatCtx = createContext<CaveatView>({ perField: new Map() })

export const CaveatProvider = CaveatCtx.Provider

export function useCaveats(): CaveatView {
  return useContext(CaveatCtx)
}

/**
 * Which of the declared per-field caveat keys actually appear in this answer.
 *
 * The same rule as `presentDeprecations`, and it is inherited rather than reinvented: the
 * declaration says what to look for, the DATA says what is there. A caveat printed for a field
 * the project stopped sending would be a false absence — the mirror of the false value this
 * family of signals exists to prevent.
 *
 * `"*"` is excluded before the walk, not filtered out of the result: it qualifies the command
 * and lives in no field, so looking for it can only ever fail.
 */
export function presentCaveats(
  value: unknown, caveats: Readonly<Record<string, string>>,
): Map<string, string> {
  const wanted = new Set(Object.keys(caveats).filter(k => k !== COMMAND_LEVEL_CAVEAT))
  const found = new Map<string, string>()
  if (wanted.size === 0) return found

  const walk = (v: unknown) => {
    if (Array.isArray(v)) { v.forEach(walk); return }
    if (!isPlainObject(v)) return
    for (const [k, child] of Object.entries(v)) {
      if (wanted.has(k)) found.set(k, caveats[k])
      walk(child)
    }
  }
  walk(value)
  return found
}

/**
 * Declared per-field caveat keys that are NOT in this answer. Diagnostics, never a gate.
 *
 * The framework cannot tell a typo from a legitimate absence and must not pretend to: a
 * producer's per-status breakdown may list only the statuses currently present, so a caveat
 * keyed on a currently-zero status is correct AND absent. A gate firing daily on that is dead
 * within a week and takes the real warning with it. The producer recognises which is which at a
 * glance — this only makes the question visible.
 */
export function absentCaveatKeys(
  value: unknown, caveats: Readonly<Record<string, string>>,
): string[] {
  const present = presentCaveats(value, caveats)
  return Object.keys(caveats)
    .filter(k => k !== COMMAND_LEVEL_CAVEAT && !present.has(k))
    .sort()
}

/**
 * A caveat, rendered beside the value it qualifies.
 *
 * **Weight is the requirement, not the styling taste.** One visual weight per meaning: if red
 * means broken, a caveat is not red. A caveat says a correct number means something narrower —
 * neither a failure nor a warning — and the producer's own wording may sound alarming without
 * being an alarm. Nothing here reads the sentence to decide how to show it.
 *
 * Not a tooltip and not behind a disclosure, deliberately. The defect being fixed is that the
 * number travels and the caveat does not; a caveat one interaction away has been filed, not
 * carried.
 *
 * **But it is clamped to one line, and that is not the same concession.** A producer reported
 * the same ~200-character sentence appearing three times on one screen — measured here, exactly
 * three — because one field name occurs in three places of their answer, and the sentence is
 * correct beside every one of them. Hiding two would put the qualification where the reader is
 * not standing, which is the original defect wearing a tidier coat. So every occurrence keeps
 * its caveat and each costs ONE line; the rest is a click away for whoever is reading that
 * particular number. The signal stays everywhere, the noise divides by three.
 */
export function CaveatNote({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <div
      onClick={() => setOpen(v => !v)}
      title={open ? undefined : 'show the whole caveat'}
      className={`text-xs leading-snug text-fg-muted italic border-l border-surface-edge pl-2
                  mt-0.5 cursor-pointer ${open ? '' : 'truncate'}`}
    >
      {children}
    </div>
  )
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

/**
 * Exported so the batch control can use the SAME runner as the row control. A second context
 * would be a second write path, and the read/write separation this surface depends on is only
 * as good as the number of ways a write can be reached.
 */
export const ActionCtx = createContext<ActionRunner | null>(null)
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

  if (done) return <span className="text-xs text-emerald-400">recorded</span>

  return (
    <div className="flex flex-wrap items-center gap-1">
      {chooseKeys.map(k => (
        <select
          key={k}
          value={picked[k] ?? ''}
          onChange={e => setPicked(p => ({ ...p, [k]: e.target.value }))}
          className="bg-surface-raised border border-surface-edge rounded text-xs px-1 py-0.5 text-fg-strong"
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
        className="px-2 py-0.5 text-xs rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
      >
        {busy ? '…' : (action.label ?? action.command)}
      </button>
      {error && <span className="text-xs text-red-400" title={error}>failed</span>}
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

/**
 * An action the project declares for a SET of rows, keyed by the list it applies to.
 *
 * Sits beside the list rather than on a row, and that placement is the whole point: pressing a
 * row's button twenty times produces twenty independent assertions, while a selection is ONE
 * statement about a set. The framework therefore never derives this from `actions` — only the
 * project knows whether it has a write that takes a list.
 *
 * `kind` carries the distinction the producer measured on their own side: they have no write
 * that consumes a set, but they do have an engine that consumes a list ONE AT A TIME. Those two
 * are honest about the same count and describe different events, so the confirmation text
 * differs — "add 13 rows to the queue, processed one at a time" versus "act on 13 rows". A
 * reader told the second expects thirteen outcomes and gets one, then waits.
 *
 * `choose` works exactly as it does for a row action: the PROJECT computes the options (its open
 * releases, in the case this was designed for). The framework renders a dropdown and derives
 * nothing — a path language would fail silently and both sides would have to maintain it.
 */
export interface BatchAction {
  command: string
  label?: string
  /** `queue` = the project serialises the list. `set` = one call for the whole set. */
  kind?: 'queue' | 'set'
  /** Which field of a row carries the identifier to hand over. The project names it. */
  idField?: string
  args?: Record<string, unknown>
  choose?: Record<string, string[]>
}

export const BATCH_ACTIONS_KEY = 'batchActions'

/**
 * The batch action declared for one named list, or null.
 *
 * Deliberately strict about `command` only. Everything else is optional and has a stated default,
 * because a declaration that is REFUSED for a missing optional field would make the surface go
 * silent about an action the project believes it offered — the false-absence direction, on the
 * one control that starts work.
 */
export function batchActionFor(parent: unknown, listKey: string): BatchAction | null {
  if (!isPlainObject(parent)) return null
  const table = parent[BATCH_ACTIONS_KEY]
  if (!isPlainObject(table)) return null
  const declared = table[listKey]
  if (!isPlainObject(declared) || typeof declared.command !== 'string') return null
  return declared as unknown as BatchAction
}

/** Framework-level keys — the only names this renderer knows, none of them a domain name. */
export const META_KEYS: ReadonlySet<string> = new Set([
  ACTIONS_KEY,
  EMPHASIS_KEY,
  BATCH_ACTIONS_KEY,
])

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
      className="inline-block border-l-2 border-sky-500/70 pl-1.5 font-medium text-fg-brightest"
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
    <div className="text-xs text-fg-ghost italic">
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

/**
 * A cell stops showing text past this many characters and offers the row detail instead.
 *
 * Defined here rather than beside the table because the layout decision below has to predict
 * exactly what the table will do. Two copies of this number would agree on the day they were
 * written and silently disagree afterwards, and the disagreement would show up as a clipped
 * column — a defect nobody would trace back to a constant.
 */
export const CELL_CLIP_CHARS = 42

/** Monospace at 14px, measured once and shared — see `charBudgetFor` for what it is an estimate of. */
export const PX_PER_CHAR = 8.4

/** What a table spends before any data: header rule, row padding, the expander column. */
export const TABLE_CHROME_PX = 92

/**
 * How many characters of table this width can carry, roughly.
 *
 * Monospace at 14px runs about 8.4px per character, and each column costs a gap on top of its
 * content. Deliberately an ESTIMATE with a stated basis: the alternative is measuring after the
 * fact and reflowing, which flashes a wrong layout at the reader before correcting it.
 */
export function charBudgetFor(px: number): number {
  return Math.floor(px / PX_PER_CHAR)
}

/** The width this table wants on screen, in pixels — the character estimate plus its chrome. */
export function tablePxWidth(rows: Record<string, unknown>[]): number {
  return tableCharWidth(rows) * PX_PER_CHAR + TABLE_CHROME_PX
}

/** The clip a cell falls back to when the table has no width to spare. */
export const CELL_CLIP_PX = CELL_CLIP_CHARS * PX_PER_CHAR

/**
 * How wide a clipped cell may run: the fallback clip PLUS the width the table left unused.
 *
 * The surface's width requirement is that every block uses the width it was given. A table that
 * flows into several groups already does. A table that fits ONCE did not, and the gap it left was
 * paid for by its longest column: measured on a two-row table in a 1150px panel, the table drew at
 * ~940px with ~470px of panel empty beside it while the cell carrying an open human decision
 * clipped at 42 characters. The width was there and the only content anyone needed was the content
 * being cut.
 *
 * Widening the CLIP rather than the table is deliberate. `table-layout: auto` hands spare width to
 * the column that asks for it, so short columns stay short and only the long one grows; forcing
 * the table to full width would stretch every column and rebuild the strip-of-nothing this file's
 * own history warns about.
 *
 * `groups` is how many side-by-side copies the table renders. Anything but one means the width is
 * already spoken for, and the fallback applies unchanged.
 */
export function cellClipPxFor(
  rows: Record<string, unknown>[], availPx: number, groups: number,
): number {
  if (groups !== 1 || availPx <= 0) return CELL_CLIP_PX
  const spare = availPx - tablePxWidth(rows)
  return spare > 0 ? CELL_CLIP_PX + spare : CELL_CLIP_PX
}

/**
 * The width this table wants, in characters — header included.
 *
 * Counts the columns the table will ACTUALLY render, which means flattening first: a `review`
 * object holding four keys is one top-level key and four columns. Counting the key instead of
 * the columns is what put a 7-column table into a half-width slot and clipped `review.criti…`
 * off its right edge — the same proxy-for-the-thing mistake as measuring a process by a
 * remembered PID.
 *
 * The per-column width is the wider of its header and its longest displayed value, and the
 * value is capped at the clip length because that is what the cell will show.
 */
export function tableCharWidth(rows: Record<string, unknown>[]): number {
  const flat = flattenUniformObjects(rows)
  const cols = columnsOf(flat).filter(c => !META_KEYS.has(c))
  const GAP = 3
  return cols.reduce((sum, c) => {
    let widest = c.length
    for (const r of flat) {
      const v = r[c]
      if (v === null || v === undefined || typeof v === 'object') continue
      widest = Math.max(widest, Math.min(String(v).length, CELL_CLIP_CHARS))
    }
    return sum + widest + GAP
  }, 0)
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

/**
 * Fields the project says carry a followable path — the declaration, not a guess.
 *
 * `names` is what the envelope declared; `present` is which of those the DATA actually holds,
 * mapped to the path each one carries. Both are needed and they are not the same question: the
 * declaration says what to look for, the data says what is there. Offering a control for a
 * declared field the project stopped sending would offer to follow a path that is not in the
 * answer — a false absence with a button attached.
 */
export interface FollowView {
  names: ReadonlySet<string>
  present: ReadonlyMap<string, string>
  /** Which command this answer came from — the stream needs it to re-verify the path. */
  command: string
  /** Whose tree it is. Carried here so no renderer has to reach for routing state. */
  project: string
  /** The field being followed right now, or null. Held here, not in the control. */
  open: string | null
  setOpen: (field: string | null) => void
}

const FollowCtx = createContext<FollowView>({
  names: new Set(), present: new Map(), command: '', project: '',
  open: null, setOpen: () => {},
})

export const FollowProvider = FollowCtx.Provider

export function useFollow(): FollowView {
  return useContext(FollowCtx)
}

/**
 * Which follow-declared fields actually appear in this answer, and what path each holds.
 *
 * Mirrors `presentCaveats` deliberately, including the walk: one selector rule for the whole
 * envelope means a producer never has to remember which key shape applies where.
 *
 * A declared field holding null, an empty string, or a non-string is NOT a target. That is the
 * ordinary state of a project between runs — nothing to follow, which is not a failure.
 */
export function presentFollowTargets(
  value: unknown, names: readonly string[],
): Map<string, string> {
  const wanted = new Set(names.filter(Boolean))
  const found = new Map<string, string>()
  if (wanted.size === 0) return found

  const walk = (v: unknown) => {
    if (Array.isArray(v)) { v.forEach(walk); return }
    if (!isPlainObject(v)) return
    for (const [k, child] of Object.entries(v)) {
      if (wanted.has(k) && typeof child === 'string' && child.trim() && !found.has(k)) {
        found.set(k, child)
      }
      walk(child)
    }
  }
  walk(value)
  return found
}

/**
 * The control offered beside a field the project declared followable.
 *
 * Rendered only where `presentFollowTargets` found the field IN THE DATA — never from the
 * declaration alone, and never from a field's name. A control offered for a path the answer no
 * longer carries would be refused by the endpoint anyway; showing it would be a button that
 * exists to fail.
 *
 * It opens a panel it does not contain. The first version rendered the panel right here, inside
 * the value's own grid cell, and it worked in every structural sense — the stream connected, the
 * lines arrived, no console error. On screen the panel was about 180px wide and broke words
 * across lines two characters at a time. A log is the widest thing this surface shows and it had
 * been put in the narrowest box available; the counts said "rendered", and only looking said
 * "unreadable". So the field holds the switch and the answer holds the panel.
 */
export function FollowControl({ field }: { field: string }) {
  const { open, setOpen, command, project } = useFollow()
  if (!command || !project) return null
  const active = open === field
  return (
    <button
      onClick={() => setOpen(active ? null : field)}
      className="ml-2 text-xs px-1.5 py-0.5 rounded border border-surface-line
                 text-fg-muted hover:text-fg-strong hover:border-surface-edge align-middle"
      title={active ? 'stop following this file' : 'follow this file live'}
    >
      {active ? 'following ×' : 'follow'}
    </button>
  )
}
