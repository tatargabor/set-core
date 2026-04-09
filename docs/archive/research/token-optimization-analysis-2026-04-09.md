# Token Optimization Analysis — 2026-04-09

Analysis of Claude token usage in set-core E2E runs, including root-cause investigation of cache tier behavior and practical optimization levers. Conducted during the craftbrew-run-20260408-1014 and craftbrew-run-20260409-0034 runs.

## Executive Summary

The hypothetical API cost of a full craftbrew E2E run is ~$2,000-2,700 at Claude 4.x Opus pay-per-use rates. **On a Max plan this translates to $0 extra bill** (subscription covers it) until the limit is hit, at which point Anthropic automatically switches to overage pricing with 5-minute cache. The "optimizations" in this analysis primarily defer overage and improve publishable benchmark numbers — they don't reduce a real dollar invoice for Max subscribers.

Three fixes were shipped during this session (commit `9ad06070`):

1. **Session resume preservation across dispatcher retries** — biggest lever, ~$250-350 hypothetical savings per run (~15-18%).
2. **Token efficiency rule for consumer projects** — ~$220 (~11%) measured impact on agent spawn count and Bash tool waste.
3. **spec_verify gate on Sonnet with Opus escalation** — ~$20 direct + model-label fix in LLM_CALL events.

One non-fix: **forcing 5-minute cache tier is not possible and not financially beneficial** on Max plan. See section "Cache Tier — Why 1h Is Used" for the full decode of Claude Code's internal logic.

## Run Cost Breakdown (craftbrew-run-20260409-0034, 8/12 changes)

```
TOTAL at time of analysis:  $1,779.84
  cache_read:   $1,140.80  (304.2M tokens, 64%)
  cache_create: $  464.92  ( 15.5M tokens, 26%) — 100% 1h tier
  output:       $  173.92  (  2.3M tokens,  9.8%)
  input:        $    0.20
```

Per-change costs for the biggest changes:

| Change | Calls | CR(M) | CC(K) | Peak/call | Cost | Sessions | Model |
|---|---:|---:|---:|---:|---:|---:|---|
| reviews-and-wishlist | 726 | 64.1 | 3942 | 166K | $392.61 | 7 | Opus |
| product-catalog | 670 | 58.4 | 2476 | 165K | $323.95 | 7 | Opus |
| cart-and-session | 555 | 51.4 | 1813 | 163K | $270.83 | 6 | Opus |
| auth-and-navigation | 463 | 40.9 | 2774 | 164K | $265.88 | 4 | Opus |
| admin-panel | 416 | 35.9 | 1934 | 167K | $214.13 | 5 | Opus |
| content-and-seo | 294 | 23.0 | 1382 | 167K | $145.09 | 5 | Opus |
| foundation-setup | 223 | 18.7 | 466 | 135K | $94.60 | 3 | **Sonnet** |

**Key observations:**
- 5–7 sessions per change is the dominant cost driver. Each session = one cold cache start.
- Peak per-call context is 130–170K across all changes — far below the 1M window. There is no "context overflow" problem. The previously reported 141%/241% warnings were a frontend metric bug (cumulative `cache_create_tokens` divided by hardcoded 200K window).
- `cache_read` at $3.75/M dominates because the same cached prefix is read ~20× per write on average (good cache efficiency).
- Output tokens are a small fraction — agents mostly read and call tools, rarely generate long text.

## The Session-Restart Bug (fixed)

### Symptom

Investigation of product-catalog (7 sessions) revealed each change goes through multiple Ralph loop sessions, and each fix/retry iteration creates a brand-new Claude session with a cold cache:

```
Session 1:  Artifact creation             66 calls, 0.17M cc
Session 2:  Main implementation          164 calls, 0.66M cc
Session 3:  Fix #1  [COLD RESTART]        134 calls, 0.39M cc
Session 4:  spec_verify gate               60 calls, 0.20M cc
Session 5:  Fix #2  [COLD RESTART]         96 calls, 0.49M cc
Session 6:  Fix #3  [COLD RESTART]         82 calls, 0.36M cc
Session 7:  spec_verify gate #2            68 calls, 0.21M cc
```

