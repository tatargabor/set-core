/**
 * A row detail in a flowed one-column list must not land in a neighbour's cell.
 *
 * The flowed list makes `tbody` a grid, which makes every `<tr>` a grid ITEM. The detail is a
 * sibling row, so auto-placement put it in the NEXT free cell: expanding the second name in a
 * row opened a panel beside the third one. Nothing threw; the panel was simply about a
 * different item than the one under the reader's cursor.
 *
 * The assertion is geometric because the defect was geometric. It also drives the page the way
 * a reader does — a real click on the expander — since the bug lives in layout, and calling a
 * handler directly would have produced the same open state with none of the placement.
 */
import { test, expect } from '@playwright/test'
import { PROJECT, settle } from './screens'

test('an expanded row spans the flow rather than taking a neighbour cell', async ({ page }) => {
  await page.goto(`/p/${PROJECT}/status`)
  await settle(page, '[data-status-tab]')
  await page.locator('[data-status-tab="changes"]').first().click()
  await settle(page)

  // The flowed list is the one-column table; find it by that shape, not by a label.
  const flowed = page.locator('table').filter({ has: page.locator('thead th', { hasText: /^name$/ }) }).last()
  await expect(flowed).toBeVisible()

  const rows = flowed.locator('tbody tr')
  const before = await rows.count()
  expect(before).toBeGreaterThan(12)

  // Pick a row that is NOT in the first column — that is where the bug showed.
  const firstBox = await rows.nth(0).boundingBox()
  let target = -1
  for (let i = 1; i < before; i++) {
    const b = await rows.nth(i).boundingBox()
    if (b && firstBox && b.x > firstBox.x + 50 && Math.abs(b.y - firstBox.y) < 5) { target = i; break }
  }
  expect(target, 'a row in a later column of the same visual line').toBeGreaterThan(0)

  const targetBox = (await rows.nth(target).boundingBox())!
  await rows.nth(target).locator('[aria-expanded]').click()
  await page.waitForTimeout(300)

  const detail = flowed.locator('tbody tr').nth(target + 1)
  const detailBox = (await detail.boundingBox())!
  const tableBox = (await flowed.boundingBox())!

  // It must start at the table's left edge, not at the opened row's column.
  expect(detailBox.x).toBeLessThan(targetBox.x - 50)
  expect(detailBox.width).toBeGreaterThan(tableBox.width * 0.8)
})
