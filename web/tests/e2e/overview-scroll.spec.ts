/**
 * The overview must be reachable to its last row BY THE USER.
 *
 * This guards a failure that is completely silent: the layout's <main> carried
 * `overflow-hidden`, so a project list taller than the viewport was simply cut
 * off — no scrollbar, no console error, and 993px of rows that no input could
 * reach.
 *
 * Every scroll here is driven by the mouse wheel, and that is the whole point.
 * `element.scrollTo()` SUCCEEDS on an `overflow: hidden` box — such a box is
 * still programmatically scrollable, it merely refuses user input. Measured:
 * the first version of this file scrolled with `scrollTo()` and passed all four
 * assertions against a bundle rebuilt with the bug back in. Scripted scrolling
 * is a proxy for scrolling; the wheel is the thing.
 *
 * The viewport is deliberately small so the assertions do not depend on how
 * many projects happen to be registered on the machine running it.
 */
import { test, expect, type Page } from '@playwright/test'

test.use({ viewport: { width: 900, height: 320 } })

const mainMetrics = (page: Page) =>
  page.evaluate(() => {
    const el = document.querySelector('main')!
    return { scrollTop: el.scrollTop, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight }
  })

/** Wheel over the list until it stops moving, so the assertion is about the bottom. */
async function wheelToBottom(page: Page) {
  await page.mouse.move(450, 200)
  let last = -1
  for (let i = 0; i < 25; i++) {
    await page.mouse.wheel(0, 400)
    await page.waitForTimeout(80)
    const { scrollTop } = await mainMetrics(page)
    if (scrollTop === last) break
    last = scrollTop
  }
  return last
}

test.beforeEach(async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('tbody tr').first()).toBeVisible()
})

test('the wheel scrolls an overflowing list to its bottom', async ({ page }) => {
  const before = await mainMetrics(page)
  expect(before.scrollHeight,
    'fixture is too short to prove anything — shrink the viewport further',
  ).toBeGreaterThan(before.clientHeight + 4)
  expect(before.scrollTop, 'should start at the top').toBe(0)

  await wheelToBottom(page)
  const after = await mainMetrics(page)

  expect(after.scrollTop, 'the wheel moved nothing — the container refuses user input').toBeGreaterThan(0)
  expect(after.scrollTop + after.clientHeight).toBeGreaterThanOrEqual(after.scrollHeight - 2)
})

test('the last row is reachable with the wheel', async ({ page }) => {
  await wheelToBottom(page)
  await expect(page.locator('tbody tr').last()).toBeInViewport()
})

test('the column header stays visible while scrolling', async ({ page }) => {
  // A sticky header is not decoration here: scrolled past it, a column of bare
  // numbers ("6/9", "14.5M", "8 closed") cannot be told apart.
  await wheelToBottom(page)
  const head = await page.locator('thead').boundingBox()
  expect(head, 'thead has no box').not.toBeNull()
  expect(head!.y).toBeGreaterThanOrEqual(0)
  expect(head!.y).toBeLessThan(60)
  await expect(page.locator('thead')).toBeInViewport()
})

test('no element under main hides overflow it actually has', async ({ page }) => {
  // The direct form of the defect, stated as a property rather than a symptom:
  // a box taller than itself whose overflow-y is `hidden` has content that no
  // input can reach. `visible` is fine (it spills into a scrollable ancestor);
  // `auto`/`scroll` is fine (it scrolls). Only `hidden` traps.
  const trapped = await page.evaluate(() => {
    const els = [document.querySelector('main')!, ...document.querySelectorAll('main *')]
    return els
      .filter(el => getComputedStyle(el).overflowY === 'hidden' && el.scrollHeight > el.clientHeight + 4)
      .map(el => `${el.tagName.toLowerCase()}.${(el.className || '').toString().slice(0, 60)}`)
  })
  expect(trapped, 'content is clipped with no way to scroll to it').toEqual([])
})

test('there is no second scrollbar competing with the page', async ({ page }) => {
  // Two nested scroll regions is the usual regression when this gets "fixed".
  const innerScrollers = await page.evaluate(() =>
    [...document.querySelectorAll('main *')].filter(el => {
      const cs = getComputedStyle(el)
      return /auto|scroll/.test(cs.overflowY) && el.scrollHeight > el.clientHeight + 4
    }).length,
  )
  expect(innerScrollers).toBe(0)
})
