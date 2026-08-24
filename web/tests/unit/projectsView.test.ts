/**
 * What the projects screen shows — and, load-bearing, what it says it is NOT
 * showing.
 *
 * The defect these tests exist against is not a crash. It is a screen that
 * narrowed itself and looked complete: a live view listing three rows while
 * thirty-six projects sit off screen, or a column of calm zeros produced by a
 * fleet that never answered. Both are more convincing than the screen they
 * replaced, which is what makes them worse than it.
 *
 * So the assertions come in pairs. Every "it hid N" has a partner asserting the
 * screen makes NO hidden claim when nothing was hidden — the false-absence
 * direction is the one that goes unnoticed.
 */

import { describe, expect, it } from 'vitest'

import { buildProjectsView } from '../../src/lib/projectsView'
import type { ProjectInfo } from '../../src/lib/api'
import type { FleetResponse } from '../../src/lib/fleetTypes'

const project = (name: string, over: Partial<ProjectInfo> = {}): ProjectInfo => ({
  name, path: `/r/${name}`, status: 'stopped', ...over,
})

const fleet = (counts: Record<string, number>): FleetResponse => ({
  agents: Object.values(counts).reduce((a, b) => a + b, 0),
  working: 0, unknown: 0, unbucketed: 0,
  projects: Object.entries(counts).map(([name, n]) => ({
    name, root: `/r/${name}`, sources: ['process'], archived: false,
    agents: Array.from({ length: n }, (_, i) => ({ pid: i + 1, name: `${name}-${i}` })) as never,
  })),
} as FleetResponse)

const NONE = { mode: 'all', query: '' } as const

describe('the view narrows, and says by how much', () => {
  const projects = [project('alpha'), project('beta'), project('gamma')]
  const measured = fleet({ alpha: 2, beta: 0, gamma: 0 })

  it('the all view lists every project and claims nothing is hidden', () => {
    const v = buildProjectsView(projects, measured, NONE)
    expect(v.rows.map(r => r.name)).toEqual(['alpha', 'beta', 'gamma'])
    // The partner assertion. A screen that always reports "0 hidden" is one
    // whose hidden count nobody reads.
    expect(v.hiddenByView).toBe(0)
    expect(v.hiddenByFilter).toBe(0)
  })

  it('the live view keeps only projects with a measured session, and counts the rest', () => {
    const v = buildProjectsView(projects, measured, { mode: 'live', query: '' })
    expect(v.rows.map(r => r.name)).toEqual(['alpha'])
    expect(v.hiddenByView).toBe(2)
    expect(v.hiddenByFilter).toBe(0)
  })

  it('both view sizes are counted without switching view', () => {
    const v = buildProjectsView(projects, measured, NONE)
    expect(v.totalAll).toBe(3)
    expect(v.totalLive).toBe(1)
  })

  it('liveness comes from the fleet, never from the project status', () => {
    // `beta` claims to be running and has no session; `alpha` claims stopped
    // and has two. The status column has been measured lying in exactly this
    // direction, so the live view must follow the fleet.
    const claims = [project('alpha', { status: 'stopped' }), project('beta', { status: 'running' })]
    const v = buildProjectsView(claims, fleet({ alpha: 2, beta: 0 }), { mode: 'live', query: '' })
    expect(v.rows.map(r => r.name)).toEqual(['alpha'])
  })
})

describe('the name filter', () => {
  const projects = [project('set-core'), project('SET-copilot'), project('other-app')]
  const measured = fleet({ 'set-core': 1, 'SET-copilot': 0, 'other-app': 3 })

  it('matches as a case-insensitive substring and counts what it dropped', () => {
    const v = buildProjectsView(projects, measured, { mode: 'all', query: 'set' })
    expect(v.rows.map(r => r.name)).toEqual(['set-core', 'SET-copilot'])
    expect(v.hiddenByFilter).toBe(1)
    expect(v.hiddenByView).toBe(0)
  })

  it('applies inside the live view too, with the two hidden counts kept apart', () => {
    const v = buildProjectsView(projects, measured, { mode: 'live', query: 'other' })
    expect(v.rows.map(r => r.name)).toEqual(['other-app'])
    // One project has no session (the view's doing); one has a session but the
    // wrong name (the filter's). A single merged number could not tell the
    // reader which control to undo.
    expect(v.hiddenByView).toBe(1)
    expect(v.hiddenByFilter).toBe(1)
  })

  it('an empty query hides nothing', () => {
    const v = buildProjectsView(projects, measured, { mode: 'all', query: '   ' })
    expect(v.rows).toHaveLength(3)
    expect(v.hiddenByFilter).toBe(0)
  })
})

