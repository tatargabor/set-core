/**
 * Turns → acts, asserted in the direction the old view failed in — task 7.20.
 *
 * The screen this replaces did three things, and only the third was cosmetic:
 * it printed `te` ("you") over machine-fed tool results, it split one action
 * across two rows with a role change between them, and it gave everything the
 * same weight. The first two are false values, so the tests below are written
 * as refutations rather than as happy paths:
 *
 *  - a turn with no text has NO speaker, and asking for one is the bug;
 *  - `role === 'user' ? 'te' : 'agent'` — the refuted implementation — is held
 *    here beside the right one, so a later "simplification" back to it fails
 *    instead of looking identical;
 *  - an unmeasured error count is `null`, never `0`. A test asserting `>= 0`
 *    passes on the build that reports "nothing failed" about something it never
 *    looked at, which is the false-absence direction and the expensive one.
 */
import { describe, expect, it } from 'vitest'

import {
  buildActs,
  errorStanding,
  sayCount,
  speakerLabel,
  speakerOf,
  toolSummary,
} from '../../src/lib/fleetConversation'
import type { LogTurn, SayAct, WorkAct } from '../../src/lib/fleetConversation'

function turn(over: Partial<LogTurn>): LogTurn {
  return {
    role: 'assistant',
    timestamp: '2026-08-19T12:05:00Z',
    text: '',
    thinking: '',
    tools: [],
    results: 0,
    sidechain: false,
    ...over,
  }
}

const call = (name: string, over: Partial<LogTurn> = {}) =>
  turn({ role: 'assistant', tools: [{ name, id: `t-${name}` }], ...over })
const result = (over: Partial<LogTurn> = {}) => turn({ role: 'user', results: 1, ...over })

describe('the role is not the speaker', () => {
  /**
   * The measurement that produced the task: 19 of 40 turns in one live session
   * were `user`-role, textless, carrying only a tool RESULT. Every one of them
   * rendered as `te`.
   */
  it('gives a textless `user` turn no speaker at all — it is not an utterance', () => {
    const acts = buildActs([call('Bash'), result()])
    expect(acts.map(a => a.kind)).toEqual(['work'])
    expect(sayCount(acts)).toBe(0)
  })

  it('keeps `you` for what the person actually said', () => {
    const acts = buildActs([turn({ role: 'user', text: 'csináld meg' })])
    const say = acts[0] as SayAct
    expect(say.kind).toBe('say')
    expect(say.speaker).toBe('person')
    expect(speakerLabel(say.speaker, say.role)).toBe('you')
  })

  /**
   * The second, quieter instance of the same defect. Measured over the six most
   * recent session logs: 41 `user` turns carry text and **9 of them were
   * written by the runtime**, not by the person.
   */
  it('names the runtime as the writer of its own wrappers, never the person', () => {
    for (const head of ['<command-name>/opsx:apply</command-name>', '<local-command-stdout>ok</local-command-stdout>', '<system-reminder>ne feledd</system-reminder>']) {
      expect(speakerOf('user', head)).toBe('runtime')
      expect(speakerLabel('runtime', 'user')).toBe('runtime')
    }
  })

  it('treats a person quoting a wrapper as the person — the prefix is anchored, not searched', () => {
    expect(speakerOf('user', 'miért van itt egy <command-name> blokk?')).toBe('person')
  })

  /**
   * The refuted implementation, held rather than described. `role === 'user' ?
   * 'te' : 'agent'` reads as a cleanup and reintroduces the whole defect; this
   * asserts the two disagree on the cases that matter, so the revert fails.
   */
  it('a bare role→label mapping would have got both of these wrong', () => {
    const naive = (t: LogTurn) => (t.role === 'user' ? 'you' : 'agent')

    const machine = result()
    expect(naive(machine)).toBe('you')
    expect(buildActs([call('Bash'), machine]).some(a => a.kind === 'say')).toBe(false)

    const runtimeTurn = turn({ role: 'user', text: '<command-name>/set:status</command-name>' })
    expect(naive(runtimeTurn)).toBe('you')
    expect(speakerOf(runtimeTurn.role, runtimeTurn.text)).toBe('runtime')
  })

  it('prints an unknown role as itself rather than guessing a speaker for it', () => {
    const acts = buildActs([turn({ role: 'system', text: 'valami' })])
    const say = acts[0] as SayAct
    expect(say.speaker).toBe('other')
    expect(speakerLabel(say.speaker, say.role)).toBe('system')
  })
})

