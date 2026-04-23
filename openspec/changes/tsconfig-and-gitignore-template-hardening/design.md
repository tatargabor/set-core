## Context

`modules/web/set_project_web/design_import_cli.py` owns `set-design-import` — the CLI that imports a v0.app export into a scaffolded consumer project. Two modes exist:

1. Full import (`--git` / `--source` / or `scaffold.yaml` `design_source` block) — clones or extracts, writes a fresh `v0-export/`, runs the quality validator.
2. `--regenerate-manifest` — skips re-import, only rewrites `docs/design-manifest.yaml` from the already-present `v0-export/`.

When the full import finds an existing `v0-export/` it rotates to `v0-export.bak.<ts>/` before writing the new tree. So even after a successful import, the project contains a `.bak` directory until the operator removes it. If the project's `tsconfig.json["exclude"]` doesn't cover that glob, TypeScript type-checks the `.bak` tree and fails the build on stale references — which is exactly what bit two changes on craftbrew-run-20260421-0025.

A recent template update patched the *nextjs template* `tsconfig.json` to exclude `"v0-export"`, `"v0-export.*"`, `"*.bak"`, `"*.bak.*"`. But consumer projects initialised before that template update keep the old exclude list forever. No existing path patches their `tsconfig.json`.

Separately, the runtime dispatcher writes per-change JSONL journals at the project root: `journals/<change>.jsonl`, plus `set/orchestration/activity-detail-*.jsonl`, `spec-coverage-history.jsonl`, `e2e-manifest-history.jsonl`. None of these are tracked intentionally, but they aren't gitignored either, so `set-merge`'s auto-stash warning fires every cycle and diffs get noisy.

## Goals / Non-Goals

**Goals:**
- Retrofit existing consumer projects to the corrected tsconfig exclude list *without* requiring a manual edit — reuse the existing `set-design-import` surface because that's what consumers invoke on every design refresh.
- Keep the patcher idempotent so repeated invocations don't mutate the file when already correct.
- Prevent runtime journal files from showing up as dirty in `git status` on fresh consumer projects.

**Non-Goals:**
- Changing what v0-export files the gate validates or the shape of `docs/design-manifest.yaml`.
- Patching `tsconfig.json` for fields outside `exclude` (e.g. `include`, compiler options).
- Retro-actively fixing `.gitignore` in already-deployed consumer projects — new entries ship via the template, so they reach existing projects only on the next `set-project init` pass. That's intentional: we don't want to rewrite consumer `.gitignore` files from a design-import CLI.
- Providing a standalone `set-tsconfig-patch` CLI. The design-import flow is the natural seam.

## Decisions

### D1: Patcher runs in both full-import and `--regenerate-manifest` paths

Both paths touch (or verify) `v0-export/`, so both paths are legitimate trigger points. Running it in both ensures:
- A fresh import on a pre-commit-793e46a0 project fixes tsconfig on the very first import.
- A re-run on a project that already has `v0-export/` (but still has the old tsconfig) fixes it via `--regenerate-manifest` without forcing a full re-import.

**Alternative considered:** Run only in `--regenerate-manifest`. Rejected — it means a project that only ever uses full imports never gets patched.

### D2: Idempotency via set-difference

The patcher reads `tsconfig.json`, computes `required - current`, and only writes back when the set is non-empty. When it writes, it appends the missing entries at the end of the existing exclude list (preserving order of anything already there). An INFO-level log lists what was added; a DEBUG log fires on the no-op path.

**Alternative considered:** Sort the final list alphabetically. Rejected — churns diffs for consumers that intentionally ordered their exclude list.

### D3: Required excludes are frozen constants

The four patterns `"v0-export"`, `"v0-export.*"`, `"*.bak"`, `"*.bak.*"` are defined as a module-level tuple. Adding new required excludes is a source change, not a config change — keeps behavior auditable.

### D4: Parse tsconfig as JSONC-lite (JSON, not JSON5)

Next.js scaffolded `tsconfig.json` is pure JSON. We don't need comment-preserving parse. If the consumer edited the file to include comments or trailing commas, the patcher logs a WARNING and skips — safer than silently corrupting the file.

**Alternative considered:** Use a JSONC parser (e.g. `json5`). Rejected — new dependency for a very narrow payoff; the template doesn't ship with comments, and violating consumers get a clear warning.

### D5: Gitignore entries are additive-only template edits

The new `.gitignore` entries live in `modules/web/set_project_web/templates/nextjs/.gitignore`, grouped under a new "Orchestration runtime journals" section. They reach consumer projects via the standard `set-project init` deploy pass — no CLI rewrite. Entries:
- `journals/` — dispatcher per-change journal dir
- `orchestration-events-*.jsonl` — rotated event log siblings
- `set/orchestration/activity-detail-*.jsonl` — activity-detail cache files
- `set/orchestration/spec-coverage-history.jsonl` — coverage history
- `set/orchestration/e2e-manifest-history.jsonl` — e2e manifest history

Note: `set/orchestration/` is *not* added wholesale, because other files in that directory (config-like entries) may legitimately belong in version control.

## Risks / Trade-offs

- [Risk] Operator has edited `tsconfig.json` to include JSON5 comments or trailing commas → patcher parses with `json.loads` and raises → caught, logged as WARNING, import continues unaffected. **Mitigation**: WARN is explicit about "manual tsconfig edit needed" so the operator knows what to do.
- [Risk] Consumer has an empty `exclude` array intentionally (wants TypeScript to see everything, e.g. for a linting-only tsconfig) → patcher still adds v0-export patterns. **Mitigation**: Accepted — users who want to exclude nothing but still use the v0 pipeline are vanishingly rare; if this bites anyone, the patcher's idempotency means they can just delete their `exclude` entries and re-run.
- [Risk] New `.gitignore` entries collide with a consumer project's deliberately-tracked files of the same name. **Mitigation**: Extremely unlikely — the patterns are orchestration-owned paths with no legitimate hand-authored use. No mitigation beyond documenting in the spec.
- [Risk] Template-level gitignore changes don't reach existing consumer projects automatically. **Mitigation**: Out of scope per Non-Goals. A future `set-project sync` capability could cover this; not needed now.

## Migration Plan

1. Land the patcher + gitignore entries in `set-core`.
2. No data migration. Next time a consumer project runs `set-design-import` (with any mode), the patcher runs once, updates tsconfig if stale, and logs the diff at INFO.
3. Fresh `set-project init --project-type web` projects get the updated `.gitignore` template; existing projects keep their file untouched.

Rollback: revert both edits. The patcher is additive and idempotent, so reverting won't corrupt any tsconfig that was patched under the new code.

## Open Questions

None.
