/**
 * v0.app design source screenshot capture for documentation.
 *
 * Renders pages from a v0.app export's Next.js dev server — the design
 * source as it looks in isolation, before any orchestration agent has
 * touched the project. Used in docs/README to show the design input
 * alongside the built result captured by app-screenshots.spec.ts.
 *
 * Usage:
 *   E2E_DESIGN_URL=http://localhost:3200 V0_EXPORT_DIR=/path/to/v0-export \
 *     pnpm screenshot:design
 *
 * Requires a running v0-export dev server (capture-design-screenshots.sh
 * starts one).
 *
 * Output: docs/images/auto/design/<route>.png
 */
import { test } from '@playwright/test'
import * as fs from 'node:fs'
import * as path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT_DIR = path.resolve(__dirname, '../../../docs/images/auto/design')
const APP_URL = process.env.E2E_DESIGN_URL || 'http://localhost:3200'
const V0_EXPORT_DIR = process.env.V0_EXPORT_DIR || ''

interface PageDef {
  name: string
  path: string
}

const FALLBACK_ROUTES: PageDef[] = [
  { name: 'home', path: '/' },
]

/**
 * Auto-discover static routes from a Next.js App Router layout.
 * v0.app exports place `app/` at the project root (not `src/app/`).
 */
function discoverRoutes(rootDir: string): PageDef[] {
  for (const candidate of [path.join(rootDir, 'app'), path.join(rootDir, 'src', 'app')]) {
    if (fs.existsSync(candidate)) {
      return walkAppDir(candidate)
    }
  }
  return []
}

function walkAppDir(appDir: string): PageDef[] {
  const routes: PageDef[] = []

  function walk(dir: string, prefix: string) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (!entry.isDirectory()) {
        if (entry.name === 'page.tsx' || entry.name === 'page.js') {
          if (prefix.includes('[') || prefix.includes('/api')) continue
          const routePath = prefix || '/'
          const name = routePath === '/' ? 'home' : routePath.slice(1).replace(/\//g, '-')
          routes.push({ name, path: routePath })
        }
        continue
      }
      if (entry.name.startsWith('[') || entry.name === 'api' || entry.name.startsWith('_')) continue
      const segment =
        entry.name.startsWith('(') && entry.name.endsWith(')') ? '' : `/${entry.name}`
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

const pages: PageDef[] = V0_EXPORT_DIR && fs.existsSync(V0_EXPORT_DIR)
  ? (discoverRoutes(V0_EXPORT_DIR).length ? discoverRoutes(V0_EXPORT_DIR) : FALLBACK_ROUTES)
  : FALLBACK_ROUTES

test.use({
  viewport: { width: 1280, height: 720 },
  baseURL: APP_URL,
})

test.describe('v0 design source screenshots', () => {
  for (const pageDef of pages) {
    test(`design — ${pageDef.name}`, async ({ page }) => {
      await page.goto(pageDef.path, { waitUntil: 'networkidle', timeout: 15_000 })
      await page.screenshot({
        path: path.join(OUT_DIR, `${pageDef.name}.png`),
        fullPage: true,
      })
    })
  }
})
