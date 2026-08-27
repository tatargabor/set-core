/**
 * Installing a module from the screen — task 7.15, and 9.17's unhappy paths are
 * what most of this file is.
 *
 * This is the only act on the fleet screen that **writes into a repository the
 * framework does not own**, and the installer's contract is that nothing it
 * does is silent. A surface can undo that contract in four ways without anyone
 * deciding to, and each has its own case here:
 *
 *  - showing only what was written, so six untouched files vanish;
 *  - computing `changed_nothing` from an empty `written`, which is the
 *    expression that reads as success;
 *  - drawing a refusal as a warning, which is something a reader clicks past;
 *  - saying *wrote* about a preview, which differs from the real thing by one
 *    boolean in the payload.
 *
 * The decisions are asserted as functions and the surface separately, because
 * they fail differently — a rule that is right and never asked answers nothing.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

import FleetInstall from '../../src/components/FleetInstall'
import {
  changeStanding,
  installOffered,
  moduleStanding,
  refusalOf,
  reportHeadline,
  reportTense,
  skipsWithReasons,
} from '../../src/lib/fleetInstall'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('the decisions', () => {
  /**
   * The load-bearing one. `written.length === 0` is a second copy of the
   * producer's rule, and it is the copy that reads as success — a report that
   * never carried the field would be reported as "nothing to do" instead of
   * "we do not know".
   */
  it('reads `changed_nothing`, and treats its absence as unstated', () => {
    expect(changeStanding({ module: 'm', project: 'p', dry_run: true, changed_nothing: true }).kind).toBe('nothing')
    expect(changeStanding({ module: 'm', project: 'p', dry_run: true, written: [], changed_nothing: false }))
      .toEqual({ kind: 'wrote', count: 0 })
    // No field at all: unknown, and an empty `written` must not decide it.
    expect(changeStanding({ module: 'm', project: 'p', dry_run: true, written: [] }).kind).toBe('unstated')
  })

  /**
   * An unexplained skip is the exact silence the installer's contract forbids.
   * Dropping it here would put that silence back one layer up.
   */
  it('gives every skip a sentence, and marks the ones the producer did not explain', () => {
    const out = skipsWithReasons({
      module: 'm', project: 'p', dry_run: true,
      skipped: [{ path: 'a', reason: 'scaffold, already present' }, { path: 'b' }, { path: 'c', reason: '  ' }],
    })
    expect(out).toEqual([
      { path: 'a', reason: 'scaffold, already present', stated: true },
      { path: 'b', reason: 'no reason given', stated: false },
      { path: 'c', reason: 'no reason given', stated: false },
    ])
  })

  it('separates a refusal from a failure, and names which refusal it is', () => {
    expect(refusalOf(404, "no project named 'x' is listed").kind).toBe('not-listed')
    expect(refusalOf(409, "module 'nextjs' is not installed: needs 'starter'").kind).toBe('refused')
    expect(refusalOf(500, 'install failed: boom').kind).toBe('failed')
    // A refusal with no sentence still says something, rather than rendering blank.
    expect(refusalOf(409, null).note).toMatch(/409/)
  })

  it('takes the tense from the report, not from which button was pressed', () => {
    expect(reportTense({ module: 'm', project: 'p', dry_run: true }).verb).toBe('would write')
    expect(reportTense({ module: 'm', project: 'p', dry_run: false }).verb).toBe('wrote')
    expect(reportHeadline({ module: 'm', project: 'p', dry_run: true, changed_nothing: false, written: ['a', 'b'], skipped: [{ path: 'c', reason: 'r' }] }))
      .toBe('would write 2 file(s), 1 left alone')
  })

  /**
   * The narrow reading, on purpose: `partial` means the project already holds
   * some of these files WITHOUT an install record, so nobody has measured what
   * a write would land on.
   */
  it('offers an install only where the report says not connected', () => {
    expect(installOffered({ name: 'a', state: 'not-connected' })).toBe(true)
    expect(installOffered({ name: 'a', state: 'partial' })).toBe(false)
    expect(installOffered({ name: 'a', state: 'connected' })).toBe(false)
    expect(installOffered({ name: 'a', state: 'unknown' })).toBe(false)
  })

  /** An absent report is not a project with no modules. */
  it('says the modules were not measured rather than showing nothing', () => {
    expect(moduleStanding(null).kind).toBe('unmeasured')
    expect(moduleStanding({ unreadable: 'the directory could not be read' }).kind).toBe('unmeasured')
    expect(moduleStanding({ connected: 0, not_connected: 3 }).kind).toBe('unmeasured')
    expect(moduleStanding({ capabilities: [{ name: 'a', state: 'not-connected' }] }))
      .toMatchObject({ kind: 'measured', total: 1, notConnected: 1 })
  })
})

