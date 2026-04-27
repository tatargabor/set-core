# Spec: docs-screenshot-pipeline

## ADDED Requirements

## IN SCOPE
- Playwright-based screenshot capture for all web dashboard pages
- CLI output capture as images (terminal → PNG/SVG)
- Consumer app screenshot capture from E2E run projects
- Single entry point command to regenerate all screenshots
- Docs updated to reference auto-generated image paths
- Skipping pages/tabs that have no data (graceful degradation)

## OUT OF SCOPE
- Video/GIF recording of interactions
- Screenshot comparison / visual regression testing
- Automatic doc generation (only image generation)
- CI pipeline integration (local-only for now)
- Screenshot annotation or watermarking

### Requirement: Web dashboard screenshot capture

The system SHALL capture full-page PNG screenshots of every navigable page in the web dashboard via Playwright.

#### Scenario: All dashboard tabs captured
- **WHEN** `pnpm screenshot:docs` is run with a valid `E2E_PROJECT`
- **THEN** PNG screenshots are saved to `docs/images/auto/web/` for each visible tab (changes, phases, tokens, sessions, log, learnings, and conditionally: plan, audit, digest)

#### Scenario: Secondary pages captured
- **WHEN** `pnpm screenshot:docs` is run
- **THEN** screenshots are also captured for: Manager project list, Memory page, Settings page, Issues page, Worktrees page, and Agent chat tab

#### Scenario: Optional tabs gracefully skipped
- **WHEN** a conditional tab (plan, audit, digest) has no data for the given project
- **THEN** the screenshot is skipped without failure and no file is written

#### Scenario: Manager page with multiple projects
- **WHEN** the manager page is captured
- **THEN** the screenshot shows the full project list with status indicators and token counts

### Requirement: CLI output screenshot capture

The system SHALL capture terminal output from key CLI commands as PNG images.

#### Scenario: CLI commands rendered as images
- **WHEN** `scripts/capture-cli-screenshots.sh` is run
- **THEN** terminal output from commands (`set-list`, `set-status`, `openspec status`, `set-memory stats`) is captured and saved as PNG files in `docs/images/auto/cli/`

#### Scenario: Terminal styling preserved
- **WHEN** CLI output contains ANSI colors and formatting
- **THEN** the captured image preserves colors and styling (not plain text)

### Requirement: Consumer app screenshot capture

The system SHALL capture screenshots of a completed consumer project's running application pages.

#### Scenario: App pages captured via Playwright
- **WHEN** a consumer project has a running dev server (detected via E2E project config)
- **THEN** Playwright navigates to key application pages (home, product list, admin, etc.) and saves screenshots to `docs/images/auto/app/`

#### Scenario: App screenshot skipped if no server
- **WHEN** the consumer project has no running dev server
- **THEN** app screenshots are skipped with a warning, not an error

### Requirement: Unified screenshot entry point

The system SHALL provide a single command that regenerates all screenshots.

#### Scenario: Top-level command
- **WHEN** user runs `make screenshots` or equivalent from the repo root
- **THEN** web dashboard screenshots, CLI screenshots, and app screenshots are all regenerated

#### Scenario: Individual category run
- **WHEN** user runs `pnpm screenshot:docs` in `web/`
- **THEN** only web dashboard screenshots are regenerated (not CLI or app)

### Requirement: Docs reference auto-generated images

The system SHALL update documentation files to reference screenshots from the auto-generated paths.

#### Scenario: Docs use canonical paths
- **WHEN** a doc file references a dashboard screenshot
- **THEN** the image path points to `images/auto/web/<name>.png` (relative to `docs/`)

#### Scenario: Stale manual screenshots removed
- **WHEN** an auto-generated screenshot replaces a manual one
- **THEN** the old manual image file is removed and the doc reference is updated
