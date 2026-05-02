import { test, expect, type APIRequestContext } from '@playwright/test'
import { PROJECT, navigateToTab } from './helpers'

interface SubSpan {
  category: 'spec' | 'code' | 'test' | 'build' | 'subagent' | 'other'
  start: string
  end: string
  duration_ms: number
  trigger_tool: string | null
  trigger_detail: string | null
}

interface ActivitySpan {
  category: string
  change: string
  start: string
  end: string
  duration_ms: number
  detail?: Record<string, unknown>
  sub_spans?: SubSpan[] | null
}

interface ActivityTimelineData {
  spans: ActivitySpan[]
}

async function getActivityTimeline(request: APIRequestContext): Promise<ActivityTimelineData> {
  const res = await request.get(`/api/${PROJECT}/activity-timeline`)
  expect(res.ok()).toBeTruthy()
  return res.json()
}

test.describe('Activity tab — implementing sub-phase breakdown', () => {
  test('API: every implementing span carries `sub_spans` field', async ({ request }) => {
    // AC-22 + AC-23 + AC-25: contract that sub_spans is always present
    // (empty list when no classifiable data) and that classifiable entries
    // have the documented shape.
    const data = await getActivityTimeline(request)
    const implementingSpans = data.spans.filter((s) => s.category === 'implementing')
    if (implementingSpans.length === 0) test.skip()

    for (const s of implementingSpans) {
      // Field MUST be present on every implementing span (not undefined / not missing)
      expect(s.sub_spans, `change=${s.change} missing sub_spans`).toBeDefined()
      expect(Array.isArray(s.sub_spans), `change=${s.change} sub_spans not array`).toBeTruthy()

      // If non-empty, every entry has the documented keys + valid category
      const VALID_CATS = new Set(['spec', 'code', 'test', 'build', 'subagent', 'other'])
      for (const sub of s.sub_spans!) {
        expect(VALID_CATS.has(sub.category), `unknown sub-category ${sub.category}`).toBeTruthy()
        expect(sub.start).toBeTruthy()
        expect(sub.end).toBeTruthy()
        expect(typeof sub.duration_ms).toBe('number')
        // trigger fields present (may be null)
        expect('trigger_tool' in sub).toBeTruthy()
        expect('trigger_detail' in sub).toBeTruthy()
      }
    }
  })

  test('API: sub_spans are confined to parent window and start-ascending', async ({ request }) => {
    // AC-24: every sub-span within parent's [start, end].
    const data = await getActivityTimeline(request)
    const implementing = data.spans.filter((s) => s.category === 'implementing' && (s.sub_spans?.length ?? 0) > 0)
    if (implementing.length === 0) test.skip()

    for (const s of implementing) {
      const subs = s.sub_spans!
      const parentStart = new Date(s.start).getTime()
      const parentEnd = new Date(s.end).getTime()
      let lastStart = -Infinity
      for (const sub of subs) {
        const sStart = new Date(sub.start).getTime()
        const sEnd = new Date(sub.end).getTime()
        expect(sStart, `sub-span starts before parent in ${s.change}`).toBeGreaterThanOrEqual(parentStart)
        expect(sEnd, `sub-span ends after parent in ${s.change}`).toBeLessThanOrEqual(parentEnd)
        expect(sStart, `sub-spans not start-ascending in ${s.change}`).toBeGreaterThanOrEqual(lastStart)
        lastStart = sStart
      }
    }
  })

  test('UI: implementing row shows expand toggle when sub_spans present', async ({ page, request }) => {
    // AC-14 + AC-21: parent row gets a toggle when sub-spans exist;
    // default-expanded UX (per UX feedback after pivot review).
    const data = await getActivityTimeline(request)
    const hasAnySubSpans = data.spans.some(
      (s) => s.category === 'implementing' && (s.sub_spans?.length ?? 0) > 0,
    )
    if (!hasAnySubSpans) test.skip()

    await navigateToTab(page, 'activity')
    // The label cell carries one of ▶ / ▼ when the toggle is offered.
    const toggle = page.locator('text=/^[▶▼]$/').first()
    await expect(toggle).toBeVisible({ timeout: 10_000 })
  })

  test('UI: sub-rows render under the parent when expanded', async ({ page, request }) => {
    // AC-15 + AC-19: indented sub-rows appear with category labels on expand.
    const data = await getActivityTimeline(request)
    const hasAnySubSpans = data.spans.some(
      (s) => s.category === 'implementing' && (s.sub_spans?.length ?? 0) > 0,
    )
    if (!hasAnySubSpans) test.skip()

    // Default-expanded: sub-row labels should be visible without click.
    // Force-clear localStorage so the test runs from the documented default.
    await page.addInitScript(() => {
      try {
        window.localStorage.removeItem('activity-implementing-sub-expanded')
      } catch {
        /* ignore */
      }
    })
    await navigateToTab(page, 'activity')

    // Compute the categories that the API guarantees will appear as sub-rows.
    const presentCats = new Set<string>()
    for (const s of data.spans) {
      if (s.category !== 'implementing') continue
      for (const sub of s.sub_spans ?? []) presentCats.add(sub.category)
    }
    if (presentCats.size === 0) test.skip()

    // Each present category gets an `└─ <name>` label in the labels column.
    for (const cat of presentCats) {
      // Use a robust matcher tolerant of the box-drawing tree marker.
      const label = page.locator(`text=/${cat}$/`).first()
      await expect(label, `sub-row label for ${cat} not visible`).toBeVisible({ timeout: 10_000 })
    }
  })

  test('UI: toggle persists collapse state in localStorage', async ({ page, request }) => {
    // AC-15: localStorage persistence across reloads.
    const data = await getActivityTimeline(request)
    const hasAnySubSpans = data.spans.some(
      (s) => s.category === 'implementing' && (s.sub_spans?.length ?? 0) > 0,
    )
    if (!hasAnySubSpans) test.skip()

    await navigateToTab(page, 'activity')

    // Click the toggle — should collapse (default is expanded).
    const toggle = page.locator('text=/^[▶▼]$/').first()
    await toggle.waitFor({ state: 'visible', timeout: 10_000 })
    await toggle.click()

    const stored = await page.evaluate(() => window.localStorage.getItem('activity-implementing-sub-expanded'))
    expect(stored, 'collapse state not persisted').toBe('false')

    // Reload and verify the collapsed state is restored — toggle char becomes ▶
    await page.reload()
    await page.locator('text=/^▶$/').first().waitFor({ state: 'visible', timeout: 10_000 })
  })
})
