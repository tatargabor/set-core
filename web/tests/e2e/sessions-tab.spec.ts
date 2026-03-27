import { test, expect } from '@playwright/test'
import { navigateToTab, PROJECT } from './helpers'

test.beforeEach(async ({ page }) => {
  await navigateToTab(page, 'sessions')
})

test('session list renders entries', async ({ page, request }) => {
  const res = await request.get(`/api/${PROJECT}/sessions`)
  const data = await res.json()
  const sessions = data.sessions ?? []
  if (sessions.length === 0) return test.skip()

  // Wait for session panel to load
  await page.waitForTimeout(3000)
  // The session panel should render something beyond "No sessions" — look for any label or outcome
  const labels = sessions.map((s: { label?: string }) => s.label).filter(Boolean)
  if (labels.length > 0) {
    const content = await page.content()
    const found = labels.some((l: string) => content.includes(l))
    expect(found).toBeTruthy()
  } else {
    // No labels — just verify the tab rendered content (not empty/error)
    const content = await page.textContent('body')
    expect(content!.length).toBeGreaterThan(100)
  }
})

test('session shows label like Decompose or Review', async ({ page, request }) => {
  const res = await request.get(`/api/${PROJECT}/sessions`)
  const data = await res.json()
  const labeled = (data.sessions ?? []).find((s: { label?: string }) => s.label)
  if (!labeled) return test.skip()

  await page.waitForTimeout(3000)
  // Labels may be truncated with CSS — check the page contains the text at DOM level
  const content = await page.content()
  expect(content).toContain(labeled.label)
})
