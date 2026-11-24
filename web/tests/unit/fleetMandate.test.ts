/**
 * The mandate on the tile and in the start form.
 *
 * The three absences must not look alike, a label must never be read as a goal,
 * and no sentence may claim that scope protection is enforced.
 */
import { describe, expect, it } from 'vitest'

import {
  DESK_RULE_NOTE, EMPTY_DRAFT, NOT_DECLARED_TITLE, NOT_STARTED_HERE_TITLE, NO_GOAL_NOTE,
  UNMEASURED_TITLE, WORK_RULE_NOTE,
  declareOutcome, deskCloseLabel, mandateFields, mandateStanding, parsePaths,
} from '../../src/lib/fleetMandate'
import type { FleetMandate } from '../../src/lib/fleetTypes'

const work: FleetMandate = {
  id: 'm-1', kind: 'work', goal: 'ship the importer',
  scope: { paths: ['src/import/'], change: 'importer' }, done_when: 'tests pass',
  requested_by: 'alpha#aaaaaaaa', requester_is_claim: true, source: 'start', delivered: true,
}

describe('what the tile says about a mandate', () => {
  it('shows the kind and the goal, and carries the rest in the title', () => {
    const s = mandateStanding({ mandate: work, mandate_absent: null })
    expect(s).toMatchObject({ kind: 'held', badge: 'work', goal: 'ship the importer', told: true })
    const title = s.kind === 'held' ? s.title : ''
    for (const part of ['src/import/', 'importer', 'tests pass', 'alpha#aaaaaaaa', 'a claim', WORK_RULE_NOTE])
      expect(title).toContain(part)
  })

  it('says a declared mandate has not reached the agent yet', () => {
    const s = mandateStanding({ mandate: { ...work, source: 'declared', delivered: false } })
    expect(s).toMatchObject({ kind: 'held', told: false })
    expect(s.kind === 'held' && s.title).toContain('NOT been told yet')
  })

  it('gives a desk the desk rule, not the work rule', () => {
    const s = mandateStanding({ mandate: { ...work, kind: 'desk', goal: 'Answer requests' } })
    expect(s.kind === 'held' && s.title).toContain(DESK_RULE_NOTE)
    expect(s.kind === 'held' && s.title).not.toContain(WORK_RULE_NOTE)
  })

  it('tells the two real absences apart', () => {
    const ours = mandateStanding({ mandate: null, mandate_absent: { reason: 'not-declared' }, terminal_label: 'a' })
    const hand = mandateStanding({ mandate: null, mandate_absent: { reason: 'not-started-here' }, session_id: 's' })
    expect(ours).toMatchObject({ kind: 'none', why: 'none declared', title: NOT_DECLARED_TITLE, canDeclare: true })
    expect(hand).toMatchObject({ kind: 'none', why: 'opened by hand', title: NOT_STARTED_HERE_TITLE, canDeclare: true })
    expect(NOT_STARTED_HERE_TITLE).toContain('nothing will tell the agent')
  })

  it('offers no declaration when there is no key to name the agent by', () => {
    const s = mandateStanding({ mandate: null, mandate_absent: { reason: 'not-started-here' } })
    expect(s).toMatchObject({ kind: 'none', canDeclare: false })
  })

  /** The refuted reading: an unreadable store drawn as "no mandate". */
  it('reports an unreadable store as unmeasured, never as no mandate', () => {
    const s = mandateStanding({ mandate: null, mandate_absent: { reason: 'unmeasured' }, terminal_label: 'a' })
    expect(s).toEqual({ kind: 'unmeasured', title: UNMEASURED_TITLE })
    // A reason this build has never heard of is not "none" either.
    expect(mandateStanding({ mandate: null, mandate_absent: { reason: 'something-new' } }).kind).toBe('unmeasured')
  })

  it('says nothing about a payload that predates mandates', () => {
    expect(mandateStanding({}).kind).toBe('unreported')
    expect(mandateStanding({ mandate: null, mandate_absent: null }).kind).toBe('unreported')
  })

  it('never reads a goal out of a label', () => {
    const s = mandateStanding({
      mandate: null, mandate_absent: { reason: 'not-declared' }, terminal_label: 'fix-the-login-bug',
    })
    expect(JSON.stringify(s)).not.toContain('login')
  })

  it('never claims the rule is enforced', () => {
    for (const text of [WORK_RULE_NOTE, DESK_RULE_NOTE, NOT_DECLARED_TITLE, NOT_STARTED_HERE_TITLE]) {
      expect(text).not.toMatch(/\bblock(ed|s)?\b|\bprevent(ed|s)?\b|\bcannot\b|\benforced\b(?! it)/i)
    }
    expect(WORK_RULE_NOTE).toMatch(/^Instructed to decline/)
    expect(WORK_RULE_NOTE).toContain('nothing enforces it')
  })
})

