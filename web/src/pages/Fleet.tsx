import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

/**
 * Fleet — every agent session running on this machine.
 *
 * ONE table, not one per project. The first draft rendered a separate table per
 * project and it was measured by looking at it: twelve repeated header rows, and
 * every column landing at a different x because each table computed its own
 * layout. Rows that answer the same question in the same fields belong in one
 * table (`.claude/rules/ui-quality.md`); the project is a column, not a heading.
 *
 * Two things are deliberately loud rather than tidy:
 *
 *  - `quiet` is never rendered as "idle" nor given a calm colour. Measured
 *    2026-08-18: the runtime flushes a turn's entries to the session log in
 *    batches, and a log was observed ~25s stale while its session was actively
 *    working. So `quiet` means "no outstanding tool call as of the last flush",
 *    and the header says so where the reader is standing.
 *  - an agent whose state could not be determined shows `unknown` WITH its
 *    reason, and the count sits next to the total. A gap is not a zero.
 */

interface FleetAgent {
  pid: number
  name: string | null
  project: string | null
  branch: string | null
  session_id: string | null
  binding_confirmed: boolean
  sources: string[]
  kind: string
  state: string
  tool: string | null
  tool_elapsed_seconds: number | null
  other_tools: string[]
  last_movement_seconds: number | null
  unknown_reason: string | null
}

interface FleetProject {
  name: string
  root: string
  sources: string[]
  archived: boolean
  agents: FleetAgent[]
}

interface FleetResponse {
  agents: number
  working: number
  unknown: number
  projects: FleetProject[]
  quiet_means: string
}

interface Row {
  agent: FleetAgent
  project: FleetProject
  /** First row of its project group — the only one that prints the project name. */
  first: boolean
}

function age(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 90) return `${Math.round(seconds)}mp`
  if (seconds < 5400) return `${Math.round(seconds / 60)}p`
  return `${Math.round(seconds / 3600)}ó`
}

