import { useEffect, useState, useCallback, useMemo } from 'react'

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
 *  - **A terminal is offered exactly where one can exist, and where it cannot
 *    the tile says why** (task 8.2). The producer carries `population` as a
 *    fact, with THREE values: `started-here` has a terminal, `foreign` cannot
 *    have one, and `unknown` means the owner service could not be asked. The
 *    third is not a shade of the second — see `lib/fleetTerminal.ts`, which
 *    holds that decision as a pure function so it can be asserted in both
 *    directions.
 *
 * This is now the LANDING screen (task 7.10), which changes what the empty and
 * degraded states cost: they are the first thing a reader sees, not an edge
 * case. Hence the three-way discovery phase below (task 7.11) — *looking*,
 * *answered and empty*, and *answered* are three different screens, and a
 * failed refresh keeps the last measurement while saying how old it is rather
 * than replacing a true screen with an error.
 */

import FleetProjectColumn from '../components/FleetProjectColumn'
import FleetTerminal from '../components/FleetTerminal'
import { COLUMN_CHOICES, readView, resolveColumns, resolveEnlarged, writeView } from '../lib/fleetViewState'
import type { ProjectView } from '../lib/fleetViewState'
import type { FleetAgent, FleetProject, FleetResponse } from '../lib/fleetTypes'
import { terminalOffer } from '../lib/fleetTerminal'

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
  // Waiting for a person (task 3.8). It reaches the tile through the same field
  // as every other state, and it is the loudest one on the screen because it is
  // the only one that is waiting for the reader.
  if (agent.state === 'waiting') {
    // `waiting_for` may be null — the runtime did not write down WHAT it is
    // waiting for. That is a gap in the reason, never a doubt about the state:
    // the agent is waiting either way, and softening the label because the
    // reason is missing would let the calmer reading win, which is the exact
    // trade this screen refuses everywhere else.
    const why = agent.waiting_for
    return (
      <span
        className="inline-flex items-center gap-1.5 text-sky-300 font-semibold whitespace-nowrap"
        title={why ?? 'A munkamenet emberi válaszra vár. Hogy mire, azt a futtatókörnyezet nem írta meg — az állapot ettől még mért.'}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-sky-300 shrink-0" />
        válaszra vár
        {why
          ? <span className="text-fg-muted font-normal truncate max-w-[16rem]">{why}</span>
          : <span className="text-fg-ghost font-normal">(mire, azt nem írta meg)</span>}
      </span>
    )
  }
  if (agent.state === 'quiet') {
    return (
      <span className="inline-flex items-center gap-1.5 text-fg-muted whitespace-nowrap">
        <span className="w-1.5 h-1.5 rounded-full bg-surface-line shrink-0" />
        csendes
      </span>
    )
  }
  // A state this screen does not know is printed AS ITSELF, never as `csendes`.
  // Measured 2026-08-19 on the live screen: a `waiting` agent rendered as quiet
  // through this fall-through, while the header two panels away counted it as
  // waiting — two fields contradicting each other, and the calmer one winning.
  // A default branch that names one state answers for every state that arrives
  // after it was written.
  return (
    <span className="inline-flex items-center gap-1.5 text-amber-400 whitespace-nowrap"
          title="A felderítés olyan állapotot jelentett, amit ez a képernyő még nem ismer — a neve látszik, jelentést nem tulajdonítunk neki.">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
      {agent.state}
    </span>
  )
}

/**
 * A state the record DECLARED that the log refuted — the `declaration_ignored`
 * field.
 *
 * The measurement already won: `state` holds the log's answer, and nothing
 * downstream needs this. Which is precisely why it is rendered. A contradiction
 * the surface never shows is one nobody ever fixes — it sits in the payload
 * being correct-but-unread, and the record that keeps lying about itself keeps
 * lying about itself. It is amber rather than red because nothing is broken for
 * the reader; it is a fact about the producer.
 */
