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
 *
 * This is now the LANDING screen (task 7.10), which changes what the empty and
 * degraded states cost: they are the first thing a reader sees, not an edge
 * case. Hence the three-way discovery phase below (task 7.11) — *looking*,
 * *answered and empty*, and *answered* are three different screens, and a
 * failed refresh keeps the last measurement while saying how old it is rather
 * than replacing a true screen with an error.
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

/** The calendar day of a turn, or '' when it has no usable timestamp. */
function dayKey(ts: string | null): string {
  if (!ts) return ''
  const d = new Date(ts)
  return isNaN(d.getTime()) ? '' : d.toLocaleDateString('hu-HU')
}

function dayLabel(ts: string | null): string {
  if (!ts) return ''
  const d = new Date(ts)
  if (isNaN(d.getTime())) return ''
  const today = new Date()
  const y = new Date(today); y.setDate(y.getDate() - 1)
  if (d.toDateString() === today.toDateString()) return 'ma'
  if (d.toDateString() === y.toDateString()) return 'tegnap'
  return d.toLocaleDateString('hu-HU', { month: '2-digit', day: '2-digit' })
}

function StateLine({ agent }: { agent: FleetAgent }) {
  if (agent.state === 'working') {
    return (
      <span className="inline-flex items-center gap-1.5 text-emerald-400 whitespace-nowrap">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
        <span>{agent.tool ?? 'dolgozik'}</span>
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

/**
 * The tabs of the log view — task 7.12.
 *
 * Design §5.8 chose the raw conversation over the existing activity timeline,
 * on the ground that they answer different questions and the timeline can be
 * added later "without disturbing this". Leaving room for it means this list,
 * not a second component: adding the timeline is one entry with `view` filled
 * in, and the strip below already renders the selection.
 *
 * The timeline entry is rendered as a DISABLED tab that says so in its own
 * label — not a clickable tab that opens onto nothing, and not silence. A
 * control with nothing behind it is the shape task 8.2 forbids for the
 * terminal, and the reason is the same here: the reader must be able to tell
 * "not built" from "nothing to show".
 */
const LOG_TABS: { id: string; label: string; absent?: string }[] = [
  { id: 'conversation', label: 'beszélgetés' },
  {
    id: 'timeline',
    label: 'idővonal',
    absent: 'a meglévő idővonal-nézet ide fog kerülni; ez a fül a helyét tartja fenn, tartalma még nincs (7.12)',
  },
]

function LogPanel({ pid, onClose, tall }: { pid: number; onClose: () => void; tall?: boolean }) {
  const [log, setLog] = useState<LogResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showThinking, setShowThinking] = useState(false)

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

  // Counted from the turns, not from a flag: the toggle below must never
  // announce a hidden thing that is not there (false absence), nor stay silent
  // about one that is.
  const thinkingTurns = log?.turns.filter(t => t.thinking).length ?? 0

  return (
    <div className="border-t border-surface-line mt-3 pt-2">
      <div className="flex items-baseline gap-2 mb-1.5 flex-wrap" role="tablist" aria-label="napló nézetek">
        {LOG_TABS.map(tab => (
          tab.absent ? (
            <span
              key={tab.id}
              role="tab"
              aria-disabled="true"
              aria-selected="false"
              data-log-tab={tab.id}
              title={tab.absent}
              className="text-xs text-fg-ghost cursor-not-allowed"
            >
              {tab.label} <span className="text-fg-ghost">(még nincs)</span>
            </span>
          ) : (
            <span
              key={tab.id}
              role="tab"
              aria-selected="true"
              data-log-tab={tab.id}
              className="text-xs text-fg-strong border-b border-fg-strong"
            >
              {tab.label}
            </span>
          )
        ))}
        {log?.truncated && (
          <span className="text-xs text-fg-muted tabular-nums">
            az utolsó {log.turns.length} a {log.total_read}-ből
          </span>
        )}
        {thinkingTurns > 0 && (
          <button
            onClick={() => setShowThinking(v => !v)}
            className="text-xs text-fg-muted hover:text-fg-strong underline-offset-2 hover:underline tabular-nums"
            title="A gondolatmenet a naplóban benne van; alapból nem jelenik meg, hogy a beszélgetés olvasható maradjon."
          >
            {showThinking ? 'gondolatmenet elrejtése' : `gondolatmenet (${thinkingTurns})`}
          </button>
        )}
        <button onClick={onClose} className="ml-auto text-xs text-fg-muted hover:text-fg-strong">bezár</button>
      </div>
      {error && <div className="text-xs text-red-400">nem olvasható: {error}</div>}
      {/* A problem is not an empty conversation, and the two must not look alike. */}
      {log?.problem && <div className="text-xs text-amber-400">{log.problem}</div>}
      {log && !log.problem && log.turns.length === 0 && (
        <div className="text-xs text-fg-muted">a napló olvasható, de nem tartalmaz beszélgetést</div>
      )}
      {!log && !error && <div className="text-xs text-fg-muted">napló olvasása…</div>}
      <div className={`${tall ? 'max-h-[55vh]' : 'max-h-80'} overflow-y-auto space-y-1.5 pr-1`}>
        {log?.turns.map((t, i, all) => {
        // A day divider, because HH:MM alone made a 60-hour gap look like a
        // minute. Measured 2026-08-18: forty turns of one session spanned three
        // calendar days, and the clock column rendered 00:04 next to 10:46 with
        // nothing between them — the reader's honest conclusion from that is a
        // session that has been busy all morning. Same false-value class as the
        // rest of this screen, arriving through a field that looked like data.
        const prevDay = i > 0 ? dayKey(all[i - 1].timestamp) : ''
        const thisDay = dayKey(t.timestamp)
        const newDay = thisDay !== '' && thisDay !== prevDay
        return (
          <div key={i} className="text-xs">
            {newDay && (
              <div className="flex items-center gap-2 mt-2 mb-1 first:mt-0">
                <span className="text-fg-ghost tabular-nums shrink-0">{dayLabel(t.timestamp)}</span>
                <span className="flex-1 border-t border-surface-line" />
              </div>
            )}
            <div className="flex items-baseline gap-2">
              <span className={`shrink-0 tabular-nums ${t.role === 'user' ? 'text-sky-400' : 'text-fg-muted'}`}>
                {t.role === 'user' ? 'te' : t.role === 'assistant' ? 'agent' : t.role}
              </span>
              <span className="text-fg-ghost tabular-nums shrink-0">{clock(t.timestamp)}</span>
              {t.tools.length > 0 && (
                <span className="text-emerald-400/80 shrink-0">
                  {t.tools.map(x => x.name).filter(Boolean).join(' ')}
                </span>
              )}
              {t.results > 0 && <span className="text-fg-ghost shrink-0">↩{t.results}</span>}
            </div>
            {showThinking && t.thinking && (
              <div className="text-fg-ghost italic whitespace-pre-wrap break-words mt-0.5 pl-1 border-l border-surface-line/60">
                {t.thinking.length > 600 ? t.thinking.slice(0, 600) + ' …' : t.thinking}
              </div>
            )}
            {t.text && (
              <div className="text-fg-normal whitespace-pre-wrap break-words mt-0.5 pl-1 border-l border-surface-line">
                {t.text.length > 600 ? t.text.slice(0, 600) + ' …' : t.text}
              </div>
            )}
          </div>
        )})}
      </div>
    </div>
  )
}

/**
 * One agent as a single-line row — task 7.4.
 *
 * While another tile is enlarged, every other agent stays visible as one of
 * these. Rows rather than nothing, because hiding the others would put a stuck
 * agent behind a screen that looks calm — the one thing `ui-quality.md` puts
 * above the rest. So the row carries the two things that make choosing which
 * agent to open a decision rather than a guess: its state, and what it is
 * doing. `StateLine` is the same component the card uses, so a state cannot
 * read one way enlarged and another way collapsed.
 */
function AgentRow({ agent, onSelect }: { agent: FleetAgent; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      data-fleet-row={agent.pid}
      title="Kattints: ez a tábla nagyítódik ki"
      className="w-full text-left flex items-baseline gap-2 px-3 py-1 rounded border border-transparent hover:border-surface-line hover:bg-surface-raised/40 transition-colors"
    >
      <span className="text-xs text-fg-strong truncate max-w-[14rem] shrink-0">
        {agent.name ?? <span className="text-fg-muted">névtelen</span>}
        {!agent.binding_confirmed && (
          <span className="ml-1 text-amber-400" title="A naplóhoz kötés nem rekordból származik">?</span>
        )}
      </span>
      <span className="text-xs shrink-0"><StateLine agent={agent} /></span>
      <span className="text-xs text-fg-muted truncate min-w-0">{agent.branch ?? '—'}</span>
      <span className="ml-auto text-xs text-fg-ghost tabular-nums shrink-0">
        {age(agent.last_movement_seconds)} · {agent.pid}
      </span>
    </button>
  )
}

function AgentCard({ agent, open, onToggle, enlarged }: {
  agent: FleetAgent
  open: boolean
  onToggle: () => void
  enlarged?: boolean
}) {
  return (
    <div
      data-fleet-enlarged={enlarged ? agent.pid : undefined}
      className={`border rounded px-3 py-2 ${enlarged ? 'border-surface-line bg-surface-raised/30' : 'border-surface-line'}`}
    >
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
        <span className="text-xs text-fg-muted truncate">{agent.branch ?? '—'}</span>
        <span className="ml-auto text-xs text-fg-ghost tabular-nums shrink-0">
          {age(agent.last_movement_seconds)} · {agent.pid}
        </span>
      </div>

      <div className="flex items-center gap-3 mt-1.5">
        <button
          onClick={onToggle}
          className="text-xs text-fg-muted hover:text-fg-strong underline-offset-2 hover:underline"
        >
          {open ? 'vissza a rácshoz' : 'napló megnyitása'}
        </button>
        {/* Stated, not silently missing. Task 5.2 forbids reporting a terminal for
            a session the framework does not own, and every session listed here was
            started by a person in their own terminal. */}
        <span className="text-xs text-fg-ghost" title="Futó, idegen munkamenethez a keret nem csatolhat terminált (mérve 2026-08-17 és 2026-08-18)">
          terminál: nem a kereté
        </span>
      </div>

      {open && <LogPanel pid={agent.pid} onClose={onToggle} tall={enlarged} />}
    </div>
  )
}

/**
 * The state before discovery has answered — task 7.11, first half.
 *
 * The whole change exists because the previous landing screen reported absence
 * it had not measured. A screen that paints "no agents" during its first second
 * reproduces that defect at the place every reader arrives first, so this says
 * what is true — the question is out, the answer is not back — and shows no
 * count at all. A gap is not a zero.
 */
function Looking() {
  return (
    <div className="p-6 max-w-2xl" data-fleet-phase="looking">
      <div className="flex items-center gap-2 text-sm text-sky-400">
        <span className="w-2 h-2 rounded-full bg-sky-400 animate-pulse shrink-0" />
        Agentek keresése…
      </div>
      <p className="mt-2 text-xs text-fg-muted leading-relaxed">
        A felderítés még nem válaszolt. Ez <span className="text-fg-strong">nem</span> azt jelenti, hogy nem fut
        agent — amíg a mérés meg nem érkezik, a képernyő nem állít se számot, se ürességet.
      </p>
    </div>
  )
}

/**
 * The state after discovery answered and there genuinely is nothing — task
 * 7.11, second half.
 *
 * This must not look like the panel above, and the difference cannot rest on a
 * spinner that a reader may or may not catch: this one is a *result*, so it is
 * phrased as one, and it carries the time it was measured and what was
 * searched. Two screens that both read "nothing here" for opposite reasons are
 * the false-absence class arriving through the layout instead of through a
 * field.
 */
function AnsweredEmpty({ at, projects }: { at: number | null; projects: number }) {
  return (
    <div className="p-6 max-w-2xl" data-fleet-phase="answered-empty">
      <div className="flex items-center gap-2 text-sm text-fg-strong">
        <span className="w-2 h-2 rounded-full bg-surface-line shrink-0" />
        A felderítés lefutott: egyetlen agent sem fut.
      </div>
      <p className="mt-2 text-xs text-fg-muted leading-relaxed tabular-nums">
        Mérve {at ? new Date(at).toLocaleTimeString('hu-HU') : '—'}-kor, {projects} ismert projekt felett.
        Ez mért eredmény, nem betöltés alatt álló képernyő.
      </p>
    </div>
  )
}

export default function Fleet() {
  const [data, setData] = useState<FleetResponse | null>(null)
  const [answeredAt, setAnsweredAt] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [enlargedPid, setEnlargedPid] = useState<number | null>(null)

  const load = useCallback(() => {
    fetch('/api/fleet/agents')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(d => { setData(d); setAnsweredAt(Date.now()); setError(null) })
      .catch(e => setError(String(e.message ?? e)))
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [load])

  // Discovery has never answered. An error here is the real thing — there is no
  // measurement to fall back on — so it replaces the screen.
  if (!data) {
    if (error) {
      return (
        <div className="p-6 max-w-2xl" data-fleet-phase="unreachable">
          <div className="text-sm text-red-400">A flotta nem olvasható: {error}</div>
          <p className="mt-2 text-xs text-fg-muted">
            A felderítés egyszer sem válaszolt, tehát a képernyő semmit nem tud a futó agentekről —
            ez nem azonos azzal, hogy nincs egy sem.
          </p>
        </div>
      )
    }
    return <Looking />
  }

  const populated = data.projects.filter(p => p.agents.length > 0 && !p.archived)
  const empty = data.projects.filter(p => p.agents.length === 0 && !p.archived)
  const active = populated.find(p => p.root === selected) ?? populated[0] ?? null
  // A remembered enlargement never determines what is shown: if that agent is
  // gone from the answer, the grid comes back rather than an empty big tile.
  const enlarged = active?.agents.some(a => a.pid === enlargedPid) ? enlargedPid : null

  return (
    <div className="h-full flex flex-col" data-fleet-phase={data.agents === 0 ? 'answered-empty' : 'answered'}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 md:px-6 py-2.5 border-b border-surface-line shrink-0">
        <span className="text-sm font-semibold text-fg-loud">Flotta</span>
        <span className="text-xs text-fg-muted tabular-nums">{data.agents} agent · {populated.length} projekt</span>
        {data.working > 0 && <span className="text-xs text-emerald-400 tabular-nums">{data.working} dolgozik</span>}
        {data.unknown > 0 && <span className="text-xs text-amber-400 tabular-nums">{data.unknown} ismeretlen</span>}
        {/* The caveat explains a state; with nothing in that state it is noise
            at the top of the landing screen. Rendered from the data, so it can
            never explain away a screen that has no agents on it. */}
        {data.agents > 0 && (
          <span className="text-xs text-fg-muted">
            a <span className="text-fg-strong">csendes</span> nem azt jelenti, hogy nem történik semmi — csak azt,
            hogy a napló legutóbbi kiírásakor nem volt nyitott eszközhívás
          </span>
        )}
        {/* A refresh that failed after a good answer keeps the answer — and says
            how old it is. Replacing a true screen with an error would trade a
            stale measurement for no measurement, which is the worse of the two
            on the landing screen. */}
        {error && (
          <span className="ml-auto text-xs text-amber-400" title={error}>
            a frissítés nem sikerült — az adat {answeredAt ? new Date(answeredAt).toLocaleTimeString('hu-HU') : '—'}-kor
            {' '}mért állapot
          </span>
        )}
      </div>

      {data.agents === 0 ? (
        <AnsweredEmpty at={answeredAt} projects={data.projects.length} />
      ) : (
      <div className="flex-1 flex min-h-0">
        <div className="w-56 shrink-0 border-r border-surface-line overflow-y-auto p-2 space-y-0.5">
          {populated.map(p => (
            <ProjectTile
              key={p.root}
              project={p}
              active={active?.root === p.root}
              onSelect={() => { setSelected(p.root); setEnlargedPid(null) }}
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
                <span className="text-xs text-fg-ghost truncate">{active.root}</span>
                {enlarged !== null && active.agents.length > 1 && (
                  <span className="ml-auto text-xs text-fg-ghost shrink-0 tabular-nums">
                    {active.agents.length - 1} sorként — kattints egyre a váltáshoz
                  </span>
                )}
              </div>
              {/* Task 7.4 — the enlarged tile stays in the list's own order, and
                  every other agent keeps a row. Rendering the enlarged one in
                  place (rather than lifting it to the top) is what makes a row
                  the way back: the agent you clicked is where you clicked. */}
              {active.agents.map(a => (
                a.pid === enlarged ? (
                  <AgentCard
                    key={a.pid}
                    agent={a}
                    enlarged
                    open
                    onToggle={() => setEnlargedPid(null)}
                  />
                ) : enlarged !== null ? (
                  <AgentRow key={a.pid} agent={a} onSelect={() => setEnlargedPid(a.pid)} />
                ) : (
                  <AgentCard
                    key={a.pid}
                    agent={a}
                    open={false}
                    onToggle={() => setEnlargedPid(a.pid)}
                  />
                )
              ))}
            </>
          ) : (
            <div className="text-sm text-fg-muted">
              Van futó agent, de egyik ismert projekthez sem sikerült kötni.
            </div>
          )}
        </div>
      </div>
      )}
    </div>
  )
}
