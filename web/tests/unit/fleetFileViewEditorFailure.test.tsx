/**
 * When the editor never arrives — B-77, on the SURFACE.
 *
 * `buildFreshness.test.ts` proves the classification; it says nothing about what
 * the panel does with it, and the panel is where the defect was: a rejected
 * lazy import left `loading the editor…` on screen for ever while the only
 * account of the failure was in the browser console.
 *
 * Reported 2026-08-24 by the user, with devtools open beside the screen — which
 * is the tell. A reader who has to open devtools to find out that nothing is
 * loading is looking at a screen that is lying calmly.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

/*
  THE FAILURE, with the wording a browser actually produces.

  Thrown from the lazy step rather than from the `vi.mock` factory, and that is
  a measurement rather than a preference: a factory that throws is reported by
  vitest as its own mocking error, whose message is EMPTY by the time the panel
  sees it — the first run of this file rendered `the editor could not be loaded —`
  with nothing after the dash. What is under test is what the panel does with a
  chunk-load error, and this drives exactly that catch with exactly that error.
*/
vi.mock('@monaco-editor/react', () => ({ loader: { config: () => {} }, default: () => null }))
vi.mock('../../src/lib/monacoLocal', () => ({
  useLocalMonaco: () => {
    throw new Error(
      'Failed to fetch dynamically imported module: http://localhost:7400/assets/index-C41P94E2.js',
    )
  },
}))

import FleetFileView from '../../src/components/FleetFileView'

const ROOT = '/home/x/proj'

/** The listing endpoint, plus whatever `index.html` the case wants served. */
function server(indexHtml: string) {
  return vi.fn((url: string | URL) => {
    const u = String(url)
    if (u.includes('index.html')) {
      return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(indexHtml) } as Response)
    }
    if (u.includes('/files/content')) {
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve({ path: 'a.ts', content: 'x\n', identity: 'id', bytes: 2 }),
      } as Response)
    }
    return Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve({
        root: ROOT, source: 'git', files: ['a.ts'], total: 1, cap: 20000, truncated: false,
      }),
    } as Response)
  })
}

/** This page's own entry script, the thing the served HTML is compared against. */
function pageBuiltWith(src: string) {
  const el = document.createElement('script')
  el.type = 'module'
  el.setAttribute('src', src)
  document.head.appendChild(el)
  return () => el.remove()
}

let removeEntry = () => {}
beforeEach(() => { localStorage.clear() })
afterEach(() => { cleanup(); removeEntry(); removeEntry = () => {}; vi.unstubAllGlobals() })

const view = () => render(<FleetFileView root={ROOT} projectName="proj" onClose={() => {}} />)

/**
 * Open a file, because the editor area only exists once one is open — which is
 * also the state the defect was reported in.
 */
async function openAFile(container: HTMLElement) {
  await waitFor(() => expect(container.querySelector('[data-fleet-file-node="a.ts"]')).toBeTruthy())
  fireEvent.click(container.querySelector('[data-fleet-file-node="a.ts"]')!)
}

describe('the editor could not be loaded', () => {
  it('says so, instead of loading for ever', async () => {
    removeEntry = pageBuiltWith('/assets/index-OLD.js')
    vi.stubGlobal('fetch', server('<script type="module" src="/assets/index-NEW.js"></script>'))
    const { container } = view()
    await openAFile(container)

    await waitFor(() => expect(container.querySelector('[data-fleet-editor-failed]')).toBeTruthy())
    expect(container.textContent, 'the endless loading line survived the failure')
      .not.toContain('loading the editor…')
  })

  /**
   * The reload control is the actionable half, and it is offered only where a
   * reload can actually help — here, where the served page no longer names this
   * page's build.
   */
  it('offers a reload when the build was measured to have been replaced', async () => {
    removeEntry = pageBuiltWith('/assets/index-OLD.js')
    vi.stubGlobal('fetch', server('<script type="module" src="/assets/index-NEW.js"></script>'))
    const { container } = view()
    await openAFile(container)

    await waitFor(() =>
      expect(container.querySelector('[data-fleet-editor-failed="stale"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-editor-reload]')).toBeTruthy()
  })

  /**
   * And NOT where it cannot. The same rejection is what an offline tab produces;
   * a reload button there spends the reader's attention and returns them to the
   * same screen. The underlying error is shown instead.
   */
  it('does not offer one when this page is still the build being served', async () => {
    removeEntry = pageBuiltWith('/assets/index-SAME.js')
    vi.stubGlobal('fetch', server('<script type="module" src="/assets/index-SAME.js"></script>'))
    const { container } = view()
    await openAFile(container)

    await waitFor(() =>
      expect(container.querySelector('[data-fleet-editor-failed="unknown"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-editor-reload]'),
      'a reload was offered for a failure a reload cannot fix').toBeNull()
    expect(container.textContent).toContain('Failed to fetch dynamically imported module')
  })
})