function StateCell({ agent }: { agent: FleetAgent }) {
  if (agent.state === 'working') {
    return (
      <span className="inline-flex items-center gap-1.5 text-emerald-400 whitespace-nowrap">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
        <span className="font-mono">{agent.tool ?? 'dolgozik'}</span>
        {agent.tool_elapsed_seconds !== null && (
          <span className="text-fg-muted tabular-nums">{age(agent.tool_elapsed_seconds)}</span>
        )}
        {agent.other_tools.length > 0 && (
          <span className="text-fg-muted">+{agent.other_tools.length}</span>
        )}
      </span>
    )
  }
  if (agent.state === 'unknown') {
    return (
      <span
        className="inline-flex items-center gap-1.5 text-amber-400 whitespace-nowrap"
        title={agent.unknown_reason ?? ''}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
        ismeretlen
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-fg-muted whitespace-nowrap">
      <span className="w-1.5 h-1.5 rounded-full bg-surface-line shrink-0" />
      csendes
    </span>
  )
}

export default function Fleet() {
  const [data, setData] = useState<FleetResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = () => {
      fetch('/api/fleet/agents')
        .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then(d => { if (!cancelled) { setData(d); setError(null) } })
        .catch(e => { if (!cancelled) setError(String(e.message ?? e)) })
    }
    load()
    const timer = setInterval(load, 5000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [])

  if (error) {
    return <div className="p-6 text-sm text-red-400">A flotta nem olvasható: {error}</div>
  }
  if (!data) {
    return <div className="p-6 text-sm text-fg-muted">Betöltés…</div>
  }

  const populated = data.projects.filter(p => p.agents.length > 0 && !p.archived)
  const empty = data.projects.filter(p => p.agents.length === 0 && !p.archived)

  const rows: Row[] = populated.flatMap(project =>
    project.agents.map((agent, i) => ({ agent, project, first: i === 0 })),
  )

  return (
    <div className="h-full overflow-y-auto">
      {/* Breadcrumb, matching the other global pages — a page you can arrive at
          cold has to say where it is. */}
      <div className="sticky top-0 z-10 flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 md:px-6 py-2.5
                      bg-surface-page border-b border-surface-line">
        <span className="text-sm font-semibold text-fg-loud">Flotta</span>
        <span className="text-xs text-fg-muted tabular-nums">
          {data.agents} agent · {populated.length} projekt
        </span>
        {data.working > 0 && (
          <span className="text-xs text-emerald-400 tabular-nums">{data.working} dolgozik</span>
        )}
        {/* A gap is not a zero: the unknown count sits beside the total, not
            inside something that has to be opened. */}
        {data.unknown > 0 && (
          <span className="text-xs text-amber-400 tabular-nums">{data.unknown} ismeretlen</span>
        )}
        <span className="text-xs text-fg-muted">
          a <span className="text-fg-strong">csendes</span> nem azt jelenti, hogy nem történik semmi —
          csak azt, hogy a napló legutóbbi kiírásakor nem volt nyitott eszközhívás
        </span>
      </div>

      <div className="px-4 md:px-6 py-4 max-w-5xl">
        <table className="w-full text-xs border-separate border-spacing-0">
          <thead>
            <tr className="text-fg-muted">
              <th className="text-left font-normal px-2.5 py-1.5 border-b border-surface-line w-[22%]">projekt</th>
              <th className="text-left font-normal px-2.5 py-1.5 border-b border-surface-line w-[24%]">agent</th>
              <th className="text-left font-normal px-2.5 py-1.5 border-b border-surface-line w-[22%]">ág</th>
              <th className="text-left font-normal px-2.5 py-1.5 border-b border-surface-line w-[18%]">állapot</th>
              <th className="text-right font-normal px-2.5 py-1.5 border-b border-surface-line w-[7%]">mozgás</th>
              <th className="text-right font-normal px-2.5 py-1.5 border-b border-surface-line w-[7%]">pid</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ agent, project, first }) => (
              <tr
                key={agent.pid}
                className={first ? 'border-t border-surface-line' : ''}
              >
                <td className={`px-2.5 py-1 align-top ${first ? 'pt-2' : ''}`}>
                  {first && (
                    <span className="text-fg-strong">
                      {project.name}
                      <span className="ml-1.5 text-fg-muted tabular-nums">{project.agents.length}</span>
                      {!project.sources.includes('registry') && (
                        <span
                          className="ml-1.5 text-fg-muted"
                          title="Csak élő processzből ismert — nincs a projekt-registryben"
                        >
                          ·nem reg.
                        </span>
                      )}
                    </span>
                  )}
                </td>
                <td className={`px-2.5 py-1 text-fg-strong truncate ${first ? 'pt-2' : ''}`}>
                  {agent.name ?? <span className="text-fg-muted">névtelen</span>}
                  {/* A binding that was guessed rather than recorded must say so
                      wherever it is shown. There is no guessing path today, so
                      this marker should never appear — which is why it is here
                      rather than assumed away. */}
                  {!agent.binding_confirmed && (
                    <span className="ml-1.5 text-amber-400" title="A naplóhoz kötés nem rekordból származik">?</span>
                  )}
                </td>
                <td className={`px-2.5 py-1 text-fg-muted font-mono truncate ${first ? 'pt-2' : ''}`}>
                  {agent.branch ?? '—'}
                </td>
                <td className={`px-2.5 py-1 ${first ? 'pt-2' : ''}`}><StateCell agent={agent} /></td>
                <td className={`px-2.5 py-1 text-right text-fg-muted tabular-nums ${first ? 'pt-2' : ''}`}>
                  {age(agent.last_movement_seconds)}
                </td>
                <td className={`px-2.5 py-1 text-right text-fg-muted tabular-nums ${first ? 'pt-2' : ''}`}>
                  {agent.pid}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {empty.length > 0 && (
          <details className="mt-5">
            <summary className="text-xs text-fg-muted cursor-pointer">
              {empty.length} regisztrált projekt, amelyben most nem fut agent
            </summary>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {empty.map(p => (
                <Link
                  key={p.root}
                  to={`/p/${encodeURIComponent(p.name)}/status`}
                  className="text-xs px-2 py-0.5 rounded border border-surface-line text-fg-muted hover:text-fg-strong"
                >
                  {p.name}
                </Link>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  )
}
