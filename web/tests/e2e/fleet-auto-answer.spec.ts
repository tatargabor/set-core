/**
 * The automatic-answers panel in a real browser (fleet-auto-answer, task 4.2b).
 *
 * jsdom lays nothing out, so "opening the panel moves nothing under it" is untestable
 * there: every rectangle is zero and any assertion about them passes. Here it is measured.
 *
 * The state and the decisions are FULFILLED at the network layer, and the cancel POST is
 * intercepted and answered — so nothing here touches a real proposal or the machine's
 * switch. The last test is the anchor against the fulfilled shape: it reads the real route
 * and asserts the fields the screen depends on.
 */
import { expect, test, type Page } from '@playwright/test'

const PENDING = {
  id: 'relay-47f1763f-0123456789ab', key: 'Q1', session_id: 'sess-e2e', agent: 'alpha · 47f1763f', project: 'alpha',
  kind: 'ask', question: 'Which release colour should the banner use?', choice: 'TEAL', tier: 'decided',
  confidence: 0.9, seconds_left: 45,
  references: [{ kind: 'operator', quote: 'the release colour is TEAL, not orange', checked: true }],
}
const STATE = { enabled: true, wired: true, forward: true, window_s: 60, likely_min: 0.8, pending: [PENDING], pending_count: 1 }
const DECISIONS = { decisions: [
  { ts: Date.now() / 1000 - 120, id: 'relay-a', key: 'Q1', agent: 'beta · 1', kind: 'ask', question: 'Squash the fixups?',
    choice: 'Yes', tier: 'likely', confidence: 0.86, outcome: 'overtaken', reason: '', human_answer: 'Yes', references: [] },
  { ts: Date.now() / 1000 - 600, id: 'relay-b', key: 'Q1', agent: 'gamma · 2', kind: 'ask', question: 'May I push?',
    choice: 'Yes', tier: 'decided', confidence: 0.9, outcome: 'excluded', reason: 'outward step: publish',
    human_answer: null, references: [] },
] }

type Box = { x: number; y: number; width: number; height: number }
const r = (b: Box | null) => (b ? [b.x, b.y, b.width, b.height].map(v => Math.round(v * 10) / 10).join(',') : 'none')

async function openFleet(page: Page, cancels: string[] = []) {
  await page.route('**/api/fleet/auto-answer', route => route.fulfill({ json: STATE }))
  await page.route('**/api/fleet/auto-answer/decisions**', route => route.fulfill({ json: DECISIONS }))
  await page.route('**/api/fleet/auto-answer/*/cancel', route => {
    cancels.push(route.request().url())
    return route.fulfill({ json: { ...STATE, pending: [], pending_count: 0 } })
  })
  await page.goto('/')
  await expect(page.locator('[data-fleet-auto-toggle]')).toHaveAttribute('data-fleet-auto-toggle', 'on', { timeout: 20_000 })
}

async function layout(page: Page) {
  const header = page.locator('[data-fleet-phase] > div').first()
  const boxes = [r(await header.boundingBox()), r(await page.locator('[data-fleet-auto-toggle]').boundingBox()),
                 r(await page.locator('[data-fleet-relay]').first().boundingBox())]
  const tiles = await page.locator('[data-fleet-shell], [data-fleet-chip], [data-fleet-column-mode], [data-fleet-usage], [data-fleet-map-toggle], [data-fleet-waves-toggle], [data-fleet-enlarged], [data-fleet-project]').evaluateAll(els =>
    els.slice(0, 40).map(el => {
      const b = el.getBoundingClientRect()
      return [b.x, b.y, b.width, b.height].map(v => Math.round(v * 10) / 10).join(',')
    }))
  return { boxes, tiles }
}

test('AC-20 + AC-19: the closed control counts, and opening the panel moves nothing under it', async ({ page }) => {
  await openFleet(page)
  await expect(page.locator('[data-fleet-auto-pending-count="1"]')).toHaveText('1')
  await page.waitForTimeout(500)
  const before = await layout(page)
  expect(before.boxes[0]).not.toBe('none')
  // An empty list would make the comparison below pass for nothing.
  expect(before.tiles.length).toBeGreaterThan(0)

  await page.locator('[data-fleet-auto-toggle]').click()
  const panel = page.locator('[data-fleet-auto-panel]')
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('TEAL')
  await expect(panel).toContainText('the release colour is TEAL, not orange')
  await expect(panel.locator('[data-fleet-auto-decisions="2"]')).toBeVisible()
  expect(await layout(page)).toEqual(before)
  expect(await panel.evaluate(el => getComputedStyle(el).position)).toBe('fixed')

  // Its own way out, and closing it moves nothing either.
  await panel.locator('[data-fleet-auto-close]').click()
  await expect(panel).toHaveCount(0)
  expect(await layout(page)).toEqual(before)
})

test('AC-18: cancel from the panel calls the route for that proposal', async ({ page }) => {
  const cancels: string[] = []
  await openFleet(page, cancels)
  await page.locator('[data-fleet-auto-toggle]').click()
  await page.locator(`[data-fleet-auto-cancel="${PENDING.id}"]`).click()
  await expect.poll(() => cancels.length).toBe(1)
  expect(cancels[0]).toContain(`/api/fleet/auto-answer/${PENDING.id}/cancel`)
  await expect(page.locator('[data-fleet-auto-pending="0"]')).toBeVisible()
})

test('the real route answers in the shape the screen renders', async ({ request }) => {
  const res = await request.get('/api/fleet/auto-answer')
  expect(res.ok()).toBe(true)
  const body = await res.json()
  expect(typeof body.enabled).toBe('boolean')
  expect(typeof body.wired).toBe('boolean')
  expect(Array.isArray(body.pending)).toBe(true)
  const log = await (await request.get('/api/fleet/auto-answer/decisions?limit=5')).json()
  expect(Array.isArray(log.decisions)).toBe(true)
})
