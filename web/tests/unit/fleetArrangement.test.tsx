/**
 * The project column on screen — D-2's manual arrangement, and the header that
 * exists because manual arrangement can hide things.
 *
 * Most of these assert a DIRECTION rather than a value, because every defect
 * this screen can produce is one that looks calm:
 *
 *  - a waiting count of zero for a state the producer cannot report;
 *  - a collapsed group that hides an agent in an undetermined state;
 *  - a parked project whose agents stop being counted;
 *  - an arranged project that quietly stops rendering when discovery loses it;
 *  - a refused save that leaves the screen looking saved.
 *
 * The drag gesture itself is not asserted here. jsdom has no layout engine, so
 * every rectangle is zero and a pointer hit-test cannot decide anything — a test
 * that "dragged" by dispatching events would be measuring the handler, not the
 * product. What is asserted is the keyboard path, which is a real way a person
 * reorders, and the model tests cover what a completed move produces.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

function agent(pid: number, name: string, state = 'quiet'): Json {
  return {
    pid, name, project: null, branch: 'main', session_id: 's', binding_confirmed: true,
    sources: ['process'], kind: 'interactive', state, tool: null, tool_elapsed_seconds: null,
    other_tools: [], last_movement_seconds: 5, unknown_reason: state === 'unknown' ? 'no log' : null,
  }
}

const project = (name: string, agents: Json[] = []): Json => ({
  name, root: `/r/${name}`, sources: ['process'], archived: false, agents,
})

function fleet(projects: Json[], extra: Json = {}): Json {
  const all = projects.flatMap(p => (p.agents as Json[]) ?? [])
  return {
    agents: all.length,
    working: all.filter(a => a.state === 'working').length,
    unknown: all.filter(a => a.state === 'unknown').length,
    projects,
    quiet_means: 'no outstanding tool call',
    ...extra,
  }
}

const LAYOUT = {
  version: 7,
  groups: [
    { id: 'g-set', name: 'set', collapsed: false, projects: ['set-core', 'set-designer'], missing: ['set-gone'] },
    { id: 'g-closed', name: 'closed', collapsed: true, projects: ['hidden'], missing: [] },
  ],
  parked: ['felretett'],
  ungrouped: ['maradek'],
  missing: ['set-gone'],
}

interface Harness {
  puts: { body: Json; status: number }[]
  putStatus: number
  putDetail: string
}

function install(agentsBody: Json, layout: Json = LAYOUT): Harness {
  const h: Harness = { puts: [], putStatus: 200, putDetail: '' }
  let current = layout
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      if (init?.method === 'PUT') {
        const body = JSON.parse(String(init.body)) as Json
        h.puts.push({ body, status: h.putStatus })
        if (h.putStatus === 409) {
          return Promise.resolve({
            ok: false, status: 409,
            json: () => Promise.resolve({ detail: h.putDetail || 'it changed meanwhile' }),
          } as Response)
        }
        // Echo the way the real server does: what came in as `projects` IS the
        // stored order, and `ungrouped_order` decides the unassigned block's
        // order. A harness that quietly re-sorted either would hide exactly the
        // defect these tests exist for.
        current = {
          version: Number((current as Json).version ?? 0) + 1,
          groups: (body.groups as Json[]).map(g => ({
            ...g, missing: [], order: (g as Json).projects,
          })),
          parked: body.parked,
          parked_missing: [],
          parked_order: body.parked,
          ungrouped: (body.ungrouped_order as string[])?.length
            ? body.ungrouped_order
            : (layout as Json).ungrouped,
          missing: [],
        }
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(current) } as Response)
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(current) } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: [] }) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(agentsBody) } as Response)
  }))
  return h
}

beforeEach(() => { try { localStorage.clear() } catch { /* no storage */ } })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

const ALL = fleet([
  project('set-core', [agent(1, 'a1')]),
  project('set-designer'),
  project('hidden', [agent(2, 'a2', 'unknown')]),
  project('felretett', [agent(3, 'a3', 'unknown')]),
  project('maradek'),
])

