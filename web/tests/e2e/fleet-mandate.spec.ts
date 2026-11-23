/**
 * The goal fields of the start form in a real browser — the two things that
 * must not move the form, measured.
 *
 * Found by looking at the first build: typing the first character of a goal
 * removed a sentence and the whole dialog jumped twenty pixels. jsdom cannot see
 * that (every rectangle is zero there), so it is held here.
 *
 * ⚠ **Nothing in this file writes anything.** Every non-GET request is refused
 * at the network layer and the list of refused requests is asserted EMPTY: the
 * form is opened, typed into and closed, never submitted.
 */
import { expect, test, type Page } from '@playwright/test'

async function openStartForm(page: Page) {
  const writes: string[] = []
  await page.route('**/api/**', route => {
    const request = route.request()
    if (request.method() === 'GET') return route.continue()
    writes.push(`${request.method()} ${new URL(request.url()).pathname}`)
    return route.fulfill({ status: 200, json: {} })
  })
  await page.goto('/')
  const offer = page.locator('[data-fleet-start="offer"]').first()
  await expect(offer).toBeVisible({ timeout: 30_000 })
  await offer.click()
  const form = page.locator('[data-fleet-start="form"]')
  await expect(form).toBeVisible()
  // The provider and worktree answers arrive after the form opens and add rows.
  await expect(page.locator('[data-fleet-start="resolved"]')).toBeVisible()
  await page.waitForTimeout(500)
  return { form, writes }
}

async function measure(page: Page) {
  const rect = (el: Element) => {
    const b = el.getBoundingClientRect()
    return [b.x, b.y, b.width, b.height].map(v => Math.round(v * 10) / 10).join(',')
  }
  return {
    dialog: await page.locator('[data-fleet-start-dialog] > div').evaluate(rect),
    // Every row of the form except the note itself, whose TEXT is what changes.
    rows: await page.locator('[data-fleet-start="form"] > *').evaluateAll(
      (els, fn) => els.map(el => new Function('el', `return (${fn})(el)`)(el)), rect.toString()),
  }
}

test('opening the scope fields moves nothing in the start form', async ({ page }) => {
  const { writes } = await openStartForm(page)
  const before = await measure(page)
  expect(before.rows.length).toBeGreaterThanOrEqual(5)
  await page.locator('[data-fleet-mandate-more]').click()
  const extras = page.locator('[data-fleet-mandate-extras]')
  await expect(extras).toBeVisible()
  expect(await measure(page)).toEqual(before)
  // It covers what is under it rather than pushing it, and it closes on its own control.
  await extras.locator('[data-fleet-mandate-extras-close]').click()
  await expect(extras).toHaveCount(0)
  expect(await measure(page)).toEqual(before)
  expect(writes).toEqual([])
})

test('typing a goal changes the sentence under it and moves nothing', async ({ page }) => {
  const { writes } = await openStartForm(page)
  await expect(page.locator('[data-fleet-start="no-mandate"]')).toBeVisible()
  const before = await measure(page)
  await page.locator('[data-fleet-mandate-goal]').first().fill('ship the importer and its tests')
  await expect(page.locator('[data-fleet-start="mandate-set"]')).toBeVisible()
  expect(await measure(page)).toEqual(before)
  await page.locator('[data-fleet-mandate-goal]').first().fill('')
  await expect(page.locator('[data-fleet-start="no-mandate"]')).toBeVisible()
  expect(await measure(page)).toEqual(before)
  await page.locator('[data-fleet-start-close]').click()
  expect(writes).toEqual([])
})
