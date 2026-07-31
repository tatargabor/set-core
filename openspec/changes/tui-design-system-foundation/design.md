## Context

The dashboard is a Vite 7 + React 19 + Tailwind v4 SPA under `web/`, ~20 000 lines across ~40
component files. It has no component library and no `components.json` — measured: zero
`@radix-ui` occurrences in the tree.

Its visual language is defined in two places and nowhere else:

- `web/src/index.css` — 10 lines, setting a monospace `font-family` and `#0a0a0a` on `body`;
- `web/src/components/tui.tsx` — 80 lines, three components and a `statusColor()` helper.

That file is imported by **6 files**. The other ~34 re-derive the same decisions inline. This is
the mechanism behind every drift figure in the proposal, and it is also why the Orchestration
tabs look coherent (they were written together and import `tui.tsx`) while Project Status does
not (it is a later, independent renderer that does not).

Three constraints frame the work, all recorded rather than assumed:

1. **The terminal language stays.** Decided 2026-07-31: it is a differentiator, the audience is
   developers with occasional demo viewing, and a future customer-facing surface will be its own
   surface rather than a light skin of this one.
2. **Compacting must never hide a failure** — `.claude/rules/ui-quality.md`. Every primitive that
   shows less than it was given inherits this obligation.
3. **`web/` has a build product and that path is unmeasured** for the generated-artefact hybrid
   problem (`CLAUDE.md`). Verification runs against a freshly built bundle, never a cached one.

## Goals / Non-Goals

**Goals:**
- One place where a status colour is decided, and a test that keeps it that way.
- One module where a reusable visual pattern is implemented, with the three existing primitives
  unchanged in name and output.
- Keyboard and focus behaviour for the nine hand-rolled interactive sites, without adopting a
  component library's appearance.
- Project Status stops widening its rows by nesting depth, and stops building prose towers.
- The change is proven on one screen before the rest are migrated.

**Non-Goals:**
- Migrating Orchestration, Manager, Memory, Settings onto the primitives — follow-up change.
- Replacing the 58 `title=` tooltips. Native `title` is adequate here; a Radix Tooltip
  migration would touch 58 sites for no measured gain.
- A light theme, or a second skin. Tokens make one possible later; building one now would be
  designing for a surface whose requirements do not exist.
- Any change to the API layer, the status contract, or anything outside `web/`.
- Restyling Battle (`web/src/components/battle/`), exempt by prior decision.

## Decisions

### D1 — Tailwind v4 `@theme` tokens, not a JS token file or CSS variables by hand

Tailwind v4 reads `@theme` in CSS and generates utility classes from it, so
`--color-status-done: <value>` yields `text-status-done` with no config file and no build step.
Alternatives considered:

- **A TypeScript token object** (`tokens.ts`) consumed via template strings — rejected: Tailwind
  cannot see dynamic class names, so it would require a safelist, which is a second copy of the
  token list that drifts. This repo has already paid for a hand-maintained second copy once (the
  `PYTHONPATH` root list in `CLAUDE.md`).
- **Bare CSS custom properties with `style={{color: var(...)}}`** — rejected: it bypasses
  Tailwind's variant system, so hover/dark/responsive states stop composing.

The token names carry **meaning, not hue** — `status-fail`, not `status-red`. That is what makes
a future second surface reskinnable, and it is also what makes the drift test able to say
something true: a literal `text-red-400` in a component is a violation regardless of whether it
happens to be the right red today.

### D2 — Radix for behaviour, TUI for appearance; three packages, not shadcn

shadcn/ui is a copy-in generator over Radix plus a specific visual style. We want the first half
and not the second, and shadcn's value (the styling) is exactly the part we would delete. So we
take the three Radix packages directly: `react-popover`, `react-dialog`, `react-tabs`.

Sizing measured, so the cost is known rather than guessed: **2** popover/dropdown sites
(`StatusTable.tsx:577`, `manager/SentinelControl.tsx:92`), **3** modal sites
(`UnifiedSidebar.tsx`, `issues/IssueDetail.tsx`, `ChangeTable.tsx`), **4** hand-rolled tab strips
(`SentinelPage`, `IssueDetail`, `DigestView`, `Dashboard`). Nine sites. Against ~20 000 lines the
tree currently holds **12** `aria-*` attributes and **9** `onKeyDown` handlers — so keyboard
access is effectively absent, and this is the cheapest point at which to acquire it.

Alternative considered: **write the focus trap ourselves**. Rejected on evidence rather than
taste — a focus trap that is subtly wrong fails silently, which is the failure direction this
repo treats as most expensive.

### D3 — The drift test asserts the source tree, and is proven to fire

A Vitest unit test greps the component sources for the three banned patterns. Two design points,
both from `.claude/rules/evidence-discipline.md`:

- **Exemptions are an explicit in-test list with reasons**, never a loosened pattern. A pattern
  wide enough to let Battle through is also wide enough to let the next violation through, and
  nobody would notice.
