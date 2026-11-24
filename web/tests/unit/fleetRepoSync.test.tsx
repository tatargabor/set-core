/**
 * The repository-sync chip and table — change `fleet-repo-sync`.
 *
 * The claims are about what the reader sees and when the server is asked: no request until
 * the table opens, one per opening or refresh, and a chip that says "not measured" rather than
 * a count it does not have.
 */
import { fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import FleetRepoSync from '../../src/components/FleetRepoSync'
import { chipText, longAge, parseRepoSync, syncCell } from '../../src/lib/fleetRepoSync'

function row(name: string, extra: Record<string, unknown> = {}) {
  return {
    name, path: `/tmp/${name}`, active_by: ['commit'], branch: 'main', detached: false,
    uncommitted: 0, untracked: 0, upstream: 'origin/main', no_upstream: false, ahead: 0, behind: 0,
    diverged: false, unpushed_branches: [], stash: 0, remote_host: 'example.org', fetch_age_s: 60,
    worktrees: [], push_may_deploy: { value: 'no', source: null, reason: 'none' }, errors: {},
    problems: [], last_commit_age_s: 100, last_session_age_s: null, ...extra,
  }
}

function answer(projects: unknown[], problem_count: number) {
  return {
    generated_at: 1, days: 30, duration_ms: 12, projects, problem_count,
    excluded: { archived: 2, e2e_run: 1, inactive: 3, missing: [], not_git: [] },
  }
}

function serve(body: unknown) {
  const f = vi.fn(() => Promise.resolve(new Response(JSON.stringify(body))))
  vi.stubGlobal('fetch', f)
  return f
}

afterEach(() => { vi.unstubAllGlobals() })

describe('the chip makes no claim before a measurement', () => {
  it('reads "not measured" with no count (AC-15)', () => {
    const t = chipText(null, Date.now())
    expect(t.count).toBeNull()
    expect(t.age).toBe('not measured')
  })

  it('carries the count and its age after one (AC-16)', () => {
    const now = Date.now()
    const t = chipText({ problems: 5, at: now - 10 * 60_000 }, now)
    expect(t.count).toBe('5')
    expect(t.age).toBe('10m ago')
  })
})

describe('requests are sent only on request', () => {
  it('sends nothing while the table is closed (AC-1)', () => {
    const f = serve(answer([], 0))
    const view = render(<FleetRepoSync />)
    expect(f).not.toHaveBeenCalled()
    expect(view.container.querySelector('[data-fleet-repo-sync="unmeasured"]')).not.toBeNull()
  })

  it('sends exactly one on opening, and a second only on refresh (AC-2)', async () => {
    const f = serve(answer([row('a', { uncommitted: 2, problems: ['uncommitted'] })], 1))
    const view = render(<FleetRepoSync />)
    fireEvent.click(view.container.querySelector('[data-fleet-repo-sync-toggle]')!)
    await waitFor(() => expect(view.container.querySelector('[data-repo-sync-row="a"]')).not.toBeNull())
    expect(f).toHaveBeenCalledTimes(1)
    expect(String((f.mock.calls[0] as unknown[])[0])).toContain('/api/fleet/repo-sync')
    fireEvent.click(view.container.querySelector('[data-repo-sync-refresh]')!)
    await waitFor(() => expect(f).toHaveBeenCalledTimes(2))
    expect(view.container.querySelector('[data-fleet-repo-sync="1"]')).not.toBeNull()
  })
})

describe('the table', () => {
  it('renders rows in the order the server ranked them, problems labelled', async () => {
    serve(answer([
      row('dirty', { uncommitted: 3, problems: ['uncommitted'] }),
      row('clean'),
    ], 1))
    const view = render(<FleetRepoSync />)
    fireEvent.click(view.container.querySelector('[data-fleet-repo-sync-toggle]')!)
    await waitFor(() => expect(view.container.querySelectorAll('[data-repo-sync-row]').length).toBe(2))
    const names = [...view.container.querySelectorAll('[data-repo-sync-row]')].map(e => e.getAttribute('data-repo-sync-row'))
    expect(names).toEqual(['dirty', 'clean'])
    expect(view.container.textContent).toContain('uncommitted')
  })

  it('shows a deploy hint with the file it was read from', async () => {
    serve(answer([row('d', {
      push_may_deploy: { value: 'yes', source: '.gitlab-ci.yml', reason: 'r', job: 'deploy', environment: 'production' },
      problems: ['push-may-deploy'],
    })], 1))
    const view = render(<FleetRepoSync />)
    fireEvent.click(view.container.querySelector('[data-fleet-repo-sync-toggle]')!)
    await waitFor(() => expect(view.container.querySelector('[data-repo-sync-deploy="yes"]')).not.toBeNull())
    expect(view.container.querySelector('[data-repo-sync-deploy="yes"]')!.textContent).toContain('.gitlab-ci.yml')
  })

  it('closes on Escape', async () => {
    serve(answer([], 0))
    const view = render(<FleetRepoSync />)
    fireEvent.click(view.container.querySelector('[data-fleet-repo-sync-toggle]')!)
    await waitFor(() => expect(view.container.querySelector('[data-fleet-repo-sync-table]')).not.toBeNull())
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(view.container.querySelector('[data-fleet-repo-sync-table]')).toBeNull()
  })
})

describe('the parser keeps gaps as gaps', () => {
  it('a null count stays null, and the sync cell says so', () => {
    const d = parseRepoSync(answer([row('g', { ahead: null, behind: null, uncommitted: null })], 1))!
    expect(d.projects[0].uncommitted).toBeNull()
    expect(syncCell(d.projects[0])).toBe('—')
  })

  it('an unexpected shape is refused, not rendered', () => {
    expect(parseRepoSync({ nope: 1 })).toBeNull()
  })

  it('reads ahead/behind and no-upstream', () => {
    const d = parseRepoSync(answer([row('x', { ahead: 2, behind: 3 }), row('y', { no_upstream: true, ahead: null, behind: null })], 2))!
    expect(syncCell(d.projects[0])).toBe('↑2 ↓3')
    expect(syncCell(d.projects[1])).toBe('no upstream')
  })

  it('ages run to days', () => {
    expect(longAge(3 * 86400)).toBe('3d')
    expect(longAge(null)).toBe('—')
  })
})
