# Design: docs-screenshot-pipeline

## Context

We have a working Playwright E2E test suite in `web/tests/e2e/` and an initial `screenshots.spec.ts` that captures 8 dashboard tabs. The docs currently reference ~15 manual PNG/GIF files in `docs/images/` and 10 rendered diagrams in `docs/howitworks/`. We want to make ALL screenshots auto-generated so they stay fresh as the UI evolves.

### Current state
- `web/tests/e2e/screenshots.spec.ts` — captures 8 dashboard tabs + manager page
- `docs/images/` — 15 manual screenshots (control-center GIFs, TUI screenshots, etc.)
- `docs/images/web-dashboard/` — 8 auto-generated PNGs (from current screenshots.spec.ts)
- CLI tools have no screenshot infrastructure
- Consumer app screenshots are manual (referenced in benchmark docs)

## Goals / Non-Goals

**Goals:**
- Single `make screenshots` to regenerate everything
- All web dashboard pages covered (currently missing ~10 pages)
- CLI output captured as images
- Consumer app screenshots automated
- Docs reference auto-generated paths

**Non-Goals:**
- Visual regression testing (no baseline comparison)
- CI integration (local workflow only)
- Replacing the hand-drawn architecture diagrams in `docs/howitworks/`

## Decisions

### D1: Output directory structure
**Decision:** All auto-generated screenshots go to `docs/images/auto/{web,cli,app}/`

**Why:** Separating auto-generated from manual images makes it safe to `rm -rf docs/images/auto/` and regenerate. Manual images (architecture diagrams, hand-drawn) stay in `docs/images/` untouched.

**Alternative considered:** Overwriting `docs/images/` in-place — rejected because it's hard to distinguish generated vs hand-made.

### D2: CLI screenshot tool
**Decision:** Use `ansi2html` (pip) + `wkhtmltoimage` (system) pipeline.

**Why:** `ansi2html` preserves ANSI colors/formatting faithfully. `wkhtmltoimage` renders the HTML to PNG at consistent dimensions. Both are well-maintained and available on Linux.

**Alternative considered:** `svg-term-cli` — nicer SVGs but requires Node.js and has rendering inconsistencies with some ANSI escapes. `termshot` — requires a running terminal emulator.

**Fallback:** If `wkhtmltoimage` is not installed, fall back to saving HTML files only (still useful, just not PNG).

### D3: Playwright screenshot config
**Decision:** Expand `screenshots.spec.ts` with page objects for each screen, using `fullPage: true` and 1280x720 viewport.

**Why:** Full-page screenshots are more useful for docs than viewport-clipped ones. 1280x720 is a common doc-friendly aspect ratio.

### D4: Consumer app screenshots
**Decision:** Separate Playwright config (`playwright.app.config.ts`) that targets the consumer app's dev server URL from env var `E2E_APP_URL`.

**Why:** The app runs on a different port than the set-web dashboard. Separate config avoids coupling.

### D5: Entry point
**Decision:** Root `Makefile` target `screenshots` that calls three sub-commands in sequence.

**Why:** Make is already available on all dev machines, and the three screenshot categories (web, cli, app) are independent steps that benefit from a simple orchestrator.

## Risks / Trade-offs

- [Risk] `wkhtmltoimage` not installed on all machines → Mitigation: Script checks and prints install instructions, falls back to HTML
- [Risk] Consumer app not running → Mitigation: App screenshots skip gracefully with warning
- [Risk] E2E project has no data for optional tabs → Mitigation: Already handled with skip logic
- [Risk] Screenshot file sizes → Mitigation: Use PNG compression, consider adding `optipng` post-step

## Open Questions

- Should we add a `.gitignore` for `docs/images/auto/` (generated, don't commit) or commit them (available without regeneration)? **Recommendation:** Commit them — most users won't have a running set-web instance to regenerate.
