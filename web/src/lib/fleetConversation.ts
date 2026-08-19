/**
 * A session log's turns, turned into what actually happened — task 7.20.
 *
 * The raw log is a list of TURNS, and a turn is a transport unit, not an event
 * a reader cares about. Measured on one live session's last 40 turns:
 * **19 `user` turns carrying no text at all, only a tool RESULT; 18 `assistant`
 * turns carrying no text, only a tool call; and 3 turns — 7.5% — carrying an
 * actual sentence.** Rendering that list one row per turn produces a screen
 * that is 92.5% machinery, and it produces two defects rather than one ugliness:
 *
 * **1. `role` is not the speaker.** The runtime feeds a tool result back under
 * the `user` role because that is where the protocol puts it. A surface that
 * prints `te` ("you") next to it states that the PERSON said what the machine
 * fed back — a false value, arriving through a field that looks like data. The
 * rule this module holds: **the speaker is decided by what the turn CARRIES,
 * never by its role.** A turn with no text has no speaker at all; it is part of
 * an act, not an utterance.
 *
 * A second, smaller instance of the same thing, measured over the six most
 * recent session logs: of 41 `user` turns that DO carry text, **9 are not the
 * person either** — `<command-name>`, `<command-message>` and
 * `<local-command-stdout>` blocks the runtime writes under the same role. They
 * get their own speaker (`runtime`) rather than being promoted to `te`.
 *
 * **2. One act, two rows, two "speakers".** A tool call and its result are one
 * action; the log splits them across two turns and puts a role change between
 * them. They are joined back into a single `work` act here.
 *
 * ## What the joining may NOT do
 *
 * Compacting must never hide a failure (`.claude/rules/ui-quality.md`). Two
 * consequences are built into the model rather than left to the renderer:
 *
 *  - **Consecutive acts are never merged into each other.** One assistant call
 *    group plus its results is one act; eighteen of them stay eighteen rows.
 *    Merging them would put a failed call inside a summary line.
 *  - **`errors` is `null` when it is not known, never `0`.** The session log
 *    carries `is_error` on every tool result (measured: 145 of 146 blocks in
 *    one live log, 4 of them true), but the log endpoint currently reduces the
 *    whole result to a COUNT and drops it. So the surface cannot mark a failed
 *    call today — and a model that reported `0` would state "nothing failed"
 *    about something it never looked at. `null` means *we did not measure it*,
 *    and the surface says so where the reader stands. The day the producer
 *    sends `errors`, this module marks the act and nothing else changes.
 */

/** One turn as the log endpoint hands it over. */
export interface LogTurn {
  role: string
  timestamp: string | null
  text: string
  thinking: string
  tools: { name: string | null; id: string | null }[]
  results: number
  sidechain: boolean
  /**
   * How many of this turn's tool results failed.
   *
   * **Optional on purpose.** An older producer — every one shipped so far —
   * sends no such field, and `undefined` must resolve to *unknown*, never to
   * zero. See the header: this is the false-absence direction, and it is the
   * expensive one, because a zero stops the reader from looking.
   */
  errors?: number
}

/** Who said a sentence. Decided from the content, never from `role`. */
export type Speaker = 'person' | 'agent' | 'runtime' | 'other'

export interface SayAct {
  kind: 'say'
  speaker: Speaker
  /** The raw role, kept so an unrecognised one can be printed as itself. */
  role: string
  at: string | null
  text: string
  thinking: string
  /** Index of the turn this came from — the renderer keys on it. */
  turn: number
}

export interface WorkAct {
  kind: 'work'
  /** When the calls were made (the call turn's timestamp, not the result's). */
  at: string | null
  /** Tool names in call order. An unnamed tool is kept as `?`, not dropped. */
  names: string[]
  calls: number
  results: number
  /**
   * Calls with no result in this window. NOT an error — the commonest cause is
   * a tail that cut between the call and its answer, and the second commonest
   * is a call still running. It is shown because a silent drop would make the
   * two counts disagree with no explanation.
   */
  unanswered: number
  /**
   * Results whose call is not in this window — the same tail cut from the other
   * end. Such an act has `calls: 0` and is rendered as a result without a call
   * rather than being attached to an unrelated one.
   */
  orphanResults: number
  /** How many results failed, or `null` when the data does not say. */
  errors: number | null
  /** The turns folded into this act, for keying and for debugging. */
  turns: number[]
}

export type Act = SayAct | WorkAct

/**
 * Text the RUNTIME writes under the `user` role.
 *
 * Anchored at the start of the (trimmed) text, because these are wrappers the
 * runtime emits around a whole turn — a substring test would catch a person
 * quoting one, which is the person speaking about the runtime, not the runtime.
 */
const RUNTIME_PREFIXES = [
  '<command-name>',
  '<command-message>',
  '<command-args>',
  '<local-command-stdout>',
  '<local-command-stderr>',
  '<system-reminder>',
  '<user-prompt-submit-hook>',
  'Caveat: The messages below',
]

/**
 * The speaker of a piece of text under a given role.
 *
 * `user` + text is the person — unless the text is one of the runtime's own
 * wrappers, in which case it is the runtime. `user` with NO text never reaches
 * here: a turn without text is not an utterance and gets folded into a work act
 * by {@link buildActs}.
 */