function Contradiction({ agent, compact }: { agent: FleetAgent; compact?: boolean }) {
  const declared = agent.declaration_ignored
  if (typeof declared !== 'string' || declared === '') return null
  const explain =
    `A rekord „${declared}” állapotot deklarált, a napló ezt megcáfolta — a mérés (“${agent.state}”) nyer. ` +
    'Ez nem a képernyő hibája és nem is javítja el: a producer rekordja mond mást, mint a naplója.'
  return (
    <span
      data-fleet-conflict-agent={agent.pid}
      title={explain}
      className="inline-flex items-center gap-1 text-xs text-amber-400 whitespace-nowrap"
    >
      <span aria-hidden>⚠</span>
      {compact ? (
        <span className="sr-only">ellentmondó deklaráció</span>
      ) : (
        <span className="font-normal">
          deklarált: <span className="line-through">{declared}</span>
        </span>
      )}
    </span>
  )
}

/**
 * The terminal control on a tile — task 8.2, both halves.
 *
 * The offer exists only where a terminal can; where it cannot, the reason stands
 * in its place. And the three outcomes are three, not two: `unknown` says we
 * could not find out, in amber, and never "there is no terminal". The wording is
 * in `lib/fleetTerminal.ts` next to the decision, so the screen cannot say one
 * thing while the model decides another.
 */
