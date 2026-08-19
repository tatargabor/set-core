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

  it('integration-merge-conflict retry classifies via retry_context (no merge_result delta)', () => {
    // Regression: consumer-d i18n-setup-and-migration attempt #1 was retried
    // because the integration merge conflicted with main. The verifier path
    // (verifier.py:4138) sets `retry_context = "Integration merge conflict..."`
    // between verify-failed and the next running, but never writes a
    // merge_result delta — so the heuristic-only classifier falls through to
    // 'unknown'. Reading retry_context lets us name the cause.
    const entries: JournalEntry[] = [
      entry('2026-05-08T08:23:14.859Z', 'current_step', 'planning', 1),
      entry('2026-05-08T08:23:16.032Z', 'status', 'running', 2, 'dispatched'),
      entry('2026-05-08T08:45:05.301Z', 'status', 'integrating', 3, 'running'),
      entry('2026-05-08T08:45:05.337Z', 'status', 'verify-failed', 4, 'integrating'),
      entry(
        '2026-05-08T08:45:05.338Z',
        'retry_context',
        'Integration merge conflict: main has diverged from your branch.\n\nRun `git merge origin/main`...',
        5,
      ),
      // engine clears retry_context shortly after — must NOT erase classification
      entry('2026-05-08T08:45:05.356Z', 'retry_context', null, 6, 'Integration merge conflict: ...'),
      entry('2026-05-08T08:45:05.358Z', 'current_step', 'fixing', 7, 'planning'),
      entry('2026-05-08T08:45:06.612Z', 'status', 'running', 8, 'verify-failed'),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(2)
    expect(g.attempts[0].outcome).toBe('retry')
    expect(g.attempts[0].retryReason).toBe('merge-conflict')
    expect(g.attempts[1].outcome).toBe('in-progress')
  })

  it('retry_context is scoped per attempt — does not leak into the next retry classification', () => {
    // After a merge-conflict retry closes, the next attempt's classification
    // must NOT inherit the prior retry_context. Here attempt #2 fails on a
    // gate (no new retry_context written) and must be classified 'gate-fail',
    // not 'merge-conflict'.
    const entries: JournalEntry[] = [
      entry('2026-05-08T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-05-08T10:01:00.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-05-08T10:01:30.000Z', 'status', 'verify-failed', 3, 'integrating'),
      entry('2026-05-08T10:01:31.000Z', 'retry_context', 'Integration merge conflict: main diverged', 4),
      entry('2026-05-08T10:01:32.000Z', 'retry_context', null, 5, 'Integration merge conflict: main diverged'),
      entry('2026-05-08T10:01:33.000Z', 'status', 'running', 6, 'verify-failed'),
      entry('2026-05-08T10:02:00.000Z', 'status', 'integrating', 7, 'running'),
      entry('2026-05-08T10:02:30.000Z', 'build_result', 'fail', 8),
      entry('2026-05-08T10:02:31.000Z', 'status', 'verify-failed', 9, 'integrating'),
      entry('2026-05-08T10:02:32.000Z', 'status', 'running', 10, 'verify-failed'),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(3)
    expect(g.attempts[0].retryReason).toBe('merge-conflict')
    expect(g.attempts[1].retryReason).toBe('gate-fail')
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

  it('post-reset cycle (failed → pending → running) opens a new attempt', () => {
    // Models the engine.reset_failed_changes path: an attempt reaches a
    // terminal `failed` status, then a fresh dispatch cycles through
    // pending → dispatched → running. The graph should NOT remain stuck on
    // the prior failed attempt — a new in-progress attempt must be opened
    // and the terminal flag must be re-armed.
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:00:30.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'pass', 3),
      entry('2026-04-12T10:02:00.000Z', 'e2e_result', 'fail', 4),
      entry('2026-04-12T10:02:30.000Z', 'status', 'failed', 5, 'integrating'),
      // ─── reset_failed unblocks the change ───
      entry('2026-04-12T10:10:00.000Z', 'status', 'pending', 6, 'failed'),
      entry('2026-04-12T10:10:01.000Z', 'status', 'running', 7, 'dispatched'),
      entry('2026-04-12T10:11:00.000Z', 'status', 'integrating', 8, 'running'),
      entry('2026-04-12T10:12:00.000Z', 'build_result', 'pass', 9),
      entry('2026-04-12T10:13:00.000Z', 'e2e_result', 'pass', 10),
      entry('2026-04-12T10:14:00.000Z', 'status', 'merged', 11, 'integrating'),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(2)
    expect(g.attempts[0].outcome).toBe('failed')
    expect(g.attempts[0].retryReason).toBe('reset-failed')
    expect(g.attempts[1].outcome).toBe('merged')
    expect(g.terminal).toBe('merged')
    const buildNodes = g.attempts.flatMap((a) => a.nodes).filter((n) => n.kind === 'build')
    expect(buildNodes).toHaveLength(2)
    const e2eNodes = g.attempts.flatMap((a) => a.nodes).filter((n) => n.kind === 'e2e')
    expect(e2eNodes).toHaveLength(2)
    expect(e2eNodes[0].result).toBe('fail')
    expect(e2eNodes[1].result).toBe('pass')
  })

  it('post-reset attempt that is still in progress sets terminal back to in-progress', () => {
    // Same as above but the new attempt has not finished yet — terminal
    // must NOT be 'failed' just because an earlier attempt failed.
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:00:30.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'pass', 3),
      entry('2026-04-12T10:02:00.000Z', 'status', 'failed', 4, 'integrating'),
      entry('2026-04-12T10:10:00.000Z', 'status', 'pending', 5, 'failed'),
      entry('2026-04-12T10:10:01.000Z', 'status', 'running', 6, 'dispatched'),
      entry('2026-04-12T10:11:00.000Z', 'status', 'integrating', 7, 'running'),
      entry('2026-04-12T10:12:00.000Z', 'build_result', 'pass', 8),
      // e2e still running, no terminal status yet
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(2)
    expect(g.attempts[0].outcome).toBe('failed')
    expect(g.attempts[0].retryReason).toBe('reset-failed')
    expect(g.attempts[1].outcome).toBe('in-progress')
    expect(g.terminal).toBe('in-progress')
  })

  it('synthesizes gate node from gate_*_ms when result is unchanged across attempts', () => {
    // Regression: craftbrew-run-20260502-1603 checkout-flow attempt #3 ran
    // e2e again and it failed again with the same `fail` result. The
    // journal records only deltas, so e2e_result emitted no entry — only
    // gate_e2e_ms (different duration) and e2e_output (different failure
    // list). Without ms-synthesis, attempt #3 had no gate-fail node and
    // was classified retry-unknown.
    const entries: JournalEntry[] = [
      // Attempt 1: e2e fails
      entry('2026-05-06T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-05-06T10:00:30.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-05-06T10:01:00.000Z', 'build_result', 'pass', 3),
      entry('2026-05-06T10:01:00.001Z', 'gate_build_ms', 17200, 4),
      entry('2026-05-06T10:02:00.000Z', 'e2e_result', 'fail', 5),
      entry('2026-05-06T10:02:00.001Z', 'gate_e2e_ms', 345143, 6),
      entry('2026-05-06T10:02:30.000Z', 'status', 'verify-failed', 7, 'integrating'),
      // Attempt 2: gates run again, e2e fails AGAIN (same value, no result delta)
      entry('2026-05-06T10:03:00.000Z', 'status', 'running', 8, 'verify-failed'),
      entry('2026-05-06T10:25:00.000Z', 'status', 'integrating', 9, 'running'),
      entry('2026-05-06T10:25:30.000Z', 'gate_build_ms', 18216, 10, 17200),
      entry('2026-05-06T10:27:00.000Z', 'gate_e2e_ms', 122357, 11, 345143),
      entry('2026-05-06T10:27:00.100Z', 'e2e_output', 'E2E: 1 NEW failure', 12, 'E2E: 17 NEW failures'),
      entry('2026-05-06T10:27:30.000Z', 'status', 'verify-failed', 13, 'integrating'),
      entry('2026-05-06T10:28:00.000Z', 'status', 'running', 14, 'verify-failed'),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(3)
    // Attempt 1: real e2e fail node
    expect(g.attempts[0].retryReason).toBe('gate-fail')
    // Attempt 2: synthesized build-pass + e2e-fail nodes from ms updates,
    // classification must be gate-fail (not unknown)
    const a2Kinds = g.attempts[1].nodes.map((n) => n.kind)
    expect(a2Kinds).toContain('build')
    expect(a2Kinds).toContain('e2e')
    const a2E2e = g.attempts[1].nodes.find((n) => n.kind === 'e2e')!
    expect(a2E2e.result).toBe('fail')
    expect(a2E2e.ms).toBe(122357)
    expect(a2E2e.output).toBe('E2E: 1 NEW failure')
    expect(g.attempts[1].retryReason).toBe('gate-fail')
  })

  it('renders all post-MVP gate kinds (lint, test_files, e2e_coverage, spec_verify, i18n_check)', () => {
    // Regression: craftbrew-run-20260415-0146 admin-products attempt #4 ran
    // build → test → e2e → lint → scope_check → test_files → e2e_coverage →
    // spec_verify → rules → review. The DAG view was hiding lint, test_files,
    // and spec_verify because GATE_KINDS was a pre-Tier1/Tier2 allow-list.
    // All of them must now be visible as gate nodes.
    const entries: JournalEntry[] = [
      entry('2026-04-12T10:00:00.000Z', 'status', 'running', 1, 'dispatched'),
      entry('2026-04-12T10:00:30.000Z', 'status', 'integrating', 2, 'running'),
      entry('2026-04-12T10:01:00.000Z', 'build_result', 'pass', 3),
      entry('2026-04-12T10:01:30.000Z', 'test_result', 'pass', 4),
      entry('2026-04-12T10:02:00.000Z', 'e2e_result', 'pass', 5),
      entry('2026-04-12T10:02:10.000Z', 'lint_result', 'pass', 6),
      entry('2026-04-12T10:02:20.000Z', 'scope_check_result', 'pass', 7),
      entry('2026-04-12T10:02:25.000Z', 'test_files_result', 'pass', 8),
      entry('2026-04-12T10:02:30.000Z', 'e2e_coverage_result', 'pass', 9),
      entry('2026-04-12T10:03:00.000Z', 'spec_verify_result', 'pass', 10),
      entry('2026-04-12T10:03:05.000Z', 'i18n_check_result', 'pass', 11),
      entry('2026-04-12T10:03:10.000Z', 'rules_result', 'pass', 12),
      entry('2026-04-12T10:04:00.000Z', 'review_result', 'pass', 13),
      entry('2026-04-12T10:05:00.000Z', 'status', 'merged', 14, 'integrating'),
    ]
    const g = journalToAttemptGraph(entries)
    expect(g.attempts).toHaveLength(1)
    const kinds = g.attempts[0].nodes.map((n) => n.kind)
    // All 11 gate kinds must appear (plus impl → 12 nodes total).
    expect(kinds).toContain('impl')
    expect(kinds).toContain('build')
    expect(kinds).toContain('test')
    expect(kinds).toContain('e2e')
    expect(kinds).toContain('lint')
    expect(kinds).toContain('scope_check')
    expect(kinds).toContain('test_files')
    expect(kinds).toContain('e2e_coverage')
    expect(kinds).toContain('spec_verify')
    expect(kinds).toContain('i18n_check')
    expect(kinds).toContain('rules')
    expect(kinds).toContain('review')
    // totalGateRuns counts non-impl nodes that have a result.
    expect(g.totalGateRuns).toBe(11)
  })
})