The "fix" sessions were particularly wasteful: each one contained a `## Context Restoration \n Before fixing the issue below, RE-READ these files` preamble that explicitly instructed the agent to re-read `seed.ts`, `design.md`, `spec.md`, etc. — files that were already in the previous session's context.

### Root Cause

Three layers contributed:

1. **`_kill_existing_wt_loop()` in `dispatcher.py`** called `os.remove(loop_state_path)` before every new set-loop dispatch. This deleted the `session_id` that `engine.sh` used to resume.

2. **`init_loop_state()` in `state.sh`** hardcoded `"session_id": null` on every invocation, even if the same worktree was being re-initialized for the same change.

3. **`engine.sh` iteration==1 condition**: the Ralph loop always generated a fresh UUID on its first iteration, never attempting `--resume`, even when a valid session_id was available from a prior set-loop run.

### Fix

| File | Change |
|---|---|
| `lib/loop/state.sh` | `init_loop_state` reads and preserves prior `session_id` + `resume_failures` when the prior state's `change` field matches the current change name. |
| `lib/set_orch/dispatcher.py` | `_kill_existing_wt_loop` no longer deletes the loop-state.json — it only kills the stale PID. |
| `lib/loop/engine.sh` | Iteration 1 now attempts `--resume` when a valid `session_id` exists. The existing 5-second fast-fail fallback still handles broken resume attempts. |
| `lib/set_orch/dispatcher.py` | `resume_change` guards session reuse: merge-rebase retries, sessions older than 60 minutes, and change-name mismatches force a fresh cache. When session resume is eligible, the "RE-READ these files" preamble is skipped. |

### Test Coverage

9 unit tests for the resume eligibility logic, 5 for `init_loop_state` preservation, 4 for `_kill_existing_wt_loop` behavior, and an end-to-end bash simulation of the full dispatch → gate-retry → re-init flow. All pass.

## Efficiency Rule for Consumer Projects

`templates/core/rules/efficiency.md` (new) codifies token-saving discipline:

- No Agent spawns for tasks solvable with 1-2 Read/Grep/Glob calls
- No re-reading files already read in the same session
- No re-reading CLAUDE.md / START.md (already in system prompt)
- TodoWrite only at meaningful milestones, not every file edit
- Prefer Edit over Write for small changes
- Use Read/Grep/Glob/Edit instead of `cat`/`grep`/`find`/`sed` in Bash
- Parallel tool calls when independent

**Measured impact** comparing the previous and current runs:

| Metric | Previous run | Current run | Change |
|---|---:|---:|---:|
| Agent spawns | 110 | 12 | **-89%** |
| cat/head/tail Bash calls | 92 | 6 | **-93%** |
| Duplicate reads per session | 74 | 80 | slight +8% |
| TodoWrite calls | 192 | 117 | -39% |

## Cache Tier — Why 1h Is Used

### The binary decode

Extracted from the Claude Code 2.1.97 bundle:

```javascript
function zc({scope, querySource}) {
    return {
        type: "ephemeral",
        ...(y21(querySource) && {ttl: "1h"}),  // 1h ONLY if y21() returns true
        ...(scope === "global" && {scope})
    };
}

function y21(querySource) {
    // Bedrock backend: gated by env var
    if (backend() === "bedrock" && envBool(process.env.ENABLE_PROMPT_CACHING_1H_BEDROCK))
        return true;

    // Non-Bedrock: requires Max/Pro plan AND not in overage
    if (!(isMaxPlan() && !usage.isUsingOverage)) return false;

    // querySource must match an allowlist from remote config
    const allowlist = cached() ?? remoteConfig("tengu_prompt_cache_1h_config").allowlist ?? [];
    return querySource !== undefined && allowlist.some(p =>
        p.endsWith("*") ? querySource.startsWith(p.slice(0, -1)) : querySource === p
    );
}
```

### Decision matrix