describe('a measured zero and an unmeasured count are different values', () => {
  const projects = [project('alpha'), project('beta')]

  it('a present answer gives every row a number, and never null', () => {
    const v = buildProjectsView(projects, fleet({ alpha: 0, beta: 0 }), NONE)
    expect(v.rows.map(r => r.liveSessions)).toEqual([0, 0])
    expect(v.liveMeasured).toBe(true)
  })

  it('a project the fleet did not mention at all is still a measured zero', () => {
    // The fleet answered; it simply holds no entry for `beta`. That is an
    // answer about `beta`, not a gap.
    const v = buildProjectsView(projects, fleet({ alpha: 1 }), NONE)
    expect(v.rows.find(r => r.name === 'beta')!.liveSessions).toBe(0)
  })

  it('no answer gives every row null, and the listing survives', () => {
    const v = buildProjectsView(projects, null, NONE)
    expect(v.rows.map(r => r.liveSessions)).toEqual([null, null])
    expect(v.liveMeasured).toBe(false)
    // The point of the whole distinction: the All view still works.
    expect(v.rows.map(r => r.name)).toEqual(['alpha', 'beta'])
  })

  it('no answer invents no live projects', () => {
    const v = buildProjectsView(projects, null, { mode: 'live', query: '' })
    expect(v.rows).toEqual([])
    expect(v.liveMeasured).toBe(false)
    // And the caller must not read this 0 as "measured: nothing is live" — the
    // flag above is what it is for.
    expect(v.totalLive).toBe(0)
  })
})

describe('the fleet may name one project twice', () => {
  // MEASURED on the running dashboard, 2026-08-24, and it is why this file has
  // a test for a shape rather than for a number: `/api/fleet/agents` returned
  // one project twice — the checkout with five agents, and a worktree of it with
  // none. Keyed by name with `set`, the empty entry won, and a project with
  // five live sessions vanished from the live view. The fail direction is the
  // one that matters: live work rendered as calm.
  const twice = {
    agents: 5, working: 0, unknown: 0, unbucketed: 0,
    projects: [
      { name: 'dup', root: '/r/dup', sources: ['registry', 'process'], archived: false,
        agents: [{ pid: 1 }, { pid: 2 }, { pid: 3 }, { pid: 4 }, { pid: 5 }] },
      { name: 'dup', root: '/r/dup-wt-bugfix', sources: ['messaging'], archived: false, agents: [] },
    ],
  } as unknown as FleetResponse

  it('sums the entries instead of letting the last one win', () => {
    const v = buildProjectsView([project('dup')], twice, NONE)
    expect(v.rows[0].liveSessions).toBe(5)
  })

  it('and the project stays in the live view', () => {
    const v = buildProjectsView([project('dup')], twice, { mode: 'live', query: '' })
    expect(v.rows.map(r => r.name)).toEqual(['dup'])
    expect(v.hiddenByView).toBe(0)
  })
})

describe('a live project the registry does not know', () => {
  const projects = [project('alpha')]
  const measured = fleet({ alpha: 1, stranger: 2, 'quiet-stranger': 0 })

  it('appears in the live view, marked, and unlinkable', () => {
    const v = buildProjectsView(projects, measured, { mode: 'live', query: '' })
    const row = v.rows.find(r => r.name === 'stranger')
    expect(row).toBeTruthy()
    expect(row!.registered).toBe(false)
    // `project: null` is what stops the render emitting a link to a route that
    // does not resolve.
    expect(row!.project).toBeNull()
    expect(row!.liveSessions).toBe(2)
  })

  it('does not appear in the all view, whose contract is the registry', () => {
    const v = buildProjectsView(projects, measured, NONE)
    expect(v.rows.map(r => r.name)).toEqual(['alpha'])
    expect(v.totalAll).toBe(1)
  })

  it('is counted in the live size, so it is visible before switching', () => {
    const v = buildProjectsView(projects, measured, NONE)
    expect(v.totalLive).toBe(2)
  })

  it('a fleet project with no session is not one of these', () => {
    // `quiet-stranger` is unregistered AND idle. It is not live work going
    // missing, so it is not injected anywhere.
    const v = buildProjectsView(projects, measured, { mode: 'live', query: '' })
    expect(v.rows.map(r => r.name)).not.toContain('quiet-stranger')
  })

  it('the rows it adds are not counted as rows the view hid', () => {
    // hiddenByView answers "how many projects am I not showing you". An added
    // row is not a hidden one, and folding it in would make the number a
    // plausible fiction rather than a count.
    const v = buildProjectsView([project('alpha'), project('beta')], fleet({ alpha: 1, beta: 0, stranger: 1 }),
      { mode: 'live', query: '' })
    expect(v.rows.map(r => r.name)).toEqual(['alpha', 'stranger'])
    expect(v.hiddenByView).toBe(1)
  })

  it('the filter applies to them like any other row', () => {
    const v = buildProjectsView(projects, measured, { mode: 'live', query: 'strang' })
    expect(v.rows.map(r => r.name)).toEqual(['stranger'])
  })
})
