## Why

set-core's `.claude/rules/` directory serves two conflicting purposes: it holds rules for developing set-core itself, AND it's the source from which `set-project init` deploys rules to consumer projects. This means every top-level `.md` file in `.claude/rules/` automatically leaks to consumer projects (e.g., `modular-architecture.md` and `openspec-artifacts.md` — set-core internal docs — ship as `set-modular-architecture.md` to web projects where they're meaningless). Internal rules must be hidden in subdirectories as a workaround.

The fix: move deployable core rules to an explicit `templates/core/rules/` directory. `deploy.sh` reads from there instead of `.claude/rules/`. This makes `.claude/rules/` purely set-core's own, and the deploy source is explicit and auditable.

## What Changes

- Create `templates/core/rules/` with only the rules that belong in every consumer project
- Change `deploy.sh _deploy_skills()` rules section to read from `templates/core/rules/` instead of `.claude/rules/`
- Remove the `-maxdepth 1` hack (no longer needed — everything in `templates/core/rules/` is deployable)
- `.claude/rules/` becomes set-core's own development rules (no longer a deploy source)

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `project-init-deploy` — Rules deploy source changes from `.claude/rules/` to `templates/core/rules/`

## Impact

- `lib/project/deploy.sh` — `_deploy_skills()` rules section (lines 174-197)
- `templates/core/rules/` — new directory with 4 rule files (copied from `.claude/rules/`)
- `templates/cross-cutting-checklist.md` — remove (superseded by `templates/core/rules/`)
- Consumer projects: no visible change (same `set-*.md` files deployed)
