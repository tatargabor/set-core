/**
 * The recorded fleet, and the one summary that must never overclaim.
 *
 * The defect these tests exist to prevent is not a crash. It is a green
 * "Restored" over six agents that never came back — the count is the part a
 * reader takes away, and a true count can still describe a partial result as a
 * whole one.
 */

import { describe, expect, it } from 'vitest'
import {
  ageLabel, allBlocked, canRestore, composition, groupByLabel, offerFor,
  restoreOffer, summarise, turnSummary,
  type PeekTurn, type RestoreResult, type RosterAnswer, type RosterEntry,
} from '../../src/lib/fleetRoster'

function entry(over: Partial<RosterEntry> = {}): RosterEntry {
  return {
    key: 'S1', session_id: 'S1', label: 'proj-1', cwd: '/p', project: 'proj',
    kind: 'interactive', first_seen: 1000, last_seen: 2000, session_log: '/log',
    resumable: true, not_resumable_reason: null, ...over,
  }
}

function answer(entries: RosterEntry[], over: Partial<RosterAnswer> = {}): RosterAnswer {
  return { project: 'proj', entries, record_exists: true, unreadable: false, ...over }
}

function result(over: Partial<RestoreResult> = {}): RestoreResult {
  return { project: 'proj', attempted: 0, started: [], skipped: [], failed: [],
           record_exists: true, complete: true, ...over }
}

const outcome = (status: 'started' | 'skipped' | 'failed', reason: string | null = null) => ({
  key: 'K', session_id: 'S', label: 'l', cwd: '/p', last_seen: 1, status, reason,
})

describe('the restore summary never overclaims', () => {
  it('says how many did NOT start, not only how many did', () => {
    const s = summarise(result({
      attempted: 9, complete: false,
      started: [outcome('started'), outcome('started'), outcome('started')] as any,
      skipped: [outcome('skipped', 'live'), outcome('skipped', 'live'),
                outcome('skipped', 'no transcript'), outcome('skipped', 'no transcript')] as any,
      failed: [outcome('failed', 'refused'), outcome('failed', 'refused')] as any,
    }))
    expect(s.headline).toContain('3 of 9')
    expect(s.headline).toContain('6 did not start')
    expect(s.unfinished).toHaveLength(6)
    expect(s.complete).toBe(false)
  })

  it('every unfinished entry carries a reason', () => {
    const s = summarise(result({
      attempted: 2, complete: false,
      started: [outcome('started')] as any,
      skipped: [outcome('skipped', 'session is bound to a live process')] as any,
    }))
    expect(s.unfinished.every(o => !!o.reason)).toBe(true)
  })

  it('only calls it complete when the SERVER did', () => {
    // Recomputing `complete` here would be a second definition, and the copy
    // that drifts is always the one being read. So a server that says false
    // wins even when the counts look complete.
    const s = summarise(result({ attempted: 3, complete: false,
                                 started: [outcome('started'), outcome('started'),
                                           outcome('started')] as any }))
    expect(s.complete).toBe(false)
    expect(s.headline).not.toMatch(/^All /)
  })

  it('says nothing was attempted when nothing was recorded', () => {
    const s = summarise(result({ attempted: 0 }))
    expect(s.headline).toContain('Nothing was recorded')
    expect(s.headline).not.toContain('restored')
  })

  it('does not read as a success when none started', () => {
    const s = summarise(result({ attempted: 4, complete: false,
                                 skipped: [outcome('skipped', 'live'), outcome('skipped', 'live'),
                                           outcome('skipped', 'live'), outcome('skipped', 'live')] as any }))
    expect(s.headline).toContain('None of the 4')
    expect(s.started).toBe(0)
  })

  it('a clean restore is allowed to say so', () => {
    // The negative control: if every headline hedged, the hedge would carry no
    // information and the partial cases would stop standing out.
    const s = summarise(result({ attempted: 2, complete: true,
                                 started: [outcome('started'), outcome('started')] as any }))
    expect(s.headline).toBe('All 2 restored.')
  })
})

