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
 */

export function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/** Unknown — never a zero, never a tick. */
function Unknown({ label = '—' }: { label?: string }) {
  return (
    <span className="text-amber-500/80" title="not provided by the project">
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
  const cols = columnsOf(rows)
  return (
    <div className="overflow-x-auto rounded border border-neutral-800">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-neutral-900/80 text-neutral-400">
            {cols.map(c => (
              <th key={c} className="text-left font-medium px-2 py-1.5 whitespace-nowrap">{c}</th>
            ))}
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function KeyGrid({ obj, depth }: { obj: Record<string, unknown>; depth: number }) {
  const entries = Object.entries(obj)
  if (entries.length === 0) return <Unknown label="(no fields)" />
  return (
    <dl className="grid grid-cols-[minmax(8rem,auto)_1fr] gap-x-4 gap-y-1 text-xs">
      {entries.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-neutral-500 truncate" title={k}>{k}</dt>
          <dd className="min-w-0"><StatusValue value={v} depth={depth + 1} /></dd>
        </div>
      ))}
    </dl>
  )
}

export function StatusValue({ value, depth = 0 }: { value: unknown; depth?: number }) {
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
      return (
        <pre className="text-[11px] text-neutral-400 bg-neutral-900 rounded p-2 overflow-x-auto">
          {JSON.stringify(value, null, 1)}
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
