import { useEffect, useState, useCallback } from 'react'

/**
 * Fleet — every agent session running on this machine.
 *
 * Two panels (task 7.1): projects on the left, the selected project's agents on
 * the right, selection without a further navigation. Cards here rather than the
 * one flat table the first draft used, because the two levels answer different
 * questions — a project is a thing you pick, an agent is a thing you read.
 *
 * Three rules this screen is shaped by, all of them measured rather than assumed:
 *
 *  - **A project tile carries enough state to be judged without selecting it**
 *    (task 7.2). Compacting must never hide a failure: if an agent inside a
 *    collapsed project is in an undetermined state, the tile says so.
 *  - **`quiet` is never rendered as "idle"** nor given a calm colour. Measured
 *    2026-08-18: the runtime flushes a turn's entries to the session log in
 *    batches, and a log was observed ~25s stale while its session was actively
 *    working. `quiet` means "no outstanding tool call as of the last flush".
 *  - **There is no terminal here, and that is a measurement, not an omission.**
 *    Task 5.2 forbids reporting a terminal for a session the framework does not
 *    own, and adoption of a running session was measured to fail twice over
 *    (resume forks the conversation; the cross-session channel reaches but does
 *    not attach). So the tile offers the log — which every agent has, through a
 *    recorded binding — and a terminal will appear only for agents set-core
 *    starts itself.
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

interface Turn {
  role: string
  timestamp: string | null
  text: string
  thinking: string
  tools: { name: string | null; id: string | null }[]
  results: number
  sidechain: boolean
}

interface LogResponse {
  turns: Turn[]
  total_read?: number
  truncated?: boolean
  problem?: string
  pid?: number
  name?: string | null
}

function age(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 90) return `${Math.round(seconds)}mp`
  if (seconds < 5400) return `${Math.round(seconds / 60)}p`
  return `${Math.round(seconds / 3600)}ó`
}

function clock(ts: string | null): string {
  if (!ts) return ''
  const d = new Date(ts)
  return isNaN(d.getTime()) ? '' : d.toLocaleTimeString('hu-HU', { hour: '2-digit', minute: '2-digit' })
}

function StateLine({ agent }: { agent: FleetAgent }) {
  if (agent.state === 'working') {
    return (
      <span className="inline-flex items-center gap-1.5 text-emerald-400 whitespace-nowrap">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
        <span className="font-mono">{agent.tool ?? 'dolgozik'}</span>
        {agent.tool_elapsed_seconds !== null && (
          <span className="text-fg-muted tabular-nums">{age(agent.tool_elapsed_seconds)}</span>
        )}
        {agent.other_tools.length > 0 && <span className="text-fg-muted">+{agent.other_tools.length}</span>}
      </span>
    )
  }
  if (agent.state === 'unknown') {
    return (
      <span className="inline-flex items-center gap-1.5 text-amber-400 whitespace-nowrap" title={agent.unknown_reason ?? ''}>
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

function ProjectTile({ project, active, onSelect }: {
  project: FleetProject
  active: boolean
  onSelect: () => void
}) {
  const working = project.agents.filter(a => a.state === 'working').length
  const unknown = project.agents.filter(a => a.state === 'unknown').length
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left px-3 py-2 rounded border transition-colors ${
        active
          ? 'border-surface-line bg-surface-raised text-fg-loud'
          : 'border-transparent hover:bg-surface-raised/50 text-fg-strong'
      }`}
    >
      <div className="flex items-baseline gap-2">
        <span className="text-sm truncate flex-1">{project.name}</span>
        <span className="text-xs text-fg-muted tabular-nums shrink-0">{project.agents.length}</span>
      </div>
      {/* Task 7.2 — state visible WITHOUT selecting the project. A tab that hides
          something wrong is the failure this whole screen is built against, so
          the counts that matter are printed on the closed tile. */}
      <div className="flex items-center gap-2.5 mt-0.5 text-xs">
        {working > 0 && (
          <span className="inline-flex items-center gap-1 text-emerald-400 tabular-nums">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />{working}
          </span>
        )}
        {unknown > 0 && (
          <span className="inline-flex items-center gap-1 text-amber-400 tabular-nums">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />{unknown}
          </span>
        )}
        {working === 0 && unknown === 0 && <span className="text-fg-ghost">csendes</span>}
        {!project.sources.includes('registry') && (
          <span className="text-fg-ghost ml-auto" title="Csak élő processzből ismert — nincs a projekt-registryben">
            nem reg.
          </span>
        )}
      </div>
    </button>
  )
}

