# Change: fix-e2e-infra-systematic

## Why

A recent multi-change E2E run surfaced ~42 VERIFY_GATE retries across 10 changes (healthy target: ~10). The worst-case change absorbed 13 retries / 5 dispatches with ~11 min wall-clock wasted on e2e alone. Root-cause analysis identified four classes of waste:

1. **Template/scaffold gaps** — missing i18n baseline keys cascade into hundreds of Playwright failures; stale `.next` cache across worktrees; hardcoded Playwright timeouts; non-deterministic port allocation; per-run prisma `force-reset` with no schema-hash cache; missing convention docs for observed anti-patterns.
2. **Gate ordering** — full e2e runs BEFORE LLM gates, so a spec_verify failure after N iterations means the full e2e ran N times wasted.
3. **Retry context loses signal** — `verdict.json` stores only a 1-line summary; structured FILE/LINE/FIX blocks never reach the fix agent; same finding recurs across retries with no convergence detection.
4. **Scope-boundary violations** — an agent working on one change modifies shared code that belongs to an already-merged change, breaking its tests and consuming retry budget trying to fix the wrong surface.

A comprehensive redesign covers all four, but the risk surface grows with ambition. This change is therefore **tiered**: Tier 1 ships now as a minimal, safe, high-ROI set of template and gate-runner fixes. Tier 2 adds cross-change regression detection signals. Tier 3 is the deeper architectural work (smart-retry layers, per-gate retry counters, incremental re-verification, full scope-boundary gate, observability dashboard) and is explicitly deferred — tracked here for continuity but not implemented in this change unless a follow-up expands scope.

## What Changes — by Tier

### Tier 1 — Ship now (template + gate-runner hardening, low risk)

Pure static-source and additive-runtime fixes. Existing runs unaffected; next scaffold gets the hardened defaults. Expected to eliminate the most common non-feature-bug failure classes observed.

**Template fixes (static, no runtime change):**
- `modules/web/set_project_web/templates/nextjs/messages/{hu,en}.json` — baseline `home.*`, `nav.*`, `footer.*`, `common.*` keys mirrored across locales.
- `scripts/check-i18n-completeness.ts` — scan `useTranslations(ns)` + `t('ns.key')` against `messages/*.json`; fail on missing keys with a clear report.
- Register `i18n_check` as a pre-e2e gate (~2s, Phase 1 mechanical) in `modules/web/set_project_web/gates.py`.
- `templates/nextjs/tests/e2e/global-setup.ts` — kill any process bound to `PW_PORT` before webServer starts; validate `.next/BUILD_COMMIT` marker against current HEAD SHA, auto-invalidate `.next/` if mismatched; write marker on successful build.
- `templates/nextjs/prisma/seed.ts` (or sibling) — SHA-256 of `prisma/schema.prisma` cached in `.set/seed-schema-hash`; skip `db push --force-reset` if unchanged. Opt-out via `PRISMA_FORCE_RESEED=1`.
- `templates/core/rules/web-conventions.md` and scaffold conventions — ban `navigator.sendBeacon` for cart/order mutations; upsert unique-key discriminator rule; `data-testid="<feature>-<element>"` naming convention; REQ-id commenting convention.
- `templates/nextjs/lib/auth/storage-state.ts` — admin auth helper for storageState; docs reference.

**Gate-runner additive improvements:**
- Deterministic per-worktree port allocation: `hash(change.name) % port_range` from `e2e_port_base`. Persisted in `change.extras.assigned_e2e_port`. Falls back to dynamic allocation if absent (forward-compat).
- `playwright.config.ts` reads `PW_TIMEOUT`, `PW_PORT`, `PW_FRESH_SERVER` from env; gate-runner passes them from directive + assigned port + a fresh-server flag.
- Config drift warning on startup: if `config.yaml` mtime > `directives.json` mtime, emit `CONFIG_DRIFT` event + WARNING log.

