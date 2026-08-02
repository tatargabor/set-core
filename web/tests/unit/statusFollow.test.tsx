/**
 * The surface half: a control appears because the project DECLARED the field, never because of
 * what the field is called, and the panel reads lines without knowing a single key.
 *
 * The two tests that matter most are the negative ones. A renderer that offers to follow
 * anything path-shaped would pass every positive test here and would have quietly moved one
 * project's vocabulary into the framework.
 */

import { describe, expect, it } from 'vitest'
import { presentFollowTargets } from '../../src/components/statusShape'

describe('presentFollowTargets', () => {
  it('finds a declared field at the top level', () => {
    expect(presentFollowTargets({ log: 'a.jsonl' }, ['log'])).toEqual(new Map([['log', 'a.jsonl']]))
  })

  it('finds a declared field at any depth, the way caveats are matched', () => {
    const data = { running: { inner: { trace: 'deep/x.log' } } }
    expect(presentFollowTargets(data, ['trace'])).toEqual(new Map([['trace', 'deep/x.log']]))
  })

  it('walks into arrays, because a producer may carry several runs', () => {
    const data = { runs: [{ other: 1 }, { log: 'second.jsonl' }] }
    expect(presentFollowTargets(data, ['log'])).toEqual(new Map([['log', 'second.jsonl']]))
  })

  it('offers NOTHING for a field named log that was not declared', () => {
    // The load-bearing test. Make the renderer recognise the name and this is what fails.
    expect(presentFollowTargets({ log: 'a.jsonl' }, [])).toEqual(new Map())
    expect(presentFollowTargets({ logFile: 'a.jsonl', trace: 'b.log' }, [])).toEqual(new Map())
  })

  it('offers nothing for a declared field the data does not carry', () => {
    // The declaration says what to look for; the data says what is there. A control here would
    // be a button whose only possible outcome is the endpoint refusing it.
    expect(presentFollowTargets({ running: null }, ['log'])).toEqual(new Map())
  })

  it('treats null, empty and whitespace as nothing to follow rather than as a failure', () => {
    expect(presentFollowTargets({ log: null }, ['log'])).toEqual(new Map())
    expect(presentFollowTargets({ log: '' }, ['log'])).toEqual(new Map())
    expect(presentFollowTargets({ log: '   ' }, ['log'])).toEqual(new Map())
  })

  it('ignores a declared field holding a structure — a path is a string', () => {
    expect(presentFollowTargets({ log: { path: 'a.jsonl' } }, ['log'])).toEqual(new Map())
  })

  it('a dotted declaration matches nothing, and that is the documented selector', () => {
    // Kept as a test rather than a comment: this is the shape a producer reaches for first, and
    // the failure is silent — no control, no error, and the declaration looks correct.
    expect(presentFollowTargets({ running: { log: 'a.jsonl' } }, ['running.log'])).toEqual(new Map())
  })

  it('keeps the first occurrence when a name repeats', () => {
    const data = { a: { log: 'first.jsonl' }, b: { log: 'second.jsonl' } }
    expect(presentFollowTargets(data, ['log'])).toEqual(new Map([['log', 'first.jsonl']]))
  })

  it('an undeclared answer is the behaviour every project has today', () => {
    expect(presentFollowTargets({ running: { log: 'a.jsonl' } }, [])).toEqual(new Map())
  })
})

describe('the follow stream URL', () => {
  it('encodes the path exactly once, including a space', async () => {
    const { followStreamURL } = await import('../../src/lib/api')
    const url = followStreamURL('proj', 'current', 'logs/a run.jsonl')

    // Encoded — but the decoded round trip must give back exactly what the project sent, which
    // is what a double-encode breaks and what only shows up on the one producer with a space.
    const qs = new URLSearchParams(url.split('?')[1])
    expect(qs.get('path')).toBe('logs/a run.jsonl')
    expect(qs.get('command')).toBe('current')
  })
})
