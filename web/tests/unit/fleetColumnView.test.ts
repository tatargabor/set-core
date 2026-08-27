/**
 * The project column's two ways of looking, and what each one drops.
 *
 * The live mode is the sharpest compaction on this screen: it removes whole
 * projects. `ui-quality.md` puts one rule above the others for exactly this —
 * compacting must never hide a failure — so these tests are mostly about the
 * counts that keep the removal visible, and about the one property the mode
 * must not lose: a live project cannot be missing from it because of where the
 * reader filed it.
 */

import { describe, expect, it } from 'vitest'

import { buildColumnView, mergeByName } from '../../src/lib/fleetColumnView'
import type { FleetProject } from '../../src/lib/fleetTypes'

const proj = (name: string, agents: number): FleetProject => ({
  name, root: `/r/${name}`, sources: ['process'], archived: false,
  agents: Array.from({ length: agents }, (_, i) => ({ pid: i + 1 })) as never,
})

const map = (...ps: FleetProject[]) => new Map(ps.map(p => [p.name, p]))

const GROUPS = { mode: 'arrangement', query: '' } as const
const LIVE = { mode: 'live', query: '' } as const

describe('the live mode', () => {
  const byName = map(proj('alpha', 2), proj('beta', 0), proj('gamma', 1))
  const order = ['alpha', 'beta', 'gamma']

  it('keeps only projects holding a live session, in the reader’s own order', () => {
    const v = buildColumnView(order, byName, LIVE)
    expect(v.rows.map(r => r.name)).toEqual(['alpha', 'gamma'])
    expect(v.flat).toBe(true)
  })

  it('states what it dropped', () => {
    expect(buildColumnView(order, byName, LIVE).hiddenNoLive).toBe(1)
  })

  it('reaches a project wherever the arrangement filed it', () => {
    // `order` is the whole document — collapsed groups, the parked section, the
    // ungrouped tail. A live project sitting in a collapsed group is the reason
    // this mode exists, so it must arrive here like any other.
    const collapsedThenParked = ['gamma', 'alpha', 'beta']
    const v = buildColumnView(collapsedThenParked, byName, LIVE)
    expect(v.rows.map(r => r.name)).toEqual(['gamma', 'alpha'])
  })

  it('does not turn an arranged-but-missing name into a row', () => {
    // A name discovery did not return is not a project on this machine. Counting
    // it would make the live count a claim about something nobody measured.
    const v = buildColumnView([...order, 'ghost'], byName, LIVE)
    expect(v.rows.map(r => r.name)).not.toContain('ghost')
    expect(v.totalPresent).toBe(3)
  })

  it('reorders and moves nothing — it returns names, in the given order', () => {
    const v = buildColumnView(order, byName, LIVE)
    const back = buildColumnView(order, byName, GROUPS)
    expect(back.rows.map(r => r.name)).toEqual(order)
    // The live view is a subsequence of the arrangement, never a re-sort.
    expect(v.rows.map(r => r.name)).toEqual(
      back.rows.map(r => r.name).filter(n => v.rows.some(r => r.name === n)))
  })
})

describe('the groups mode', () => {
  const byName = map(proj('alpha', 2), proj('beta', 0))

  it('claims nothing is hidden while nothing is', () => {
    const v = buildColumnView(['alpha', 'beta'], byName, GROUPS)
    // The partner assertion to every hidden count: a screen that always reports
    // a number teaches the reader to stop reading it.
    expect(v.hiddenNoLive).toBe(0)
    expect(v.hiddenByFilter).toBe(0)
    expect(v.flat).toBe(false)
  })

  it('still counts the live projects, so the control can state that size', () => {
    expect(buildColumnView(['alpha', 'beta'], byName, GROUPS).totalLive).toBe(1)
  })
})

