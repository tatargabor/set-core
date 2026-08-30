/**
 * The board strip, on screen.
 *
 * Every assertion here guards a promise made on the cross-project channel when the
 * producer's `board` contract was handed over (2026-08-30). The dangerous ones are
 * the honesty ones: `unknown` must not fold into a lane, the off-board and
 * coverage warnings must be visible where the reader stands, and a failed command
 * must render as a gap — never as zero, never as silence.
 *
 * The component is rendered directly (not through the whole Fleet page): its
 * guarantees are about ITS answer, and the page-level harness is already proven
 * out by `fleetAgentTree.test.tsx`.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '@testing-library/react'

import FleetBoard from '../../src/components/FleetBoard'

const CONTRACT = {
  configured: true,
  source: 'manifest',
  command: 'node scripts/set-api.mjs',
  commands: ['releases', 'bugs', 'board', 'current'],
  writeCommands: [],
  primary: 'current',
  onDemand: [],
  timeout: 30,
  timeouts: {},
  cwd: '.',
}

/** The producer's own day-one shape, verbatim from the live answer it documented. */
const BOARD = {
  contractVersion: 1,
  command: 'board',
  ok: true,
  generatedAt: '2026-08-30T00:36:10+02:00',
  data: {
    lanes: [
      { lane: 'planned', count: 0 },
      { lane: 'specified', count: 2 },
      { lane: 'in-progress', count: 29 },
      { lane: 'implemented', count: 0 },
      { lane: 'demoed', count: 0 },
      { lane: 'done', count: 0 },
    ],
    unknown: 149,
    total: 180,
    plannedNotOnBoard: [{ release: 'v1.24.0', kind: 'ticket', ref: '293', reason: 'pending' }],
    coverage: { complete: false, reason: 'the projection is refreshed by a run, not continuously' },
    cards: [
      { id: 'SET-0077', title: 'a specified card', lane: 'specified', kind: 'ticket',
        tasksDone: 0, tasksTotal: 4, plannedRelease: 'v1.24.0' },
      { id: 'SET-0081', title: 'an in-progress card', lane: 'in-progress', kind: 'ticket',
        tasksDone: 2, tasksTotal: 3, blocked: { by: 'review', detail: 'open critical findings' } },
      { id: 'SET-0090', title: 'no signal', lane: 'unknown', mibol: 'no-signal' },
    ],
  },
}

type Route = (url: string) => unknown | undefined

function install(route: Route) {
  vi.stubGlobal('fetch', vi.fn((url: string | URL) => {
    const body = route(String(url))
    return Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve(body ?? {}),
    } as Response)
  }))
}

beforeEach(() => { vi.useRealTimers() })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

const strip = (c: HTMLElement) => c.querySelector<HTMLElement>('[data-fleet-board-strip]')!

/** The contract call resolves, then the board call. */
const rendered = async (c: HTMLElement) => waitFor(() => {
  expect(c.querySelector('[data-fleet-board-bands]')).toBeTruthy()
}, { timeout: 4000 })

