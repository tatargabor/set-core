/**
 * The relation map in a real browser — the measurements a unit test cannot take.
 *
 * jsdom lays nothing out, so "opening a detail moves nothing" and "the map
 * takes no room from the page" are untestable there: every rectangle is zero
 * and any assertion about them passes. Here they are measured.
 *
 * The map's payload is FULFILLED at the network layer, for the reason the
 * install spec gives and with the same weakness: a fulfilled body encodes what
 * this file believes the producer sends. The last test is the anchor against
 * that — it reads the real route and asserts the fields the screen depends on.
 *
 * Nothing here starts, stops or instructs an agent; the only request the tests
 * make of the server is the one read.
 */
import { expect, test, type Page } from '@playwright/test'

const agent = (pid: number, label: string, seat: string | null, mandate: object | null, reason?: string) => ({
  pid, label, seat, state: 'quiet', population: 'started-here',
  mandate, mandate_absent: mandate ? null : { reason: reason ?? 'not-declared' },
})
const mandate = (kind: string, goal: string) => ({ id: `m-${goal.length}`, kind, goal, delivered: true, source: 'start' })
const engagement = (id: string, from: [string, number], to: [string, string | null, number | null],
                    state: string, waiting: boolean, age: number) => ({
  type: 'engagement', id, from_seat: from[0], from_pid: from[1], to_project: to[0], to_seat: to[1], to_pid: to[2],
  kind: 'REQUEST', subject: 'the export format', state, reason: state === 'failed' ? 'not-on-bus' : null,
  age_seconds: age, waiting,
})

const PAYLOAD = {
  projects: [
    { name: 'alpha', archived: false, expanded: true, agents: [
      agent(1, 'alpha-importer', 'alpha#1', mandate('work', 'ship the importer')),
      agent(2, 'alpha-1200', 'alpha#2', null),
    ] },
    { name: 'beta', archived: false, expanded: true, agents: [agent(9, 'beta-desk', 'beta#9', mandate('desk', 'Answer requests'))] },
    { name: 'gamma', archived: false, expanded: true, agents: [agent(20, 'gamma-work', 'gamma#20', mandate('work', 'migrate settings'))] },
    { name: 'delta', archived: false, expanded: false, agents: [] },
    { name: 'eta', archived: false, expanded: false, agents: [] },
  ],
  relations: [
    engagement('e-open', ['alpha#1', 1], ['beta', 'beta#9', 9], 'open', false, 240),
    engagement('e-wait', ['gamma#20', 20], ['beta', 'beta#9', 9], 'open', true, 4000),
    engagement('e-fail', ['alpha#2', 2], ['delta', null, null], 'failed', false, 600),
    { type: 'started', from_seat: 'alpha#1', from_pid: 1, to_pid: 2, to_seat: 'alpha#2', is_claim: true },
    { type: 'flow', from_project: 'alpha', to_project: 'gamma', what: 'a new field', how: null },
  ],
  counts: { no_mandate: 1, waiting: 1, failed: 1 },
  sources: { inventory: true, mandates: true, bus: true, roles: 'ok' },
}

type Rect = { x: number; y: number; width: number; height: number }
const rounded = (r: Rect) => [r.x, r.y, r.width, r.height].map(v => Math.round(v * 10) / 10).join(',')

async function rects(page: Page, selector: string): Promise<string[]> {
  return page.locator(selector).evaluateAll(els => els.map(el => {
    const b = el.getBoundingClientRect()
    return `${el.getAttribute('data-id') ?? ''}@${[b.x, b.y, b.width, b.height].map(v => Math.round(v * 10) / 10).join(',')}`
  }))
}

async function openFleet(page: Page) {
  await page.route('**/api/fleet/map', route => route.fulfill({ json: PAYLOAD }))
  await page.goto('/')
  await expect(page.locator('[data-fleet-map-toggle]')).toHaveAttribute('data-fleet-map-read', 'read', { timeout: 20_000 })
}

test('the closed control carries the counts, and opening the map moves nothing under it', async ({ page }) => {
  await openFleet(page)
  const toggle = page.locator('[data-fleet-map-toggle]')
  await expect(toggle.locator('[data-fleet-map-count="no-mandate"]')).toHaveText('1 no mandate')
  await expect(toggle.locator('[data-fleet-map-count="waiting"]')).toHaveText('1 waiting')
  await expect(toggle.locator('[data-fleet-map-count="failed"]')).toHaveText('1 failed')

  const header = page.locator('[data-fleet-phase] > div').first()
  const before = [rounded((await header.boundingBox())!), rounded((await toggle.boundingBox())!)]
  await toggle.click()
  await expect(page.locator('[data-fleet-map-panel]')).toBeVisible()
  await expect(page.locator('.react-flow__node')).not.toHaveCount(0)
  const after = [rounded((await header.boundingBox())!), rounded((await toggle.boundingBox())!)]
  expect(after).toEqual(before)
})