describe('the waiting count — a state the producer does not report is not a zero', () => {
  it('says the state is unmeasured instead of rendering “0 waiting for an answer”', async () => {
    install(ALL)
    const { container } = render(<Fleet />)
    const header = await waitFor(() => {
      const el = container.querySelector('[data-fleet-attention]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })

    // The envelope carries no `waiting` key and no agent is in that state, so
    // the honest report is that nothing was measured. A rendered zero would be
    // an ANSWER nobody gave — the same false absence the whole screen exists
    // to prevent, arriving through the one control that is supposed to catch it.
    expect(header.querySelector('[data-fleet-waiting="unreported"]')).toBeTruthy()
    expect(header.textContent ?? '').not.toMatch(/0\s*waiting/)
  })

  it('counts and offers the jump as soon as the producer reports the state', async () => {
    install(fleet([
      project('set-core', [agent(1, 'a1')]),
      project('hidden', [agent(2, 'a2', 'waiting')]),
      project('felretett', []),
    ], { waiting: 1 }))
    const { container } = render(<Fleet />)

    await waitFor(() => {
      expect(container.querySelector('[data-fleet-jump="waiting"]')).toBeTruthy()
    })
    expect(container.querySelector('[data-fleet-waiting="unreported"]')).toBeNull()
    expect(container.querySelector('[data-fleet-jump="waiting"]')!.textContent).toMatch(/1 waiting for an answer/)
  })

  /**
   * `waiting: 0` from a producer that DOES report the state is a measurement,
   * and must read as one. A truthiness check on that key would collapse it into
   * "not reported" — the absent-key-is-not-an-empty-value defect with its two
   * cases swapped.
   */
  it('treats an explicit zero as a measurement, not as an absent field', async () => {
    install(fleet([project('set-core', [agent(1, 'a1')])], { waiting: 0 }))
    const { container } = render(<Fleet />)
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-attention]')).toBeTruthy()
    })
    expect(container.querySelector('[data-fleet-waiting="unreported"]')).toBeNull()
    expect(container.querySelector('[data-fleet-attention]')!.textContent).toMatch(/0 waiting for an answer/)
  })
})