| Situation | Cache tier | Real money |
|---|---|---|
| Max plan + under limit (current state) | **1h** (automatic) | $0 extra (covered by subscription) |
| Max plan + overage | **5m** (automatic) | Pay-per-use, standard rates |
| API key only (no Max) | **5m** (automatic) | Pay-per-use, standard rates |
| Bedrock + env var set | **1h** | AWS Bedrock pricing |

The `m6()` (Max plan check) function's purpose was confirmed by a label string in the binary: `"Sonnet 4.6 with 1M context · Billed as extra usage"` — the "Billed as extra usage" suffix appears only when `m6()` returns true, meaning the user is on a subscription where overage IS billable.

### Why forcing 5m is impossible and unwise

1. **Not controllable** — no env var, flag, or config switches the cache tier. The `ENABLE_PROMPT_CACHING_1H_BEDROCK` env var only applies to the Bedrock backend. `DISABLE_PROMPT_CACHING*` env vars disable caching entirely (catastrophic: $4,500+ per run).
2. **Not financially beneficial on Max plan** — the 1h cache tier is a feature of the Max subscription, included in the flat fee. Switching to 5m does not save real money; it would only count against the user's remaining monthly tokens slightly slower.
3. **Binary patching is untenable** — every Claude Code update would re-break it.
4. **Anthropic's pricing model is intentional** — the 1h cache is a Max-subscriber benefit. When the subscription limit is hit, Anthropic automatically drops users to the 5m cache at pay-per-use rates. Our "optimization" is already applied on the Anthropic side when it actually matters.

### Available env vars (for reference)

Found in the 2.1.97 binary:

- `ENABLE_PROMPT_CACHING_1H_BEDROCK` — Bedrock only
- `DISABLE_PROMPT_CACHING` — kills all caching, never use in production
- `DISABLE_PROMPT_CACHING_HAIKU` / `_OPUS` / `_SONNET` — per-model disable
- `CLAUDE_CODE_MAX_OUTPUT_TOKENS` — output budget cap

The `--betas <headers...>` CLI flag exists but is documented as "API key users only" — Max-plan sessions route through the subscription backend, not the direct API.

## What Could Still Be Done (Not Shipped)

### Sonnet model routing (parked)

Initial analysis suggested that routing simpler changes to Sonnet could save $500-800 per run. On closer inspection, Sonnet is significantly weaker at:

- Design token interpretation (uses shadcn defaults instead of figma-derived values)
- Component hierarchy planning (inline monoliths instead of proper decomposition)
- Figma source → Next.js server-component adaptation
- shadcn component selection (e.g., Dialog vs Sheet vs Popover)
- Edge case handling for TypeScript nullable types

**Realistic scope:** only the following change types are safely Sonnet-compatible:

- Foundation setup (config, package.json, tsconfig)
- Prisma schema + migrations
- Seed data / fixtures
- i18n translation files
- Route wiring stubs
- API endpoints with precise specs

**Not Sonnet-compatible** (require Opus):

- Any UI component work
- Auth/session logic
- Business rules with edge cases
- E2E tests
- Fix/retry iterations (need diagnosis)

The realistic savings shrink to ~$100-150 per run (only 1-2 changes per typical run are Sonnet-compatible), and require per-change model annotation in the plan. Deferred until a future change.

### Per-change token budget enforcement

A hard cap per change (e.g., max 200K cache_create OR 100 tool calls) with automatic pause + escalation would prevent runaway loops. Not implemented yet; runs currently rely on `max_iterations` and `max_turns` as soft limits.

### spec_verify max-turns reduction

Current setting is `--max-turns 40`. Median observed usage is 28 turns. Dropping to 25 would force more focused verification and save marginal cost (~$30-50), but may increase false negatives. Not worth it alone.

### set-usage monitoring before big runs

Before starting a full E2E run, check `set-usage` 5h/weekly windows. If close to the Max plan limit, reduce parallelism or postpone — overage at standard rates is significantly more expensive than waiting.

## Key Data Points

### Session duration distribution (current run)