describe('the board', () => {
  it('draws the six lanes in the producer\'s own array order, and unknown as its own band', async () => {
    install(u => {
      if (u.includes('/project-status/contract')) return CONTRACT
      if (u.includes('commands=board')) return { commands: { board: BOARD } }
      return undefined
    })
    const { container } = render(<FleetBoard project="p" />)
    await rendered(container)

    const bands = container.querySelectorAll('[data-fleet-board-bands] > [data-fleet-board-lane]')
    expect(Array.from(bands).map(b => b.getAttribute('data-fleet-board-lane')))
      .toEqual(['planned', 'specified', 'in-progress', 'implemented', 'demoed', 'done'])
    // Widths follow the COUNTS, not position: in-progress is the only wide lane today.
    const wide = bands[2] as HTMLElement
    expect(wide.style.flexGrow).toBe('29')
    expect((bands[1] as HTMLElement).style.flexGrow).toBe('2')
    expect((bands[0] as HTMLElement).style.flexGrow).toBe('')

    // `unknown` is OUTSIDE the lane bands — a scalar, drawn hatched, never a seventh band.
    expect(container.querySelector('[data-fleet-board-unknown="149"]')).toBeTruthy()
  })

  it('legends the populated lanes and the unknown count', async () => {
    install(u => {
      if (u.includes('/project-status/contract')) return CONTRACT
      if (u.includes('commands=board')) return { commands: { board: BOARD } }
      return undefined
    })
    const { container } = render(<FleetBoard project="p" />)
    await rendered(container)
    const legend = container.querySelector('[data-fleet-board-legend]')!.textContent!
    expect(legend).toContain('specified 2')
    expect(legend).toContain('in-progress 29')
    expect(container.querySelector('[data-fleet-board-unknown-legend="149"]')).toBeTruthy()
    // Empty lanes are not legend noise; zero lanes exist as zero-width bands.
    expect(legend).not.toContain('planned 0')
  })

  it('surfaces plannedNotOnBoard and the incomplete coverage — visible, not swallowed', async () => {
    install(u => {
      if (u.includes('/project-status/contract')) return CONTRACT
      if (u.includes('commands=board')) return { commands: { board: BOARD } }
      return undefined
    })
    const { container } = render(<FleetBoard project="p" />)
    await rendered(container)
    expect(container.querySelector('[data-fleet-board-off-board="1"]')!.textContent)
      .toContain('1 planned off board')
    expect(container.querySelector('[data-fleet-board-coverage-incomplete]')).toBeTruthy()
  })

  it('renders a failed board command as a gap with its class — never as an empty strip', async () => {
    install(u => {
      if (u.includes('/project-status/contract')) return CONTRACT
      if (u.includes('commands=board')) {
        return { commands: { board: { ok: false, errorClass: 'timeout', error: 'no answer in 30s' } } }
      }
      return undefined
    })
    const { container } = render(<FleetBoard project="p" />)
    await waitFor(() => {
      const el = container.querySelector('[data-fleet-board-strip="gap"]')
      expect(el).toBeTruthy()
      expect(el!.textContent).toContain('timeout')
      expect(el!.textContent).toContain('The project did not answer in time.')
    })
    expect(container.querySelector('[data-fleet-board-bands]')).toBeNull()
  })

  it('draws nothing at all for a project that declares no board command', async () => {
    install(u => {
      if (u.includes('/project-status/contract'))
        return { ...CONTRACT, commands: ['releases', 'bugs'] }
      return undefined
    })
    const { container } = render(<FleetBoard project="p" />)
    // The contract answered — the strip's silence is a decision, not a pending fetch.
    await waitFor(() => {
      expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls
        .some((c: unknown[]) => String(c[0]).includes('commands=board'))).toBe(false)
    })
    expect(container.querySelector('[data-fleet-board-strip]')).toBeNull()
  })

  it('says the shape moved when the answer carries no lanes array', async () => {
    install(u => {
      if (u.includes('/project-status/contract')) return CONTRACT
      if (u.includes('commands=board')) return { commands: { board: { ok: true, data: {} } } }
      return undefined
    })
    const { container } = render(<FleetBoard project="p" />)
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-board-strip="shape"]')!.textContent)
        .toContain('no lanes array')
    })
  })

  it('renders an all-zero board as the project\'s own zero, in words', async () => {
    install(u => {
      if (u.includes('/project-status/contract')) return CONTRACT
      if (u.includes('commands=board')) {
        return { commands: { board: { ok: true, data: {
          lanes: [
            { lane: 'planned', count: 0 }, { lane: 'specified', count: 0 },
            { lane: 'in-progress', count: 0 }, { lane: 'implemented', count: 0 },
            { lane: 'demoed', count: 0 }, { lane: 'done', count: 0 },
          ],
          unknown: 0, total: 0,
        } } } }
      }
      return undefined
    })
    const { container } = render(<FleetBoard project="p" />)
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-board-empty]')!.textContent)
        .toContain('0 cards')
    })
  })

  it('re-asks on its own, but no faster than the transport cache would honour', async () => {
    // Fake timers ONLY here: this test drives the clock, and waitFor — which needs
    // real ones — is not part of it. The initial fetch is flushed by advancing time
    // by zero, which also flushes the microtasks its promise chain waits on.
    vi.useFakeTimers()
    install(u => {
      if (u.includes('/project-status/contract')) return CONTRACT
      if (u.includes('commands=board')) return { commands: { board: BOARD } }
      return undefined
    })
    render(<FleetBoard project="p" />)
    const boardCalls = () => (global.fetch as ReturnType<typeof vi.fn>).mock.calls
      .filter((c: unknown[]) => String(c[0]).includes('commands=board')).length
    // The contract call resolves, the state flips, the board effect mounts and its
    // first tick fires — a few microtask hops, so loop until the first call lands.
    for (let i = 0; i < 10 && boardCalls() === 0; i++) await vi.advanceTimersByTimeAsync(1)
    const first = boardCalls()
    expect(first).toBe(1)
    // Under the 30s cache there is no second call; past it there is exactly one more.
    await vi.advanceTimersByTimeAsync(20_000)
    expect(boardCalls()).toBe(first)
    await vi.advanceTimersByTimeAsync(15_000)
    expect(boardCalls()).toBe(first + 1)
  })
})

