/**
 * The dashboard's screen inventory, shared by the layout probe and the design-review capture.
 *
 * It lives in one file because the two passes must cover *the same* set. A capture that walks
 * more screens than the probe measured produces images nobody has a metric for; a probe that
 * walks more than the capture produces numbers nobody can look at. Either way the two halves
 * stop being about one subject, and the disagreement is invisible — both runs succeed.
 *
 * Tab lists are **discovered from the DOM**, never hard-coded. The orchestration tabs depend on
 * what a run produced, and the Project Status tabs come from the project's own contract — a
 * literal list here would silently under-cover exactly the projects that have the most to show,
 * and it would report full coverage while doing it.
 */
import type { Page } from '@playwright/test'

export const PROJECT = process.env.E2E_PROJECT!

export interface Screen {
  /** Stable file-name-safe id. */
  id: string
  /** Path to navigate to, relative to baseURL. */
  path: string
  /** Optional: after landing, click this tab and wait for it. */
  tab?: { attr: 'data-tab' | 'data-status-tab'; value: string }
  /** Human label for reports. */
  label: string
  /**
   * A selector that must exist before this screen is measured or captured.
   *
   * Not optional politeness — the Project Status page fetches through the project's own
   * command and that took **3.8 s** when measured, so a fixed settle photographed an empty
   * page and the tab discovery returned zero. Zero tabs and a clean screen are indistinguishable
   * from a screen with nothing wrong, which is the direction that costs.
   */
  waitFor?: string
}

/** Routes that exist regardless of what any project contains. */
export const STATIC_SCREENS: Screen[] = [
  { id: 'manager', path: '/', label: 'Manager — project list' },
  { id: 'issues-global', path: '/issues', label: 'Global issues' },
  { id: 'project-status', path: `/p/${PROJECT}/status`, label: 'Project Status (landing)', waitFor: '[data-status-tab]' },
  { id: 'orch', path: `/p/${PROJECT}/orch`, label: 'Orchestration (landing)', waitFor: '[data-tab]' },
  { id: 'worktrees', path: `/p/${PROJECT}/orch/worktrees`, label: 'Worktrees' },
  { id: 'issues-project', path: `/p/${PROJECT}/issues`, label: 'Project issues' },
  { id: 'memory', path: `/p/${PROJECT}/memory`, label: 'Memory' },
  { id: 'settings', path: `/p/${PROJECT}/settings`, label: 'Settings' },
]

/**
 * Read the tab strip out of the live DOM.
 *
 * Returns `[]` when the strip is absent, and the caller treats that as "no tabs", not as an
 * error — a project without a status contract legitimately has none. What the caller must NOT
 * do is treat `[]` as coverage: an empty list beside a zero finding count is the shape error
 * this repo keeps finding, so the run log states the discovered count per screen.
 */
export async function discoverTabs(
  page: Page,
  attr: 'data-tab' | 'data-status-tab',
): Promise<string[]> {
  return page.$$eval(`[${attr}]`, (els, a) =>
    els.map((e) => e.getAttribute(a as string)).filter((v): v is string => !!v),
    attr,
  ).catch(() => [])
}

/**
 * Settle: let data land and layout stop moving before anything is measured or captured.
 *
 * The `networkidle` wait carries an explicit short timeout, and the reason is worth keeping.
 * This dashboard holds a live connection and polls, so the network is *never* idle — the
 * default 30 s wait therefore expired on every screen and the caught rejection hid it. The
 * first run spent all its time in a wait that could not succeed, and looked like a slow probe
 * rather than a broken one.
 *
 * So: ask for idle briefly, accept not getting it, and rely on the fixed settle instead. A
 * condition that can never be met is not a wait, it is a sleep with a misleading name.
 */
export async function settle(page: Page, waitFor?: string): Promise<boolean> {
  let arrived = true
  if (waitFor) {
    // 25 s, because the underlying command's own declared budget is 30 s. A wait shorter than
    // what the producer is allowed to take measures the network, not the screen.
    arrived = await page
      .waitForSelector(waitFor, { timeout: 25_000, state: 'attached' })
      .then(() => true)
      .catch(() => false)
  }
  await page.waitForLoadState('networkidle', { timeout: 1500 }).catch(() => {})
  await page.waitForTimeout(500)
  return arrived
}
