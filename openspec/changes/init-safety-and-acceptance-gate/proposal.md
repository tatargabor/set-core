# Proposal: Init Safety and Acceptance Gate

## Why

Three issues discovered during E2E orchestration runs (craftbrew-run15, minishop runs):

1. **`set-project init` destroys project work on re-init.** Re-init adds `--force` automatically, which overwrites scaffold files (`next.config.js`, `globals.css`, `utils.ts`, `playwright.config.ts`) even when the project has modified them. The `config.yaml` is also fully overwritten instead of additively merged. This breaks running projects.

2. **No cross-feature acceptance testing.** Per-change E2E tests only validate individual features in isolation. No agent writes journey tests that span multiple features (e.g., browse catalog → add to cart → checkout → verify order). This means integration gaps between changes go undetected.

3. **`max_parallel: 3` default causes cross-change blindness.** Parallel worktrees don't see each other's work. A catalog change adds a placeholder button that should link to cart, but the cart change never updates it because it branched before the catalog change merged. Sequential execution (`max_parallel: 1`) ensures each change builds on the latest main.

## What Changes

- **Init scaffold protection**: Template files marked as `protected` in `manifest.yaml` are skipped during re-init if the project has modified them (git diff check). Config files use additive YAML merge instead of overwrite.
- **Acceptance test change directive**: The planner template instructs the decomposer to always include a final `acceptance-tests` change that writes cross-feature journey E2E tests covering all acceptance criteria from the spec. This change depends on all other changes. **BREAKING**: Existing plans without this change are unaffected — only new decompositions include it.
- **`max_parallel: 1` default**: Change the default from 3 to 1. Existing projects with explicit `max_parallel` in their config are unaffected.

## Capabilities

### New Capabilities
- `init-scaffold-protection` — Protected file detection and additive config merge during re-init
- `acceptance-test-planning` — Planner directive for final acceptance test change with journey test writing rules

### Modified Capabilities
- `max-parallel-default` — Change default from 3 to 1
- `project-init-deploy` — Re-init skips protected scaffold files, merges config additively

## Impact

- `lib/set_orch/profile_deploy.py` — Protected file skip logic
- `lib/set_orch/config.py` — max_parallel default change
- `lib/set_orch/templates.py` — Planner prompt: acceptance-tests change directive
- `modules/web/set_project_web/templates/nextjs/manifest.yaml` — Protected file annotations
- `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` — max_parallel: 1
- `bin/set-project` — Config merge logic for re-init
