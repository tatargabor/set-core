/**
 * Which provider an agent starts on, and which one it runs on — tasks 8.1–8.6.
 *
 * Asserted as functions AND through the rendered screen, for the reason the
 * sibling start-locations file gives: a rule that is right and never asked
 * answers nothing, which is the shape that let a fully-green change ship an
 * empty panel.
 *
 * The load-bearing assertions here are the three that separate facts a layout
 * would happily merge: an unrecorded provider from the default, a provider with
 * no credential from a provider that does not exist, and a project-override
 * credential from an ordinary one. Each of those pairs renders identically if
 * nobody insists otherwise, and in each pair the wrong half is a statement
 * about whose account is being billed.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'
import {
  fetchProviderCatalogue,
  levelLabel,
  modelsFor,
  offerableProviders,
  previewResolution,
  providerMark,
  type ProviderCatalogue,
} from '../../src/lib/fleetProviders'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const CATALOGUE: ProviderCatalogue = {
  default_provider: 'anthropic',
  default_model: 'opus',
  providers: [
    { name: 'anthropic', models: ['opus', 'sonnet'], default_model: 'opus',
      requires_credential: false, configured: false, usable: true },
    { name: 'glm', models: ['glm-4.6'], default_model: 'glm-4.6',
      requires_credential: true, configured: true, usable: true },
    { name: 'needs-key', models: ['m1'], default_model: null,
      requires_credential: true, configured: false, usable: false },
  ],
}

describe('the decisions', () => {
  it('offers an unusable provider WITH THE REASON rather than omitting it', () => {
    const offered = offerableProviders(CATALOGUE)
    expect(offered.map(p => p.name)).toEqual(['anthropic', 'glm', 'needs-key'])
    // The one that cannot be used says why. Dropping it would make a declared
    // provider and a non-existent one look identical, and a reader who had just
    // configured it would conclude the screen was broken.
    expect(offered[2].disabledReason).toMatch(/no credential/)
    expect(offered[1].disabledReason).toBeNull()
  })

  it('does not report a provider that needs no credential as unconfigured', () => {
    // `configured: false` on a login-based provider is true and irrelevant. The
    // reason it must not become "unusable" is that the reader would go looking
    // for a key nobody needs.
    expect(offerableProviders(CATALOGUE)[0].disabledReason).toBeNull()
  })

  it('offers a model only from the chosen provider’s own catalogue', () => {
    expect(modelsFor(CATALOGUE, 'glm')).toEqual(['glm-4.6'])
    // No provider chosen means no model list — a global one would be exactly
    // the cross-provider combination the resolver refuses everywhere else.
    expect(modelsFor(CATALOGUE, null)).toEqual([])
  })

  it('carries the machine default model only to the machine default PROVIDER', () => {
    // The correction taken during implementation, held on this side too so the
    // preview and the resolver cannot disagree.
    expect(previewResolution(CATALOGUE, null, null))
      .toEqual({ provider: 'anthropic', model: 'opus',
                 providerLevel: 'machine-default', modelLevel: 'machine-default' })
    expect(previewResolution(CATALOGUE, 'glm', null))
      .toEqual({ provider: 'glm', model: 'glm-4.6',
                 providerLevel: 'request', modelLevel: 'provider-default' })
  })

  it('never previews a PROJECT level, because the screen cannot see one', () => {
    // The override lives in a file only the owner reads. A preview claiming to
    // know it would invent the one level that decides whose account pays.
    for (const [p, m] of [[null, null], ['glm', null], ['glm', 'glm-4.6']] as const) {
      const preview = previewResolution(CATALOGUE, p, m)
      expect(preview.providerLevel).not.toBe('project')
      expect(preview.modelLevel).not.toBe('project')
    }
  })

  it('reads an unrecorded provider as a GAP, never as the default', () => {
    const mark = providerMark({ recorded: false, provider: null, model: null, provenance: {} })
    expect(mark.kind).toBe('unrecorded')
    expect(mark.text).toMatch(/unrecorded/)
    // The machine default's name must not appear anywhere in it.
    expect(mark.text).not.toMatch(/anthropic/)
    expect(providerMark(undefined).kind).toBe('unrecorded')
  })

  it('marks a credential that came from a project override', () => {
    const mark = providerMark({
      recorded: true, provider: 'glm', model: 'glm-4.6',
      provenance: { provider: 'project', model: 'project', credential: 'project' },
    })
    expect(mark.kind).toBe('override')
    expect(mark.text).toMatch(/project key/)
  })

  it('states the frame even for an ordinary agent', () => {
    const mark = providerMark({
      recorded: true, provider: 'glm', model: 'glm-4.6',
      provenance: { provider: 'request', model: 'request', credential: 'machine-default' },
    })
    expect(mark.kind).toBe('plain')
    expect(mark.text).toBe('glm · glm-4.6')
    expect(mark.title).toMatch(/machine default/)
  })

  it('names each level in words a person reads', () => {
    expect(levelLabel('project')).toBe('project override')
    expect(levelLabel(undefined)).toBe('unknown')
  })
})

// --------------------------------------------------------------------------- //
// the form and the tile
// --------------------------------------------------------------------------- //

const PROJECT = { name: 'proj', root: '/repo', agents: [], sources: ['registry'], archived: false }

function stubFleet(opts: {
  catalogue?: ProviderCatalogue | 'unreadable'
  agents?: any[]
  onStart?: (body: any) => void
} = {}) {
  const started: any[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url)
    if (u === '/api/fleet/owner') {
      return { ok: true, json: async () => ({ available: true, held: 0 }) } as any
    }
    if (u.startsWith('/api/fleet/providers')) {
      if (opts.catalogue === 'unreadable') return { ok: false, status: 503, json: async () => ({}) } as any
      return { ok: true, json: async () => (opts.catalogue ?? CATALOGUE) } as any
    }
    if (u.includes('/worktrees')) {
      return { ok: true, json: async () => ({ project: 'proj', root: '/repo', locations: [] }) } as any
    }
    if (u === '/api/fleet/agents' && init?.method === 'POST') {
      const body = JSON.parse(String(init.body))
      started.push(body)
      opts.onStart?.(body)
      return { ok: true, json: async () => ({ label: body.label }) } as any
    }
    if (u.startsWith('/api/fleet/agents')) {
      // ⚠ `agents` at the top level is a COUNT, not a list — the list lives on
      // each project. Getting this wrong does not fail as a type error; React
      // tries to render the array's objects as children and the whole page
      // throws, which reads like a defect in whatever was added last.
      const rows = opts.agents ?? []
      return {
        ok: true,
        json: async () => ({
          agents: rows.length,
          working: 0, unknown: 0, waiting: 0, quiet: rows.length,
          projects: [{ ...PROJECT, agents: rows }],
          measured_at: new Date().toISOString(),
          quiet_means: 'no outstanding tool call',
        }),
      } as any
    }
    return { ok: true, json: async () => ({}) } as any
  }))
  return started
}

async function openStartForm() {
  render(<Fleet />)
  const button = await waitFor(() => {
    const el = document.querySelector('[data-fleet-start="offer"]')
    if (!el) throw new Error('no start control yet')
    return el as HTMLElement
  })
  fireEvent.click(button)
}

function agentRow(over: Record<string, any> = {}) {
  return {
    pid: 4243, name: 'a1', project: 'proj', branch: 'main', session_id: 's1',
    binding_confirmed: true, sources: ['proc'], kind: 'agent', state: 'working',
    tool: null, tool_elapsed_seconds: null, other_tools: [],
    last_movement_seconds: 3, unknown_reason: null, ...over,
  }
}

describe('the form', () => {
  it('offers every declared provider and DISABLES the unusable one', async () => {
    stubFleet()
    await openStartForm()

    const select = await waitFor(() => {
      const el = document.querySelector('[data-fleet-start="provider"]') as HTMLSelectElement | null
      if (!el) throw new Error('no provider select yet')
      return el
    })
    const options = Array.from(select.options)
    expect(options.map(o => o.value)).toEqual(['', 'anthropic', 'glm', 'needs-key'])
    // Asserted on the rendered STATE, not on the wording: `disabled` is what a
    // reader cannot click, and the reason travels beside it.
    expect(options.find(o => o.value === 'needs-key')!.disabled).toBe(true)
    expect(options.find(o => o.value === 'glm')!.disabled).toBe(false)
  })

  it('shows the resolved frame and the level that supplies each half', async () => {
    stubFleet()
    await openStartForm()

    const resolved = await waitFor(() => {
      const el = document.querySelector('[data-fleet-start="resolved"]')
      if (!el) throw new Error('no preview yet')
      return el as HTMLElement
    })
    expect(resolved.textContent).toContain('anthropic')
    expect(resolved.textContent).toContain('machine default')

    const select = document.querySelector('[data-fleet-start="provider"]') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'glm' } })
    await waitFor(() => {
      expect(document.querySelector('[data-fleet-start="resolved"]')!.textContent).toContain('glm-4.6')
    })
    expect(document.querySelector('[data-fleet-start="resolved"]')!.textContent).toContain('this start')
  })

  it('sends only what was CHOSEN, never the previewed default', async () => {
    // Sending the preview would record `request` provenance for a level nobody
    // selected — which then reads on the screen as a deliberate choice.
    const started = stubFleet()
    await openStartForm()
    await waitFor(() => {
      if (!document.querySelector('[data-fleet-start="provider"]')) throw new Error('not yet')
    })
    fireEvent.submit(document.querySelector('[data-fleet-start="form"]') as HTMLFormElement)
    await waitFor(() => expect(started.length).toBe(1))
    expect(started[0].provider).toBeUndefined()
    expect(started[0].model).toBeUndefined()
  })

  it('carries the chosen provider and model to the start request', async () => {
    const started = stubFleet()
    await openStartForm()
    const select = await waitFor(() => {
      const el = document.querySelector('[data-fleet-start="provider"]') as HTMLSelectElement | null
      if (!el) throw new Error('not yet')
      return el
    })
    fireEvent.change(select, { target: { value: 'glm' } })
    const models = await waitFor(() => {
      const el = document.querySelector('[data-fleet-start="model"]') as HTMLSelectElement | null
      if (!el) throw new Error('no model select yet')
      return el
    })
    fireEvent.change(models, { target: { value: 'glm-4.6' } })
    fireEvent.submit(document.querySelector('[data-fleet-start="form"]') as HTMLFormElement)

    await waitFor(() => expect(started.length).toBe(1))
    expect(started[0].provider).toBe('glm')
    expect(started[0].model).toBe('glm-4.6')
  })

  it('says the catalogue could not be read rather than showing no providers', async () => {
    // An empty select and a failed request are different facts, and the second
    // one silently wearing the first one's clothes is this repository's
    // most-repeated defect.
    stubFleet({ catalogue: 'unreadable' })
    await openStartForm()
    await waitFor(() => {
      const el = document.querySelector('[data-fleet-start="catalogue-unread"]')
      if (!el) throw new Error('no notice yet')
      expect(el.textContent).toMatch(/could not be read/)
    })
    expect(document.querySelector('[data-fleet-start="provider"]')).toBeNull()
  })
})

describe('the tile', () => {
  it('renders an unrecorded provider as unrecorded, distinctly', async () => {
    stubFleet({ agents: [agentRow({ provider: { recorded: false, provider: null, model: null, provenance: {} } })] })
    render(<Fleet />)
    const mark = await waitFor(() => {
      const el = document.querySelector('[data-fleet-provider]')
      if (!el) throw new Error('no provider marker yet')
      return el as HTMLElement
    })
    expect(mark.getAttribute('data-fleet-provider')).toBe('unrecorded')
    expect(mark.textContent).toMatch(/unrecorded/)
    // ⚠ NOT amber, and this assertion was REVERSED after looking at the live
    // screen. Every agent on a running machine is unrecorded until it is
    // started through this, so amber here meant three tiles out of three
    // shouting in the colour reserved for "something is wrong" — and the one
    // case that genuinely needs it could no longer stand out. Distinct from a
    // named provider is the requirement; alarming is not.
    expect(mark.className).not.toContain('amber')
    expect(mark.textContent).not.toMatch(/⚠/)
  })

  it('marks a project-override credential where the agent is listed', async () => {
    stubFleet({ agents: [agentRow({
      provider: { recorded: true, provider: 'glm', model: 'glm-4.6',
                  provenance: { provider: 'project', model: 'project', credential: 'project' } },
    })] })
    render(<Fleet />)
    const mark = await waitFor(() => {
      const el = document.querySelector('[data-fleet-provider]')
      if (!el) throw new Error('no provider marker yet')
      return el as HTMLElement
    })
    expect(mark.getAttribute('data-fleet-provider')).toBe('override')
    expect(mark.textContent).toMatch(/project key/)
    // The ONLY case that spends this screen's alarm colour.
    expect(mark.className).toContain('amber')
    expect(mark.textContent).toMatch(/⚠/)
  })

  it('states an ordinary agent’s provider without shouting about it', async () => {
    stubFleet({ agents: [agentRow({
      provider: { recorded: true, provider: 'glm', model: 'glm-4.6',
                  provenance: { credential: 'machine-default' } },
    })] })
    render(<Fleet />)
    const mark = await waitFor(() => {
      const el = document.querySelector('[data-fleet-provider]')
      if (!el) throw new Error('no provider marker yet')
      return el as HTMLElement
    })
    expect(mark.getAttribute('data-fleet-provider')).toBe('plain')
    // Amber is this screen's "look at this" colour and must not be spent here.
    expect(mark.className).not.toContain('amber')
    // …and the three kinds must not collapse into one look. A test that only
    // said "not amber" would pass on a screen where unrecorded and running-on-
    // glm render identically, which is the distinction 8.5 exists for.
    const unrecorded = providerMark(undefined)
    expect(unrecorded.text).not.toBe(providerMark({
      recorded: true, provider: 'glm', model: 'glm-4.6', provenance: {},
    }).text)
  })
})

// --------------------------------------------------------------------------- //
// The project override — found by LOOKING at the running screen, not by a test
// --------------------------------------------------------------------------- //

describe('the project override the browser cannot see', () => {
  it('takes the SERVER’s resolution when nothing is chosen', () => {
    // Before this, the preview said `anthropic · opus (machine default)` for a
    // project whose override sends it to glm. Not "unknown" — a confident,
    // plausible, wrong statement about which account the start would spend
    // against, in the one place this change exists to make visible.
    const withOverride: ProviderCatalogue = {
      ...CATALOGUE,
      resolved: { provider: 'glm', model: 'glm-4.5-air',
                  provenance: { provider: 'project', model: 'project', credential: 'machine-default' } },
    }
    expect(previewResolution(withOverride, null, null)).toEqual({
      provider: 'glm', model: 'glm-4.5-air',
      providerLevel: 'project', modelLevel: 'project',
    })
  })

  it('lets an explicit choice outrank the server’s default', () => {
    const withOverride: ProviderCatalogue = {
      ...CATALOGUE,
      resolved: { provider: 'glm', model: 'glm-4.5-air', provenance: { provider: 'project' } },
    }
    expect(previewResolution(withOverride, 'anthropic', null).provider).toBe('anthropic')
    expect(previewResolution(withOverride, 'anthropic', null).providerLevel).toBe('request')
  })

  it('falls back to the local derivation when the server resolved nothing', () => {
    // A configuration too incomplete to resolve must not empty the preview —
    // the catalogue is still listable, and a gap is rendered as one.
    expect(previewResolution({ ...CATALOGUE, resolved: null }, null, null).provider)
      .toBe('anthropic')
  })

  it('asks the catalogue about THIS project', async () => {
    const seen: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      seen.push(String(url))
      return { ok: true, json: async () => CATALOGUE } as any
    }))
    await fetchProviderCatalogue('set-core')
    expect(seen[0]).toBe('/api/fleet/providers?project=set-core')
  })
})
