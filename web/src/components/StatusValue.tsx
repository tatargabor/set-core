/**
 * Renders a value a project reported about itself — by SHAPE, never by name.
 *
 * No field name appears anywhere in this file, and that is the point. set-core does not
 * know what a project calls its releases, and the next project to publish a contract will
 * call them something else. A renderer that special-cases a known key becomes coupled to
 * one project's vocabulary and quietly stops working for the second one.
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
 *
 * The shape machinery lives in `statusShape.tsx` and the table in `StatusTable.tsx`; both
 * are re-exported here so this module stays the single import surface it has always been.
 */

import { useState } from 'react'
import {
  ACTIONS_KEY,
  type BatchAction,
  batchActionFor,
  DeprecatedLabel,
  Emphasis,
  HiddenNote,
  META_KEYS,
  RowActions,
  Unknown,
  emphasisOf,
  isPlainObject,
  partitionKeys,
  useCaveats,
  CaveatNote,
  CommandCaveat,
  FollowControl,
  useFollow,
  useDeprecation,
  type ResolvedRole,
  resolveRole,
  foldedPartners,
  useRoles,
  humanDuration,
  ProgressValue,
  LimitValue,
} from './statusShape'
import { StatusTable } from './StatusTable'

export {
  ACTIONS_KEY,
  ActionProvider,
  DeprecationProvider,
  EMPHASIS_KEY,
  FollowProvider,
  RoleProvider,
  presentFollowTargets,
  emphasisOf,
  isPlainObject,
  presentDeprecations,
  useDeprecation,
} from './statusShape'
export type { ActionRunner, DeprecationView, RowAction } from './statusShape'

/**
 * How long a value may be and still share a row with its neighbours.
 *
 * Not a style choice: past this, the label plus the value stops fitting a track, and the value
 * wraps into a narrow column — the cell-tower shape this surface removed from tables and must not
 * reintroduce in key grids.
 */
const SHORT_VALUE_CHARS = 24

function Scalar({ value, role = null }: { value: unknown; role?: ResolvedRole | null }) {
  if (value === null || value === undefined) return <Unknown />
  if (typeof value === 'boolean') {
    return value
      ? <span className="text-emerald-400">yes</span>
      : <span className="text-fg-faint">no</span>
  }
  if (typeof value === 'number') {
    // The role decides WHAT this number is; everything below decides how it looks, and can be
    // changed here without a single producer re-shipping. Undeclared keeps today's behaviour —
    // every integer a quantity — which is right far more often than it is wrong.
    if (role?.kind === 'progress') {
      return <ProgressValue value={value} partnerValue={role.partnerValue} partner={role.partner} />
    }
    if (role?.kind === 'limit') {
      return <LimitValue value={value} partnerValue={role.partnerValue} partner={role.partner} />
    }
    if (role?.kind === 'id') {
      // An identifier is a NAME. Grouping its digits invites the eye to compare magnitudes that
      // do not exist — the measured case was a process id rendered as `3,218,705`.
      return <span className="text-fg-loud tabular-nums">{String(value)}</span>
    }
    if (role?.kind === 'duration-seconds') {
      return (
        <span className="text-fg-loud tabular-nums" title={`${value}s`}>
          {humanDuration(value)}
        </span>
      )
    }
    return <span className="text-fg-loud tabular-nums">{value.toLocaleString()}</span>
  }
  const text = String(value)
  if (text === '') return <Unknown label="(empty)" />
  if (role?.kind === 'path') {
    // A path is not prose, so it does not get the reading measure below — that wraps an
    // inline-block around the value and misaligns it in a grid built for short scalars. It also
    // has no spaces, so word wrapping cannot help it: `break-all` is what keeps a long path
    // inside its container instead of pushing the column wider.
    return <span className="text-fg-strong break-all">{text}</span>
  }
  // Prose gets a measure. Measured on a 1920 px screen: a project's `note` and `description`
  // ran the full 1650 px of the panel — roughly 200 characters per line, which the eye cannot
  // track back to the next line's start. 80ch is the long end of the readable range and, in this
  // monospace face, about 672 px; every table cell is already capped tighter than that, so the
  // cap binds exactly where the text is running loose and nowhere else.
  //
  // Applied by LENGTH, not by field name — this renderer never learns what a field means. Below
  // the threshold no line can reach an uncomfortable measure anyway, so the cap would only add
  // an inline-block nobody asked for.
  if (text.length > 90) {
    return <span className="text-fg-strong break-words inline-block max-w-[80ch] align-top">{text}</span>
  }
  return <span className="text-fg-strong break-words">{text}</span>
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
  if (index === 0) return { rule: 'border-l-4 border-fg-normal', label: 'text-fg-brightest font-semibold' }
  if (index === 1) return { rule: 'border-l-2 border-fg-faint', label: 'text-fg-normal font-medium' }
  return { rule: 'border-l border-surface-edge', label: 'text-fg-faint' }
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
      <span className={`text-sm ${style.label}`}>{decl.label || decl.key}</span>
      <span className="text-xs text-fg-ghost uppercase tracking-wide" title="the project's own word for this section">
        {decl.severity || decl.key}
      </span>
      {/* No row count here when the two agree: the list below states it, and a heading
          repeating it is one fact in two places — which is how two facts start. It appears
          only to name a disagreement, because THAT the list below cannot say. */}
      {disagrees && (
        <span
          className="text-xs text-amber-500"
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
  const roles = useRoles()
  // The per-field signals moved into `FieldExtras`, which reads them itself.
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
          <StatusValue value={obj[decl.key]} depth={depth + 1} batch={batchActionFor(obj, decl.key)} role={resolveRole(roles, obj, decl.key)} />
        </section>
      ))}
      {visible.filter(k => !isBlockValue(obj[k])).length > 0 && (
        <dl className="grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1 text-sm pt-1">
          {visible.filter(k => !isBlockValue(obj[k])).map(k => (
            <div key={k} className="contents">
              <dt className="text-fg-faint truncate" title={k}>{k}</dt>
              <dd className="min-w-0">
                <StatusValue value={obj[k]} depth={depth + 1} batch={batchActionFor(obj, k)} role={resolveRole(roles, obj, k)} />
                <FieldExtras k={k} />
              </dd>
            </div>
          ))}
        </dl>
      )}
      {/* A tall value takes the full width with its name above it — see `isBlockValue`. */}
      {visible.filter(k => isBlockValue(obj[k])).map(k => (
        <section key={k} className="space-y-1 pt-1">
          <div className="text-sm text-fg-faint">{k}</div>
          <StatusValue value={obj[k]} depth={depth + 1} batch={batchActionFor(obj, k)} role={resolveRole(roles, obj, k)} />
          <FieldExtras k={k} block />
        </section>
      ))}
      <HiddenNote count={hiddenCount} />
      <RowActions value={obj[ACTIONS_KEY]} />
    </div>
  )
}