**Scope for Tier 1 — what is NOT touched:**
- Gate ordering unchanged (full e2e stays at its current position).
- Retry flow unchanged (single `verify_retry_count`, full-pipeline re-run on fail).
- No new gates beyond `i18n_check`.
- No change to `verdict.json` schema.

Tier 1 is safe because every change is either (a) only affects newly-scaffolded projects (template files), (b) adds a new optional gate that is additive, or (c) is a pure observability log. Existing running projects see no behavior change.

### Tier 2 — Ship next (cross-change regression signal + structured findings)

After Tier 1 proves out, Tier 2 adds two targeted fixes that improve retry quality without changing gate ordering or introducing subagents:

**Structured findings in verdict.json (backward-compatible):**
- Extend `gate_verdict.py` to optionally write `findings: [{id, severity, title, file, line_start, line_end, code_context, fix_block, fingerprint, confidence}]` alongside the existing `summary`. Legacy verdicts without `findings` remain parseable.
- `retry_context` assembly uses `findings` when present, falling back to `summary` otherwise. Reviewer FIX blocks flow verbatim to the next iteration.
- Finding extractors for: build (TS errors), test (vitest/jest failures), e2e (Playwright failing tests), review (CRITICAL blocks), spec_verify (CRITICAL blocks).
- Fingerprint = first 8 hex chars of `SHA256(file:line_start:title[:50])` — stable across retries; used by Tier 3 convergence detection.

**Integration-gate cross-change regression detection:**
- When `merger._run_integration_gates` e2e phase fails, parse the failing test list. Each failing test's owning change is resolved via (a) `tests/e2e/<change>.spec.ts` file naming convention, (b) REQ-id tag from the test body, (c) `change.merged_scope_files` lookup.
- If any failing test is owned by an ALREADY-MERGED change, emit `CROSS_CHANGE_REGRESSION` event with `{current_change, regressed_tests: [{test, owning_change}]}`.
- Prepend the regression report verbatim to the agent's redispatch `retry_context`:
  > Your change broke tests belonging to already-merged feature `<X>`. These tests pass on `main`. Do NOT modify `<X>`'s code. Instead, fix your change so it doesn't affect `<X>`'s surface. Failing tests from `<X>`: ... Allowlist (your scope only): ... Touched files that overlap `<X>`'s scope: ...
- No specialized subagent (Tier 3); the main agent gets a clear framing on the redispatch.

Tier 2 is safe because findings are additive (forward-compat field), and the cross-change regression handler only affects the redispatch retry_context content — no change to which code paths fire.

### Tier 3 — Deferred (tracked here for continuity, not implemented in this change)

The following were explored in design.md but are NOT part of this change's implementation. They may form follow-up changes once Tier 1–2 ship and data justifies them:

- Gate phase restructure (mechanical → smoke → LLM → full e2e).
- Per-gate retry counters (`change.extras.gate_retries`).
- Incremental re-verification (re-run only the failing gate + diff-invalidated upstream).
- `max_phase_runtime_secs` ceiling.
- Smart-retry layer 1 (same-session quick fix) and layer 2 (targeted fix-subagent).
- Consolidated Layer 3 redispatch with per-gate budget separation.
- Convergence detection (fingerprint count threshold → Layer 3 escalation).
- Unified infra-fail classifier (across all LLM gates).
- `RESUME_CONTEXT.md` on timeout/manual-resume paths.
- Full `scope_boundary` gate (blocking) + per-change `scope_files` declaration.
- Cross-change-regression specialized Layer 2 subagent.
- Observability dashboard (per-change retry-layer histogram, metrics).

These are documented in `design.md` for reference, but tasks.md intentionally limits implementation to Tier 1 and Tier 2 only.

## Scenarios covered by this change

