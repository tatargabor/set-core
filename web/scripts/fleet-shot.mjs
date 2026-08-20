/**
 * Take a real screenshot of the running fleet screen, so a human — or an agent
 * that can read images — can LOOK at it.
 *
 * This is the fallback for `ui-quality.md`'s visual-check rule when the Chrome
 * extension is not connected. It is NOT a screenshot test: nothing is compared
 * against a stored baseline, because a baseline comparison would go green on an
 * empty panel that was already empty. The output is a picture somebody looks at.
 */
import { chromium } from '@playwright/test'

const OUT = process.argv[2] || '/tmp/fleet.png'
const URL = process.argv[3] || 'http://127.0.0.1:7400/fleet'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1800, height: 1000 } })

const errors = []
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
page.on('pageerror', e => errors.push(String(e)))

await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 })
// The screen fetches on its own schedule; wait for a project row rather than a
// fixed delay, so a slow answer does not get photographed as an empty screen.
await page.waitForSelector('[data-fleet-project-column-width], [data-fleet-phase]', { timeout: 20000 })
    .catch(() => {})
await page.waitForTimeout(2500)

await page.screenshot({ path: OUT, fullPage: false })

// What the picture cannot say by itself.
const facts = await page.evaluate(() => ({
  docked: document.querySelectorAll('[data-fleet-dock]').length,
  tiles: document.querySelectorAll('[data-tile-controls]').length,
  splitters: document.querySelectorAll('[role="separator"]').length,
  unknownPanels: document.querySelector('[data-fleet-unknown-panels]')?.getAttribute('data-fleet-unknown-panels') ?? null,
  overflow: !!document.querySelector('[data-fleet-dock-overflow]'),
  bodyScrollsSideways: document.body.scrollWidth > document.body.clientWidth,
}))
console.log(JSON.stringify({ out: OUT, errors, ...facts }, null, 2))
await browser.close()
