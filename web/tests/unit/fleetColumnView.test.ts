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
