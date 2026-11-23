## Context

Today the design pipeline pulls a v0.app export into `v0-export/` and treats it as the design source-of-truth. The `design-fidelity` skeleton check enforces that named **shells** (`v0-export/components/site-header.tsx`, etc.) are mounted into `src/components/`. But the underlying **primitives** (`v0-export/components/ui/command.tsx`, `dialog.tsx`, …) are silently ignored. The agent independently scaffolds `src/components/ui/` either via `shadcn add` or by template defaults — producing a primitive layer that may be older, newer, or a different shadcn fork than what v0 used.

When a v0 shell relies on an extended primitive API (`<CommandDialog title="…">`), this skew surfaces as a **late-stage TypeScript build failure** after the skeleton check has already passed. The fix every time is the same: copy or extend the project primitive to match the v0 primitive. We have observed this pattern in a recent micro-web E2E run (the agent first mounted the v0 shell, then on the next gate attempt patched the project primitive's type to extend the missing fields), and the same drift class is structurally guaranteed to recur on any future v0-driven change.

Constraints:
- Cannot pin a "shadcn version" — shadcn is a code-generator CLI, not a package; output drifts across CLI versions and v0 customizes by hand on top.
- Cannot block the agent from regenerating `src/components/ui/` (it does so legitimately when scaffolding new primitives).
- Must not surprise existing projects that have intentionally divergent primitive layers (e.g. swapped library, custom theming layer).
- Must keep the existing tsconfig exclusion of `v0-export/` intact so the primary v0 tree is not type-checked twice.

Stakeholders: web profile (Layer 2), agents authoring UI changes, operators reviewing forensic drift logs.

## Goals / Non-Goals

**Goals:**
- Eliminate the skeleton→build→patch→retry cycle caused by v0/project primitive API skew.
- Make `v0-export/components/ui/` the single source-of-truth for any primitive that v0 actually exports.
- Preserve project-only primitives (files in `src/components/ui/` not present in `v0-export/components/ui/`) — sync is unidirectional v0→project for shared files only.
- Surface skew as an actionable, blocking finding when sync is disabled (so projects that opt out still get loud errors instead of silent build failures).
- Keep the change additive: existing projects without a `v0-export/` see no behavior change.

**Non-Goals:**
- Pinning shadcn CLI versions or freezing v0's shadcn snapshot (impossible — v0 hand-edits).
- Auto-running `shadcn add` to fill missing primitives (out of scope; sync only handles primitives v0 itself exported).
- Versioning or diffing primitive content over time (a future "primitive history" capability could; this change just establishes ground truth).
- Changing the design-fidelity gate's shell/skeleton phases beyond ordering and the new skew check.
- Touching non-web profiles or projects without v0-export.

## Decisions

### D1 — Sync at import time (not at gate time)

We add the primitive sync to `set-design-import`, **not** to the `design-fidelity` gate. Rationale:

- Gate-time sync would mutate the agent worktree mid-verify, polluting the agent's git diff and breaking the "uncommitted_check: clean" precondition. The agent would see surprise files appear that it did not author.
- Import time runs once per design refresh, in a known state, before any agent dispatch. The sync result is committed to the scaffold's base commit and inherited by every change worktree branched off of it — exactly like every other deployed file.
- Gate-time sync would also need to handle race conditions across parallel changes; import-time sync is single-process by construction.

Alternatives considered:
- *Sync from a post-merge hook* — too late; the build already failed by then.
- *Sync from `set-project init`* — too early; v0-export may not yet be present when init runs (init can be a bare project setup before any design source is hooked up).

### D2 — Sync semantics: overwrite shared files, preserve project-only files, never delete

For each file in `v0-export/components/ui/**.tsx`:
1. Compute target path: `src/components/ui/<same-relpath>.tsx`.
2. If target does not exist → **create** it with v0's content. INFO log "added".
3. If target exists and content equals v0's → **no-op**. DEBUG log only.
4. If target exists and content differs → **overwrite** with v0's content. INFO log with both content hashes.

Files in `src/components/ui/` that have NO counterpart in `v0-export/components/ui/` are preserved untouched. We never delete from `src/`.

Rationale: this matches the "v0 is design source of truth" mental model that already applies to shells, while protecting project-only primitives from accidental data loss. Symmetric to how the manifest-driven shell sync already behaves.

Alternatives considered:
- *Three-way merge* — over-engineered; primitives are atomic files, not editable surfaces. If a project diverges intentionally it should set `sync_ui: false`.
- *Rename collisions to `.bak`* — adds noise; the agent has git for history.

### D3 — Opt-out via `orchestration.yaml`, default ON

Add `design_import.sync_ui: true|false` (default `true`). When `false`:
- `set-design-import` skips the sync entirely.
- The gate's new `ui-primitive-skew` phase emits findings as **warnings** (severity downgrade), not blocking violations.

Rationale: defaults bias toward correctness for the common case (v0 → project), but preserve the escape hatch for the rare project that swapped its primitive library after running the v0 sync once and now wants to freeze drift. Forensic logs still record all primitive deltas under `--dry-run`.

### D4 — Skew detection in the gate is signature-based, not byte-based

The new `ui-primitive-skew` phase compares **exported component signatures**, not file bytes:
- For each `v0-export/components/ui/*.tsx` file, extract top-level exports and the type literal of each exported component's first parameter (Props).
- Compare with the corresponding `src/components/ui/*.tsx` exports/types.
- Report `ui-primitive-skew` when an exported name exists in v0 but not in project, OR when the project's Props type is structurally narrower than v0's (missing fields v0 declares).

Byte-equal-but-cosmetically-different files (whitespace, import-order, comment differences) MUST NOT trigger the violation. Project Props types that are SUPERSETS of v0's (extra fields) MUST NOT trigger either — wider is fine.

Rationale: file-byte equality is too noisy (Prettier differences, comment churn). The actual failure mode we care about is "the agent calls `<CommandDialog title=…>` but the project type omits `title`". A structural signature check catches that exact class without false positives.

Implementation note: use TypeScript's compiler API or a regex-based AST walker scoped to the narrow grammar of shadcn primitives (export + interface/type pairs). Regex-based approach is lighter and matches existing tooling style in `v0_fidelity_gate.py` (`run_skeleton_check` already uses simple AST-free heuristics).

### D5 — Phase ordering in `run_skeleton_check`

Run the new `ui-primitive-skew` phase BEFORE the existing `shell-not-mounted` phase. If skew exists, the agent gets the actionable error first ("primitive API drift detected, sync via …"). Fixing the skew typically also resolves what would otherwise appear as `missing-shared-file` because the agent stops trying to mount a shell whose primitive doesn't compile.

Rationale: error ordering is UX. The current symptom path (skeleton-fail → mount → build-fail → patch primitive) is precisely the wrong ordering — the leaf cause shows up last. Surfacing the root cause first cuts retry cycles.

### D6 — Sync runs on `--regenerate-manifest` too

Both full `set-design-import --git <url>` and `set-design-import --regenerate-manifest` invoke the sync, identical to how tsconfig-exclude patching works today (see `v0-design-import` spec). This avoids a "stale primitive" trap where someone regenerates the manifest after v0 evolves but the primitives stay frozen.

## Risks / Trade-offs

- [**Risk**] Existing project that has manually edited `src/components/ui/command.tsx` will see those edits silently overwritten on next `set-design-import`.
  → **Mitigation:** the INFO-level overwrite log names the file and both content hashes; release notes call this out; `sync_ui: false` is the documented escape hatch. The pre-existing `*.bak`/`*.bak.*` tsconfig exclusion already covers manual snapshots agents/operators may take.

- [**Risk**] Project-only primitives that depend on a v0 primitive (e.g. project authored `src/components/ui/data-table.tsx` that imports from `@/components/ui/command`) may break if the v0 sync changes the imported primitive's API in an incompatible way.
  → **Mitigation:** this is the same drift class we are trying to surface. The new skew phase will flag it, and the standard build gate will catch the import error. This change does not regress the failure mode — it moves it earlier and labels it.

- [**Risk**] Adding a TS-AST or regex parser to the importer increases its complexity and failure surface.
  → **Mitigation:** D4 picks the lighter regex approach scoped to the small grammar already used elsewhere in `v0_fidelity_gate.py`. Sync itself (D2) is byte-level copy, no parser needed. The parser only runs in the gate's skew detection, where errors are recoverable (skip the file with a DEBUG log).

- [**Risk**] Non-deterministic v0 exports (different file content for the same logical primitive across exports) could cause noisy overwrite churn.
  → **Mitigation:** v0 exports are deterministic by URL+ref; the runner pins `ref` already (see `tests/e2e/scaffolds/*/scaffold.yaml`). For the set-core development project this is non-issue. We log every overwrite so any churn is visible.

- [**Trade-off**] Sync semantics treat v0 as authoritative for shared files. A project that wants to evolve its primitive layer beyond v0's choices must either (a) rename the primitive, (b) set `sync_ui: false`, or (c) PR the change upstream into v0. We accept (a)+(b) as documented escape hatches; (c) is out of scope.

- [**Trade-off**] We do not handle the inverse direction (project-evolved primitives flowing back into v0). This is intentional — v0 is a design tool, not a code repository, and v0 user flow is "regenerate, re-export". A "v0 codegen feedback" capability would be a separate change.

## Migration Plan

1. Land the change on a feature branch.
2. Run `set-design-import --regenerate-manifest --dry-run` against `tests/e2e/scaffolds/micro-web/` to verify the sync logs (no actual disk changes).
3. Run a fresh `./tests/e2e/runners/run-micro-web.sh` and confirm:
   - `src/components/ui/command.tsx` matches `v0-export/components/ui/command.tsx` post-import.
   - `foundational-scaffold-and-shell` change reaches build/test/e2e/design-fidelity all-green in **1 attempt** (down from 2–3).
4. Repeat with `run-craftbrew.sh` to validate against a richer v0 source.
5. Update `templates/core/rules/design-bridge.md` (deployed to consumers via `set-project init`) to describe the new sync behavior.
6. Document `design_import.sync_ui: false` in the project-init audit output (`set-audit scan`) so operators know how to opt out.

Rollback: revert the proposal commit. The reverted code restores pre-change behavior, but on-disk syncs that already executed leave their overwritten files in place — the rollback does NOT undo prior writes to `src/components/ui/`. To fully undo a sync, an operator must restore the affected files from git history. Acceptable: the sync result is itself a valid project state (v0-aligned primitives), and reverting the code stops further syncs; any project that wants to revert the data needs `git checkout <pre-sync-sha> -- src/components/ui/`.

## Open Questions

- **Q1**: Should the sync also cover `v0-export/lib/utils.ts` (the `cn` helper) and `v0-export/hooks/`? These are not "ui primitives" strictly but are commonly imported by v0 components. **Tentative**: out of scope for v1; revisit if telemetry shows agents patching `lib/utils.ts` for skew. Document this scope boundary in the spec's "non-requirements".
- **Q2**: How should the gate's skew phase render in the activity dashboard? The dashboard currently only shows Build/Test/E2e tabs (per user feedback in this run). Adding a "design-fidelity" tab is a separate concern but the skew finding's `retry_context` should still surface in the existing per-attempt log view. **Tentative**: no UI change in this proposal; track UI surfacing as a follow-up.
- **Q3**: Do we want a `--no-sync-ui` CLI flag on `set-design-import` in addition to the YAML knob? **Tentative**: yes — symmetric to `--regenerate-manifest`. Specs to declare both.