/**
 * Is this value tall enough that a label beside it becomes a full-height gutter?
 *
 * The grid these labels live in shares one column across every row, so its width is set by the
 * widest label and its HEIGHT is the sum of every value. Put a 174-row table in one of those
 * rows and the word `bugs` reserves 150px for the whole length of the table — measured on a
 * live screen, a strip of nothing running the entire page beside the only content on it.
 *
 * So a label sits BESIDE a value it is comparable in size to, and ABOVE one it is not. The test
 * is the value's shape, not its key: anything that renders as a table or a block of its own.
 */
function isBlockValue(v: unknown): boolean {
  if (Array.isArray(v)) return v.length > 0
  return isPlainObject(v)
}

/**
 * Everything that hangs off a field's value: its caveat, and the control to follow it.
 *
 * One place rather than four. The four sites — two in the sectioned grid, two in the plain one —
 * had already drifted into being copies of each other, and a fifth signal would have had to be
 * added to all of them, which is exactly how one of them ends up missing it.
 *
 * Order matters: the control sits ON the value's line, the caveat BELOW it. A caveat is a
 * sentence about the value and belongs under it; a control is an affordance and belongs where
 * the eye already is.
 */
function FieldExtras({ k, block = false }: { k: string; block?: boolean }) {
  const caveats = useCaveats()
  const follow = useFollow()
  const path = follow.present.get(k)
  const caveat = caveats.perField.get(k)
  return (
    <>
      {path && <FollowControl field={k} />}
      {/*
        A marker beside a VALUE; a sentence under a BLOCK.

        The marker works by adjacency — it inherits the meaning of the thing it sits next to. A
        block is a table or a nested object with a heading, and there is no value beside it, so
        the same marker renders as a lone exclamation mark qualifying a whole section. Measured
        twice on the live screen after the marker shipped: two orphan glyphs, neither attached to
        anything a reader could name. A block also has the room a single field does not.
      */}
      {caveat !== undefined && (
        block
          ? <CommandCaveat>{caveat}</CommandCaveat>
          : <CaveatNote>{caveat}</CaveatNote>
      )}
    </>
  )
}

