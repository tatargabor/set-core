/**
 * Consumer app screenshot capture for documentation.
 *
 * Usage:
 *   E2E_APP_URL=http://localhost:3100 PROJECT_DIR=/path/to/project pnpm screenshot:app
 *
 * Requires a running consumer app dev server.
 * Auto-discovers routes from Next.js App Router (src/app/) if PROJECT_DIR is set.
 *
 * Output: docs/images/auto/app/<name>.png
 */
import { test } from '@playwright/test'
import * as fs from 'node:fs'
import * as path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT_DIR = path.resolve(__dirname, '../../../docs/images/auto/app')
const APP_URL = process.env.E2E_APP_URL || 'http://localhost:3100'
const PROJECT_DIR = process.env.PROJECT_DIR || ''

interface PageDef {
  name: string
  path: string
  clickFirstLink?: boolean
  requiresAuth?: boolean
}

const FALLBACK_ROUTES: PageDef[] = [
  { name: 'home', path: '/' },
  { name: 'products', path: '/products' },
  { name: 'product-detail', path: '/products', clickFirstLink: true },
  { name: 'cart', path: '/cart' },
  { name: 'admin-login', path: '/admin/login' },
  { name: 'admin-dashboard', path: '/admin', requiresAuth: true },
  { name: 'admin-products', path: '/admin/products', requiresAuth: true },
]

/** Auto-discover static routes from Next.js App Router */
function discoverRoutes(projectDir: string): PageDef[] {
  const appDir = path.join(projectDir, 'src', 'app')
  if (!fs.existsSync(appDir)) return []

  const routes: PageDef[] = []

  function walk(dir: string, prefix: string) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isDirectory()) {
        if (entry.name === 'page.tsx' || entry.name === 'page.js') {
          if (prefix.includes('[') || prefix.includes('/api')) continue
          const routePath = prefix || '/'
          const name = routePath === '/' ? 'home' : routePath.slice(1).replace(/\//g, '-')
          routes.push({
            name,
            path: routePath,
            requiresAuth: routePath.startsWith('/admin') && !routePath.includes('login') && !routePath.includes('register'),
          })
        }
        continue
      }
      if (entry.name.startsWith('[') || entry.name === 'api' || entry.name.startsWith('_')) continue
      const segment = (entry.name.startsWith('(') && entry.name.endsWith(')')) ? '' : `/${entry.name}`
      walk(path.join(dir, entry.name), prefix + segment)
    }
  }

  walk(appDir, '')

  const seen = new Set<string>()
  return routes.filter(r => {
    if (seen.has(r.path)) return false
    seen.add(r.path)
    return true
  })
}

// Resolve pages
let pages: PageDef[]
if (PROJECT_DIR && fs.existsSync(path.join(PROJECT_DIR, 'src', 'app'))) {
  pages = discoverRoutes(PROJECT_DIR)
  // Add product-detail click-through if products page exists
  if (pages.some(p => p.path === '/products')) {
    pages.push({ name: 'product-detail', path: '/products', clickFirstLink: true })
  }
} else {
  pages = FALLBACK_ROUTES
}

test.use({
  viewport: { width: 1280, height: 720 },
  baseURL: APP_URL,
})

test.describe('Consumer app screenshots', () => {
  let loggedIn = false

  for (const pageDef of pages) {
    test(`app — ${pageDef.name}`, async ({ page }) => {
      // Admin pages need login first
      if (pageDef.requiresAuth && !loggedIn) {
        await page.goto('/admin/login', { waitUntil: 'networkidle', timeout: 10_000 })
        const email = page.locator('input[type="email"], input[name="email"]')
        if (await email.isVisible({ timeout: 2000 }).catch(() => false)) {
          await email.fill('admin@test.com')
          await page.locator('input[type="password"]').fill('admin123')
          await page.locator('button[type="submit"]').click()
          await page.waitForTimeout(1000)
          loggedIn = true
        }
      }

      if (pageDef.clickFirstLink) {
        await page.goto(pageDef.path, { waitUntil: 'networkidle', timeout: 10_000 })
        const link = page.locator("a[href*='/products/']").first()
        if (await link.isVisible({ timeout: 3000 }).catch(() => false)) {
          await link.click()
          await page.waitForLoadState('networkidle')
        }
      } else {
        await page.goto(pageDef.path, { waitUntil: 'networkidle', timeout: 10_000 })
      }

      await page.screenshot({
        path: path.join(OUT_DIR, `${pageDef.name}.png`),
        fullPage: true,
      })
    })
  }
})