function TerminalControl({ agent, ownerReachable, open, onToggle }: {
  agent: FleetAgent
  ownerReachable?: boolean
  open: boolean
  onToggle: () => void
}) {
  const offer = terminalOffer(agent, ownerReachable)
  if (offer.kind === 'available') {
    return (
      <button
        onClick={onToggle}
        data-fleet-terminal-open={offer.label}
        className="text-xs text-sky-300 hover:text-sky-200 underline-offset-2 hover:underline"
        title="A keret indította ezt az agentet és tartja a terminálját — a nézet bezárása nem állítja le."
      >
        {open ? 'terminál bezárása' : 'terminál megnyitása'}
      </button>
    )
  }
  return (
    <span
      data-fleet-terminal-absent={offer.kind}
      title={offer.reason}
      className={`text-xs ${offer.kind === 'unknown' ? 'text-amber-400' : 'text-fg-ghost'}`}
    >
      {offer.kind === 'unknown' ? 'terminál: nem tudjuk' : 'terminál: nem a kereté'}
    </span>
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
/**
 * Column counts as WHOLE class names, not built by interpolation.
 *
 * Tailwind scans the source for literal class strings; `grid-cols-${n}` is
 * invisible to that scan, so the class exists in the DOM and not in the CSS —
 * a layout that silently does not apply, which reads as "the grid does not
 * work" rather than as a build problem.
 */
const GRID_COLS: Record<number, string> = {
  1: 'grid-cols-1',
  2: 'grid-cols-1 md:grid-cols-2',
  3: 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3',
  4: 'grid-cols-1 md:grid-cols-2 xl:grid-cols-4',
}

/**
 * Who started this agent — task 7.8.
 *
 * Two sources, shown as two different claims rather than as one "parent",
 * because they answer different questions: the OWNER's note says who asked for
 * the start (a record, and the only thing that can answer for a
 * framework-started agent at all — those have the owner process as their
 * ancestor); the ancestry walk says who is above it in the process tree
 * (measured, and it survives when nothing was recorded). They can disagree, and
 * a screen that picked one silently would report the disagreement as a fact.
 */
function Lineage({ agent }: { agent: FleetAgent }) {
  const p = agent.parent
  if (!p) return null
  const recorded = p.source === 'recorded'
  // A pid with no session record has no seat name. Saying "unknown parent"
  // there would be a false absence — the relation IS known, only the name is
  // missing, so the pid stands in for it.
  const who = p.seat ?? (p.pid_without_seat != null ? `pid ${p.pid_without_seat}` : null)
  if (!who) return null
  return (
    <span
      data-fleet-parent={p.source}
      className="text-xs text-fg-ghost shrink-0"
      title={recorded
        ? 'A tulajdonos feljegyezte, ki kérte ennek az agentnek az indítását — rekord, nem következtetés.'
        : 'A processzfából mérve: ez az első agent-ős. Nem ugyanaz, mint aki kérte — a kettő eltérhet.'}
    >
      ← {who}
      <span className={recorded ? 'ml-1 text-fg-ghost' : 'ml-1 text-amber-400/70'}>
        {recorded ? 'feljegyezve' : 'processzfából'}
      </span>
    </span>
  )
}

function AgentRow({ agent, onSelect }: { agent: FleetAgent; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      data-fleet-row={agent.pid}
      title="Kattints: ez a tábla nagyítódik ki"
      className="w-full text-left flex items-baseline gap-2 px-3 py-1 rounded border border-transparent hover:border-surface-line hover:bg-surface-raised/40 transition-colors"
    >
      <span className="text-xs text-fg-strong truncate max-w-[14rem] shrink-0">
        {/* Same identity rule as the card — a row and a card must not name the
            same agent differently. */}
        {agent.terminal_label ?? agent.name ?? <span className="text-fg-muted">névtelen</span>}
        {!agent.binding_confirmed && (
          <span className="ml-1 text-amber-400" title="A naplóhoz kötés nem rekordból származik">?</span>
        )}
      </span>
      <span className="text-xs shrink-0"><StateLine agent={agent} /></span>
      {/* The contradiction rides on the ROW too, not only on the enlarged card:
          a row is where an agent sits while another tile is open, and a marker
          that only appears when you enlarge is a marker for something you
          already decided to look at. */}
      <Contradiction agent={agent} compact />
      <span className="text-xs text-fg-muted truncate min-w-0">{agent.branch ?? '—'}</span>
      <span className="ml-auto text-xs text-fg-ghost tabular-nums shrink-0">
        {age(agent.last_movement_seconds)} · {agent.pid}
      </span>
    </button>
  )
}

function AgentCard({ agent, open, onToggle, enlarged, ownerReachable, terminalOpen, onTerminal }: {
  agent: FleetAgent
  open: boolean
  onToggle: () => void
  enlarged?: boolean
  ownerReachable?: boolean
  /** Whether THIS agent's terminal is the one open. */
  terminalOpen: boolean
  onTerminal: (label: string | null) => void
}) {
  const offer = terminalOffer(agent, ownerReachable)
  return (
    <div
      data-fleet-enlarged={enlarged ? agent.pid : undefined}
      className={`border rounded px-3 py-2 ${enlarged ? 'border-surface-line bg-surface-raised/30' : 'border-surface-line'}`}
    >
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-sm text-fg-strong">
          {/* The name the OWNER gave it wins over the one derived from the
              session id. Measured 2026-08-19: the tile said `set-core-9a` for
              an agent the owner holds as `set-core-0906`, so matching a tile
              against `sac`/journal output meant translating between two names
              for one thing — the second-place defect, inside one screen. */}
          {agent.terminal_label ?? agent.name ?? <span className="text-fg-muted">névtelen</span>}
          {/* No guessing path exists today, so this marker should never appear —
              which is exactly why it is rendered rather than assumed away. */}
          {!agent.binding_confirmed && (
            <span className="ml-1.5 text-amber-400" title="A naplóhoz kötés nem rekordból származik">?</span>
          )}
        </span>
        <StateLine agent={agent} />
        <Contradiction agent={agent} />
        <Lineage agent={agent} />
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
        {/* Offered where it can exist, reasoned where it cannot — task 8.2. */}
        <TerminalControl
          agent={agent}
          ownerReachable={ownerReachable}
          open={terminalOpen}
          onToggle={() => onTerminal(terminalOpen ? null : (offer.kind === 'available' ? offer.label : null))}
        />
      </div>

      {open && <LogPanel pid={agent.pid} onClose={onToggle} tall={enlarged} />}
      {terminalOpen && offer.kind === 'available' && (
        <FleetTerminal label={offer.label} onClose={() => onTerminal(null)} />
      )}
    </div>
  )
}

/**
 * Starting an agent — task 8.3, first half.
 *
 * Two rules shape this, and both are about not offering what does not exist:
 *
 *  - **The owner is asked first.** `GET /api/fleet/owner` answers whether an
 *    agent can be started at all, and the answer carries the reason when it
 *    cannot. A button that is present and fails is worse than one that is absent
 *    with a reason beside it — the same rule the terminal control follows.
 *  - **The label is the user's, and it is what everything else addresses.** Stop
 *    and terminal both take a label, so it is prefilled rather than generated
 *    silently: a name the reader chose is one they can find again.
 *
 * The dashboard process never forks the agent itself — it asks the owner
 * service, whose whole reason to exist is that a process started from here would
 * join this service's control group and die with the next deploy.
 */
interface OwnerHealth { available: boolean; reason?: string; held?: number }

function StartAgent({ project, onStarted }: { project: FleetProject; onStarted: (label: string) => void }) {
  const [owner, setOwner] = useState<OwnerHealth | null>(null)
  const [open, setOpen] = useState(false)
  const [label, setLabel] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch('/api/fleet/owner')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(d => { if (!cancelled) setOwner(d) })
      .catch(e => { if (!cancelled) setOwner({ available: false, reason: String(e?.message ?? e) }) })
    return () => { cancelled = true }
  }, [])

  const suggest = useCallback(() => {
    const stamp = new Date().toTimeString().slice(0, 5).replace(':', '')
    return `${project.name}-${stamp}`
  }, [project.name])

  // Not asked yet. Silence here would read as "you cannot start one".
  if (owner === null) {
    return <span className="text-xs text-fg-ghost">indítás: a tulajdonos szolgáltatás megkérdezése…</span>
  }
  if (!owner.available) {
    return (
      <span data-fleet-start="unavailable" className="text-xs text-amber-400" title={owner.reason ?? ''}>
        agent nem indítható innen: {owner.reason ?? 'a tulajdonos szolgáltatás nem elérhető'}
      </span>
    )
  }

  if (!open) {
    return (
      <button
        data-fleet-start="offer"
        onClick={() => { setLabel(suggest()); setOpen(true); setError(null) }}
        className="text-xs text-sky-300 hover:text-sky-200 underline-offset-2 hover:underline"
        title="A keret indítja és tartja — ennek lesz terminálja a böngészőben."
      >
        + agent indítása
      </button>
    )
  }

  return (
    <form
      data-fleet-start="form"
      className="inline-flex items-baseline gap-1.5"
      onSubmit={e => {
        e.preventDefault()
        const name = label.trim()
        if (!name || busy) return
        setBusy(true)
        setError(null)
        fetch('/api/fleet/agents', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ label: name, cwd: project.root }),
        })
          .then(async r => {
            if (!r.ok) {
              const body = await r.json().catch(() => null)
              throw new Error(String(body?.detail ?? `HTTP ${r.status}`))
            }
            return r.json()
          })
          .then((agent: { label?: string }) => {
            setOpen(false)
            onStarted(String(agent.label ?? name))
          })
          .catch(e => setError(String(e?.message ?? e)))
          .finally(() => setBusy(false))
      }}
    >
      <input
        autoFocus
        value={label}
        onChange={e => setLabel(e.target.value)}
        aria-label="az indítandó agent neve"
        className="bg-surface-panel border border-surface-line rounded px-1.5 py-0.5 text-xs text-fg-strong w-48"
      />
      <button type="submit" disabled={busy} className="text-xs text-sky-300 hover:underline disabled:opacity-50">
        {busy ? 'indítás…' : 'indítás'}
      </button>
      <button type="button" onClick={() => setOpen(false)} className="text-xs text-fg-muted hover:text-fg-strong">
        mégse
      </button>
      {error && <span className="text-xs text-red-400" title={error}>nem indult el: {error}</span>}
    </form>
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
  // The remembered view, cached against the project it belongs to. `localStorage`
  // has no subscription, so a write has to put the new value here as well or the
  // next render reads the old choice back — and the project it was read FOR is
  // stored with it, so a project switch cannot show the previous project's memory
  // for one frame.
  const [memory, setMemory] = useState<{ project: string | null; view: ProjectView }>(
    { project: null, view: {} },
  )

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

  const projects = useMemo(() => data?.projects ?? [], [data])
  const populated = useMemo(() => projects.filter(p => p.agents.length > 0), [projects])
  // No fallback to "whatever discovery listed first": the column picks the
  // first project in the ARRANGED order and says so through `onSelect`, so the
  // selected project is always one the reader can find in the list.
  const active = useMemo(
    () => projects.find(p => p.name === selected) ?? null,
    [projects, selected],
  )
  const activeName = active?.name ?? null
  const remembered = memory.project === activeName ? memory.view : readView(activeName)
  const columns = resolveColumns(remembered)
  const enlarged = resolveEnlarged(remembered, active?.agents.map(a => a.pid) ?? [])
  const setEnlarged = useCallback((project: string | null, pid: number | null) => {
    writeView(project, { enlarged: pid })
    setMemory({ project, view: readView(project) })
  }, [])
  /**
   * Which terminal is open — task 8.3's reattach half.
   *
   * Remembered by LABEL, per project, and resolved against the live answer on
   * every render: a remembered label whose agent is gone, or which no longer
   * belongs to a `started-here` agent, opens nothing. The memory says what to
   * show; it never says what exists. That is what makes a reload a reattach —
   * the socket reopens, the server replays the buffered screen, and the reader
   * lands on the screen as it already is rather than on a blank one.
   */
  const setColumns = useCallback((project: string | null, columns: number) => {
    writeView(project, { columns })
    setMemory({ project, view: readView(project) })
  }, [])

  const setTerminal = useCallback((project: string | null, label: string | null) => {
    writeView(project, { terminal: label })
    setMemory({ project, view: readView(project) })
  }, [])
  const openTerminal = useMemo(() => {
    const want = remembered.terminal
    if (typeof want !== 'string' || !active) return null
    const alive = active.agents.some(a => terminalOffer(a, data?.owner_reachable).kind === 'available'
      && a.terminal_label === want)
    return alive ? want : null
  }, [remembered.terminal, active, data?.owner_reachable])

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

  return (
    <div className="h-full flex flex-col" data-fleet-phase={data.agents === 0 ? 'answered-empty' : 'answered'}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 md:px-6 py-2.5 border-b border-surface-line shrink-0">
        <span className="text-sm font-semibold text-fg-loud">Flotta</span>
        <span className="text-xs text-fg-muted tabular-nums">{data.agents} agent · {populated.length} projektben</span>
        {/* The per-state counts moved into the column's attention header, which
            is where the jump to the first one lives. Two places carrying the
            same count is one place too many: the copy nobody maintains is the
            one that drifts, and it is always the one being read. */}
        {/* The caveat explains a state; with nothing in that state it is noise
            at the top of the landing screen. Rendered from the data, so it can
            never explain away a screen that has no agents on it. */}
        {data.agents > 0 && (
          <span className="text-xs text-fg-muted">
            a <span className="text-fg-strong">csendes</span> nem azt jelenti, hogy nem történik semmi — csak azt,
            hogy a napló legutóbbi kiírásakor nem volt nyitott eszközhívás
          </span>
        )}
        {/* One cause, named once. A screen that can offer no terminal ANYWHERE
            has a single reason, and stating it per row would put 22 copies of it
            on the landing screen while still not saying it is one fact. `false`
            only — an absent key is not a `false`, and an older server that says
            nothing must not be reported as a dead owner. */}
        {data.owner_reachable === false && (
          <span
            data-fleet-owner="unreachable"
            className="text-xs text-amber-400"
            title="A tulajdonos szolgáltatás nem válaszolt, ezért egyetlen agentről sem tudjuk, a keret tartja-e. Ez nem azt jelenti, hogy egyiknek sincs terminálja."
          >
            a tulajdonos szolgáltatás nem válaszol — a terminálok hovatartozása ismeretlen, nem hiányzó
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

      <div className="flex-1 flex min-h-0">
        {/* Task 7.1 / D-2 — the hand-made arrangement. It renders even when
            nothing is running: a project's position is a statement about the
            project, not about who happens to be in it, so the list must not
            empty itself when the agents close. */}
        <FleetProjectColumn
          data={data}
          selected={active?.name ?? null}
          onSelect={name => setSelected(name)}
        />

        <div className="flex-1 overflow-y-auto p-3 space-y-2 min-w-0">
          {data.agents === 0 ? (
            <AnsweredEmpty at={answeredAt} projects={data.projects.length} />
          ) : active ? (
            <>
              <div className="flex items-baseline gap-2 px-0.5 flex-wrap">
                <span className="text-sm text-fg-loud">{active.name}</span>
                <span className="text-xs text-fg-muted tabular-nums">{active.agents.length} agent</span>
                <span className="text-xs text-fg-ghost truncate">{active.root}</span>
                <StartAgent
                  project={active}
                  onStarted={label => { setTerminal(active.name, label); load() }}
                />
                {/* Density is a per-project choice — task 7.5. Offered only
                    where it can change anything: with one agent there is
                    nothing to lay out, and while a tile is enlarged the grid
                    is not the arrangement in use. */}
                {enlarged === null && active.agents.length > 1 && (
                  <span className="ml-auto flex items-center gap-1 shrink-0" title="Hány oszlopban jelenjenek meg az agentek ebben a projektben">
                    <span className="text-xs text-fg-ghost">oszlop</span>
                    {COLUMN_CHOICES.map(c => (
                      <button
                        key={c}
                        data-fleet-columns={c}
                        aria-pressed={c === columns}
                        onClick={() => setColumns(active.name, c)}
                        className={`text-xs tabular-nums px-1.5 rounded border ${
                          c === columns
                            ? 'border-surface-line bg-surface-raised/60 text-fg-strong'
                            : 'border-transparent text-fg-ghost hover:text-fg-muted'
                        }`}
                      >{c}</button>
                    ))}
                  </span>
                )}
                {enlarged !== null && active.agents.length > 1 && (
                  <span className="ml-auto text-xs text-fg-ghost shrink-0 tabular-nums">
                    {active.agents.length - 1} sorként — kattints egyre a váltáshoz
                  </span>
                )}
              </div>
              {/* A selected project with nothing running is not an error and not
                  an empty panel: the arrangement keeps it in the list on
                  purpose, so the right-hand side says what it measured. */}
              {active.agents.length === 0 && (
                <div className="text-sm text-fg-muted">
                  Ebben a projektben a felderítés nem talált futó agentet.
                  {active.archived && <span className="text-fg-ghost"> (archivált projekt)</span>}
                </div>
              )}
              {/* Task 7.4 — the enlarged tile stays in the list's own order, and
                  every other agent keeps a row. Rendering the enlarged one in
                  place (rather than lifting it to the top) is what makes a row
                  the way back: the agent you clicked is where you clicked. */}
              {/* A grid when nothing is enlarged, a single column when
                  something is — an enlarged tile carries a log or a terminal
                  and needs the width, and the rows beside it are a list, not
                  a layout. `space-y-2` on the parent still spaces the header
                  and the panels; the grid owns its own gaps. */}
              <div className={enlarged === null ? `grid gap-2 ${GRID_COLS[columns] ?? GRID_COLS[2]}` : 'space-y-2'}>
              {active.agents.map(a => (
                a.pid === enlarged ? (
                  <AgentCard
                    key={a.pid}
                    agent={a}
                    enlarged
                    open
                    onToggle={() => setEnlarged(active.name, null)}
                    ownerReachable={data.owner_reachable}
                    terminalOpen={openTerminal !== null && openTerminal === a.terminal_label}
                    onTerminal={label => setTerminal(active.name, label)}
                  />
                ) : enlarged !== null ? (
                  <AgentRow key={a.pid} agent={a} onSelect={() => setEnlarged(active.name, a.pid)} />
                ) : (
                  <AgentCard
                    key={a.pid}
                    agent={a}
                    open={false}
                    onToggle={() => setEnlarged(active.name, a.pid)}
                    ownerReachable={data.owner_reachable}
                    terminalOpen={openTerminal !== null && openTerminal === a.terminal_label}
                    onTerminal={label => setTerminal(active.name, label)}
                  />
                )
              ))}
              </div>
            </>
          ) : (
            <div className="text-sm text-fg-muted">
              Van futó agent, de egyik ismert projekthez sem sikerült kötni.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
