/**
 * Task 9.17 — the install surface on its unhappy paths.
 *
 * The task's own words are the whole design: **assert what the SCREEN shows,
 * not what the installer returned** — the two differ exactly when the surface
 * is wrong. So nothing here reads a payload and calls that a pass; every
 * assertion is about rendered, visible text reached by clicking the controls a
 * person clicks.
 *
 * ## Which assertions are live, and why the rest are not
 *
 * Measured against the running server on 2026-08-19 before this file was
 * written, `dry_run` only, nothing written anywhere:
 *
 * | module on this project | answer |
 * |---|---|
 * | `starter`, `capacitor-nextjs` | 200, files to write, `changed_nothing: false` |
 * | `nextjs` | 200, 48 to write, 2 skipped (`scaffold, already present`) |
 * | `core-rules` | **409** `no module named 'core-rules' ships with this framework` |
 *
 * So the live system produces a **refusal** and a **report**, and it cannot
 * produce the other two: no module here has every one of its files present with
 * an install record (skips-everything), and **none of the three shipped
 * manifests declares `requires:`** — checked, not assumed — so the
 * missing-requirement refusal is unreachable from a click today.
 *
 * Those two therefore have their answers fulfilled at the network layer, and
 * that is a real weakness worth naming rather than hiding: **a fulfilled body
 * encodes what I believe the producer sends.** Rename `changed_nothing` at the
 * source and every fulfilled test here stays green while the screen goes wrong.
 *
 * That is what the first test is for. It runs a real click against the real
 * route and asserts three things that each go wrong if a field is renamed —
 * `dry_run` (the tense flips to "done"), `changed_nothing` (an "unstated"
 * warning appears), `written` (the file list disappears). It is the anchor; the
 * fulfilled tests describe rendering, and this one proves the shape is not a
 * fiction.
 *
 * ⚠ **Nothing in this file ever writes into a repository.** The one control
 * that would — `[data-fleet-install-for-real]` — is asserted and never clicked,
 * and the live test intercepts the route to fail loudly if a `dry_run: false`
 * body is ever sent from this suite.
 */
import { test, expect, type Page } from '@playwright/test'

const FLEET_CWD = process.env.E2E_FLEET_CWD || process.cwd().replace(/\/web$/, '')
const PROJECT_NAME = FLEET_CWD.split('/').filter(Boolean).pop()!

/** The offer is made for `not-connected` only — `installOffered` in `fleetInstall.ts`. */
const OFFERED_STATE = 'not-connected'

/**
 * Open THIS repository's modules panel, the way a person opens it.
 *
 * Two things here were learned by getting them wrong, and both are load-bearing:
 *
 *  - **`data-fleet-project` is on the ROW, not on the control.** The row also
 *    carries a drag handle and a group menu, so clicking its box is not the
 *    same act as choosing the project. The control is the button named after
 *    it, and a click on the row silently did nothing.
 *  - **Which project the panel is for must be ASSERTED, not assumed.** The
 *    column selects one by itself when nothing is chosen, and the one it lands
 *    on is whatever the arrangement puts first. With the selection click doing
 *    nothing, this suite drove the install surface of a project it never chose
 *    — on this machine, a consumer's repository. The panel is only *read*
 *    there, but the next click sends an install request, so the guard belongs
 *    before it rather than after: nothing proceeds until the panel says it
 *    belongs to this repository.
 *
 * The whole thing is a poll rather than a sequence because the fleet screen
 * re-renders on every discovery pass; a click can land while the strip is
 * moving, and clicking again is what a person does.
 */