| Scenario | Tier | Resolution |
|---|---|---|
| Missing i18n keys cascade e2e failures | 1 | `i18n_check` gate fails fast pre-e2e with clear key list |
| Stale `.next` cache across worktrees | 1 | `BUILD_COMMIT` marker invalidates `.next/` when HEAD changes |
| Zombie `next start` on assigned port | 1 | `kill-stale-process` hook runs before `webServer` start |
| Prisma `force-reset` wastes 30s when schema unchanged | 1 | Schema-hash cache skips reset |
| Port collision between parallel worktrees | 1 | Deterministic `hash(change.name) % range` allocation |
| Playwright globalTimeout ignores gate directive | 1 | `PW_TIMEOUT` env flows from directive → config |
| User edits `config.yaml` but orchestrator uses stale `directives.json` | 1 | `CONFIG_DRIFT` warning on startup |
| Repeated `sendBeacon` / testid / upsert anti-patterns | 1 | Convention docs document + ban at authoring time |
| Agent loses reviewer FIX block on retry | 2 | `verdict.json.findings` preserves FILE/LINE/FIX verbatim |
| Agent broke already-merged feature's tests | 2 | `CROSS_CHANGE_REGRESSION` event + prescriptive retry_context |
| Same finding surfaces N times across retries | 3 (deferred) | Convergence detection — Tier 3 |
| Agent modifies files outside its scope pre-merge | 3 (deferred) | `scope_boundary` gate — Tier 3 |
| Full pipeline re-runs on every gate fail | 3 (deferred) | Incremental re-verification — Tier 3 |

Scenarios not yet addressed (Tier 3) continue to behave as today — they are not made worse by this change, but they are not yet eliminated.

## Non-goals / out of scope

- Post-merge rollback automation.
- Changes to spec_verify or review prompts beyond the finding extraction wrapper.
- Agent-side prompt tuning for scope creep.
- Auto-classification of shared-infrastructure files beyond a small hardcoded allowlist (`package.json`, `pnpm-lock.yaml`, `prisma/schema.prisma`).
- Smart-retry layered architecture (Tier 3, deferred).
- Full scope-boundary gate (Tier 3, deferred).

## Risks and mitigations

- **`i18n_check` false positive in a polyglot branch.** Mitigated by making the check accept optional template placeholders (`{interpolation}`) and running only against `useTranslations` imports, not dynamic key construction.
- **Deterministic port allocation collision.** Hash modulo on 100+ range is unlikely to collide for typical change counts (<20). Added unit test enumerates common names to verify no pairwise collision.
- **Playwright env-var regression.** A project that ships its own `playwright.config.ts` without env-var support would not benefit but would also not regress — env vars just aren't consulted. Template update is opt-in per scaffold.
- **Cross-change regression detector false negatives.** If a failing test's owning change can't be resolved (no file convention, no REQ tag), it falls through as a generic failure — no event emitted, no regression. Safe: worst case is current behavior.
- **Findings extractor fragility.** Extractors parse LLM/CLI output that may change format. Each extractor is resilient: returns `[]` on unparseable regions, logs a WARNING, pipeline falls back to `summary`-only retry context.
- **verdict.json schema forward-compat.** New `findings` field is optional; consumers must tolerate its absence. Existing dashboard code continues to read `summary`.

## Rollout strategy

1. Ship Tier 1 behind no flag. Template changes only affect `set-project init` output going forward; no impact on running projects. `i18n_check` gate rolls out with the next web-module release; can be disabled per-project via `gate_overrides.i18n_check: skip` if needed.
2. Ship Tier 2. `verdict.json.findings` is additive; consumers fall back to `summary`. `CROSS_CHANGE_REGRESSION` emits only when the detection resolves an owning change; otherwise silent.
3. Validate on next full E2E run: compare VERIFY_GATE count vs baseline. Success criterion: measurable reduction with no new failure modes.
4. If Tier 1–2 prove out, open a follow-up change for Tier 3 items, prioritized by observed remaining retry pattern.