function LogPanel({ pid, onClose }: { pid: number; onClose: () => void }) {
  const [log, setLog] = useState<LogResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = () => {
      fetch(`/api/fleet/agents/${pid}/log?limit=40`)
        .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then(d => { if (!cancelled) { setLog(d); setError(null) } })
        .catch(e => { if (!cancelled) setError(String(e.message ?? e)) })
    }
    load()
    const t = setInterval(load, 5000)
    return () => { cancelled = true; clearInterval(t) }
  }, [pid])

  return (
    <div className="border-t border-surface-line mt-3 pt-2">
      <div className="flex items-baseline gap-2 mb-1.5">
        <span className="text-xs text-fg-strong">beszélgetés</span>
        {log?.truncated && (
          <span className="text-xs text-fg-muted tabular-nums">
            az utolsó {log.turns.length} a {log.total_read}-ből
          </span>
        )}
        <button onClick={onClose} className="ml-auto text-xs text-fg-muted hover:text-fg-strong">bezár</button>
      </div>
      {error && <div className="text-xs text-red-400">nem olvasható: {error}</div>}
      {/* A problem is not an empty conversation, and the two must not look alike. */}
      {log?.problem && <div className="text-xs text-amber-400">{log.problem}</div>}
      {log && !log.problem && log.turns.length === 0 && (
        <div className="text-xs text-fg-muted">a napló olvasható, de nem tartalmaz beszélgetést</div>
      )}
      <div className="max-h-80 overflow-y-auto space-y-1.5 pr-1">
        {log?.turns.map((t, i) => (
          <div key={i} className="text-xs">
            <div className="flex items-baseline gap-2">
              <span className={`shrink-0 tabular-nums ${t.role === 'user' ? 'text-sky-400' : 'text-fg-muted'}`}>
                {t.role === 'user' ? 'te' : t.role === 'assistant' ? 'agent' : t.role}
              </span>
              <span className="text-fg-ghost tabular-nums shrink-0">{clock(t.timestamp)}</span>
              {t.tools.length > 0 && (
                <span className="font-mono text-emerald-400/80 shrink-0">
                  {t.tools.map(x => x.name).filter(Boolean).join(' ')}
                </span>
              )}
              {t.results > 0 && <span className="text-fg-ghost shrink-0">↩{t.results}</span>}
            </div>
            {t.text && (
              <div className="text-fg-normal whitespace-pre-wrap break-words mt-0.5 pl-1 border-l border-surface-line">
                {t.text.length > 600 ? t.text.slice(0, 600) + ' …' : t.text}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function AgentCard({ agent, open, onToggle }: {
  agent: FleetAgent
  open: boolean
  onToggle: () => void
}) {
  return (
    <div className="border border-surface-line rounded px-3 py-2">
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-sm text-fg-strong">
          {agent.name ?? <span className="text-fg-muted">névtelen</span>}
          {/* No guessing path exists today, so this marker should never appear —
              which is exactly why it is rendered rather than assumed away. */}
          {!agent.binding_confirmed && (
            <span className="ml-1.5 text-amber-400" title="A naplóhoz kötés nem rekordból származik">?</span>
          )}
        </span>
        <StateLine agent={agent} />
        <span className="text-xs text-fg-muted font-mono truncate">{agent.branch ?? '—'}</span>
        <span className="ml-auto text-xs text-fg-ghost tabular-nums shrink-0">
          {age(agent.last_movement_seconds)} · {agent.pid}
        </span>
      </div>

      <div className="flex items-center gap-3 mt-1.5">
        <button
          onClick={onToggle}
          className="text-xs text-fg-muted hover:text-fg-strong underline-offset-2 hover:underline"
        >
          {open ? 'napló elrejtése' : 'napló megnyitása'}
        </button>
        {/* Stated, not silently missing. Task 5.2 forbids reporting a terminal for
            a session the framework does not own, and every session listed here was
            started by a person in their own terminal. */}
        <span className="text-xs text-fg-ghost" title="Futó, idegen munkamenethez a keret nem csatolhat terminált (mérve 2026-08-17 és 2026-08-18)">
          terminál: nem a kereté
        </span>
      </div>

      {open && <LogPanel pid={agent.pid} onClose={onToggle} />}
    </div>
  )
}

export default function Fleet() {
  const [data, setData] = useState<FleetResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [openPid, setOpenPid] = useState<number | null>(null)

  const load = useCallback(() => {
    fetch('/api/fleet/agents')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(d => { setData(d); setError(null) })
      .catch(e => setError(String(e.message ?? e)))
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [load])

  if (error) {
    return <div className="p-6 text-sm text-red-400">A flotta nem olvasható: {error}</div>
  }
  // Task 7.11 — the pre-answer state says it is looking. Never an empty fleet,
  // never a zero: both are answers, and no answer has arrived yet.
  if (!data) {
    return <div className="p-6 text-sm text-fg-muted">Agentek keresése…</div>
  }

  const populated = data.projects.filter(p => p.agents.length > 0 && !p.archived)
  const empty = data.projects.filter(p => p.agents.length === 0 && !p.archived)
  const active = populated.find(p => p.root === selected) ?? populated[0] ?? null

  return (
    <div className="h-full flex flex-col">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 md:px-6 py-2.5 border-b border-surface-line shrink-0">
        <span className="text-sm font-semibold text-fg-loud">Flotta</span>
        <span className="text-xs text-fg-muted tabular-nums">{data.agents} agent · {populated.length} projekt</span>
        {data.working > 0 && <span className="text-xs text-emerald-400 tabular-nums">{data.working} dolgozik</span>}
        {data.unknown > 0 && <span className="text-xs text-amber-400 tabular-nums">{data.unknown} ismeretlen</span>}
        <span className="text-xs text-fg-muted">
          a <span className="text-fg-strong">csendes</span> nem azt jelenti, hogy nem történik semmi — csak azt,
          hogy a napló legutóbbi kiírásakor nem volt nyitott eszközhívás
        </span>
      </div>

      <div className="flex-1 flex min-h-0">
        <div className="w-56 shrink-0 border-r border-surface-line overflow-y-auto p-2 space-y-0.5">
          {populated.map(p => (
            <ProjectTile
              key={p.root}
              project={p}
              active={active?.root === p.root}
              onSelect={() => { setSelected(p.root); setOpenPid(null) }}
            />
          ))}
          {empty.length > 0 && (
            <details className="mt-3 px-3">
              <summary className="text-xs text-fg-ghost cursor-pointer">
                {empty.length} agent nélkül
              </summary>
              <div className="mt-1.5 space-y-0.5">
                {empty.map(p => (
                  <div key={p.root} className="text-xs text-fg-ghost truncate">{p.name}</div>
                ))}
              </div>
            </details>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2 min-w-0">
          {active ? (
            <>
              <div className="flex items-baseline gap-2 px-0.5">
                <span className="text-sm text-fg-loud">{active.name}</span>
                <span className="text-xs text-fg-muted tabular-nums">{active.agents.length} agent</span>
                <span className="text-xs text-fg-ghost font-mono truncate">{active.root}</span>
              </div>
              {active.agents.map(a => (
                <AgentCard
                  key={a.pid}
                  agent={a}
                  open={openPid === a.pid}
                  onToggle={() => setOpenPid(openPid === a.pid ? null : a.pid)}
                />
              ))}
            </>
          ) : (
            <div className="text-sm text-fg-muted">Nem fut agent egyetlen projektben sem.</div>
          )}
        </div>
      </div>
    </div>
  )
}
