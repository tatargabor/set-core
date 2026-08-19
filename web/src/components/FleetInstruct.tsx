import { useCallback, useEffect, useRef, useState } from 'react'

import VoiceInput from './VoiceInput'
import type { FleetAgent, InstructReport } from '../lib/fleetTypes'
import { holdNote, isSettled, meaningOf, offerWaiterRemedy } from '../lib/fleetInstructOutcome'
import { instructability } from '../lib/fleetDeclared'

/**
 * The agent's own input — task 7.7, and task 4.4 where there is nothing to type
 * into.
 *
 * ## A 200 is not a delivery
 *
 * The route answers with three separate facts and this component renders them
 * as three: the send happened (`accepted`), what the channel said became of it
 * (`outcome`), and whether the agent actually has it (`delivered_to_agent`). A
 * green "sent ✓" off the status code would state an event that did not happen —
 * `sits-unread` and `wakes-nobody` are both ordinary 200s in which nobody was
 * told anything.
 *
 * ## `held` has a clock, so this component does too
 *
 * A hold is not a resting state: it expires on its own, and no endpoint exists
 * to re-ask what became of it. So a held outcome is never left standing as a
 * present-tense claim — it is re-rendered every second as *held as of N ago,
 * and nothing has re-checked it since*, which is a statement about a moment and
 * stays true. A tile that draws "held" once and stops is pointing at a message
 * that may already be dead.
 *
 * ## Where the input cannot be
 *
 * `instructable: false` removes the input and puts the producer's own sentence
 * in its place. Not a disabled box (which invites typing), not the agent
 * dropped from the screen (which hides running work), and not a box that
 * silently goes nowhere — which is the worst of the three.
 *
 * ## Dictation is a way of filling the box, not a second way of sending
 *
 * Task 7.6. The mic is the dashboard's existing `VoiceInput`, unchanged, and it
 * writes into the SAME `text` the keyboard writes into — so everything after
 * the words exist is one path: the same review, the same Enter, the same three
 * facts back. Two rules shape it, and both are about what dictation must not
 * quietly become:
 *
 *  - **it never sends.** A transcript that dispatched itself would put words
 *    nobody read in front of a live agent, and the send is the irreversible
 *    half. What arrives is a draft;
 *  - **a partial is not what you have.** In-progress text is shown BESIDE the
 *    box, dim and labelled, never inside it. If the connection drops mid
 *    sentence the box still holds only finalised words — a partial sitting in
 *    the box looks exactly like something you typed and meant.
 *
 * When Soniox is not configured or there is no microphone, `VoiceInput` renders
 * nothing at all. That is the task's *absent rather than failing*, and it is the
 * component's own behaviour rather than a check repeated here — a second copy of
 * that condition is the one that would drift.
 */

const TONE: Record<string, string> = {
  delivered: 'text-emerald-400',
  undelivered: 'text-amber-400',
  pending: 'text-sky-300',
  failed: 'text-red-400',
  unknown: 'text-amber-400',
}

