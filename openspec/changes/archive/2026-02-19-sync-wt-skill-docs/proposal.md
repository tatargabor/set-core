## Why

The `/wt:*` command files (`.claude/commands/wt/*.md`) are significantly out of sync with their corresponding `bin/wt-*` CLI tools. CLIs evolved with new subcommands, flags, and options, but the skill files were never updated. This causes agents to miss available functionality (e.g., `set-memory` has 25+ subcommands but the skill only documents 9).

## What Changes

Update all out-of-sync `.claude/commands/wt/*.md` files to match current CLI capabilities:

- **memory.md** (biggest gap): Add missing subcommands (forget, stats, cleanup, get, context, brain, export, import, sync status, migrate, repair), fix legacy type aliases (Observation→Learning, Event→Context), document recall modes
- **loop.md**: Add missing flags (--stall-threshold, --iteration-timeout, --permission-mode, --label, --force, --done openspec)
- **merge.md**: Add --squash, --no-push, fix --target→--to flag name
- **work.md**: Add -e/--editor, --no-create, -p/--project flags
- **new.md**: Add -b/--branch, --skip-fetch, --new, -p/--project flags

## Scope

- Only `.claude/commands/wt/*.md` files — no CLI code changes
- Documentation-only change — no behavior changes
- Files are gitignored (deployed per-project via `set-project init`)
