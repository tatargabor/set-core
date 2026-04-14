# Change: fix-e2e-infra-systematic

## Why

The craftbrew-run-20260414-0140 E2E run surfaced **42 VERIFY_GATE retries across 10 changes** (healthy run target: ~10). Two changes absorbed ~65% of the waste: `promotions-and-email` (13 retries, 5 dispatches, ~11 min of wall-clock wasted on e2e alone) and `checkout-and-orders` (14 retries, 4 dispatches). Root-cause analysis of session JSONLs, events, and templates identified that the vast majority of these retries were NOT feature bugs — they were **infrastructure, gate-ordering, and retry-context deficiencies** that the agent was forced to chase repeatedly.

### What broke

Three classes of problems compound each other:

**1. Template and scaffold gaps** cause every new web project to inherit the same bugs. Observed: missing `messages/{hu,en}.json` baseline keys (`home.*`, `nav.*`, `footer.*`) causing a single hydration error to cascade into ~200 Playwright failures; hardcoded `globalTimeout` in `playwright.config.ts` that ignores the gate's `e2e_timeout`; no stale-process kill before `webServer` (zombie `next start` from prior worktrees blocks the port); no BUILD_ID marker to invalidate `.next` cache across sessions; no deterministic port allocation (hash-based) for parallel worktrees; `prisma db push --force-reset` on every run (~30s) with no schema-hash cache; no storageState helper (login-per-test copy-pasted everywhere); no testid cross-check linter; no REQ→test binding enforcement.

**2. Gate ordering is suboptimal.** Current order runs the expensive full e2e (~100s) BEFORE the expensive LLM gates (spec_verify ~267s, review ~100s). When spec_verify or review fails after 6 iterations, the full e2e has run 6 times too. For `promotions-and-email`, this alone was ~11 minutes wasted.

**3. Retry is all-or-nothing and loses context.** A single gate fail triggers a full pipeline re-run (build + test + e2e + spec_verify + review) with the retry delivered as a `retry_context` blob. The agent loses the structured FILE/LINE/FIX blocks from the reviewer because `verdict.json` stores only a 1-line summary. Same findings repeat across attempts (observed: "Gift card upsert overwrites recipient email" surfaced on 5 consecutive review cycles). No convergence detection — the loop consumes all retry slots on the same finding.

### Why one big change

The three classes are entangled. Fixing only templates leaves the gate-ordering waste. Fixing only ordering doesn't help the same-finding-N-times problem. Fixing only the retry layer doesn't help a run that keeps tripping on missing i18n keys. A coherent design covers all three with one unified retry/gate-ordering architecture plus a template/scaffold hardening pass.

## What Changes

Four phases with clear boundaries, each shippable independently but designed to compose:

### Phase A — Template & scaffold hardening

Static-source fixes that ship with the nextjs web template and core rules. No runtime architecture change.

- Template: complete `messages/{hu,en}.json` baseline (`home.*`, `nav.*`, `footer.*`, `common.*`) + `scripts/check-i18n-completeness.ts` lint.
- Template: `playwright.config.ts` — `globalTimeout` via `process.env.PW_TIMEOUT`, deterministic `webServer.port` via `process.env.PW_PORT`, disable `reuseExistingServer` default.
- Template: `tests/e2e/global-setup.ts` — BUILD_ID marker (`.next/BUILD_COMMIT`) validated against current HEAD SHA, auto-invalidate `.next` if mismatched; kill-stale-process hook (port-scoped) before `webServer` starts.
- Template: `prisma/seed.ts` schema-hash cache (skip `db push --force-reset` if Prisma schema unchanged since last seed).
- Template: `lib/auth/storage-state.ts` helper + planning-rules reference — agents can copy-paste the storageState pattern.
- Template: `craftbrew-conventions.md` + `templates/core/rules/web-conventions.md` extensions — `sendBeacon` ban, testid naming scheme, REQ-id commenting convention in specs, upsert unique-key discriminator rule.
- Gate-runner: deterministic port allocation per worktree (hash of change name → port offset in `e2e_port_base` range).
- Gate-runner: change-scoped e2e execution (`--grep` constructed from `change.requirements` REQ-ids).
- Config: `config.yaml` → `directives.json` drift detection — warn on startup if yaml mtime > directives.json mtime, auto-regenerate if safe.