```
  median duration: 334s (5.6 min)
  mean duration:   542s (9.0 min)
  max duration:    1983s (33.0 min)
```

### Call gap distribution (within session)

```
  median gap:    2.8s
  mean gap:      6.0s
  gaps > 5 min:  4 / 3,496  (0.1%)
  gaps > 1 hour: 0 / 3,496
```

This is why 5m cache tier would work fine technically — sessions are continuous enough that the cache would almost never expire mid-session. The problem is we can't select the tier.

### Base context per session

```
median: 30K tokens (system prompt + CLAUDE.md + rules + initial user prompt)
mean:   30K
max:    41K
min:    27K
```

Each new session pays this as fresh cache_create. Reducing session count (via the resume fix) is the main lever here.

### Tool usage across all sessions (3,562 tool calls total)

```
  Bash             1,081  (30.3%)
  Read               988  (27.7%)
  Write              424  (11.9%)
  Edit               393  (11.0%)
  TodoWrite          192  ( 5.4%)
  Glob               158  ( 4.4%)
  Grep               144  ( 4.0%)
  Agent              110  ( 3.1%) → reduced to 12 with efficiency rule
  Skill               44  ( 1.2%)
  ToolSearch          28  ( 0.8%)
```

## Projected Impact on Next E2E Run

Extrapolating from the current run ($1,780 at 8/12 changes → ~$2,670 at full 12/12):

| Metric | Current (unfixed) | With all three fixes | Delta |
|---|---:|---:|---:|
| Session cold starts | ~60 (12 changes × 5 avg) | ~36 (12 × 3 avg) | **-40%** |
| cache_create | $700 | $420 | -$280 |
| cache_read | $1,700 | $1,440 | -$260 |
| spec_verify gate | $220 | $75 (Sonnet) | -$145 |
| **Total run** | **~$2,670** | **~$2,000** | **~-$670 (-25%)** |

These are hypothetical API-pricing numbers. On Max plan the real benefit is "25% less subscription token usage", not "$670 back on the invoice."

## Related Commits

- `9ad06070` — `perf: preserve Claude session across dispatcher retries + efficiency rule` (session resume fix + efficiency rule + spec_verify Sonnet)
- `616b4963` — `docs(openspec): fix-context-window-metric change proposal` (the 141%/241% metric bug)
- `61ec` / `5600` (memory refs) — prior investigations of the same metric bug, now captured in the OpenSpec change

## Files Referenced

- `lib/loop/state.sh` — `init_loop_state` session preservation
- `lib/loop/engine.sh` — Ralph loop session selection
- `lib/set_orch/dispatcher.py` — `_kill_existing_wt_loop`, `resume_change`, `_build_resume_preamble`
- `lib/set_orch/verifier.py` — `_execute_spec_verify_gate` (Sonnet fix), `_capture_context_tokens_end` (metric bug)
- `templates/core/rules/efficiency.md` — token-efficiency rule (new)
- `web/src/components/ChangeTable.tsx:99,106,201` — frontend 200K hardcode (not yet fixed — captured in `fix-context-window-metric` change)
- `openspec/specs/context-window-metrics/spec.md` — stale metric formula (not yet fixed)

## Open Questions for Future Analysis

1. **When does a Max plan actually hit overage?** We know the 5h and weekly windows from `set-usage`, but not how they interact with E2E runs of this scale. Worth measuring.
2. **Is the 1h cache allowlist user-specific or global?** The `tengu_prompt_cache_1h_config` remote config might vary. Worth testing with a fresh Anthropic account.
3. **Does `--bare` mode change the cache tier?** The flag disables hooks/LSP/auto-memory and forces API key auth. If it bypasses `m6()`, it might route through the 5m tier — at pay-per-use cost. Test before relying on.
4. **Can we influence `querySource` from the CLI?** Our calls show `repl_main_thread` implicitly. If a non-allowlisted querySource (e.g., `sdk`) can be forced, 5m tier could be selected — but with unknown consequences for other features.

---

*Analysis conducted by Claude Opus 4.6 (1M context) with tg during session on 2026-04-09.*
