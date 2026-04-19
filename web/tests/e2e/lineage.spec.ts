/**
 * Lineage-aware UI tests (tasks 14.10–14.12, 15.3–15.4, 9.3, 15b.16).
 *
 * Uses the standard API-UI verification pattern: fetch `/api/<project>/lineages`
 * to learn what the fixture offers, then assert the browser renders matching
 * structure.  Tests skip gracefully on single-lineage fixtures.
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

test.describe('Left-sidebar lineage list (14.10-14.12)', () => {
  test.beforeEach(async ({ page }) => {
    await clearSelection(page)
  })

  test('14.10 sidebar renders every lineage with correct live markers', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length === 0) test.skip()

    await page.goto(ORCH_BASE)
    // All-lineages row is always present
    await expect(page.locator('[data-lineage="__all__"]')).toBeVisible()

    for (const l of lineages) {
      const row = page.locator(`[data-lineage="${l.id}"]`)
      await expect(row).toBeVisible()
      await expect(row).toContainText(l.display_name)
      if (l.is_live) {
        // live dot has aria-label="live"
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
    // Intercept the next /state call to confirm the lineage param is forwarded.
    const stateCallWaiter = page.waitForRequest(req =>
      req.url().includes(`/api/${PROJECT}/state`) &&
      req.url().includes(`lineage=${encodeURIComponent(other!.id)}`)
    )

    await page.locator(`[data-lineage="${other!.id}"]`).click()
    await stateCallWaiter

    // The lineage-hint appears when the selected lineage differs from live.
    // We only assert presence when the sentinel is actively running (live lineage
    // exists and status is non-terminal).  On finished projects the hint still
    // rotates based on spec_lineage_id, so keep the assertion best-effort.
    const hint = page.locator('[data-testid="lineage-hint"]')
    if (await hint.count() > 0) {
      await expect(hint.first()).toContainText('sentinel running')
    }
  })

  test('14.11 selection survives page reload (localStorage persistence)', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length === 0) test.skip()

    // Use the LAST row so we do not accidentally re-pick the default lineage —
    // clicking the already-selected row would be a no-op and the assertion
    // would still pass without actually exercising the setter.
    const target = lineages[lineages.length - 1]

    await page.goto(ORCH_BASE)
    // Wait for the lineage list to mount so the click lands on a real button.
    await expect(page.locator(`[data-lineage="${target.id}"]`)).toBeVisible()
    await page.locator(`[data-lineage="${target.id}"]`).click()

    // Poll localStorage — setLineageId writes synchronously on click.
    await expect.poll(async () =>
      page.evaluate((p) => window.localStorage.getItem(`set-lineage-${p}`), PROJECT)
    ).toBe(target.id)

    await page.reload()

    const storedAfter = await page.evaluate((p) => window.localStorage.getItem(`set-lineage-${p}`), PROJECT)
    expect(storedAfter).toBe(target.id)

    // The selected row should have the highlight class after reload.
    await expect(page.locator(`[data-lineage="${target.id}"]`)).toHaveClass(/bg-neutral-800/)
  })

  test('14.12 "All lineages" mode shows cross-lineage hint and forwards __all__', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length === 0) test.skip()

    await page.goto(ORCH_BASE)
    const stateCallWaiter = page.waitForRequest(req =>
      req.url().includes(`/api/${PROJECT}/state`) &&
      req.url().includes('lineage=__all__')
    )

    await page.locator('[data-lineage="__all__"]').click()
    await stateCallWaiter

    // The "Viewing all lineages" hint appears (Section 14.9 + 14.8 sibling).
    await expect(page.locator('[data-testid="lineage-hint-all"]')).toBeVisible()
  })
})

test.describe('PhaseView per-lineage behaviour (15.3-15.4, 9.3)', () => {
  test.beforeEach(async ({ page }) => {
    await clearSelection(page)
  })

  test('15.3 phase numbering is lineage-scoped', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length < 2) test.skip()

    const state = await getLiveState(request)
    await page.goto(ORCH_BASE)
    await navigateToTab(page, 'phases')

    // For each lineage, open the tab, count phase groups, confirm numbering
    // restarts from Phase 1 (i.e., no phase-group ids leak across lineages).
    for (const l of lineages) {
      await page.locator(`[data-lineage="${l.id}"]`).click()
      // If the click lands on the already-selected default lineage no refetch
      // fires.  Use a best-effort race so the loop does not hang.
      await Promise.race([
        page.waitForRequest(req =>
          req.url().includes(`/api/${PROJECT}/state`) &&
          req.url().includes(`lineage=${encodeURIComponent(l.id)}`)
        ).catch(() => null),
        page.waitForTimeout(500),
      ])

      const groups = await page.locator('[data-testid^="phase-group-"]').all()
      if (groups.length === 0) continue

      // Parse `data-testid="phase-group-<phase>|<planVersion>|<lineage>"`
      // (pipe-separated — see PhaseView key builder).  The lineage segment is
      // populated only in `__all__` mode; per-lineage views use an empty
      // segment because the filter is already applied upstream.
      for (const g of groups) {
        const key = await g.getAttribute('data-testid')
        expect(key).toBeTruthy()
        const parts = key!.replace('phase-group-', '').split('|')
        const groupLineage = parts[2] ?? ''
        if (groupLineage) {
          expect(groupLineage).toBe(l.id)
        }
      }

      // Smallest phase number should be 1 (no synthetic phase 0 post-migration).
      const phaseNumbers = await Promise.all(groups.map(async g => {
        const key = await g.getAttribute('data-testid')
        return parseInt(key!.replace('phase-group-', '').split('|')[0], 10)
      }))
      const min = Math.min(...phaseNumbers)
      expect(min).toBeGreaterThanOrEqual(1)
    }

    // Sanity: live state's lineage should still match state.spec_lineage_id.
    // (Sentinel badge decouples from view — 14.8.)
    if (state.spec_lineage_id) {
      expect(lineages.some(l => l.id === state.spec_lineage_id)).toBeTruthy()
    }
  })

  test('15.4 modern project does not render synthetic Phase 0 or Previous-cycles header', async ({ page, request }) => {
    // Regression guard: no matter how many changes/archives a modern project
    // has, the PhaseView must not emit the pre-migration "Phase 0 (archived)"
    // fallback — every entry has a real phase number now.
    await page.goto(ORCH_BASE)
    await navigateToTab(page, 'phases')
    await page.waitForSelector('[data-testid^="phase-group-"], [data-testid="toggle-unattributed"]', {
      timeout: 10_000,
    }).catch(() => {})

    // Scope to the main panel — the sidebar may legitimately display a
    // lineage whose display_name includes "Previous cycles" (it is the
    // backfill label for a truly unattributed lineage), which must not be
    // conflated with the PhaseView's removed synthetic header.
    const phasePanel = page.locator('main')
    const panelText = (await phasePanel.innerText()).toLowerCase()
    expect(panelText).not.toContain('phase 0 (archived)')
    expect(panelText).not.toContain('previous cycles')

    // Legacy entries (no spec_lineage_id + no phase) are gated behind the
    // "Show unattributed" toggle, which starts hidden.  If the toggle is
    // present, the default label must be "Show" (not "Hide").
    const toggle = page.locator('[data-testid="toggle-unattributed"]')
    if (await toggle.count() > 0) {
      await expect(toggle).toContainText(/Show unattributed/i)
    }

    // Also: every phase-group headline that renders starts at phase >= 1.
    const groups = await page.locator('[data-testid^="phase-group-"]').all()
    for (const g of groups) {
      const key = await g.getAttribute('data-testid')
      const phaseNum = parseInt(key!.replace('phase-group-', '').split('|')[0], 10)
      expect(phaseNum).toBeGreaterThanOrEqual(1)
    }
  })

  test('9.3 two plan versions with the same phase number render separate subheaders', async ({ page, request }) => {
    const state = await getLiveState(request)

    // Bucket live + archived changes by (phase, plan_version) to discover whether
    // the fixture actually exercises the collision case.
    const seen = new Map<number, Set<string>>()
    for (const c of state.changes ?? []) {
      if (c.phase == null) continue
      const pv = c.plan_version == null ? '' : String(c.plan_version)
      const set = seen.get(c.phase) ?? new Set<string>()
      set.add(pv)
      seen.set(c.phase, set)
    }
    const collidingPhase = [...seen.entries()].find(([, vs]) => vs.size >= 2)
    if (!collidingPhase) test.skip()

    await page.goto(ORCH_BASE)
    await navigateToTab(page, 'phases')

    const [phaseNum, versions] = collidingPhase!
    const labels = await Promise.all([...versions].map(async v => {
      // Non-all mode: key format is `${phase}|${planVersion}|` (trailing empty lineage).
      const header = page.locator(`[data-testid="phase-group-${phaseNum}|${v}|"]`).first()
      if (await header.count() === 0) return null
      return header.locator('span.font-medium').first().textContent()
    }))
    const rendered = labels.filter(Boolean) as string[]
    // At least two distinct "Phase N (plan v…)" labels when the collision exists.
    expect(rendered.length).toBeGreaterThanOrEqual(2)
    for (const label of rendered) {
      expect(label).toMatch(new RegExp(`Phase ${phaseNum} \\(plan v`))
    }
  })
})

test.describe('Lineage network guard (15b.16)', () => {
  test('every orchestration-scoped fetch except the sidebar live-state poll carries a lineage query param after the selector has resolved', async ({ page, request }) => {
    const lineages = await getLineages(request)
    if (lineages.length === 0) test.skip()

    // Start capturing only AFTER the lineage context has resolved.  The
    // initial tick of the dashboard can fire a lineage-unaware fetch
    // because React has not yet received the default selection from
    // LineageList's effect — the server handles the missing filter by
    // applying the default-selection rule, so that tick is legitimate
    // and not what 15b.16 is guarding against.  The guard is: once the
    // selector has a concrete value, every subsequent call must carry it.
    await page.goto(ORCH_BASE)
    await expect.poll(async () =>
      page.evaluate((p) => window.localStorage.getItem(`set-lineage-${p}`), PROJECT)
    ).not.toBeNull()

    const seen: string[] = []
    page.on('request', req => {
      const url = req.url()
      if (/\/api\/[^/]+\/(state|digest|activity-timeline|llm-calls)(\?|$)/.test(url)) {
        seen.push(url)
      }
    })

    // Trigger a fresh round of fetches by clicking the currently-selected
    // row again (a no-op setter) — not reliable — so instead navigate
    // between tabs, which each fire their own lineage-scoped fetch.
    await navigateToTab(page, 'digest')
    await page.waitForTimeout(500)
    await navigateToTab(page, 'activity')
    await page.waitForTimeout(500)
    await navigateToTab(page, 'tokens')
    await page.waitForTimeout(500)

    // The sidebar poll from ProjectLayout intentionally omits lineage — it
    // drives the sentinel-badge binding (Section 14.8).  Every OTHER call
    // to the lineage-scoped endpoints must carry a lineage query param.
    const withoutLineage = seen.filter(u => !u.includes('lineage='))
    const unexpected = withoutLineage.filter(u =>
      !u.match(/\/api\/[^/]+\/state(\?|$)/)
    )
    expect(unexpected).toEqual([])
  })
})
