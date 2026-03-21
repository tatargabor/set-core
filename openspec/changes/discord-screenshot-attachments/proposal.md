# Proposal: Discord Screenshot Attachments

## Why

The orchestration engine already collects Playwright screenshots during smoke tests (per-change) and E2E tests (per-phase/merge). These live on disk under `SetRuntime().screenshots_dir` but are only visible through the TUI or by browsing the filesystem. The Discord integration currently posts text-only status messages — there's no way to see visual test results without SSH-ing into the machine or opening the web dashboard.

Screenshots provide immediate visual feedback: did the login page render? Is the product listing broken? A picture in Discord is worth a thousand log lines.

## What Changes

### Screenshot attachment on smoke failure

When a smoke test fails for a change, the verifier already collects screenshots to `wt/orchestration/screenshots/smoke/<change>/`. After collection, post the failure screenshots to the run's Discord thread with a spoiler tag so they don't clutter the thread visually.

### Screenshot gallery on run completion

When an orchestration run completes (status → done/failed), collect all screenshots from the run and post them as a single gallery message in the thread. Discord renders multiple images in a compact grid. This gives a visual summary of the entire run.

### Screenshot attachment on E2E completion

After phase-end E2E tests complete, post E2E screenshots to the thread. These go to `wt/orchestration/e2e-screenshots/cycle-N/` and should be posted similarly to smoke screenshots.

### Screenshot size management

Discord has a 25MB file upload limit per message and 10 files per message. Screenshots need to be:
- Resized if larger than 1MB (Playwright screenshots can be large)
- Batched into groups of 10 if there are many
- Skipped with a count message if total exceeds 25MB

## Capabilities

### New Capabilities
- `discord-smoke-screenshots`: Smoke test failure screenshots posted to Discord thread with spoiler
- `discord-run-screenshot-gallery`: All screenshots posted as gallery on run completion
- `discord-e2e-screenshots`: E2E test screenshots posted to Discord thread

### Modified Capabilities
- `discord-notifications`: Extended to handle file attachments alongside text/embed messages

## Risk

**Low**. Screenshot posting is fire-and-forget — failures are logged but never block the orchestration pipeline. Discord API rate limits are the main concern, mitigated by batching.

## Scope

### In Scope
- Posting smoke failure screenshots to thread (spoiler-tagged)
- Posting E2E screenshots to thread after phase-end tests
- Run completion screenshot gallery in thread
- Image size/count management for Discord limits
- Integration with existing `collect_screenshots` and `_collect_smoke_screenshots`

### Out of Scope
- Screenshot thumbnail generation (Discord does this automatically)
- Screenshot comparison / visual diff
- Storing screenshots in Discord as permanent archive
- Video recording attachment
