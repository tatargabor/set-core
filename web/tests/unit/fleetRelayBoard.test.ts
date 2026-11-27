import { describe, expect, it } from 'vitest'

import {
  answerable, boardChoices, composeAnswer, oneClick, PERMISSION_ANSWERS, permissionButtons, readyToSend, rowStatus, statusCounts, taughtLine, verdictSentence,
} from '../../src/lib/fleetRelayBoard'
import type { WaitingQuestion } from '../../src/lib/fleetRelay'
import { parseDetail, type DetailQuestion } from '../../src/lib/fleetRelayTeach'

const q = (over: Partial<DetailQuestion> = {}): DetailQuestion => ({
  key: 'Q1', question: 'Melyik menjen előbb?', options: ['Előbb a devauth-os felvétel', 'Előbb a UNAS (Recommended)'],
  outcome: 'below-bar', reason: 'likely 0.60 below 0.80', choice: 'Előbb a devauth-os felvétel', tier: 'likely',
  confidence: 0.6, references: [], ...over,
})

const detail = (questions: DetailQuestion[], over: Record<string, unknown> = {}) => parseDetail({
  id: 'relay-1', project: 'p', kind: 'question', questions: questions.length, seconds: 60, release_requested: false,
  waits_for: 'answer', decider: { state: 'forwarded', method: 'fork', seconds_left: null, questions },
  teach: { allowed: true, reason: '', prefill: '' }, ...over,
})!

describe('fleet-relay-board', () => {
  it('marks the proposal and the recommended option, and sends the option text unchanged', () => {
    const c = boardChoices(q())
    expect(c.map(x => [x.value, x.proposed, x.recommended])).toEqual([
      ['Előbb a devauth-os felvétel', true, false],
      ['Előbb a UNAS (Recommended)', false, true],
    ])
  })

  it('a continuation: the → mark is dropped from the label, kept in the value, and still matches the proposal', () => {
    const c = boardChoices(q({ options: ['→ Nézd meg a box2-t.'], choice: '→ Nézd meg a box2-t.' }))
    expect(c).toEqual([{ value: '→ Nézd meg a box2-t.', label: 'Nézd meg a box2-t.', proposed: true, recommended: false }])
  })

  it('a proposal outside the options is offered as an extra choice', () => {
    const c = boardChoices(q({ options: ['→ A'], choice: 'Do B instead' }))
    expect(c.map(x => [x.label, x.proposed])).toEqual([['A', false], ['Do B instead', true]])
  })

  it('no proposal adds nothing', () => {
    expect(boardChoices(q({ choice: null })).some(x => x.proposed)).toBe(false)
  })

  it('one click answers a single-question call only', () => {
    expect(oneClick(detail([q()]))).toBe(true)
    expect(oneClick(detail([q(), q({ key: 'Q2' })]))).toBe(false)
    expect(oneClick(detail([q()], { kind: 'permission' }))).toBe(false)
    expect(oneClick(detail([q()], { release_requested: true }))).toBe(false)
    expect(oneClick(detail([]))).toBe(false)
  })

  it('a permission prompt and a call handed back get no answer controls', () => {
    expect(answerable(detail([q()], { kind: 'permission' }))).toBe(false)
    expect(answerable(detail([q()], { release_requested: true }))).toBe(false)
    expect(answerable(detail([q()]))).toBe(true)
  })

  it('a permission prompt gets exactly Allow and Deny, unless it was handed back', () => {
    expect(PERMISSION_ANSWERS).toEqual(['Allow', 'Deny'])
    expect(permissionButtons(detail([q()], { kind: 'permission' }))).toBe(true)
    expect(permissionButtons(detail([], { kind: 'permission', decider: null }))).toBe(true)
    expect(permissionButtons(detail([q()], { kind: 'permission', release_requested: true }))).toBe(false)
    expect(permissionButtons(detail([q()]))).toBe(false)
  })

  it('a several-question call is ready only when every question has an answer', () => {
    expect(readyToSend(['a', 'b'], 3)).toBe(false)
    expect(readyToSend(['a', ' ', 'c'], 3)).toBe(false)
    expect(readyToSend(['a', undefined, 'c'], 3)).toBe(false)
    expect(readyToSend(['a', 'b', 'c'], 3)).toBe(true)
    expect(readyToSend([], 0)).toBe(false)
  })

  it('the verdict carries the decider\'s reason, not a generic line', () => {
    expect(verdictSentence(q({ outcome: 'no-decision', choice: null, reason: 'abstained: Only the operator knows when he is free.' }), null))
      .toEqual({ text: 'No proposal: Only the operator knows when he is free.', tone: 'muted' })
    expect(verdictSentence(q(), null).text).toBe('Proposed «Előbb a devauth-os felvétel», not sure enough to write it (likely 0.60 below 0.80).')
    expect(verdictSentence(q({ outcome: 'excluded', reason: 'outward step: send' }), null).text).toContain('not written: outward step: send')
    expect(verdictSentence(q({ outcome: 'allowed' }), 41.6).text).toBe('Writes «Előbb a devauth-os felvétel» in 42 s unless you answer first.')
    expect(verdictSentence(q({ outcome: null }), null).text).toBe('The decider is still reading it.')
  })
})


