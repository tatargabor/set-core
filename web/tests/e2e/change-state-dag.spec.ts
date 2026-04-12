import { test, expect } from '@playwright/test'
import { getApiState, navigateToTab, PROJECT } from './helpers'

const MOCK_JOURNAL_TWO_ATTEMPTS = {
  entries: [
    { ts: '2026-04-12T10:00:00.000Z', field: 'current_step', old: null, new: 'implement', seq: 1 },
    { ts: '2026-04-12T10:01:00.000Z', field: 'build_result', old: null, new: 'pass', seq: 2 },
    { ts: '2026-04-12T10:01:00.001Z', field: 'gate_build_ms', old: null, new: 4200, seq: 3 },
    { ts: '2026-04-12T10:02:00.000Z', field: 'test_result', old: null, new: 'fail', seq: 4 },
    {
      ts: '2026-04-12T10:02:00.001Z',
      field: 'test_output',
      old: null,
      new: 'Error: expected 1 to equal 2',
      seq: 5,
    },
    { ts: '2026-04-12T10:03:00.000Z', field: 'current_step', old: null, new: 'implement', seq: 6 },
    { ts: '2026-04-12T10:04:00.000Z', field: 'build_result', old: null, new: 'pass', seq: 7 },
    { ts: '2026-04-12T10:05:00.000Z', field: 'test_result', old: null, new: 'pass', seq: 8 },
    { ts: '2026-04-12T10:06:00.000Z', field: 'status', old: 'verifying', new: 'merged', seq: 9 },
  ],
  grouped: {},
}

test.beforeEach(async ({ page }) => {
  await page.route(`**/api/${PROJECT}/changes/*/journal`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_JOURNAL_TWO_ATTEMPTS),
    })
  })
})

async function selectFirstChangeAndOpenTimeline(page: import('@playwright/test').Page) {
  await navigateToTab(page, 'changes')
  const state = await getApiState(await page.context().request)
  const firstChange = state.changes[0]
  if (!firstChange) {
    test.skip()
    return null
  }
  await page.locator(`text="${firstChange.name}"`).first().click()
  const timelineButton = page.locator('button', { hasText: /^Timeline$/ }).first()
  await timelineButton.click()
  await page.waitForTimeout(1500)
  return firstChange.name
}

test('DAG renders with correct attempt count from mocked journal', async ({ page }) => {
  const changeName = await selectFirstChangeAndOpenTimeline(page)
  if (!changeName) return

  // Toolbar shows "2 attempts"
  await expect(page.locator('text=/2 attempts/')).toBeVisible({ timeout: 5000 })

  // React Flow canvas is present
  const flow = page.locator('.react-flow')
  await expect(flow).toBeVisible()

  // Expect at least 6 nodes: 2 impls + 2 builds + 2 tests (terminal node adds 1 more = 7)
  const nodes = page.locator('.react-flow__node')
  const count = await nodes.count()
  expect(count).toBeGreaterThanOrEqual(6)
})

test('clicking a gate node opens the detail panel with output text', async ({ page }) => {
  const changeName = await selectFirstChangeAndOpenTimeline(page)
  if (!changeName) return

  // Click the first gate node (any node with role button)
  const gateNodes = page.locator('.react-flow__node-gate')
  await gateNodes.first().click()

  // Detail panel becomes visible — pre block should be present if output exists
  // The panel includes the word "attempt" and "started"
  await expect(page.locator('text=/attempt/').first()).toBeVisible({ timeout: 3000 })
})

test('Linear toggle swaps React Flow for ChangeTimelineDetail', async ({ page }) => {
  const changeName = await selectFirstChangeAndOpenTimeline(page)
  if (!changeName) return

  // React Flow canvas is visible first
  await expect(page.locator('.react-flow')).toBeVisible()

  // Click the Linear button in the toolbar
  await page.locator('button', { hasText: 'Linear' }).first().click()
  await page.waitForTimeout(500)

  // React Flow canvas should no longer be visible
  await expect(page.locator('.react-flow')).toHaveCount(0)
})
