import { test, expect } from '@playwright/test'
import { PROJECT, ORCH_BASE } from './helpers'

test('tab click updates URL', async ({ page }) => {
  await page.goto(ORCH_BASE)
  await page.click('[data-tab="phases"]')
  await expect(page).toHaveURL(/tab=phases/)
})

test('direct URL navigation loads correct tab', async ({ page }) => {
  await page.goto(`${ORCH_BASE}?tab=phases`)
  const tab = page.locator('[data-tab="phases"]')
  // Active tab has bg-neutral-800 class
  await expect(tab).toHaveClass(/bg-neutral-800/)
})

test('sidebar contains project name', async ({ page }) => {
  await page.goto(ORCH_BASE)
  // Project name appears in the page — header bar or sidebar
  const content = await page.content()
  expect(content).toContain(PROJECT)
})

test('manager page lists projects', async ({ page }) => {
  await page.goto('/')
  // Should show at least one project (the one we're testing)
  await expect(page.locator(`text="${PROJECT}"`).first()).toBeVisible()
})

test('clicking project navigates to orch', async ({ page }) => {
  await page.goto('/')
  // Click the project name/link
  await page.locator(`text="${PROJECT}"`).first().click()
  await expect(page).toHaveURL(new RegExp(`/p/${PROJECT}`))
})
