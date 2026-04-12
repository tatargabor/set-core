import { describe, expect, it } from 'vitest'
import { journalToAttemptGraph } from '../../src/lib/dag/journalToAttemptGraph'
import type { JournalEntry } from '../../src/lib/api'

function entry(
  ts: string,
  field: string,
  newVal: unknown,
  seq = 0,
  oldVal: unknown = null,
): JournalEntry {
  return { ts, field, new: newVal, old: oldVal, seq }
}

describe('journalToAttemptGraph', () => {
  it('returns empty graph for empty entries', () => {
    const g = journalToAttemptGraph([])
    expect(g.attempts).toEqual([])
    expect(g.terminal).toBe('in-progress')
    expect(g.totalGateRuns).toBe(0)
    expect(g.totalMs).toBe(0)
  })

  it('single-attempt happy path ending in merged', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:00:30.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'pass', 3),
      entry('2026-04-12T10:01:00.001Z', 'gate_build_ms', 4200, 4),
      entry('2026-04-12T10:02:00.000Z', 'test_result', 'pass', 5),
      entry('2026-04-12T10:02:00.001Z', 'gate_test_ms', 8100, 6),
      entry('2026-04-12T10:03:00.000Z', 'e2e_result', 'pass', 7),
      entry('2026-04-12T10:03:00.001Z', 'gate_e2e_ms', 120000, 8),
      entry('2026-04-12T10:04:00.000Z', 'status', 'merged', 9, 'integrating'),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(1)
    expect(g.terminal).toBe('merged')
    const attempt = g.attempts[0]
    expect(attempt.outcome).toBe('merged')
    // impl + build + test + e2e = 4 nodes
    expect(attempt.nodes).toHaveLength(4)
    expect(attempt.nodes[0].kind).toBe('impl')
    expect(attempt.nodes[1].kind).toBe('build')
    expect(attempt.nodes[1].ms).toBe(4200)
    expect(attempt.nodes[2].kind).toBe('test')
    expect(attempt.nodes[3].kind).toBe('e2e')
    expect(g.totalGateRuns).toBe(3)
  })

  it('two-attempt with test-fail retry', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:00:30.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'pass', 3),
      entry('2026-04-12T10:02:00.000Z', 'test_result', 'fail', 4),
      entry('2026-04-12T10:02:30.000Z', 'status', 'verify-failed', 5, 'integrating'),
      entry('2026-04-12T10:02:31.000Z', 'status', 'running', 6, 'verify-failed'),
      entry('2026-04-12T10:03:00.000Z', 'status', 'integrating', 7, 'running'),
      entry('2026-04-12T10:04:00.000Z', 'build_result', 'pass', 8),
      entry('2026-04-12T10:05:00.000Z', 'test_result', 'pass', 9),
      entry('2026-04-12T10:06:00.000Z', 'status', 'merged', 10, 'integrating'),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(2)
    expect(g.attempts[0].outcome).toBe('retry')
    expect(g.attempts[0].retryReason).toBe('gate-fail')
    expect(g.attempts[1].outcome).toBe('merged')
    const buildNodes = g.attempts.flatMap((a) => a.nodes).filter((n) => n.kind === 'build')
    expect(buildNodes).toHaveLength(2)
    expect(buildNodes[0].runIndexForKind).toBe(1)
    expect(buildNodes[1].runIndexForKind).toBe(2)
  })

  it('three-attempt with mixed gate fails', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:00:30.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'fail', 3),
      entry('2026-04-12T10:01:30.000Z', 'status', 'verify-failed', 4, 'integrating'),
      entry('2026-04-12T10:01:31.000Z', 'status', 'running', 5, 'verify-failed'),
      entry('2026-04-12T10:02:30.000Z', 'status', 'integrating', 6, 'running'),
      entry('2026-04-12T10:03:00.000Z', 'build_result', 'pass', 7),
      entry('2026-04-12T10:04:00.000Z', 'test_result', 'fail', 8),
      entry('2026-04-12T10:04:30.000Z', 'status', 'verify-failed', 9, 'integrating'),
      entry('2026-04-12T10:04:31.000Z', 'status', 'running', 10, 'verify-failed'),
      entry('2026-04-12T10:05:30.000Z', 'status', 'integrating', 11, 'running'),
      entry('2026-04-12T10:06:00.000Z', 'build_result', 'pass', 12),
      entry('2026-04-12T10:07:00.000Z', 'test_result', 'pass', 13),
      entry('2026-04-12T10:08:00.000Z', 'status', 'merged', 14, 'integrating'),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(3)
    expect(g.attempts[0].retryReason).toBe('gate-fail')
    expect(g.attempts[1].retryReason).toBe('gate-fail')
    expect(g.attempts[2].outcome).toBe('merged')
    expect(g.terminal).toBe('merged')
  })

  it('merge-conflict retry sets retryReason to merge-conflict', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:00:30.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'pass', 3),
      entry('2026-04-12T10:02:00.000Z', 'test_result', 'pass', 4),
      entry('2026-04-12T10:03:00.000Z', 'merge_result', 'fail', 5),
      entry('2026-04-12T10:03:30.000Z', 'status', 'verify-failed', 6, 'integrating'),
      entry('2026-04-12T10:03:31.000Z', 'status', 'running', 7, 'verify-failed'),
      entry('2026-04-12T10:04:30.000Z', 'status', 'integrating', 8, 'running'),
      entry('2026-04-12T10:05:00.000Z', 'build_result', 'pass', 9),
      entry('2026-04-12T10:06:00.000Z', 'test_result', 'pass', 10),
      entry('2026-04-12T10:07:00.000Z', 'merge_result', 'pass', 11),
      entry('2026-04-12T10:08:00.000Z', 'status', 'merged', 12, 'integrating'),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(2)
    expect(g.attempts[0].retryReason).toBe('merge-conflict')
    expect(g.terminal).toBe('merged')
  })

  it('interrupted attempt leaves terminal in-progress', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:00:30.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'pass', 3),
      entry('2026-04-12T10:02:00.000Z', 'test_result', 'pass', 4),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(1)
    expect(g.attempts[0].outcome).toBe('in-progress')
    expect(g.terminal).toBe('in-progress')
  })

  it('verify-failed without subsequent running stays as in-progress attempt', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:00:30.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-04-12T10:01:00.000Z', 'e2e_result', 'fail', 3),
      entry('2026-04-12T10:01:30.000Z', 'status', 'verify-failed', 4, 'integrating'),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(1)
    // The attempt is pending retry but not yet closed — DAG still shows it live
    expect(g.terminal).toBe('in-progress')
  })

  it('skipped gate is not added as a node', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:00:30.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'pass', 3),
      entry('2026-04-12T10:02:00.000Z', 'e2e_result', 'skip', 4),
      entry('2026-04-12T10:03:00.000Z', 'test_result', 'pass', 5),
      entry('2026-04-12T10:04:00.000Z', 'status', 'merged', 6, 'integrating'),
    ]
    const g = journalToAttemptGraph(entries)
    const kinds = g.attempts[0].nodes.map((n) => n.kind)
    expect(kinds).not.toContain('e2e')
    expect(kinds).toContain('build')
    expect(kinds).toContain('test')
    expect(g.totalGateRuns).toBe(2)
  })

  it('out-of-order seqs with same ts are stable-sorted by seq', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'test_result', 'pass', 4),
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1),
      entry('2026-04-12T10:00:00.000Z', 'status', 'integrating', 2),
      entry('2026-04-12T10:00:00.000Z', 'build_result', 'pass', 3),
      entry('2026-04-12T10:00:00.000Z', 'status', 'merged', 5),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(1)
    const gateKinds = g.attempts[0].nodes
      .filter((n) => n.kind !== 'impl')
      .map((n) => n.kind)
    expect(gateKinds).toEqual(['build', 'test'])
  })

  it('impl duration equals time between running and first gate', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:00:30.000Z', 'build_result', 'pass', 2),
      entry('2026-04-12T10:00:40.000Z', 'status', 'merged', 3, 'integrating'),
    ]
    const g = journalToAttemptGraph(entries)
    const impl = g.attempts[0].nodes[0]
    expect(impl.kind).toBe('impl')
    expect(impl.ms).toBe(30000)
  })

  it('runIndexForKind counts across attempts', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:01:00.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-04-12T10:01:30.000Z', 'build_result', 'pass', 3),
      entry('2026-04-12T10:02:00.000Z', 'test_result', 'fail', 4),
      entry('2026-04-12T10:02:30.000Z', 'status', 'verify-failed', 5, 'integrating'),
      entry('2026-04-12T10:02:31.000Z', 'status', 'running', 6, 'verify-failed'),
      entry('2026-04-12T10:03:00.000Z', 'status', 'integrating', 7, 'running'),
      entry('2026-04-12T10:03:30.000Z', 'build_result', 'pass', 8),
      entry('2026-04-12T10:04:00.000Z', 'test_result', 'fail', 9),
      entry('2026-04-12T10:04:30.000Z', 'status', 'verify-failed', 10, 'integrating'),
      entry('2026-04-12T10:04:31.000Z', 'status', 'running', 11, 'verify-failed'),
      entry('2026-04-12T10:05:00.000Z', 'status', 'integrating', 12, 'running'),
      entry('2026-04-12T10:05:30.000Z', 'build_result', 'pass', 13),
      entry('2026-04-12T10:06:00.000Z', 'test_result', 'pass', 14),
      entry('2026-04-12T10:07:00.000Z', 'status', 'merged', 15, 'integrating'),
    ]
    const g = journalToAttemptGraph(entries)
    const builds = g.attempts.flatMap((a) => a.nodes).filter((n) => n.kind === 'build')
    const tests = g.attempts.flatMap((a) => a.nodes).filter((n) => n.kind === 'test')
    expect(builds.map((n) => n.runIndexForKind)).toEqual([1, 2, 3])
    expect(tests.map((n) => n.runIndexForKind)).toEqual([1, 2, 3])
  })

  it('attaches output and ms to the matching gate result within 2s window', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'fail', 2),
      entry('2026-04-12T10:01:00.100Z', 'build_output', 'error: missing semicolon', 3),
      entry('2026-04-12T10:01:00.200Z', 'gate_build_ms', 3300, 4),
    ]
    const g = journalToAttemptGraph(entries)
    const build = g.attempts[0].nodes.find((n) => n.kind === 'build')!
    expect(build.output).toBe('error: missing semicolon')
    expect(build.ms).toBe(3300)
  })

  it('failed status sets terminal to failed', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'fail', 2),
      entry('2026-04-12T10:02:00.000Z', 'status', 'failed', 3, 'running'),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.terminal).toBe('failed')
    expect(g.attempts[0].outcome).toBe('failed')
  })

  it('transform is pure — same input produces deep-equal outputs', () => {
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'pass', 2),
      entry('2026-04-12T10:02:00.000Z', 'status', 'merged', 3),
    ]
    const a = journalToAttemptGraph(entries)
    const b = journalToAttemptGraph(entries)
    expect(a).toEqual(b)
  })

  it('real nano-run-style journal produces 2 attempts, in-progress terminal', () => {
    // This mirrors the nano-run-20260412-1941 infra journal: 1 retry where e2e
    // failed, then gates all pass but the run is still integrating.
    const entries: JournalEntry[] = [
      entry('2026-04-12T17:45:04.859Z', 'current_step', 'planning', 1),
      entry('2026-04-12T17:45:06.013Z', 'status', 'running', 2, 'dispatched'),
      entry('2026-04-12T17:53:29.058Z', 'status', 'integrating', 3, 'running'),
      entry('2026-04-12T17:53:38.293Z', 'build_result', 'pass', 4),
      entry('2026-04-12T17:53:38.790Z', 'test_result', 'pass', 6),
      entry('2026-04-12T17:53:53.333Z', 'e2e_result', 'fail', 9),
      entry('2026-04-12T17:53:53.335Z', 'status', 'verify-failed', 12, 'integrating'),
      entry('2026-04-12T17:53:53.340Z', 'current_step', 'fixing', 15),
      entry('2026-04-12T17:53:54.570Z', 'status', 'running', 16, 'verify-failed'),
      entry('2026-04-12T17:55:57.368Z', 'status', 'integrating', 17, 'running'),
      entry('2026-04-12T17:56:19.000Z', 'e2e_result', 'pass', 20, 'fail'),
      entry('2026-04-12T17:56:19.100Z', 'scope_check_result', 'pass', 23),
      entry('2026-04-12T17:56:19.200Z', 'e2e_coverage_result', 'warn', 26),
      entry('2026-04-12T17:57:57.000Z', 'rules_result', 'pass', 29),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(2)
    expect(g.attempts[0].outcome).toBe('retry')
    expect(g.attempts[0].retryReason).toBe('gate-fail')
    expect(g.attempts[1].outcome).toBe('in-progress')
    expect(g.terminal).toBe('in-progress')
    // attempt 1 has impl + build + test + e2e = 4 nodes
    expect(g.attempts[0].nodes).toHaveLength(4)
    // attempt 2 has impl + e2e + scope_check + e2e_coverage + rules = 5 nodes
    expect(g.attempts[1].nodes).toHaveLength(5)
    // e2e runs twice across attempts
    const e2eNodes = g.attempts.flatMap((a) => a.nodes).filter((n) => n.kind === 'e2e')
    expect(e2eNodes).toHaveLength(2)
    expect(e2eNodes[0].result).toBe('fail')
    expect(e2eNodes[1].result).toBe('pass')
  })
})
