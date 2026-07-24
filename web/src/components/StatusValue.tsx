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
  DeprecatedLabel,
  Emphasis,
  HiddenNote,
  META_KEYS,
  RowActions,
  Unknown,
  emphasisOf,
  isPlainObject,
  partitionKeys,
  useDeprecation,
} from './statusShape'
import { StatusTable } from './StatusTable'

export {
  ACTIONS_KEY,
  ActionProvider,
  DeprecationProvider,
  EMPHASIS_KEY,
  emphasisOf,
  isPlainObject,
  presentDeprecations,
  useDeprecation,
} from './statusShape'
export type { ActionRunner, DeprecationView, RowAction } from './statusShape'

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
      // The row count moved INTO the table, because that is where a filter can make it
      // stop being the whole truth. It still counts ROWS and says so: under a key like
      // `openManualTasks`, "15 items" reads as "15 open tasks", and once the project
      // publishes its own derived count the screen carries two numbers about one thing.
      return (
        <StatusTable
          rows={value as Record<string, unknown>[]}
          renderValue={(v, d) => <StatusValue value={v} depth={d} />}
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
        <pre className="text-[11px] text-neutral-400 bg-neutral-900 rounded p-2 overflow-x-auto">
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
      <div className={depth > 0 ? 'rounded border border-neutral-800 bg-neutral-900/40 p-2 min-w-[18rem]' : ''}>
        <KeyGrid obj={value} depth={depth} />
      </div>
    )
  }

  return <Scalar value={value} />
}

export default StatusValue
