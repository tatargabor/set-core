/**
 * Layout probe — the mechanical half of a design review.
 *
 * It answers the questions a screenshot cannot answer cheaply or repeatably: does this screen
 * scroll sideways, does a row tower over its neighbours, how much of the viewport is unused,
 * how many distinct type sizes are in play. Those are properties of the DOM, so they are
 * measured, not judged — which makes them regression-testable and keeps a human (or a model)
 * from re-deciding them screen by screen.
 *
 * What it deliberately does NOT do is call any of that a verdict. A number here says *where to
 * look*; whether the screen is good is settled by looking at it. This split is the whole point:
 * the mechanical pass narrows the corpus so the judgement pass can be thorough where it matters
 * instead of even everywhere.
 *
 * Output goes OUTSIDE the repository. The measured project's screens carry its domain data —
 * partner names, identifiers, free text — and this framework persists nothing derived from a
 * consumer's data into its own tree. The metrics are shapes and counts, but the element samples
 * would carry text, so the whole artifact stays in the runtime directory.
 *
 * Usage:
 *   E2E_PROJECT=<project> npx playwright test layout-probe --config=playwright.probe.config.ts
 */
import { test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import path from 'node:path'
import { PROJECT, STATIC_SCREENS, type Screen, discoverTabs, settle } from './screens'

const RUN_ID = process.env.DESIGN_RUN_ID || new Date().toISOString().replace(/[:.]/g, '-')
const OUT_DIR = path.join(homedir(), '.local/share/set-core/design-review', RUN_ID)

const VIEWPORT = { width: 1920, height: 1080 }

test.use({ viewport: VIEWPORT })
test.describe.configure({ mode: 'serial' })

/** One screen's measurements. Every field is a count or a pixel figure — no text content. */
interface Metrics {
  id: string
  label: string
  path: string
  tab: string | null
  /** Page-level sideways scroll in px. Anything > 0 means the reader must scroll to see a row. */
  pageOverflowX: number
  /** Total scrollable page height beyond the fold. */
  pageOverflowY: number
  /** Elements whose content is wider than their box, with whether the box was made scrollable. */
  overflowing: { tag: string; cls: string; over: number; scrollable: boolean }[]
  /** Per table: row count, median row height, tallest row, and how many exceed 3× the median. */
  tables: { rows: number; medianRowH: number; maxRowH: number; towers: number; cols: number }[]
  /** Unused horizontal band on the right, in px: viewport width minus the rightmost content edge. */
  unusedRightPx: number
  /** Unused vertical band at the bottom when the page does NOT scroll, in px. */
  unusedBottomPx: number
  /** Distinct computed font sizes actually rendered, with an occurrence count each. */
  fontSizes: Record<string, number>
  /** Elements rendered but effectively invisible in the fold (0-size boxes) — a render smell. */
  zeroSizeVisible: number
}

async function measure(page: import('@playwright/test').Page): Promise<Omit<Metrics, 'id' | 'label' | 'path' | 'tab'>> {
  return page.evaluate(() => {
    const de = document.documentElement
    const vw = window.innerWidth
    const vh = window.innerHeight

    const visible = (el: Element) => {
      const r = el.getBoundingClientRect()
      const s = getComputedStyle(el)
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0'
    }

    const all = Array.from(document.querySelectorAll('body *'))

    // ── Overflow: content wider than its box. `scrollable` separates a deliberate scroller
    //    (someone chose overflow-x-auto) from a box that is simply too small for its content.
    //    Both are findings; they have different fixes, so they are never merged into one count.
    const overflowing = all
      .filter(visible)
      .map((el) => {
        const over = el.scrollWidth - el.clientWidth
        const s = getComputedStyle(el)
        return {
          tag: el.tagName.toLowerCase(),
          cls: (el.className && typeof el.className === 'string' ? el.className : '').slice(0, 120),
          over,
          scrollable: s.overflowX === 'auto' || s.overflowX === 'scroll',
        }
      })
      .filter((o) => o.over > 2)
      .sort((a, b) => b.over - a.over)
      .slice(0, 12)

    // ── Tables: a tower is a row far taller than its peers. The median (not the mean) is the
    //    comparison, because one 14-line row drags a mean up and then compares itself to it.
    const tables = Array.from(document.querySelectorAll('table')).map((t) => {
      const rows = Array.from(t.querySelectorAll('tbody tr')).filter(visible)
      const hs = rows.map((r) => r.getBoundingClientRect().height).sort((a, b) => a - b)
      const median = hs.length ? hs[Math.floor(hs.length / 2)] : 0
      return {
        rows: rows.length,
        medianRowH: Math.round(median),
        maxRowH: Math.round(hs[hs.length - 1] || 0),
        towers: median > 0 ? hs.filter((h) => h > median * 3).length : 0,
        cols: t.querySelectorAll('thead th').length,
      }
    })

    // ── Unused space. Measured against elements that actually carry text, so a full-width
    //    transparent wrapper does not report the gutter as "used".
    const textEls = all.filter((el) => {
      if (!visible(el)) return false
      const own = Array.from(el.childNodes).some(
        (n) => n.nodeType === Node.TEXT_NODE && (n.textContent || '').trim().length > 0,
      )
      return own
    })
    const rects = textEls.map((el) => el.getBoundingClientRect())
    const rightEdge = rects.length ? Math.max(...rects.map((r) => r.right)) : 0
    const bottomEdge = rects.length ? Math.max(...rects.map((r) => r.bottom)) : 0
    const pageScrollsY = de.scrollHeight - de.clientHeight > 2

    const fontSizes: Record<string, number> = {}
    for (const el of textEls) {
      const fs = getComputedStyle(el).fontSize
      fontSizes[fs] = (fontSizes[fs] || 0) + 1
    }

    return {
      pageOverflowX: Math.max(0, de.scrollWidth - de.clientWidth),
      pageOverflowY: Math.max(0, de.scrollHeight - de.clientHeight),
      overflowing,
      tables,
      unusedRightPx: Math.max(0, Math.round(vw - rightEdge)),
      unusedBottomPx: pageScrollsY ? 0 : Math.max(0, Math.round(vh - bottomEdge)),
      fontSizes,
      zeroSizeVisible: all.filter((el) => {
        const r = el.getBoundingClientRect()
        const s = getComputedStyle(el)
        return r.width === 0 && r.height === 0 && s.display !== 'none' && (el.textContent || '').trim().length > 0
      }).length,
    }
  })
}

const results: Metrics[] = []
const coverage: { screen: string; tabsFound: number }[] = []
const notArrived: string[] = []

test('probe every screen', async ({ page }) => {
  test.setTimeout(10 * 60_000)

  for (const s of STATIC_SCREENS) {
    await page.goto(s.path)
    const arrived = await settle(page, s.waitFor)
    if (s.waitFor && !arrived) {
      // Recorded, never swallowed. A screen whose content never arrived yields metrics of an
      // empty page — all of which read as "nothing wrong here".
      notArrived.push(s.id)
      console.log(`[layout-probe] !! ${s.id}: "${s.waitFor}" never appeared — metrics are of an EMPTY page`)
    }
    results.push({ id: s.id, label: s.label, path: s.path, tab: null, ...(await measure(page)) })

    // Expand the screen into its tabs, discovered live.
    const attr = s.id === 'project-status' ? 'data-status-tab' : s.id === 'orch' ? 'data-tab' : null
    if (!attr) continue

    const tabs = await discoverTabs(page, attr)
    coverage.push({ screen: s.id, tabsFound: tabs.length })

    for (const t of tabs) {
      const sel = `[${attr}="${t}"]`
      const el = page.locator(sel).first()
      if (!(await el.count())) continue
      await el.click().catch(() => {})
      await settle(page)
      results.push({
        id: `${s.id}--${t}`,
        label: `${s.label} › ${t}`,
        path: s.path,
        tab: t,
        ...(await measure(page)),
      })
    }
  }

  mkdirSync(OUT_DIR, { recursive: true })
  writeFileSync(
    path.join(OUT_DIR, 'layout-metrics.json'),
    JSON.stringify({ runId: RUN_ID, project: PROJECT, viewport: VIEWPORT, coverage, notArrived, screens: results }, null, 2),
  )

  // The run states its own coverage. A findings count means nothing without the size of the
  // corpus it was taken from — a zero over three screens reads exactly like a zero over thirty.
  console.log(`\n[layout-probe] ${results.length} screens measured → ${OUT_DIR}/layout-metrics.json`)
  for (const c of coverage) console.log(`[layout-probe]   ${c.screen}: ${c.tabsFound} tabs discovered`)
  if (notArrived.length) console.log(`[layout-probe] EMPTY-PAGE metrics for: ${notArrived.join(', ')}`)
})