describe('the offer states what the act can actually deliver', () => {
  it('names both numbers when some entries cannot be resumed', () => {
    const offer = restoreOffer(answer([
      entry(), entry({ key: 'S2', session_id: 'S2' }),
      entry({ key: 'S3', session_id: 'S3', resumable: false,
              not_resumable_reason: 'no transcript', session_log: null }),
    ]))
    expect(offer.total).toBe(3)
    expect(offer.resumable).toBe(2)
    expect(offer.label).toContain('2 of 3')
    expect(offer.label).toContain('cannot be resumed')
  })

  it('states one number when everything can come back', () => {
    expect(restoreOffer(answer([entry()])).label).toBe('Restore 1 agent')
  })

  it('offers nothing for a project with no entries', () => {
    // A control that would do nothing invites the click that teaches the reader
    // the screen is lying about having something.
    expect(canRestore(answer([]))).toBe(false)
    expect(canRestore(null)).toBe(false)
    expect(canRestore(answer([entry()]))).toBe(true)
  })

  it('offers restore even when nothing is resumable, and says so', () => {
    // Deliberate: the entries are still information — they are the agents the
    // user had. Hiding the control would also hide the fact that they are gone.
    const a = answer([entry({ resumable: false, session_log: null,
                              not_resumable_reason: 'no transcript' })])
    expect(canRestore(a)).toBe(true)
    expect(restoreOffer(a).label).toContain('0 of 1')
  })
})

describe('age labels', () => {
  it('reads in the unit a person would use', () => {
    expect(ageLabel(30)).toBe('30s')
    expect(ageLabel(600)).toBe('10m')
    expect(ageLabel(7200)).toBe('2.0h')
    expect(ageLabel(200000)).toBe('2.3d')
  })

  it('says unknown rather than inventing a number', () => {
    expect(ageLabel(NaN)).toBe('unknown')
    expect(ageLabel(-1)).toBe('unknown')
  })
})

describe('a body of the wrong shape costs a control, never the screen', () => {
  // Found by the existing fleet suite: its fetch mocks answer every /api/fleet
  // URL with the AGENT LISTING payload, which has no `entries` at all. The first
  // version of this module read `answer.entries.length` and threw inside a
  // render, taking down 62 tests across 11 files.
  //
  // Held as a test rather than a comment, because a later "simplification" back
  // to `answer.entries.length` looks identical and fails only at runtime, on a
  // screen, in front of someone.

  it('treats a payload with no entries list as nothing recorded', () => {
    const wrong = { agents: 3, projects: [{ name: 'demo' }] } as unknown as RosterAnswer
    expect(canRestore(wrong)).toBe(false)
    expect(() => restoreOffer(wrong)).not.toThrow()
    expect(restoreOffer(wrong).total).toBe(0)
  })

  it('treats an entries field that is not an array as nothing recorded', () => {
    const wrong = { project: 'p', entries: 'lots', record_exists: true } as unknown as RosterAnswer
    expect(canRestore(wrong)).toBe(false)
  })

  it('summarises a result whose lists are missing without throwing', () => {
    const wrong = { project: 'p', attempted: 3 } as unknown as RestoreResult
    const s = summarise(wrong)
    expect(s.started).toBe(0)
    expect(s.complete).toBe(false)
    // And it must not claim completeness from an absent flag: `undefined` is
    // not `true`, and reading it as one would report a restore nobody measured.
    expect(s.headline).not.toMatch(/^All /)
  })

  it('a truthy-but-not-true complete flag does not count as complete', () => {
    const wrong = { project: 'p', attempted: 1, started: [], skipped: [], failed: [],
                    complete: 'yes' } as unknown as RestoreResult
    expect(summarise(wrong).complete).toBe(false)
  })
})

