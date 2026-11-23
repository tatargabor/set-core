# Design: e2e-testdir-drift-guard

## Context

`e2e-dep-drift-guard` (archived 2026-04-21) and `e2e-env-drift-guard` (active) established the pattern: detect a known crash signature on the unparseable-fail path of `execute_e2e_gate`, recover in-gate, do not consume `verify_retry_count`, prepend a `[self-heal: ...]` marker. This change ports that pattern to a third adjacent failure class — testdir drift — and adds a new layer of defense (verify-time canary) that catches the drift earlier in the merge pipeline.

The three drift classes are siblings:

| Class | Mismatch | Where it bites |
|---|---|---|
| dep-drift | `package.json` declares X, `node_modules` doesn't have it | Playwright crash with `Cannot find module 'X'` |
| env-drift | `schema.prisma` declares provider X, `.env` carries URL for provider Y | Prisma crash with `URL must start with the protocol ...` |
| testdir-drift | `playwright.config.ts` declares testDir X, spec files live at Y | Playwright exits with `Error: No tests found.` |

Each is a bootstrap-time mismatch caused by the orchestrator (or a prior commit) writing one half of a config-pair while the other half drifted. Each is cheap to recover. Each wastes a retry slot if not caught.

The empirical case for testdir-drift comes from `micro-web-run-20260501-1805`: a `test-infrastructure-setup` change committed `playwright.config.ts` with `testDir: "e2e"` to satisfy an older scaffold convention. Subsequent feature changes wrote their specs to `tests/e2e/` (the canonical path the dispatcher's prompt now instructs agents to use). After merge, main carried the old config and the new specs — a structural conflict that the merge mechanism did not surface because the two file edits did not collide at the line level (different files entirely).

## Goals / Non-Goals

**Goals:**

- End the misleading `[no parseable failure list — likely crash, OOM, or formatter issue]` diagnostic for the testdir-drift failure class. Replace with a precise, actionable message.
- Recover automatically in-gate when the drift is detectable and the canonical recovery path is unambiguous, mirroring the `e2e-dep-drift-guard` / `e2e-env-drift-guard` self-heal contract (no retry-budget consumption, single-attempt, forensic marker).
- Catch the drift at PR-time via a verify-gate canary so most occurrences never reach the merge stage in the first place.
- Treat existing consumer projects (whose configs were scaffolded under prior conventions) as first-class — the gate self-heal is the safety net for them, distinct from any forward-ported template change.

**Non-Goals:**

- Do not touch the merge mechanism itself to "smarter-merge" `playwright.config.ts` differences. That is broader scope (covered briefly in *Alternatives Considered*) and would require modeling structural-conflict awareness in the merger.
- Do not change `lib/set_orch/CoreProfile` or any Layer-1 abstraction — testdir conventions are web-specific.
- Do not move any spec files automatically. The self-heal aligns the *config* to where specs live, never the other way around. Moving spec files mid-gate would be too aggressive and would risk breaking imports relative to spec paths.
- Do not introduce a YAML or JS parser for `playwright.config.ts` — the file is TypeScript with structural complexity that no quick parser would handle correctly. Line-replace with regex matching the canonical fields (`testDir:`, `globalSetup:`) is sufficient for the recovery contract.
- Do not retire or modify the existing self-heal classes. Testdir-drift is additive.

## Decisions

### 1. Three layers of defense, not two

**Decision**: Failure-parser classification (Layer 2a) + gate-runner self-heal (Layer 2b) + verify-time canary (Layer 2c).

**Why**: The dep-drift and env-drift changes each ship with two layers (template pre-flight + gate self-heal). For testdir-drift, the equivalent of a "template pre-flight" — a runtime check inside `playwright.config.ts` — is awkward: the config file IS the source of truth for `testDir`, so it cannot meaningfully validate itself against where specs live without recursive bootstrap weirdness. The natural pre-flight equivalent is a **verify-gate canary** that runs at PR-time, scanning both config and spec layout from the outside. This catches drift earlier in the lifecycle (before merge), where it can be surfaced as a `warn` GateResult to the agent for self-correction, rather than only after a downstream gate failure.

**Why not just self-heal**: leaving the verify canary out would mean every drift incident waits for the integration gate to fire, surfacing as an unparseable failure first, then recovering. Even with self-heal, that path emits noise in logs and dashboard. The verify canary lets the agent fix the drift in the worktree before merge — clean, traceable, no rerun.

**Alternative considered**: Layer 1 in the dispatcher prompt — instruct the agent to verify their `playwright.config.ts` matches where their specs are. **Rejected** as redundant once Layer 2c exists: the verify canary catches the same condition mechanically and does not depend on agent compliance with prose instructions.

### 2. Detection signature: `Error: No tests found` plus on-disk corroboration

**Decision**: `_extract_testdir_drift(e2e_output: str, project_root: str) -> bool` returns `True` only when ALL of:

- `e2e_output` contains the literal string `Error: No tests found.`
- `project_root` contains at least one `*.spec.ts` file under any directory.
- That file is NOT inside the directory declared as `testDir:` in `playwright.config.ts`.

**Why this is more conservative than env-drift's signature**: Playwright's "No tests found" can also fire when an operator passes a typo'd CLI argument or filters with a `--grep` that matches nothing. Adding the on-disk corroboration ("there ARE spec files, but the config doesn't see them") rules out those false positives. The check is cheap — one `os.walk` over the project root with an early exit on first hit, plus one regex match against the config file.

**Why a single string-contains and not a multi-pattern union (like env-drift)**: Playwright emits exactly one variant of this error message, regardless of where the path comes from (CLI arg, testMatch, testIgnore). A union would only invite false matches.

### 3. Canonical-testdir resolution: count + tiebreak by convention

**Decision**: `_resolve_canonical_testdir(project_root)` returns the directory containing the most `*.spec.ts` files, with a tiebreaker preferring `tests/e2e/` over `e2e/` (and any other path).

**Why**: In the empirical case, main retained `e2e/smoke.spec.ts` from the old scaffold AND `tests/e2e/blog-list-with-filter.spec.ts` (and several others) from merged worktrees. A naïve "most spec files" rule correctly picks `tests/e2e/`. But if a project has exactly one stale spec in `e2e/` and one in `tests/e2e/`, the tiebreaker matters. We prefer `tests/e2e/` because:

- It is the path the dispatcher prompt instructs every agent to use (since the `e2e-tests` lint commit `b27a96b3` strengthened this).
- It is the path the canonical scaffold template has used since the template `playwright.config.ts` was updated.
- It is the path `set-project init` writes new global-setup templates to.

Stale `e2e/smoke.spec.ts` is by definition the legacy artifact; aligning to `tests/e2e/` resolves toward the desired end state.

**Alternative considered**: pick the testDir whose contents match the agent's most recent commit. **Rejected** — too coupled to git introspection inside a self-heal probe. The directory-count + convention tiebreaker is sufficient and self-contained.

### 4. Atomic config rewrite: line-replace with field-aware regex

**Decision**: `_resync_playwright_config_testdir(project_root, new_testdir)` reads `playwright.config.ts`, replaces lines matching `^\s*testDir\s*:\s*"[^"]*",?\s*$` and `^\s*globalSetup\s*:\s*"[^"]*",?\s*$` with the corrected paths (preserving leading whitespace and trailing comma/comment if present), or appends them inside the `defineConfig({` block if absent. Atomic write via `tmpfile + os.replace`.

**Why**: `playwright.config.ts` is a TypeScript file with imports, computed values, conditional logic, and devices arrays. A full TS parse is overkill. A targeted line-replace works because both `testDir` and `globalSetup` are conventionally written as one-line string-literal assignments inside `defineConfig({...})` — the canonical template uses exactly this form, and consumer projects rarely deviate.

**Why also rewrite `globalSetup`**: in the empirical case, both fields drifted together (`testDir: "e2e"` paired with `globalSetup: "./e2e/global-setup.ts"`). Rewriting one without the other leaves the gate broken in a different way (Playwright would now find tests but globalSetup would crash on missing path). The two are logically coupled; the self-heal must treat them as a pair.

**Path canonicalization**: `globalSetup` MUST point at `<new_testdir>/global-setup.ts`. If that file does not exist but `e2e/global-setup.ts` (or another stale path) does, copy its contents to the new path before rewriting the config. Never delete the stale file in the same pass — leave that to a future cleanup; deleting on self-heal is too aggressive.

**Failure mode**: if the regex does not match either field (unusual config layout), return `False`; the gate falls through to the normal fail path with the original output. Log at WARNING with the file path and a hint.

### 5. Self-heal ordering: dep-drift → env-drift → testdir-drift

**Decision**: In `execute_e2e_gate`, evaluate self-heals in the order `_self_heal_missing_module` → `_self_heal_db_env_drift` → `_self_heal_testdir_drift`, all gated by the same `self_heal_attempted` boolean.

**Why**: A `MODULE_NOT_FOUND` crash short-circuits the e2e run before Prisma init AND before Playwright reaches its test-discovery phase, so dep-drift cannot coexist in the same output as either env-drift or testdir-drift. Env-drift fires inside Prisma's `db push` step, also before Playwright's discovery. Testdir-drift fires only after Playwright successfully starts and tries to discover tests. The orderings are mutually exclusive in practice; we evaluate them in the order they would actually fire (earliest crash first) so the most-fundamental issue is recovered first if multiple ever did somehow appear.

**Single-attempt guarantee**: at most one self-heal per gate invocation, period. The combined-flag pattern (`self_heal_attempted` shared across all three classes) prevents any stacking. If testdir-drift fires and its rerun ALSO crashes with a different drift signature (e.g., the stale config also had a wrong `DATABASE_URL`), the gate fails with the rerun's output and the operator/agent picks up the second issue manually — we do not chain self-heals.

### 6. Marker text: distinct verb per drift class

**Decision**: prepend exactly `[self-heal: synced playwright.config.ts testDir from <old> to <new>]` to `GateResult.output` when testdir-drift self-heal recovers. The angle-bracket placeholders are filled with the actual paths.

**Why**: matches the dep-drift (`installed <pkg>`) and env-drift (`synced .env from config.yaml`) marker patterns. The verb `synced` is reused (env-drift also uses it), but the object differs (`.env from config.yaml` vs `playwright.config.ts testDir from ... to ...`), so a regex search like `\[self-heal: synced playwright` finds testdir-drift specifically. Forensics tools (`set-run-logs`, dashboard) can use a single regex (`\[self-heal: `) to find any self-healed gate run, then differentiate by class via the rest of the marker.

### 7. Verify canary: warn-only, not fail

**Decision**: `_lint_playwright_testdir_consistency` runs in `verifier.py`, alongside `_lint_e2e_navigation` (which landed in commit `b27a96b3`). If `playwright.config.ts` `testDir` points at a directory that does not contain any `*.spec.ts` files (or contains substantially fewer than another sibling directory), emit a `warn`-level GateResult, not `fail`.

**Why warn instead of fail**: failing the verify gate would block the merge and force the agent to a re-roll. Warn surfaces the drift to the agent via the verify-gate review, who can fix it as part of the same commit cycle. The runtime self-heal is the second-chance safety net if the agent ignores the warn. Two layers, both forgiving.

**Why "substantially fewer"**: a project might legitimately keep one smoke-test spec at the canonical path while everything else lives under a feature-organized subdirectory. We avoid false-positive warns by only flagging when the testDir contains zero spec files OR when another directory contains 3x as many specs as testDir. Heuristic; tunable.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Self-heal masks a real misconfigured `playwright.config.ts` (e.g., operator intentionally pointed testDir at a different path for debugging), hiding it from the operator | Forensic logs + `[self-heal: ...]` marker in `GateResult.output`. Dashboard flags changes whose merge included a self-heal. The verify canary fires first in normal flow, giving the operator a chance to dismiss the warn before runtime self-heal would fire. |
| Regex line-replace fails for unusually formatted `playwright.config.ts` (e.g., multi-line testDir computed from a function call) | The regex is field-aware (`^\s*testDir\s*:\s*"[^"]*"`) — it matches only the canonical string-literal form. Non-matching configs cause `_resync_playwright_config_testdir` to return `False`; the gate falls through to its normal fail path with the precise testdir-mismatch error message (Layer 2a still fired). No broken rewrite. |
| Canonical-testdir resolver picks the wrong directory in projects with a non-conventional layout | The tiebreaker prefers `tests/e2e/` — the canonical path. For projects that deliberately use a different convention (rare), the warn from Layer 2c gives advance notice and the operator can suppress self-heal by adding the testDir to a project-local override file (future work, not in this change). For now: `tests/e2e/` wins. |
| The stale `e2e/global-setup.ts` content does not move correctly; Playwright crashes after self-heal because `globalSetup` points at a path with the wrong content | Rewrite copies the stale `e2e/global-setup.ts` to `tests/e2e/global-setup.ts` ONLY if the destination does not already exist. If the destination exists (canonical path is already populated), trust it and rewrite only the config. Atomic copy via `shutil.copy` after a `pathlib.Path.exists()` check — both raise on permission errors which are caught and surfaced. |
| Concurrent gate runs race on `playwright.config.ts` write | Self-heal runs in the same process as the gate; gates are serialized per change (one verify pipeline per change at a time). No cross-process write contention. The atomic `os.replace` protects against half-written state if the gate is killed mid-rewrite. |
| Future spec layout convention change makes the `tests/e2e/` tiebreaker stale | The canonical path is a constant in `gates.py` — a one-line change when (if) the convention shifts. Comment near the constant documents the rationale. |
| `_lint_playwright_testdir_consistency` false-positive on legitimate non-canonical layouts produces operator fatigue | The "substantially fewer" heuristic (3x ratio) prevents flagging projects that legitimately spread specs across multiple directories. Warn level (not fail) keeps the cost low. If false-positive rate is high in practice, tighten or add an opt-out. |

## Migration Plan

This change is **fully additive**. No existing behavior is removed or modified.

- **Deploy**: ship the gates.py and verifier.py changes via the normal set-core release. Restart any running `set-web` / sentinel processes to pick up the new code (Python module cache means a venv-level restart is required — same as for env-drift's gates.py changes).
- **Forward-compat for consumer projects**: existing scaffolds keep their `playwright.config.ts` as-is. The gate self-heal is the safety net; the verify canary surfaces any drift on the next PR.
- **Backward-compat**: the new self-heal returns `None` for any signature that doesn't match, which is a no-op for the gate flow. The verify canary returns `pass` for any project without `playwright.config.ts` (e.g. non-web projects). No behavior change for projects that don't drift.
- **Rollback**: revert the gates.py and verifier.py changes. The commit is self-contained; no schema migrations, no template overwrites.

## Alternatives Considered

### A. Fix the drift at merge time, not gate time

When the merger detects that the worktree modifies `playwright.config.ts` testDir-relevant fields and main has a different value, either auto-merge the worktree's change OR fail the merge with an actionable message. This prevents the drift from happening at all, rather than recovering downstream.

**Rejected (for this change)** because:

- The merger today merges files at the diff/conflict level, not at the structural-config level. Adding "config-aware" merging is a much larger scope (would need to model `playwright.config.ts`, `package.json`, `tsconfig.json`, and friends as structured configs with field-level merge rules). Worth doing eventually as a separate change.
- The drift's true root cause is more often a **stale main config** — the worktree's change is correct, but main never got the canonical testDir because the relevant prior change committed the legacy convention. A merge-time check would not have caught the empirical case (the worktree did NOT modify `testDir` in its commits; main was already wrong before the worktree branched).
- The gate self-heal has lower deployment cost and lower risk: it changes the recovery behavior of one already-failing path. The merge-aware approach changes a hot path that runs on every successful merge.

This change addresses the *symptom* with two layers (warn at PR-time, self-heal at gate-time). A future change, scoped separately, could address the merge-time *cause* — and the two would compose cleanly.

### B. Move spec files instead of rewriting the config

When drift is detected, walk all `*.spec.ts` files and move them into the directory the config declares as `testDir`. This aligns specs to config rather than config to specs.

**Rejected** because:

- Spec files often have relative imports that would break on move (`import { fixture } from "../fixtures"`). Self-healing requires knowing the import topology, which is too fragile.
- The dispatcher prompt and verify canary both treat `tests/e2e/` as canonical — moving specs *out* of that path goes against the convention this change reinforces.
- Rewriting one config file is one atomic operation. Moving N spec files is N file ops with N potential failure modes (in the middle of a partial move, you get a worse mess than before).

### C. Layer 2a only — improve the diagnostic, skip the self-heal

Just teach the failure parser to recognize "No tests found" and report it precisely; let the agent fix it across a retry slot. Rely entirely on the verify canary (Layer 2c) for prevention.

**Rejected** because:

- It still consumes a `verify_retry_count` slot for what is mechanically recoverable. The dep-drift / env-drift precedents established that self-heal of bootstrap mismatches is the right call for recoverable, non-ambiguous classes. Testdir-drift is in the same class.
- The verify canary is `warn`-level, not `fail` — agents may legitimately ignore warns if their attention is on the feature work. Without the runtime self-heal, ignored warns become retry-burn at integration time.

### D. Detect via Playwright reporter exit code only

Return `pass` whenever `exit_code == 1` AND output contains `Error: No tests found`. **Rejected** as a no-op: doesn't actually fix the underlying state. The next gate run would crash with the same message. Self-heal must mutate the config and prove the rerun passes before reporting `pass`.

## Forensic Visibility

Operators inspecting a self-healed run will see two new log events:

```
[INFO] set_project_web.gates: e2e_testdir_drift_detected change=<name> wt=<path> stale_testdir=e2e canonical_testdir=tests/e2e spec_count=11
[INFO] set_project_web.gates: e2e_testdir_self_heal_resynced_and_rerun change=<name> resync_duration_ms=8 rerun_outcome=pass
```

And the gate output will start with `[self-heal: synced playwright.config.ts testDir from e2e to tests/e2e]\n` — visible in the verdict sidecar, the dashboard's gate-output panel, and `set-run-logs <run-id> --gate e2e --change <name> | grep self_heal`.

The verify canary, when it fires, emits a new GateResult class:

```
[INFO] set_project_web.verifier: playwright_testdir_consistency_warn change=<name> stale_testdir=e2e canonical_candidate=tests/e2e
```

surfaced through the standard verify-gate review UI as a `warn` (yellow), not a `fail` (red).

## Open Questions

- **Should the verify canary be opt-out per project?** A small set of legitimate non-canonical layouts may exist. Defer until empirical false-positive rate is measured; add opt-out via `.set/orchestration/verify-overrides.yaml` only if needed.
- **Should the self-heal also delete stale `e2e/smoke.spec.ts` when it copies `e2e/global-setup.ts` over?** Currently no — leaving stale spec files alone is the conservative choice and only the config and global-setup get updated. Operator-driven cleanup is fine for now. Revisit if stale-spec false-fail noise becomes common.
- **Should the marker include the count of spec files moved into scope?** Currently the marker shows `from <old> to <new>` which is enough for forensics. Adding count adds noise without clear utility.
