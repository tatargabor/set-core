/**
 * The fleet's wave-board chip — the order of the list, what the closed chip
 * counts, and the progress-bar arithmetic.
 */
import { describe, expect, it } from 'vitest'
import {
  barSegments, itemTotal, orderBoards, parseBoards, secondsSince, totals,
  type ReadableBoard, type UnreadableBoard, type WaveBoard,
} from '../../src/lib/fleetWaves'

function board(project: string, job: string, counts: Partial<ReadableBoard['counts']> = {}): ReadableBoard {
  return {
    project, job, title: `Board ${job}`, artifact_url: null,
    counts: { todo: 0, doing: 0, done: 0, blocked: 0, skipped: 0, ...counts },
    other: 0, waves: 1, current_wave: null, updated: null, unreadable: false,
  }
}

const broken = (project: string, job: string): UnreadableBoard =>
  ({ project, job, unreadable: true, reason: 'not valid JSON (line 1)' })

describe('orderBoards', () => {
  it('lists the selected project first, then the rest by name (AC-10)', () => {
    const boards: WaveBoard[] = [board('a', 'x'), board('c', 'x'), board('b', 'y'), board('b', 'x')]
    expect(orderBoards(boards, 'b').map(b => `${b.project}/${b.job}`))
      .toEqual(['b/x', 'b/y', 'a/x', 'c/x'])
  })

  it('sorts by name alone when nothing is selected', () => {
    expect(orderBoards([board('b', 'x'), board('a', 'x')], null).map(b => b.project)).toEqual(['a', 'b'])
  })

  it('does not reorder the array it was given', () => {
    const input = [board('b', 'x'), board('a', 'x')]
    orderBoards(input, null)
    expect(input.map(b => b.project)).toEqual(['b', 'a'])
  })
})

describe('totals', () => {
  it('adds up blocked items across boards (AC-5)', () => {
    expect(totals([board('a', 'x', { blocked: 3 }), board('b', 'y', { blocked: 11 })]))
      .toEqual({ boards: 2, blocked: 14, unreadable: 0, stale: 0 })
  })

  it('counts an unreadable board instead of folding it into zero', () => {
    expect(totals([board('a', 'x', { blocked: 1 }), broken('b', 'y')]))
      .toEqual({ boards: 2, blocked: 1, unreadable: 1, stale: 0 })
  })

  it('is all zeros for no boards (AC-6: the chip renders nothing)', () => {
    expect(totals([])).toEqual({ boards: 0, blocked: 0, unreadable: 0, stale: 0 })
  })

  it('counts stale boards, and only those the server called stale (AC-16)', () => {
    const stale = { ...board('a', 'x'), manual_open: 2, commits_since_change: 40, stale: true }
    const current = { ...board('b', 'y'), manual_open: 2, commits_since_change: 1, stale: false }
    const unmeasured = { ...board('c', 'z'), manual_open: 2, commits_since_change: null, stale: false }
    expect(totals([stale, current, unmeasured, { ...stale, job: 'w' }]).stale).toBe(2)
  })

  it('reads a board from an older server, without the fields, as not stale', () => {
    expect(totals([board('a', 'x')]).stale).toBe(0)
  })
})

describe('barSegments', () => {
  it('splits the bar by status in a fixed order, leaving empty statuses out', () => {
    const segs = barSegments(board('a', 'x', { todo: 1, done: 2, blocked: 1 }))
    expect(segs.map(s => s.status)).toEqual(['done', 'blocked', 'todo'])
    expect(segs.map(s => s.percent)).toEqual([50, 25, 25])
  })

  it('carries items in an unknown status as their own segment', () => {
    const b = { ...board('a', 'x', { done: 1 }), other: 1 }
    expect(barSegments(b).map(s => s.status)).toEqual(['done', 'other'])
    expect(itemTotal(b)).toBe(2)
  })

  it('is empty for an empty board rather than dividing by zero', () => {
    expect(barSegments(board('a', 'x'))).toEqual([])
  })
})

describe('secondsSince', () => {
  it('measures from an ISO time, and is null for none or garbage', () => {
    const now = Date.parse('2026-10-11T12:00:00Z')
    expect(secondsSince('2026-10-11T11:59:00Z', now)).toBe(60)
    expect(secondsSince(null, now)).toBeNull()
    expect(secondsSince('yesterday-ish', now)).toBeNull()
  })
})

describe('parseBoards', () => {
  it('drops what it cannot render instead of crashing the header', () => {
    expect(parseBoards({ agents: [] })).toEqual([])
    expect(parseBoards({ boards: [{ project: 'a' }, null, board('b', 'x'), { project: 'c', job: 'j', unreadable: true, reason: 'r' }] })
      .map(b => b.project)).toEqual(['b', 'c'])
  })

  it('keeps an old-shape board, without the staleness fields', () => {
    const old = board('a', 'x')
    expect(parseBoards({ boards: [old] })).toEqual([old])
  })
})