describe('the filter', () => {
  const byName = map(proj('set-core', 3), proj('SET-copilot', 0), proj('other-app', 1))
  const order = ['set-core', 'SET-copilot', 'other-app']

  it('matches case-insensitively and flattens the tree while it is typed', () => {
    const v = buildColumnView(order, byName, { mode: 'arrangement', query: 'set' })
    expect(v.rows.map(r => r.name)).toEqual(['set-core', 'SET-copilot'])
    // A group tree with most of its rows removed is no longer the arrangement.
    expect(v.flat).toBe(true)
    expect(v.hiddenByFilter).toBe(1)
  })

  it('combines with the live mode, keeping the two causes apart', () => {
    const v = buildColumnView(order, byName, { mode: 'live', query: 'set' })
    expect(v.rows.map(r => r.name)).toEqual(['set-core'])
    // One dropped for holding no session, one for the name. A merged number
    // could not tell the reader which control to undo.
    expect(v.hiddenNoLive).toBe(1)
    expect(v.hiddenByFilter).toBe(1)
  })

  it('a whitespace-only query hides nothing and keeps the tree', () => {
    const v = buildColumnView(order, byName, { mode: 'arrangement', query: '  ' })
    expect(v.rows).toHaveLength(3)
    expect(v.flat).toBe(false)
  })
})

describe('one project named twice by discovery', () => {
  // MEASURED on the live screen, 2026-08-24: the fleet returned one project as
  // two entries — the checkout with five agents, and a worktree of it with
  // none. Keyed assignment let the empty entry win, and the column read
  // `live 5` while the screen's own header counted agents in 6 projects. The
  // fail direction is the one that matters: running work rendered as idle.
  const twice = [proj('dup', 5), { ...proj('dup', 0), root: '/r/dup-wt' }, proj('solo', 1)]

  it('merges the agents instead of letting the last entry win', () => {
    const m = mergeByName(twice)
    expect(m.size).toBe(2)
    expect(m.get('dup')!.agents).toHaveLength(5)
  })

  it('keeps the first entry’s own fields', () => {
    // The agents are the only field a second entry ADDS to; everything else it
    // merely restates, and the registry entry is the one that carries them.
    expect(mergeByName(twice).get('dup')!.root).toBe('/r/dup')
  })

  it('and the project is then live', () => {
    const v = buildColumnView(['dup', 'solo'], mergeByName(twice), LIVE)
    expect(v.rows.map(r => r.name)).toEqual(['dup', 'solo'])
  })
})

