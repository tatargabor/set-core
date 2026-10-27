/**
 * The wave-board chip and list with stale boards — change `wave-board-staleness`,
 * AC-16 to AC-18. Rendered from a mocked route, because the claim is about what
 * the reader sees: a stale board must be visible on the CLOSED chip, and a
 * current board must look exactly as it did before.
 */
import { fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import FleetWaves from '../../src/components/FleetWaves'

function board(project: string, job: string, extra: Record<string, unknown> = {}) {
  return {
    project, job, title: `Board ${job}`, artifact_url: null,
    counts: { todo: 2, doing: 0, done: 1, blocked: 1, skipped: 0 },
    other: 0, waves: 1, current_wave: { id: 'w0', title: 'First' },
    updated: '2026-10-01T10:00:00Z', unreadable: false, ...extra,
  }
}

const stale = (project: string, commits: number, manual: number) =>
  board(project, 'j', { reviewed: null, manual_open: manual, commits_since_change: commits, stale: true })
const current = (project: string) =>
  board(project, 'j', { reviewed: null, manual_open: 3, commits_since_change: 1, stale: false })

function serve(boards: unknown[]) {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({ boards })))))
}

async function mount(boards: unknown[]) {
  serve(boards)
  const view = render(<FleetWaves selected={null} onSelectProject={() => {}} />)
  await waitFor(() => expect(view.container.querySelector('[data-fleet-waves]')).not.toBeNull())
  return view.container
}

afterEach(() => { vi.unstubAllGlobals() })

describe('stale wave boards', () => {
  it('counts stale boards on the closed chip (AC-16)', async () => {
    const c = await mount([stale('a', 40, 2), stale('b', 9, 1), current('c')])
    const count = c.querySelector('[data-fleet-waves-stale-total]')
    expect(count?.getAttribute('data-fleet-waves-stale-total')).toBe('2')
    expect(c.querySelector('[data-fleet-waves-toggle]')?.getAttribute('aria-label')).toContain('2 stale')
    // Closed: the list is not rendered, and the count is visible anyway.
    expect(c.querySelector('[data-fleet-waves-list]')).toBeNull()
  })

  it('marks the stale row with its commits and names the manual items (AC-17)', async () => {
    const c = await mount([stale('a', 438, 4)])
    fireEvent.click(c.querySelector('[data-fleet-waves-toggle]')!)
    const marker = c.querySelector('[data-fleet-waves-stale]')
    expect(marker?.textContent).toContain('438 since')
    expect(marker?.getAttribute('title')).toContain('4 open items only an agent can move')
  })

  it('shows no marker and no count when nothing is stale (AC-18)', async () => {
    const c = await mount([current('a'), board('b', 'old-server')])
    expect(c.querySelector('[data-fleet-waves-stale-total]')).toBeNull()
    fireEvent.click(c.querySelector('[data-fleet-waves-toggle]')!)
    expect(c.querySelectorAll('[data-fleet-waves-row]')).toHaveLength(2)
    expect(c.querySelector('[data-fleet-waves-stale]')).toBeNull()
  })

  it('says "not measured" for a board whose commits could not be counted', async () => {
    const c = await mount([board('a', 'j', { manual_open: 2, commits_since_change: null, stale: false })])
    fireEvent.click(c.querySelector('[data-fleet-waves-toggle]')!)
    const row = c.querySelector('[data-fleet-waves-row="j"]')!
    expect(row.querySelector('[title*="not measured"]')).not.toBeNull()
  })
})
