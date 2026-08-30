import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

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
import { RestoreFromEmpty, RestoreForProject } from '../components/FleetRestore'
import FleetPm from '../components/FleetPm'
import FleetBoard from '../components/FleetBoard'
import FleetWirePanel from '../components/FleetWirePanel'
import type { ChannelsPayload } from '../lib/fleetWireLayout'
import FleetUsageStrip from '../components/FleetUsageStrip'
import FleetSplitter from '../components/FleetSplitter'
import {
  MAX_PANE, MIN_PANE, SPLIT_PROJECTS, clampPane, loadSplits, positionOf, saveSplits,
  type Splits,
} from '../lib/fleetSplits'
import FleetTerminal from '../components/FleetTerminal'
import { Bot, CirclePlus, Columns2, Columns3, Columns4, EyeOff, FolderTree, Folders, Kanban, Layers, Minimize2, Presentation, Repeat, Square, TriangleAlert } from 'lucide-react'
import { Chip, Dot } from '../components/Chip'

import { age } from '../lib/fleetAge'
import { COLUMN_CHOICES, fitColumns, readView, resolveColumns, resolveEnlarged, resolveFocus, resolveLogs, resolveTerminals, writeView } from '../lib/fleetViewState'
import type { ProjectView } from '../lib/fleetViewState'
import { resolvePanels, unrenderablePanels } from '../lib/fleetPanels'
import FleetDockBand from '../components/FleetDockBand'
import FleetWorkCycle from '../components/FleetWorkCycle'
import SrOnly from '../components/SrOnly'
import {
  bandsOn, defaultDockSize, dockSplitKey, dockedBands, docksFor, loadDocks, remainingArea, saveDocks,
  withCollapsed, withDock,
  type DockEdge, type DockedView, type DockMap,
} from '../lib/fleetDocks'
import { PANEL_AGENT, PANEL_BOARD, PANEL_FILES, PANEL_WORK_CYCLE } from '../lib/fleetPanels'
import FleetFileView, { type FileRequest } from '../components/FleetFileView'
import { fileToOpen } from '../lib/fleetFiles'
import {
  agentKey, loadAgentOrders, moveKey, orderAgents, saveAgentOrder, type AgentOrderMap,
} from '../lib/fleetAgentOrder'
import { useReorder } from '../lib/useReorder'
import type { FleetAgent, FleetProject, FleetResponse } from '../lib/fleetTypes'
import { offerWithRemembered, rememberTerminalLabels, terminalOffer } from '../lib/fleetTerminal'
import type { LabelMemory } from '../lib/fleetTerminal'
import { buildActs, speakerLabel, speakerOf } from '../lib/fleetConversation'
import { OWNERSHIP_NOTE, cardClasses, ownershipOf } from '../lib/fleetCardStyle'
import { ATT_BACKGROUND, ATT_INPUT, ATT_PROMPT, ATT_WORKING, inputWaitTone, tally } from '../lib/fleetAttention'
import { WaitThresholdsContext, useWaitThresholds } from '../lib/fleetWaitThresholds'
import {
  defaultLocation, fetchStartLocations, locationLabel, offerable, selectorWorthShowing,
} from '../lib/fleetStartLocations'
import type { StartLocation } from '../lib/fleetStartLocations'
import {
  fetchProviderCatalogue, levelLabel, modelsFor, offerableProviders,
  previewResolution, providerMark,
} from '../lib/fleetProviders'
import type { ProviderCatalogue } from '../lib/fleetProviders'
import { blockUnexpectedFrom, declaredStanding, instructability, phaseRepeatsBlock, purposeStanding } from '../lib/fleetDeclared'
import { mark as cacheMark, UNMEASURED_TITLE } from '../lib/fleetCacheHeat'
import type { DeclaredStanding } from '../lib/fleetDeclared'
import FleetInstruct from '../components/FleetInstruct'
import FleetWaiters from '../components/FleetWaiters'
import FleetInstall from '../components/FleetInstall'
import FleetRename from '../components/FleetRename'
import TileControls from '../components/TileControls'
import { plainExcerpt } from '../lib/excerptText'
import FleetAgentLog, { SayRow, WorkRow } from '../components/FleetAgentLog'
import type { LogResponse } from '../components/FleetAgentLog'
import { descendantStanding, parentClaim } from '../lib/fleetLineage'
import { currentSelection, tileClickCollapses, tileClickOpens } from '../lib/fleetTileClick'
import type { Speaker } from '../lib/fleetConversation'


/*
  ONE size for every branch — *"quiet main feliratok kulon fontméret?????"*,
  asked on 2026-08-19, and it was not a misreading.

  Measured from the source, not from the picture: nothing between `body` and
  this span sets a font size (`grep -n 'font-size' src/index.css` → only the
  none; the card, the grid and the title row carry no `text-*`). So these five
  branches inherited the browser default of **16px**, while the agent's NAME
  beside them is `text-sm` (14px) and its branch is `text-xs` (12px). Three
  sizes in one row, with the largest spent on the least important word.

  The size belongs here rather than on the row, because `StateLine` is rendered
  in two places — the tile and the compact row — and a size supplied by the
  caller is a second copy that drifts the moment one caller is restyled.
*/
/**
 * What typing at this session now would do — the question the reader is really
 * asking of the fleet.
 *
 * The user's own framing, 2026-08-28: a message written into a working session
 * is *pointless*. It is not lost — the runtime queues it — but nothing happens
 * until the turn ends, and the difference is exactly what the four-value status
 * can answer and the log cannot.
 */
function Queues({ queued }: { queued: boolean }) {
  return (
    <span
      className="text-fg-ghost font-normal"
      data-fleet-write-effect={queued ? 'queued' : 'now'}
      title={queued
        ? 'A message sent now is queued — it is picked up when the current work ends.'
        : 'The prompt is free: a message sent now is acted on immediately.'}
    >
      {queued ? '· queues' : '· acts now'}
    </span>
  )
}

/**
 * How long a person has been waited for, coloured by the escalation.
 *
 * The tooltip carries the one caveat that cannot be measured away: the status
 * tracks the SESSION LOOP, not the person. Somebody standing at the keyboard
 * typing an answer keeps the wait growing, because typing is not submitting.
 */
function WaitFor({ seconds }: { seconds: number | null | undefined }) {
  const tone = inputWaitTone(seconds, useWaitThresholds())
  if (tone === null) return null
  return (
    <span
      data-fleet-wait-tone={tone}
      className={`tabular-nums font-normal ${
        tone === 'red' ? 'text-rose-400' : tone === 'amber' ? 'text-amber-400' : 'text-fg-muted'
      }`}
      title={'How long this session has been waiting, from the runtime\'s own record. '
        + 'It tracks the SESSION, not the person — it keeps growing while somebody is typing an answer.'}
    >
      {age(seconds as number)}
    </span>
  )
}

function StateLine({ agent }: { agent: FleetAgent }) {
  const thresholds = useWaitThresholds()
  // Waiting for a person, with a command the agent launched still running.
  //
  // It renders as a WAIT with a background note, not as its own calm state.
  // The first version had it the other way round and stayed silent for a
  // session that had been waiting 20 minutes with a question on screen, because
  // a `dev` server was up — the runtime's own base status there is `idle`.
  if (agent.state === 'quiet' && agent.attention === ATT_BACKGROUND) {
    const tone = inputWaitTone(agent.input_wait_seconds, thresholds)
    const parked = tone === 'parked'
    return (
      <span
        className={`inline-flex items-center gap-1.5 text-xs whitespace-nowrap ${
          tone === 'red' ? 'text-rose-400 font-semibold'
            : tone === 'amber' ? 'text-amber-400 font-semibold'
              : parked ? 'text-fg-ghost' : 'text-fg-muted'
        }`}
        data-fleet-attention={ATT_BACKGROUND}
        data-fleet-parked={parked ? 'true' : undefined}
        title="The turn ended and the prompt is free, so a person is needed — but a command this agent launched (a dev server, a monitor) is still running, which is why it can look busy."
      >
        <span className={`shrink-0 ${
          parked ? 'w-1.5 h-1.5 rotate-45 border border-fg-ghost'
            : `w-1.5 h-1.5 rounded-full ${
              tone === 'red' ? 'bg-rose-400' : tone === 'amber' ? 'bg-amber-400' : 'bg-fg-muted'}`
        }`} />
        {parked ? 'parked' : 'waiting for input'}
        <WaitFor seconds={agent.input_wait_seconds} />
        <span className="text-fg-ghost font-normal" title="a command this agent launched is still running">
          · bg command
        </span>
        <Queues queued={false} />
      </span>
    )
  }
  // The turn ended and nothing is running: this session is waiting for input,
  // and it is the only class where writing to it is acted on immediately.
  if (agent.state === 'quiet' && agent.attention === ATT_INPUT) {
    const tone = inputWaitTone(agent.input_wait_seconds, thresholds)
    const parked = tone === 'parked'
    return (
      <span
        className={`inline-flex items-center gap-1.5 text-xs whitespace-nowrap ${
          tone === 'red' ? 'text-rose-400 font-semibold'
            : tone === 'amber' ? 'text-amber-400 font-semibold'
              : parked ? 'text-fg-ghost' : 'text-fg-muted'
        }`}
        data-fleet-attention={ATT_INPUT}
        data-fleet-parked={parked ? 'true' : undefined}
        title={parked
          ? 'Waiting for a person for over 15 minutes. Counted, but not treated as urgent — nobody is standing on it, and a mark that shouts for two hours takes the colour away from the wait you are actually working with.'
          : "Measured from the runtime's own record: the turn ended and nothing is running."}
      >
        <span className={`shrink-0 ${
          parked ? 'w-1.5 h-1.5 rotate-45 border border-fg-ghost'
            : `w-1.5 h-1.5 rounded-full ${
              tone === 'red' ? 'bg-rose-400' : tone === 'amber' ? 'bg-amber-400' : 'bg-fg-muted'}`
        }`} />
        {parked ? 'parked' : 'waiting for input'}
        <WaitFor seconds={agent.input_wait_seconds} />
        {/* When a PERSON last wrote here — the signal that separates the agent
            you are working with from the one you let go. Shown on the parked
            branch, where it is the fact that decides whether to go back. */}
        {parked && typeof agent.last_human_input_seconds === 'number' && (
          <span className="text-fg-ghost font-normal"
                title="when a person last wrote into this session">
            · you: {age(agent.last_human_input_seconds)}
          </span>
        )}
        <Queues queued={false} />
      </span>
    )
  }
  if (agent.state === 'working') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400 whitespace-nowrap">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
        <span>{agent.tool ?? 'working'}</span>
        {agent.tool_elapsed_seconds !== null && (
          <span className="text-fg-muted tabular-nums">{age(agent.tool_elapsed_seconds)}</span>
        )}
        {agent.other_tools.length > 0 && <span className="text-fg-muted">+{agent.other_tools.length}</span>}
        <Queues queued />
      </span>
    )
  }
  if (agent.state === 'unknown') {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-amber-400 whitespace-nowrap" title={agent.unknown_reason ?? ''}>
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
        className="inline-flex items-center gap-1.5 text-xs text-sky-300 font-semibold whitespace-nowrap"
        data-fleet-attention={ATT_PROMPT}
        title={why ?? 'The session is waiting for a person. What for was not written down by the runtime — the state is measured either way.'}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-sky-300 shrink-0" />
        waiting for an answer
        {why
          ? <span className="text-fg-muted font-normal truncate max-w-[16rem]">{why}</span>
          : <span className="text-fg-ghost font-normal">(what for was not written down)</span>}
        <WaitFor seconds={agent.input_wait_seconds} />
      </span>
    )
  }
  // MEASURED that a person is being asked — a question tool is outstanding.
  // Louder than `waiting`, which is the runtime's declaration about itself:
  // this one needs nobody's word for it, and it is the state a reader can
  // always clear. Named `asking` rather than `blocked` because the tile also
  // carries `declared.blocked`, which is the agent's own claim about something
  // else entirely.
  if (agent.state === 'asking') {
    return (
      <span
        className="inline-flex items-center gap-1.5 text-xs text-sky-300 font-semibold whitespace-nowrap"
        data-fleet-attention={ATT_PROMPT}
        title={`This agent has ${agent.tool ?? 'a question tool'} open — it is stopped in front of a person. Measured from the session log, not declared.`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-sky-300 animate-pulse shrink-0" />
        asking you
        {agent.tool && <span className="text-fg-muted font-normal">{agent.tool}</span>}
        {agent.tool_elapsed_seconds !== null && (
          <span className="text-fg-muted tabular-nums font-normal">{age(agent.tool_elapsed_seconds)}</span>
        )}
      </span>
    )
  }
  // A quiet log with a RUNNING loop. Measured 2026-08-28: two live sessions were
  // `busy` in the runtime's record and `quiet` in the log at the same instant,
  // because a turn's entries are flushed in batches. This branch used to fall
  // through to the one below and print "wait unmeasured" — a measured state
  // rendered as an unmeasured one, and the calmer reading won.
  if (agent.state === 'quiet' && agent.attention === ATT_WORKING) {
    return (
      <span
        className="inline-flex items-center gap-1.5 text-xs text-emerald-400 whitespace-nowrap"
        data-fleet-attention={ATT_WORKING}
        title="The runtime's record says this session's loop is running. Its log shows no open tool call, which only means the last flush landed between calls."
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
        working
        <span className="text-fg-muted font-normal">no open call</span>
        <Queues queued />
      </span>
    )
  }
  if (agent.state === 'quiet') {
    return (
      /* The caveat lives HERE, on the word it is about. It used to run across
         the top of the landing screen as a sentence — explaining a state the
         reader might not have on screen at all, above the thing they came to
         look at. Beside the word, it is one hover away from whoever is
         actually reading it. */
      <span
        className="inline-flex items-center gap-1.5 text-xs text-fg-muted whitespace-nowrap"
        data-fleet-attention={agent.attention ?? 'none'}
        title={'“quiet” does not mean nothing is happening — only that no tool call was open when the log '
          + 'was last flushed. Whether this session is waiting for you could NOT be measured: its runtime '
          + 'record carried no status (a headless run does not write one).'}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-surface-line shrink-0" />
        quiet
        <span className="text-fg-ghost font-normal">· wait unmeasured</span>
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
    <span className="inline-flex items-center gap-1.5 text-xs text-amber-400 whitespace-nowrap"
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
        <SrOnly>contradicting declaration</SrOnly>
      ) : (
        <span className="font-normal">
          declared: <span className="line-through">{declared}</span>
        </span>
      )}
    </span>
  )
}





/**
 * What the agent has been doing, on the tile itself — B-10.
 *
 * *"nem hiszem hogy üres kellene legyen akár egy agent is, már biztosan van róla
 * valami log, info"*, and that is exactly right: the tile had ~500 px of height
 * and one sentence in it, while the same agent's log endpoint had turns and tool
 * runs to show. The first attempt at filling that space stretched the EXCERPT to
 * twelve lines, which the same reader rejected in the next breath — one long
 * message is not information, it is the same nothing spread wider.
 *
 * So the tile shows the conversation itself, in the same rows the log panel uses
 * (`SayRow`, `WorkRow`), and the excerpt above it goes back to one line.
 *
 * Only where there is nothing better in the space: a tile with its log or its
 * terminal open already has the real thing, and a second copy underneath would
 * be noise and a second poll.
 *
 * ⚠ Verbatim consumer-session content, like the excerpt — displayed and never
 * written anywhere: no `localStorage`, no cache, no committed artifact.
 */
