/**
 * Screenshot generator for documentation.
 *
 * Usage:
 *   E2E_PROJECT=minishop-run5 pnpm screenshot:docs
 *
 * If E2E_PROJECT is not set, auto-detects the latest "done" project from the API.
 *
 * Outputs PNGs to docs/images/auto/web/ for embedding in documentation.
 */
import { test, expect } from '@playwright/test'
import { PROJECT, ORCH_BASE, navigateToTab } from './helpers'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT_DIR = path.resolve(__dirname, '../../../docs/images/auto/web')

/** Dashboard tabs that are always present. */
const TABS = [
  'changes',
  'phases',
  'tokens',
  'sessions',
  'log',
  'learnings',
  'agent',
  'sentinel',
] as const

/** Dashboard tabs that only appear when the project has the relevant data. */
const OPTIONAL_TABS = [
  'plan',
  'digest',
  'context',
  'audit',
] as const

test.use({ viewport: { width: 1280, height: 720 } })

test.describe('Documentation screenshots', () => {

  // ── Manager / global pages ──

  test('manager — project list', async ({ page }) => {
    await page.goto('/')
    await page.waitForSelector(`text="${PROJECT}"`, { timeout: 10_000 })
    await page.waitForTimeout(500)
    await page.screenshot({ path: path.join(OUT_DIR, 'manager-project-list.png'), fullPage: true })
  })

  test('global — issues page', async ({ page }) => {
    await page.goto('/issues')
    // Wait for page to load — may show "No issues" or an issue list
    await page.waitForTimeout(1000)
    await page.screenshot({ path: path.join(OUT_DIR, 'global-issues.png'), fullPage: true })
  })

  // ── Dashboard overview ──

  test('dashboard — overview', async ({ page }) => {
    await page.goto(ORCH_BASE)
    await page.waitForSelector('[data-tab="changes"]', { timeout: 10_000 })
    await page.waitForTimeout(500)
    await page.screenshot({ path: path.join(OUT_DIR, 'dashboard-overview.png'), fullPage: true })
  })

  // ── Always-present tabs ──

  for (const tab of TABS) {
    test(`tab — ${tab}`, async ({ page }) => {
      await navigateToTab(page, tab)
      await page.waitForTimeout(800)
      await page.screenshot({ path: path.join(OUT_DIR, `tab-${tab}.png`), fullPage: true })
    })
  }

  // ── Conditional tabs (skip if not visible) ──

  for (const tab of OPTIONAL_TABS) {
    test(`tab — ${tab}`, async ({ page }) => {
      await page.goto(ORCH_BASE)
      await page.waitForSelector('[data-tab="changes"]', { timeout: 10_000 })
      const tabButton = page.locator(`[data-tab="${tab}"]`)
      if (!(await tabButton.isVisible().catch(() => false))) {
        test.skip()
        return
      }
      await navigateToTab(page, tab)
      await page.waitForTimeout(800)
      await page.screenshot({ path: path.join(OUT_DIR, `tab-${tab}.png`), fullPage: true })
    })
  }

  // ── Secondary pages ──

  test('page — memory', async ({ page }) => {
    await page.goto(`/p/${PROJECT}/memory`)
    await page.waitForTimeout(1000)
    await page.screenshot({ path: path.join(OUT_DIR, 'page-memory.png'), fullPage: true })
  })

  test('page — settings', async ({ page }) => {
    await page.goto(`/p/${PROJECT}/settings`)
    await page.waitForTimeout(1000)
    await page.screenshot({ path: path.join(OUT_DIR, 'page-settings.png'), fullPage: true })
  })

  test('page — project issues', async ({ page }) => {
    await page.goto(`/p/${PROJECT}/issues`)
    await page.waitForTimeout(1000)
    await page.screenshot({ path: path.join(OUT_DIR, 'page-issues.png'), fullPage: true })
  })

  test('page — worktrees', async ({ page }) => {
    await page.goto(`/p/${PROJECT}/orch/worktrees`)
    await page.waitForTimeout(1000)
    await page.screenshot({ path: path.join(OUT_DIR, 'page-worktrees.png'), fullPage: true })
  })
})
