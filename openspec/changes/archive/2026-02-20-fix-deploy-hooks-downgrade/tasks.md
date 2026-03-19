## 1. Stale Entry Detection

- [x] 1.1 Add jq function to detect stale `wt-hook-memory PreToolUse` entries in PreToolUse array (any entry with command containing `wt-hook-memory PreToolUse`)
- [x] 1.2 Add jq function to detect stale `wt-hook-memory PostToolUse` entries in PostToolUse array (entries whose matcher is NOT in canonical set: `Read`, `Bash`)

## 2. Surgical Prune Logic

- [x] 2.1 Add `prune_stale_hooks()` jq filter that removes stale entries from PreToolUse and PostToolUse while preserving all non-wt-hook-memory entries (activity-track.sh, user hooks)
- [x] 2.2 Ensure Skill/activity-track.sh PreToolUse entry is added if missing (canonical config requires it)

## 3. Replace Idempotency Check

- [x] 3.1 Replace `has_unified` check with `is_canonical` check — detect stale entries instead of just "unified present"
- [x] 3.2 When stale entries found: backup settings.json, run prune filter, log what was removed
- [x] 3.3 When no stale entries and all canonical hooks present: skip (exit 0)

## 4. Verification

- [x] 4.1 Run `wt-deploy-hooks` on a project with old 6-matcher config (e.g. reddit) and verify it downgrades correctly
- [x] 4.2 Run `wt-deploy-hooks` on set-core (already canonical) and verify it skips
- [x] 4.3 Run full `install.sh` dry check — verify `install_projects()` would invoke deploy on all registered projects