describe('the card board', () => {
  const renderBoard = async () => {
    install(u => {
      if (u.includes('/project-status/contract')) return CONTRACT
      if (u.includes('commands=board')) return { commands: { board: BOARD } }
      return undefined
    })
    const r = render(<FleetBoard project="p" />)
    await rendered(r.container)
    return r
  }

  it('renders one column per declared band, in the producer\'s order, headers taken from the array', async () => {
    const { container } = await renderBoard()
    const cols = container.querySelectorAll('[data-fleet-board-columns] > [data-fleet-board-col]')
    expect(Array.from(cols).map(c => c.getAttribute('data-fleet-board-col')))
      .toEqual(['planned', 'specified', 'in-progress', 'implemented', 'demoed', 'done'])
    // Header counts are the producer's — including the zeros.
    expect(container.querySelector('[data-fleet-board-col="in-progress"]')!.textContent)
      .toContain('29')
    expect(container.querySelector('[data-fleet-board-col="planned"]')!.textContent)
      .toContain('0')
  })

  it('places each card by its own lane, and the header count stays the producer\'s', async () => {
    const { container } = await renderBoard()
    const spec = container.querySelector('[data-fleet-board-col="specified"]')!
    expect(spec.querySelector('[data-fleet-board-card="SET-0077"]')).toBeTruthy()
    // The producer says specified holds 2; the answer ships 1 card in it. The
    // header says 2, one card renders, and nothing reconciles the difference.
    expect(spec.textContent).toContain('2')
    expect(spec.querySelectorAll('[data-fleet-board-card]').length).toBe(1)
  })

  it('renders the generic face: progress only with both fields, blocked mark, no domain field name', async () => {
    const { container } = await renderBoard()
    const c1 = container.querySelector('[data-fleet-board-card="SET-0077"]')!
    expect(c1.textContent).toContain('0/4')
    expect(c1.textContent).toContain('v1.24.0')
    const c2 = container.querySelector('[data-fleet-board-card="SET-0081"]')!
    expect(c2.textContent).toContain('2/3')
    expect(c2.querySelector('[title="open critical findings"]')).toBeTruthy()
    // The producer's reason field keeps its domain name on the producer side; the
    // framework's face has no `note` here to render, and no domain word anywhere.
    expect(c2.textContent).not.toContain('mibol')
    const c3 = container.querySelector('[data-fleet-board-card="SET-0090"]')!
    expect(c3).toBeTruthy()
    expect(c3.textContent).not.toContain('/')
  })

  it('keeps the unknown tray visually apart, header counted from the scalar', async () => {
    const { container } = await renderBoard()
    const tray = container.querySelector('[data-fleet-board-tray]')!
    expect(tray.querySelector('[data-fleet-board-card="SET-0090"]')).toBeTruthy()
    // The scalar is 149; the tray holds 1 card. The header says 149.
    expect(tray.textContent).toContain('149')
    // The tray is NOT one of the band columns.
    expect(tray.getAttribute('data-fleet-board-col')).toBeNull()
  })

  it('renders an unreadable cards field as a shape warning, not as silence', async () => {
    install(u => {
      if (u.includes('/project-status/contract')) return CONTRACT
      if (u.includes('commands=board')) {
        return { commands: { board: { ok: true, data: { ...BOARD.data, cards: 180 } } } }
      }
      return undefined
    })
    const { container } = render(<FleetBoard project="p" />)
    await rendered(container)
    expect(container.querySelector('[data-fleet-board-cards-shape]')!.textContent)
      .toContain('cannot read')
  })

  it('is read-only: no card is a button, form or link', async () => {
    const { container } = await renderBoard()
    const board = container.querySelector('[data-fleet-board-columns]')!
    expect(board.querySelector('button, a, input, form')).toBeNull()
  })
})
