import { describe, expect, it } from 'vitest'

import { answerable, boardChoices, oneClick, readyToSend, verdictSentence } from '../../src/lib/fleetRelayBoard'
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