### Phase B — Gate ordering + incremental re-verification

Reorder pre-merge gates to fail-fast cheap + delay expensive, and re-run only the failing gate (+ upstream invalidation) after a fix.

New gate order:

```
Phase 1: Mechanical cheap (fail-fast)
  build → test → scope_check → test_files → e2e_coverage

Phase 2: Smoke (catches broken server/env in ~20s)
  smoke_e2e (healthcheck + 1–2 critical routes, scope-bounded)

Phase 3: LLM quality gates
  spec_verify → review → rules

Phase 4: Ground-truth verification
  full e2e (--grep on change.requirements)
```

Per-gate retry counters in `change.extras['gate_retries']` replace the single `verify_retry_count`. Each gate carries its own `in_gate`, `subagent`, and shared-redispatch budget. Incremental re-verification: after a fix, determine invalidated upstream gates from the diff (touched `.ts/.tsx` → re-run build; touched only `.spec.ts` → re-run that test subset only; touched only `.md` → re-run spec_verify only) and re-run only that subset — the full pipeline runs again only on full-redispatch.

`verdict.json` schema extended with `findings: [{severity, id, title, file, line_start, line_end, code_context, fix_block, confidence}]` — structured, not truncated summaries.

### Phase C — Smart retry layers

Three retry layers per gate, each with its own budget and escalation path.

**Layer 1 — In-gate same-session quick fix.** For mechanical gates (`build`, `test`, `rules`), when a gate fails the engine sends a targeted prompt to the SAME agent session via `claude --resume <sid>`: just the failure diagnosis and the files to touch. Agent replies, engine re-runs only that gate. Max 2 in-gate retries per gate. No full pipeline re-run. Preserves session cache and avoids "you failed" framing.

**Layer 2 — Targeted fix-subagent.** For LLM and structural gates (`spec_verify`, `review`, `e2e`, `smoke_e2e`), after Layer 1 exhausts (or is skipped for non-mechanical gates), the engine spawns a **fresh Claude session** as a dedicated fix-subagent with the structured findings. Scope is tightly bounded (specific file allowlist, no spec/tasks editing, sonnet model, max_turns=15, 300s timeout). The subagent commits its fix and returns. Engine re-runs the gate + any upstream gates the subagent's diff invalidated. Max 2 subagent retries per gate.

**Layer 3 — Full redispatch.** Only when Layers 1–2 can't resolve — fall through to the current architecture: set `status=verify-failed`, enqueue full redispatch with consolidated `retry_context` (includes per-gate findings verbatim, not truncated). Max 1 full redispatch per change (down from 2–3 today, because Layers 1–2 catch most cases).

**Convergence detection.** Fingerprint each finding (`hash(file+line+title[:50])`). Across retries, if the same fingerprint resurfaces 3 times, skip to Layer 3 with a "SAME FINDING N TIMES — rethink approach" framing. Prevents the 5-same-finding loop observed on `promotions-and-email`.

**Unified infra-fail classification.** Extend the spec_verify infra classifier (already handles `timed_out=True`) to cover all gates: LLM `exit=1 && VERIFY_RESULT present in tail` → verdict (not infra); CLI timeout, `max_turns` without verdict, subprocess crash → infra. Infra fails do NOT consume retry budget.

### Phase D — Observability + tuning

Metrics and dashboard hooks so we can tune the retry policy based on production signal, not guesses.

- New event types: `RETRY_LAYER_1_ATTEMPT`, `RETRY_LAYER_2_ATTEMPT`, `RETRY_LAYER_3_ATTEMPT`, `RETRY_CONVERGENCE_FAIL`, `SUBAGENT_FIX_START`, `SUBAGENT_FIX_END`.
- Dashboard: per-change retry-layer histogram (how many attempts resolved at which layer).
- Metrics in `orchestration-state`: `metrics.retry_layer_success_rate` (per layer), `metrics.convergence_failures`, `metrics.avg_retries_per_gate`.
- `RESUME_CONTEXT.md` — on `MANUAL_RESUME` or `ISSUE_DIAGNOSED_TIMEOUT` recovery, engine writes a worktree-scoped summary of all prior findings (spec_verify + review + e2e + build) for the resumed agent to load.

