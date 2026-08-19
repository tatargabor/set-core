/**
 * Tasks 9.5, 9.6, 9.7 — the fleet screen, driven the way a person drives it.
 *
 * The rule these three share is stated in `.claude/rules/evidence-discipline.md`
 * and it is why they are here rather than in the unit suite: **the harness
 * usually has powers the user does not.** A test that writes to the pty's file
 * descriptor and reads the echo proves the plumbing and says nothing about the
 * product — `overflow: hidden` disables *user* scrolling, not programmatic
 * scrolling, and a handler called directly fires on a control the user cannot
 * reach. So every assertion below goes through the browser: a keystroke is
 * typed, a button is clicked, a response is intercepted.
 *
 * ⚠ This spec STARTS ITS OWN AGENT and stops it again. It deliberately does not
 * borrow one that is already running: typing into somebody's live session is not
 * a test, it is an interruption.
 */
import { test, expect, type APIRequestContext } from '@playwright/test'

const LABEL = `e2e-fleet-terminal-${process.pid}`
const FLEET_CWD = process.env.E2E_FLEET_CWD || process.cwd().replace(/\/web$/, '')
const PROJECT_NAME = FLEET_CWD.split('/').filter(Boolean).pop()!

async function startAgent(request: APIRequestContext): Promise<{ pid: number } | null> {
  const owner = await request.get('/api/fleet/owner')
  if (!owner.ok()) return null
  const state = await owner.json()
  if (!state.available) return null
  const res = await request.post('/api/fleet/agents', {
    data: { label: LABEL, cwd: FLEET_CWD, rows: 30, cols: 100, requested_by: 'e2e' },
  })
  if (!res.ok()) return null
  return await res.json()
}

test.describe('task 9.5 — a keystroke typed in the browser reaches the agent', () => {
  test('and the agent\'s output comes back to the same component', async ({ page, request }) => {
    const started = await startAgent(request)
    test.skip(started === null, 'the agent owner is not available on this machine')
    try {
      await page.goto('/')
      // A person selects the project FIRST — the right-hand panel shows the
      // selected project's agents and nothing else. Skipping this step and
      // reaching straight for a tile would be the harness using a route the
      // user does not have.
      await page.locator(`[data-fleet-project="${PROJECT_NAME}"]`).first().click()

      // Keyed by the LABEL we started it under, which is the identity the owner
      // and the surface share. A person opens the terminal by CLICKING this
      // control; if it is absent this fails here, which is the point — an agent
      // the framework just started must be offered one.
      const open = page.locator(`[data-fleet-terminal-open="${LABEL}"]`)
      await expect(open).toBeVisible({ timeout: 20_000 })
      await open.click()
      await expect(page.locator('[data-fleet-terminal-phase="attached"]').first())
        .toBeVisible({ timeout: 20_000 })

      // The replayed screen must arrive before anything is typed — otherwise a
      // pass could come from the agent's own start-up output rather than from
      // the keystroke.
      const host = page.locator('[data-fleet-terminal-host]').first()
      await expect(host).toBeVisible()
      await page.waitForTimeout(1500)
      const before = (await host.innerText()).length

      // TYPED, through the browser's own keyboard. `page.keyboard.type` goes
      // through the same event path a person's keystroke does; writing to the
      // pty fd from the test would prove the plumbing and nothing about this.
      await host.click()
      await page.keyboard.type('echo set-core-e2e-marker')
      await expect
        .poll(async () => (await host.innerText()).includes('set-core-e2e-marker'),
              { timeout: 15_000, message: 'the typed characters never reached the terminal' })
        .toBe(true)
      expect((await host.innerText()).length).toBeGreaterThan(before)
    } finally {
      await request.post(`/api/fleet/agents/${LABEL}/stop`).catch(() => undefined)
    }
  })
})

test.describe('task 9.6 — the negative half', () => {
  test('an agent the framework did not start is offered no terminal at all', async ({ page, request }) => {
    const res = await request.get('/api/fleet/agents')
    expect(res.ok()).toBeTruthy()
    const body = await res.json()
    const foreign = body.projects
      .flatMap((p: any) => p.agents)
      .filter((a: any) => a.population === 'foreign')
    test.skip(foreign.length === 0, 'no foreign session is running on this machine')

    const victim = foreign[0]
    await page.goto('/')
    await page.locator(`[data-fleet-project="${victim.project}"]`).first().click()

    // The card that carries this agent's name. Scoped rather than page-wide,
    // because the project may hold agents the framework DID start and a page-wide
    // "no terminal offered" would then be asserting the opposite of the truth.
    const card = page.locator('[data-fleet-ownership]')
      .filter({ hasText: victim.name ?? String(victim.pid) }).first()
    await expect(card).toBeVisible({ timeout: 20_000 })

    // A positive-only check passes on a build that offers a terminal for every
    // agent, which is exactly the build this assertion exists to fail.
    await expect(card.locator('[data-fleet-terminal-open]')).toHaveCount(0)
    // …and the reason is SHOWN rather than the control merely being missing:
    // silence would leave a reader wondering whether the screen is broken.
    await expect(card.locator('[data-fleet-terminal-absent]').first()).toBeVisible()
  })
})

test.describe('task 9.7 — the pre-answer state', () => {
  test('says it is looking, and shows no zero while discovery is outstanding', async ({ page }) => {
    // Discovery held open, so the screen is observed in the state it passes
    // through too fast to see otherwise. Intercepting the response is the only
    // way to hold it — and it holds the PRODUCER, not the renderer, so what is
    // measured is still the screen's own behaviour.
    let release: (() => void) | null = null
    const held = new Promise<void>(res => { release = res })
    await page.route('**/api/fleet/agents*', async route => {
      await held
      await route.continue()
    })

    await page.goto('/', { waitUntil: 'commit' })
    await expect(page.locator('[data-fleet-phase="looking"]')).toBeVisible({ timeout: 15_000 })

    // The rule that matters: a screen with no answer must not render a COUNT.
    // A zero here is an answer nobody gave — the false-absence class, arriving
    // through a field that looks like data.
    const text = (await page.locator('body').innerText()).toLowerCase()
    expect(text).not.toMatch(/\b0 agents?\b/)
    expect(text).not.toMatch(/\b0 waiting for an answer\b/)
    expect(text).not.toMatch(/\bidle\b/)

    release!()
    // …and once the answer arrives the screen stops saying it is looking, so the
    // assertion above is about a TRANSIENT state and not about a stuck one. A
    // test that only saw the first half would pass on a screen that never
    // finishes looking, which is a worse bug than the one it guards.
    await expect(page.locator('[data-fleet-phase="looking"]')).toHaveCount(0, { timeout: 20_000 })
    await expect(page.locator('[data-fleet-project]').first()).toBeVisible({ timeout: 20_000 })
  })
})