describe('the offer never promises what the act would skip', () => {
  // Found by LOOKING at the running screen, 2026-08-21 — not by any test.
  // The control read "Restore 7 agents" for a project whose seven sessions were
  // all alive; restore skips a live session, so the button promised an act that
  // would have done nothing. Resumable is about the transcript. Restorable is
  // about the transcript AND nobody being on it.

  const live = (over: Partial<RosterEntry> = {}) => entry({ running: true, ...over })
  const dead = (over: Partial<RosterEntry> = {}) => entry({ running: false, ...over })

  it('subtracts the sessions that are already running', () => {
    const offer = restoreOffer(answer([live({ key: 'A' }), dead({ key: 'B' }), dead({ key: 'C' })]))
    expect(offer.restorable).toBe(2)
    expect(offer.label).toContain('Restore 2 of 3')
    expect(offer.label).toContain('1 already running')
  })

  it('offers no act at all when everything recorded is up', () => {
    const offer = restoreOffer(answer([live({ key: 'A' }), live({ key: 'B' })]))
    expect(offer.actionable).toBe(false)
    expect(offer.label).toBe('All 2 already running')
    expect(offer.label).not.toContain('Restore')
  })

  it('counts BOTH reasons separately when they occur together', () => {
    const offer = restoreOffer(answer([
      live({ key: 'A' }), dead({ key: 'B' }),
      dead({ key: 'C', resumable: false, session_log: null, not_resumable_reason: 'no transcript' }),
    ]))
    expect(offer.label).toContain('Restore 1 of 3')
    expect(offer.label).toContain('1 already running')
    expect(offer.label).toContain('1 cannot be resumed')
  })

  it('an UNMEASURED liveness is never subtracted', () => {
    // `null` is "we could not ask". Counting it as running would shrink what
    // the button offers on the strength of a measurement nobody took — and it
    // fails toward offering LESS than is there, which reads as data loss.
    const offer = restoreOffer(answer([entry({ key: 'A', running: null }),
                                       entry({ key: 'B', running: null })]))
    expect(offer.running).toBe(0)
    expect(offer.restorable).toBe(2)
    expect(offer.label).toBe('Restore 2 agents')
  })

  it('an older server that says nothing about running is not treated as running', () => {
    const offer = restoreOffer(answer([entry({ key: 'A' })]))  // no `running` key at all
    expect(offer.actionable).toBe(true)
    expect(offer.label).toBe('Restore 1 agent')
  })
})

describe('a restored agent says WHICH name came back', () => {
  const named = (name_source: string, over: Record<string, unknown> = {}) => ({
    ...outcome('started'), name_source, label_used: 'l', ...over,
  })

  it('separates the agents nobody named from the ones that did not start', () => {
    const s = summarise(result({
      attempted: 3, complete: true,
      started: [named('restored'),
                named('renamed', { key: 'K2', wanted_label: 'wanted', label_used: 'wanted-r2' }),
                named('derived', { key: 'K3', label_used: 'proj-restored' })] as any,
    }))
    // They started. They are not failures and must not be marked as ones.
    expect(s.unfinished).toHaveLength(0)
    expect(s.unnamed.map(o => o.key)).toEqual(['K2', 'K3'])
    expect(s.headline).toContain('All 3 restored')
  })

  it('treats a missing name_source as unknown, never as derived', () => {
    // An older server says nothing about where the name came from. Claiming it
    // invented one would put a warning on the screen with nothing behind it.
    const s = summarise(result({ attempted: 1, complete: true, started: [outcome('started')] as any }))
    expect(s.unnamed).toHaveLength(0)
  })
})

/**
 * What was OPEN, versus what is merely remembered.
 *
 * Measured 2026-08-26 on one machine: 233 recorded entries against 13 that were
 * open in the last observed round, because an entry is keyed on the session id
 * and a resume mints a new one. The offer built from the record was honest
 * about what it would do — and what it would do was start conversations nobody
 * had left open.
 */