describe('fleet-relay-board: a note beside the option, teach per question', () => {
  it('a note travels with the option instead of replacing it', () => {
    expect(composeAnswer('Nem tudom, kérdezd meg', 'a GLS ügyfélszolgálatot')).toBe('Nem tudom, kérdezd meg — a GLS ügyfélszolgálatot')
    expect(composeAnswer('Ugyanaz működik', '  ')).toBe('Ugyanaz működik')
    expect(composeAnswer(undefined, 'saját válasz')).toBe('saját válasz')
    expect(composeAnswer('', '')).toBe('')
  })

  it('says whether the rule landed', () => {
    const base = { written: true, project: 'proj', rules_file: '.claude/rules/auto-answer-taught.md', commit: { sha: 'abc1234', branch: 'main', reason: '' } }
    expect(taughtLine(base, 1)).toEqual({ text: 'Rule committed in proj (main) as abc1234. Not pushed.', ok: true })
    expect(taughtLine({ ...base, commit: { sha: '', branch: '', reason: 'hook refused' } }, 2)!.ok).toBe(false)
    expect(taughtLine({ ...base, written: false, commit: { sha: '', branch: '', reason: 'no checkout' } }, 1)!.text).toBe('Rule not written: no checkout')
    expect(taughtLine(null, 1)).toBeNull()
    expect(taughtLine(base, 0)).toBeNull()
  })
})

describe('fleet-relay-board row status', () => {
  const w = (over: Partial<WaitingQuestion> = {}): WaitingQuestion => ({
    id: 'relay-1', session_id: 's1', project: 'p', questions: 1, target: 'command', seconds: 20,
    release_requested: false, kind: 'question', auto_answer: null, auto_on: true, auto_off: null, ...over,
  })
  const key = (s: ReturnType<typeof rowStatus>) => [s.key, s.why]

  it('a fresh call with the decider on and no verdict yet is "decider reading", not yours', () => {
    expect(rowStatus(w(), null, false, 120).key).toBe('reading')
    expect(rowStatus(w({ seconds: 149 }), null, false, 120).key).toBe('reading')
  })

  it('past the bound with no verdict it is yours, naming that the decider gave none', () => {
    expect(key(rowStatus(w({ seconds: 151 }), null, false, 120))).toEqual(['yours', 'the decider gave no verdict'])
  })

  it('auto off — for the machine or for this agent — is yours, never "reading"', () => {
    expect(key(rowStatus(w({ auto_on: false, auto_off: 'off' }), null, false, 120))).toEqual(['yours', 'auto answering is off'])
    expect(key(rowStatus(w({ auto_on: false, auto_off: 'agent' }), null, false, 120))).toEqual(['yours', 'auto off for this agent'])
    expect(rowStatus(w({ auto_on: undefined }), null, false, 120).key).toBe('yours')
  })

  it('an allowed proposal with a countdown is "auto in N s"', () => {
    const s = rowStatus(w(), detail([q({ outcome: 'allowed' })], { decider: { state: 'proposed', method: 'fork', seconds_left: 41.6, questions: [q({ outcome: 'allowed' })] } }), false, 120)
    expect([s.key, s.word, s.tone]).toEqual(['due', 'auto in 42 s', 'auto'])
  })

  it('the list summary alone is enough for the countdown (detail not read yet)', () => {
    const v = { state: 'proposed', outcome: 'allowed', reason: '', choice: 'A', tier: 'decided', seconds_left: 10 }
    expect(rowStatus(w({ auto_answer: v }), null, false, 120).key).toBe('due')
  })

  it('every verdict that is not written says why it is yours', () => {
    const one = (outcome: string) => key(rowStatus(w(), detail([q({ outcome })]), false, 120))
    expect(one('excluded')).toEqual(['yours', 'outward step'])
    expect(one('no-decision')).toEqual(['yours', 'no source settles it'])
    expect(one('below-bar')).toEqual(['yours', 'not sure enough to write it'])
  })

  it('a two-question call with one allowed and one excluded is yours for the outward step', () => {
    expect(key(rowStatus(w(), detail([q({ outcome: 'held' }), q({ outcome: 'excluded' })]), false, 120)))
      .toEqual(['yours', 'outward step'])
  })

  it('precedence: answered beats permission beats to-terminal beats a verdict', () => {
    const perm = w({ kind: 'permission' })
    expect(rowStatus(perm, null, true, 120).key).toBe('answered')
    expect(rowStatus({ ...perm, release_requested: true }, null, false, 120).key).toBe('permission')
    expect(rowStatus(w({ release_requested: true }), detail([q({ outcome: 'excluded' })]), false, 120).key).toBe('terminal')
  })

  it('a cancelled automatic answer is yours', () => {
    expect(key(rowStatus(w(), detail([q({ outcome: 'allowed' })], { decider: { state: 'cancelled', method: 'fork', seconds_left: null, questions: [q({ outcome: 'allowed' })] } }), false, 120)))
      .toEqual(['yours', 'the automatic answer was cancelled'])
  })

  it('the heading counts per status, yours first, zeros left out', () => {
    const c = statusCounts([
      rowStatus(w(), null, false, 120),
      rowStatus(w(), detail([q({ outcome: 'excluded' })]), false, 120),
      rowStatus(w({ auto_on: false, auto_off: 'off' }), null, false, 120),
    ])
    expect(c.map(x => [x.key, x.n])).toEqual([['yours', 2], ['reading', 1]])
  })
})