describe('the freshest-first order', () => {
  /** A project whose agents last moved these many seconds ago. */
  const moving = (name: string, ...secs: (number | null)[]): FleetProject => ({
    name, root: `/r/${name}`, sources: ['process'], archived: false,
    agents: secs.map((s, i) => ({ pid: i + 1, last_movement_seconds: s })) as never,
  })

  const RECENT = { mode: 'live', query: '', sort: 'recent' } as const

  it('puts the project whose agent moved most recently on top', () => {
    // The reader's own order is deliberately the reverse of the answer, so a
    // pass cannot come from the input already being sorted.
    const byName = map(moving('slow', 3600), moving('mid', 600), moving('fresh', 5))
    const v = buildColumnView(['slow', 'mid', 'fresh'], byName, RECENT)
    expect(v.rows.map(r => r.name)).toEqual(['fresh', 'mid', 'slow'])
    expect(v.sorted).toBe(true)
  })

  it('ranks a project by its FRESHEST agent, not the one the row displays', () => {
    // `busy` shows `⏱ 3600` on the row — the stalest agent — while one of its
    // agents moved five seconds ago. Sorting on what the row happens to display
    // would file the project the reader is working in at the bottom.
    const byName = map(moving('busy', 5, 3600), moving('quiet', 600))
    const v = buildColumnView(['quiet', 'busy'], byName, RECENT)
    expect(v.rows.map(r => r.name)).toEqual(['busy', 'quiet'])
  })

  it('puts projects with no measured movement at the END, and counts them', () => {
    // Not "oldest" — nobody looked. An unmeasured row sorted among the measured
    // ones would state a time that was never taken.
    const byName = map(moving('unknown', null), moving('old', 7200), moving('fresh', 3))
    const v = buildColumnView(['unknown', 'old', 'fresh'], byName, RECENT)
    expect(v.rows.map(r => r.name)).toEqual(['fresh', 'old', 'unknown'])
    expect(v.unmeasured).toBe(1)
  })

  it('keeps the reader’s order among projects that moved at the same moment', () => {
    // A poll runs every few seconds; an unstable tie would make rows swap under
    // the pointer for no reason the reader can see.
    const byName = map(moving('c', 60), moving('a', 60), moving('b', 60))
    const v = buildColumnView(['c', 'a', 'b'], byName, RECENT)
    expect(v.rows.map(r => r.name)).toEqual(['c', 'a', 'b'])
  })

  it('ranks by the number the row DISPLAYS, so the order reads off the screen', () => {
    // Measured on the running dashboard while a first attempt bucketed by whole
    // minutes: four projects all inside one minute, and `3s` rendered BELOW
    // `32s`. Defensible, unreadable — which on a screen is the same as wrong.
    const byName = map(moving('shows-32s', 32), moving('shows-3s', 3))
    expect(buildColumnView(['shows-32s', 'shows-3s'], byName, RECENT).rows.map(r => r.name))
      .toEqual(['shows-3s', 'shows-32s'])
  })

  it('does not swap two rows showing the SAME age', () => {
    // Both render `1s`; the raw seconds differ in the third decimal, and the
    // fleet polls every couple of seconds. Sorting on the raw value swaps the
    // top of the list under the pointer beneath two identical numbers.
    const byName = map(moving('a', 1.002), moving('b', 1.001))
    expect(buildColumnView(['a', 'b'], byName, RECENT).rows.map(r => r.name))
      .toEqual(['a', 'b'])
    // Same at the minute resolution, where `age` rounds 130s and 140s alike.
    const mins = map(moving('x', 130), moving('y', 125))
    expect(buildColumnView(['x', 'y'], mins, RECENT).rows.map(r => r.name))
      .toEqual(['x', 'y'])
  })

  it('does not floor an unmeasured project into the freshest minute', () => {
    // `null` and 0 both reach the comparator as falsy-looking values, and a
    // project nobody measured landing at the very top is the false-value
    // direction: it would claim the strongest fact on the screen.
    const byName = map(moving('nothing', null), moving('now', 2))
    const v = buildColumnView(['nothing', 'now'], byName, RECENT)
    expect(v.rows.map(r => r.name)).toEqual(['now', 'nothing'])
  })

  it('is IGNORED while the group tree renders — that order is the arrangement', () => {
    // Re-sorting the tree would either shuffle rows inside groups or flatten
    // what the reader built by hand. `sorted` says so, so the control can too.
    const byName = map(moving('slow', 3600), moving('fresh', 5))
    const v = buildColumnView(['slow', 'fresh'], byName, { mode: 'arrangement', query: '', sort: 'recent' })
    expect(v.rows.map(r => r.name)).toEqual(['slow', 'fresh'])
    expect(v.sorted).toBe(false)
    expect(v.flat).toBe(false)
  })

  it('applies to a filtered list, which is already flat', () => {
    const byName = map(moving('set-slow', 3600), moving('other', 1), moving('set-fresh', 5))
    const v = buildColumnView(['set-slow', 'other', 'set-fresh'], byName,
      { mode: 'arrangement', query: 'set', sort: 'recent' })
    expect(v.rows.map(r => r.name)).toEqual(['set-fresh', 'set-slow'])
    expect(v.sorted).toBe(true)
  })

  it('changes nothing without being asked — the default is the reader’s order', () => {
    // The partner assertion: every test above would also pass if the sort ran
    // unconditionally, and this is the one that says it does not.
    const byName = map(moving('slow', 3600), moving('fresh', 5))
    const v = buildColumnView(['slow', 'fresh'], byName, LIVE)
    expect(v.rows.map(r => r.name)).toEqual(['slow', 'fresh'])
    expect(v.sorted).toBe(false)
    expect(buildColumnView(['slow', 'fresh'], byName, GROUPS).sorted).toBe(false)
  })

  it('hides nothing — the same rows, in a different order', () => {
    // A sort that dropped a row would be the compaction rule's own failure,
    // arriving through a control that never claimed to compact.
    const byName = map(moving('a', 1), moving('b', null), moving('c', 99))
    const order = ['a', 'b', 'c']
    const plain = buildColumnView(order, byName, LIVE).rows.map(r => r.name)
    const sorted = buildColumnView(order, byName, RECENT).rows.map(r => r.name)
    expect([...sorted].sort()).toEqual([...plain].sort())
  })
})