async function openModules(page: Page) {
  await page.goto('/')
  const row = page.locator(`[data-fleet-project="${PROJECT_NAME}"]`).first()
  await expect(row).toBeVisible({ timeout: 20_000 })

  const anyPanel = page.locator('[data-fleet-install-panel]')
  const unmeasured = page.locator('[data-fleet-modules="unmeasured"]')
  await expect.poll(async () => {
    if (await anyPanel.count() > 0
        && await anyPanel.first().getAttribute('data-fleet-install-panel') === PROJECT_NAME) {
      return true
    }
    await row.getByRole('button', { name: PROJECT_NAME, exact: true })
      .click({ timeout: 5_000 }).catch(() => undefined)
    // A server that never measured the modules has nothing to offer and
    // nothing to refuse. That is a different screen, not a failing one — so it
    // ends the wait, and the skip below is what it ends in.
    if (await unmeasured.count() > 0) return true
    const toggle = page.locator('[data-fleet-modules="measured"]').first()
    if (await toggle.count() > 0 && await toggle.getAttribute('data-fleet-modules-open') !== 'on') {
      await toggle.click({ timeout: 5_000 }).catch(() => undefined)
    }
    return false
  }, {
    timeout: 30_000,
    intervals: [300, 500, 1000, 1000],
    message: `the modules panel for ${PROJECT_NAME} never opened — if another project's panel `
      + 'is open instead, the selection click did not take and NOTHING here may proceed',
  }).toBe(true)

  test.skip(await unmeasured.count() > 0,
            'this server did not report what modules the project has')

  const panel = page.locator(`[data-fleet-install-panel="${PROJECT_NAME}"]`)
  await expect(panel).toBeVisible()
  return panel
}

/**
 * Arrange the precondition, not the outcome.
 *
 * A row only offers a preview when the capability report calls it
 * `not-connected`, so reaching the refusal by clicking needs a row in that
 * state. This rewrites **that field and nothing else** — the install route is
 * left alone, so the refusal the screen renders is the live server's own.
 * `not-connected` is not an invented state either: it is what the same
 * capability reports on projects that do not hold those files.
 */
async function offerModule(page: Page, module: string) {
  await page.route('**/api/fleet/agents', async route => {
    if (route.request().method() !== 'GET') return route.fallback()
    const res = await route.fetch()
    const body = await res.json()
    for (const p of body.projects ?? []) {
      if (p.name !== PROJECT_NAME) continue
      for (const cap of p.capabilities?.capabilities ?? []) {
        if (cap.name === module) cap.state = OFFERED_STATE
      }
    }
    await route.fulfill({ response: res, json: body })
  })
}

/** Answer the install route with one report, and record what was asked for. */
async function answerInstall(page: Page, answer: { status?: number; body: unknown }) {
  const asked: { module?: string; dry_run?: boolean }[] = []
  await page.route('**/api/fleet/projects/*/install', async route => {
    asked.push(JSON.parse(route.request().postData() || '{}'))
    await route.fulfill({
      status: answer.status ?? 200,
      contentType: 'application/json',
      body: JSON.stringify(answer.body),
    })
  })
  return asked
}

