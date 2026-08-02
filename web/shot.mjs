import { chromium } from '@playwright/test'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1600, height: 1000 } })
const errs = []
p.on('console', m => { if (m.type() === 'error') errs.push(m.text()) })
await p.goto(process.argv[2], { waitUntil: 'domcontentloaded' })
await p.waitForTimeout(28000)
const tab = p.locator('button', { hasText: 'history' }).first()
if (await tab.count()) { await tab.click(); await p.waitForTimeout(2500) }
await p.screenshot({ path: process.argv[3], fullPage: true })
console.log('js errors:', errs.length ? errs.slice(0,2) : 'none')
await b.close()