export default function FleetInstruct({ agent, compact, terminalOpen }: {
  agent: FleetAgent
  /**
   * Rendered on a ROW rather than inside a card — task 7.3.
   *
   * The difference is only the frame: a card separates the input from what is
   * above it with a rule and a margin, a row has nothing above it to separate
   * from. Everything else — what can be sent, to whom, the outcome, dictation —
   * is identical, deliberately: a compact input that could do less would be a
   * second answer to "can this agent be instructed", and the density would
   * decide it.
   */
  compact?: boolean
  /**
   * A terminal is open on this tile, so an input already exists.
   *
   * Only the REFUSAL branch reads it. The input itself stays: a seat and a pty
   * are two addresses for one agent, and the box also carries dictation, which
   * the terminal does not.
   */
  terminalOpen?: boolean
}) {
  const [text, setText] = useState('')
  /** In-progress dictation. Never merged into `text` — see the header. */
  const [heard, setHeard] = useState('')
  /** When the last partial arrived — the preview's own freshness. */
  const heardAt = useRef(0)
  const [sending, setSending] = useState(false)
  const [report, setReport] = useState<InstructReport | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  /** When the report arrived. Used only for the hold's age — see the header. */
  const [reportedAt, setReportedAt] = useState<number | null>(null)
  const [, setTick] = useState(0)
  const box = useRef<HTMLTextAreaElement | null>(null)

  const can = instructability(agent)
  const open = report !== null && !isSettled(report)

  // A hold is the only outcome that keeps moving after it is shown, so the
  // clock runs only while one is open — a permanent interval on every tile
  // would re-render the whole fleet once a second for nothing.
  useEffect(() => {
    if (!open) return
    const t = setInterval(() => setTick(n => n + 1), 1000)
    return () => clearInterval(t)
  }, [open])

  /**
   * The preview expires on its own.
   *
   * `VoiceInput` announces a transcript but never announces that it stopped
   * hearing anything: a recording ended with no finalised words leaves the last
   * partial standing, and *"hearing: …"* about a microphone that is off is the
   * false-presence shape this screen exists against. Partials arrive
   * continuously while a mic is live, so silence for a few seconds is the
   * measurement that the dictation is over — and the box, which is the part
   * that can be sent, is never touched either way.
   */
  const listening = heard.trim().length > 0
  useEffect(() => {
    if (!listening) return
    const t = setInterval(() => {
      if (Date.now() - heardAt.current > 3000) setHeard('')
    }, 1000)
    return () => clearInterval(t)
  }, [listening])

  const send = useCallback(async () => {
    const body = text.trim()
    if (!body || sending) return
    setSending(true)
    setFailure(null)
    try {
      const res = await fetch(`/api/fleet/agents/${agent.pid}/instruct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: body }),
      })
      const payload = await res.json().catch(() => null)
      if (!res.ok) {
        // A 409 carries the channel's own report (a refusal, or no address).
        // Rendered as an outcome rather than as a generic error, because the
        // reader needs to know WHICH of the two happened.
        const detail = payload?.detail
        if (detail && typeof detail === 'object' && 'outcome' in detail) {
          setReport(detail as InstructReport)
          setReportedAt(Date.now())
        } else {
          setFailure(String(detail?.reason ?? detail ?? `HTTP ${res.status}`))
        }
        return
      }
      setReport(payload as InstructReport)
      setReportedAt(Date.now())
      // The text is cleared only on a send that was made and answered. On a
      // refusal it stays in the box: retyping a lost instruction is the kind of
      // small cruelty that makes a surface untrustworthy.
      setText('')
      // And with it the preview: a sent instruction leaves nothing being heard.
      setHeard('')
    } catch (e) {
      setFailure(String((e as Error)?.message ?? e))
    } finally {
      setSending(false)
    }
  }, [agent.pid, text, sending])

  if (can.kind === 'no') {
    /*
      A FALSE ABSENCE, and it was on screen: *"no input: this session has no
      seat on the messaging bus"* rendered directly above a live terminal that
      takes keystrokes. The sentence is true about the BUS and false about what
      the reader takes from it — whether they can type at this agent. Measured
      2026-08-19 on the consumer-a tile, and it is the class `evidence-discipline`
      calls false absence: the surface announcing that something is missing when
      it is right there.

      So the reason stands only where it is the whole story. With a terminal
      open there IS an input, and the seat's absence is not what the reader
      needs at that moment.
    */
    if (terminalOpen) return null
    return (
      <div className={compact ? 'min-w-0' : 'mt-2 border-t border-surface-line pt-2'} data-fleet-instruct="refused">
        {/*
          Task 4.4: the reason stands WHERE THE INPUT WOULD BE — and quietly.
          Seen on the live screen in amber: most agents on this machine have no
          seat, so thirteen tiles carried an amber line at once. Amber means
          *needs attention* everywhere else here, and spending it on the
          ordinary case is how a colour stops meaning anything — the reader then
          misses the one tile that really is undetermined. The sentence stays;
          the alarm does not.
        */}
        <div className="text-xs text-fg-ghost" title={can.reason}>no input: {can.reason}</div>
      </div>
    )
  }

  const meaning = report ? meaningOf(report.outcome) : null

  return (
    <div className={compact ? 'min-w-0' : 'mt-2 border-t border-surface-line pt-2'} data-fleet-instruct={can.kind} data-fleet-own-surface="instruct">
      <div className="flex items-end gap-2">
        <textarea
          ref={box}
          rows={1}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send() }
          }}
          data-fleet-instruct-input={agent.pid}
          placeholder={can.kind === 'unknown'
            ? 'send an instruction — this server did not say whether the agent has an address'
            : `send an instruction to ${can.seat ?? 'this agent'}`}
          className="flex-1 min-w-0 resize-y bg-surface-page border border-surface-edge rounded px-2 py-1 text-xs text-fg-normal placeholder:text-fg-ghost focus:outline-none focus:border-sky-400/60"
        />
        {/* Task 7.6 — dictation into the same box. `onTranscript` appends, so
            speaking after typing continues the sentence instead of replacing
            it, and the reader can fix a misheard word before sending. */}
        <VoiceInput
          onTranscript={t => { setText(prev => (prev ? `${prev} ${t}` : t)); setHeard('') }}
          onPartial={t => { heardAt.current = Date.now(); setHeard(t) }}
          disabled={sending}
        />
        <button
          onClick={() => void send()}
          disabled={sending || !text.trim()}
          data-fleet-instruct-send={agent.pid}
          className="text-xs text-sky-300 hover:text-sky-200 disabled:opacity-40 disabled:hover:text-sky-300 shrink-0 pb-1"
        >
          {sending ? 'sending…' : 'send'}
        </button>
      </div>

      {/* What is being heard right now — outside the box on purpose, so a
          sentence that never finalises cannot be sent as if it had been. */}
      {heard.trim() && (
        <div className="mt-1 text-xs text-fg-ghost italic" data-fleet-instruct-heard={agent.pid}>
          hearing: {heard}
        </div>
      )}

      {failure && <div className="mt-1 text-xs text-red-400">the send failed: {failure}</div>}

      {report && meaning && (
        <div className="mt-1.5 space-y-1" data-fleet-outcome={report.outcome}>
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className={`text-xs font-semibold ${TONE[meaning.tone] ?? 'text-fg-muted'}`}>
              {meaning.label}
            </span>
            {/* The three facts, as three. `delivered_to_agent` is the one a
                reader actually wants and the one a status code cannot answer. */}
            <span
              className="text-xs text-fg-ghost"
              data-fleet-delivered={report.delivered_to_agent ? 'yes' : 'no'}
              title="Whether the AGENT has it. A held message is never counted as delivered."
            >
              {report.delivered_to_agent ? 'the agent has it' : 'the agent does not have it'}
            </span>
            {report.accepted === false && (
              <span className="text-xs text-red-400">the send was not made</span>
            )}
          </div>

          <div className="text-xs text-fg-muted">{meaning.note}</div>

          {/* A hold keeps moving. Re-stated with its age every second, so it can
              never stand as a present-tense claim nobody checked. */}
          {!isSettled(report) && reportedAt !== null && (
            <div className="text-xs text-sky-300" data-fleet-outcome-open="held">
              {holdNote((Date.now() - reportedAt) / 1000)}
            </div>
          )}

          {report.superseded && (
            <div className="text-xs text-amber-400">
              this replaced an earlier “{report.superseded}” — the hold did not last
            </div>
          )}

          {report.reason && <div className="text-xs text-fg-muted">{report.reason}</div>}

          {/* The channel's own words, verbatim and unparsed. Shown because a
              summary of a notice is a second judgement. */}
          {report.notices && report.notices.length > 0 && (
            <ul className="text-xs text-fg-ghost list-none space-y-0.5">
              {report.notices.map((n, i) => <li key={i}>· {n}</li>)}
            </ul>
          )}

          {/* Task 7.7: `waiters_here: 0` is where the remedy belongs. There is no
              install endpoint, so this states the command rather than offering a
              button with nothing behind it — the shape task 8.2 forbids. */}
          {offerWaiterRemedy(report) && (
            <div className="text-xs text-amber-400" data-fleet-remedy="no-waiter">
              nothing is listening for this session, so the message waits for a person to type
              into it. A waiter is a <code className="text-fg-muted">sac wait</code> process
              started for that session; until one runs, every instruction sent here sits unread.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
