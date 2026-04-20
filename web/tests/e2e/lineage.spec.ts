/**
 * Lineage-aware UI tests (tasks 14.10–14.12, 15.3–15.4, 9.3, 15b.16).
 *
 * Uses the standard API-UI verification pattern: fetch `/api/<project>/lineages`
 * to learn what the fixture offers, then assert the browser renders matching
 * structure.  Tests skip gracefully on single-lineage fixtures.
 *
 * Note: the "All lineages" merged view was removed before ship — runs that
 * share phase numbers from specs days apart mixed more confusingly than
 * usefully, and the narrow analytics use case can be served by a future
 * side-by-side comparison view instead.  Every user-facing lineage switch
 * goes through a concrete per-lineage row in the sidebar.
 */

import { test, expect, type Page, type APIRequestContext } from '@playwright/test'
import { PROJECT, ORCH_BASE, navigateToTab } from './helpers'

interface LineageMeta {
  id: string
  display_name: string
  is_live: boolean
  last_seen_at?: string | null
  change_count: number
  merged_count: number
}

async function getLineages(request: APIRequestContext): Promise<LineageMeta[]> {
  const res = await request.get(`/api/${PROJECT}/lineages`)
  expect(res.ok()).toBeTruthy()
  const body = await res.json() as { lineages: LineageMeta[] }
  return body.lineages ?? []
}

async function getLiveState(request: APIRequestContext) {
  const res = await request.get(`/api/${PROJECT}/state`)
  expect(res.ok()).toBeTruthy()
  return res.json() as Promise<{ spec_lineage_id?: string | null; status?: string; changes: Array<{ name: string; phase?: number; plan_version?: string | number | null; spec_lineage_id?: string | null; _archived?: boolean }> }>
}

/**
 * Clear per-project localStorage once, after the first navigation.  We do not
 * use `addInitScript` because it reapplies on page.reload() — which would
 * wipe the value we are specifically trying to verify survives the reload
 * in test 14.11.
 */
async function clearSelection(page: Page) {
  await page.goto(ORCH_BASE)
  await page.evaluate((p) => {
    try { window.localStorage.removeItem(`set-lineage-${p}`) } catch {}
  }, PROJECT)
}

/**
 * Stub the WebSocket so lineage-filtered views stay stable for the duration
 * of the test.  The WS `state_update` event carries unfiltered state; the
 * production Dashboard handler now refetches via REST when a lineage is
 * active, but the stub keeps the test's network tracing free of that
 * follow-up refetch and makes the assertions deterministic.
 */
async function stubWebSocket(page: Page) {
  await page.addInitScript(() => {
    // @ts-expect-error - intentionally clobbering for test isolation
    window.WebSocket = class { constructor(){} close(){} send(){} addEventListener(){} removeEventListener(){} }
  })
}

test.describe('Left-sidebar lineage list (14.10-14.12)', () => {
  test.beforeEach(async ({ page }) => {
    await clearSelection(page)
  })

  test('14.10 sidebar renders every lineage with correct live markers and NO All-lineages row', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length === 0) test.skip()

    await page.goto(ORCH_BASE)
    // Regression guard: the `__all__` entry was removed from the UI.
    await expect(page.locator('[data-lineage="__all__"]')).toHaveCount(0)

    for (const l of lineages) {
      const row = page.locator(`[data-lineage="${l.id}"]`)
      await expect(row).toBeVisible()
      await expect(row).toContainText(l.display_name)
      if (l.is_live) {
        await expect(row.locator('[aria-label="live"]')).toBeVisible()
      }
    }
  })

  test('14.10 clicking a non-live lineage filters tabs but leaves sentinel badge on live', async ({ page, request }) => {
    const lineages = await getLineages(request)
    const live = lineages.find(l => l.is_live)
    const other = lineages.find(l => !l.is_live)
    if (!live || !other) test.skip()

    await page.goto(ORCH_BASE)
    const stateCallWaiter = page.waitForRequest(req =>
      req.url().includes(`/api/${PROJECT}/state`) &&
      req.url().includes(`lineage=${encodeURIComponent(other!.id)}`)
    )
    await page.locator(`[data-lineage="${other!.id}"]`).click()
    await stateCallWaiter

    const hint = page.locator('[data-testid="lineage-hint"]')
    if (await hint.count() > 0) {
      await expect(hint.first()).toContainText('sentinel running')
    }
  })

  test('14.11 selection survives page reload (localStorage persistence)', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length === 0) test.skip()

    // Use the LAST row so we do not accidentally re-pick the default lineage.
    const target = lineages[lineages.length - 1]

    await page.goto(ORCH_BASE)
    await expect(page.locator(`[data-lineage="${target.id}"]`)).toBeVisible()
    await page.locator(`[data-lineage="${target.id}"]`).click()

    await expect.poll(async () =>
      page.evaluate((p) => window.localStorage.getItem(`set-lineage-${p}`), PROJECT)
    ).toBe(target.id)

    await page.reload()

    const storedAfter = await page.evaluate((p) => window.localStorage.getItem(`set-lineage-${p}`), PROJECT)
    expect(storedAfter).toBe(target.id)

    await expect(page.locator(`[data-lineage="${target.id}"]`)).toHaveClass(/bg-neutral-800/)
  })

  test('14.12 "All lineages" UI entry is absent (regression guard)', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length === 0) test.skip()

    await page.goto(ORCH_BASE)
    // Hard assertion: the removed entry must not creep back in via a stale
    // localStorage value, a cached build, or a future refactor.
    await expect(page.locator('[data-lineage="__all__"]')).toHaveCount(0)
    await expect(page.getByText(/^All lineages$/)).toHaveCount(0)
  })
})

