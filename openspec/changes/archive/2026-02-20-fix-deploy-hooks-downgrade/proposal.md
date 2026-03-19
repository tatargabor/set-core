## Why

The `raw-conversation-ingest` change reduced hook scope (PreToolUse: Skill-only, PostToolUse: Read+Bash only) but `wt-deploy-hooks` can't downgrade projects that already have the old expanded config (6 PreToolUse + 6 PostToolUse matchers). The idempotency check sees "unified hooks present" and skips — it never checks whether there are *too many* matchers. Running `install.sh` or `set-project init` leaves reddit, mediapipe, tgholsters etc. with stale overhead hooks.

## What Changes

- **Smart downgrade in `wt-deploy-hooks`**: Instead of checking "are unified hooks present → skip", compare the actual hook entries against the canonical config and surgically remove only `wt-hook-memory` entries that shouldn't be there (e.g. PreToolUse Read/Edit/Write/Bash/Task/Grep memory matchers), while preserving any non-wt hooks (activity-track.sh, user-added hooks)
- **`install.sh` triggers re-deploy**: The `install_projects()` flow already calls `set-project init` → `wt-deploy-hooks` for every registered project — the fix is entirely in the deploy script's comparison logic

## Capabilities

### New Capabilities
- `hook-config-downgrade`: Ability for `wt-deploy-hooks` to detect and remove stale `wt-hook-memory` matchers from PreToolUse/PostToolUse, bringing projects in line with the canonical reduced config without touching non-wt hooks

### Modified Capabilities
- `auto-memory-hooks-deploy`: Idempotency check updated — instead of "unified present → skip", compares actual matchers against canonical set and upgrades OR downgrades as needed

## Impact

- `bin/wt-deploy-hooks` — rewrite idempotency/comparison logic
- All registered projects' `.claude/settings.json` — stale PreToolUse/PostToolUse memory matchers removed on next `install.sh` or `set-project init` run
- No new files, no new dependencies