const report = (over: Record<string, unknown> = {}) => ({
  module: 'starter', project: 'demo', dry_run: true,
  written: ['a.md', 'b.md'],
  skipped: [{ path: '.gitignore', reason: 'scaffold, already present' }],
  changed_nothing: false,
  lines: [],
  ...over,
})

const caps = {
  capabilities: [
    { name: 'starter', state: 'not-connected', present: 0, total: 3 },
    { name: 'nextjs', state: 'partial', present: 7, total: 50, reason: 'present without an install record' },
  ],
  connected: 0, partial: 1, not_connected: 1, unknown: 0,
}

function installFetch(answer: { ok: boolean; status?: number; body: unknown }) {
  const stub = vi.fn(() => Promise.resolve({
    ok: answer.ok,
    status: answer.status ?? (answer.ok ? 200 : 409),
    json: () => Promise.resolve(answer.body),
  } as Response))
  vi.stubGlobal('fetch', stub)
  return stub
}

// By its MARKER, not by its words: the strip is marks and numbers now, and a
// test anchored to a sentence breaks every time the sentence is edited.
const openPanel = () => fireEvent.click(document.querySelector('[data-fleet-modules="measured"]')!)

describe('the surface — what the reader is actually shown', () => {
  it('offers a preview on the not-connected module and not on the partial one', () => {
    render(<FleetInstall project="demo" root="/home/x/demo" capabilities={caps} />)
    openPanel()
    expect(document.querySelector('[data-fleet-install-preview="starter"]')).toBeTruthy()
    expect(document.querySelector('[data-fleet-install-preview="nextjs"]')).toBeNull()
    // …and says why the offer is absent, rather than leaving a bare row.
    expect(document.querySelector('[data-fleet-capability-note="nextjs"]')?.textContent)
      .toMatch(/without an install record/)
  })

  /** The first click previews. Nothing is written, and the screen says so. */
  it('previews first, and says the write has not happened', async () => {
    const stub = installFetch({ ok: true, body: report() })
    render(<FleetInstall project="demo" root="/home/x/demo" capabilities={caps} />)
    openPanel()
    fireEvent.click(screen.getByText('preview the install'))
    await waitFor(() => expect(document.querySelector('[data-fleet-install-report="starter"]')).toBeTruthy())
    expect(JSON.parse(String((stub.mock.calls[0][1] as RequestInit).body)).dry_run).toBe(true)
    expect(document.querySelector('[data-fleet-install-tense="preview"]')?.textContent).toMatch(/would write/)
    expect(screen.getByText(/nothing has been written yet/)).toBeTruthy()
  })

  /**
   * 9.17's first unhappy path. An install that skips everything is a GOOD
   * outcome and a misleading screen unless the skips are on it.
   */
  it('shows every skipped file with its reason, never only the writes', async () => {
    installFetch({ ok: true, body: report({
      written: [],
      changed_nothing: true,
      skipped: [
        { path: 'a.md', reason: 'the project edited it' },
        { path: 'b.md', reason: 'once: true — seeded, never rewritten' },
      ],
    }) })
    render(<FleetInstall project="demo" root="/home/x/demo" capabilities={caps} />)
    openPanel()
    fireEvent.click(screen.getByText('preview the install'))
    await waitFor(() => expect(document.querySelector('[data-fleet-install-skipped="2"]')).toBeTruthy())
    expect(screen.getByText(/the project edited it/)).toBeTruthy()
    expect(screen.getByText(/once: true/)).toBeTruthy()
  })

  /** 9.17's second: an install that writes nothing says so in its own words. */
  it('says changed-nothing out loud', async () => {
    installFetch({ ok: true, body: report({ written: [], changed_nothing: true }) })
    render(<FleetInstall project="demo" root="/home/x/demo" capabilities={caps} />)
    openPanel()
    fireEvent.click(screen.getByText('preview the install'))
    await waitFor(() => expect(document.querySelector('[data-fleet-install-changed="nothing"]')).toBeTruthy())
  })

  /**
   * And the case the derived version gets wrong: `written` is empty because the
   * producer said nothing at all. A screen computing it from the array would
   * report the same calm as the case above.
   */
  it('does not turn an unstated outcome into a changed-nothing', async () => {
    const { changed_nothing: _drop, ...noField } = report({ written: [] })
    installFetch({ ok: true, body: noField })
    render(<FleetInstall project="demo" root="/home/x/demo" capabilities={caps} />)
    openPanel()
    fireEvent.click(screen.getByText('preview the install'))
    await waitFor(() => expect(document.querySelector('[data-fleet-install-changed="unstated"]')).toBeTruthy())
    expect(document.querySelector('[data-fleet-install-changed="nothing"]')).toBeNull()
  })

  /**
   * 9.17's third, and the one the task calls a refusal rather than a warning: a
   * missing requirement. Rendered red and terminal — no retry beside it, because
   * what lies past a dismissed warning is a half-installed project nobody chose.
   */
  it('renders a missing requirement as a refusal, not as an offer to proceed', async () => {
    installFetch({ ok: false, status: 409, body: { detail: "module 'nextjs' is not installed: requires 'starter'" } })
    render(<FleetInstall project="demo" root="/home/x/demo" capabilities={caps} />)
    openPanel()
    fireEvent.click(screen.getByText('preview the install'))
    await waitFor(() => expect(document.querySelector('[data-fleet-install-refusal="refused"]')).toBeTruthy())
    const refusal = document.querySelector('[data-fleet-install-refusal="refused"]')!
    expect(refusal.className).toMatch(/text-red-400/)
    expect(refusal.textContent).toMatch(/requires 'starter'/)
    // Nothing to click past it with, and no report claiming anything happened.
    expect(document.querySelector('[data-fleet-install-for-real="starter"]')).toBeNull()
    expect(document.querySelector('[data-fleet-install-report="starter"]')).toBeNull()
  })

  it('separates a project this screen never listed from a refusal about its state', async () => {
    installFetch({ ok: false, status: 404, body: { detail: "no project named 'demo' is listed" } })
    render(<FleetInstall project="demo" root="/home/x/demo" capabilities={caps} />)
    openPanel()
    fireEvent.click(screen.getByText('preview the install'))
    await waitFor(() => expect(document.querySelector('[data-fleet-install-refusal="not-listed"]')).toBeTruthy())
  })

  /**
   * The real write is a second, deliberate click, and its label carries the
   * blast radius — how many files and into which directory.
   */
  it('writes only on a second click, and names what that click will do', async () => {
    const stub = installFetch({ ok: true, body: report() })
    render(<FleetInstall project="demo" root="/home/x/demo" capabilities={caps} />)
    openPanel()
    fireEvent.click(screen.getByText('preview the install'))
    await waitFor(() => expect(document.querySelector('[data-fleet-install-for-real="starter"]')).toBeTruthy())
    const button = document.querySelector('[data-fleet-install-for-real="starter"]')!
    expect(button.textContent).toMatch(/writes 2 file\(s\) into \/home\/x\/demo/)
    expect(stub).toHaveBeenCalledTimes(1)

    installFetch({ ok: true, body: report({ dry_run: false }) })
    fireEvent.click(button)
    await waitFor(() => expect(document.querySelector('[data-fleet-install-tense="done"]')).toBeTruthy())
    expect(document.querySelector('[data-fleet-install-tense="done"]')?.textContent).toMatch(/^wrote /)
    // And it is not offered again — a write already made is not a button.
    expect(document.querySelector('[data-fleet-install-for-real="starter"]')).toBeNull()
  })

  it('says the modules were not measured rather than showing an empty panel', () => {
    render(<FleetInstall project="demo" root="/home/x/demo" capabilities={null} />)
    expect(document.querySelector('[data-fleet-modules="unmeasured"]')).toBeTruthy()
    expect(document.querySelector('[data-fleet-install-panel]')).toBeNull()
  })
})