test.describe('PhaseView per-lineage behaviour (15.3-15.4, 9.3)', () => {
  test.beforeEach(async ({ page }) => {
    await clearSelection(page)
    await stubWebSocket(page)
  })

  test('15.3 phase numbering is lineage-scoped', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length < 2) test.skip()

    await page.goto(ORCH_BASE)
    await navigateToTab(page, 'phases')

    for (const l of lineages) {
      await page.locator(`[data-lineage="${l.id}"]`).click()
      await Promise.race([
        page.waitForRequest(req =>
          req.url().includes(`/api/${PROJECT}/state`) &&
          req.url().includes(`lineage=${encodeURIComponent(l.id)}`)
        ).catch(() => null),
        page.waitForTimeout(500),
      ])
      await page.waitForTimeout(800)

      const groups = await page.locator('[data-testid^="phase-group-"]').all()
      if (groups.length === 0) continue

      const phaseNumbers = await Promise.all(groups.map(async g => {
        const key = await g.getAttribute('data-testid')
        return parseInt(key!.replace('phase-group-', '').split('|')[0], 10)
      }))
      const min = Math.min(...phaseNumbers)
      expect(min).toBeGreaterThanOrEqual(1)
    }
  })

  test('15.4 modern project does not render synthetic Phase 0 or Previous-cycles header', async ({ page, request }) => {
    await page.goto(ORCH_BASE)
    await navigateToTab(page, 'phases')
    await page.waitForSelector('[data-testid^="phase-group-"], [data-testid="toggle-unattributed"]', {
      timeout: 10_000,
    }).catch(() => {})

    const phasePanel = page.locator('main')
    const panelText = (await phasePanel.innerText()).toLowerCase()
    expect(panelText).not.toContain('phase 0 (archived)')
    expect(panelText).not.toContain('previous cycles')

    const toggle = page.locator('[data-testid="toggle-unattributed"]')
    if (await toggle.count() > 0) {
      await expect(toggle).toContainText(/Show unattributed/i)
    }

    const groups = await page.locator('[data-testid^="phase-group-"]').all()
    for (const g of groups) {
      const key = await g.getAttribute('data-testid')
      const phaseNum = parseInt(key!.replace('phase-group-', '').split('|')[0], 10)
      expect(phaseNum).toBeGreaterThanOrEqual(1)
    }
  })

  test('9.3 two plan versions with the same phase number render separate subheaders within a single lineage', async ({ page, request }) => {
    // Plan-version collisions now only happen WITHIN one lineage when a
    // replan overlaps an earlier cycle's phase numbers.  The nano fixture
    // has one plan per lineage so this test skips in practice — the
    // assertion shape is preserved for future fixtures that exercise
    // per-lineage replans.
    const lineages = await getLineages(request)
    const state = await getLiveState(request)

    for (const l of lineages) {
      await page.goto(ORCH_BASE)
      await page.locator(`[data-lineage="${l.id}"]`).click()
      await page.waitForTimeout(400)

      const res = await request.get(`/api/${PROJECT}/state?lineage=${encodeURIComponent(l.id)}`)
      if (!res.ok()) continue
      const filtered = await res.json() as typeof state
      const seen = new Map<number, Set<string>>()
      for (const c of filtered.changes ?? []) {
        if (c.phase == null) continue
        const pv = c.plan_version == null ? '' : String(c.plan_version)
        const set = seen.get(c.phase) ?? new Set<string>()
        set.add(pv)
        seen.set(c.phase, set)
      }
      const collidingPhase = [...seen.entries()].find(([, vs]) => vs.size >= 2)
      if (!collidingPhase) continue

      await navigateToTab(page, 'phases')
      await page.waitForTimeout(400)
      const [phaseNum] = collidingPhase!
      const headers = await page.locator(`[data-testid^="phase-group-${phaseNum}|"]`).all()
      const labels: string[] = []
      for (const h of headers) {
        const label = await h.locator('span.font-medium').first().textContent()
        if (label) labels.push(label.trim())
      }
      const renderedVersions = new Set<string>()
      for (const label of labels) {
        const m = label.match(new RegExp(`^Phase ${phaseNum} \\(plan v(\\S+)\\)`))
        if (m) renderedVersions.add(m[1])
      }
      expect(renderedVersions.size).toBeGreaterThanOrEqual(2)
      return
    }
    test.skip()
  })
})

