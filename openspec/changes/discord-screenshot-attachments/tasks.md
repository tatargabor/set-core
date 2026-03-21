# Tasks: Discord Screenshot Attachments

## Phase 1: Screenshot module

- [x] 1.1 Create `lib/set_orch/discord/screenshots.py` with `_prepare_screenshots(paths)` — filter by size, optionally resize with Pillow, enforce MAX_FILES_PER_MSG=10 and MAX_TOTAL_SIZE=25MB
- [x] 1.2 Add `post_screenshots(thread, paths, caption, spoiler)` — posts `discord.File` attachments to a thread, batching into multiple messages if >10 files
- [x] 1.3 Add `collect_run_screenshots(run_state)` — gathers all smoke + E2E screenshot paths for a completed run from `SetRuntime()` directories

## Phase 2: Smoke failure screenshots

- [x] 2.1 In `watcher.py` `_forward_to_discord()` per-change status loop, detect `verify-failed` + `smoke_screenshot_count > 0` from the change dict in state JSON
- [x] 2.2 Resolve absolute screenshot path: `watcher.project_path / change["smoke_screenshot_dir"]`, glob for `**/*.png`
- [x] 2.3 Get the active run thread from `events.py` `_run_state` (expose via `get_active_thread()` helper)
- [x] 2.4 Call `post_screenshots(thread, paths, caption, spoiler=True)`
- [x] 2.5 Track already-posted screenshots per change key (avoid re-posting on state re-poll) — add `_discord_screenshots_posted` set on watcher
- [ ] 2.6 Verify: trigger a smoke failure with screenshots → spoiler-tagged images appear in thread

## Phase 3: E2E screenshots

- [x] 3.1 In `watcher.py`, detect when `e2e_screenshot_count` changes from 0 → N on any change
- [x] 3.2 Read `e2e_screenshot_dir`, glob for `**/*.png`, call `post_screenshots(thread, paths, caption="📸 E2E: {result}")`
- [ ] 3.3 Verify: E2E test with screenshots → images appear in thread

## Phase 4: Run completion gallery

- [x] 4.1 In `events.py` `_handle_run_complete()`, gather all `smoke_screenshot_dir` and `e2e_screenshot_dir` paths from state changes
- [x] 4.2 Call `collect_run_screenshots(state_changes)` → list of all screenshot paths
- [x] 4.3 Call `post_screenshots(thread, paths, caption="📊 Run #{id} — {count} screenshots")` as gallery
- [ ] 4.4 Verify: run completion with mixed smoke/e2e screenshots → gallery message in thread
