# Proposal: docs-screenshot-pipeline

## Why

Documentation images are manually created and quickly become stale as the UI evolves. Every screenshot in `docs/images/` and `docs/howitworks/` is a hand-captured PNG or GIF that nobody regenerates. We already have Playwright E2E infrastructure — extending it to automatically generate all documentation screenshots creates a single `pnpm screenshot:docs` command that keeps every image in sync with the live UI. CLI/terminal output screenshots can be generated similarly via script capture.

## What Changes

- **Expand the Playwright screenshot spec** to cover ALL web dashboard pages (currently 8 tabs, missing ~10 pages: Memory, Settings, Issues, Worktrees, Mutes, Agent chat, Plan, Audit, Digest, Sentinel)
- **Add CLI output capture script** that runs key CLI commands (`set-list`, `set-status`, `openspec status`, `set-memory stats`, etc.) and saves terminal output as images using a terminal-to-image tool (e.g., `ansi2html` + `wkhtmltoimage`, or `svg-term`)
- **Add consumer app screenshot capture** for E2E run projects — capture the actual built application pages (storefront, admin, etc.) using Playwright against the dev server
- **Replace static images in docs** with references to auto-generated paths, and add a top-level `make screenshots` or `pnpm screenshot:all` entry point
- **Add placeholder system** — docs reference a canonical path (`docs/images/auto/`), and the pipeline regenerates them on demand

## Capabilities

### New Capabilities
- `docs-screenshot-pipeline` — the automated pipeline for generating all documentation screenshots

### Modified Capabilities
_(none — existing specs are unaffected)_

## Impact

- `web/tests/e2e/screenshots.spec.ts` — expand with all dashboard pages
- `web/package.json` — new scripts
- `scripts/` — new CLI screenshot capture script
- `docs/wt-web.md`, `docs/gui.md`, `docs/developer-memory.md`, `docs/worktrees.md`, `docs/sentinel.md`, `docs/cli-reference.md` — update image references to auto-generated paths
- `docs/images/auto/` — new output directory for all generated screenshots
- `Makefile` or root `package.json` — top-level `screenshot:all` command
