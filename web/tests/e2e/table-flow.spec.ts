/**
 * A table much narrower than its panel flows into side-by-side groups.
 *
 * Measured on the debt tab before the change: a three-column table drew at roughly 700 px inside
 * an 1800 px panel, so more than half the screen carried nothing while the rows ran down past the
 * fold. Stretching the columns to fill the width was tried earlier and rejected — the gaps land
 * between the values a reader is comparing — so the rows flow instead.
 *
 * Browser-only, and not by preference: the decision reads the panel's measured width, which is
 * exactly the thing jsdom does not have. A unit test here would assert against a zero and pass
 * whatever the code did.
 */
import { expect, test } from '@playwright/test'
import { PROJECT, settle } from './screens'

test.use({ viewport: { width: 1920, height: 1080 } })

const tablesIn = (page: import('@playwright/test').Page, label: string) =>
  page.locator('section', { hasText: label }).first().locator('table')

test('a narrow table with many rows flows into more than one group', async ({ page }) => {
  await page.goto(`/p/${PROJECT}/status?tab=debt`)
  await settle(page, '[data-status-tab]')

  const tables = page.locator('table')
  expect(await tables.count()).toBeGreaterThan(1)

  // Every group carries its own header, or the right-hand columns would be unlabelled — which is
  // the whole reason this is a repeated table rather than a CSS column trick.
  for (let i = 0; i < await tables.count(); i++) {
    await expect(tables.nth(i).locator('thead th').first()).toBeVisible()
  }

  // The groups are genuinely SIDE BY SIDE. Stacked groups with repeated headers would satisfy a
  // naive count while using no more width than before — the mechanism running with no result.
  const a = (await tables.nth(0).boundingBox())!
  const b = (await tables.nth(1).boundingBox())!
  expect(b.x).toBeGreaterThan(a.x + a.width - 10)
  expect(Math.abs(b.y - a.y)).toBeLessThan(40)
})

test('every delivered row survives the split', async ({ page }) => {
  await page.goto(`/p/${PROJECT}/status?tab=debt`)
  await settle(page, '[data-status-tab]')

  // The count line is written from the data and is rendered once, outside the groups. Flowing is
  // a layout choice and must not become a quiet truncation — so the rows on screen must add up
  // to what the table says it has.
  const stated = await page.getByText(/^\d+ rows?$/).first().innerText()
  const expected = parseInt(stated, 10)
  expect(expected).toBeGreaterThan(0)
  expect(await page.locator('tbody tr').count()).toBe(expected)
})

test('a table that already fills its panel is left as one', async ({ page }) => {
  // The bugs tab is wider than the screen, so a second group could not fit. Splitting there would
  // make both halves scroll sideways — strictly worse than one table that does.
  await page.goto(`/p/${PROJECT}/status?tab=bugs`)
  await settle(page, '[data-status-tab]')
  expect(await page.locator('table').count()).toBe(1)
})