describe('a call and its result are one act', () => {
  it('folds the pair into a single act with the call time', () => {
    const acts = buildActs([
      call('Bash', { timestamp: '2026-08-19T12:05:00Z' }),
      result({ timestamp: '2026-08-19T12:05:09Z' }),
    ])
    expect(acts).toHaveLength(1)
    const work = acts[0] as WorkAct
    expect(work.calls).toBe(1)
    expect(work.results).toBe(1)
    expect(work.unanswered).toBe(0)
    expect(work.at).toBe('2026-08-19T12:05:00Z')
  })

  it('folds several calls made in one turn with the results that answer them', () => {
    const acts = buildActs([
      turn({ tools: [{ name: 'Read', id: 'a' }, { name: 'Read', id: 'b' }, { name: 'Grep', id: 'c' }] }),
      result({ results: 3 }),
    ])
    expect(acts).toHaveLength(1)
    expect(toolSummary(acts[0] as WorkAct)).toBe('Read ×2 · Grep')
  })

  /**
   * The load-bearing negative. Merging consecutive acts would turn eighteen
   * tool rows into one tidy line — and put a failed call inside a summary,
   * which is the compaction the ui-quality rule forbids.
   */
  it('never merges two consecutive acts into one row', () => {
    const acts = buildActs([call('Bash'), result(), call('Bash'), result(), call('Bash'), result()])
    expect(acts).toHaveLength(3)
    expect(acts.every(a => a.kind === 'work')).toBe(true)
  })

  /**
   * Two call turns before any answer. Added after a mutation run: replacing the
   * `open.results > 0` guard with an unconditional close changed NOTHING in the
   * suite, which is the mutation being weak rather than the test — the measured
   * shape is strictly call→result→call→result, so nothing distinguished the two.
   * This is the case that does: a runtime that splits parallel calls across two
   * turns must not be split on screen either, and the guard is what holds that.
   */
  it('keeps calls made before any answer in one act', () => {
    const acts = buildActs([call('Read'), call('Grep'), result(), result()])
    expect(acts).toHaveLength(1)
    const work = acts[0] as WorkAct
    expect(work.calls).toBe(2)
    expect(work.results).toBe(2)
    expect(work.unanswered).toBe(0)
  })

  it('a sentence ends the open act rather than being folded into it', () => {
    const acts = buildActs([
      call('Bash'),
      result(),
      turn({ text: 'kész van' }),
      call('Read'),
      result(),
    ])
    expect(acts.map(a => a.kind)).toEqual(['work', 'say', 'work'])
  })

  it('a turn carrying both a sentence and a call produces both — a sentence is not a side effect', () => {
    const acts = buildActs([turn({ text: 'megnézem', tools: [{ name: 'Read', id: 'x' }] }), result()])
    expect(acts.map(a => a.kind)).toEqual(['say', 'work'])
  })

  it('marks a call still waiting for its answer instead of dropping the difference', () => {
    const acts = buildActs([call('Bash')])
    expect((acts[0] as WorkAct).unanswered).toBe(1)
  })

  it('keeps a result whose call was cut off as its own act rather than pairing it with a later call', () => {
    const acts = buildActs([result(), call('Read'), result()])
    expect(acts).toHaveLength(2)
    const orphan = acts[0] as WorkAct
    expect(orphan.calls).toBe(0)
    expect(orphan.orphanResults).toBe(1)
    expect((acts[1] as WorkAct).calls).toBe(1)
  })
})

describe('an unmeasured failure is not a zero', () => {
  it('reports `null` when the producer sends no error flag', () => {
    const acts = buildActs([call('Bash'), result()])
    expect((acts[0] as WorkAct).errors).toBeNull()
  })

  it('says the failure state is unknown rather than reporting none', () => {
    const standing = errorStanding(buildActs([call('Bash'), result()]))
    expect(standing).toEqual({ known: false })
  })

  it('counts them once the producer does send the flag', () => {
    const acts = buildActs([call('Bash'), result({ errors: 1 })])
    expect((acts[0] as WorkAct).errors).toBe(1)
    expect(errorStanding(acts)).toEqual({ known: true, failed: 1 })
  })

  it('a measured zero is a fact and says so', () => {
    expect(errorStanding(buildActs([call('Bash'), result({ errors: 0 })]))).toEqual({ known: true, failed: 0 })
  })

  /**
   * One measured turn may not vouch for an unmeasured one. A mixed window —
   * one old-shaped result, one new — is unknown, because the count would
   * otherwise be a partial sum presented as a total.
   */
  it('one declared turn does not make a mixed window measured', () => {
    const acts = buildActs([
      call('Bash'), result({ errors: 1 }),
      call('Read'), result(),
    ])
    expect(errorStanding(acts)).toEqual({ known: false })
  })

  it('says nothing at all when there are no results — a warning on nothing is noise', () => {
    expect(errorStanding(buildActs([turn({ text: 'szia' })]))).toBeNull()
    expect(errorStanding([])).toBeNull()
  })

  /**
   * The refuted shape: `errors ?? 0` type-checks everywhere and turns *we did
   * not look* into *nothing failed*.
   */
  it('a `?? 0` default would have claimed a clean run it never measured', () => {
    const work = buildActs([call('Bash'), result()])[0] as WorkAct
    expect(work.errors ?? 0).toBe(0)
    expect(work.errors).toBeNull()
  })
})

describe('the sentences are countable, which is what makes them findable', () => {
  it('counts only the acts that carry an utterance', () => {
    const turns = [
      turn({ role: 'user', text: 'kezdd el' }),
      call('Bash'), result(),
      call('Bash'), result(),
      turn({ text: 'kész' }),
    ]
    const acts = buildActs(turns)
    expect(acts).toHaveLength(4)
    expect(sayCount(acts)).toBe(2)
  })
})
