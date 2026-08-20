/**
 * B-29 — the terminal's last row must be fully visible, at every window height.
 *
 * ## Why this is measured in pixels, and in the browser
 *
 * `.claude/rules/evidence-discipline.md`: *the check verifies the MECHANISM and
 * is silent about the RESULT*. A test that asserts `FitAddon.fit()` ran, or that
 * `term.rows` changed, passes on a screen whose bottom row is cut in half —
 * because fitting is the mechanism and being visible is the result. So this
 * measures the rendered row's rectangle against the two boxes that can cut it:
 * the host's own client box, and the window.
 *
 * ## Why the LAST row specifically
 *
 * A terminal program puts its status line on its last row. Losing it is not
 * losing a row; it is losing the one row that says what the agent is doing. And
 * it fails in the reassuring direction — everything above it looks normal.
 *
 * ## Why several heights rather than one
 *
 * The two mechanisms this guards appear at different sizes. The border rounding
 * only shows at heights that land just under a row multiple; the overflow only
 * shows once the card runs out of room. One height would have missed one of
 * them — as the first, single-height version of this probe did.
 *
 * ⚠ This spec STARTS ITS OWN AGENT and stops it again, for the reason the
 * sibling terminal spec states: typing into somebody's live session is not a
 * test, it is an interruption.
 */
import { test, expect, type APIRequestContext } from '@playwright/test'

const LABEL = `e2e-fleet-terminal-fits-${process.pid}`
const FLEET_CWD = process.env.E2E_FLEET_CWD || process.cwd().replace(/\/web$/, '')
const PROJECT_NAME = FLEET_CWD.split('/').filter(Boolean).pop()!

/** Heights that between them exercise both mechanisms — see the header. */
const HEIGHTS = [708, 600, 520, 480, 440, 400]

async function startAgent(request: APIRequestContext): Promise<{ pid: number } | null> {
  // An explicit timeout so a hung server reports AS a hung server. Without it
  // the call runs to the test timeout and the run reads as a product failure —
  // the exact misreading `evidence-discipline.md` records for this suite.
  const owner = await request.get('/api/fleet/owner', { timeout: 15_000 })
  if (!owner.ok()) return null
  if (!(await owner.json()).available) return null
  const res = await request.post('/api/fleet/agents', {
    timeout: 30_000,
    data: { label: LABEL, cwd: FLEET_CWD, rows: 30, cols: 100, requested_by: 'e2e' },
  })
  if (!res.ok()) return null
  return await res.json()
}

test('B-29 — the last terminal row is fully visible at every window height', async ({ page, request }) => {
  test.setTimeout(180_000)
  const started = await startAgent(request)
  test.skip(started === null, 'the agent owner is not available on this machine')
  try {
    await page.setViewportSize({ width: 1258, height: HEIGHTS[0] })
    await page.goto('/')
    await page.locator(`[data-fleet-project="${PROJECT_NAME}"]`).first().click({ timeout: 20_000 })
    const open = page.locator(`[data-fleet-terminal-open="${LABEL}"]`)
    await expect(open).toBeVisible({ timeout: 30_000 })
    await open.click()
    await expect(page.locator('[data-fleet-terminal-phase="attached"]').first())
      .toBeVisible({ timeout: 30_000 })
    // The enlarged view is the one the report came from, and it is the one where
    // the card runs out of room first.
    const full = page.locator('[data-fleet-terminal-full="off"]').first()
    if (await full.count()) await full.click({ timeout: 15_000 })
    await page.waitForTimeout(4000)

    const cut: string[] = []
    for (const h of HEIGHTS) {
      await page.setViewportSize({ width: 1258, height: h })
      await page.waitForTimeout(900)
      const m = await page.evaluate(() => {
        const host = document.querySelector('[data-fleet-terminal-host]') as HTMLElement | null
        if (!host) return null
        const hr = host.getBoundingClientRect()
        const borderTop = parseFloat(getComputedStyle(host).borderTopWidth || '0')
        const clientBottom = hr.top + borderTop + host.clientHeight
        const rows = host.querySelectorAll('.xterm-rows > div')
        if (!rows.length) return null
        const last = (rows[rows.length - 1] as HTMLElement).getBoundingClientRect()
        const limit = Math.min(clientBottom, window.innerHeight)
        return {
          rows: rows.length,
          rowHeight: +last.height.toFixed(1),
          visible: +Math.max(0, Math.min(last.bottom, limit) - last.top).toFixed(1),
          overClient: +(last.bottom - clientBottom).toFixed(1),
          overWindow: +(last.bottom - window.innerHeight).toFixed(1),
        }
      })
      expect(m, `no terminal rows rendered at height ${h}`).not.toBeNull()
      // Printed, not asserted: how short the terminal gets is a fact worth
      // seeing in the run, and a threshold nobody has measured is not a rule.
      console.log(`  height ${h}: ${m!.rows} rows, last row ${m!.visible}/${m!.rowHeight} px`)
      // A 0.5 px tolerance for sub-pixel layout; anything more is a cut row.
      if (m!.visible < m!.rowHeight - 0.5) {
        cut.push(`height ${h}: last row ${m!.visible}/${m!.rowHeight} px visible `
          + `(past the host by ${m!.overClient} px, past the window by ${m!.overWindow} px)`)
      }
    }
    expect(cut, `the status row was cut at ${cut.length} of ${HEIGHTS.length} heights:\n` + cut.join('\n'))
      .toEqual([])
  } finally {
    await request.post(`/api/fleet/agents/${LABEL}/stop`).catch(() => undefined)
  }
})