export function speakerOf(role: string, text: string): Speaker {
  if (role === 'assistant') return 'agent'
  if (role === 'user') {
    const head = text.trimStart()
    return RUNTIME_PREFIXES.some(p => head.startsWith(p)) ? 'runtime' : 'person'
  }
  return 'other'
}

/** The label a speaker is shown under. `you` is reserved for the person. */
export function speakerLabel(speaker: Speaker, role: string): string {
  switch (speaker) {
    case 'person': return 'you'
    case 'agent': return 'agent'
    case 'runtime': return 'runtime'
    default: return role
  }
}

function toolNames(turn: LogTurn): string[] {
  return turn.tools.map(t => (t.name && String(t.name).trim()) || '?')
}

/**
 * Fold a turn list into acts.
 *
 * The shape it folds, measured over six live logs (854 turns): an assistant
 * turn holding exactly one `tool_use`, followed by a `user` turn holding
 * exactly one `tool_result`, repeated. The general case is handled anyway
 * because the protocol permits it: several calls in one turn, several result
 * turns after one call turn, text and a call in the SAME turn (which produces
 * two acts — a sentence is not a side effect of a call), and either end of a
 * pair missing because the window was cut.
 */
export function buildActs(turns: LogTurn[]): Act[] {
  const acts: Act[] = []
  let open: WorkAct | null = null

  const closeOpen = () => {
    if (!open) return
    open.unanswered = Math.max(0, open.calls - open.results)
    acts.push(open)
    open = null
  }

  turns.forEach((turn, i) => {
    const names = toolNames(turn)
    const results = turn.results ?? 0

    // A sentence closes whatever act was open: text is a boundary, because it
    // is the thing the reader is scanning for and burying it inside a work act
    // would defeat the whole exercise.
    if (turn.text || turn.thinking) {
      closeOpen()
      acts.push({
        kind: 'say',
        speaker: speakerOf(turn.role, turn.text),
        role: turn.role,
        at: turn.timestamp,
        text: turn.text,
        thinking: turn.thinking,
        turn: i,
      })
    }

    if (names.length === 0 && results === 0) return

    if (names.length > 0) {
      // A new call group starts a new act unless the open one is still
      // unanswered — parallel calls arrive as one turn, but a runtime that
      // splits them across two turns before any result must not be split on
      // screen either.
      if (open && open.results > 0) closeOpen()
      if (!open) {
        open = {
          kind: 'work',
          at: turn.timestamp,
          names: [],
          calls: 0,
          results: 0,
          unanswered: 0,
          orphanResults: 0,
          errors: null,
          turns: [],
        }
      }
      open.names.push(...names)
      open.calls += names.length
      open.turns.push(i)
    }

    if (results > 0) {
      if (!open) {
        // A result with no call in this window. Its own act, and it says so —
        // attaching it to a later call would invent a pairing.
        open = {
          kind: 'work',
          at: turn.timestamp,
          names: [],
          calls: 0,
          results: 0,
          unanswered: 0,
          orphanResults: 0,
          errors: null,
          turns: [],
        }
      }
      open.results += results
      if (open.calls === 0) open.orphanResults += results
      if (!open.turns.includes(i)) open.turns.push(i)
      // Unknown stays unknown: only a turn that actually declares `errors`
      // moves the counter off `null`. A turn without the field leaves it where
      // it was, so one measured turn cannot vouch for an unmeasured one — the
      // act is `errorsKnown` only when every result turn in it declared.
      if (typeof turn.errors === 'number') {
        open.errors = (open.errors ?? 0) + turn.errors
      } else {
        open.errors = null
      }
      // Every call answered, and nothing else pending — close it, so the next
      // call group starts its own row.
      if (open.calls > 0 && open.results >= open.calls) closeOpen()
    }
  })

  closeOpen()
  return acts
}

/** How many acts carry an actual sentence — the 7.5% the screen exists to show. */
export function sayCount(acts: Act[]): number {
  return acts.filter(a => a.kind === 'say').length
}

/**
 * What the surface may state about failed tool calls across a set of acts.
 *
 * Three outcomes, and the third is the one the false-absence rule is about:
 *
 *  - `{ known: true, failed: n }` — measured, `n` may be 0 and that is a fact.
 *  - `{ known: false }` — at least one act's results carry no error flag, so
 *    the screen must NOT say that nothing failed.
 *  - `null` — there are no results at all, so there is nothing to say. A
 *    warning here would be a gate firing daily on nothing.
 */
export function errorStanding(acts: Act[]): { known: true; failed: number } | { known: false } | null {
  const work = acts.filter((a): a is WorkAct => a.kind === 'work' && a.results > 0)
  if (work.length === 0) return null
  if (work.some(a => a.errors === null)) return { known: false }
  return { known: true, failed: work.reduce((n, a) => n + (a.errors ?? 0), 0) }
}

/**
 * A compact label for a work act's tools: `Bash ×3 · Read`.
 *
 * Repeats are counted rather than repeated, and the ORDER of first appearance
 * is kept — this is one act, so nothing is hidden by counting inside it.
 */
export function toolSummary(act: WorkAct): string {
  const counts = new Map<string, number>()
  for (const n of act.names) counts.set(n, (counts.get(n) ?? 0) + 1)
  return [...counts.entries()].map(([n, c]) => (c > 1 ? `${n} ×${c}` : n)).join(' · ')
}