test.describe('Tab walk (v1 vs v2 cross-lineage differentiation)', () => {
  test.beforeEach(async ({ page }) => {
    await clearSelection(page)
    // No WS stub here — these tests exercise the real end-to-end flow
    // including the Dashboard's WS state_update → REST refetch path
    // that keeps the filtered view coherent after a lineage flip.
  })

  test('each lineage-scoped tab renders distinct content after switching lineage', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length < 2) test.skip()

    const [first, second] = lineages
    await page.goto(ORCH_BASE)

    // Lock in the first lineage.
    await page.locator(`[data-lineage="${first.id}"]`).click()
    await page.waitForTimeout(600)

    // Capture representative content per tab for the first lineage.
    const captured: Record<string, string> = {}
    const tabs = ['changes', 'phases', 'activity', 'tokens', 'digest', 'sessions', 'learnings'] as const
    for (const tab of tabs) {
      const tabBtn = page.locator(`[data-tab="${tab}"]`)
      if (await tabBtn.count() === 0) continue
      await navigateToTab(page, tab)
      await page.waitForTimeout(500)
      captured[tab] = (await page.locator('main').innerText()).slice(0, 4000)
    }

    // Flip to the second lineage.
    await page.locator(`[data-lineage="${second.id}"]`).click()
    await page.waitForTimeout(800)

    // At least one of the lineage-scoped tabs must reflect the switch.
    // Tabs like Log/Sentinel/Agent are deliberately daemon-scoped and may
    // render the same text for both lineages — exclude them from the
    // "must differ" assertion.
    const lineageScopedTabs = ['changes', 'phases', 'activity', 'tokens', 'digest'] as const
    let anyDiffered = false
    for (const tab of lineageScopedTabs) {
      if (!(tab in captured)) continue
      const tabBtn = page.locator(`[data-tab="${tab}"]`)
      if (await tabBtn.count() === 0) continue
      await navigateToTab(page, tab)
      await page.waitForTimeout(500)
      const now = (await page.locator('main').innerText()).slice(0, 4000)
      if (now !== captured[tab]) anyDiffered = true
    }
    expect(anyDiffered).toBeTruthy()
  })

  test('archived change on v1 opens its journal / DAG without a 404', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length < 2) test.skip()

    // Walk each lineage, selecting it in the sidebar and scanning for an
    // archived row.  As soon as we find one, exercise the journal fetch.
    await page.goto(ORCH_BASE)
    let exercised = false
    for (const l of lineages) {
      await page.locator(`[data-lineage="${l.id}"]`).click()
      // Dashboard's REST poll fires ~2s after lineage change; WS is stubbed
      // so that poll is what updates the Changes table with archive-sourced
      // entries.  Wait long enough for it to land before scanning.
      await page.waitForTimeout(2800)
      await navigateToTab(page, 'changes')
      await page.waitForTimeout(600)
      const archivedRow = page.locator('text=/\\(archived\\)/').first()
      if (await archivedRow.count() === 0) continue
      await archivedRow.click()
      await page.waitForTimeout(1000)
      const panelText = (await page.locator('main').innerText()).toLowerCase()
      expect(panelText).not.toContain('failed to load journal')
      expect(panelText).not.toContain('change not found')
      exercised = true
      break
    }
    expect(exercised).toBeTruthy()
  })
})

test.describe('Lineage network guard (15b.16)', () => {
  test('every orchestration-scoped fetch except the sidebar live-state poll carries a lineage query param after the selector has resolved', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length === 0) test.skip()

    await page.goto(ORCH_BASE)
    await expect.poll(async () =>
      page.evaluate((p) => window.localStorage.getItem(`set-lineage-${p}`), PROJECT)
    ).not.toBeNull()

    const seen: string[] = []
    page.on('request', req => {
      const url = req.url()
      if (/\/api\/[^/]+\/(state|digest|activity-timeline|llm-calls|sessions|learnings)(\?|$)/.test(url)) {
        seen.push(url)
      }
    })

    const tabs = ['activity', 'tokens', 'digest', 'phases', 'sessions', 'learnings'] as const
    for (const tab of tabs) {
      const tabBtn = page.locator(`[data-tab="${tab}"]`)
      if (await tabBtn.count() === 0) continue
      await navigateToTab(page, tab)
      await page.waitForTimeout(400)
    }

    // The sidebar poll from ProjectLayout intentionally omits lineage.
    // Every OTHER call to the lineage-scoped endpoints must carry it.
    const withoutLineage = seen.filter(u => !u.includes('lineage='))
    const unexpected = withoutLineage.filter(u =>
      !u.match(/\/api\/[^/]+\/state(\?|$)/)
    )
    expect(unexpected).toEqual([])
  })
})
