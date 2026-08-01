/**
 * Opening a record is a click on the row, not on a 12-pixel caret.
 *
 * The interesting half is not that the row opens — it is what must NOT open it. A row-wide
 * handler swallows every click inside the row unless it is guarded, and the two that matter here
 * are a checkbox (selecting is not reading) and the end of a text selection (copying a value is
 * not reading either, and collapsing the record mid-drag destroys what the reader was looking at).
 *
 * Browser-only on purpose: `window.getSelection()` and `closest()` against real event targets are
 * what the guard is made of, and jsdom's versions would let a broken guard pass.
 */
import { expect, test } from '@playwright/test'
import { PROJECT, settle } from './screens'

test.use({ viewport: { width: 1920, height: 1080 } })

async function firstExpandableRow(page: import('@playwright/test').Page) {
  await page.goto(`/p/${PROJECT}/status?tab=bugs`)
  await settle(page, '[data-status-tab]')
  const row = page.locator('tbody tr').filter({ has: page.locator('[aria-expanded]') }).first()
  await expect(row).toBeVisible()
  return row
}

test('clicking anywhere on a row opens the whole record', async ({ page }) => {
  const row = await firstExpandableRow(page)
  const caret = row.locator('[aria-expanded]')
  await expect(caret).toHaveAttribute('aria-expanded', 'false')

  // A cell in the middle of the row — deliberately not the caret, which is the old target.
  await row.locator('td[data-col]').first().click()
  await expect(caret).toHaveAttribute('aria-expanded', 'true')

  await row.locator('td[data-col]').first().click()
  await expect(caret).toHaveAttribute('aria-expanded', 'false')
})

test('the caret still works, and opens the record once rather than twice', async ({ page }) => {
  // The caret kept its own keyboard handler and lost its click handler to the row's. Had it kept
  // both, one click would toggle twice and the record would appear not to open at all.
  const row = await firstExpandableRow(page)
  const caret = row.locator('[aria-expanded]')
  await caret.click()
  await expect(caret).toHaveAttribute('aria-expanded', 'true')
})

test('selecting a row does not open it — a checkbox is not a request to read', async ({ page }) => {
  const row = await firstExpandableRow(page)
  const caret = row.locator('[aria-expanded]')
  const box = row.locator('input[type=checkbox]')

  await box.check()
  await expect(box).toBeChecked()
  await expect(caret).toHaveAttribute('aria-expanded', 'false')
})

test('ending a text selection inside a row does not collapse what was being read', async ({ page }) => {
  const row = await firstExpandableRow(page)
  const caret = row.locator('[aria-expanded]')
  await row.locator('td[data-col]').first().click()
  await expect(caret).toHaveAttribute('aria-expanded', 'true')

  // Drag across a value in the opened detail, the way someone copying an identifier would.
  const cell = row.locator('td[data-col]').first()
  const b = (await cell.boundingBox())!
  await page.mouse.move(b.x + 6, b.y + b.height / 2)
  await page.mouse.down()
  await page.mouse.move(b.x + b.width - 6, b.y + b.height / 2, { steps: 8 })
  await page.mouse.up()

  await expect(caret).toHaveAttribute('aria-expanded', 'true')
})