## Scenarios covered

The design handles each of the following:

| Scenario | Resolution |
|---|---|
| Build fails (TS errors) | Layer 1 in-gate quick fix → re-run build only |
| Unit test fails | Layer 1 in-gate quick fix → re-run test only |
| Smoke e2e fails (server 500, env broken) | Layer 2 subagent (isolated, small scope) → re-run smoke only |
| spec_verify reports CRITICAL | Layer 2 subagent with structured findings → re-run spec_verify only |
| Review reports CRITICAL | Layer 2 subagent applies FIX blocks verbatim → re-run review only |
| Full e2e fails (3/20 tests) | Layer 2 subagent + `--grep` on failing tests → re-run those 3 only |
| Rules (lint) fails | Layer 1 mechanical fix → re-run rules only |
| Multiple gates fail same pipeline | Stop at first blocker, fix, re-run (unchanged — safer than continuing on broken code) |
| Gate flakes (intermittent) | Layer 1 retry same-session often passes on re-run (jitter) |
| Subagent can't fix | Escalate to Layer 3 (full redispatch) with accumulated findings |
| Subagent breaks upstream gate | Diff-based invalidation re-runs upstream gates; convergence detection catches if subagent keeps regressing |
| Per-attempt timeout | Kill + count as attempt; after budget exhausted, escalate layer |
| Infinite-loop same finding | Convergence detection fires at N=3, escalates to Layer 3 with rethink framing |
| Supervisor restart mid-retry | Already handled by fix-supervisor-restart-merge-bypass (just landed) |
| Agent session expired (>60min) | Layer 1 skipped; Layer 2 always fresh session anyway |
| Worktree manually edited | Detected at Layer 3; full pipeline replay (conservative) |
| Gate infra fail (max_turns, timeout, crash) | Unified classifier → NO retry budget consumed → gate retries at same budget |
| Architecture refactor needed | Convergence detection + Layer 3 escalation with "rethink approach" framing |
| Scope-filtered e2e misses broader regression | Integration gate in merger runs full suite before merge — safety net unchanged |

## Non-goals / out of scope

- Removing the integration gate full-suite run in the merger. The merger's full e2e remains as the pre-merge safety net; pre-merge e2e in Phase 4 runs with `--grep` to be faster, but the integration gate is comprehensive.
- Cross-change regression detection (Scenario M). The current integration gate + automatic post-merge rollback handles this; not this change's scope.
- Replacing the spec_verify/review LLM models or their prompts beyond adding structured finding extraction.
- Agent prompt tuning for scope creep mitigation. Convention docs (Phase A) ship updated guidance; deeper agent-side work is a separate effort.

## Risks and mitigations

- **Complexity.** 4 phases, ~3 weeks dev. Mitigated by explicit phase boundaries — each phase is independently shippable and useful. Phase A alone would save ~30% of run-20260414 retries by itself.
- **Retry masking real failures.** Smart retry + incremental re-verification could let a subagent fix one gate while breaking another that isn't re-verified. Mitigated by (a) diff-based invalidation of upstream gates, (b) integration gate runs full suite, (c) convergence detection on repeated findings.
- **Token cost.** More subagent invocations. Each subagent is ~15 turns × sonnet, versus full-redispatch main-agent iteration which is 80+ turns × opus. Net token savings estimated 40–60% per retry based on observed run data.
- **Config surface growth.** New `smart_retry` block in `config.yaml`. Mitigated by sane defaults that match current behavior when `smart_retry.enabled: false`.
- **Stale state during phase rollout.** Migrating `verify_retry_count` → per-gate counters requires a forward-compat read path (existing state files read as defaults). Addressed in Phase B tasks.

## Rollout strategy

1. Ship Phase A behind no flag — pure template/scaffold hardening. Validates immediately on next craftbrew-run.
2. Ship Phase B behind `smart_retry.enabled` flag, default off initially. Smoke-test on a single change with small scope first, then enable for full runs.
3. Ship Phase C behind the same flag. Run micro-web E2E with it on, compare retry counts.
4. Ship Phase D observability. Use it to tune counters and thresholds over 2–3 full runs.
5. Flip default to `smart_retry.enabled: true` once metrics show ≥30% retry reduction without regressions.
