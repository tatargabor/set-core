import { useEffect, useMemo, useRef, useState } from 'react'

import { buildActs, errorStanding, sayCount, speakerLabel, toolSummary } from '../lib/fleetConversation'
import type { Act, LogTurn, SayAct, Speaker, WorkAct } from '../lib/fleetConversation'
import { plainExcerpt } from '../lib/excerptText'

/**
 * One agent's session log, as a view of its own.
 *
 * ## Why this is a component and not a block inside the fleet page
 *
 * It was one, and the cost of that came due on the PM screen (B-33): PM mode
 * presents ONE agent full screen, and for an agent the framework did not start
 * there is no terminal to show — so the content area rendered a warning and
 * ~700 px of black, while the same agent's log endpoint had a whole
 * conversation to give. Measured: 3 of 20 live agents have no pty, and 2 of the
 * 4 items PM mode had queued were among them.
 *
 * The fleet page had already learned this once, for the tiles (B-10, *"nem
 * hiszem hogy üres kellene legyen akár egy agent is, már biztosan van róla
 * valami log, info"*). The finding was right and the fix was local to a file
 * nobody else could import, so the next surface repeated the defect. Moving it
 * here is what makes the answer reusable rather than remembered.
 *
 * ⚠ Everything below renders VERBATIM session content, which may come from a
 * consumer project. Displayed and never written down: no `localStorage`, no
 * cache, no committed artifact. See CLAUDE.md — the boundary is persistence.
 */


export interface LogResponse {
  turns: LogTurn[]
  total_read?: number
  truncated?: boolean
  problem?: string
  pid?: number
  name?: string | null
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
export function SayRow({ act, showThinking, expanded, onExpand, compact }: {
  act: SayAct
  showThinking: boolean
  expanded: boolean
  onExpand: () => void
  /**
   * On a TILE rather than in the log panel — B-10/B-11.
   *
   * The panel's job is to show what was said, in full, with the marks intact;
   * measured on the tile that is 2340 characters of raw markdown — table pipes,
   * `##` headings and all — which is the same *"több soros … értelmetlen"* the
   * excerpt was just cut back for. So the compact row strips the marks (the
   * producer's words, none of them rendered or interpreted) and stops at two
   * lines, with no expand control: a tile is where you decide WHICH agent to
   * open, and the panel is where you read.
   */
  compact?: boolean
}) {
  const style = SAY_STYLE[act.speaker]
  const long = act.text.length > CLIP
  const shown = compact ? plainExcerpt(act.text) : (long && !expanded ? act.text.slice(0, CLIP) : act.text)
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
      {act.text && (compact ? (
        <div
          className={`${style.body} leading-relaxed break-words mt-0.5`}
          style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
        >
          {shown}
        </div>
      ) : (
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
      ))}
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
export function WorkRow({ act }: { act: WorkAct }) {
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
/**
 * The log of one agent, polled while it is on screen.
 *
 * `onClose` is OPTIONAL, and its absence is a real case rather than a default:
 * on a tile this view is something the reader opened and can shut, on the PM
 * screen it is what the surface fell back to and there is nothing to shut. A
 * close button with nothing behind it is the shape this repo already forbids
 * for the terminal — the reader concludes the screen is broken instead of
 * concluding there is no panel.
 */
export default function FleetAgentLog({ pid, onClose }: { pid: number; onClose?: () => void }) {
  const [log, setLog] = useState<LogResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showThinking, setShowThinking] = useState(false)
  const [expanded, setExpanded] = useState<Set<number>>(() => new Set())
  const scrollBox = useRef<HTMLDivElement | null>(null)
  /**
   * Whether the reader is still at the newest end — B-8.
   *
   * A log opens at the LATEST, because the newest turn is what the reader came
   * for and a box that starts at the top hides it behind the whole history.
   * But it must not yank the view back while somebody is reading upwards, so
   * the stickiness is a fact about where they are rather than a mode: at the
   * bottom (within a line's slack) means follow, anywhere else means leave it.
   */
  const stick = useRef(true)

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

  // Follow the newest turn, unless the reader has scrolled away from it. Runs
  // on every render rather than on a length change: an act can grow (a turn
  // gains text) without the count moving, and the reader watching the bottom
  // would then see the new line half off screen.
  useEffect(() => {
    const el = scrollBox.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  })

  // Counted from the turns, not from a flag: the toggle below must never
  // announce a hidden thing that is not there (false absence), nor stay silent
  // about one that is.
  // `log?.turns` is not enough: a response that arrives WITHOUT the field is
  // a different case from no response, and `log?.turns.filter` throws on it —
  // which takes the whole panel down, and with it whatever surface embedded
  // it. A malformed payload must degrade to an empty conversation, never to a
  // blank screen.
  const thinkingTurns = log?.turns?.filter(t => t.thinking).length ?? 0

  // The turns become acts here (task 7.20). Every count below is taken from the
  // ACTS, so the header can never disagree with the rows underneath it.
  const acts = useMemo(() => buildActs(log?.turns ?? []), [log])
  const sentences = sayCount(acts)

  return (
    <div
      className="border-t border-surface-line mt-3 pt-2 flex-1 min-h-0 flex flex-col"
      data-fleet-own-surface="log"
    >
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
            the last {log.turns?.length ?? 0} of {log.total_read}
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
        {onClose && (
          <button onClick={onClose} className="ml-auto text-xs text-fg-muted hover:text-fg-strong">close</button>
        )}
      </div>
      {error && <div className="text-xs text-red-400">cannot be read: {error}</div>}
      {/* A problem is not an empty conversation, and the two must not look alike. */}
      {log?.problem && <div className="text-xs text-amber-400">{log.problem}</div>}
      {log && !log.problem && (log.turns?.length ?? 0) === 0 && (
        <div className="text-xs text-fg-muted">the log is readable and holds no conversation</div>
      )}
      {!log && !error && <div className="text-xs text-fg-muted">reading the log…</div>}
      {/* Fills what the card gives it when the tile is enlarged. `55vh` was
          the same guess as the terminal's `62vh` and wrong for the same
          reason: the strip above it is not a fixed height. */}
      <div
        ref={scrollBox}
        onScroll={e => {
          const el = e.currentTarget
          // One line of slack: a browser's fractional scroll heights mean an
          // exact comparison reads as "scrolled away" while the reader has not
          // moved, and following would then stop for no visible reason.
          stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24
        }}
        className="flex-1 min-h-[10rem] overflow-y-auto space-y-1 pr-1"
      >
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