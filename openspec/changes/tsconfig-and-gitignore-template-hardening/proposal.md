## Why

Long-running E2E observations surfaced two repeat failure patterns tied to the nextjs consumer template:

1. **Stale tsconfig exclude clauses in long-lived consumer projects.** When v0 sources are re-imported, `set-design-import` rotates `v0-export/` to `v0-export.bak.<ts>/`. Older scaffolded `tsconfig.json` files only excluded the canonical `"v0-export"` (no glob), so the backup directories were type-checked and repeatedly failed the build on stale references — taking down whole changes. The template has since been updated to exclude the glob variants, but consumer projects initialised before that template update still carry the old exclude list. `set-design-import --regenerate-manifest` is the natural retrofit seam because it runs on every fresh design snapshot.

2. **Untracked runtime journal noise in `git status`.** Every dispatcher cycle produces `journals/<change>.jsonl` and `set/orchestration/*.jsonl` at the project root. These are expected to persist across runs for debugging, but they aren't ignored — so `set-merge`'s "auto-stashed uncommitted changes" notice fires every iteration and the changes show up in every diff.

Both are tooling-severity, both can be fixed together without touching orchestrator logic.

## What Changes

- `set-design-import` now patches `tsconfig.json["exclude"]` idempotently on every run that rewrites `v0-export/` (full import OR `--regenerate-manifest`). The patcher ensures `"v0-export"`, `"v0-export.*"`, `"*.bak"`, `"*.bak.*"` are all present. INFO-logs what it added; no-op when already up to date.
- The nextjs template `.gitignore` gains entries for runtime journal files that land at the project root: `journals/`, `orchestration-events-*.jsonl`, `set/orchestration/activity-detail-*.jsonl`, `set/orchestration/spec-coverage-history.jsonl`, `set/orchestration/e2e-manifest-history.jsonl`.
- Unit coverage for the tsconfig patcher (stub scaffold → assert exclude updated idempotently) and a template-level assertion for the gitignore entries.

## Capabilities

### New Capabilities
- `v0-design-import`: captures the `set-design-import` CLI contract, including the new idempotent tsconfig-patch responsibility.

### Modified Capabilities
- `web-template-gitignore`: extend with a requirement covering orchestration-runtime journal patterns.

## Impact

- `modules/web/set_project_web/design_import_cli.py` — new `_patch_tsconfig_excludes` step, called from both the full-import branch and the `--regenerate-manifest` branch.
- `modules/web/set_project_web/templates/nextjs/.gitignore` — additive entries only.
- Consumer projects re-running `set-design-import` after the fix deploys will get their `tsconfig.json` patched automatically on the next design refresh. No breaking changes.
- Tests under `tests/unit/` for the tsconfig patcher; a lightweight template-content check for the gitignore additions.
