## Why

When a user opens a Claude Code session on a finished project's main branch, CLAUDE.md has no information about how to start the application. The existing `generate_startup_guide()` only writes to worktree CLAUDE.md during dispatch — the main branch never gets a startup reference. A separate `START.md` file (profile-generated, auto-detected) would give both humans and agents an instant "how to run this" reference that CLAUDE.md points to.

## What Changes

- Add `generate_startup_file()` method to the `ProjectType` ABC (profile system)
- Implement it in `WebProjectType` — generates `START.md` with install, dev server, DB, test commands
- Move detection logic from `dispatcher.py:generate_startup_guide()` into the web profile
- Dispatcher and merger call `profile.generate_startup_file()` instead of hardcoded detection
- `deploy.sh` adds a `## Getting Started` reference in CLAUDE.md pointing to `START.md`
- Post-merge: merger regenerates `START.md` on main after each successful merge

## Capabilities

### New Capabilities
- `startup-file-generation` — Profile-driven START.md generation with CLAUDE.md reference

### Modified Capabilities
- `startup-guide` — Existing dispatcher inline guide replaced by profile delegation + file reference

## Impact

- `lib/set_orch/profile_types.py` — new ABC method
- `modules/web/set_project_web/` — implement detection logic (moved from dispatcher)
- `lib/set_orch/dispatcher.py` — delegate to profile, reference START.md
- `lib/set_orch/merger.py` — regenerate START.md post-merge
- `lib/project/deploy.sh` — add CLAUDE.md reference section
- `templates/` — START.md not a static template (generated dynamically)
