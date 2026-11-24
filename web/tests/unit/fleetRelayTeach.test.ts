import { describe, expect, it } from 'vitest'

import {
  answerFieldCount, canAlsoTeach, canSendOwn, ownAnswerBlocked, parseDetail, prefillAnswer, teachResultLines, waitsForText,
  type TeachResult,
} from '../../src/lib/fleetRelayTeach'

const base = {
  id: 'relay-1', project: 'proj', kind: 'question', questions: 1, seconds: 120, release_requested: false,
  waits_for: 'answer',
  decider: { state: 'forwarded', method: 'fork', seconds_left: null, questions: [
    { key: 'Q1', question: 'Mehet élesbe?', options: ['Igen (Recommended)', 'Még ne'], outcome: 'no-decision',
      reason: 'abstained', choice: null, tier: null, confidence: null, references: [] },
  ] },
  teach: { allowed: true, reason: '', prefill: '' },
}

describe('fleet-relay-teach helpers', () => {
  it('parses the detail and rejects a wrong shape', () => {
    const d = parseDetail(base)!
    expect(d.decider?.questions[0].options).toEqual(['Igen (Recommended)', 'Még ne'])
    expect(parseDetail({ id: 1 })).toBeNull()
    expect(parseDetail({ ...base, decider: null })!.decider).toBeNull()
  })

  it('prefills the proposal, else the recommended option, else nothing', () => {
    expect(prefillAnswer(parseDetail({ ...base, teach: { ...base.teach, prefill: '→ Run the tests' } })!)).toBe('Run the tests')
    expect(prefillAnswer(parseDetail(base)!)).toBe('Igen (Recommended)')
    const plain = { ...base, decider: { ...base.decider, questions: [{ ...base.decider.questions[0], options: ['A', 'B'] }] } }
    expect(prefillAnswer(parseDetail(plain)!)).toBe('')
  })

  it('says what the call waits for', () => {
    expect(waitsForText(parseDetail({ ...base, waits_for: 'release' })!)).toMatch(/terminal/)
    expect(waitsForText(parseDetail({ ...base, waits_for: 'countdown', decider: { ...base.decider, seconds_left: 41.6 } })!)).toMatch(/42s/)
    expect(waitsForText(parseDetail({ ...base, kind: 'permission' })!)).toMatch(/only by a person/)
  })

  it('reports each step and is ok only when answered (or gone), written and committed', () => {
    const r: TeachResult = { answered: true, answer_reason: '', written: true, rules_file: '.claude/rules/auto-answer-taught.md',
      project: 'proj', commit: { sha: 'abc1234', branch: 'main', reason: '' } }
    expect(teachResultLines(r)).toEqual({ ok: true, lines: ['Answered — the agent has it.',
      'Rule committed in proj (main) as abc1234 — .claude/rules/auto-answer-taught.md. Not pushed.'] })
    const hook = teachResultLines({ ...r, commit: { sha: '', branch: 'main', reason: 'the commit was refused: blocked' } })
    expect(hook.ok).toBe(false)
    expect(hook.lines[1]).toMatch(/not committed: the commit was refused: blocked/)
    expect(teachResultLines({ ...r, answered: false, answer_reason: 'the question was no longer waiting, so nothing was answered' }).ok).toBe(true)
    expect(teachResultLines({ ...r, answered: false, answer_reason: 'boom' }).ok).toBe(false)
    expect(teachResultLines({ ...r, written: false, commit: { sha: '', branch: '', reason: 'not a git repository' } }).lines[1])
      .toBe('Rule not written: not a git repository')
  })
})

describe('fleet-relay-answer-own helpers', () => {
  it('counts one field per question: the decider list first, else the relay count', () => {
    expect(answerFieldCount(parseDetail(base)!)).toBe(1)
    expect(answerFieldCount(parseDetail({ ...base, decider: null, questions: 3 })!)).toBe(3)
    expect(answerFieldCount(parseDetail({ ...base, decider: null, questions: null })!)).toBe(1)
  })

  it('is not offered for a permission prompt or a released call', () => {
    expect(ownAnswerBlocked(parseDetail(base)!)).toBeNull()
    expect(ownAnswerBlocked(parseDetail({ ...base, kind: 'permission' })!)).toMatch(/Allow or Deny/)
    expect(ownAnswerBlocked(parseDetail({ ...base, release_requested: true })!)).toMatch(/terminal/)
  })

  it('sends only when every field holds text', () => {
    expect(canSendOwn(['Nem'], 1)).toBe(true)
    expect(canSendOwn(['  '], 1)).toBe(false)
    expect(canSendOwn(['a', ''], 2)).toBe(false)
    expect(canSendOwn(['a'], 2)).toBe(false)
  })

  it('offers also-teach only for one question where teach is allowed', () => {
    expect(canAlsoTeach(parseDetail(base)!)).toBe(true)
    expect(canAlsoTeach(parseDetail({ ...base, teach: { ...base.teach, allowed: false } })!)).toBe(false)
    expect(canAlsoTeach(parseDetail({ ...base, decider: null, questions: 2 })!)).toBe(false)
  })
})
