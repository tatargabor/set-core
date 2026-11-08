/**
 * The wave-board list with dependencies between boards — change
 * `wave-board-shared-linked`, AC-14. Rendered from a mocked route: the claim is
 * what the reader sees — "waits on N" / "blocks N" on the row, a dangling
 * reference on the CLOSED chip, and a board without dependencies unchanged.
 */
import { fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import FleetWaves from '../../src/components/FleetWaves'
import { dependencyMarks, totals, type ReadableBoard } from '../../src/lib/fleetWaves'

function board(project: string, job: string, extra: Record<string, unknown> = {}) {
  return {
    project, job, title: `Board ${job}`, artifact_url: null,
    counts: { todo: 2, doing: 0, done: 1, blocked: 0, skipped: 0 },
    other: 0, waves: 1, current_wave: { id: 'w0', title: 'First' },
    updated: '2026-10-01T10:00:00Z', unreadable: false, ...extra,
  }
}

const waiting = board('A', 'j', {
  waiting: 2, deps_unresolved: 0, deps_in: [],
  deps_out: [
    { item: 'a', on: { project: 'B', job: 'k', item: 'b' }, status: 'doing', met: false },
    { item: 'c', on: { project: 'B', job: 'k', item: 'd' }, status: 'todo', met: false },
    { item: 'e', on: { project: 'B', job: 'k', item: 'f' }, status: 'done', met: true },
  ],
})
const blocking = board('B', 'k', {
  waiting: 0, deps_unresolved: 0, deps_out: [],
  deps_in: [
    { item: 'b', by: { project: 'A', job: 'j', item: 'a' }, met: false },
    { item: 'f', by: { project: 'A', job: 'j', item: 'e' }, met: true },
  ],
})
const dangling = board('C', 'm', {
  waiting: 1, deps_unresolved: 1, deps_in: [],
  deps_out: [{ item: 'x', on: { project: 'C', job: 'nowhere', item: 'y' }, status: null, met: false }],
})

async function mount(boards: unknown[]) {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ boards })))))
  const view = render(<FleetWaves selected={null} onSelectProject={() => {}} />)
  await waitFor(() => expect(view.container.querySelector('[data-fleet-waves]')).not.toBeNull())
  return view.container
}

afterEach(() => { vi.unstubAllGlobals() })

describe('wave-board dependencies', () => {
  it('counts only unmet edges', () => {
    const w = dependencyMarks(waiting as ReadableBoard)
    expect(w.waitsOn.map(d => d.item)).toEqual(['a', 'c'])
    expect(dependencyMarks(blocking as ReadableBoard).blocks.map(d => d.item)).toEqual(['b'])
    expect(totals([waiting, blocking, dangling] as ReadableBoard[]).dangling).toBe(1)
  })

  it('shows waits on N and blocks N with the references in the tooltip (AC-14)', async () => {
    const c = await mount([waiting, blocking])
    fireEvent.click(c.querySelector('[data-fleet-waves-toggle]')!)
    const waits = c.querySelector('[data-fleet-waves-row="j"] [data-fleet-waves-waits]')
    expect(waits?.textContent).toContain('waits on 2')
    expect(waits?.getAttribute('title')).toContain('a → B/k/b (doing)')
    expect(waits?.getAttribute('title')).not.toContain('B/k/f')
    const blocks = c.querySelector('[data-fleet-waves-row="k"] [data-fleet-waves-blocks]')
    expect(blocks?.textContent).toContain('blocks 1')
    expect(blocks?.getAttribute('title')).toContain('A/j/a → b')
  })

  it('puts a dangling reference on the closed chip (AC-14)', async () => {
    const c = await mount([dangling, waiting])
    expect(c.querySelector('[data-fleet-waves-list]')).toBeNull()
    expect(c.querySelector('[data-fleet-waves-dangling]')?.getAttribute('data-fleet-waves-dangling')).toBe('1')
    expect(c.querySelector('[data-fleet-waves-toggle]')?.getAttribute('aria-label')).toContain('1 dangling dependency')
  })

  it('leaves a board without dependencies as it was', async () => {
    const c = await mount([board('A', 'plain'), board('B', 'old-server', { deps_out: [], deps_in: [], waiting: 0 })])
    expect(c.querySelector('[data-fleet-waves-dangling]')).toBeNull()
    fireEvent.click(c.querySelector('[data-fleet-waves-toggle]')!)
    expect(c.querySelector('[data-fleet-waves-waits]')).toBeNull()
    expect(c.querySelector('[data-fleet-waves-blocks]')).toBeNull()
  })
})