describe('nothing compacted may hide a state', () => {
  it('counts a collapsed group’s and the parked section’s agents in the header', async () => {
    install(ALL)
    const { container } = render(<Fleet />)
    const header = await waitFor(() => {
      const el = container.querySelector('[data-fleet-attention]') as HTMLElement
      expect(el.textContent).toMatch(/unknown/)
      return el
    })
    // Two agents in an undetermined state: one inside a COLLAPSED group, one
    // inside the parked section. Neither row is on screen; both are counted.
    expect(header.textContent).toMatch(/2 unknown/)
    expect(container.querySelector('[data-fleet-project="hidden"]')).toBeNull()
    expect(container.querySelector('[data-fleet-project="felretett"]')).toBeNull()
  })

  it('marks the collapsed group itself, where the reader is standing', async () => {
    install(ALL)
    const { container } = render(<Fleet />)
    const group = await waitFor(() => {
      const el = container.querySelector('[data-fleet-group="g-closed"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(group.getAttribute('data-fleet-group-collapsed')).toBe('true')
    // The counter is on the closed header, not only in the global total. A
    // total tells the reader that something is wrong somewhere; this tells them
    // which closed box to open.
    expect(within(group).getByTitle('unknown state').textContent).toMatch(/1/)
  })

  it('marks the parked section with its own count while it stays closed', async () => {
    install(ALL)
    const { container } = render(<Fleet />)
    const parked = await waitFor(() => {
      const el = container.querySelector('[data-fleet-parked]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(parked.getAttribute('data-fleet-parked-open')).toBe('false')
    expect(within(parked).getByTitle('unknown state').textContent).toMatch(/1/)
  })

  it('jumps into a collapsed group, opening it rather than scrolling past it', async () => {
    install(ALL)
    const { container } = render(<Fleet />)
    await waitFor(() => expect(container.querySelector('[data-fleet-group="g-closed"]')).toBeTruthy())
    const jump = container.querySelector('[data-fleet-jump="unknown"]') as HTMLElement
    expect(jump).toBeTruthy()
    expect(container.querySelector('[data-fleet-project="hidden"]')).toBeNull()
    fireEvent.click(jump)
    // A jump that leaves the target closed is a jump to nothing.
    expect(container.querySelector('[data-fleet-project="hidden"]')).toBeTruthy()
  })
})

describe('an arranged project discovery no longer finds', () => {
  it('is rendered as missing rather than dropped from the list', async () => {
    install(ALL)
    const { container } = render(<Fleet />)
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-missing="set-gone"]')).toBeTruthy()
    })
    expect(container.querySelector('[data-fleet-missing="set-gone"]')!.textContent).toMatch(/missing/)
  })

  it('is still in the document a save writes back', async () => {
    const h = install(ALL)
    const { container } = render(<Fleet />)
    const handle = await waitFor(() => {
      const el = container.querySelector('[data-drag-handle="g-set:set-core"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })

    fireEvent.keyDown(handle, { key: 'ArrowDown' })
    await waitFor(() => expect(h.puts).toHaveLength(1))
    const body = h.puts[0].body as { groups: { projects: string[] }[]; base_version: number }
    expect(body.groups[0].projects).toContain('set-gone')
  })
})

describe('reordering', () => {
  it('moves a project inside its group from the keyboard, and saves the version it read', async () => {
    const h = install(ALL)
    const { container } = render(<Fleet />)
    const handle = await waitFor(() => {
      const el = container.querySelector('[data-drag-handle="g-set:set-core"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })

    fireEvent.keyDown(handle, { key: 'ArrowDown' })
    await waitFor(() => expect(h.puts).toHaveLength(1))
    const body = h.puts[0].body as { groups: { id: string; projects: string[] }[]; base_version: number }
    expect(body.groups[0].projects.slice(0, 2)).toEqual(['set-designer', 'set-core'])
    // `base_version` is what makes a stale write refusable; sending the wrong
    // one turns the 409 into a silent overwrite.
    expect(body.base_version).toBe(7)
  })

  it('does not move past the end of its own group', async () => {
    // Its own layout, because the shared one's `set-set` group ends with a
    // MISSING member — and a missing member is a real position in the stored
    // order, so its neighbour moving down is a legitimate reorder rather than
    // the boundary this test is about. Reusing that fixture would have made the
    // assertion pass for the wrong reason before 2026-08-19 and fail for the
    // wrong reason after it.
    const h = install(ALL, {
      version: 3,
      groups: [{ id: 'g-veg', name: 'tail', collapsed: false, projects: ['set-core', 'set-designer'], missing: [], order: ['set-core', 'set-designer'] }],
      parked: [], parked_missing: [], parked_order: [], ungrouped: [], missing: [],
    })
    const { container } = render(<Fleet />)
    const handle = await waitFor(() => {
      const el = container.querySelector('[data-drag-handle="g-veg:set-designer"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    // The last entry of the group. A move down would have to leave the group,
    // and leaving a group by dragging is precisely what D-2 refuses.
    fireEvent.keyDown(handle, { key: 'ArrowDown' })
    await new Promise(r => setTimeout(r, 0))
    expect(h.puts).toHaveLength(0)
  })

  /**
   * The stored order is one list, and a missing member holds a position in it.
   *
   * Before the API returned `order`, the client rendered `projects` then
   * `missing` and sent back the concatenation — so a name discovery could not
   * find was re-appended to the END of its group on every single save. The user
   * could watch it walk downwards each time they dragged anything, and nothing
   * on the screen said why. This asserts the position survives a move that
   * crosses it.
   */
  it('reorders across a missing member and keeps that member where it sits', async () => {
    const h = install(ALL, {
      version: 4,
      groups: [{
        id: 'g-mid', name: 'mid', collapsed: false,
        projects: ['set-core', 'set-designer'], missing: ['set-gone'],
        order: ['set-core', 'set-gone', 'set-designer'],
      }],
      parked: [], parked_missing: [], parked_order: [], ungrouped: [], missing: ['set-gone'],
    })
    const { container } = render(<Fleet />)
    const handle = await waitFor(() => {
      const el = container.querySelector('[data-drag-handle="g-mid:set-core"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })

    fireEvent.keyDown(handle, { key: 'ArrowDown' })
    await waitFor(() => expect(h.puts).toHaveLength(1))
    const body = h.puts[0].body as { groups: { projects: string[] }[] }
    // The whole stored list, in one piece — `set-gone` at index 0 now, because
    // that is where the move put it, and NOT flattened to the end.
    expect(body.groups[0].projects).toEqual(['set-gone', 'set-core', 'set-designer'])
  })

  /**
   * A click on the handle is not a drag — found on the LIVE screen, 2026-08-19.
   *
   * Pressing a grip and releasing without moving reordered the list and saved
   * it. `indexAt` answers "which row is under this point", and a press in the
   * lower half of a row is already past that row's midpoint, so it answers with
   * the next row. Measured against the running server: one click on a project's
   * grip moved it six stored positions, because the rows in between were hidden
   * by the ungrouped filter.
   *
   * The direction is the expensive one — nothing fails, nothing is lost, and the
   * arrangement is hand-made work nobody diffs. So the assertion is the absence
   * of a save, which is the only visible trace the defect had.
   *
   * jsdom gives every rectangle zero size, so `indexAt` falls through to the LAST
   * rendered row. The handle under test therefore has to be one that is not last
   * — the first — or the wrong index and the right one coincide and the test
   * passes on the unfixed component. Measured: with `g-k:hidden` (the last row)
   * the mutant came back NOT CAUGHT, which is what sent this comment here instead
   * of a green tick.
   *
   * And the mutant has to be the WHOLE pre-fix behaviour. The fix has two halves
   * — a movement threshold in `onPointerMove` and an `engaged` check on release —
   * and each masks the other, so removing one at a time reports NOT CAUGHT for a
   * test that is perfectly good. That is belt and braces, not a dead test; the
   * honest mutation restores both, and it is CAUGHT.
   */
  it('does not reorder when the handle is merely clicked', async () => {
    const h = install(ALL, {
      version: 9,
      groups: [{
        id: 'g-k', name: 'k', collapsed: false,
        projects: ['set-core', 'set-designer', 'hidden'], missing: [],
        order: ['set-core', 'set-designer', 'hidden'],
      }],
      parked: [], parked_missing: [], parked_order: [], ungrouped: [], missing: [],
    })
    const { container } = render(<Fleet />)
    const handle = await waitFor(() => {
      const el = container.querySelector('[data-drag-handle="g-k:set-core"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })

    // A press and a release at the same point: the whole gesture a click is.
    fireEvent.pointerDown(handle, { button: 0, pointerId: 1, clientY: 40 })
    fireEvent.pointerMove(handle, { pointerId: 1, clientY: 40 })
    fireEvent.pointerUp(handle, { pointerId: 1, clientY: 40 })
    await new Promise(r => setTimeout(r, 0))
    expect(h.puts).toHaveLength(0)
  })

  /**
   * The ungrouped block is orderable — the limit this screen used to print.
   *
   * It said "sorrendjük a felderítésé" because a drag there had nothing to
   * persist into. `ungrouped_order` exists now, so both halves are asserted: the
   * move is saved under the key the API reads, and the sentence stating the
   * limit is gone. A stale caveat is worse than no caveat — it teaches the
   * reader that the caveats on this screen are decoration.
   */
  it('reorders the ungrouped block and sends it as `ungrouped_order`', async () => {
    const h = install(fleet([
      project('egy', [agent(1, 'a1')]),
      project('ketto', [agent(2, 'a2')]),
      project('harom', [agent(3, 'a3')]),
    ], { waiting: 0 }), {
      version: 5,
      groups: [], parked: [], parked_missing: [], parked_order: [],
      ungrouped: ['egy', 'ketto', 'harom'], missing: [],
    })
    const { container } = render(<Fleet />)
    const handle = await waitFor(() => {
      const el = container.querySelector('[data-drag-handle="ungrouped:egy"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(container.textContent ?? '').not.toContain('sorrendjük a felderítésé')

    fireEvent.keyDown(handle, { key: 'ArrowDown' })
    await waitFor(() => expect(h.puts).toHaveLength(1))
    const body = h.puts[0].body as { ungrouped_order: string[] }
    expect(body.ungrouped_order).toEqual(['ketto', 'egy', 'harom'])
  })
})

describe('a refused save', () => {
  it('says so, keeps the unsaved change on screen, and offers the reload', async () => {
    const h = install(ALL)
    h.putStatus = 409
    h.putDetail = 'the arrangement changed (yours 7, current 9)'
    const { container } = render(<Fleet />)
    const handle = await waitFor(() => {
      const el = container.querySelector('[data-drag-handle="g-set:set-core"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })

    fireEvent.keyDown(handle, { key: 'ArrowDown' })
    const banner = await waitFor(() => {
      const el = container.querySelector('[data-fleet-conflict]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(banner.textContent).toMatch(/current 9/)
    expect(banner.textContent).toMatch(/not saved/)
    expect(within(banner).getByText(/reload/)).toBeTruthy()

    // The move the user made is still what they see. Reverting it silently and
    // keeping it silently are both worse than saying which one happened.
    const group = container.querySelector('[data-fleet-group="g-set"]') as HTMLElement
    const order = Array.from(group.querySelectorAll('[data-fleet-project]')).map(e => e.getAttribute('data-fleet-project'))
    expect(order.slice(0, 2)).toEqual(['set-designer', 'set-core'])
  })
})

describe('a discovered project the arrangement places nowhere', () => {
  it('gets its own block instead of rendering nowhere', async () => {
    install(fleet([
      project('set-core', [agent(1, 'a1')]),
      project('set-designer'),
      project('hidden'),
      project('felretett'),
      project('maradek'),
      project('sehol', [agent(9, 'a9', 'unknown')]),
    ]))
    const { container } = render(<Fleet />)
    const block = await waitFor(() => {
      const el = container.querySelector('[data-fleet-orphans]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(within(block).getByText('sehol')).toBeTruthy()
    // And it is counted, so the header cannot read calm while it is there.
    expect(container.querySelector('[data-fleet-attention]')!.textContent).toMatch(/1 unknown/)
  })
})

describe('assignment is a control, never a cross-group drag', () => {
  it('moves a project into another group and saves the membership', async () => {
    const h = install(ALL)
    const { container } = render(<Fleet />)
    // Wait for the ARRANGEMENT, not merely for a row with that name: until the
    // arrangement answers there is no group to move out of, and a row captured
    // before it arrives is a node that has since been replaced.
    await waitFor(() => expect(container.querySelector('[data-fleet-group="g-set"]')).toBeTruthy())
    const row = container.querySelector('[data-fleet-project="set-core"]') as HTMLElement

    fireEvent.click(within(row).getByLabelText('set-core — group and park'))
    fireEvent.click(within(row).getByText('→ closed'))

    await waitFor(() => expect(h.puts).toHaveLength(1))
    const body = h.puts[0].body as { groups: { id: string; projects: string[] }[] }
    expect(body.groups[0].projects).not.toContain('set-core')
    expect(body.groups[1].projects).toContain('set-core')
  })

  it('parks a project, and the parked section then counts it', async () => {
    const h = install(ALL)
    const { container } = render(<Fleet />)
    await waitFor(() => expect(container.querySelector('[data-fleet-group="g-set"]')).toBeTruthy())
    const row = container.querySelector('[data-fleet-project="set-core"]') as HTMLElement

    fireEvent.click(within(row).getByLabelText('set-core — group and park'))
    fireEvent.click(within(row).getByText('⇣ park it'))

    await waitFor(() => expect(h.puts).toHaveLength(1))
    expect((h.puts[0].body as { parked: string[] }).parked).toContain('set-core')
  })
})

describe('the arrangement outlives the agents in it', () => {
  it('keeps every project in the column when discovery finds nothing running', async () => {
    install(fleet([
      project('set-core'), project('set-designer'), project('hidden'),
      project('felretett'), project('maradek'),
    ]))
    const { container } = render(<Fleet />)
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-group="g-set"]')).toBeTruthy()
    })
    // A project's position is a statement about the project, not about who
    // happens to be running in it — so an empty fleet must not empty the list.
    expect(container.querySelector('[data-fleet-project="set-core"]')).toBeTruthy()
    expect(screen.getByText(/discovery ran/i)).toBeTruthy()
  })
})

describe('the agent tile and the header must not contradict each other', () => {
  /**
   * Found by looking at the screen, not by a failing check.
   *
   * The header counted a `waiting` agent correctly while the tile beside it read
   * `csendes`, because the tile's last branch was an unconditional fall-through
   * that named one state. A default branch answers for every state invented
   * after it was written, and it answers with the calmest one — so the screen
   * reported quiet for the one agent that was waiting for the reader.
   */
  it('renders a waiting agent as waiting, not as quiet', async () => {
    install(fleet([project('set-core', [
      { ...agent(1, 'a1', 'waiting'), waiting_for: 'approval needed' },
    ])], { waiting: 1 }))
    const { container } = render(<Fleet />)
    await waitFor(() => expect(screen.getByText('a1')).toBeTruthy())

    const right = container.querySelector('[data-fleet-enlarged="1"]') as HTMLElement
    // ⚠ Still Hungarian, on purpose: this string comes from `Fleet.tsx`, which is
    // being edited in parallel and is translated in the follow-up. Asserting the
    // English here before the source says it would be a test that passes on a
    // screen nobody built yet.
    expect(within(right).getByText(/waiting for an answer/)).toBeTruthy()
    expect(within(right).queryByText('csendes')).toBeNull()
    expect(within(right).getByText('approval needed')).toBeTruthy()
  })

  it('prints a state it does not recognise as itself rather than as quiet', async () => {
    install(fleet([project('set-core', [agent(1, 'a1', 'compacting')])]))
    const { container } = render(<Fleet />)
    await waitFor(() => expect(screen.getByText('a1')).toBeTruthy())

    const right = container.querySelector('[data-fleet-enlarged="1"]') as HTMLElement
    expect(within(right).getByText('compacting')).toBeTruthy()
    expect(within(right).queryByText('csendes')).toBeNull()
  })
})