describe('the goal fields of the start form', () => {
  it('sends nothing when nothing was typed', () => {
    expect(mandateFields(EMPTY_DRAFT)).toEqual({ kind: 'none' })
    expect(mandateFields({ ...EMPTY_DRAFT, goal: '   ' })).toEqual({ kind: 'none' })
    expect(NO_GOAL_NOTE).toContain('no mandate')
  })

  it('sends only the fields that were filled', () => {
    expect(mandateFields({ ...EMPTY_DRAFT, goal: ' ship it ' }))
      .toEqual({ kind: 'mandate', mandate: { goal: 'ship it' } })
    expect(mandateFields({ goal: 'ship it', paths: 'src/a/, src/b/\nsrc/a/', change: ' c ', doneWhen: ' green ' }))
      .toEqual({ kind: 'mandate', mandate: { goal: 'ship it', paths: ['src/a/', 'src/b/'], change: 'c', done_when: 'green' } })
  })

  /** The server would start the agent and drop the scope without a word. */
  it('refuses a scope or a closing condition that has no goal', () => {
    for (const draft of [
      { ...EMPTY_DRAFT, paths: 'src/' }, { ...EMPTY_DRAFT, change: 'c' }, { ...EMPTY_DRAFT, doneWhen: 'green' },
    ]) expect(mandateFields(draft).kind).toBe('problem')
  })

  it('splits paths on lines and commas', () => {
    expect(parsePaths(' a/ ,b/\n\n c/ , a/')).toEqual(['a/', 'b/', 'c/'])
    expect(parsePaths('  ')).toEqual([])
  })
})

describe('what a declaration came to', () => {
  it('says the agent will be told only when the framework can tell it', () => {
    expect(declareOutcome({ carrier: true })).toMatchObject({ told: true })
    expect(declareOutcome({ carrier: true }).text).toContain('next session start')
    for (const answer of [{ carrier: false }, {}, null]) {
      const out = declareOutcome(answer)
      expect(out.told).toBe(false)
      expect(out.text).toContain('Nothing tells this agent')
    }
  })
})

describe('the desk close countdown (fleet-mandate-and-desk 10.4)', () => {
  const desk: FleetMandate = { ...work, id: 'm-d', kind: 'desk', goal: 'Answer requests' }

  it('shows the minutes left, rounded up, on a desk with a forecast', () => {
    const l = deskCloseLabel({ mandate: desk, desk_close: { closes_in_seconds: 61, bound_seconds: 300 } })
    expect(l?.text).toBe('closes in ~2 min')
    expect(l?.title).toContain('unless another request arrives')
    expect(l?.title).toContain('5 min')
  })

  it('says closing at zero, never a negative or zero-minute countdown', () => {
    expect(deskCloseLabel({ mandate: desk, desk_close: { closes_in_seconds: 0, bound_seconds: 300 } })?.text)
      .toBe('closing')
  })

  it('shows nothing without a forecast, or on a work agent', () => {
    expect(deskCloseLabel({ mandate: desk, desk_close: null })).toBeNull()
    expect(deskCloseLabel({ mandate: desk })).toBeNull()
    expect(deskCloseLabel({ mandate: work, desk_close: { closes_in_seconds: 60, bound_seconds: 300 } })).toBeNull()
    expect(deskCloseLabel({ mandate: null, desk_close: { closes_in_seconds: 60, bound_seconds: 300 } })).toBeNull()
  })
})