describe('the last composition', () => {
  const open = (over: Partial<RosterEntry> = {}) => entry({ in_last_round: true, ...over })
  const past = (over: Partial<RosterEntry> = {}) => entry({ in_last_round: false, ...over })

  it('splits the record into what was open and the rest', () => {
    const c = composition(answer(
      [open({ key: 'A' }), past({ key: 'B' }), past({ key: 'C' })],
      { last_round_at: 5000 },
    ))
    expect(c.known).toBe(true)
    expect(c.entries.map(e => e.key)).toEqual(['A'])
    expect(c.rest.map(e => e.key)).toEqual(['B', 'C'])
    expect(c.observedAt).toBe(5000)
  })

  it('offers only the composition, and its keys are what the request carries', () => {
    const c = composition(answer([open({ key: 'A' }), open({ key: 'B' }), past({ key: 'C' })]))
    const offer = offerFor(c.entries)
    expect(offer.restorable).toBe(2)
    expect(offer.keys).toEqual(['A', 'B'])
    expect(offer.label).toBe('Restore 2 agents')
  })

  it('a fleet observed with nothing open reports an EMPTY composition, not the previous round', () => {
    // The reason the round is a stored stamp rather than max(last_seen): a
    // derived answer would hand back agents the user had already closed and
    // call them "what was open".
    const c = composition(answer([past({ key: 'A' }), past({ key: 'B' })], { last_round_at: 9000 }))
    expect(c.known).toBe(true)
    expect(c.entries).toEqual([])
    expect(c.rest).toHaveLength(2)
  })

  it('a record that cannot say is UNKNOWN, never "nothing was open"', () => {
    // `undefined` is an older server, `null` is a record with no observation.
    // Neither may read as `false`, which would mean the agent was not open.
    for (const value of [undefined, null]) {
      const c = composition(answer([entry({ key: 'A', in_last_round: value })]))
      expect(c.known).toBe(false)
      expect(c.reason).toContain('does not say')
      expect(c.rest.map(e => e.key)).toEqual(['A'])
      expect(c.entries).toEqual([])
    }
  })

  it('a mixed answer, where only some entries carry the field, is unknown rather than partly known', () => {
    // Half an answer is not half a composition. Treating the entries that
    // happen to carry the field as the whole truth would offer a subset of a
    // subset, with nothing saying so.
    const c = composition(answer([open({ key: 'A' }), entry({ key: 'B' })]))
    expect(c.known).toBe(false)
    expect(c.rest).toHaveLength(2)
  })

  it('an empty record is not a composition', () => {
    expect(composition(answer([])).known).toBe(false)
    expect(composition(null).known).toBe(false)
  })

  it('the offer keys never include a running or unresumable entry', () => {
    const offer = offerFor([
      open({ key: 'A' }),
      open({ key: 'B', running: true }),
      open({ key: 'C', resumable: false, session_log: null, not_resumable_reason: 'no transcript' }),
    ])
    expect(offer.keys).toEqual(['A'])
    expect(offer.restorable).toBe(1)
  })
})

/**
 * One label, several conversations — B-80.
 *
 * Measured on a live record 2026-08-26: six entries read the same label and
 * differed only by an age. The list was honest and nobody could choose from it.
 */
describe('lineages', () => {
  const at = (key: string, label: string | null, last_seen: number, over: Partial<RosterEntry> = {}) =>
    entry({ key, label, last_seen, ...over })

  it('groups repeated labels, newest first inside and between', () => {
    const lines = groupByLabel([
      at('A', 'bugfix', 100), at('B', 'other', 500), at('C', 'bugfix', 900), at('D', 'bugfix', 300),
    ])
    expect(lines.map(l => [l.label, l.entries.length])).toEqual([['bugfix', 3], ['other', 1]])
    expect(lines[0].entries.map(e => e.key)).toEqual(['C', 'D', 'A'])
    expect(lines[0].key).toBe('C')
  })

  it('a label with one entry is a lineage of one, not a group to open', () => {
    const lines = groupByLabel([at('A', 'solo', 100)])
    expect(lines).toHaveLength(1)
    expect(lines[0].entries).toHaveLength(1)
  })

  it('two unlabelled entries are never merged into one agent', () => {
    // They have nothing in common but the absence of a name. Grouping them
    // would claim they are the same agent, which the record does not say.
    const lines = groupByLabel([at('A', null, 100), at('B', null, 200)])
    expect(lines).toHaveLength(2)
    expect(lines.map(l => l.label).sort()).toEqual(['A', 'B'])
  })

  it('says when nothing in a lineage can come back', () => {
    const gone = { resumable: false, session_log: null, not_resumable_reason: 'no transcript' }
    expect(allBlocked([at('A', 'x', 1, gone), at('B', 'x', 2, { running: true })])).toBe(true)
    expect(allBlocked([at('A', 'x', 1, gone), at('B', 'x', 2)])).toBe(false)
  })
})

describe('a turn that says nothing is described by what it did', () => {
  const turn = (over: Partial<PeekTurn> = {}): PeekTurn =>
    ({ role: 'assistant', timestamp: null, text: '', thinking: '', tools: [], results: 0, ...over })

  it('renders the text when there is text', () => {
    expect(turnSummary(turn({ text: 'hello' }))).toBe('hello')
  })

  it('names the tools when there is no text', () => {
    // Measured on the live record: the last turn of a recorded session is often
    // a tool-only assistant turn or an empty user entry. Dropping those would
    // make the peek look like it found nothing; drawing them blank is worse.
    expect(turnSummary(turn({ tools: [{ name: 'Bash' }, { name: 'Read' }] }))).toBe('ran Bash, Read')
    expect(turnSummary(turn({ results: 2 }))).toBe('2 tool results')
    expect(turnSummary(turn({ thinking: 'x' }))).toBe('thought')
    expect(turnSummary(turn())).toContain('nothing recorded')
  })
})
