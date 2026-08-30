/**
 * A LOOK at the board strip — not a structural assertion suite.
 *
 * ui-quality.md: a UI change is not done until somebody looked at it. This spec
 * opens the fleet screen, selects the project that publishes `board`, and
 * screenshots the strip. The screenshot is the deliverable; the visibility
 * assertion only makes sure it shows the strip rather than nothing.
 *
 * Cold start is slow on a machine with many live agents (discovery took ~3 s per
 * answer measured, and the column renders after several of them), so the waits
 * here are generous on purpose.
 */
import { test, expect } from '@playwright/test'

/**
 * BOARD_PROJECT names the project to look at — required, because a default here
 * would write some project's name into the framework, and the framework knows no
 * project by name. Run: BOARD_PROJECT=<name> npx playwright test <this file>
 */
const PROJECT = process.env.BOARD_PROJECT

test.skip(!PROJECT, 'set BOARD_PROJECT=<a project that declares a board command>')

test('the board strip renders under the selected project header', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/')
  const row = page.locator(`[data-fleet-project="${PROJECT}"]`).first()
  try {
    await row.waitFor({ state: 'visible', timeout: 15_000 })
  } catch {
    // Not showing: the project may sit behind a collapsed group. Open every
    // collapsed one — the group's own toggle is the header button with
    // aria-expanded="false"; the drag grip beside it is a different control.
    const collapsed = page.locator('[data-fleet-group][data-fleet-group-collapsed="true"]')
    const n = await collapsed.count()
    for (let i = 0; i < n; i++) {
      await collapsed.nth(i).getByRole('button', { name: /▸/ }).first().click()
    }
    await row.waitFor({ state: 'visible', timeout: 15_000 })
  }
  await row.click()
  const strip = page.locator('[data-fleet-board-strip]').first()
  await expect(strip).toBeVisible({ timeout: 20_000 })
  await page.screenshot({ path: 'test-results/board-strip.png', fullPage: false })
})
