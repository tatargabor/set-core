/**
 * A table wider than its panel must SAY how much it is not showing.
 *
 * This lives in the browser pass and cannot move to a unit test, which is the point of writing it
 * down. The count comes from `offsetLeft`/`offsetWidth` on the header cells, and jsdom reports
 * every box as zero-sized — so a jsdom test would assert against a fabricated geometry and pass
 * whatever the code did. The stub in `tests/unit/setup.ts` says the same thing from the other end.
 *
 * The defect it guards: two tables on the landing tab ended mid-word at the panel edge, with the
 * box scrollable and nothing announcing it. The screen looked complete. That is the failure this
 * surface treats as worse than clutter — a tidy page reporting a calm it has not verified.
 */
import { expect, test } from '@playwright/test'
import { PROJECT, settle } from './screens'

test.use({ viewport: { width: 1920, height: 1080 } })

test('a table too wide for its panel states how many columns are off to the right', async ({ page }) => {
  await page.goto(`/p/${PROJECT}/status`)
  await settle(page, '[data-status-tab]')

  const marker = page.getByText(/\d+ columns? off to the right/).first()
  await expect(marker).toBeVisible()

  // The count is a measurement, not a decoration: the table it belongs to must actually be
  // scrollable sideways. A marker that appears over a table which fits would be the false-absence
  // defect inverted — announcing hidden content that is not hidden.
  const scroller = page.locator('div.overflow-x-auto').filter({ has: page.locator('table') }).first()
  const { scrollWidth, clientWidth } = await scroller.evaluate((el) => ({
    scrollWidth: el.scrollWidth,
    clientWidth: el.clientWidth,
  }))
  expect(scrollWidth).toBeGreaterThan(clientWidth)

  // And scrolling to the end must retire the claim, rather than leaving a stale count on screen.
  //
  // Asserted as a COUNT across the page, not on `.first()`. This tab carries three wide tables, so
  // scrolling one to its end leaves the other two markers standing — and `.first()` then resolves
  // to a different table's marker and reports the claim as still present. The first version of
  // this test failed for exactly that reason, which is a test-authoring bug wearing a product
  // bug's clothes: it accused the code of leaving a stale count when nothing was stale.
  const markers = page.getByText(/columns? off to the right/)
  const before = await markers.count()
  expect(before).toBeGreaterThan(0)

  await scroller.evaluate((el) => { el.scrollLeft = el.scrollWidth })
  await expect(markers).toHaveCount(before - 1, { timeout: 5000 })
})
