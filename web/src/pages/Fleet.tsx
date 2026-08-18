import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

/**
 * Fleet — every agent session running on this machine.
 *
 * A table rather than cards, because the rows are comparable: same fields,
 * asked the same question. Grouped by project because that is the unit someone
 * navigates by.
 *
 * Two things are deliberately loud rather than tidy:
 *
 *  - `quiet` is never rendered as "idle" or with a calm colour. Measured
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

function age(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 90) return `${Math.round(seconds)}s`
  if (seconds < 5400) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

function StateCell({ agent }: { agent: FleetAgent }) {
  if (agent.state === 'working') {
    return (
      <span className="inline-flex items-center gap-1.5 text-emerald-400">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        {agent.tool ?? 'working'}
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
      <span className="inline-flex items-center gap-1.5 text-amber-400" title={agent.unknown_reason ?? ''}>
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
        unknown
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-fg-muted">
      <span className="w-1.5 h-1.5 rounded-full bg-surface-line" />
      quiet
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
    return (
      <div className="p-6">
        <div className="text-sm text-red-400">A flotta nem olvasható: {error}</div>
      </div>
    )
  }
  if (!data) {
    return <div className="p-6 text-sm text-fg-muted">Betöltés…</div>
  }

  const populated = data.projects.filter(p => p.agents.length > 0 && !p.archived)
  const empty = data.projects.filter(p => p.agents.length === 0 && !p.archived)

  return (
    <div className="p-4 md:p-6 max-w-6xl">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 mb-1">
        <h1 className="text-lg font-semibold text-fg-loud">Flotta</h1>
        <span className="text-sm text-fg-muted tabular-nums">
          {data.agents} agent · {populated.length} projekt
        </span>
        {data.working > 0 && (
          <span className="text-sm text-emerald-400 tabular-nums">{data.working} dolgozik</span>
        )}
        {/* A gap is not a zero: the unknown count sits next to the total, not
            inside a panel someone has to open. */}
        {data.unknown > 0 && (
          <span className="text-sm text-amber-400 tabular-nums">{data.unknown} ismeretlen</span>
        )}
      </div>

      <p className="text-xs text-fg-muted mb-5">
        A <span className="text-fg-strong">quiet</span> nem azt jelenti, hogy nem történik semmi:{' '}
        {data.quiet_means}.
      </p>

      {populated.map(project => (
        <section key={project.root} className="mb-6">
          <div className="flex items-baseline gap-2 mb-1.5">
            <h2 className="text-sm font-medium text-fg-strong">{project.name}</h2>
            <span className="text-xs text-fg-muted tabular-nums">{project.agents.length}</span>
            {!project.sources.includes('registry') && (
              <span className="text-xs text-fg-muted" title="Csak élő processzből ismert — nincs a projekt-registryben">
                nincs regisztrálva
              </span>
            )}
          </div>

          <div className="overflow-x-auto border border-surface-line rounded">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-fg-muted border-b border-surface-line">
                  <th className="text-left font-normal px-2.5 py-1.5">agent</th>
                  <th className="text-left font-normal px-2.5 py-1.5">ág</th>
                  <th className="text-left font-normal px-2.5 py-1.5">állapot</th>
                  <th className="text-right font-normal px-2.5 py-1.5">mozgás</th>
                  <th className="text-right font-normal px-2.5 py-1.5">pid</th>
                </tr>
              </thead>
              <tbody>
                {project.agents.map(agent => (
                  <tr key={agent.pid} className="border-b border-surface-line/50 last:border-0">
                    <td className="px-2.5 py-1.5 text-fg-strong">
                      {agent.name ?? <span className="text-fg-muted">névtelen</span>}
                      {/* A binding that was guessed rather than recorded must say
                          so wherever it is shown. There is no guessing path today,
                          so this marker should never appear — which is exactly why
                          it is here rather than assumed. */}
                      {!agent.binding_confirmed && (
                        <span className="ml-1.5 text-amber-400" title="A naplóhoz kötés nem rekordból származik">
                          ?
                        </span>
                      )}
                    </td>
                    <td className="px-2.5 py-1.5 text-fg-muted font-mono">{agent.branch ?? '—'}</td>
                    <td className="px-2.5 py-1.5"><StateCell agent={agent} /></td>
                    <td className="px-2.5 py-1.5 text-right text-fg-muted tabular-nums">
                      {age(agent.last_movement_seconds)}
                    </td>
                    <td className="px-2.5 py-1.5 text-right text-fg-muted tabular-nums">{agent.pid}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}

      {empty.length > 0 && (
        <details className="mt-6">
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
  )
}
