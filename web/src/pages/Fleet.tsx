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
import { COLUMN_CHOICES, readView, resolveColumns, resolveEnlarged, resolveFocus, resolveLogs, resolveTerminals, writeView } from '../lib/fleetViewState'
import type { ProjectView } from '../lib/fleetViewState'
import type { FleetAgent, FleetProject, FleetResponse } from '../lib/fleetTypes'
import { terminalOffer } from '../lib/fleetTerminal'
import { buildActs, errorStanding, sayCount, speakerOf, speakerLabel, toolSummary } from '../lib/fleetConversation'
import { OWNERSHIP_NOTE, cardClasses, ownershipOf } from '../lib/fleetCardStyle'
import { tally } from '../lib/fleetAttention'
import { blockUnexpectedFrom, declaredStanding, phaseRepeatsBlock, purposeStanding } from '../lib/fleetDeclared'
import type { DeclaredStanding } from '../lib/fleetDeclared'
import FleetInstruct from '../components/FleetInstruct'
import FleetWaiters from '../components/FleetWaiters'
import TileControls from '../components/TileControls'
import { plainExcerpt } from '../lib/excerptText'
import { descendantStanding, parentClaim } from '../lib/fleetLineage'
import { currentSelection, tileClickOpens } from '../lib/fleetTileClick'
import type { Act, LogTurn, SayAct, Speaker, WorkAct } from '../lib/fleetConversation'

interface LogResponse {
  turns: LogTurn[]
  total_read?: number
  truncated?: boolean
  problem?: string
  pid?: number
  name?: string | null
}

function age(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 90) return `${Math.round(seconds)}s`
  if (seconds < 5400) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
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
  // Used only by the log's day divider, which is why it is translated with the
  // rest of that view (the dashboard is English; only the projects are not).
  if (d.toDateString() === today.toDateString()) return 'today'
  if (d.toDateString() === y.toDateString()) return 'yesterday'
  return d.toLocaleDateString('hu-HU', { month: '2-digit', day: '2-digit' })
}

