## Why

Preparing for release. The README and supporting docs have accumulated drift since major features were added (memory export/import, proactive context, sync, GUI memory browse). Multiple CLI commands are undocumented, the "Latest update" date is stale, and the Team Sync section is missing a critical GitHub traffic warning — `sync_interval_ms` defaults to 15s, generating ~480 git ops/hour.

## What Changes

- Full README refresh following `docs/readme-guide.md` mandatory section structure
- Add missing CLI commands to README: `wt-openspec` (3 subcommands), `set-memory sync` (4 subcommands), `set-memory proactive`, `set-memory stats`, `set-memory cleanup`, `set-memory-hooks remove`
- Add `wt-hook-memory-recall` and `wt-hook-memory-save` to internal hooks note
- Add GUI memory features to Features section: [M] button, Browse dialog, Export/Import, Remember Note
- Add wt-control GitHub traffic warning and usage guidance
- Change `team.sync_interval_ms` default from 15000 → 120000 (2 minutes)
- Update "Latest update" date to release date
- Update `docs/config.md` section count (14 → 16)
- Update `docs/readme-guide.md` CLI documentation rules to include new commands
- Remove or populate empty `AGENTS.md`

## Capabilities

### New Capabilities

- `team-sync-traffic-guard`: Document and enforce safe Team Sync polling defaults to prevent GitHub rate limiting

### Modified Capabilities

- `developer-memory-docs`: Add sync, proactive, stats, cleanup, GUI features to README
- `worktree-tools`: Add wt-openspec to documented CLI tools

## Impact

- `README.md` — full rewrite/refresh
- `docs/readme-guide.md` — add new CLI commands to documentation rules
- `docs/config.md` — update section list
- `AGENTS.md` — remove (empty placeholder)
- `gui/constants.py` — `team.sync_interval_ms` default change 15000 → 120000
- No breaking changes; documentation-first with one config default change