function KeyGrid({ obj, depth }: { obj: Record<string, unknown>; depth: number }) {
  const view = useDeprecation()
  const roles = useRoles()
  const folded = foldedPartners(roles, obj)
  // The caveat is read by `FieldExtras`, which renders it beside the value — the number and
  // its qualification travel together, which is the whole reason the signal exists. It is no
  // longer read HERE, because it no longer affects how wide a row is.
  const sections = sectionsOf(obj)
  if (sections.length > 0) return <SectionedGrid obj={obj} depth={depth} sections={sections} />
  // A partner already shown verbatim inside its pair does not get a second row. Driven by the
  // project's OWN declaration that the two fields are one fact — never by a judgement here.
  const all = Object.keys(obj).filter(k => !META_KEYS.has(k) && !folded.has(k))
  const emphasised = emphasisOf(obj)
  if (all.length === 0 && !(ACTIONS_KEY in obj)) return <Unknown label="(no fields)" />
  const { visible, hiddenCount } = partitionKeys(all, view)
  // A record of many short scalars is a LIST, not a paragraph: stacked one per row it spends a
  // full-width panel on a column of about 200px and pushes everything below it off the fold.
  // Measured on a live answer — a six-key block used 12% of the width available to it.
  //
  // The condition is read from the data, never from a key name: every value a scalar, every
  // rendered value short, and enough of them that columns beat a stack. A block with one long
  // value stays stacked, because wrapping it into a narrow column is the cell-tower defect this
  // surface spent the day removing.
  //
  // The earlier version required EVERY field to be short and stacked the whole block otherwise —
  // so one long `description` among nine short fields forced all ten into a 200px column fourteen
  // rows deep. A single field decided the layout of its neighbours.
  //
  // Now each field decides only for itself: short ones flow into tracks, a long one takes a full
  // row. The project's ORDER is preserved exactly — no `dense` packing, because backfilling a gap
  // with a later field would silently reorder someone else's record, and this renderer promotes
  // nothing.
  const isWide = (k: string) => {
    const v = obj[k]
    if (isBlockValue(v)) return true
    // The caveat used to count toward this width, because it rendered as a sentence on the
    // value's own line and a long one wrapped a 200px column seven lines deep. It is a
    // fixed-width marker now, so including it would widen rows for a thing that no longer
    // takes width — and the cost of that was measured, not guessed: it pushed `change`,
    // `tasksDone` and `state` out of the compact grid and down the page, which is the exact
    // complaint this whole round is answering.
    return String(v ?? '').length > SHORT_VALUE_CHARS
  }

  /**
   * DECLARED order, unchanged — and the alignment is fixed by having fewer wide fields instead.
   *
   * Sorting the short fields first did line the columns up, and it was wrong. Measured on the
   * live screen: the producer sends `change` and `title` first because that is what the block is
   * ABOUT, and reordering by width buried them under `pid`, `turns` and `lastToolAt`. The field
   * order is the one statement of importance a project makes without any extra declaration, and
   * a renderer that overrides it has decided something about someone else's domain.
   *
   * The raggedness had a different cause anyway: six fields counted as wide because their CAVEAT
   * was long, and the caveat is a marker now. Two remain wide in the measured block, and a grid
   * that breaks twice reads as a grid.
   */
  const inline = visible.filter(k => !isBlockValue(obj[k]))
  const blocks = visible.filter(k => isBlockValue(obj[k]))
  // Tracks are worth having only once several fields can share a row.
  const compact = inline.filter(k => !isWide(k)).length >= 2

  return (
    <div className="space-y-1">
      <dl className={
        compact
          // `auto-fill`, not `auto-fit`: auto-fit collapses the empty tracks and stretches the
          // survivors, so a two-field block spreads each pair across half a 1650px panel and puts
          // 600px of nothing between a label and its value. auto-fill keeps the track width, so
          // pairs stay the size they need and simply leave the rest of the row unused.
          ? 'grid gap-x-8 gap-y-1 text-sm [grid-template-columns:repeat(auto-fill,minmax(22rem,1fr))]'
          : 'grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1 text-sm'
      }>
        {inline.map(k => (
          <div
            key={k}
            className={compact
              ? `grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4${isWide(k) ? ' col-span-full' : ''}`
              : 'contents'}
          >
            <dt className="text-fg-faint truncate" title={k}>
              {view.names.has(k)
                ? <DeprecatedLabel name={k} />
                : emphasised.has(k) ? <Emphasis>{k}</Emphasis> : k}
            </dt>
            <dd className="min-w-0">
              <StatusValue value={obj[k]} depth={depth + 1} batch={batchActionFor(obj, k)} role={resolveRole(roles, obj, k)} />
              <FieldExtras k={k} />
            </dd>
          </div>
        ))}
      </dl>
      {/*
        Blocks sit SIDE BY SIDE when they fit, instead of stacking full-width down the page.

        Reported by the user, twice, against two different tabs: "kihasználatlan helyek jobbra".
        Measured on a 1920 px screen — a 7-column table rendered ~700 px wide with ~950 px of the
        panel empty beside it, and the next block waiting a screenful below. Nothing was wrong
        with either block; the page was simply spending its width on nothing.

        `auto-fit` with a 38rem floor, not a column count: at 1920 px that is two columns of
        ~825 px, at laptop width one. No breakpoint to maintain, and no screen size where a block
        is squeezed below its floor. Only rendered when there is more than one block — a grid of
        one is a stack with extra machinery.
      */}
      <div>
        {blocks.map(k => (
          <section key={k} className="space-y-1 pt-1">
            <div className="text-sm text-fg-faint">{k}</div>
            <StatusValue value={obj[k]} depth={depth + 1} batch={batchActionFor(obj, k)} role={resolveRole(roles, obj, k)} />
            <FieldExtras k={k} block />
          </section>
        ))}
      </div>
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
        <span key={i} className="px-1.5 py-0.5 rounded bg-surface-raised text-xs">
          <StatusValue value={v} depth={depth + 1} />
        </span>
      ))}
      {hidden > 0 && (
        <button
          onClick={() => setExpanded(v => !v)}
          className="text-xs text-fg-faint hover:text-fg-normal underline decoration-dotted"
        >
          {expanded ? 'show fewer' : `+${hidden} more`}
        </button>
      )}
    </div>
  )
}