test.describe('task 9.17 — the install surface, driven by clicking', () => {
  test('LIVE: the real route answers a preview, and the screen says preview', async ({ page }) => {
    // Guard, not decoration: this suite must never cause a write, and the guard
    // belongs where the effect is. Anything but `dry_run: true` fails here
    // rather than reaching the installer.
    const sent: { module?: string; dry_run?: boolean }[] = []
    await page.route('**/api/fleet/projects/*/install', async route => {
      const body = JSON.parse(route.request().postData() || '{}')
      sent.push(body)
      if (body.dry_run !== true) {
        await route.abort('blockedbyclient')
        return
      }
      await route.continue()
    })

    const panel = await openModules(page)
    const offered = panel.locator(`[data-fleet-capability-state="${OFFERED_STATE}"]`).first()
    test.skip(await offered.count() === 0, 'no module on this project is offered for install')
    const module = (await offered.getAttribute('data-fleet-capability'))!

    await panel.locator(`[data-fleet-install-preview="${module}"]`).click()
    const report = panel.locator(`[data-fleet-install-report="${module}"]`)
    await expect(report).toBeVisible({ timeout: 20_000 })

    // The preview asked for a preview. This is the default that makes "I
    // clicked it to see what it does" a non-destructive act.
    expect(sent).toEqual([{ module, dry_run: true }])

    // ── the three rename detectors ──────────────────────────────────────────
    // `dry_run`: gone, and `reportTense` reads undefined as falsy → 'done'.
    await expect(report.locator('[data-fleet-install-tense="preview"]')).toBeVisible()
    await expect(report.locator('[data-fleet-install-tense="done"]')).toHaveCount(0)
    await expect(report).toContainText('nothing has been written yet')
    await expect(report).toContainText(/would write/)

    // `changed_nothing`: gone, and a missing field renders the amber "the
    // report did not say" line. Its ABSENCE here is the assertion.
    await expect(report.locator('[data-fleet-install-changed="unstated"]')).toHaveCount(0)

    // `written`: gone, and the file list disappears with it.
    await expect(report.locator('[data-fleet-install-written]')).toBeVisible()

    // The write is offered, names its blast radius, and is NOT clicked.
    const forReal = report.locator(`[data-fleet-install-for-real="${module}"]`)
    await expect(forReal).toBeVisible()
    await expect(forReal).toContainText('install for real')
    await expect(forReal).toContainText(FLEET_CWD)
  })

  test('an install that skips every file shows every skip, with its reason, unfolded', async ({ page }) => {
    // The producer's real skip shape, copied from a measured answer:
    // `{path, reason}` — `nextjs` returned `.gitignore — scaffold, already present`.
    // The third has no reason on purpose: an unexplained skip is the exact
    // silence the installer's contract forbids, and this asserts the surface
    // does not put that silence back by hiding it.
    const asked = await answerInstall(page, {
      body: {
        module: 'starter', project: PROJECT_NAME, dry_run: true,
        written: [],
        skipped: [
          { path: '.claude/rules/a.md', reason: 'scaffold, already present' },
          { path: '.claude/rules/b.md', reason: 'protected by the manifest' },
          { path: '.claude/rules/c.md', reason: '' },
        ],
        changed_nothing: true,
        lines: [],
      },
    })
    await offerModule(page, 'starter')

    const panel = await openModules(page)
    await panel.locator('[data-fleet-install-preview="starter"]').click()
    const report = panel.locator('[data-fleet-install-report="starter"]')
    await expect(report).toBeVisible({ timeout: 20_000 })
    expect(asked).toEqual([{ module: 'starter', dry_run: true }])

    const skips = report.locator('[data-fleet-install-skipped="3"]')
    await expect(skips).toBeVisible()

    // Every path AND every reason legible, at the same weight as a write would be.
    await expect(skips).toContainText('.claude/rules/a.md')
    await expect(skips).toContainText('scaffold, already present')
    await expect(skips).toContainText('.claude/rules/b.md')
    await expect(skips).toContainText('protected by the manifest')

    // The unexplained one is SAID to be unexplained, not rendered as a bare path.
    await expect(skips).toContainText('.claude/rules/c.md')
    await expect(skips).toContainText('no reason given')
    await expect(skips.locator('[data-fleet-install-skip-stated="no"]')).toHaveCount(1)
    await expect(skips.locator('[data-fleet-install-skip-stated="yes"]')).toHaveCount(2)

    // `ui-quality.md`: compacting must never hide a failure. The skips are the
    // half a "done" would hide, so they may not sit behind a fold — asserted
    // structurally, because "it happened to be open" is not the same claim.
    expect(await skips.evaluate(el => el.closest('details') !== null)).toBe(false)

    // Nothing was written, so there is no file list claiming otherwise.
    await expect(report.locator('[data-fleet-install-written]')).toHaveCount(0)
  })

  test('an install that writes nothing says so — from the producer\'s own field', async ({ page }) => {
    await answerInstall(page, {
      body: {
        module: 'starter', project: PROJECT_NAME, dry_run: true,
        written: [], skipped: [], changed_nothing: true, lines: [],
      },
    })
    await offerModule(page, 'starter')

    const panel = await openModules(page)
    await panel.locator('[data-fleet-install-preview="starter"]').click()
    const report = panel.locator('[data-fleet-install-report="starter"]')
    await expect(report).toBeVisible({ timeout: 20_000 })

    await expect(report.locator('[data-fleet-install-changed="nothing"]')).toBeVisible()
    await expect(report).toContainText('this install wrote no files')
    await expect(report).toContainText(/would write no files/)
    // The outcome most often misread as failure is stated, not left as a blank.
    await expect(report.locator('[data-fleet-install-changed="unstated"]')).toHaveCount(0)
  })

  test('a MISSING changed_nothing is not a measured zero — it says it does not know', async ({ page }) => {
    // The false-absence class from `.claude/rules/evidence-discipline.md`, at
    // the one place on this screen where it can happen: `written: []` with the
    // field absent. Deriving "nothing was written" from an empty list is a
    // second copy of the producer's rule — and it is the copy that reads as
    // success exactly when the answer is unknown.
    await answerInstall(page, {
      body: {
        module: 'starter', project: PROJECT_NAME, dry_run: true,
        written: [], skipped: [], lines: [],
      },
    })
    await offerModule(page, 'starter')

    const panel = await openModules(page)
    await panel.locator('[data-fleet-install-preview="starter"]').click()
    const report = panel.locator('[data-fleet-install-report="starter"]')
    await expect(report).toBeVisible({ timeout: 20_000 })

    await expect(report.locator('[data-fleet-install-changed="unstated"]')).toBeVisible()
    await expect(report).toContainText('the report did not say whether anything was written')
    // And it must NOT be drawn as the measured "wrote no files" outcome.
    await expect(report.locator('[data-fleet-install-changed="nothing"]')).toHaveCount(0)
    await expect(report).not.toContainText('this install wrote no files')
  })

  test('LIVE: a refusal from the real server is terminal — no write is offered beside it', async ({ page }) => {
    // The refusal is the live server's own; only the offer gate is arranged, so
    // that a row the framework refuses can be reached by clicking at all. On
    // this project `core-rules` is reported `partial`, and `partial` is
    // deliberately not offered — see `installOffered`.
    const CAP = 'core-rules'
    await offerModule(page, CAP)

    const panel = await openModules(page)
    const row = panel.locator(`[data-fleet-capability="${CAP}"]`)
    test.skip(await row.count() === 0, `this project does not report a '${CAP}' capability`)
    await panel.locator(`[data-fleet-install-preview="${CAP}"]`).click()

    const refusal = row.locator('[data-fleet-install-refusal="refused"]')
    await expect(refusal).toBeVisible({ timeout: 20_000 })
    // 409 is a verdict on the state, not a server falling over. Rendering it as
    // `failed` would tell the reader to retry instead of to fix something.
    await expect(row.locator('[data-fleet-install-refusal="failed"]')).toHaveCount(0)
    await expect(refusal).toContainText('refused:')
    // The server's own sentence, verbatim — it is the only thing that says what
    // to fix. Measured live: "no module named 'core-rules' ships with this framework".
    await expect(refusal).toContainText(CAP)

    // Terminal: no report to authorise, and above all no write offered. A
    // warning is something a reader clicks past, and past this one is a
    // half-installed project nobody chose.
    await expect(row.locator(`[data-fleet-install-report="${CAP}"]`)).toHaveCount(0)
    await expect(row.locator(`[data-fleet-install-for-real="${CAP}"]`)).toHaveCount(0)
  })

  test('a refusal for a MISSING REQUIREMENT reaches the reader word for word', async ({ page }) => {
    // The task's third case. It cannot be produced by clicking today: none of
    // the shipped manifests declares `requires:`, so `check_requirements` has
    // nothing to find — verified, not assumed. The wording below is the
    // installer's own, from `module_install.py`.
    //
    // What this asserts that the live refusal above does not: the requirement's
    // sentence survives to the screen intact. A refusal summarised to "install
    // refused" is a screen that tells the reader something is wrong and not
    // what — and the missing prerequisite's name is the entire actionable part.
    await answerInstall(page, {
      status: 409,
      body: {
        detail: "module 'capacitor-nextjs' is not installed: "
          + "requires module 'nextjs', which this project does not have",
      },
    })
    await offerModule(page, 'starter')

    const panel = await openModules(page)
    const row = panel.locator('[data-fleet-capability="starter"]')
    await panel.locator('[data-fleet-install-preview="starter"]').click()

    const refusal = row.locator('[data-fleet-install-refusal="refused"]')
    await expect(refusal).toBeVisible({ timeout: 20_000 })
    await expect(refusal).toContainText('is not installed')
    await expect(refusal).toContainText("requires module 'nextjs'")
    await expect(refusal).toContainText('which this project does not have')
    await expect(row.locator('[data-fleet-install-for-real="starter"]')).toHaveCount(0)
  })
})