function StateLine({ agent }: { agent: FleetAgent }) {
  if (agent.state === 'working') {
    return (
      <span className="inline-flex items-center gap-1.5 text-emerald-400 whitespace-nowrap">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
        <span>{agent.tool ?? 'working'}</span>
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
        unknown
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
        title={why ?? 'The session is waiting for a person. What for was not written down by the runtime — the state is measured either way.'}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-sky-300 shrink-0" />
        waiting for an answer
        {why
          ? <span className="text-fg-muted font-normal truncate max-w-[16rem]">{why}</span>
          : <span className="text-fg-ghost font-normal">(what for was not written down)</span>}
      </span>
    )
  }
  if (agent.state === 'quiet') {
    return (
      <span className="inline-flex items-center gap-1.5 text-fg-muted whitespace-nowrap">
        <span className="w-1.5 h-1.5 rounded-full bg-surface-line shrink-0" />
        quiet
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
          title="Discovery reported a state this screen does not know yet — its name is shown and no meaning is attributed to it.">
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
    `The record declared the state “${declared}” and the log refuted it — the measurement (“${agent.state}”) wins. ` +
    'This is not the screen\'s fault and the screen does not fix it: the producer\'s record says one thing and its log another.'
  return (
    <span
      data-fleet-conflict-agent={agent.pid}
      title={explain}
      className="inline-flex items-center gap-1 text-xs text-amber-400 whitespace-nowrap"
    >
      <span aria-hidden>⚠</span>
      {compact ? (
        <span className="sr-only">contradicting declaration</span>
      ) : (
        <span className="font-normal">
          declared: <span className="line-through">{declared}</span>
        </span>
      )}
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
  { id: 'conversation', label: 'conversation' },
  {
    id: 'timeline',
    label: 'timeline',
    absent: 'the existing activity timeline will move here; this tab holds its place and has no content yet (7.12)',
  },
]

/**
 * How a sentence and a machine action are told apart on screen — task 7.20.
 *
 * `lib/fleetConversation.ts` holds the model and the measurement; this is the
 * weight given to each act. One rule decides every choice below: **the 7.5% of
 * the log that is a sentence must be findable by running an eye down the
 * column**, and the 92.5% that is machinery must stay legible without
 * competing for that eye. So a sentence gets a card, the reading size and a
 * coloured rail; an act gets one dim line at 11px.
 *
 * `te` appears for the person and for nobody else. A runtime-written turn under
 * the `user` role says who wrote it, in its own weight — quieter than a person,
 * louder than a tool line, and never silent, because a hidden entry is one the
 * reader cannot account for.
 */
const SAY_STYLE: Record<Speaker, { rail: string; label: string; body: string; note?: string }> = {
  person: {
    rail: 'border-sky-400 bg-sky-400/[0.06]',
    label: 'text-sky-300 font-semibold',
    body: 'text-sm text-fg-normal',
  },
  agent: {
    rail: 'border-surface-edge',
    label: 'text-fg-muted font-semibold',
    body: 'text-sm text-fg-normal',
  },
  runtime: {
    rail: 'border-surface-line',
    label: 'text-fg-ghost',
    body: 'text-xs text-fg-muted',
    note: 'written by the runtime under the `user` role — the person did not say this',
  },
  other: {
    rail: 'border-amber-400/60',
    label: 'text-amber-400',
    body: 'text-sm text-fg-normal',
    note: 'unknown role — printed as itself, no meaning is attributed to it',
  },
}

const CLIP = 600

function SayRow({ act, showThinking, expanded, onExpand }: {
  act: SayAct
  showThinking: boolean
  expanded: boolean
  onExpand: () => void
}) {
  const style = SAY_STYLE[act.speaker]
  const long = act.text.length > CLIP
  const shown = long && !expanded ? act.text.slice(0, CLIP) : act.text
  return (
    <div
      data-log-act="say"
      data-log-speaker={act.speaker}
      className={`border-l-2 pl-2.5 pr-1 py-1 rounded-r ${style.rail}`}
    >
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className={`text-xs ${style.label}`} title={style.note}>
          {speakerLabel(act.speaker, act.role)}
        </span>
        <span className="text-xs text-fg-ghost tabular-nums">{clock(act.at)}</span>
        {style.note && <span className="text-xs text-fg-ghost italic">{style.note}</span>}
      </div>
      {showThinking && act.thinking && (
        <div className="text-xs text-fg-ghost italic whitespace-pre-wrap break-words mt-0.5">
          {act.thinking.length > CLIP ? act.thinking.slice(0, CLIP) + ' …' : act.thinking}
        </div>
      )}
      {act.text && (
        <div className={`${style.body} leading-relaxed whitespace-pre-wrap break-words mt-0.5`}>
          {shown}
          {long && (
            <button
              onClick={onExpand}
              className="ml-1 text-xs text-sky-400 hover:text-sky-300 underline-offset-2 hover:underline"
            >
              {expanded ? 'less' : `… ${act.text.length - CLIP} more characters`}
            </button>
          )}
        </div>
      )}
      {!act.text && !act.thinking && (
        <div className="text-xs text-fg-ghost italic mt-0.5">
          thinking, with no text — the runtime did not keep its content
        </div>
      )}
    </div>
  )
}

/**
 * A tool call and its result — ONE line, because they are one act.
 *
 * What this line may never do is imply that nothing went wrong. Three separate
 * facts ride on it, and the third is the one the compaction rule is about:
 *
 *  - `↩n` — results that came back.
 *  - *n awaiting a result* — a call with no result in this window. Not a failure:
 *    it is either still running or the tail cut between the two. Amber, which
 *    on this screen means *undetermined*, never *broken*.
 *  - a failed call, in red — **only when the data says so.** When it does not,
 *    this line stays silent and the panel header carries the admission once,
 *    where the reader is standing. Marking every line would be noise; marking
 *    nothing and saying nothing would be the false absence.
 */
function WorkRow({ act }: { act: WorkAct }) {
  const failed = act.errors !== null && act.errors > 0
  return (
    <div
      data-log-act="work"
      data-log-errors={act.errors === null ? 'unknown' : String(act.errors)}
      className={`flex items-baseline gap-2 pl-2.5 border-l text-xs leading-5 ${
        failed ? 'border-red-400/70' : 'border-surface-line/60'
      }`}
    >
      <span className="text-fg-ghost tabular-nums shrink-0 w-8">{clock(act.at)}</span>
      {act.calls > 0 ? (
        <span className="text-emerald-400/70 min-w-0 truncate" title={act.names.join(', ')}>
          {toolSummary(act)}
        </span>
      ) : (
        <span className="text-fg-ghost italic min-w-0 truncate">
          result — its call is outside this window
        </span>
      )}
      {act.results > 0 && (
        <span className="text-fg-ghost tabular-nums shrink-0" title={`${act.results} result(s) came back`}>
          ↩{act.results}
        </span>
      )}
      {act.unanswered > 0 && (
        <span
          className="text-amber-400/80 shrink-0"
          title="The call has no result in this window: it is either still running, or the log tail cut between the two. Not a failure — but not finished either."
        >
          {act.unanswered} awaiting a result
        </span>
      )}
      {failed && (
        <span
          className="text-red-400 font-semibold shrink-0"
          title="The returned result reported a failure. Joining the call to its result may not hide that — so it is marked here, on the row it happened on."
        >
          ⚠ {act.errors} failed
        </span>
      )}
    </div>
  )
}

/**
 * What the panel may state about failures, stated once and at the top.
 *
 * The producer sends a COUNT of tool results and drops `is_error` (measured in
 * one live log: 145 of 146 result blocks carry the flag, 4 of them true). So
 * today this renders the admission rather than a number — and it renders it
 * above the scroll container, which is where the reader is standing, not inside
 * it where a scroll can carry it off screen.
 */
function ErrorStanding({ acts }: { acts: Act[] }) {
  const standing = errorStanding(acts)
  if (standing === null) return null
  if (!standing.known) {
    return (
      <span
        data-log-errors-standing="unknown"
        className="text-xs text-amber-400"
        title="Tool results are shown, but which of them failed is not carried by this data: the session log knows (is_error), the log endpoint passes on only the count. So this view does NOT claim that nothing failed."
      >
        ⚠ failure state not carried
      </span>
    )
  }
  if (standing.failed > 0) {
    return (
      <span data-log-errors-standing="failed" className="text-xs text-red-400 font-semibold tabular-nums">
        {standing.failed} failed call(s)
      </span>
    )
  }
  return (
    <span
      data-log-errors-standing="none"
      className="text-xs text-fg-ghost tabular-nums"
      title="Measured: no tool call failed in this window."
    >
      0 failed calls
    </span>
  )
}

function LogPanel({ pid, onClose, tall }: { pid: number; onClose: () => void; tall?: boolean }) {
  const [log, setLog] = useState<LogResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showThinking, setShowThinking] = useState(false)
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set())

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

  // The turns become acts here (task 7.20). Every count below is taken from the
  // ACTS, so the header can never disagree with the rows underneath it.
  const acts = useMemo(() => buildActs(log?.turns ?? []), [log])
  const sentences = sayCount(acts)

  return (
    <div className="border-t border-surface-line mt-3 pt-2" data-fleet-own-surface="log">
      <div className="flex items-baseline gap-2 mb-1.5 flex-wrap" role="tablist" aria-label="log views">
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
              {tab.label} <span className="text-fg-ghost">(not built yet)</span>
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
            the last {log.turns.length} of {log.total_read}
          </span>
        )}
        {/* Counted from the acts. A log that is all machinery says so out loud:
            an empty-looking conversation and a conversation of pure tool
            traffic are two different facts, and the reader must not have to
            infer which one they are looking at. */}
        {acts.length > 0 && (
          <span
            data-log-sentences={sentences}
            className="text-xs text-fg-muted tabular-nums"
            title="How many acts carry an actual sentence. The rest are tool calls and their results — also in the log, just not speech."
          >
            {sentences > 0 ? `${sentences} sentence(s)` : 'not one sentence'} / {acts.length} acts
          </span>
        )}
        <ErrorStanding acts={acts} />
        {thinkingTurns > 0 && (
          <button
            onClick={() => setShowThinking(v => !v)}
            className="text-xs text-fg-muted hover:text-fg-strong underline-offset-2 hover:underline tabular-nums"
            title="The thinking is in the log; it stays hidden by default so the conversation remains readable."
          >
            {showThinking ? 'hide thinking' : `thinking (${thinkingTurns})`}
          </button>
        )}
        <button onClick={onClose} className="ml-auto text-xs text-fg-muted hover:text-fg-strong">close</button>
      </div>
      {error && <div className="text-xs text-red-400">cannot be read: {error}</div>}
      {/* A problem is not an empty conversation, and the two must not look alike. */}
      {log?.problem && <div className="text-xs text-amber-400">{log.problem}</div>}
      {log && !log.problem && log.turns.length === 0 && (
        <div className="text-xs text-fg-muted">the log is readable and holds no conversation</div>
      )}
      {!log && !error && <div className="text-xs text-fg-muted">reading the log…</div>}
      <div className={`${tall ? 'max-h-[55vh]' : 'max-h-80'} overflow-y-auto space-y-1 pr-1`}>
        {acts.map((act, i, all) => {
        // A day divider, because HH:MM alone made a 60-hour gap look like a
        // minute. Measured 2026-08-18: forty turns of one session spanned three
        // calendar days, and the clock column rendered 00:04 next to 10:46 with
        // nothing between them — the reader's honest conclusion from that is a
        // session that has been busy all morning. Same false-value class as the
        // rest of this screen, arriving through a field that looked like data.
        const prevDay = i > 0 ? dayKey(all[i - 1].at) : ''
        const thisDay = dayKey(act.at)
        const newDay = thisDay !== '' && thisDay !== prevDay
        return (
          <div key={act.kind === 'say' ? `s${act.turn}` : `w${act.turns.join('-')}-${i}`}>
            {newDay && (
              <div className="flex items-center gap-2 mt-2 mb-1 first:mt-0">
                <span className="text-xs text-fg-ghost tabular-nums shrink-0">{dayLabel(act.at)}</span>
                <span className="flex-1 border-t border-surface-line" />
              </div>
            )}
            {act.kind === 'say' ? (
              <SayRow
                act={act}
                showThinking={showThinking}
                expanded={expanded.has(act.turn)}
                onExpand={() => setExpanded(prev => {
                  const next = new Set(prev)
                  if (next.has(act.turn)) next.delete(act.turn); else next.add(act.turn)
                  return next
                })}
              />
            ) : (
              <WorkRow act={act} />
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
function Lineage({ agent, canJumpSeat, onJumpSeat }: {
  agent: FleetAgent
  canJumpSeat?: (seat: string) => boolean
  onJumpSeat?: (seat: string) => void
}) {
  const claim = parentClaim(agent)
  if (claim.kind === 'none') return null
  /*
    Asking and acting are two callbacks on purpose. One that did both would be
    called DURING RENDER to decide whether to offer the control — and would
    then navigate while rendering, which is a state change inside a render pass
    and an infinite loop with it. The question is pure; the act is not.
  */
  const reachable = claim.seat !== null && canJumpSeat?.(claim.seat) === true
  const body = (
    <>
      ← {claim.label}
      <span className={claim.measured ? 'ml-1 text-fg-ghost' : 'ml-1 text-amber-400/70'}>
        {claim.measured ? 'recorded' : 'from the process tree'}
      </span>
    </>
  )
  return reachable ? (
    <button
      data-fleet-parent={claim.measured ? 'recorded' : 'ancestry'}
      data-fleet-parent-jump={claim.seat}
      onClick={() => onJumpSeat?.(claim.seat as string)}
      className="text-xs text-fg-ghost shrink-0 hover:text-fg-strong underline-offset-2 hover:underline"
      title={`${claim.note}. Click to go to it.`}
    >
      {body}
    </button>
  ) : (
    <span
      data-fleet-parent={claim.measured ? 'recorded' : 'ancestry'}
      className="text-xs text-fg-ghost shrink-0"
      title={claim.note}
    >
      {body}
    </span>
  )
}

/**
 * Who runs UNDER this agent — task 7.18.
 *
 * The count is never shown bare. `live_only` says it covers recorded starts
 * that are still running, so a child started with `claude -p` that has already
 * exited is not in it — and a lone `2` reads as *this agent has two children*,
 * which is a claim nobody measured. The caveat rides in the tooltip and the
 * bound is marked on the number itself.
 *
 * `known: false` renders as *we could not look*, never as zero: without a seat
 * there is no key to look the agent up by, and a zero there would answer a
 * question nobody asked.
 */
function Descendants({ agent, canJumpPid, onJumpPid }: {
  agent: FleetAgent
  canJumpPid?: (pid: number) => boolean
  onJumpPid?: (pid: number) => void
}) {
  const standing = descendantStanding(agent)
  if (standing.kind === 'unknown') {
    /*
      Seen on the live screen: `↳ ?` on four tiles out of five, because the
      lookup needs a seat and most agents have none. The absence is real and it
      is already SAID on the same tile — `no input: this session has no seat on
      the messaging bus` — so a second marker for the same cause is the
      second-copy defect inside one card, and it fires on every tile that has
      nothing to report.

      It stays for the case that is NOT already explained: an agent that has a
      seat and still could not be looked up. There the marker is the only thing
      that says so, and it means what it says.
    */
    if (agent.instructable !== true) return null
    return (
      <span
        data-fleet-descendants="unknown"
        className="text-xs text-amber-400/70 shrink-0"
        title={`We could not look: ${standing.reason}. This is not "nothing runs under it".`}
      >
        ↳ ?
      </span>
    )
  }
  if (standing.kind === 'none') return null
  return (
    <span className="inline-flex items-baseline gap-1 shrink-0" data-fleet-descendants={standing.live}>
      <span
        className="text-xs text-fg-muted tabular-nums"
        title={standing.caveat
          ? `${standing.live} agent(s) run under this one — ${standing.caveat}.`
          : `${standing.live} agent(s) run under this one.`}
      >
        ↳ {standing.live}
        {/* The bound, ON the number. A count whose limit lives only in a
            tooltip is a count the reader takes for complete. */}
        {standing.caveat && <span className="text-fg-ghost">*</span>}
      </span>
      {standing.pids.map(pid => (
        canJumpPid?.(pid) ? (
          <button
            key={pid}
            data-fleet-descendant-jump={pid}
            onClick={() => onJumpPid?.(pid)}
            className="text-xs text-fg-ghost tabular-nums hover:text-fg-strong underline-offset-2 hover:underline"
            title="Go to this agent"
          >
            {pid}
          </button>
        ) : (
          <span key={pid} className="text-xs text-fg-ghost tabular-nums" title="Running, but not on this screen">
            {pid}
          </span>
        )
      ))}
    </span>
  )
}

/**
 * The last thing said in this session — task 7.3.
 *
 * The point of the tile is that a reader learns what is going on WITHOUT
 * opening anything; a state word alone ("quiet", "working") says the shape of
 * the moment and nothing about the subject.
 *
 * Absence is stated rather than rendered as a blank: a tail made entirely of
 * tool traffic means nothing was said recently, and an empty line would read as
 * a session in which nothing was ever said. Same rule as everywhere else on
 * this screen — a gap is not a zero.
 */
function Excerpt({ agent, lines = 2 }: { agent: FleetAgent; lines?: number }) {
  // An excerpt made entirely of table scaffolding leaves nothing after
  // stripping. That is the same absence as a tail of pure tool traffic, and it
  // gets the same sentence rather than an empty line.
  if (!agent.excerpt || !plainExcerpt(agent.excerpt)) {
    return (
      <div className="text-xs text-fg-ghost mt-1 italic">
        the tail of the log is all tool traffic — nothing was said recently
      </div>
    )
  }
  // `excerpt_from` is a ROLE, and a role is not a speaker — task 7.20, the same
  // false value the log panel carries. Measured over the six most recent
  // session logs: of 41 `user` turns that carry text, 9 were written by the
  // runtime (`<command-name>`, `<command-message>`, `<local-command-stdout>`),
  // not by the person. So the label is decided from the text as well as the
  // role, and `te` is reserved for what the person actually said.
  // Markdown marks stripped line by line — raised 2026-08-19: the busiest agent
  // showed `| |---|---| | **7.7** utasítás | …` as its excerpt, which is pipes
  // and asterisks where the answer to "what is happening" should be. Nothing is
  // rendered, interpreted or shortened; the marks go and the words stay.
  const shown = plainExcerpt(agent.excerpt)
  const speaker: Speaker = agent.excerpt_from === 'user'
    ? speakerOf('user', agent.excerpt)
    : agent.excerpt_from === 'agent' ? 'agent' : 'other'
  const tone = speaker === 'person' ? 'text-sky-400/80' : speaker === 'runtime' ? 'text-fg-ghost' : 'text-fg-muted'
  return (
    <div className="flex gap-1.5 mt-1 min-w-0" data-fleet-excerpt={agent.excerpt_from ?? 'ismeretlen'}>
      <span
        className={`text-xs shrink-0 ${tone}`}
        data-fleet-excerpt-speaker={speaker}
        title={speaker === 'runtime'
          ? 'Written by the runtime under the `user` role — the person did not say this.'
          : undefined}
      >
        {speaker === 'other' ? 'log' : speakerLabel(speaker, 'user')}
      </span>
      <span
        className="text-xs text-fg-muted min-w-0"
        style={{ display: '-webkit-box', WebkitLineClamp: lines, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
      >
        {shown}
      </span>
    </div>
  )
}

function AgentRow({ agent, onSelect }: { agent: FleetAgent; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      data-fleet-row={agent.pid}
      title="Click: this tile is enlarged"
      className="w-full text-left flex items-baseline gap-2 px-3 py-1 rounded border border-transparent hover:border-surface-line hover:bg-surface-raised/40 transition-colors"
    >
      <span className="text-xs text-fg-strong truncate max-w-[14rem] shrink-0">
        {/* Same identity rule as the card — a row and a card must not name the
            same agent differently. */}
        {agent.terminal_label ?? agent.name ?? <span className="text-fg-muted">unnamed</span>}
        {!agent.binding_confirmed && (
          <span className="ml-1 text-amber-400" title="The binding to the session log did not come from a record">?</span>
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

/**
 * What the agent SAYS about itself — tasks 3.4 and 3.5.
 *
 * Rendered BESIDE the measured state, never instead of it. The load-bearing
 * case is the pair that disagrees: measured `quiet` next to a declared block is
 * an agent the tile would otherwise draw as calm — and it exists on this
 * machine right now, not hypothetically (pid 1433849, measured 2026-08-19).
 *
 * Three absences are three different sentences: the bus could not be asked, the
 * agent declares nothing, and there is no declaration to age. Only the middle
 * one is a fact about the agent.
 *
 * ⚠ `focus` and `files` may carry a consumer's own words and paths — one live
 * focus named a partner company and an unpaid invoice. They are shown and never
 * written anywhere: no `localStorage`, no log, no cache.
 */
function Declared({ standing, full, blockShown }: {
  standing: DeclaredStanding
  full?: boolean
  /**
   * Whether the header is already carrying the block. The phase is dropped only
   * when it would repeat a marker the reader can see — never when the marker is
   * absent, which would take the fact off the tile altogether.
   */
  blockShown?: boolean
}) {
  if (standing.kind === 'unasked') {
    return (
      <div className="text-xs text-amber-400 mt-1" data-fleet-declared="unasked"
           title="The messaging bus could not be asked, so nothing is known about what this agent says it is doing. That is not the same as an agent that says nothing.">
        ⚠ we could not ask what this agent says about itself
      </div>
    )
  }
  if (standing.kind === 'silent') {
    // Stated only where there is room for it. Seen on the live screen: with
    // most agents declaring nothing, this line appeared on every tile in the
    // grid — a sentence that says there is nothing to say, repeated thirteen
    // times, which is the noise `ui-quality.md` puts below a compact screen.
    // The distinction it protects (silent vs unasked) still matters, so it is
    // moved rather than dropped: an enlarged tile says it, and the tile that
    // could NOT be asked says so everywhere.
    if (!full) return null
    return (
      <div className="text-xs text-fg-ghost mt-1" data-fleet-declared="silent">
        declares nothing about itself
      </div>
    )
  }
  return (
    <div className="text-xs mt-1 space-y-0.5" data-fleet-declared="declared">
      <div className="flex items-baseline gap-2 flex-wrap">
        <span className="text-fg-ghost shrink-0">says:</span>
        {standing.phase && !phaseRepeatsBlock(standing.phase, !!blockShown) && (
          <span className="text-fg-muted shrink-0" data-fleet-declared-phase={standing.phase}>{standing.phase}</span>
        )}
        {/* `flex-1` with a real minimum, so the focus shares the label's line
            instead of wrapping under it and leaving `says:` alone in a row of
            its own — visible the moment the doubled phase stopped filling that
            gap. Below the minimum it still wraps, which is the right fallback:
            a narrow tile gets a full-width sentence rather than a column of
            three characters. */}
        {standing.focus && (
          <span className="text-fg-normal flex-1 min-w-[14rem]" style={full ? undefined : {
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
          }}>{standing.focus}</span>
        )}
        {/* A declaration does not expire on its own, so its AGE is what lets a
            reader weigh it. Deliberately not turned into a staleness verdict:
            a threshold discards the true positives first. */}
        {standing.ageSeconds !== null && (
          <span className="text-fg-ghost tabular-nums shrink-0"
                title="How long ago the agent said this. It has not been restated since.">
            {age(standing.ageSeconds)} ago
          </span>
        )}
      </div>
      {standing.files.length > 0 && (
        <div className="text-fg-ghost truncate" title={standing.files.join('\n')}>
          {standing.files.length} file(s): {standing.files.slice(0, full ? 8 : 3).join(', ')}
          {standing.files.length > (full ? 8 : 3) && ' …'}
        </div>
      )}
    </div>
  )
}

/**
 * What the agent is working TOWARDS — task 3.9, from the engine's own record.
 *
 * Two absences that must not look alike: no record at all (on a machine with no
 * engine that is every agent — measured 13 of 13), and a record whose task file
 * could not be counted. Neither draws a progress bar, because a `0/0` renders
 * identically to a change nobody has started.
 *
 * `stale` is the third status and the one worth seeing: a record claiming a run
 * whose process is gone. `pid_unverified` is its quieter sibling — a pid held by
 * something that is not an agent, which is what pid reuse looks like from here.
 */
function Purpose({ agent }: { agent: FleetAgent }) {
  const p = purposeStanding(agent)
  if (p.kind === 'no-record') return null
  const tone = p.status === 'running' ? 'text-emerald-400'
    : p.status === 'finished' ? 'text-fg-muted' : 'text-amber-400'
  return (
    <div className="flex items-baseline gap-2 flex-wrap text-xs mt-1" data-fleet-purpose={p.change}>
      <span className="text-fg-ghost shrink-0">for:</span>
      <span className="text-fg-normal truncate min-w-0">{p.change}</span>
      {p.group && <span className="text-fg-ghost shrink-0">· {p.group}</span>}
      <span className={`shrink-0 ${tone}`} data-fleet-purpose-status={p.status}
            title={p.status === 'stale'
              ? 'The record claims a run whose process is gone — see task 7.14: 68 days of “in progress” that was not.'
              : undefined}>
        {p.status}
      </span>
      {p.pidUnverified && (
        <span className="text-amber-400 shrink-0"
              title="The record claims a live run, and the pid it names is held by something that is not an agent. A pid is recycled, so this says which question was answered.">
          pid unverified
        </span>
      )}
      {p.progress ? (
        <span className="text-fg-muted tabular-nums shrink-0" data-fleet-progress={`${p.progress.done}/${p.progress.total}`}>
          {p.progress.done}/{p.progress.total} tasks
        </span>
      ) : (
        <span className="text-fg-ghost shrink-0" data-fleet-progress="unmeasured"
              title="The task file could not be counted. A 0/0 would draw a bar for a change nobody measured.">
          progress not measured
        </span>
      )}
    </div>
  )
}

function AgentCard({ agent, open, onToggle, enlarged, focused, wide, typing, ownerReachable, terminalOpen, onTerminal, onFocus, onEnlarge, onOpen, onTyping, canJumpSeat, onJumpSeat, canJumpPid, onJumpPid }: {
  agent: FleetAgent
  open: boolean
  onToggle: () => void
  enlarged?: boolean
  /** The tile is alone on the panel — full screen. */
  focused?: boolean
  /** Take the whole row of the grid: something is open inside and needs width. */
  wide?: boolean
  /** The reader's keyboard is in this tile's terminal. Measured, not inferred. */
  typing?: boolean
  ownerReachable?: boolean
  /** Whether THIS agent's terminal is open. Several may be open at once. */
  terminalOpen: boolean
  onTerminal: (label: string | null) => void
  /** Ask for this agent alone on the panel, or back to the grid. */
  onFocus?: () => void
  /**
   * Ask for the 7.4 layout — this tile big, the others as rows.
   *
   * Its own control since 2026-08-19. It used to be what the log button did,
   * which meant reading one agent's log hid every other agent; the two acts are
   * now separate and the log opens where the tile already is.
   */
  onEnlarge?: () => void
  /**
   * The tile's own body is a way in — asked for 2026-08-19.
   *
   * Absent on a tile that is ALREADY open, which makes the act one-directional
   * on purpose: a click that closes what you are reading is a trap, and the
   * control that closes it is visible in the corner. See `lib/fleetTileClick.ts`
   * for what a click has to get past first.
   */
  onOpen?: () => void
  /** Reports the keyboard entering or leaving this agent's terminal. */
  onTyping?: (typing: boolean) => void
  /**
   * Go to an agent by seat (7.8, upwards) or by pid (7.18, downwards).
   *
   * They return whether that agent is on this screen AT ALL, so the tile can
   * decide whether to offer a way in: a control that scrolls to nothing is the
   * shape 8.2 forbids, and a relative outside the fleet is a fact rather than a
   * destination.
   */
  canJumpSeat?: (seat: string) => boolean
  onJumpSeat?: (seat: string) => void
  canJumpPid?: (pid: number) => boolean
  onJumpPid?: (pid: number) => void
}) {
  const offer = terminalOffer(agent, ownerReachable)
  // Ownership decides the tile's edge — see `lib/fleetCardStyle.ts` for why it
  // is the edge's SHAPE and not a colour. The tiles used to be bordered with
  // `surface-line`, which is the same neutral-800 as the surface behind them:
  // an edge that cannot be seen, which is what made the grid read as one block.
  const ownership = ownershipOf(agent, ownerReachable)
  // Computed once: the header marker and the block below must not be able to
  // disagree about what the agent declared.
  const standing = declaredStanding(agent)
  return (
    <div
      data-fleet-enlarged={enlarged ? agent.pid : undefined}
      data-fleet-focused={focused ? agent.pid : undefined}
      data-fleet-ownership={ownership}
      data-fleet-typing={typing ? agent.pid : undefined}
      title={OWNERSHIP_NOTE[ownership]}
      data-fleet-opens={onOpen ? agent.pid : undefined}
      onClick={onOpen
        ? e => {
            if (tileClickOpens({
              target: e.target as Element,
              card: e.currentTarget,
              selection: currentSelection(),
            })) onOpen()
          }
        : undefined}
      className={`${cardClasses(ownership, { enlarged, focused, typing })}${wide ? ' md:col-span-full' : ''}${onOpen ? ' cursor-pointer' : ''}`}
    >
      {/* Two parts, so the controls stay in the corner. With everything in one
          wrapping row, a long name pushed the icons onto a second line — a
          title bar that moves is not a title bar. The left half wraps; the
          right half never does. */}
      <div className="flex items-start gap-2">
      <div className="flex-1 min-w-0 flex items-baseline gap-2 flex-wrap">
        <span className="text-sm text-fg-strong">
          {/* The name the OWNER gave it wins over the one derived from the
              session id. Measured 2026-08-19: the tile said `set-core-9a` for
              an agent the owner holds as `set-core-0906`, so matching a tile
              against `sac`/journal output meant translating between two names
              for one thing — the second-place defect, inside one screen. */}
          {agent.terminal_label ?? agent.name ?? <span className="text-fg-muted">unnamed</span>}
          {/* No guessing path exists today, so this marker should never appear —
              which is exactly why it is rendered rather than assumed away. */}
          {!agent.binding_confirmed && (
            <span className="ml-1.5 text-amber-400" title="The binding to the session log did not come from a record">?</span>
          )}
        </span>
        <StateLine agent={agent} />
        {/* The declared block rides BESIDE the measured state and never instead
            of it — task 3.5. The case this exists for is the disagreement:
            measured `quiet` with the agent declaring itself blocked, which the
            tile would otherwise draw as calm. Marked only where it is
            unexpected: beside `waiting` it adds a reason, not a surprise. */}
        {blockUnexpectedFrom(agent.state, standing) && (
          <span
            data-fleet-declared-blocked={agent.pid}
            className="inline-flex items-center gap-1 text-xs text-amber-400 font-semibold whitespace-nowrap"
            title="The agent declares itself blocked while the measurement says otherwise. Both are true: the state is measured from the log, the block is what the agent says. Neither replaces the other."
          >
            <span aria-hidden>⚠</span> says it is blocked
          </span>
        )}
        <Contradiction agent={agent} />
        {/* Both directions of the same relation: 7.8 upwards (who started this
            one) and 7.18 downwards (who runs under it). */}
        <Lineage agent={agent} canJumpSeat={canJumpSeat} onJumpSeat={onJumpSeat} />
        <Descendants agent={agent} canJumpPid={canJumpPid} onJumpPid={onJumpPid} />
        <span className="text-xs text-fg-muted truncate">{agent.branch ?? '—'}</span>
        <span className="ml-auto text-xs text-fg-ghost tabular-nums shrink-0">
          {age(agent.last_movement_seconds)} · {agent.pid}
        </span>
      </div>
        {/* Window controls, top right — asked for 2026-08-19. They used to be
            four sentences in a row under the excerpt, which is a paragraph
            where a title bar belongs. Every sentence survives in the tooltip
            and in `aria-label`, so nothing that had to be SAID is now unsaid. */}
        <TileControls
          agent={agent}
          ownerReachable={ownerReachable}
          logOpen={open}
          onLog={onToggle}
          enlarged={enlarged}
          onEnlarge={onEnlarge}
          focused={focused}
          onFocus={onFocus}
          terminalOpen={terminalOpen}
          onTerminal={onTerminal}
        />
      </div>

      <Purpose agent={agent} />
      <Declared standing={standing} full={enlarged || focused} blockShown={blockUnexpectedFrom(agent.state, standing)} />
      {/* More of the conversation on an unopened tile — asked for 2026-08-19:
          *"egy projektben fő agent 6-8 lesz … még jobb bele info akkor is ha
          nincs nyitva a terminál"*. A tile that shows two lines makes the
          reader open something to learn anything, and with eight agents that is
          eight openings. */}
      <Excerpt agent={agent} lines={enlarged || focused ? 8 : 4} />

      {/* Task 7.7 — the agent's own input, and task 4.4 where there is nothing
          to type into: the producer's reason stands in the input's place. */}
      <FleetInstruct agent={agent} />

      {open && <LogPanel pid={agent.pid} onClose={onToggle} tall={enlarged} />}
      {terminalOpen && offer.kind === 'available' && (
        <FleetTerminal
          label={offer.label}
          onClose={() => onTerminal(null)}
          full={focused}
          onToggleFull={onFocus}
          onFocusChange={onTyping}
        />
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
    return <span className="text-xs text-fg-ghost">start: asking the owner service…</span>
  }
  if (!owner.available) {
    return (
      <span data-fleet-start="unavailable" className="text-xs text-amber-400" title={owner.reason ?? ''}>
        no agent can be started from here: {owner.reason ?? 'the owner service is not reachable'}
      </span>
    )
  }

  if (!open) {
    return (
      <button
        data-fleet-start="offer"
        onClick={() => { setLabel(suggest()); setOpen(true); setError(null) }}
        className="text-xs text-sky-300 hover:text-sky-200 underline-offset-2 hover:underline"
        title="The framework starts it and holds it — this one will have a terminal in the browser."
      >
        + start an agent
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
        aria-label="name for the agent to start"
        className="bg-surface-panel border border-surface-line rounded px-1.5 py-0.5 text-xs text-fg-strong w-48"
      />
      <button type="submit" disabled={busy} className="text-xs text-sky-300 hover:underline disabled:opacity-50">
        {busy ? 'starting…' : 'start'}
      </button>
      <button type="button" onClick={() => setOpen(false)} className="text-xs text-fg-muted hover:text-fg-strong">
        cancel
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
        Looking for agents…
      </div>
      <p className="mt-2 text-xs text-fg-muted leading-relaxed">
        Discovery has not answered yet. This does <span className="text-fg-strong">not</span> mean no agent is
        running — until the measurement arrives, the screen states neither a count nor an emptiness.
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
        Discovery ran: no agent is running.
      </div>
      <p className="mt-2 text-xs text-fg-muted leading-relaxed tabular-nums">
        Measured at {at ? new Date(at).toLocaleTimeString() : '—'}, over {projects} known projects.
        This is a result, not a screen still loading.
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

  /**
   * Which labels have a terminal open — several at once since 2026-08-19.
   *
   * The single-terminal limit was a shape of this memory, not of the server:
   * attaching replays the buffered screen and a second viewer is the same code
   * path as the first (task 8.3). The alternative the request also floated —
   * freezing a picture of one terminal while looking at another — is refused
   * because a frozen screen is wrong exactly while something is happening on
   * it, and it looks like data while being wrong.
   */
  const setTerminals = useCallback((project: string | null, labels: string[]) => {
    writeView(project, { terminals: labels })
    setMemory({ project, view: readView(project) })
  }, [])
  const attachable = useMemo(
    () => (active?.agents ?? [])
      .filter(a => terminalOffer(a, data?.owner_reachable).kind === 'available')
      .map(a => a.terminal_label)
      .filter((l): l is string => typeof l === 'string'),
    [active, data?.owner_reachable],
  )
  const openTerminals = useMemo(
    () => resolveTerminals(remembered, attachable),
    [remembered, attachable],
  )
  const toggleTerminal = useCallback((project: string | null, label: string | null, on: boolean) => {
    if (!label) { return }
    const next = on
      ? (openTerminals.includes(label) ? openTerminals : [...openTerminals, label])
      : openTerminals.filter(l => l !== label)
    setTerminals(project, next)
  }, [openTerminals, setTerminals])

  /**
   * The agent shown ALONE — the full screen asked for on 2026-08-19.
   *
   * Kept as its own state rather than folded into `enlarged`, because they
   * answer different questions: `enlarged` is *this one is big and the others
   * are rows*, focus is *this one and nothing else*. What focus may not do is
   * make a broken sibling invisible, so the header counts what it covers —
   * see `hiddenTally` below.
   */
  const focus = resolveFocus(remembered, active?.agents.map(a => a.pid) ?? [])
  const focused = active?.agents.find(a => a.pid === focus) ?? null
  /**
   * What the full screen is COVERING — `ui-quality.md`'s rule about compaction,
   * and this layout hides the most of any on the screen.
   *
   * Counted from the hidden agents themselves, never from the difference of two
   * totals: a count taken by subtraction stays plausible while the list it
   * describes is wrong. The same `tally` the project column uses, so a hidden
   * `unknown` cannot be counted one way here and another way there.
   */
  const hidden = focused ? (active?.agents ?? []).filter(a => a.pid !== focused.pid) : []
  const hiddenTally = tally(hidden.length > 0 ? [{ name: active?.name ?? '', agents: hidden }] : [])
  const setFocus = useCallback((project: string | null, pid: number | null) => {
    writeView(project, { focus: pid })
    setMemory({ project, view: readView(project) })
  }, [])

  /**
   * Where the keyboard is. Session state, deliberately NOT remembered: it is a
   * fact about right now, and a remembered "you were typing here" would be a
   * claim about a keyboard that is somewhere else.
   */
  const [typingLabel, setTypingLabel] = useState<string | null>(null)

  /**
   * Go to an agent, wherever it is — tasks 7.8 and 7.18.
   *
   * Both directions of the lineage need the same act: find that agent on this
   * screen and put the reader in front of it. It crosses projects, because a
   * parent that started an agent in another project is exactly the case a
   * reader is trying to follow; it selects the project first, so the tile is
   * actually on screen when it is enlarged.
   *
   * Returns whether the agent is here at all, so a tile can decide whether to
   * OFFER the jump — a control that goes nowhere is the shape 8.2 forbids.
   */
  const findAgent = useCallback((match: (a: FleetAgent) => boolean) => {
    for (const p of projects) {
      const found = p.agents.find(match)
      if (found) return { project: p.name, agent: found }
    }
    return null
  }, [projects])

  const goTo = useCallback((match: (a: FleetAgent) => boolean) => {
    const hit = findAgent(match)
    if (!hit) return
    setSelected(hit.project)
    writeView(hit.project, { enlarged: hit.agent.pid })
    setMemory({ project: hit.project, view: readView(hit.project) })
  }, [findAgent])

  const canJumpSeat = useCallback((seat: string) => findAgent(a => a.seat === seat) !== null, [findAgent])
  const onJumpSeat = useCallback((seat: string) => goTo(a => a.seat === seat), [goTo])
  const canJumpPid = useCallback((pid: number) => findAgent(a => a.pid === pid) !== null, [findAgent])
  const onJumpPid = useCallback((pid: number) => goTo(a => a.pid === pid), [goTo])

  /**
   * Whose log is open — several at once, and in the grid rather than only on an
   * enlarged tile. Reading a log and choosing a layout are two acts; tying them
   * together made "what is this agent saying" cost "hide every other agent".
   */
  const openLogs = resolveLogs(remembered, active?.agents.map(a => a.pid) ?? [], enlarged)
  const toggleLog = useCallback((project: string | null, pid: number, on: boolean) => {
    const next = on
      ? (openLogs.includes(pid) ? openLogs : [...openLogs, pid])
      : openLogs.filter(p => p !== pid)
    writeView(project, { logs: next })
    setMemory({ project, view: readView(project) })
  }, [openLogs])

  // Discovery has never answered. An error here is the real thing — there is no
  // measurement to fall back on — so it replaces the screen.
  if (!data) {
    if (error) {
      return (
        <div className="p-6 max-w-2xl" data-fleet-phase="unreachable">
          <div className="text-sm text-red-400">The fleet cannot be read: {error}</div>
          <p className="mt-2 text-xs text-fg-muted">
            Discovery has never answered, so this screen knows nothing about the running agents —
            which is not the same as there being none.
          </p>
        </div>
      )
    }
    return <Looking />
  }

  return (
    <div className="h-full flex flex-col" data-fleet-phase={data.agents === 0 ? 'answered-empty' : 'answered'}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 md:px-6 py-2.5 border-b border-surface-line shrink-0">
        <span className="text-sm font-semibold text-fg-loud">Fleet</span>
        {/*
          ONE count, and it says which projects it is counting — raised
          2026-08-19. The header said `12 agent · 6 projektben` while the column
          said `12 agents · 41 projects`: the same screen, two numbers for
          "projects", and nothing saying that one was the projects holding an
          agent and the other every project known. That is the second-copy
          defect inside a single view, and the copy nobody maintains is the one
          being read. The sentence now carries both numbers and their relation,
          and the column's duplicate is gone.
        */}
        <span
          className="text-xs text-fg-muted tabular-nums"
          title="Agents discovered on this machine, and how many of the known projects are holding at least one."
        >
          {data.agents} agents in {populated.length} of {data.projects.length} projects
        </span>
        {/* The per-state counts moved into the column's attention header, which
            is where the jump to the first one lives. Two places carrying the
            same count is one place too many: the copy nobody maintains is the
            one that drifts, and it is always the one being read. */}
        {/* The caveat explains a state; with nothing in that state it is noise
            at the top of the landing screen. Rendered from the data, so it can
            never explain away a screen that has no agents on it. */}
        {data.agents > 0 && (
          <span className="text-xs text-fg-muted">
            <span className="text-fg-strong">quiet</span> does not mean nothing is happening — only that no tool
            call was open when the log was last flushed
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
            title="The owner service did not answer, so for no agent do we know whether the framework holds it. This does not mean none of them has a terminal."
          >
            the owner service is not answering — who holds the terminals is unknown, not absent
          </span>
        )}
        {/* A refresh that failed after a good answer keeps the answer — and says
            how old it is. Replacing a true screen with an error would trade a
            stale measurement for no measurement, which is the worse of the two
            on the landing screen. */}
        {error && (
          <span className="ml-auto text-xs text-amber-400" title={error}>
            the refresh failed — this is the state measured at{' '}
            {answeredAt ? new Date(answeredAt).toLocaleTimeString() : '—'}
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
                  onStarted={label => { toggleTerminal(active.name, label, true); load() }}
                />
                {/* Task 7.13 — the orphaned waiters live next to the offer that
                    would otherwise add to the pile: an instruction reporting
                    `waiters_here: 0` invites installing one. Only orphans are
                    offered, one at a time, and removal says it stops a process. */}
                <FleetWaiters />
                {/* Density is a per-project choice — task 7.5. Offered only
                    where it can change anything: with one agent there is
                    nothing to lay out, and while a tile is enlarged the grid
                    is not the arrangement in use. */}
                {!focused && enlarged === null && active.agents.length > 1 && (
                  <span className="ml-auto flex items-center gap-1 shrink-0" title="How many columns the agents are laid out in for this project">
                    <span className="text-xs text-fg-ghost">columns</span>
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
                {/* The full screen covers its siblings, so it says what it is
                    covering — and marks the states a reader would have to act
                    on. A tidy screen that reports calm it has not verified is
                    worse than a cluttered one; here the calm would be a layout
                    choice rather than a measurement. */}
                {focused && (
                  <span className="ml-auto flex items-baseline gap-2 shrink-0" data-fleet-focus-cover={hidden.length}>
                    {hidden.length > 0 && (
                      <span className="text-xs text-fg-muted tabular-nums">
                        {hidden.length} more agent(s) hidden
                      </span>
                    )}
                    {hiddenTally.unknown > 0 && (
                      <span className="text-xs text-amber-400 tabular-nums" data-fleet-focus-hidden="unknown">
                        {hiddenTally.unknown} unknown
                      </span>
                    )}
                    {hiddenTally.waiting > 0 && (
                      <span className="text-xs text-sky-300 font-semibold tabular-nums" data-fleet-focus-hidden="waiting">
                        {hiddenTally.waiting} waiting for a person
                      </span>
                    )}
                    {hiddenTally.conflicts > 0 && (
                      <span className="text-xs text-amber-400 tabular-nums" data-fleet-focus-hidden="conflicts">
                        {hiddenTally.conflicts} contradicting record(s)
                      </span>
                    )}
                    <button
                      onClick={() => setFocus(active.name, null)}
                      data-fleet-focus-exit
                      className="text-xs text-fg-muted hover:text-fg-strong underline-offset-2 hover:underline"
                    >
                      ⤡ back to the grid
                    </button>
                  </span>
                )}
                {!focused && enlarged !== null && active.agents.length > 1 && (
                  <span className="ml-auto text-xs text-fg-ghost shrink-0 tabular-nums">
                    {active.agents.length - 1} as rows — click one to switch
                  </span>
                )}
              </div>
              {/* A selected project with nothing running is not an error and not
                  an empty panel: the arrangement keeps it in the list on
                  purpose, so the right-hand side says what it measured. */}
              {active.agents.length === 0 && (
                <div className="text-sm text-fg-muted">
                  Discovery found no running agent in this project.
                  {active.archived && <span className="text-fg-ghost"> (archived project)</span>}
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
              {/* `items-start` because a stretched tile is an EMPTY tile: the
                  grid used to make every card as tall as the tallest in its
                  row, so one open terminal left its neighbour as a large empty
                  box — raised 2026-08-19 (*"az sem segít hogy különböző
                  méretűek"*). Each card now ends where its content ends, and
                  the shared minimum keeps the short ones from looking like
                  scraps. */}
              {focused ? (
                /* Full screen — one agent, the whole panel. What it covers is
                   counted in the header above, never silently dropped. */
                <AgentCard
                  key={focused.pid}
                  agent={focused}
                  enlarged
                  focused
                  open={openLogs.includes(focused.pid)}
                  onToggle={() => toggleLog(active.name, focused.pid, !openLogs.includes(focused.pid))}
                  ownerReachable={data.owner_reachable}
                  terminalOpen={openTerminals.includes(focused.terminal_label ?? '')}
                  onTerminal={label => toggleTerminal(active.name, label ?? focused.terminal_label ?? null, label !== null)}
                  onFocus={() => setFocus(active.name, null)}
                  canJumpSeat={canJumpSeat}
                  onJumpSeat={onJumpSeat}
                  canJumpPid={canJumpPid}
                  onJumpPid={onJumpPid}
                  typing={typingLabel !== null && typingLabel === focused.terminal_label}
                  onTyping={on => setTypingLabel(on ? focused.terminal_label ?? null : null)}
                />
              ) : (
              <div className={enlarged === null
                ? `grid gap-2 items-start ${GRID_COLS[columns] ?? GRID_COLS[2]}`
                : 'space-y-2'}>
              {active.agents.map(a => {
                const card = (extra: { enlarged?: boolean; open: boolean; onToggle: () => void }) => (
                  <AgentCard
                    key={a.pid}
                    agent={a}
                    /*
                      A tile that has opened something takes the whole row.
                      Raised 2026-08-19: *"a sorok megtörnek"* — with one tile
                      three times the height of its neighbour, the grid's rows
                      stop lining up and a hole opens under the short one. The
                      cause is that a log or a terminal is a different KIND of
                      element from a tile: it wants width, and it is the one
                      thing on screen the reader is actually looking at.
                    */
                    wide={extra.open || openTerminals.includes(a.terminal_label ?? '')}
                    {...extra}
                    onEnlarge={() => setEnlarged(active.name, enlarged === a.pid ? null : a.pid)}
                    /* The tile's body opens the agent, and only while it is not
                       already the enlarged one — see AgentCard's `onOpen`. */
                    onOpen={extra.enlarged ? undefined : () => setEnlarged(active.name, a.pid)}
                    ownerReachable={data.owner_reachable}
                    terminalOpen={openTerminals.includes(a.terminal_label ?? '')}
                    onTerminal={label => toggleTerminal(active.name, label ?? a.terminal_label ?? null, label !== null)}
                    onFocus={() => setFocus(active.name, a.pid)}
                    canJumpSeat={canJumpSeat}
                    onJumpSeat={onJumpSeat}
                    canJumpPid={canJumpPid}
                    onJumpPid={onJumpPid}
                    typing={typingLabel !== null && typingLabel === a.terminal_label}
                    onTyping={on => setTypingLabel(on ? a.terminal_label ?? null : null)}
                  />
                )
                const open = openLogs.includes(a.pid)
                const toggle = () => toggleLog(active.name, a.pid, !open)
                return a.pid === enlarged
                  ? card({ enlarged: true, open, onToggle: toggle })
                  : enlarged !== null
                    ? <AgentRow key={a.pid} agent={a} onSelect={() => setEnlarged(active.name, a.pid)} />
                    : card({ open, onToggle: toggle })
              })}
              </div>
              )}
            </>
          ) : (
            <div className="text-sm text-fg-muted">
              There are running agents, but none could be bound to a known project.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