export function StatusValue(
  { value, depth = 0, batch = null, role = null }: {
    value: unknown
    depth?: number
    /**
     * What this value IS, as the project declared it — resolved by the caller, because only the
     * caller knows the field's name AND the object it sits in. A paired role needs both: the
     * partner is looked up among that object's own keys and nowhere else.
     */
    role?: ResolvedRole | null
    /**
     * A batch action the PARENT object declared for THIS list. Passed down rather than looked
     * up here, because by the time a list is being rendered its own key is gone — and the
     * declaration is keyed by that name. A list reached any other way simply has none.
     */
    batch?: BatchAction | null
  },
) {
  const view = useDeprecation()
  const tableRoles = useRoles()

  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="text-fg-faint text-xs">none <span className="text-fg-dim">(0)</span></span>
    }
    if (value.every(isPlainObject)) {
      // The row count moved INTO the table, because that is where a filter can make it
      // stop being the whole truth. It still counts ROWS and says so: under a key like
      // `openManualTasks`, "15 items" reads as "15 open tasks", and once the project
      // publishes its own derived count the screen carries two numbers about one thing.
      return (
        <StatusTable
          rows={value as Record<string, unknown>[]}
          renderValue={(v, d, owner, key) => (
            <StatusValue
              value={v} depth={d}
              role={owner && key ? resolveRole(tableRoles, owner, key) : null}
            />
          )}
          batch={batch}
        />
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
        <pre className="text-xs text-fg-muted bg-surface-panel rounded p-2 overflow-x-auto">
          {JSON.stringify(shown, null, 1)}
        </pre>
      )
    }
    return (
      // The minimum width is not decoration. A nested object inside a table cell renders a
      // two-column grid whose label column alone wants 8rem; in a narrow cell the value
      // column collapses to about one character per line, and a one-sentence field turns a
      // row into a 500-pixel tower. Measured on a live answer, not reasoned about — a
      // ragged nested key cannot be flattened into columns (correctly, since most rows do
      // not have it), so the cell is where it has to be survivable.
      //
      // The variable is NESTING, not length, and the producer measured it: the offending
      // string was the 15th longest value on the whole surface, and the longest — about
      // nine times its size — renders fine at top level, where it has the page's width.
      // So do not "fix" this by asking the project to shorten anything.
      <div className={depth > 0 ? 'rounded border border-surface-line bg-surface-panel/40 p-2 min-w-[18rem]' : ''}>
        <KeyGrid obj={value} depth={depth} />
      </div>
    )
  }

  return <Scalar value={value} role={role} />
}

export default StatusValue