- **The test is mutation-checked before its green is believed.** A known violation is introduced,
  the test must fail; removed, it must pass. A checker that cannot fail reports "clean" and
  "cannot detect" identically. The restore is verified by re-grepping the file, not assumed from
  the revert command — `git checkout` cannot restore an untracked file and says nothing when it
  fails.

The test also guards **its own corpus**: it must exclude itself, since the test file contains
every banned pattern as a string literal. This is the measurement-inside-the-corpus shape already
recorded in the rules, and here it fails toward a *permanent* failure rather than a silent pass —
noisy, but the safe direction.

### D4 — Project Status: remove the depth-based minimum width, add row-detail displacement

Two separate defects, and they need different fixes:

- **Width.** `StatusValue.tsx:344` applies `min-w-[18rem]` when `depth > 0`. It is deleted. A
  nested value lays out in the width it is given. The measurement that settles this: on a real
  answer, the value that broke the layout was the **15th longest** string on the surface, and the
  longest — about nine times its size — rendered fine. Truncating the producer's text would have
  treated a symptom that was not there.
- **Height.** A prose value in a cell wraps into a tower. It moves to a row-detail expansion, and
  the collapsed row states that it did — including a failure marker when the displaced value is
  in a failing state, because otherwise displacement becomes a place a broken thing can sit while
  the page looks calm.

Alternative considered: **truncate the cell text with a `title` tooltip**. Rejected — it is the
compact-that-hides shape the surface spec forbids, and a tooltip is unreachable on touch.

### D5 — Migrate the existing violations rather than grandfathering them

The 81 font sizes, 34 `font-mono` and 493 colour classes are replaced in this change, so the
drift test's baseline is zero. A grandfathered allowlist would be a third copy of the drift
figures, would need maintaining, and — the deciding reason — a test whose baseline is "494
violations, don't add a 495th" gets muted the first time it is inconvenient.

Most of this is mechanical (`text-[10px]` → `text-xs`, `text-blue-400` → `text-status-done`), but
mechanical is not automatic: `text-neutral-500` means "idle status" in some places and "muted
label" in others, and only the second should stay a neutral. That distinction is made by reading,
per file, and it is the bulk of the change's effort.

## Risks / Trade-offs

- **[The colour migration changes a screen's meaning without changing its appearance]** — a
  `text-neutral-500` that was a *status* becomes `text-status-idle`; if the mapping is wrong the
  screen looks identical and now lies. → The Playwright suite screenshots the affected screens
  before and after; a pixel change is expected only where a colour was genuinely inconsistent,
  and each such difference is examined rather than accepted in bulk.
- **[Deleting `min-w-[18rem]` may collapse narrow nested values to unreadable widths]** — the
  minimum was presumably added for a reason nobody recorded. → The fix is verified on a real
  project's answer, not on a fixture, and both the wide case (the table that overflowed) and the
  narrow case (a two-key object in a narrow column) are looked at. Per `ui-quality.md`,
  structural counts do not settle a layout question — someone looks at the screen.
- **[Radix ships its own focus and portal behaviour that may fight the existing layout]** — the
  status page is a `flex flex-col h-full overflow-hidden` column with its own scroll container. →
  Radix portals to `body` by default; the three sites are converted one at a time, each verified
  in the running app before the next.
- **[The drift test becomes the thing that blocks unrelated work]** — a developer adding a screen
  hits a failure about a colour class. → That is the intended cost, and the failure message names
  the file, the line and the token to use instead. The alternative is the current state, where the
  rule exists and is violated 608 times.
- **[The E2E suite drives the page with powers a user does not have]** — recorded in
  `evidence-discipline.md`: scripted scrolling passes on a page where user scrolling is broken. →
  Assertions about the new row-detail behaviour use `page.mouse` / real clicks, and the layout fix
  is mutation-checked: the old `min-w-[18rem]` is restored into a built bundle and the test must
  fail.

## Migration Plan

1. Tokens land first and coexist with the literal classes — nothing breaks, nothing is enforced.
2. The primitive module is created; `tui.tsx` re-exports from it so the six importing files are
   untouched in this step.
3. Project Status is converted onto the primitives and its two layout defects fixed. This is the
   proof screen; it is looked at, in the running app, before anything else proceeds.
4. The mechanical migration of the remaining violations, file by file.
5. The drift test is enabled last, and only once step 4 brings the count to zero — enabling it
   earlier would mean disabling it, and a test that has been disabled once is disabled again.

**Rollback:** every step is independently revertible; the tokens are additive, the primitive
module keeps the old entry point alive, and the drift test is a single file. No data, no schema,
no consumer contract is touched.

## Open Questions

- Does `--color-status-blocked` (orange) survive as its own meaning, or is it `warn`? The current
  code uses orange only for `merge-blocked`. Resolvable while writing the tokens; not a blocker.
- The Battle view's exemption is inherited from a prior decision whose reasoning is not recorded
  here. It stays exempt in this change; whether it should be is a question for the follow-up.