function TileActivity({ agent, onOpenTerminal }: {
  /**
   * The whole agent, not just its pid — because this component now owns the
   * fallback the excerpt used to be, and that comes from the fleet payload
   * rather than from the log endpoint. The two sources fail independently: a
   * log this component cannot read does not take the state pass's excerpt with
   * it, and that is the case the fallback exists for.
   */
  agent: FleetAgent
  /**
   * Clicking the log hands over the LIVE terminal — asked for 2026-08-19:
   * *"ha nem terminál nézet van aktiválva akkor a jsonl-es log nézet mutassa az
   * agent dobozában a tartalmat, ha rákattintok akkor meg váltson terminálba"*.
   *
   * The two views are the same subject at two removes: the log is what was
   * said, already written down; the terminal is the thing still happening. So
   * the log is what a tile shows by default — it costs no attachment and reads
   * like text — and touching it is the natural way to ask for the live one.
   *
   * Absent where no terminal can exist (an agent the framework did not start),
   * and then the area is not clickable at all rather than clickable and inert:
   * a control that does nothing is worse than no control, because the reader
   * concludes the screen is broken instead of concluding the agent is foreign.
   */
  onOpenTerminal?: () => void
}) {
  const [log, setLog] = useState<LogResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const box = useRef<HTMLDivElement | null>(null)
  const stick = useRef(true)

  useEffect(() => {
    let cancelled = false
    const load = () => {
      fetch(`/api/fleet/agents/${agent.pid}/log?limit=20`)
        .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then(d => { if (!cancelled) { setLog(d); setError(null) } })
        .catch(e => { if (!cancelled) setError(String(e.message ?? e)) })
    }
    load()
    // Slower than the open log panel's 5 s: this runs for every tile of the
    // selected project at once, and it is context rather than the thing being
    // watched.
    const t = setInterval(load, 10_000)
    return () => { cancelled = true; clearInterval(t) }
  }, [agent.pid])

  const acts = useMemo(() => buildActs(log?.turns ?? []), [log])
  useEffect(() => {
    const el = box.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  })

  /*
    Three absences, three sentences. A blank box would claim the third while it
    might be either of the first two.

    Each carries the EXCERPT beneath it, which is what the tile used to render
    above this component unconditionally. Here it is not a second copy: these
    three branches show no conversation at all, and the excerpt comes from a
    different source — the fleet payload's state pass — so it still has
    something to say exactly when this component does not.
  */
  if (error) return (
    <>
      <div className="text-xs text-fg-ghost mt-1.5">the log cannot be read: {error}</div>
      <Excerpt agent={agent} lines={1} />
    </>
  )
  if (!log) return (
    <>
      <div className="text-xs text-fg-ghost mt-1.5">reading the log…</div>
      <Excerpt agent={agent} lines={1} />
    </>
  )
  if (acts.length === 0) return (
    <>
      <div className="text-xs text-fg-muted mt-1.5">the log is readable and holds no conversation</div>
      <Excerpt agent={agent} lines={1} />
    </>
  )

  return (
    <div
      ref={box}
      onScroll={e => {
        const el = e.currentTarget
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24
      }}
      data-fleet-tile-activity={agent.pid}
      data-fleet-own-surface="activity"
      onClick={onOpenTerminal
        ? () => {
            // A click that ends a text selection is not a request for the
            // terminal — the reader was copying a line out of the log, and
            // swapping the view under them would take it away mid-gesture.
            if (currentSelection().trim().length > 0) return
            onOpenTerminal()
          }
        : undefined}
      title={onOpenTerminal ? 'the log, as written down — click to take the live terminal' : undefined}
      className={`flex-1 min-h-0 overflow-y-auto mt-1.5 space-y-1 pr-1${onOpenTerminal ? ' cursor-pointer' : ''}`}
    >
      {acts.map((act, i) => (
        act.kind === 'say'
          ? <SayRow key={i} act={act} showThinking={false} expanded={false} onExpand={() => undefined} compact />
          : <WorkRow key={i} act={act} />
      ))}
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
/** The layout each choice produces, drawn rather than numbered. */
const COLUMN_GLYPH: Record<number, typeof Square> = {
  1: Square, 2: Columns2, 3: Columns3, 4: Columns4,
}

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
/**
 * The last thing actually said, and — when nothing else is open — the thing that
 * fills the tile.
 *
 * `grow` is what stops the taller tiles from being emptier ones. The height now
 * comes from the row rather than from this text, so without it a 355 px tile
 * would hold four lines and 200 px of nothing, which is the objection the old
 * `items-start` rule was right about. With it, the extra height becomes more of
 * the conversation — *"még jobb bele info akkor is ha nincs nyitva a terminál"*.
 *
 * Two limits, and the smaller one wins: the line clamp caps how much is shown,
 * the parent's height clips what does not fit. Neither alone is enough — a clamp
 * without a bound overflows a short tile, a bound without a clamp cuts a line in
 * half at the edge.
 */
function Excerpt({ agent, lines = 2, grow = false }: { agent: FleetAgent; lines?: number; grow?: boolean }) {
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
    <div
      className={`flex gap-1.5 mt-1 min-w-0${grow ? ' flex-1 min-h-0 overflow-hidden' : ''}`}
      // `unknown`, not `ismeretlen` — English, like the rest of the product.
      // Found 2026-08-20 by the language checker, not by eye: nothing reads this
      // value, so it never appeared on screen and never broke a test. A string
      // nobody renders and nobody asserts is exactly where a rule stops holding
      // without anyone noticing.
      data-fleet-excerpt={agent.excerpt_from ?? 'unknown'}
    >
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

/**
 * One agent while another tile is enlarged — task 7.3's remaining half.
 *
 * **It carries its input.** The requirement is explicit — *"Under any density,
 * the tile SHALL retain its state and its input"* — and the row used to drop it:
 * an agent you could instruct became uninstructable purely because you enlarged
 * a DIFFERENT tile. That is the compaction-hides-something shape applied to an
 * affordance rather than to a failure, and it is worse than hiding a fact,
 * because the reader cannot even tell that something was taken away.
 *
 * The row is a `div` and not a `button` for that reason. An input inside a
 * button is invalid, and every keystroke would also be a click on the enlarge
 * control — so the selecting button is the identity half only, and the input
 * sits beside it with its own surface marker.
 */
/**
 * The other agents as TABS, when one tile is enlarged — asked for 2026-08-19:
 * *"teljes nézetnél a nem megnyitott agenteket ne sorokba csukja ossze hanem
 * tabokat kel csinalni egy uj felső sorba"*.
 *
 * They were rows, stacked above and below the big tile, and each row was a
 * full line: name, state, branch, age, pid and an input box. With three agents
 * that is two lines of chrome around the thing you enlarged in order to see
 * more of; with eight it is eight, and the enlarged tile is back to the size it
 * had in the grid. A tab strip is one line no matter how many there are, and it
 * scrolls sideways rather than wrapping — wrapping would rebuild the problem.
 *
 * ## What a tab must still carry, and what it cannot
 *
 * `ui-quality.md`: compacting must never hide a failure. A tab is the most
 * compact thing on this screen, so everything that is an ALARM rides on it —
 * the state's colour and dot, the unconfirmed-binding mark, and the
 * contradiction. Those are the three that mean *look at this one*.
 *
 * What does NOT fit is the branch, the age and the pid — none of which is an
 * alarm — so they move into the tab's `title` and its accessible name. They are
 * findable, not lost.
 *
 * ⚠ **One thing the row could do and a tab cannot: instruct an agent without
 * selecting it.** The row carried a compact input; a tab is too small to hold
 * one honestly. The cost is one click — select the agent, then type into its
 * card — and it is stated here rather than discovered later.
 */
function AgentTabs({ agents, selected, onSelect, onMove }: {
  agents: readonly FleetAgent[]
  selected: number | null
  onSelect: (pid: number) => void
  /**
   * Move the agent at `from` to `to` — asked for 2026-08-26: *"a tabokat akarom
   * tudni húzva rendezni felül és a sorrendet mentve kialakítani"*.
   *
   * Absent, and the strip is exactly what it was: a click still selects, and no
   * gesture reorders anything. A surface that only works when a callback happens
   * to be passed is a surface that will one day be silently unarrangeable, so
   * the drag attributes are only attached when this is here.
   */
  onMove?: (from: number, to: number) => void
}) {
  const strip = useRef<HTMLDivElement | null>(null)
  /*
    A DRAG MUST NOT ALSO SELECT.

    The tab is its own handle — a tab is too small to carry a separate grip — so
    the same element receives both the gesture and the click. `preventDefault` on
    pointerdown does not stop the click, which is what keeps a plain click
    selecting; but after a real drag that click would ALSO enlarge the agent the
    reader was only moving, which is a layout change nobody asked for.

    So a move raises this flag and the next click spends it. It is cleared on
    every pointerdown rather than after a timeout: a keyboard move raises it too,
    and a flag that outlives the gesture would swallow the reader's next real
    click on some other tab.
  */
  const moved = useRef(false)
  const { handlers, dragFrom, dragTo } = useReorder(
    (from, to) => { moved.current = true; onMove?.(from, to) },
    strip,
    agents.length,
    'x',
  )
  return (
    <div
      ref={strip}
      role="tablist"
      aria-label="agents in this project"
      data-fleet-agent-tabs={agents.length}
      /* `overflow-x-auto` with `shrink-0` tabs: many agents scroll, they never
         wrap onto a second line. A tab strip that grows downwards is a row list
         with extra steps. */
      className="flex items-center gap-1 overflow-x-auto shrink-0 border-b border-surface-line pb-1 mb-2"
    >
      {agents.map((a, i) => {
        const on = a.pid === selected
        /* ONE computation per tab. The bar, the red name, the price and the
           tooltip all read `heat`, so no second expression can disagree with
           it about whether this seat is cold. */
        const heat = cacheMark(a.cache)
        const why = [
          a.terminal_label ?? a.name ?? 'unnamed',
          a.state,
          a.branch ?? 'no branch',
          `pid ${a.pid}`,
          `last moved ${age(a.last_movement_seconds)} ago`,
          /* The exact remaining time, size and cost. The bar answers "roughly
             how far along"; a decision needs "8m, then $1.96", and reading a
             tooltip is already an act of attention. */
          heat.kind === 'unmeasured' ? UNMEASURED_TITLE : heat.title,
        ].join(' · ')
        /* The tab being dragged, and where it would land — the same two marks
           the project column draws, so the reader sees the move before
           committing it rather than only afterwards. */
        const lifted = dragFrom === i
        const target = dragTo === i && dragFrom !== null && dragFrom !== i
        return (
          <button
            key={a.pid}
            role="tab"
            aria-selected={on}
            title={onMove ? `${why} — drag to reorder, or ←/→ when focused` : why}
            data-fleet-agent-tab={a.pid}
            data-fleet-agent-tab-active={on ? 'on' : undefined}
            {...(onMove
              ? {
                  ...handlers,
                  'data-drag-item': '',
                  'data-drag-index': i,
                  'data-drag-handle': agentKey(a),
                  onPointerDownCapture: () => { moved.current = false },
                }
              : {})}
            onClick={() => {
              // Spent, not merely read: the next click on any tab must select.
              if (moved.current) { moved.current = false; return }
              onSelect(a.pid)
            }}
            className={`relative shrink-0 flex items-center gap-1.5 px-2 py-1 rounded-t text-xs border-b-2 transition-colors ${
              on
                ? 'border-sky-400 text-fg-loud bg-surface-raised/60'
                : 'border-transparent text-fg-muted hover:text-fg-strong hover:bg-surface-raised/40'
            }${lifted ? ' opacity-50' : ''}${target ? ' ring-1 ring-sky-400/60' : ''}`}
          >
            {/* The state's DOT, not its word: the colour is the alarm and it
                survives at any width, while the word would be the first thing
                a narrow strip truncated. The word is in the tooltip. */}
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${TAB_DOT[a.state] ?? 'bg-amber-400'}`} aria-hidden />
            {/* The NAME goes red once the cache is cold — asked for 2026-08-27:
                *"ha full piros mar a vonal véggi akkor a felirat is legyen piros
                szinu ne csak fehér"*. Driven by the same `heat.kind` as the full
                bar and the price, so the three cannot disagree about it. */}
            <span className={`truncate max-w-[10rem]${heat.kind === 'cold' ? ' text-red-400' : ''}`}>
              {a.terminal_label ?? a.name ?? 'unnamed'}
            </span>
            {/* The price, once it decides something. While the cache lives its
                read cost is what the reader pays whatever they do; once it is
                cold, $1.96 and $.15 are different decisions. */}
            {heat.kind === 'cold' && heat.price && (
              <span className="text-red-400 shrink-0 tabular-nums" data-fleet-tab-cache-price={heat.price}>
                {heat.price}
              </span>
            )}
            {/* A seat nothing was measured on. Amber, which on this strip
                already means withheld-or-unknown — never the cold red, and
                never silence. */}
            {heat.kind === 'unmeasured' && (
              <span className="text-amber-400 shrink-0" data-fleet-tab-cache="unmeasured"
                    title={UNMEASURED_TITLE} aria-hidden>?</span>
            )}
            {/* The cooling bar: length is time, thickness is the stake. Sits on
                the tab's bottom edge, under the selection border, so it never
                competes with the state dot at the front. */}
            {heat.kind !== 'unmeasured' && (
              <span className="absolute left-1 right-1 bottom-0 flex items-end pointer-events-none"
                    style={{ height: `${heat.thickness}px` }}
                    data-fleet-tab-cache={heat.kind}
                    data-fleet-tab-cache-fill={heat.fill.toFixed(3)}
                    data-fleet-tab-cache-thickness={heat.thickness}
                    aria-hidden>
                <span className={`block h-full ${heat.colour}`} style={{ width: `${heat.fill * 100}%` }} />
              </span>
            )}
            {!a.binding_confirmed && (
              <span className="text-amber-400 shrink-0" title="The binding to the session log did not come from a record">?</span>
            )}
            {typeof a.declaration_ignored === 'string' && a.declaration_ignored !== '' && (
              <span className="text-amber-400 shrink-0" title="This agent declared a state the log refuted — open it to see which.">⚠</span>
            )}
            <SrOnly>{why}</SrOnly>
          </button>
        )
      })}
    </div>
  )
}

/**
 * The dot's colour per state, in ONE place.
 *
 * `StateLine` draws the same five states, and a second copy of this mapping
 * would drift the day a state is added — the tab would then be calm about
 * something the tile marks. Keyed by the state STRING and defaulting to amber,
 * so a state neither knows about is loud rather than invisible.
 */
const TAB_DOT: Record<string, string> = {
  working: 'bg-emerald-400 animate-pulse',
  waiting: 'bg-sky-300',
  // Measured that a person is being asked. It must have its own entry: the
  // fallback below is amber, which already means `unknown` on this strip, so
  // an unlisted state does not merely look unstyled — it looks like a
  // different state, deliberately chosen.
  asking: 'bg-sky-300 animate-pulse',
  quiet: 'bg-surface-line',
  unknown: 'bg-amber-400',
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
function Declared({ standing, full, blockShown, contentShown }: {
  standing: DeclaredStanding
  full?: boolean
  /**
   * Whether the tile is already showing the terminal or the log — B-61.
   *
   * With content on the tile this block stands down, because it is then a
   * second and staler copy of what the reader is looking at. The exception is
   * the one absence that is a fact about the FRAMEWORK rather than about the
   * agent: *we could not ask*. That is a failure, and `ui-quality.md` does not
   * let a compaction hide one.
   */
  contentShown?: boolean
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
    // An agent that says nothing, on a tile that is already showing something:
    // there is no absence worth a row here.
    if (contentShown) return null
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
    <div className="text-xs mt-1" data-fleet-declared="declared">
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
          /* ONE line on a closed tile — B-61. Two lines was already a
             compromise; with the header down to two rows the focus gets one of
             them, and the whole sentence stays in the tooltip rather than in
             the layout. An enlarged tile has the room, so it keeps the lot. */
          <span className="text-fg-normal flex-1 min-w-[14rem] truncate" title={standing.focus}>{standing.focus}</span>
        )}
        {/* The file COUNT stays on the row even when the names do not — B-61
            compacts the layout, and dropping the fact would be hiding rather
            than compacting. The names are in the tooltip, one per line. */}
        {standing.files.length > 0 && !full && (
          <span className="text-fg-ghost shrink-0 tabular-nums" title={standing.files.join('\n')}
                data-fleet-declared-files={standing.files.length}>
            {standing.files.length} file(s)
          </span>
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
      {/* The files ride ON the same row on a closed tile — a count and a
          tooltip, because the names themselves were a row of their own for a
          fact the reader almost never needs spelled out. Enlarged, there is
          room to name them. */}
      {standing.files.length > 0 && (full
        ? (
          <div className="text-fg-ghost truncate mt-0.5" title={standing.files.join('\n')}>
            {standing.files.length} file(s): {standing.files.slice(0, 8).join(', ')}
            {standing.files.length > 8 && ' …'}
          </div>
        )
        : null)}
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

function AgentCard({ agent, open, onToggle, enlarged, focused, typing, ownerReachable, terminalOpen, onTerminal, onFocus, onEnlarge, onOpen, onCollapse, onTyping, canJumpSeat, onJumpSeat, canJumpPid, onJumpPid, onDock, dockedEdge, onRenamed, projectRoot, knownFiles, onOpenFile, checkouts, home, onReveal }: {
  agent: FleetAgent
  open: boolean
  onToggle: () => void
  enlarged?: boolean
  /** The tile is alone on the panel — full screen. */
  focused?: boolean
  /** Take the whole row of the grid: something is open inside and needs width. */
  /** The reader's keyboard is in this tile's terminal. Measured, not inferred. */
  typing?: boolean
  ownerReachable?: boolean
  /** Whether THIS agent's terminal is open. Several may be open at once. */
  terminalOpen: boolean
  onTerminal: (label: string | null) => void
  /** Send this panel to an edge, or `null` to bring it back into the grid. */
  onDock?: (edge: DockEdge | null) => void
  dockedEdge?: DockEdge | null
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
   * Put this tile back where it came from — the title-bar half of `onOpen`.
   *
   * Separate from `onEnlarge` because the two answer different questions: the
   * control in the corner toggles, this one only ever CLOSES, and it is refused
   * everywhere except the title bar (see `tileClickCollapses`).
   */
  onCollapse?: () => void
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
  /**
   * The agent was renamed, from one label to another.
   *
   * The screen holds the label in three places besides the payload — which
   * terminals are open, which panel is docked, and the remembered label that
   * keeps an open terminal alive across an unanswered poll. All three are keyed
   * on the name, so the parent moves them rather than waiting for the next
   * listing: a terminal that closes itself because the name changed underneath
   * it is the opposite of the invisibility a rename promises.
   */
  onRenamed?: (from: string, to: string) => void
  /** The project's root, so a file reference in the terminal can be resolved. */
  projectRoot?: string
  /** The files that project has — see `FleetTerminal`'s prop of the same name. */
  knownFiles?: ReadonlySet<string>
  onOpenFile?: (file: { path: string; line?: number }, root: string) => void
  /** Every checkout the file endpoints serve — see `FleetTerminal`'s own note. */
  checkouts?: readonly string[]
  /** The framework account's home, for `~/` in this agent's output. */
  home?: string
  /** Reveal a directory in the file view, opening nothing. */
  onReveal?: (path: string, root: string) => void
}) {
  /**
   * B-30 — an OPEN terminal survives a poll the owner did not answer.
   *
   * The upgrade is refused for everything except `unknown`, and only while the
   * pane is already open: `foreign` and `orphaned` are the owner speaking, and a
   * remembered label must never overrule an answer. See `offerWithRemembered`.
   */
  const offer = offerWithRemembered(
    terminalOffer(agent, ownerReachable),
    agent.terminal_label ?? undefined,
    !!terminalOpen,
  )
  // Ownership decides the tile's edge — see `lib/fleetCardStyle.ts` for why it
  // is the edge's SHAPE and not a colour. The tiles used to be bordered with
  // `surface-line`, which is the same neutral-800 as the surface behind them:
  // an edge that cannot be seen, which is what made the grid read as one block.
  const ownership = ownershipOf(agent, ownerReachable)
  // Computed once: the header marker and the block below must not be able to
  // disagree about what the agent declared.
  const standing = declaredStanding(agent)
  /*
    THE TERMINAL OUTRANKS THE LOG — asked for 2026-08-19: *"csinaltam wpc-be egy
    uj agentet és erre megnyitotta a history log-ot és a terminalt is … ha van
    terminal nezet akkor meg az legyen!!!"*.

    Both really were open, and neither was a bug on its own. Starting an agent
    opens its terminal (`onStarted`), and `resolveLogs` opens the ENLARGED
    tile's log while no choice has been made — a default that is deliberate and
    tested. A newly started agent is both at once, so the tile stacked an empty
    log panel (*"no session log is bound to this agent"*) on top of the live
    terminal that had the answer.

    The rule is a precedence, not a removal: the log stays exactly as it was and
    comes back the moment the terminal closes. What may not happen is the two
    rendering together, because then the reader has to work out which of the two
    is the live one.

    And the control must not lie about it: `logOpen` is what is SHOWN, so the
    log icon is not lit for a panel the terminal is covering. Clicking it is an
    explicit choice and therefore outranks the default the other way — it closes
    the terminal and shows the log.
  */
  const logShown = open && !terminalOpen
  /*
    B-61 — WHAT THE HEADER COSTS, AND WHEN.

    Reported 2026-08-22 with a picture of three agents: *"alig marad hely a
    terminal tartalmának mert tul sok helyet elvisz felette a heder … sztem 2 sor
    kellene egy layout/agent fejlécnek összesen"*. Measured on that screenshot,
    per tile, above the terminal: a title row, a two-to-three-line `says:` block,
    a `N file(s):` line, an always-open instruction box, and then the terminal's
    own row — five to six rows of chrome for about ten rows of content.

    Two decisions get it to two, and neither of them HIDES anything the reader
    was relying on:

    - the instruction box opens from a control (see `TileControls`), because a
      box nobody has typed into is not information;
    - the `says:` block becomes ONE row: the focus takes a single line with the
      whole sentence in its tooltip, and the file NAMES — a row of their own —
      become a count on the same line, names in the tooltip. Enlarged, where
      there is room, the names come back.

    What was tried and taken back out, because it crossed from compacting into
    hiding: standing the `says:` block down entirely while the terminal or the
    log is open. It reads well — the terminal is the better answer — but the
    declared focus comes from the messaging bus and the log does NOT carry it, so
    the row is the only place that fact exists. Two rows of header plus the
    terminal's own status row is the honest arithmetic here.
  */
  const [instructOpen, setInstructOpen] = useState(false)
  /*
    ONE computation, shared with the tab. Reported by the user 2026-08-27 with
    two screenshots: the mark was visible only after full-screening into the
    tabbed view — *"nem latszik a normal grid-es ablak title-ben csak ha
    fullscrenelem és a tabokban nézem"*.

    The cause was that the mark hung off the tab strip rather than off the
    agent, and the strip is drawn in one view mode only, and only where a
    project holds several agents. Measured the same day: of twelve live agents,
    the strip could carry a mark for seven.

    `cacheMark` is the same function `AgentTabs` calls, so the two surfaces
    cannot disagree about whether a seat is cold — the single-condition rule
    that requirement already imposes WITHIN a tab, applied ACROSS surfaces.
  */
  const heat = cacheMark(agent.cache)
  /*
    WHERE THE TERMINAL'S STATUS ROW LANDS — asked for 2026-08-22: *"egy sorba
    kerüljön a csempe ikonja és a layout ikon"*.

    The tile carried two icon rows for one agent: its own title bar, and the
    terminal's row directly beneath it. This is the slot the second one is drawn
    into, so there is one row instead of two.

    Held in STATE rather than a ref: a ref does not re-render, so the terminal
    would receive `null` on the pass that creates the element and never hear that
    it now exists — the row would simply be missing, silently, which is the
    failure shape this screen keeps meeting.
  */
  const [termSlot, setTermSlot] = useState<HTMLSpanElement | null>(null)
  const showLog = () => {
    if (!terminalOpen) { onToggle(); return }
    onTerminal(null)
    if (!open) onToggle()
  }
  return (
    <div
      data-fleet-enlarged={enlarged ? agent.pid : undefined}
      data-fleet-focused={focused ? agent.pid : undefined}
      data-fleet-ownership={ownership}
      data-fleet-typing={typing ? agent.pid : undefined}
      title={OWNERSHIP_NOTE[ownership]}
      data-fleet-opens={onOpen ? agent.pid : undefined}
      data-fleet-collapses={onCollapse ? agent.pid : undefined}
      onClick={onOpen || onCollapse
        ? e => {
            const where = {
              target: e.target as Element,
              card: e.currentTarget,
              selection: currentSelection(),
            }
            // Asked in one act, answered in one place. `onOpen` is absent on a
            // tile that is already open and `onCollapse` on one that is not, so
            // the two never both apply — but the order is stated rather than
            // relied upon, because a future caller passing both would otherwise
            // get whichever branch happened to be written first.
            if (onCollapse && tileClickCollapses(where)) { onCollapse(); return }
            if (onOpen && tileClickOpens(where)) onOpen()
          }
        : undefined}
      /* A COLUMN, always — it is what lets the excerpt, the log and the terminal
         take the height the row gives them instead of guessing a fraction of the
         viewport. `min-h-0` is not decoration: without it a flex child refuses to
         shrink below its content and the card grows past the panel instead of
         scrolling inside it. `flex-1` only where the card is meant to fill: the
         full-screen one, and the enlarged one in a stack of rows. */
      className={`${cardClasses(ownership, { enlarged, focused, typing })} flex flex-col min-h-0 overflow-hidden${
        focused || enlarged ? ' flex-1' : ''}${onOpen ? ' cursor-pointer' : ''}`}
    >
      {/* Two parts, so the controls stay in the corner. With everything in one
          wrapping row, a long name pushed the icons onto a second line — a
          title bar that moves is not a title bar. The left half wraps; the
          right half never does. */}
      <div className="relative flex items-start gap-2" data-fleet-tile-head={agent.pid}
           /* The same figures the tab puts in its tooltip — remaining minutes,
              size and rewrite cost — so changing view mode changes nothing about
              what is reachable, only about how much room it has. */
           title={heat.kind === 'unmeasured' ? UNMEASURED_TITLE : heat.title}>
      {/*
        NO WRAP once the terminal's row shares this line — found by LOOKING,
        2026-08-22, on the three-agent screen the merge was asked for: with the
        status row beside it the left half ran out of room and dropped `4m ·
        2657090` onto a line of its own, so a merge made to save a row gave the
        row back on exactly the tiles it was meant to help.

        Wrapping was the right behaviour while this half had the whole line: a
        long name pushed the icons onto a second row, and a title bar that moves
        is not a title bar. Now the icons are held by their own siblings, so the
        left half can truncate instead — the name keeps its `title`, and nothing
        here is a fact that disappears rather than shortens.

        Keyed on `terminalOpen`, which is STATE. The slot element's child count
        says the same thing and says it one render too late: the portal fills
        after this pass, and nothing would re-run to notice.
      */}
      <div className={`flex-1 min-w-0 flex items-baseline gap-2 ${terminalOpen ? 'flex-nowrap overflow-hidden' : 'flex-wrap'}`}>
        {/* Cold turns the name red here for the same reason it does on the tab,
            and by the same condition. A ternary rather than an appended class:
            `text-fg-strong` and `text-red-400` set the same property, so which
            one wins would be decided by stylesheet order rather than by this
            expression — a mark that is right by luck. */}
        <span className={`text-sm min-w-0 truncate ${heat.kind === 'cold' ? 'text-red-400' : 'text-fg-strong'}`}>
          {/* The name the OWNER gave it wins over the one derived from the
              session id. Measured 2026-08-19: the tile said `set-core-9a` for
              an agent the owner holds as `set-core-0906`, so matching a tile
              against `sac`/journal output meant translating between two names
              for one thing — the second-place defect, inside one screen. */}
          {/* The name is rendered INSIDE the rename control, so that editing
              replaces it rather than sitting beside it. For an agent this
              framework does not hold, the control renders its children and
              nothing else — there is no name of ours to change, and an
              offered-then-failing control is worse than an absent one. */}
          <FleetRename agent={agent} onRenamed={onRenamed}>
            {agent.terminal_label ?? agent.name ?? <span className="text-fg-muted">unnamed</span>}
          </FleetRename>
          {/* No guessing path exists today, so this marker should never appear —
              which is exactly why it is rendered rather than assumed away. */}
          {!agent.binding_confirmed && (
            <span className="ml-1.5 text-amber-400" title="The binding to the session log did not come from a record">?</span>
          )}
        </span>
        <StateLine agent={agent} />
        {/* The cache group rides AFTER the state line, not beside the name,
            because the name already carries the binding-not-confirmed marker —
            an amber `?`. Two amber question marks touching would be one glyph
            with two meanings, separable only by tooltip. Reported as latent on
            the tab strip (task 7.4); this surface is where it would have become
            live, so the two are held apart here by position AND by wording. */}
        {heat.kind === 'cold' && heat.price && (
          <span className="text-xs text-red-400 shrink-0 tabular-nums" data-fleet-tile-cache-price={heat.price}>
            {heat.price}
          </span>
        )}
        {/* The tile has room a tab does not, and it spends it on the SAME fact
            said unambiguously: `cache ?` cannot be mistaken for the bare `?`
            three words to its left. */}
        {heat.kind === 'unmeasured' && (
          <span className="text-xs text-amber-400 shrink-0 whitespace-nowrap"
                data-fleet-tile-cache="unmeasured" title={UNMEASURED_TITLE}>cache ?</span>
        )}
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
        <ProviderMarker agent={agent} />
        {/* Both directions of the same relation: 7.8 upwards (who started this
            one) and 7.18 downwards (who runs under it). */}
        <Lineage agent={agent} canJumpSeat={canJumpSeat} onJumpSeat={onJumpSeat} />
        <Descendants agent={agent} canJumpPid={canJumpPid} onJumpPid={onJumpPid} />
        <span className="text-xs text-fg-muted truncate">{agent.branch ?? '—'}</span>
        <span className="ml-auto text-xs text-fg-ghost tabular-nums shrink-0">
          {age(agent.last_movement_seconds)} · {agent.pid}
        </span>
      </div>
        {/* The terminal's own row, drawn HERE — see `termSlot` above. It sits
            left of the tile's controls, so the reader's eye goes name → what the
            terminal is doing → what can be done to the tile. Empty and
            zero-width when no terminal is open. */}
        <span ref={setTermSlot} className="flex items-center gap-1.5 min-w-0 shrink" data-fleet-terminal-slot={agent.pid} />
        {/* Window controls, top right — asked for 2026-08-19. They used to be
            four sentences in a row under the excerpt, which is a paragraph
            where a title bar belongs. Every sentence survives in the tooltip
            and in `aria-label`, so nothing that had to be SAID is now unsaid. */}
        <TileControls
          agent={agent}
          ownerReachable={ownerReachable}
          logOpen={logShown}
          onLog={showLog}
          enlarged={enlarged}
          onEnlarge={onEnlarge}
          focused={focused}
          onFocus={onFocus}
          terminalOpen={terminalOpen}
          onTerminal={onTerminal}
          onDock={onDock}
          dockedEdge={dockedEdge}
          instructOpen={instructOpen}
          /* Offered only where there is a box to open. An agent with no seat
             gets no control and keeps its one-line reason where the box would
             be — a control that opened a sentence would be a control that does
             nothing, which this screen's own rule calls worse than none. */
          onInstruct={instructability(agent).kind !== 'no' ? () => setInstructOpen(o => !o) : undefined}
        />
        {/* The cooling bar, on the header's bottom edge — the tile's equivalent
            of the tab's. Length is time, thickness is the stake, and both come
            from the same `heat` the name and the price read, so this cannot be
            full while the name is not red.

            Spans the whole header rather than sitting inline: in the grid view
            the tile IS the unit, and a bar across its head is scannable down a
            column of tiles the way the tab's is across a strip. */}
        {heat.kind !== 'unmeasured' && (
          <span className="absolute left-0 right-0 -bottom-px flex items-end pointer-events-none"
                style={{ height: `${heat.thickness}px` }}
                data-fleet-tile-cache={heat.kind}
                data-fleet-tile-cache-fill={heat.fill.toFixed(3)}
                data-fleet-tile-cache-thickness={heat.thickness}
                aria-hidden>
            <span className={`block h-full ${heat.colour}`} style={{ width: `${heat.fill * 100}%` }} />
          </span>
        )}
      </div>

      <Purpose agent={agent} />
      <Declared
        standing={standing}
        full={enlarged || focused}
        blockShown={blockUnexpectedFrom(agent.state, standing)}
        contentShown={terminalOpen || logShown}
      />
      {/* More of the conversation on an unopened tile — asked for 2026-08-19:
          *"egy projektben fő agent 6-8 lesz … még jobb bele info akkor is ha
          nincs nyitva a terminál"*. A tile that shows two lines makes the
          reader open something to learn anything, and with eight agents that is
          eight openings. */}
      {/* ONE line, then an ellipsis — B-11: *"ez a több soros first message az
          agent után értelmetlen. le kell vágni egy sorba aztán ..."*. What fills
          the tile is `TileActivity` below, not this. */}
      {/*
        THE EXCERPT MOVED INSIDE `TileActivity` — 2026-08-20, found by looking at
        the running screen rather than by any test.

        It used to render here, and its condition was `!terminalOpen &&
        !logShown` — **character for character the condition below it**. So the
        excerpt was never on screen without the activity view underneath it, and
        the activity view's newest `say` row is the same sentence: every open
        tile carried *"Most újranézem a képernyőt…"* as its excerpt and again,
        verbatim, two rows below. Two components, one render condition, one
        fact — the second-copy defect in its purest form, and no structural
        count could see it because both copies were correct.

        Deleting it outright would have been wrong: `TileActivity` reads the log
        ENDPOINT, the excerpt comes from the fleet payload's state pass, so on a
        tile whose log cannot be read the excerpt is the only thing that still
        has content. That is precisely one component's fallback, which is where
        it now lives — and one component answering *what does this tile say*
        cannot disagree with itself.
      */}

      {/* Task 7.7 — the agent's own input, and task 4.4 where there is nothing
          to type into: the producer's reason stands in the input's place.
          `terminalOpen` is passed so that reason cannot be stated over a live
          terminal — see `FleetInstruct`. */}
      <FleetInstruct agent={agent} terminalOpen={terminalOpen} boxOpen={instructOpen} />

      {!logShown && !terminalOpen && (
        <TileActivity
          agent={agent}
          onOpenTerminal={offer.kind === 'available' ? () => onTerminal(offer.label) : undefined}
        />
      )}
      {logShown && <FleetAgentLog pid={agent.pid} onClose={onToggle} />}
      {terminalOpen && offer.kind === 'available' && (
        <FleetTerminal
          label={offer.label}
          onClose={() => onTerminal(null)}
          full={focused}
          onToggleFull={onFocus}
          onFocusChange={onTyping}
          headerSlot={termSlot}
          projectRoot={projectRoot}
          knownFiles={knownFiles}
          agentCwd={agent.cwd ?? undefined}
          onOpenFile={onOpenFile}
          checkouts={checkouts}
          home={home}
          onReveal={onReveal}
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
  const [locations, setLocations] = useState<StartLocation[] | null>(null)
  const [locationsFailed, setLocationsFailed] = useState(false)
  const [cwd, setCwd] = useState(project.root)
  // `null` here means COULD NOT ASK, never "no providers declared" — the same
  // distinction the locations above draw, and for the same reason.
  const [catalogue, setCatalogue] = useState<ProviderCatalogue | null>(null)
  const [catalogueFailed, setCatalogueFailed] = useState(false)
  const [provider, setProvider] = useState<string | null>(null)
  const [model, setModel] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch('/api/fleet/owner')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(d => { if (!cancelled) setOwner(d) })
      .catch(e => { if (!cancelled) setOwner({ available: false, reason: String(e?.message ?? e) }) })
    return () => { cancelled = true }
  }, [])

  // Asked when the form opens, for the same reason the locations are.
  useEffect(() => {
    if (!open) return
    let cancelled = false
    fetchProviderCatalogue(project.name).then(answer => {
      if (cancelled) return
      setCatalogueFailed(answer === null)
      setCatalogue(answer)
    })
    return () => { cancelled = true }
  }, [open, project.name])

  // Asked when the form opens, not on every poll: a `git worktree list` per
  // project on the fleet's polling path would be paid by every reader for a
  // control almost nobody has open.
  useEffect(() => {
    if (!open) return
    let cancelled = false
    fetchStartLocations(project.name).then(answer => {
      if (cancelled) return
      if (answer === null) {
        // Not an empty list — that is the value that reads as "no worktrees".
        setLocationsFailed(true)
        setLocations(null)
        setCwd(project.root)
        return
      }
      setLocationsFailed(false)
      setLocations(answer.locations)
      setCwd(defaultLocation(answer.locations, answer.root || project.root))
    })
    return () => { cancelled = true }
  }, [open, project.name, project.root])

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
      /* A control, so it is drawn as one — the words read as part of the
         sentence the row makes, which is the same defect as the file view's
         `files` before it became a glyph. */
      <button
        data-fleet-start="offer"
        onClick={() => { setLabel(suggest()); setOpen(true); setError(null) }}
        aria-label="start an agent"
        className="p-1 rounded border border-transparent text-sky-300 hover:text-sky-200 hover:border-surface-line shrink-0"
        title="Start an agent here — the framework starts it and holds it, and this one will have a terminal in the browser."
      ><CirclePlus size={13} strokeWidth={1.75} /></button>
    )
  }

  const preview = previewResolution(catalogue, provider, model)

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
          // Only what was CHOSEN travels. Sending the previewed default would
          // record it as `request` provenance — a level nobody selected, which
          // then reads on the screen as a deliberate choice.
          body: JSON.stringify({
            label: name,
            cwd: cwd || project.root,
            ...(provider ? { provider } : {}),
            ...(model ? { model } : {}),
          }),
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
      {locations && selectorWorthShowing(locations) && (
        <select
          data-fleet-start="location"
          value={cwd}
          onChange={e => setCwd(e.target.value)}
          aria-label="working tree to start the agent in"
          title={cwd}
          className="bg-surface-panel border border-surface-line rounded px-1.5 py-0.5 text-xs text-fg-strong max-w-[14rem]"
        >
          {offerable(locations).map(loc => (
            <option key={loc.path} value={loc.path}>{locationLabel(loc)}</option>
          ))}
        </select>
      )}
      {/* 8.1 / 8.3. Every declared provider is offered; the unusable ones are
          DISABLED with the reason rather than omitted, because a provider that
          is missing from the list and one that does not exist look identical. */}
      {catalogue && (
        <select
          data-fleet-start="provider"
          value={provider ?? ''}
          onChange={e => { setProvider(e.target.value || null); setModel(null) }}
          aria-label="provider to start the agent on"
          /* ⚠ CAPPED, and it is not cosmetic. A select sizes itself to its
             LONGEST option, and the longest one here is a sentence explaining
             why a provider is unusable — so the closed control grew to ~370px
             and pushed `start` to the far edge of the viewport. Found by
             looking at the screen; every test was green. Same shape a peer
             measured on this screen the same morning, where a column grew to
             its longest sentence and slid the start button out of reach. */
          className="bg-surface-panel border border-surface-line rounded px-1.5 py-0.5 text-xs text-fg-strong max-w-[11rem]"
        >
          <option value="">provider: default</option>
          {offerableProviders(catalogue).map(p => (
            <option key={p.name} value={p.name} disabled={p.disabledReason !== null}
                    title={p.disabledReason ?? undefined}>
              {p.name}{p.disabledReason ? ' — ' + p.disabledReason : ''}
            </option>
          ))}
        </select>
      )}
      {catalogue && modelsFor(catalogue, preview.provider).length > 0 && (
        <select
          data-fleet-start="model"
          value={model ?? ''}
          onChange={e => setModel(e.target.value || null)}
          aria-label="model to start the agent on"
          className="bg-surface-panel border border-surface-line rounded px-1.5 py-0.5 text-xs text-fg-strong"
        >
          <option value="">model: default</option>
          {modelsFor(catalogue, preview.provider).map(m => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      )}
      {/* 8.2. The frame, before the click — with the LEVEL that supplies each
          half, so a start on somebody else's account is visible rather than
          discoverable afterwards from a bill. */}
      {catalogue && (
        <span
          data-fleet-start="resolved"
          className="text-xs text-fg-muted whitespace-nowrap"
          /* The levels move into the tooltip when both say the same thing. On
             screen `(machine default / machine default)` wrapped onto a second
             line and said one word twice — it is a distinction only when the
             two halves DIFFER, which is exactly when a start is spending
             somebody else's budget. */
          title={`Provider from ${levelLabel(preview.providerLevel)}, model from ${levelLabel(preview.modelLevel)}.`}
        >
          → {preview.provider ?? 'no provider'} · {preview.model ?? 'no model'}
          <span className="text-fg-ghost">
            {' '}({preview.providerLevel === preview.modelLevel
              ? levelLabel(preview.providerLevel)
              : `${levelLabel(preview.providerLevel)} / ${levelLabel(preview.modelLevel)}`})
          </span>
        </span>
      )}
      {catalogueFailed && (
        <span data-fleet-start="catalogue-unread" className="text-xs text-amber-400"
              title="The provider catalogue could not be read. This is not the same as a machine that declares none — the start will use whatever the owner resolves.">
          providers could not be read — the owner will resolve
        </span>
      )}
      <button type="submit" disabled={busy} className="text-xs text-sky-300 hover:underline disabled:opacity-50">
        {busy ? 'starting…' : 'start'}
      </button>
      <button type="button" onClick={() => setOpen(false)} className="text-xs text-fg-muted hover:text-fg-strong">
        cancel
      </button>
      {locationsFailed && (
        <span data-fleet-start="locations-unread" className="text-xs text-amber-400">
          worktrees could not be read — starting in the project root
        </span>
      )}
      {error && <span className="text-xs text-red-400" title={error}>did not start: {error}</span>}
    </form>
  )
}

/**
 * Which provider a running agent is on — tasks 8.4 and 8.5.
 *
 * Three renderings, because they are three facts and the layout must not let
 * one wear another's clothes:
 *
 *  - **unrecorded** — amber, and it SAYS unrecorded. Nobody wrote down what
 *    this agent runs on. The machine default's name here would be a claim about
 *    which account is being billed, indistinguishable from a measured one.
 *  - **project key** — amber and marked, because it is the case where the cost
 *    lands somewhere other than the reader expects and is invisible in every
 *    other way: same label, same terminal, same transcript.
 *  - **plain** — muted, and it still names the provider. An agent whose frame
 *    is never stated is one whose cost and quality the next reader assigns to
 *    the wrong frame.
 *
 * ⚠ Amber is already this screen's "look at this" colour, and it is used here
 * for the two cases that need looking at — never for the ordinary one.
 */
function ProviderMarker({ agent }: { agent: FleetAgent }) {
  // The MEASURED model comes with the cache record, and it exists for agents
  // nobody recorded a provider for — which is most of them on a running
  // machine. Passing it is what puts a model in the header at all.
  const mark = providerMark(agent.provider, agent.cache?.model)
  // ⚠ Three tones, not two, and the split moved after LOOKING at the screen.
  // `unrecorded` was amber, and every agent on a live machine is unrecorded
  // until it is started through this — so three tiles out of three shouted in
  // the colour this screen reserves for "something is wrong". A colour every
  // row wears means nothing, and the one case that genuinely needs it — a
  // credential from a project override, where the bill lands elsewhere — could
  // no longer stand out. Unrecorded stays STATED and stays distinct; it just
  // stops claiming to be a fault.
  const tone =
    mark.kind === 'mismatch' ? 'text-red-400 font-semibold'
    : mark.kind === 'override' ? 'text-amber-400'
    : mark.kind === 'unrecorded' ? 'text-fg-ghost'
    : 'text-fg-muted'
  return (
    <span
      data-fleet-provider={mark.kind}
      data-fleet-provider-pid={agent.pid}
      className={`text-xs shrink-0 whitespace-nowrap ${tone}`}
      title={mark.title}
    >
      {mark.kind === 'override' || mark.kind === 'mismatch' ? <span aria-hidden>⚠ </span> : null}
      {mark.text}
    </span>
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
      {/* The PRIMARY placement of restore, and deliberately not the obvious one.
          After a reboot no project holds an agent, so the column offers nothing
          to click — a per-project control alone would be unreachable in exactly
          the state this feature exists for. It renders nothing when the roster
          is empty, so a machine that has never recorded anything sees the panel
          it saw before. */}
      <RestoreFromEmpty />
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

  // ------------------------------------------------------------------ //
  // The project list's width — a divider position, stored on the server //
  // ------------------------------------------------------------------ //
  //
  // The default is the width this column had when it was fixed (`w-72` =
  // 18rem = 288px), so a screen with nothing stored looks exactly as it did.
  //
  // The stored value arrives asynchronously and is only applied when it EXISTS.
  // A read that fails leaves the default in place rather than resetting the pane
  // to something — a preference that could not be read is not a preference to
  // discard, and the fail direction matters: this pane can be dragged shut.
  const DEFAULT_PROJECT_WIDTH = 288
  const [projectWidth, setProjectWidth] = useState(DEFAULT_PROJECT_WIDTH)
  const [splits, setSplits] = useState<Splits>({})
  const shellRef = useRef<HTMLDivElement | null>(null)

  /**
   * Docking, keyed by PROJECT — corrected by the user 2026-08-20: *"layout nem
   * projekt szinten van hanem globálisan. ez nem jó, projekt szinten kell
   * értelmezni"*.
   *
   * This was one flat list, and the reasoning behind it was that a docked band
   * belongs to the screen rather than to a project. The reasoning was tidy and
   * the effect was not: a terminal docked in one project held the same edge in
   * every other project, and `renderDocked` below could only say *"no running
   * agent with this terminal in <the project you are looking at>"*. The whole
   * right-hand side of the screen was an empty band naming somebody else's
   * project — a false absence produced by the layout itself.
   *
   * What renders is `docks`: the SELECTED project's list and nothing else. A
   * project with no key has nothing docked, which is also what an unselected
   * screen has.
   */
  const [dockMap, setDockMap] = useState<DockMap>({})
  const docks = useMemo(() => docksFor(dockMap, selected), [dockMap, selected])

  /**
   * The wire view — the channel graph between live agents — and its toggle.
   *
   * The toggle rides the same server-backed document as the docks (its own
   * key, one PUT), so the choice survives a reload like every other
   * arrangement this screen remembers. A read failure leaves it hidden, which
   * is the default rather than a reported state: the toggle is one click to
   * retry, and a banner for it would be noise.
   */
  const [channels, setChannels] = useState<ChannelsPayload | null>(null)
  const [wiresShown, setWiresShown] = useState(false)
  /** Set the moment the user toggles. The stored value arrives from a slow
      endpoint (the layout GET runs discovery), and a late answer must never
      overwrite a click that happened while it was in flight — measured live:
      the answer landed seconds after a toggle and silently switched the view
      back off. First intent wins; the stored value only fills the initial
      render. */
  const wiresTouched = useRef(false)

  useEffect(() => {
    let cancelled = false
    fetch('/api/fleet/layout')
      .then(r => (r.ok ? r.json() : null))
      .then(body => {
        if (!cancelled && !wiresTouched.current && body && typeof body === 'object')
          setWiresShown(Boolean((body as { wires_shown?: unknown }).wires_shown))
      })
      .catch(() => { /* hidden until the toggle is used — see above */ })
    return () => { cancelled = true }
  }, [])

  const toggleWires = useCallback(() => {
    wiresTouched.current = true
    setWiresShown(prev => {
      const next = !prev
      void fetch('/api/fleet/layout/wires', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shown: next }),
      }).catch(() => { /* the local state already flipped; the write retries on the next toggle */ })
      return next
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    void loadSplits().then(stored => {
      if (cancelled) return
      setSplits(stored)
      setProjectWidth(positionOf(stored, SPLIT_PROJECTS, DEFAULT_PROJECT_WIDTH))
    })
    void loadDocks().then(stored => { if (!cancelled) setDockMap(stored) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  /**
   * Store one project's docking — the local map first, the server after.
   *
   * Only the selected project's key is touched, so docking a terminal here
   * cannot take a band apart in a project the reader is not looking at. A write
   * with no project selected is not made at all rather than made somewhere.
   */
  const writeDocks = useCallback((next: DockedView[]) => {
    if (!selected) return
    setDockMap(prev => ({ ...prev, [selected]: next }))
    void saveDocks(selected, next)
  }, [selected])

  /**
   * Dock a panel to an edge, or undock it — task 5.1 / 5.7.
   *
   * The local list changes first and is what the screen renders, so a write that
   * fails does not snap the layout back: the reader just did this, and undoing a
   * deliberate act to report an unrelated failure is worse than the failure.
   */
  const dockPanel = useCallback((kind: string, id: string, edge: DockEdge | null) => {
    writeDocks(withDock(docks, { kind, id }, edge))
  }, [docks, writeDocks])

  /**
   * Tidy a band away to a strip, or open it again — task 6.1's other half.
   *
   * Without this the collapse behaviour existed in the component and was
   * unreachable from the screen: the failure marker was written for a state
   * nobody could enter. A mechanism that cannot be reached is not a feature,
   * and it is worse than an absent one because it reads as done.
   */
  const collapseBand = useCallback((kind: string, id: string, collapsed: boolean) => {
    writeDocks(withCollapsed(docks, { kind, id }, collapsed))
  }, [docks, writeDocks])

  /** Resize one docked band. Same two-callback split as every other divider. */
  /**
   * `cap` exists for ONE caller: maximising.
   *
   * `MAX_PANE` is a DRAG limit — it stops a reader shoving a divider until the
   * panel beside it is unusable, and 900 px is a sensible ceiling for that.
   * It is the wrong ceiling for a maximise, which is a deliberate act meaning
   * *as large as this can go*: capping it there left the band at 900 of 1919 and
   * the control read as broken. Measured 2026-08-22, and reported as
   * *"a teljes képernyőt ahol csak lehet view kell elfoglalnia"*.
   *
   * What does NOT change is the room kept for whatever sits beside the band —
   * `maxBandSize` still subtracts it. A band that swallowed the screen would
   * leave the agents nowhere to be, and this screen does not hide things to make
   * one of them bigger.
   */
  const resizeBand = useCallback((key: string, px: number, commit: boolean, cap: number = MAX_PANE) => {
    const value = clampPane(px, cap)
    const next = { ...splits, [key]: value }
    setSplits(next)
    if (commit) void saveSplits(next)
  }, [splits])

  // How far the divider may travel: never so far that the panel beside it has
  // no room left. Measured against the shell rather than the window, because
  // the shell is what the two panes actually share.
  const [shellWidth, setShellWidth] = useState(0)
  useEffect(() => {
    const el = shellRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) setShellWidth(entry.contentRect.width)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  // 360px is the narrowest the agent panel stays useful at; below that the
  // tiles stop being tiles. With no measurement yet, the cap is the static one —
  // an unmeasured shell must not silently pin the divider to its minimum.
  const maxProjectWidth = shellWidth > 0 ? Math.max(MIN_PANE, Math.min(MAX_PANE, shellWidth - 360)) : MAX_PANE

  // Written on release, not per pixel. The local value is what the user is
  // looking at, so it stays whatever they dragged even if the write fails —
  // snapping the pane back to the stored value would undo a deliberate act to
  // report a failure that has nothing to do with it.
  const commitProjectWidth = useCallback((px: number) => {
    const value = clampPane(px, MAX_PANE)
    setProjectWidth(value)
    const next = { ...splits, [SPLIT_PROJECTS]: value }
    setSplits(next)
    void saveSplits(next)
  }, [splits])

  const load = useCallback(() => {
    fetch('/api/fleet/agents')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(d => { setData(d); setAnsweredAt(Date.now()); setError(null) })
      .catch(e => setError(String(e.message ?? e)))
    // The channel graph rides the same cycle. A failed answer keeps the last
    // one on screen — the wires are already labelled with their write ages, so
    // a gap between polls reads as stale data, not as silence about a failure;
    // `sourceAvailable: false` inside a payload is the only source-down signal
    // this surface trusts, because that one is a measurement.
    fetch('/api/fleet/channels')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d: ChannelsPayload) => setChannels(d))
      .catch(() => { /* keep the last graph; see above */ })
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [load])

  /**
   * pid → the label the owner last confirmed — B-30, second half.
   *
   * In a ref rather than in state, because it must not drive a render on its
   * own: it is a fallback consulted while an answer is missing, never a source
   * the screen reports from. It is rebuilt from every answered poll, so a pid
   * the owner stops listing loses its entry on that same poll.
   */
  const labelMemory = useRef<LabelMemory>({})
  if (data) {
    labelMemory.current = rememberTerminalLabels(
      labelMemory.current,
      (data.projects ?? []).flatMap(p => p.agents),
      data.owner_reachable !== false,
    )
  }
  /**
   * The projects, with one gap filled while the owner is silent — B-30.
   *
   * When the owner cannot be asked, the API sends `population: "unknown"` and
   * `terminal_label: null` for every agent, because it has nowhere to get the
   * label from and inventing one there would be a false value. Downstream,
   * though, the label is the IDENTITY of an open pane: which terminal is open,
   * which one is docked, which one has the keyboard. Losing it for one poll
   * therefore does not merely hide a tile — it takes the layout apart.
   *
   * So the label is restored from the last confirmed pairing, and ONLY the
   * label. `population` stays `unknown`, so `terminalOffer` still refuses to
   * offer a terminal that cannot be confirmed, and the header still says the
   * owner is not answering. Nothing here claims the agent is held; it claims
   * that the pane already on screen belongs to this agent, which is a fact the
   * screen itself established.
   */
  const projects = useMemo(() => {
    const raw = data?.projects ?? []
    if (!data || data.owner_reachable !== false) return raw
    return raw.map(p => ({
      ...p,
      agents: p.agents.map(a => (
        a.terminal_label ? a : { ...a, terminal_label: labelMemory.current[a.pid] ?? null }
      )),
    }))
  }, [data])
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
  /**
   * Panels this build cannot render — task 4.2.
   *
   * A stored layout outlives the build that wrote it, so a panel may name a kind
   * this build does not have. It is REPORTED rather than dropped: dropping it
   * would tell the reader they had closed something they never closed, which is
   * the false-absence class in the direction where nobody goes looking.
   *
   * The agent terminal is one kind among these, not the implicit whole — the
   * older kind-less memory (`terminals`) is read as agent panels, never
   * rewritten, so a reader who cannot write to storage does not lose a layout by
   * reading it.
   */
  const unknownPanels = useMemo(
    () => unrenderablePanels(resolvePanels(remembered)),
    [remembered],
  )
  /** Which edge this panel sits on, or null when it is in the grid. */
  /**
   * Open one file of one project in the file view, docking the view if needed.
   *
   * The default edge is the right one and it IS a default, not a rule: the band
   * carries its own dock controls, so the reader moves it wherever they want and
   * the arrangement remembers. Opening it docked rather than into the grid keeps
   * the agent grid what it is — a grid of agents — and costs the reader one drag
   * if they disagree.
   *
   * Docking through `dockPanel` rather than by writing the list here, because
   * that is the one path that also persists the arrangement. A second way of
   * adding a band is a second way for the stored layout to disagree with the
   * screen.
   */
  /*
    A DOCKED FILE VIEW IS AN OPEN ONE — found by clicking, 2026-08-22.

    The arrangement is stored, so a panel comes back docked on the next load
    without anybody calling `openFile`, and `filesOpen` knew nothing about it.
    Pressing the edge it was on then undocked it into a grid that had no reason
    to draw it, and the panel simply vanished — a control that reads as "move
    this" doing "delete this".

    So the two facts are reconciled in one direction only: a dock entry implies
    openness. The reverse is deliberately NOT true — an open panel with no entry
    is exactly the grid case.
  */
  useEffect(() => {
    const docked = docks.filter(d => d.kind === PANEL_FILES).map(d => d.id)
    if (docked.length === 0) return
    setFilesOpen(prev => (docked.every(id => prev.has(id))
      ? prev
      : new Set([...prev, ...docked])))
  }, [docks])

  /*
    WHERE THE READER WAS, per project — asked for 2026-08-22: *"files ha bezarom
    akkor mentse el hol volt hogy ha ujra kinyitom akkor ott legyen"*.

    IN MEMORY, and deliberately not in the stored arrangement: a path belongs to
    the consumer's domain, and this dashboard persists nothing derived from it
    (External Project Confidentiality). So it survives closing and re-opening the
    panel — which is what was asked — and not a reload of the page.

    Keyed by project root, because two projects' panels remember different files.
  */
  const [lastFile, setLastFile] = useState<Record<string, FileRequest>>({})
  const rememberFile = useCallback((root: string, file: FileRequest) => {
    setLastFile(prev => (prev[root]?.path === file.path && prev[root]?.line === file.line
      ? prev
      : { ...prev, [root]: file }))
  }, [])

  const openFile = useCallback((root: string, file: FileRequest) => {
    // An empty path means "just open the panel" — and that is the one case where
    // the remembered file is the answer. A named file always wins: somebody who
    // ctrl-clicked a path asked for THAT file, not for where they were before.
    const wanted = fileToOpen(file, lastFile[root])
    setFileRequest({ root, file: wanted })
    setFilesOpen(prev => (prev.has(root) ? prev : new Set([...prev, root])))
    // A band tidied away to its strip is OPEN and not visible, which is the
    // state that made the control look broken. Asking for a file un-tidies it;
    // it does not move the panel, because where it sits is the reader's arrangement.
    const band = docks.find(d => d.kind === PANEL_FILES && d.id === root)
    if (band?.collapsed) collapseBand(PANEL_FILES, root, false)
  }, [docks, collapseBand, lastFile])

  /**
   * Reveal a DIRECTORY in the panel's structure pane. Nothing opens.
   *
   * Routed through `openFile` because everything about GETTING to the panel is
   * the same act — open it if it is closed, un-tidy it if it is collapsed on a
   * strip — and only what the panel then does with the request differs. A second
   * path to the same panel would be a second place for those three steps to
   * drift.
   */
  const revealDirectory = useCallback((root: string, path: string, from?: string) => {
    openFile(root, { path, reveal: true, ...(from ? { from } : {}) })
  }, [openFile])

  /** Close it: the panel stops existing, wherever it was. */
  const closeFiles = useCallback((root: string) => {
    setFilesOpen(prev => {
      const next = new Set(prev)
      next.delete(root)
      return next
    })
    if (docks.some(d => d.kind === PANEL_FILES && d.id === root)) {
      dockPanel(PANEL_FILES, root, null)
    }
  }, [docks, dockPanel])

  /**
   * The work-cycle panel, opened per project ROOT.
   *
   * Deliberately the same three steps as the file view — open if closed, un-tidy
   * if collapsed, close from wherever it sits — rather than a second path to a
   * panel, which is a second place for those steps to drift.
   */
  const [workCycleOpen, setWorkCycleOpen] = useState<Set<string>>(new Set())
  const openWorkCycle = useCallback((root: string) => {
    setWorkCycleOpen(prev => (prev.has(root) ? prev : new Set([...prev, root])))
    const band = docks.find(d => d.kind === PANEL_WORK_CYCLE && d.id === root)
    if (band?.collapsed) collapseBand(PANEL_WORK_CYCLE, root, false)
  }, [docks, collapseBand])
  const closeWorkCycle = useCallback((root: string) => {
    setWorkCycleOpen(prev => {
      const next = new Set(prev)
      next.delete(root)
      return next
    })
    if (docks.some(d => d.kind === PANEL_WORK_CYCLE && d.id === root)) {
      dockPanel(PANEL_WORK_CYCLE, root, null)
    }
  }, [docks, dockPanel])

  /**
   * The board panel, opened per project ROOT — the same three steps as the file
   * view and the work cycle, for the reason they state: a second path to a
   * panel is a second place for those steps to drift.
   */
  const [boardOpen, setBoardOpen] = useState<Set<string>>(new Set())
  const openBoard = useCallback((root: string) => {
    setBoardOpen(prev => (prev.has(root) ? prev : new Set([...prev, root])))
    const band = docks.find(d => d.kind === PANEL_BOARD && d.id === root)
    if (band?.collapsed) collapseBand(PANEL_BOARD, root, false)
  }, [docks, collapseBand])
  const closeBoard = useCallback((root: string) => {
    setBoardOpen(prev => {
      const next = new Set(prev)
      next.delete(root)
      return next
    })
    if (docks.some(d => d.kind === PANEL_BOARD && d.id === root)) {
      dockPanel(PANEL_BOARD, root, null)
    }
  }, [docks, dockPanel])
  const [boardMax, setBoardMax] = useState<string | null>(null)
  // FULL SCREEN — the whole layout, not a grid cell. Held by project ROOT; the
  // overlay carries its own exit, so leaving the project is not the only way out.
  const [boardFullscreen, setBoardFullscreen] = useState<string | null>(null)
  // Same pattern for the file view. Its panel keeps ONE mounted instance per
  // placement; full screen is the instance's own root escaping to `fixed`, so
  // unsaved editor state survives the round trip.
  const [filesFullscreen, setFilesFullscreen] = useState<string | null>(null)
  const toggleBoardMax = useCallback((project: string | null, root: string) => {
    setBoardMax(prev => {
      const next = prev === root ? null : root
      if (next !== null) {
        writeView(project, { enlarged: null })
        setMemory({ project, view: readView(project) })
      }
      return next
    })
  }, [])

  const dockedEdgeOf = useCallback((label: string | null | undefined): DockEdge | null => (
    label ? docks.find(d => d.kind === PANEL_AGENT && d.id === label)?.edge ?? null : null
  ), [docks])

  /**
   * The agents the GRID lays out — everything not currently docked.
   *
   * A docked agent rendered in both places would be two renderings of one
   * agent, and they drift: the copy nobody is looking at while editing the
   * other is the one that goes stale. It would also mean docking gave the
   * reader a second panel rather than moving the one they had.
   */
/*
    THE HAND-MADE AGENT ORDER — asked for 2026-08-26.

    Held here rather than inside the strip because the GRID reads it too: one
    list governs both surfaces, so they cannot disagree. Loaded once, then owned
    locally and written through — the write is optimistic, so a drag shows its
    result before the server answers, and a failed write leaves the screen
    saying something the file does not. That trade is the same one the docking
    makes, and for the same reason: what is lost is one sequence, re-dragged.
  */
  const [agentOrders, setAgentOrders] = useState<AgentOrderMap>({})
  useEffect(() => {
    let dead = false
    void loadAgentOrders().then(orders => { if (!dead) setAgentOrders(orders) })
    return () => { dead = true }
  }, [])

  /*
    The dock filter FIRST, then the reader's order. A docked agent is not in the
    grid to be ordered within it — and its place in the stored list is kept for
    when it comes back, which is `moveKey`'s rule seen from the other side.
  */
  const gridAgents = useMemo(
    () => orderAgents(
      (active?.agents ?? []).filter(a => dockedEdgeOf(a.terminal_label) === null),
      active ? agentOrders[active.name] : undefined,
    ),
    [active, dockedEdgeOf, agentOrders],
  )

  /** Move an agent within the project's order, and store the result. */
  const moveAgent = useCallback((from: number, to: number) => {
    if (!active) return
    const project = active.name
    const next = moveKey(gridAgents, agentOrders[project], from, to)
    setAgentOrders(prev => ({ ...prev, [project]: next }))
    void saveAgentOrder(project, next)
  }, [active, gridAgents, agentOrders])

  /**
   * ⚠ Resolved against `gridAgents`, NOT against every agent in the project —
   * and this line is the whole of a defect found by looking at the screen on
   * 2026-08-20, which 655 green tests could not see.
   *
   * `enlarged` and `focus` name a pid that the GRID is supposed to lay out
   * specially. Resolved against every agent, docking the enlarged one left a
   * pid that the grid no longer contains: every remaining tile then took the
   * "somebody else is enlarged, so I am a tab" branch and rendered `null`. The
   * result was an entirely EMPTY panel, under a header still saying `3 agent`
   * and `2 as tabs` — a screen contradicting itself, with nothing thrown and
   * nothing to count.
   *
   * Docking a maximised panel therefore returns the grid to its ordinary
   * layout, which is also the honest reading: the maximised one is no longer
   * in the grid to be maximised within it.
   */
  const enlarged = resolveEnlarged(remembered, gridAgents.map(a => a.pid))
  /*
    WHICH FILE VIEW IS MAXIMISED — the panel's answer to the agents' `enlarged`.

    A separate value rather than widening `enlarged`, which is a pid in the
    stored view (`fleetViewState`): squeezing a non-agent into a number would
    mean a sentinel that is not a pid, and a false value in a stored field is a
    defect this repository has paid for before.

    The two are kept EXCLUSIVE at their setters, so the screen never has two
    things claiming to be the big one. That exclusivity is the whole reason this
    is not simply a boolean somewhere in the panel.

    Not remembered across a reload, unlike the agents' choice — stated rather
    than hidden: `filesOpen` is not stored either, so a reload starts with no
    file view unless the arrangement docked one.
  */
  const [filesMax, setFilesMax] = useState<string | null>(null)

  const setEnlarged = useCallback((project: string | null, pid: number | null) => {
    // One big thing at a time. Enlarging an agent puts a maximised file view
    // back into the grid rather than leaving two panels both claiming the space.
    if (pid !== null) setFilesMax(null)
    writeView(project, { enlarged: pid })
    setMemory({ project, view: readView(project) })
  }, [])

  /**
   * The TREE shortcut — clicking an agent's sub-row in the project column.
   *
   * Deliberately the SAME two acts as selecting a tile by hand: select the
   * project, then enlarge that agent. Going through `setEnlarged` rather than
   * poking the stored view directly is the whole point — one code path owns
   * the exclusivity rules (a maximised file view stands down, the memory is
   * refreshed), so a tree click cannot produce a state a tile click could not.
   * And because the enlarged pid is remembered per project and resolved
   * against the live answer on return, leaving and coming back restores the
   * same agent without this handler doing anything extra.
   */
  const focusAgentFromTree = useCallback((project: string, pid: number) => {
    setSelected(project)
    setEnlarged(project, pid)
  }, [setEnlarged])

  /**
   * A DOCKED band's size before it was maximised, so it can be put back.
   *
   * Asked for 2026-08-22: *"a teljes képernyő kell akkor is ha ki van téve 4
   * iranybol valahova"*. A docked panel is sized by its divider, so maximising
   * one is a resize to the largest the arrangement allows — and a resize that
   * cannot be undone is not a maximise, it is losing the width the reader chose.
   * Hence the remembered value, keyed by the same split key the divider uses.
   */
  const [bandRestore, setBandRestore] = useState<Record<string, number>>({})

  /** Maximise the file view, or put it back — the other half of the rule above. */
  const toggleFilesMax = useCallback((project: string | null, root: string) => {
    setFilesMax(prev => {
      const next = prev === root ? null : root
      if (next !== null) {
        writeView(project, { enlarged: null })
        setMemory({ project, view: readView(project) })
      }
      return next
    })
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
  /**
   * The labels a terminal can be attached to — or `null` when nobody could be
   * asked (B-30).
   *
   * `null` is not `[]`, and the difference is the whole defect: an empty list
   * means *the owner answered and holds nothing*, which closes every open
   * terminal; `null` means *the question was not answered*, which must close
   * nothing. The API draws exactly this distinction one layer down and the
   * screen used to flatten it on arrival.
   */
  const attachable = useMemo(
    () => (data?.owner_reachable === false
      ? null
      : (active?.agents ?? [])
        .filter(a => terminalOffer(a, data?.owner_reachable).kind === 'available')
        .map(a => a.terminal_label)
        .filter((l): l is string => typeof l === 'string')),
    [active, data?.owner_reachable],
  )
  const openTerminals = useMemo(
    () => resolveTerminals(remembered, attachable),
    [remembered, attachable],
  )
  /*
    WHICH FILES THIS PROJECT HAS — the set a terminal needs before it may offer
    a path as a link.

    Fetched once per project and only while a terminal is actually open: a
    reader looking at tiles has no use for it, and the endpoint runs `git
    ls-files` on a real tree. The file view fetches its own listing rather than
    sharing this one, because it also needs the cap and the truncation flag, and
    a set stripped of those would be the same data with the caveat removed.
  */
  const [knownFiles, setKnownFiles] = useState<Record<string, ReadonlySet<string>>>({})

  /*
    EVERY checkout the file endpoints will serve, across every project.

    Not just the active project's, and that is the point: an agent prints an
    absolute path into a second project as readily as into its own, and the
    framework may read both. What is NOT here is any listing of them — the
    browser is told which checkouts exist and asks the server about no path,
    because an endpoint answering "is there a file at X" for any path on the
    machine is the oracle `files.py` exists to refuse.

    An older server sends no `checkouts`, and the result is an empty list rather
    than a guess: the recogniser then falls back to the one checkout it holds a
    listing for, which is what it did before this field existed.
  */
  const allCheckouts = useMemo(
    () => [...new Set((data?.projects ?? []).flatMap(p => p.checkouts ?? []))],
    [data],
  )


  /*
    WHICH CHECKOUTS to list — the project's own, and every WORKTREE an open
    terminal's agent is standing in.

    One listing per project was wrong for a worktree agent, and wrong twice:
    a file it names may not exist in the project root at all, and when it does,
    it is a different file on a different branch. Reported 2026-08-26. The
    endpoint now serves a worktree of a known project, so the fix is to ask it
    for the checkout the agent is actually in.
  */
  const listingRoots = useMemo(() => {
    const roots = new Set<string>()
    if (active?.root) roots.add(active.root)
    for (const agent of active?.agents ?? []) {
      const label = agent.terminal_label
      if (!label || !openTerminals.includes(label)) continue
      if (agent.cwd) roots.add(agent.cwd)
    }
    return [...roots]
  }, [active, openTerminals])

  /* The listing arrives once per checkout, and only once a terminal is open. */
  useEffect(() => {
    if (openTerminals.length === 0) return
    const wanted = listingRoots.filter(r => !knownFiles[r])
    if (wanted.length === 0) return
    let dead = false
    for (const root of wanted) {
      void fetch(`/api/fleet/files?root=${encodeURIComponent(root)}`)
        .then(r => (r.ok ? r.json() : null))
        .then(body => {
          if (dead || !body) return
          setKnownFiles(prev => ({ ...prev, [root]: new Set<string>(body.files ?? []) }))
        })
        .catch(() => {
          // A listing that cannot be fetched means no file links for that
          // checkout, which is the correct degradation: `fileReference` refuses
          // everything without a known set, so nothing is offered that cannot
          // be opened. Silent on purpose — the terminal itself is unaffected.
        })
    }
    return () => { dead = true }
  }, [listingRoots, openTerminals.length, knownFiles])

  const toggleTerminal = useCallback((project: string | null, label: string | null, on: boolean) => {
    if (!label) { return }
    const next = on
      ? (openTerminals.includes(label) ? openTerminals : [...openTerminals, label])
      : openTerminals.filter(l => l !== label)
    setTerminals(project, next)
  }, [openTerminals, setTerminals])

  /**
   * An agent was renamed. Carry the three places this screen keys on its name.
   *
   * The server has already written the durable half — the record and the layout
   * document — so this does NOT save the docks again: it moves the local copies
   * so the screen is right immediately rather than at the next poll. A terminal
   * that closes itself, or a docked panel that empties, because the name changed
   * underneath it would be the opposite of what a rename promises.
   *
   * `labelMemory` moves too, and it is the one nobody would think of: it keeps
   * an open terminal alive across a poll the owner did not answer, and it is
   * keyed by pid but HOLDS the label. Left behind, it would re-assert the old
   * name the first time the owner went quiet.
   */
  const onAgentRenamed = useCallback((from: string, to: string) => {
    setTerminals(selected, openTerminals.map(l => (l === from ? to : l)))
    setDockMap(prev => {
      const next: Record<string, DockedView[]> = {}
      for (const [project, entries] of Object.entries(prev)) {
        next[project] = entries.map(e =>
          e.kind === PANEL_AGENT && e.id === from ? { ...e, id: to } : e)
      }
      return next
    })
    labelMemory.current = Object.fromEntries(
      Object.entries(labelMemory.current).map(([pid, label]) => [pid, label === from ? to : label]),
    )
    /* The hand-made order is keyed by the same label, so it moves with the
       rename here as well as on the server. Both, deliberately: the server's
       carry is what survives a reload, and this one is what keeps the agent
       from jumping to the end of the strip between now and the next layout
       read. */
    setAgentOrders(prev => {
      const next: AgentOrderMap = {}
      for (const [project, keys] of Object.entries(prev)) {
        const renamed = keys.map(k => (k === from ? to : k))
        next[project] = renamed.filter((k, i) => renamed.indexOf(k) === i)
      }
      return next
    })
  }, [openTerminals, selected, setTerminals])

  /**
   * The agent shown ALONE — the full screen asked for on 2026-08-19.
   *
   * Kept as its own state rather than folded into `enlarged`, because they
   * answer different questions: `enlarged` is *this one is big and the others
   * are rows*, focus is *this one and nothing else*. What focus may not do is
   * make a broken sibling invisible, so the header counts what it covers —
   * see `hiddenTally` below.
   */
  // Same rule as `enlarged` above, and the failure here is the mirror image:
  // resolved against every agent, a docked-and-focused panel would render in the
  // band AND full-screen over the grid — one agent, two renderings, drifting.
  const focus = resolveFocus(remembered, gridAgents.map(a => a.pid))
  const focused = gridAgents.find(a => a.pid === focus) ?? null
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
  /*
    A FILE SOMEBODY ASKED FOR, and which project's view should take it.

    Held here rather than inside the panel because the asker is somewhere else
    entirely — a terminal, several tiles away — and the panel may not even be
    open yet. `openFile` docks the view if it has to, then hands the request
    down; the panel clears it once taken, so a re-render cannot re-open the same
    file over the reader's later navigation.
  */
  const [fileRequest, setFileRequest] = useState<{ root: string; file: FileRequest } | null>(null)
  /*
    WHETHER THE FILE VIEW EXISTS, kept apart from WHERE IT IS.

    Two facts, and merging them is what broke it. The first build tracked only
    the dock entry, so "closed" and "not docked" were the same state: the panel
    could only live on the right, undocking WAS closing, and — reported
    2026-08-22, *"becsuktam jobbra és nem tudom kinyitni"* — a band tidied away
    to its strip counted as already open, so the control that should have brought
    it back did nothing at all.

    Now openness is this set, and placement is the dock map exactly as it is for
    an agent: an entry means an edge, no entry means the grid.
  */
  const [filesOpen, setFilesOpen] = useState<ReadonlySet<string>>(new Set())

  /*
    Is the FILE view the big one right now — ONE derived answer, asked by every
    branch that lays the panel out.

    Derived rather than read straight from `filesMax`, because a panel that is
    docked, closed, or belongs to another project is not the big one HERE: the
    grid would otherwise collapse into a column for something it is not drawing.
    The layout, the tab strip and the tile all consult this single value, so they
    cannot disagree about what is maximised.
  */
  /*
    Is the file view on screen for THIS project at all — docked or in the grid.

    One value, because the control that opens it and the control that closes it
    are the same button: a control whose label says "open" while the panel is
    already open on an edge is a control that lies about the state it is in.
  */
  const filesShowing = !!active?.root
    && (filesOpen.has(active.root) || docks.some(d => d.kind === PANEL_FILES && d.id === active.root))
  const workCycleShowing = !!active?.root
    && (workCycleOpen.has(active.root)
        || docks.some(d => d.kind === PANEL_WORK_CYCLE && d.id === active.root))
  const boardShowing = !!active?.root
    && (boardOpen.has(active.root)
        || docks.some(d => d.kind === PANEL_BOARD && d.id === active.root))

  const filesBig = filesMax !== null
    && filesMax === active?.root
    && filesOpen.has(filesMax)
    && !docks.some(d => d.kind === PANEL_FILES && d.id === filesMax)

  /*
    HOW MANY TILES THE GRID ACTUALLY DRAWS — the agents it lays out plus the
    file view when that is a tile rather than a docked band. The same two
    conditions the tile itself renders under, read once here so the layout, the
    column control and the tile cannot disagree about the count.
  */
  const fileTileInGrid = !!active?.root
    && filesOpen.has(active.root)
    && !docks.some(d => d.kind === PANEL_FILES && d.id === active.root)
  // The work cycle and the board count too — the comment above says the layout,
  // the column control and the tiles cannot disagree about this number, and the
  // work-cycle tile was missing from it (measured when the board tile landed;
  // the file view was the only project panel the count knew).
  const workCycleTileInGrid = !!active?.root
    && workCycleOpen.has(active.root)
    && !docks.some(d => d.kind === PANEL_WORK_CYCLE && d.id === active.root)
  const boardTileInGrid = !!active?.root
    && boardOpen.has(active.root)
    && !docks.some(d => d.kind === PANEL_BOARD && d.id === active.root)
  const gridTiles = gridAgents.length
    + (fileTileInGrid ? 1 : 0) + (workCycleTileInGrid ? 1 : 0) + (boardTileInGrid ? 1 : 0)
  /* The preference, clamped to what there is to lay out — see `fitColumns`. */
  const fittedColumns = fitColumns(columns, gridTiles)

  /**
   * PM mode — the fleet chooses what the reader looks at, one item at a time.
   *
   * Held here rather than in the component so leaving it returns the reader to
   * the arrangement they had: the whole grid, the docks and the selection are
   * still mounted underneath, untouched. A mode that rebuilt the screen on exit
   * would be a mode people are reluctant to try.
   */
  const [pmOn, setPmOn] = useState(false)
  /**
   * The server owns `enabled`, so the button must be told what it already is.
   *
   * Found by looking at the running screen: the mode had been turned on
   * through the API and the button still read "PM mode off". That is not a
   * cosmetic mismatch — the server keeps running judgement cycles while the
   * button says nobody asked for them, which is exactly the cost this feature
   * was designed to avoid.
   */
  useEffect(() => {
    let cancelled = false
    fetch('/api/fleet/pm')
      .then(r => (r.ok ? r.json() : null))
      .then(d => { if (!cancelled && d && typeof d.enabled === 'boolean') setPmOn(d.enabled) })
      .catch(() => { /* the toggle simply starts off; nothing about an agent changes */ })
    return () => { cancelled = true }
  }, [])
  /**
   * When the reader last put something into the fleet panel.
   *
   * ONE capture handler on the panel rather than a prop threaded through the
   * terminal and the instruct box, and the widening is deliberate: for an agent
   * the framework holds no terminal for, the instruct box is the only way to
   * answer, so a signal that watched only the terminal would protect nothing on
   * exactly those items. Typing anywhere on this panel means the reader is
   * engaged, which is the fact the freeze actually needs.
   *
   * **A CLICK counts too — 2026-08-21: *"ha nyomok egy gombot megszakad az
   * átmenet"*.** It watched `keydown` alone, so the reader who was working the
   * screen with the mouse — opening a log, switching a tab, pressing a control
   * — was measured as absent, and the countdown ran out under their hand. The
   * question this signal answers is *is somebody working here*, and a key is
   * only one of the two ways to answer it; the strip said "type anything to
   * stay", which was an accurate description of a guard that was too narrow.
   *
   * Deliberately NOT wheel or pointer MOVE. A scroll can be an idle nudge and
   * a moved cursor is not an act, so counting them would make the queue
   * unable to advance while the pointer merely rests on the panel — the
   * opposite failure, and a quieter one.
   */
  const [lastInputAt, setLastInputAt] = useState<number | null>(null)
  const noteInput = useCallback(() => setLastInputAt(Date.now()), [])
  const togglePm = useCallback(async (on: boolean) => {
    setPmOn(on)
    try {
      await fetch('/api/fleet/pm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: on }),
      })
    } catch {
      // The mode is a way of LOOKING. If the server did not hear the toggle the
      // panel simply reports what it cannot read; nothing about any agent has
      // changed either way, so there is nothing here to roll back.
    }
  }, [])

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
   * Put the agent PM mode is presenting into the agent view.
   *
   * The same jump the lineage links use, plus one thing they do not need: for an
   * agent the framework holds no terminal for, the LOG is opened.
   *
   * That half preserves a finding another session measured as B-33 while this
   * mode was being built — **3 of 20 live agents have no pty, and 2 of the 4
   * items the queue held were among them**. Half the queue. Without this the
   * mode selects an agent whose panel offers a tile and an input box it cannot
   * send through, when the log endpoint has a whole conversation to give.
   */
  const presentAgent = useCallback((pid: number) => {
    const hit = findAgent(a => a.pid === pid)
    if (!hit) return
    setSelected(hit.project)
    const opening = hit.agent.terminal_label
      ? { enlarged: pid }
      : { enlarged: pid, logs: [...readView(hit.project).logs ?? [], pid].filter((v, i, a) => a.indexOf(v) === i) }
    writeView(hit.project, opening)
    setMemory({ project: hit.project, view: readView(hit.project) })
  }, [findAgent])

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

  // ------------------------------------------------------------------ //
  // Docked views — tasks 5.3-5.7                                        //
  // ------------------------------------------------------------------ //
  const bands = useMemo(() => dockedBands(docks, splits), [docks, splits])

  /**
   * Whether docking has left the agent grid less room than it needs.
   *
   * The nesting below does the SUBTRACTION — the browser is better at it than
   * arithmetic here, and one expression of a fact cannot drift from itself. But
   * flexbox has no way to SAY it ran out: it just shrinks things, and a squeezed
   * grid looks like a small grid. So the arithmetic is done here for the one
   * thing layout cannot report, and for nothing else.
   */
  const roomLeft = useMemo(
    () => remainingArea(
      { width: shellWidth, height: shellRef.current?.clientHeight ?? 0 },
      bands, splits,
    ),
    [shellWidth, bands, splits],
  )

  /**
   * How large one band may become — measured against the shell, not assumed.
   *
   * Against the shell's own box rather than the window, because the shell is
   * what the panes actually share, and against the axis the band divides. A
   * single constant would be wrong on both counts: it cannot know the window,
   * and it cannot know which dimension it is limiting.
   */
  const maxBandSize = useCallback((edge: DockEdge) => {
    const horizontal = edge === 'left' || edge === 'right'
    const room = horizontal
      ? shellWidth - projectWidth - 360
      : (shellRef.current?.clientHeight ?? 0) - 200
    return room > MIN_PANE ? Math.min(MAX_PANE, room) : MAX_PANE
  }, [shellWidth, projectWidth])

  /**
   * The largest a band may become when MAXIMISED — the room, without the drag
   * ceiling. See `resizeBand`'s `cap` for why the two differ.
   */
  const fullBandSize = useCallback((edge: DockEdge) => {
    /*
      MEASURED AT THE MOMENT OF THE CLICK, from the shell itself.

      Two reasons, both found by watching this return 900 while the arithmetic
      said 1025. `shellWidth` is state and can be a render behind; and the
      project column is NOT inside the shell — measured 2026-08-22, shell 1620 px
      in a 1919 px window with the column and the rail taking the difference — so
      subtracting `projectWidth` from it takes the same strip away twice.

      Asking the element is one fact instead of two that have to agree.
    */
    const el = shellRef.current
    const horizontal = edge === 'left' || edge === 'right'
    const room = horizontal
      ? (el?.clientWidth ?? 0) - 360
      : (el?.clientHeight ?? 0) - 200
    return room > MIN_PANE ? room : MAX_PANE
  }, [])

  /**
   * Make a docked band as large as the arrangement allows, or put it back.
   *
   * "As large as allowed" and not "the whole window": `maxBandSize` already
   * keeps a strip for the grid beside it, because a band that swallowed the
   * screen would leave the agents with nowhere to be — and this screen's rule is
   * that compacting must never hide something. The control says so in its label
   * rather than promising a full screen it will not deliver.
   */
  const toggleBandMax = useCallback((key: string, edge: DockEdge) => {
    const now = splits[key]
    const restore = bandRestore[key]
    if (restore !== undefined) {
      setBandRestore(prev => {
        const next = { ...prev }
        delete next[key]
        return next
      })
      resizeBand(key, restore, true)
      return
    }
    setBandRestore(prev => ({ ...prev, [key]: now ?? defaultDockSize(edge) }))
    const full = fullBandSize(edge)
    resizeBand(key, full, true, full)
  }, [splits, bandRestore, resizeBand, fullBandSize])

  /** What a docked band is called on screen. */
  const dockTitle = useCallback((kind: string, id: string) => (
    kind === PANEL_AGENT ? id : `${kind} · ${id}`
  ), [])

  /**
   * How many items in this band are failing — or `null` for "could not tell".
   *
   * The three-way answer matters more than the number. For an agent band the
   * question is answerable from the live inventory; for a kind this build does
   * not have, it is NOT, and saying zero there would be a claim of calm nobody
   * measured. So the fallback is `null`, never 0.
   */
  const dockFailing = useCallback((band: { kind: string; id: string }): number | null => {
    if (band.kind !== PANEL_AGENT) return null
    const agent = active?.agents.find(a => a.terminal_label === band.id)
    if (!agent) return null
    return agent.state === 'unknown' ? 1 : 0
  }, [active])

  /**
   * What goes inside a docked band.
   *
   * An agent band renders the agent's own card — the same component the grid
   * uses, not a copy: two renderings of one agent drift, and the docked copy is
   * the one nobody looks at while editing the other. A kind this build does not
   * have renders the reason, because a blank band is indistinguishable from a
   * broken one.
   */
  const renderDocked = useCallback((band: { kind: string; id: string }) => {
    if (band.kind === PANEL_FILES) {
      /* Keyed on the project ROOT — one file view per project, whichever agent
         asked for the file. The band survives a project switch the way every
         other docked band does; it simply lists the project it was opened for. */
      const project = data?.projects.find(p => p.root === band.id)
      if (!project) {
        return (
          <div className="p-2 text-xs text-fg-muted">
            no project with this root is on the screen — the panel is kept, not closed
          </div>
        )
      }
      const bandEdge = docks.find(d => d.kind === PANEL_FILES && d.id === band.id)?.edge ?? null
      return (
        <FleetFileView
          root={project.root}
          projectName={project.name}
          request={fileRequest?.root === project.root ? fileRequest.file : null}
          initial={lastFile[project.root] ?? null}
          onOpened={f => rememberFile(project.root, f)}
          onRequestHandled={() => setFileRequest(null)}
          onClose={() => closeFiles(band.id)}
          onDock={edge => dockPanel(PANEL_FILES, band.id, edge)}
          dockedEdge={bandEdge}
          /* Maximising a DOCKED panel is a resize to the largest the
             arrangement allows — asked for 2026-08-22, and the reason the
             control is offered here at all now: *"a teljes képernyő kell akkor
             is ha ki van téve 4 iranybol valahova"*. */
          maximised={bandRestore[dockSplitKey({ kind: PANEL_FILES, id: band.id })] !== undefined}
          onMaximise={bandEdge
            ? () => toggleBandMax(dockSplitKey({ kind: PANEL_FILES, id: band.id }), bandEdge)
            : undefined}
          fullscreen={filesFullscreen === project.root}
          onFullscreen={() => setFilesFullscreen(filesFullscreen === project.root ? null : project.root ?? null)}
        />
      )
    }
    if (band.kind === PANEL_WORK_CYCLE) {
      const project = data?.projects.find(p => p.root === band.id)
      if (!project) {
        return (
          <div className="p-2 text-xs text-fg-muted">
            no project with this root is on the screen — the panel is kept, not closed
          </div>
        )
      }
      return (
        <FleetWorkCycle
          root={project.root}
          projectName={project.name}
          onClose={() => closeWorkCycle(band.id)}
        />
      )
    }
    if (band.kind === PANEL_BOARD) {
      const project = data?.projects.find(p => p.root === band.id)
      if (!project) {
        return (
          <div className="p-2 text-xs text-fg-muted">
            no project with this root is on the screen — the panel is kept, not closed
          </div>
        )
      }
      const bandEdge = docks.find(d => d.kind === PANEL_BOARD && d.id === band.id)?.edge ?? null
      return (
        <FleetBoard
          project={project.name}
          projectName={project.name}
          onClose={() => closeBoard(band.id)}
          onDock={edge => dockPanel(PANEL_BOARD, band.id, edge)}
          dockedEdge={bandEdge}
          /* Maximising a DOCKED board resizes the band, the way the docked
             files panel already does — NOT the grid's boardMax. The old wiring
             flipped the icon while arming boardMax for a grid the board was
             not in: nothing visibly happened, and the armed state starved the
             files tile on the next switch-back (reproduced 2026-08-30). */
          maximised={bandRestore[dockSplitKey({ kind: PANEL_BOARD, id: band.id })] !== undefined}
          onMaximise={bandEdge
            ? () => toggleBandMax(dockSplitKey({ kind: PANEL_BOARD, id: band.id }), bandEdge)
            : undefined}
          onOpenTarget={path => openFile(project.root, { path })}
        />
      )
    }
    if (band.kind !== PANEL_AGENT) {
      return (
        <div className="p-2 text-xs text-amber-300">
          this build has no panel of kind "{band.kind}"
        </div>
      )
    }
    const agent = active?.agents.find(a => a.terminal_label === band.id)
    if (!agent) {
      return (
        <div className="p-2 text-xs text-fg-muted">
          no running agent with this terminal in {active?.name ?? 'this project'} — the panel is kept, not closed
        </div>
      )
    }
    return (
      <AgentCard
        agent={agent}
        projectRoot={active?.root}
        knownFiles={knownFiles[agent.cwd || active?.root || '']}
        onOpenFile={active?.root ? ((f, from) => openFile(active.root as string, { ...f, from })) : undefined}
        checkouts={allCheckouts}
        home={data?.home}
        onReveal={active?.root ? ((path, from) => revealDirectory(active.root as string, path, from)) : undefined}
        enlarged
        open={openLogs.includes(agent.pid)}
        onToggle={() => toggleLog(active?.name ?? null, agent.pid, !openLogs.includes(agent.pid))}
        ownerReachable={data?.owner_reachable}
        terminalOpen={openTerminals.includes(agent.terminal_label ?? '')}
        onTerminal={label => toggleTerminal(active?.name ?? null, label ?? agent.terminal_label ?? null, label !== null)}
        /* The docked tile keeps its own dock controls, with the current edge
           shown as active. Without them a docked panel could only be taken out
           entirely, never moved to another edge — and pressing the edge it is
           already on is what makes the control a way back rather than a dead
           end. */
        onDock={agent.terminal_label
          ? edge => dockPanel(PANEL_AGENT, agent.terminal_label as string, edge)
          : undefined}
        dockedEdge={dockedEdgeOf(agent.terminal_label)}
        onRenamed={onAgentRenamed}
        canJumpSeat={canJumpSeat}
        onJumpSeat={onJumpSeat}
        canJumpPid={canJumpPid}
        onJumpPid={onJumpPid}
        typing={typingLabel !== null && typingLabel === agent.terminal_label}
        onTyping={on => setTypingLabel(on ? agent.terminal_label ?? null : null)}
      />
    )
  }, [active, data, openLogs, openTerminals, toggleLog, toggleTerminal, canJumpSeat, onJumpSeat,
      canJumpPid, onJumpPid, typingLabel, dockPanel, dockedEdgeOf, fileRequest, docks, closeFiles, rememberFile, lastFile,
      bandRestore, toggleBandMax])

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
      {/* Centred for the same reason as the project row below: this strip is
          a title, an icon toggle and two chips, and only one of those four has
          a text baseline to align to. */}
      <div className="relative flex flex-wrap items-center gap-x-3 gap-y-1 px-4 md:px-6 py-2.5 border-b border-surface-line shrink-0">
        <span className="text-sm font-semibold text-fg-loud">Fleet</span>
        {/* The toggle. It starts and stops NOTHING — turning it on does not
            instruct, start or stop any agent, and turning it off returns the
            reader to the arrangement underneath, which was never unmounted. */}
        <button
          onClick={() => void togglePm(!pmOn)}
          data-fleet-pm-toggle={pmOn ? 'on' : 'off'}
          aria-pressed={pmOn}
          aria-label={`PM mode ${pmOn ? 'on' : 'off'}`}
          className={`p-1 rounded border shrink-0 ${
            pmOn
              ? 'border-sky-400/60 bg-sky-400/10 text-sky-300'
              : 'border-surface-line text-fg-muted hover:text-fg-strong'
          }`}
          title="PM mode presents one agent at a time — whichever is waiting on you. It touches no agent, and leaving it restores this screen."
        ><Presentation size={13} strokeWidth={1.75} /></button>
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
        <Chip
          jump="fleet-agents"
          mark={<Bot size={13} strokeWidth={1.75} aria-hidden />}
          count={data.agents}
          title="Agents discovered on this machine."
          label={`${data.agents} agents`}
        />
        {/* The RATIO stays one chip, and that is the whole point of it. The
            header once said `12 agent · 6 projektben` while the column said
            `12 agents · 41 projects`: the same screen, two numbers for
            "projects", and nothing saying one counted the projects holding an
            agent and the other every project known (raised 2026-08-19). Split
            into two chips they would drift apart again; `10/53` carries the
            relation in the value itself. */}
        <Chip
          jump="fleet-projects"
          mark={<Folders size={13} strokeWidth={1.75} aria-hidden />}
          count={`${populated.length}/${data.projects.length}`}
          title="How many of the known projects are holding at least one agent."
          label={`${populated.length} of ${data.projects.length} projects hold an agent`}
        />
        {/* The per-state counts moved into the column's attention header, which
            is where the jump to the first one lives. Two places carrying the
            same count is one place too many: the copy nobody maintains is the
            one that drifts, and it is always the one being read. */}
        {/* One cause, named once. A screen that can offer no terminal ANYWHERE
            has a single reason, and stating it per row would put 22 copies of it
            on the landing screen while still not saying it is one fact. `false`
            only — an absent key is not a `false`, and an older server that says
            nothing must not be reported as a dead owner. */}
        {data.owner_reachable === false && (
          <Chip
            jump="owner-unreachable"
            data={{ 'data-fleet-owner': 'unreachable' }}
            tone="text-amber-400"
            mark={<TriangleAlert size={13} strokeWidth={1.75} aria-hidden />}
            count="?"
            title="The owner service did not answer, so for no agent do we know whether the framework holds it. This does not mean none of them has a terminal."
            label="the owner service is not answering — who holds the terminals is unknown, not absent"
          />
        )}
        {/* A refresh that failed after a good answer keeps the answer — and says
            how old it is. Replacing a true screen with an error would trade a
            stale measurement for no measurement, which is the worse of the two
            on the landing screen. */}
        {error && (
          /* The TIME is the number here — a stale screen is only readable if you
             can see how stale. `?` where even that is unknown, because a missing
             timestamp is not "just now". */
          <Chip
            jump="refresh-failed"
            tone="text-amber-400"
            mark={<TriangleAlert size={13} strokeWidth={1.75} aria-hidden />}
            count={answeredAt ? new Date(answeredAt).toLocaleTimeString() : '?'}
            title={`The refresh failed (${error}) — this is the state measured at the time shown, not now.`}
            label={`the refresh failed — this is the state measured at ${
              answeredAt ? new Date(answeredAt).toLocaleTimeString() : 'an unknown time'}`}
          />
        )}

        {/* The account quota, pushed right on the header's own line. Bars only at
            rest — asked for by the user on the built screen, and the same
            icons-and-numbers rule the chips above already follow. It fetches its
            own snapshot, so a slow usage read cannot delay anything here. */}
        <FleetUsageStrip />
      </div>

      {/* The PM strip — under the header, ABOVE the panel, and it replaces
          nothing. The queue decides which agent the screen below is showing;
          the screen below stays the screen. An earlier build made this a
          full-screen overlay and it threw away the project column, the tabs,
          the instruct box and the docks in order to show one terminal. */}
      {pmOn && (
        <FleetPm
          onPresent={presentAgent}
          onExit={() => void togglePm(false)}
          lastInputAt={lastInputAt}
        />
      )}

      {/* THE BOARD, FULL SCREEN. Outside the grid's overflow on purpose: the
          reader asked for the whole layout, and a maximised TILE only ever gets
          the room its cell can spare (that was the report — maximize that
          cannot maximise). Keyed on root, so it stays up while it is up; the
          panel's own ⛶ control is the way out, alongside each project switch. */}
      {boardFullscreen && (() => {
        const project = data?.projects.find(p => p.root === boardFullscreen)
        if (!project) return null
        return (
          // z-[60]: the app sidebar is fixed z-50 (UnifiedSidebar), and at the
          // overlay's old z-40 it painted ON TOP of the full-screen board — the
          // first column and the legend head sat hidden under it (seen on
          // screen, 2026-08-30). Full screen means the whole window.
          <div className="fixed inset-0 z-[60] bg-surface-page/95 p-3 flex" data-fleet-board-fullscreen-root={project.root}>
            <div className="flex-1 min-w-0 rounded border border-surface-line bg-surface-panel/60">
              <FleetBoard
                project={project.name}
                projectName={project.name}
                fullscreen
                onClose={() => setBoardFullscreen(null)}
                onFullscreen={() => setBoardFullscreen(null)}
                onOpenTarget={path => {
                  // The file view lives in the page BENEATH the overlay — leave
                  // full screen first, then open the artefact there.
                  setBoardFullscreen(null)
                  openFile(project.root, { path })
                }}
              />
            </div>
          </div>
        )
      })()}

      {/* One source for the escalation thresholds, wrapping BOTH the project
          column's counters and every agent tile: threading the value into one
          subtree and not the other is a screen whose row and tile disagree
          about when a wait became urgent. */}
      <WaitThresholdsContext.Provider value={data?.input_wait_thresholds ?? null}>
      <div
        className="flex-1 flex min-h-0"
        ref={shellRef}
        // Named so a test can aim at the element the handlers are actually on.
        // A test that fires at `document` would pass on a build with no handler
        // here at all, because capture from the root reaches everything.
        data-fleet-shell
        // Capture, so it fires before anything stops the event — xterm's own
        // hidden textarea and every input on the panel are covered by this one
        // handler. Only armed in PM mode: nothing else needs it.
        onKeyDownCapture={pmOn ? noteInput : undefined}
        // `pointerdown` rather than `click`: a click is only delivered after
        // the button comes back up, and a control that stops propagation or
        // re-renders on press never produces one. The press is the act.
        onPointerDownCapture={pmOn ? noteInput : undefined}
      >
        {/* Task 7.1 / D-2 — the hand-made arrangement. It renders even when
            nothing is running: a project's position is a statement about the
            project, not about who happens to be in it, so the list must not
            empty itself when the agents close. */}
        <FleetProjectColumn
          data={data}
          selected={active?.name ?? null}
          onSelect={name => setSelected(name)}
          onSelectAgent={focusAgentFromTree}
          focusedPid={enlarged}
          width={projectWidth}
          wiresShown={wiresShown}
          onToggleWires={toggleWires}
        />

        {/* The wire gutter, when shown: it takes the strip between the project
            list and the main pane, so a wire runs from an agent row's edge
            into the gutter and never across readable content. The width it
            claims is paid for by the right-edge dock bands, which yield while
            the view is shown — the trade the toggle exists to offer. */}
        {wiresShown && <FleetWirePanel payload={channels} />}

        {/* The divider between the list and the panel. Its size lives in the
            same server-side document as the arrangement, because it is the same
            kind of thing: a position set once by hand and relied on. */}
        <FleetSplitter
          axis="x"
          label="project list width"
          size={projectWidth}
          min={MIN_PANE}
          max={maxProjectWidth}
          onDrag={setProjectWidth}
          onCommit={commitProjectWidth}
        />

        {/* A COLUMN with a definite height, not a scrolling box — raised
            2026-08-19: *"nem használjuk ki a helyet jobb oldalt … azt akarom
            fixen legyen értelmes ablak mérete az agenteknek"*. Measured before
            the change on 1900×1100: the content stopped at 450 px in an 1100 px
            panel (59 % empty) with five agents, and at 292 px (73 %) with two,
            while the left column was a dense list. The cause was here: a box
            that scrolls has no height to give, so every tile below sized itself
            from its own text and the rest of the screen stayed black. The
            header keeps its natural height; the agent area takes what is left
            and does its own scrolling. */}
        {/* ------------------------------------------------------------ //
            Docked views (tasks 5.3-5.7), then whatever space is left.

            The nesting IS the geometry: left/right bands are flex siblings of
            the remaining area in a row, top/bottom in a column. Expressing it
            as nesting rather than as computed pixel offsets means the browser
            does the subtraction, so the band and the gap cannot disagree — the
            drift that produces a layout which still looks like a layout.

            The agent grid inside is handed a smaller box and is told nothing
            about what took the rest. That is what keeps the column count
            meaning what the reader chose: three columns stays three columns,
            in a narrower area.
            ------------------------------------------------------------ */}
        {/* A column wrapper so the overflow notice sits ABOVE the docked row
            rather than beside it — the shell itself is a row, and an unwrapped
            notice would become a third column of its own. */}
        <div className="flex-1 min-h-0 min-w-0 flex flex-col">
        {shellWidth > 0 && roomLeft.overflowed && (
          <div
            data-fleet-dock-overflow
            className="shrink-0 px-3 py-1 text-xs text-amber-400 border-b border-amber-500/30"
          >
            the docked views leave the agent grid less room than it needs — drag an edge back, or undock one
          </div>
        )}
        <div className="flex-1 min-h-0 min-w-0 flex flex-row" data-fleet-docked={bands.length || undefined}>
          {bandsOn(bands, 'left').map(band => (
            <FleetDockBand
              key={dockSplitKey(band)}
              band={band}
              title={dockTitle(band.kind, band.id)}
              showTitle={band.kind !== PANEL_AGENT}
              collapsed={band.collapsed === true}
              onToggleCollapsed={() => collapseBand(band.kind, band.id, band.collapsed !== true)}
              max={maxBandSize(band.edge)}
              failing={dockFailing(band)}
              onResize={px => resizeBand(dockSplitKey(band), px, false)}
              onResizeCommit={px => resizeBand(dockSplitKey(band), px, true)}
              onUndock={() => dockPanel(band.kind, band.id, null)}
            >
              {renderDocked(band)}
            </FleetDockBand>
          ))}
          <div className="flex-1 min-h-0 min-w-0 flex flex-col">
            {bandsOn(bands, 'top').map(band => (
              <FleetDockBand
                key={dockSplitKey(band)}
                band={band}
                title={dockTitle(band.kind, band.id)}
                showTitle={band.kind !== PANEL_AGENT}
                collapsed={band.collapsed === true}
                onToggleCollapsed={() => collapseBand(band.kind, band.id, band.collapsed !== true)}
                max={maxBandSize(band.edge)}
                failing={dockFailing(band)}
                onResize={px => resizeBand(dockSplitKey(band), px, false)}
                onResizeCommit={px => resizeBand(dockSplitKey(band), px, true)}
                onUndock={() => dockPanel(band.kind, band.id, null)}
              >
                {renderDocked(band)}
              </FleetDockBand>
            ))}
        <div className="flex-1 min-h-0 p-3 min-w-0 flex flex-col gap-2">
          {/* `!active` is load-bearing, and its absence was the defect. This
              read `data.agents === 0` alone, so a FLEET-wide zero replaced the
              project strip — and the strip is where `StartAgent` lives. The
              screen you land on after a reboot therefore offered no way to
              start the first agent, which is the one state where starting one
              is the only thing to do. Reported 2026-08-27 as *"itt a fejlécnek
              kellene lennie hogy tudjak ujat indítani mashogy ne tudok"*.
              Same class as the layout control that hid itself exactly when a
              reader reached for it: the zero is a fact about the fleet, not a
              reason to withdraw a project's own controls. The measurement is
              not lost — it moves next to the per-project line below. */}
          {data.agents === 0 && !active ? (
            <AnsweredEmpty at={answeredAt} projects={data.projects.length} />
          ) : active ? (
            <>
              {/* CENTRED, not baseline-aligned. Measured on the running screen:
                  the items sat at 9, 11, 12, 0, 11, 7, 11 and 0 pixels from the
                  row's top — an icon button has no text to put a baseline on,
                  so `items-baseline` pinned it to the top while every chip
                  floated at its own text baseline. With the words gone this row
                  is glyphs and digits, and glyphs align by their box. */}
              <div className="flex items-center gap-2 px-0.5 flex-wrap">
                <span className="text-sm text-fg-loud">{active.name}</span>
                <Chip
                  jump="agent-count"
                  mark={<Bot size={13} strokeWidth={1.75} aria-hidden />}
                  count={active.agents.length}
                  title={`${active.agents.length} agent(s) in this project`}
                  label={`${active.agents.length} agents`}
                />
                {/* The path KEEPS its words. It is the only thing on this row
                    that says WHICH checkout — a worktree and its host share a
                    name — so there is no mark that could stand in for it. This
                    is the line "text only where it is really needed" draws. */}
                <span className="text-xs text-fg-ghost truncate">{active.root}</span>
                <StartAgent
                  project={active}
                  onStarted={label => { toggleTerminal(active.name, label, true); load() }}
                />
                {/* The per-project act, beside the one that starts a NEW agent —
                    two different things, so two controls rather than a mode on
                    one. It renders nothing when this project has no record. */}
                <RestoreForProject project={active.name} onRestored={load} />
                {/* Task 7.13 — the orphaned waiters live next to the offer that
                    would otherwise add to the pile: an instruction reporting
                    `waiters_here: 0` invites installing one. Only orphans are
                    offered, one at a time, and removal says it stops a process. */}
                <FleetWaiters />
                {/* Task 7.15 — the modules this project has, and installing one
                    that is missing. In the project's own strip because the act
                    is a project's, not an agent's; folded shut because it is
                    the only control here that writes into a foreign tree, and
                    an offer that is always open is one somebody clicks by
                    accident. */}
                <FleetInstall project={active.name} root={active.root} capabilities={active.capabilities} />
                {/* Density is a per-project choice — task 7.5. */}
                {/* Offered whenever there is more than one agent — including
                    while a tile is open. It used to hide itself under
                    `!focused && enlarged === null`, on the reasoning that the
                    grid is not the arrangement in use. The reasoning was sound
                    and the effect was not: opening a tile is exactly when a
                    reader reaches for the layout, and the control had vanished
                    — reported twice, the second time as *"megint nem látom a
                    több oszlopos elrendezési lehetőséget. mi van itt?"*, and
                    read as lost work rather than as a hidden control.
                    So it stays, and choosing a count also closes whatever is
                    open: a control that is visible but does nothing where you
                    clicked it is worse than one that is missing. */}
                {/*
                  THE FILE VIEW'S OWN CONTROL, and it lives HERE — asked for
                  2026-08-22: *"hogy tudom csak ugy magatol megnyitni a file
                  bögészót a projektben ha nincs link?"*.

                  It used to be the word `files` in the title row, between the
                  path and *+ start an agent*, where it read as part of a
                  sentence rather than as a control — which is the same defect as
                  a divider drawn in the colour of the surface behind it: present,
                  and invisible for it.

                  So it is a button in the row that already answers *what is on
                  screen and how*, in the same visual language as the column
                  glyphs, and it is LIT while the panel is open — so it also says
                  whether the files are showing, which the word never did.

                  Rendered outside the `agents.length > 1` guard on purpose: a
                  project with one agent has files too.
                */}
                <button
                  data-fleet-files-open={active.root}
                  aria-pressed={filesShowing}
                  aria-label="the project's files"
                  title={filesShowing
                    ? "Close the project's files"
                    : "Open the project's files — the panel sits in the grid and can be sent to any edge"}
                  onClick={() => (filesShowing ? closeFiles(active.root) : openFile(active.root, { path: '' }))}
                  className={`ml-auto p-1 rounded border shrink-0 ${
                    filesShowing
                      ? 'border-surface-line bg-surface-raised/60 text-fg-strong'
                      : 'border-transparent text-fg-ghost hover:text-fg-muted'
                  }`}
                ><FolderTree size={13} strokeWidth={1.75} /></button>
                {/*
                  The work cycle, offered wherever the files are. A project that
                  has not adopted the engine still gets the panel: it is the
                  panel that SAYS so, with what is missing — a control that
                  vanishes for an unadopted project would leave the reader with
                  no way to find out why.
                */}
                <button
                  data-fleet-work-cycle-open={active.root}
                  aria-pressed={workCycleShowing}
                  aria-label="the work cycle"
                  title={workCycleShowing
                    ? 'Close the work cycle'
                    : 'Open the work cycle — what the engine can drive here, and what its runs came to'}
                  onClick={() => (workCycleShowing
                    ? closeWorkCycle(active.root)
                    : openWorkCycle(active.root))}
                  className={`p-1 rounded border shrink-0 ${
                    workCycleShowing
                      ? 'border-surface-line bg-surface-raised/60 text-fg-strong'
                      : 'border-transparent text-fg-ghost hover:text-fg-muted'
                  }`}
                ><Repeat size={13} strokeWidth={1.75} /></button>
                <button
                  data-fleet-board-open={active.root}
                  aria-pressed={boardShowing}
                  aria-label="the project's board"
                  title={boardShowing
                    ? 'Close the board'
                    : 'Open the board — the cards the project publishes, as a panel with room controls'}
                  onClick={() => (boardShowing ? closeBoard(active.root) : openBoard(active.root))}
                  className={`p-1 rounded border shrink-0 ${
                    boardShowing
                      ? 'border-surface-line bg-surface-raised/60 text-fg-strong'
                      : 'border-transparent text-fg-ghost hover:text-fg-muted'
                  }`}
                ><Kanban size={13} strokeWidth={1.75} /></button>
                {/*
                  OFFERED WHENEVER THE GRID DRAWS ANYTHING — it used to hide
                  itself under `agents.length > 1`, and that hid the one state a
                  reader cannot get out of. The default is TWO columns, so a
                  project with a single agent opened into a half-empty grid with
                  no control to fix it: *"ha csak 1 terminal van akkor nincs
                  layout grid size ikon megjelenítve … és akkor latom gridbe de
                  nem tudom beallitani 1-esbe"* (2026-08-27). A stored choice
                  outliving the agents that justified it is the same trap one
                  size down.

                  The lit glyph is the FITTED count, not the stored one, so it
                  says what is on screen rather than what was once chosen — and
                  a choice with no tiles to fill is disabled rather than
                  clickable-and-inert. The stored preference is untouched by
                  either, and rides in `data-fleet-columns-choice` so nothing
                  that needs to read it has to infer it from the lit button.
                */}
                {gridTiles > 0 && (
                  <span
                    className="flex items-center gap-1 shrink-0"
                    data-fleet-columns-choice={columns}
                    data-fleet-columns-fitted={fittedColumns}
                    title={fittedColumns === columns
                      ? 'How many columns this project is laid out in — choosing one returns to the grid'
                      : `Laid out in ${fittedColumns} column${fittedColumns > 1 ? 's' : ''}: there ${gridTiles === 1 ? 'is one tile' : `are ${gridTiles} tiles`} to place, and ${columns} is remembered for when there are more`}
                  >
                    {COLUMN_CHOICES.map(c => {
                      /* The icon SHOWS the arrangement — asked for 2026-08-19:
                         *"oszlop 1,2,3,4 helyett ikonok kellenek amin látszik
                         hogy hogy fog kinézni! layout ikonok"*. A digit names
                         the count and leaves the reader to picture it; the
                         glyph is the picture. The number stays in the label and
                         in `data-fleet-columns`, so nothing that could only
                         read the digit lost anything. */
                      const Glyph = COLUMN_GLYPH[c] ?? Columns2
                      /* A count past the tiles cannot be drawn, so it is not
                         offered as if it could: four columns holding one tile
                         is three empty columns, which is the emptiness this
                         control exists to get out of. One is always offered —
                         it is the way back from any stored choice. */
                      const unusable = c > gridTiles
                      return (
                        <button
                          key={c}
                          data-fleet-columns={c}
                          aria-pressed={c === fittedColumns}
                          disabled={unusable}
                          aria-label={`${c} column${c > 1 ? 's' : ''}`}
                          title={unusable
                            ? `${c} columns needs ${c} tiles — this project has ${gridTiles}`
                            : `${c} column${c > 1 ? 's' : ''}`}
                          onClick={() => {
                            setColumns(active.name, c)
                            setFocus(active.name, null)
                            setEnlarged(active.name, null)
                          }}
                          className={`p-1 rounded border ${
                            c === fittedColumns
                              ? 'border-surface-line bg-surface-raised/60 text-fg-strong'
                              : unusable
                                ? 'border-transparent text-fg-ghost/30 cursor-default'
                                : 'border-transparent text-fg-ghost hover:text-fg-muted'
                          }`}
                        ><Glyph size={13} strokeWidth={1.75} /></button>
                      )
                    })}
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
                      <Chip
                        jump="focus-hidden"
                        mark={<EyeOff size={13} strokeWidth={1.75} aria-hidden />}
                        count={hidden.length}
                        title={`${hidden.length} more agent(s) are covered by this full screen`}
                        label={`${hidden.length} more agents hidden`}
                      />
                    )}
                    {hiddenTally.unknown > 0 && (
                      <Chip
                        data={{ 'data-fleet-focus-hidden': 'unknown' }}
                        tone="text-amber-400"
                        mark={<Dot cls="bg-amber-400" />}
                        count={hiddenTally.unknown}
                        title={`${hiddenTally.unknown} of the covered agents are in an unknown state`}
                        label={`${hiddenTally.unknown} unknown, hidden by the full screen`}
                      />
                    )}
                    {hiddenTally.waiting > 0 && (
                      <Chip
                        data={{ 'data-fleet-focus-hidden': 'waiting' }}
                        tone="text-sky-300 font-semibold"
                        mark={<Dot cls="bg-sky-300" />}
                        count={hiddenTally.waiting}
                        title={`${hiddenTally.waiting} of the covered agents are waiting for a person`}
                        label={`${hiddenTally.waiting} waiting for a person, hidden by the full screen`}
                      />
                    )}
                    {hiddenTally.conflicts > 0 && (
                      <Chip
                        data={{ 'data-fleet-focus-hidden': 'conflicts' }}
                        tone="text-amber-400"
                        mark={<TriangleAlert size={13} strokeWidth={1.75} aria-hidden />}
                        count={hiddenTally.conflicts}
                        title={`${hiddenTally.conflicts} of the covered agents declared a state their log contradicts`}
                        label={`${hiddenTally.conflicts} contradicting records, hidden by the full screen`}
                      />
                    )}
                    <button
                      onClick={() => setFocus(active.name, null)}
                      data-fleet-focus-exit
                      aria-label="back to the grid"
                      title="Back to the grid — stop covering the other agents"
                      className="p-1 rounded border border-transparent text-fg-muted hover:text-fg-strong shrink-0"
                    ><Minimize2 size={13} strokeWidth={1.75} /></button>
                  </span>
                )}
                {/* Counted off the SAME list the strip renders. It said
                    `active.agents.length - 1` while the strip dropped the docked
                    ones, which is the two-copies-of-one-fact defect in its
                    cheapest form: the header would claim 3 tabs above a strip
                    holding 2, and the number is the part a reader believes. */}
                {!focused && enlarged !== null && gridAgents.length > 1 && (
                  <Chip
                    className="ml-auto"
                    jump="as-tabs"
                    tone="text-fg-ghost"
                    mark={<Layers size={13} strokeWidth={1.75} aria-hidden />}
                    count={gridAgents.length - 1}
                    title={`${gridAgents.length - 1} agent(s) are strip tabs while this one is enlarged — click one to switch`}
                    label={`${gridAgents.length - 1} as tabs, click one to switch`}
                  />
                )}
              </div>
              {/* The board loads ONLY when the reader opens it — the kanban glyph
                  in the row above (decided 2026-08-30: nothing about a project's
                  board should spawn subprocesses or take room until the reader
                  asks). The last answer stays in the session's memory, so
                  reopening after a switch is instant. */}

              {/* Task 4.2 — a panel whose KIND this build does not have.
                  Stated where the reader is standing, above the grid, rather
                  than only in the place it would have been rendered: the whole
                  point is that there is no such place. Naming the kind is what
                  makes it actionable — "something is missing" is not a report. */}
              {unknownPanels.length > 0 && (
                <div
                  data-fleet-unknown-panels={unknownPanels.length}
                  className="shrink-0 rounded border border-amber-500/40 bg-amber-500/5 px-2 py-1.5 text-xs text-amber-300 space-y-0.5"
                >
                  <div className="font-semibold">
                    {unknownPanels.length} panel(s) this build cannot render — kept, not closed
                  </div>
                  {unknownPanels.map(u => (
                    <div key={`${u.ref.kind} ${u.ref.id}`} className="text-fg-muted">
                      <span className="text-amber-300">{u.ref.kind}</span>
                      <span className="text-fg-ghost"> · {u.ref.id}</span>
                      <span className="text-fg-ghost"> — {u.reason}</span>
                    </div>
                  ))}
                </div>
              )}
              {/* A selected project with nothing running is not an error and not
                  an empty panel: the arrangement keeps it in the list on
                  purpose, so the right-hand side says what it measured. */}
              {active.agents.length === 0 && (
                <div className="text-sm text-fg-muted">
                  Discovery found no running agent in this project.
                  {active.archived && <span className="text-fg-ghost"> (archived project)</span>}
                  {/* The fleet-wide result, kept as a RESULT rather than
                      dropped. It used to be the whole panel; now that the strip
                      above stays, this is what is left of it that a reader
                      still needs — the two readings of "nothing here" are told
                      apart by the sentence, not by which screen appeared. */}
                  {data.agents === 0 && (
                    <span className="text-fg-ghost tabular-nums">
                      {' '}Nowhere else either — discovery ran at{' '}
                      {answeredAt ? new Date(answeredAt).toLocaleTimeString() : '\u2014'}
                      {' '}over {data.projects.length} known projects.
                    </span>
                  )}
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
              {/* `auto-rows-[minmax(11rem,1fr)]` — a floor AND a share, which is
                  what makes this different from the `items-start` it replaces.
                  That earlier rule was a real fix for a real complaint (*"az sem
                  segít hogy különböző méretűek"*): a stretched row made one
                  card as tall as its tallest neighbour, so an open terminal left
                  the tile beside it a large empty box. But it fixed the ragged
                  row by handing the height decision back to each card's own
                  text, and five cards of text in an 1100 px panel is 59 % black
                  screen.
                  The floor is what stops a stretch from being emptiness: every
                  tile is at least 11rem, the excerpt grows into whatever the row
                  gives it (see `Excerpt`), and `1fr` divides the panel evenly so
                  the tiles are the same size as each other — which was the
                  original complaint. When there are more agents than fit, the
                  rows keep the floor and this box scrolls. */}
              {focused ? (
                /* Full screen — one agent, the whole panel. What it covers is
                   counted in the header above, never silently dropped. */
                <AgentCard
                  key={focused.pid}
                  agent={focused}
                  projectRoot={active.root}
                  knownFiles={knownFiles[focused.cwd || active.root]}
                  onOpenFile={(f, from) => openFile(active.root, { ...f, from })}
                  checkouts={allCheckouts}
                  home={data.home}
                  onReveal={(path, from) => revealDirectory(active.root, path, from)}
                  enlarged
                  focused
                  open={openLogs.includes(focused.pid)}
                  onToggle={() => toggleLog(active.name, focused.pid, !openLogs.includes(focused.pid))}
                  ownerReachable={data.owner_reachable}
                  terminalOpen={openTerminals.includes(focused.terminal_label ?? '')}
                  onTerminal={label => toggleTerminal(active.name, label ?? focused.terminal_label ?? null, label !== null)}
                  onDock={focused.terminal_label
                    ? edge => dockPanel(PANEL_AGENT, focused.terminal_label as string, edge)
                    : undefined}
                  dockedEdge={dockedEdgeOf(focused.terminal_label)}
                  onRenamed={onAgentRenamed}
                  onFocus={() => setFocus(active.name, null)}
                  /* The same act on the same surface as in the grid: a click on
                     the title bar leaves full screen. Without it the two layouts
                     would answer one gesture differently. */
                  onCollapse={() => setFocus(active.name, null)}
                  canJumpSeat={canJumpSeat}
                  onJumpSeat={onJumpSeat}
                  canJumpPid={canJumpPid}
                  onJumpPid={onJumpPid}
                  typing={typingLabel !== null && typingLabel === focused.terminal_label}
                  onTyping={on => setTypingLabel(on ? focused.terminal_label ?? null : null)}
                />
              ) : (
              <div className={enlarged === null && !filesBig
                ? `flex-1 min-h-0 overflow-y-auto grid gap-2 auto-rows-[minmax(11rem,1fr)] ${GRID_COLS[fittedColumns] ?? GRID_COLS[2]}`
                : 'flex-1 min-h-0 flex flex-col'}>
              {/* One enlarged tile: the others are a tab strip, not rows. The
                  strip is OUTSIDE the scrolling area so it stays put while the
                  enlarged tile scrolls — a tab bar that scrolls away is a tab
                  bar you have to go looking for. */}
              {/* `gridAgents` again, for the same reason the grid uses it —
                  asked for 2026-08-20: *"ha ki van téve layoutba fixen egy view
                  akkor ne hozza a view tabs listaban az altalanos view sorban"*.
                  A docked agent has a place of its own on the screen; listing it
                  here too offers a second way to reach one thing, and clicking
                  it would enlarge a tile the grid does not contain.

                  This is a MOVE, not a compaction, so `ui-quality.md`'s rule
                  about hiding a failure is satisfied by the band rather than by
                  the tab: the docked panel is on screen, with its own failure
                  marker (`data-fleet-dock-marker`) on its edge. Nothing about it
                  becomes unreachable or unmarked by leaving the strip. */}
              {/* Also when the FILE view is the big one: the agents are then all
                  in the strip, and a strip is how they stay reachable. Without
                  this, maximising the files would hide every agent with nothing
                  saying where they went — the false-absence shape, in the
                  direction where the reader stops looking. */}
              {/* Two conditions, and they differ by one agent for a reason. With
                  an agent enlarged, a single agent needs no strip — there is
                  nothing to switch TO, and rendering it would show the same
                  agent twice (which is exactly what a test caught). With the
                  FILE view big, every agent is off screen, so even one of them
                  needs the strip to stay reachable. */}
              {((enlarged !== null && gridAgents.length > 1) || (filesBig && gridAgents.length > 0)) && (
                <AgentTabs
                  agents={gridAgents}
                  selected={enlarged}
                  onSelect={pid => setEnlarged(active.name, pid)}
                  onMove={moveAgent}
                />
              )}
              {/* `gridAgents`, not `active.agents`: a docked agent has MOVED to
                  its edge, not been duplicated there. Rendering it in both
                  places would give the reader a second panel where they asked
                  for the same one somewhere else — and two renderings of one
                  agent drift, with the unwatched copy going stale. */}
              {/*
                THE FILE VIEW AS A TILE — asked for 2026-08-22: *"nem csak jobb
                oldalt akarom tartani, hanem ugyanúgy rendezni mint agentek
                nézetét"*.

                Open and not docked means here, in the same grid, under the same
                column choice and the same uniform row height as every agent.
                Docked, it is drawn by `renderDocked` and this renders nothing —
                the panel MOVED to its edge, and drawing it in both places would
                give the reader two of one thing, with the unwatched copy going
                stale. That is the same rule `gridAgents` already follows.
              */}
              {active.root && filesOpen.has(active.root)
                && !docks.some(d => d.kind === PANEL_FILES && d.id === active.root) && (
                <div
                  className={`${cardClasses('ours', {})} flex flex-col overflow-hidden min-h-44${
                    filesBig ? ' flex-1' : ''}`}
                  data-fleet-file-tile={active.root}
                  data-fleet-file-max={filesBig ? 'on' : 'off'}
                >
                  {/* min-h-44 = the grid's own 11rem row floor. With an agent
                      enlarged the column becomes flex-col, and a maximised board
                      tile (flex-1, remembered per project) starved this tile to
                      a header sliver — the reported switch-back misrender
                      (2026-08-30). The floor holds it at the smallest the grid
                      would ever draw it. */}
                  <FleetFileView
                    root={active.root}
                    projectName={active.name}
                    request={fileRequest?.root === active.root ? fileRequest.file : null}
                    initial={lastFile[active.root] ?? null}
                    onOpened={f => rememberFile(active.root as string, f)}
                    onRequestHandled={() => setFileRequest(null)}
                    onClose={() => closeFiles(active.root)}
                    onDock={edge => dockPanel(PANEL_FILES, active.root, edge)}
                    dockedEdge={null}
                    maximised={filesBig}
                    onMaximise={() => toggleFilesMax(active.name, active.root)}
                    fullscreen={filesFullscreen === active.root}
                    onFullscreen={() => setFilesFullscreen(
                      filesFullscreen === active.root ? null : active.root ?? null)}
                  />
                </div>
              )}
              {/*
                THE WORK CYCLE AS A TILE, on the same terms as the file view: a
                panel of the PROJECT rather than of an agent, in the grid until
                somebody sends it to an edge. Docked, `renderDocked` draws it and
                this renders nothing — one panel, one place, never two copies to
                drift apart.
              */}
              {active.root && workCycleOpen.has(active.root)
                && !docks.some(d => d.kind === PANEL_WORK_CYCLE && d.id === active.root) && (
                <div
                  className={`${cardClasses('ours', {})} flex flex-col min-h-0 overflow-hidden`}
                  data-fleet-work-cycle-tile={active.root}
                >
                  <FleetWorkCycle
                    root={active.root}
                    projectName={active.name}
                    onClose={() => closeWorkCycle(active.root)}
                  />
                </div>
              )}
              {/*
                THE BOARD AS A TILE, on the same terms as the file view and the
                work cycle. Its own chrome — dock to an edge, maximise, close —
                is what makes it a panel of the same class as the agents', not a
                second-class summary (asked for 2026-08-30). While the panel is
                open anywhere, the inline copy under the header stays the
                summary strip only: one board, one place, never two to drift.
              */}
              {active.root && boardOpen.has(active.root)
                && !docks.some(d => d.kind === PANEL_BOARD && d.id === active.root) && (
                <div
                  className={`${cardClasses('ours', {})} flex flex-col min-h-0 overflow-hidden${
                    boardMax === active.root ? ' flex-1' : ''}`}
                  data-fleet-board-tile={active.root}
                  data-fleet-board-max={boardMax === active.root ? 'on' : 'off'}
                >
                  <FleetBoard
                    project={active.name}
                    projectName={active.name}
                    onClose={() => closeBoard(active.root)}
                    onDock={edge => dockPanel(PANEL_BOARD, active.root, edge)}
                    dockedEdge={null}
                    maximised={boardMax === active.root}
                    onMaximise={() => toggleBoardMax(active.name, active.root)}
                    fullscreen={boardFullscreen === active.root}
                    onFullscreen={() => setBoardFullscreen(
                      boardFullscreen === active.root ? null : active.root ?? null)}
                    onOpenTarget={path => openFile(active.root, { path })}
                  />
                </div>
              )}
              {gridAgents.map(a => {
                const card = (extra: { enlarged?: boolean; open: boolean; onToggle: () => void }) => (
                  <AgentCard
                    key={a.pid}
                    agent={a}
                    projectRoot={active.root}
                    knownFiles={knownFiles[a.cwd || active.root]}
                    onOpenFile={(f, from) => openFile(active.root, { ...f, from })}
                    checkouts={allCheckouts}
                    home={data.home}
                    onReveal={(path, from) => revealDirectory(active.root, path, from)}
                    /*
                      No `wide` any more, and the reason it existed is now fixed
                      at its source. A tile that had opened something used to
                      take the whole row, because *"a sorok megtörnek"* — one
                      tile three times the height of its neighbour left a hole
                      under the short one. The rows are UNIFORM now
                      (`auto-rows-[minmax(11rem,1fr)]`), so a tall tile cannot
                      ragged a row and the override has nothing left to fix.
                      What it did still have was a cost, reported 2026-08-19:
                      *"column most itt a második rowt változtatta csak … és nem
                      az összeset?"* — with two of three tiles holding something
                      open, choosing three columns changed one tile and the
                      control looked broken. A layout control the reader picked
                      must not be overruled by which panels happen to be open;
                      the way to give one tile the whole panel is to maximise it,
                      which is a control the reader operates on purpose.
                    */
                    {...extra}
                    onEnlarge={() => setEnlarged(active.name, enlarged === a.pid ? null : a.pid)}
                    /* The tile's body opens the agent, and only while it is not
                       already the enlarged one — see AgentCard's `onOpen`. */
                    onOpen={extra.enlarged ? undefined : () => setEnlarged(active.name, a.pid)}
                    /* …and the title bar puts it back — asked for 2026-08-20,
                       *"mint egy minimize"*. Only the head, never the body:
                       the body is what was enlarged in order to be read. */
                    onCollapse={extra.enlarged ? () => setEnlarged(active.name, null) : undefined}
                    ownerReachable={data.owner_reachable}
                    terminalOpen={openTerminals.includes(a.terminal_label ?? '')}
                    onTerminal={label => toggleTerminal(active.name, label ?? a.terminal_label ?? null, label !== null)}
                    onDock={a.terminal_label
                      ? edge => dockPanel(PANEL_AGENT, a.terminal_label as string, edge)
                      : undefined}
                    dockedEdge={dockedEdgeOf(a.terminal_label)}
                    onRenamed={onAgentRenamed}
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
                return a.pid === enlarged && !filesBig
                  ? card({ enlarged: true, open, onToggle: toggle })
                  : enlarged !== null || filesBig
                    /* The unselected agents are in the tab strip above. They
                       used to be `AgentRow`s here — one line each, with an
                       input — and `AgentRow` is DELETED rather than left
                       unused: a component nothing renders is a second answer
                       to "how is an unselected agent shown", and it drifts
                       from the tabs the moment either is touched. */
                    ? null
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
            {bandsOn(bands, 'bottom').map(band => (
              <FleetDockBand
                key={dockSplitKey(band)}
                band={band}
                title={dockTitle(band.kind, band.id)}
                showTitle={band.kind !== PANEL_AGENT}
                collapsed={band.collapsed === true}
                onToggleCollapsed={() => collapseBand(band.kind, band.id, band.collapsed !== true)}
                max={maxBandSize(band.edge)}
                failing={dockFailing(band)}
                onResize={px => resizeBand(dockSplitKey(band), px, false)}
                onResizeCommit={px => resizeBand(dockSplitKey(band), px, true)}
                onUndock={() => dockPanel(band.kind, band.id, null)}
              >
                {renderDocked(band)}
              </FleetDockBand>
            ))}
          </div>
          {/* The wire view OWNS the right edge while shown (see the toggle
              above): the bands yield rather than squeeze, because their stored
              edge, size and collapsed state are untouched — they come back
              whole when the view is hidden. Filtering the RENDER list, not the
              stored map, is what makes that reversible. */}
          {(wiresShown ? [] : bandsOn(bands, 'right')).map(band => (
            <FleetDockBand
              key={dockSplitKey(band)}
              band={band}
              title={dockTitle(band.kind, band.id)}
              showTitle={band.kind !== PANEL_AGENT}
              collapsed={band.collapsed === true}
              onToggleCollapsed={() => collapseBand(band.kind, band.id, band.collapsed !== true)}
              max={maxBandSize(band.edge)}
              failing={dockFailing(band)}
              onResize={px => resizeBand(dockSplitKey(band), px, false)}
              onResizeCommit={px => resizeBand(dockSplitKey(band), px, true)}
              onUndock={() => dockPanel(band.kind, band.id, null)}
            >
              {renderDocked(band)}
            </FleetDockBand>
          ))}
        </div>
        </div>
      </div>
      </WaitThresholdsContext.Provider>
    </div>
  )
}
