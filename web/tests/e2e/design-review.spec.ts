/**
 * Design-review capture — the judgement half's raw material.
 *
 * Two images per screen, and the pair is the point:
 *
 *  - `-fold.png` is the viewport alone, at native size. It answers what a reader actually sees
 *    on arrival: is the space used, is the navigation findable, is anything cramped. Every one
 *    of those questions is about the fold, so a full-page capture cannot answer them — it
 *    removes the fold, which is the very boundary being judged.
 *  - `-full.png` is the whole document. It answers what the screen contains, which is a
 *    different question and the one a docs screenshot is usually after.
 *
 * The existing `screenshots.spec.ts` takes only the second kind, at 1280×720, into
 * `docs/images/auto/web/`. That is right for documentation and wrong for this: a review of
 * density conducted at a size nobody uses, with the fold discarded, and the result committed
 * into a public repository alongside a consumer's data.
 *
 * So this one goes to the runtime directory instead. The screens under review carry the
 * measured project's domain content — names, identifiers, free text — and this framework
 * persists nothing derived from a consumer's data into its own tree.
 *
 * Usage:
 *   E2E_PROJECT=<project> npx playwright test design-review --config=playwright.probe.config.ts
 */
import { test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import path from 'node:path'
import { PROJECT, STATIC_SCREENS, discoverTabs, settle } from './screens'

const RUN_ID = process.env.DESIGN_RUN_ID || new Date().toISOString().replace(/[:.]/g, '-')
const OUT_DIR = path.join(homedir(), '.local/share/set-core/design-review', RUN_ID, 'shots')

test.use({ viewport: { width: 1920, height: 1080 } })
test.describe.configure({ mode: 'serial' })

const shot = async (page: import('@playwright/test').Page, id: string) => {
  await page.screenshot({ path: path.join(OUT_DIR, `${id}-fold.png`), fullPage: false })
  await page.screenshot({ path: path.join(OUT_DIR, `${id}-full.png`), fullPage: true })
}

test('capture every screen', async ({ page }) => {
  test.setTimeout(15 * 60_000)
  mkdirSync(OUT_DIR, { recursive: true })

  const taken: string[] = []
  const empty: string[] = []

  for (const s of STATIC_SCREENS) {
    await page.goto(s.path)
    const arrived = await settle(page, s.waitFor)
    if (s.waitFor && !arrived) empty.push(s.id)
    await shot(page, s.id)
    taken.push(s.id)

    const attr = s.id === 'project-status' ? 'data-status-tab' : s.id === 'orch' ? 'data-tab' : null
    if (!attr) continue

    for (const t of await discoverTabs(page, attr)) {
      const el = page.locator(`[${attr}="${t}"]`).first()
      if (!(await el.count())) continue
      await el.click().catch(() => {})
      if (!(await settle(page))) empty.push(`${s.id}--${t}`)
      await shot(page, `${s.id}--${t}`)
      taken.push(`${s.id}--${t}`)
    }
  }

  writeFileSync(path.join(OUT_DIR, 'index.json'), JSON.stringify({ runId: RUN_ID, project: PROJECT, taken, empty }, null, 2))
  console.log(`\n[design-review] ${taken.length} screens × 2 images → ${OUT_DIR}`)
  if (empty.length) console.log(`[design-review] !! captured EMPTY (content never arrived): ${empty.join(', ')}`)
})
