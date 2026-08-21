/**
 * Renaming a running agent, from the tile.
 *
 * The control exists to repair names a reboot lost — which no code can derive,
 * because the framework cannot know which conversation somebody called
 * `bugfix`. So the two properties that matter are that it is offered only where
 * it can work, and that a refusal leaves the name it was refused for alone.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import FleetRename from '../../src/components/FleetRename'
import type { FleetAgent } from '../../src/lib/fleetTypes'

const agent = (over: Partial<FleetAgent> = {}): FleetAgent => ({
  pid: 1, name: 'proj-ab', project: 'proj', cwd: '/p', state: 'quiet',
  population: 'started-here', terminal_label: 'before', ...over,
} as FleetAgent)

describe('rename is offered only where the framework holds the name', () => {
  it('offers no control for an agent this framework does not hold, but keeps the name', () => {
    // Not a disabled pencil: an offered-then-failing control invites the click
    // that teaches the reader the screen is lying. And not nothing at all: the
    // name is rendered here, so returning null would take the name away too.
    const { container } = render(
      <FleetRename agent={agent({ population: 'foreign', terminal_label: null })}>
        proj-ab
      </FleetRename>)
    expect(container.querySelector('[data-fleet-rename]')).toBeNull()
    expect(container.textContent).toContain('proj-ab')
  })

  it('editing REPLACES the name instead of sitting beside it', async () => {
    // Found by looking, 2026-08-21: the header read `set-core-memory
    // [set-core-memory] rename cancel` — the same string twice, one editable.
    // No structural test would have called that wrong.
    const { container } = render(<FleetRename agent={agent()}>before</FleetRename>)
    expect(container.textContent).toContain('before')
    fireEvent.click(container.querySelector('[data-fleet-rename="before"]')!)
    const text = container.textContent ?? ''
    expect(text.match(/before/g) ?? []).toHaveLength(0)
    expect(container.querySelector('[data-fleet-rename-input="before"]')).toBeTruthy()
  })

  it('offers the control on a held agent', () => {
    const { container } = render(<FleetRename agent={agent()} />)
    expect(container.querySelector('[data-fleet-rename="before"]')).toBeTruthy()
  })
})

describe('the rename itself', () => {
  it('sends the new name and reports it once the server confirmed', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({}) }))
    vi.stubGlobal('fetch', fetchMock)
    const renamed = vi.fn()

    const { container } = render(<FleetRename agent={agent()} onRenamed={renamed} />)
    fireEvent.click(container.querySelector('[data-fleet-rename="before"]')!)
    const input = container.querySelector('[data-fleet-rename-input="before"]') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'after' } })
    await act(async () => { fireEvent.keyDown(input, { key: 'Enter' }) })

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/fleet/agents/before/rename')
    expect(JSON.parse(String(init.body))).toEqual({ new_label: 'after' })
    expect(renamed).toHaveBeenCalledWith('before', 'after')
  })

  it('shows a refusal and leaves the name it was refused for alone', async () => {
    // The server refuses a name another agent holds rather than deriving a
    // variant. That refusal is information for the person looking at it.
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false, status: 409, json: async () => ({ detail: 'after is already held here (pid 9)' }),
    })))
    const renamed = vi.fn()

    const { container } = render(<FleetRename agent={agent()} onRenamed={renamed} />)
    fireEvent.click(container.querySelector('[data-fleet-rename="before"]')!)
    const input = container.querySelector('[data-fleet-rename-input="before"]') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'after' } })
    await act(async () => { fireEvent.keyDown(input, { key: 'Enter' }) })

    await waitFor(() =>
      expect(container.querySelector('[data-fleet-rename-error="before"]')).toBeTruthy())
    expect(screen.getByText(/already held/)).toBeTruthy()
    expect(renamed).not.toHaveBeenCalled()
    expect((container.querySelector('[data-fleet-rename-input="before"]') as HTMLInputElement).value)
      .toBe('after')
  })

  it('does not call the server for a name that has not changed', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(<FleetRename agent={agent()} />)
    fireEvent.click(container.querySelector('[data-fleet-rename="before"]')!)
    const input = container.querySelector('[data-fleet-rename-input="before"]') as HTMLInputElement
    await act(async () => { fireEvent.keyDown(input, { key: 'Enter' }) })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('escape closes without asking for anything', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(<FleetRename agent={agent()} />)
    fireEvent.click(container.querySelector('[data-fleet-rename="before"]')!)
    const input = container.querySelector('[data-fleet-rename-input="before"]') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'typed-then-thought-better-of-it' } })
    await act(async () => { fireEvent.keyDown(input, { key: 'Escape' }) })
    expect(fetchMock).not.toHaveBeenCalled()
    expect(container.querySelector('[data-fleet-rename="before"]')).toBeTruthy()
  })
})