test('a detail opens above the map: the canvas keeps its size and no node moves', async ({ page }) => {
  await openFleet(page)
  await page.locator('[data-fleet-map-toggle]').click()
  await expect(page.locator('.react-flow__node[data-id="a:1"]')).toBeVisible()
  // Let the initial fit settle before the first measurement.
  await page.waitForTimeout(800)

  const canvas = page.locator('[data-fleet-map-canvas]')
  const measure = async () => ({
    canvas: rounded((await canvas.boundingBox())!),
    panel: rounded((await page.locator('[data-fleet-map-panel]').boundingBox())!),
    // The graph's own box: a detail that took a column of the canvas would
    // leave the canvas and every node where they were and shrink only this.
    graph: rounded((await page.locator('.react-flow').boundingBox())!),
    nodes: await rects(page, '.react-flow__node'),
    labels: await rects(page, '[data-fleet-map-edge-label]'),
  })
  const before = await measure()
  expect(before.nodes.length).toBeGreaterThanOrEqual(6)
  // A zero-sized canvas would make every comparison below pass for nothing.
  expect((await canvas.boundingBox())!.width).toBeGreaterThan(300)
  expect((await canvas.boundingBox())!.height).toBeGreaterThan(200)

  // A node's detail.
  await page.locator('.react-flow__node[data-id="a:1"]').click()
  const detail = page.locator('[data-fleet-map-detail]')
  await expect(detail).toBeVisible()
  await expect(detail).toContainText('ship the importer')
  expect(await measure()).toEqual(before)

  // It has its own way out, and closing it moves nothing either.
  await detail.locator('[data-fleet-map-detail-close]').click()
  await expect(detail).toHaveCount(0)
  expect(await measure()).toEqual(before)

  // An edge's detail, opened from its label.
  await page.locator('[data-fleet-map-edge-label="e:e-wait"]').click()
  await expect(detail).toContainText('No linked reply has arrived')
  expect(await measure()).toEqual(before)
})

test('the three relation kinds are drawn with three different strokes, and what is wrong is marked on its edge', async ({ page }) => {
  await openFleet(page)
  await page.locator('[data-fleet-map-toggle]').click()
  await expect(page.locator('.react-flow__edge')).toHaveCount(5)

  const dash = async (id: string) => page.locator(`.react-flow__edge[data-id="${id}"] path.react-flow__edge-path`)
    .evaluate(el => getComputedStyle(el).strokeDasharray)
  const kinds = [await dash('e:e-open'), await dash('s:2'), await dash('f:4')]
  expect(new Set(kinds).size).toBe(3)

  await expect(page.locator('[data-fleet-map-edge-label="e:e-wait"]')).toHaveText('⚠ waiting · 67m')
  await expect(page.locator('[data-fleet-map-edge-label="e:e-fail"]')).toHaveText('⚠ failed · 10m')
  await expect(page.locator('[data-fleet-map-edge-label="e:e-open"]')).toHaveText('open · 4m')
  await expect(page.locator('[data-fleet-map-agent="alpha-1200"]')).toHaveAttribute('data-fleet-map-no-mandate', 'yes')

  // No label is struck out by a line: every label is the top element at its own centre.
  const covered = await page.locator('[data-fleet-map-edge-label]').evaluateAll(els => els.filter(el => {
    const b = el.getBoundingClientRect()
    const top = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2)
    return top !== el
  }).map(el => el.getAttribute('data-fleet-map-edge-label')))
  expect(covered).toEqual([])
})

test('the real route answers with the shape the screen reads', async ({ page }) => {
  // The anchor: nothing fulfilled. If a field is renamed at the source, this
  // fails while every fulfilled test above stays green.
  //
  // It asks the route itself and does not wait for the header control: the real
  // map joins the whole inventory, which was measured at 3 s idle and past 20 s
  // on a loaded machine. A deadline on the CONTROL would then fail for load and
  // say nothing about the shape, which is the one thing this test is for.
  test.setTimeout(150_000)
  await page.goto('/')
  const body = await page.evaluate(() => fetch('/api/fleet/map').then(r => r.json()))
  expect(Array.isArray(body.projects)).toBe(true)
  expect(Array.isArray(body.relations)).toBe(true)
  for (const key of ['no_mandate', 'waiting', 'failed']) expect(typeof body.counts[key]).toBe('number')
  for (const key of ['inventory', 'mandates', 'bus']) expect(typeof body.sources[key]).toBe('boolean')
  expect(typeof body.sources.roles).toBe('string')
  for (const project of body.projects) {
    expect(typeof project.name).toBe('string')
    expect(typeof project.expanded).toBe('boolean')
    for (const a of project.agents) {
      expect('mandate' in a && 'mandate_absent' in a && 'label' in a && 'state' in a).toBe(true)
    }
  }
})
