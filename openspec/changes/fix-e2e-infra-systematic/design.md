# Design: fix-e2e-infra-systematic

## Design goals

1. **Fail fast, fix targeted, re-run minimal.** A gate failure should trigger the cheapest applicable fix mechanism, then re-run only what's necessary.
2. **Preserve signal across retries.** Reviewer FILE/LINE/FIX blocks must reach the fix agent intact, not as a truncated summary.
3. **Prevent convergence failures.** Same finding appearing N times is a planning signal, not a retry budget exhaustion.
4. **Fail-safe defaults.** Integration gate full suite remains as the pre-merge safety net. Smart retry is additive, not replacement.
5. **Incremental rollout.** Each phase shippable independently. Flag-gated so we can compare runs with/without.

## Gate execution model

### Current (observed in run-20260414)

```
┌──────────────────────────────────────────────────────────────┐
│ handle_change_done                                           │
│   → _integrate_main_into_branch (status=integrating)         │
│   → GatePipeline.run()                                       │
│       build → test → e2e → scope_check → test_files          │
│       → e2e_coverage → spec_verify → rules → review          │
│   → any blocking fail → status=verify-failed, retry dispatch │
│   → all pass → status=done, merge_queue.append               │
└──────────────────────────────────────────────────────────────┘

Retry: new agent iteration, retry_context = gate output dump,
       full pipeline re-runs from scratch.
```

### Proposed

```
┌──────────────────────────────────────────────────────────────┐
│ handle_change_done                                           │
│   → _integrate_main_into_branch                              │
│   → GatePipeline.run() with smart-retry enabled              │
│       ┌─ Phase 1 (mechanical fail-fast) ───────────────────┐ │
│       │ build → test → scope_check → test_files            │ │
│       │ → e2e_coverage                                     │ │
│       └─────────────────────────────────────────────────────┘ │
│       ┌─ Phase 2 (smoke catches env issues) ────────────────┐│
│       │ smoke_e2e (healthcheck + 1–2 critical routes)       ││
│       └─────────────────────────────────────────────────────┘│
│       ┌─ Phase 3 (LLM quality) ─────────────────────────────┐│
│       │ spec_verify → review → rules                        ││
│       └─────────────────────────────────────────────────────┘│
│       ┌─ Phase 4 (ground truth) ────────────────────────────┐│
│       │ full e2e (--grep on change.requirements)            ││
│       └─────────────────────────────────────────────────────┘│
│                                                              │
│   On any gate fail:                                          │
│       → try Layer 1 (in-gate same-session) if applicable     │
│       → try Layer 2 (fix-subagent) with structured findings  │
│       → Layer 3 (full redispatch) only if above exhausted    │
│       → convergence detection fingerprints findings          │
│       → incremental re-verification re-runs only touched     │
│         gates (diff-based invalidation)                      │
└──────────────────────────────────────────────────────────────┘
```

## Data model changes

### `change.extras['gate_retries']`

Replaces the single `verify_retry_count` with per-gate structured budgets.

```json
{
  "build": {
    "in_gate_attempts": 0,
    "subagent_attempts": 0,
    "last_layer": null,
    "last_outcome": null
  },
  "test": { "...": "..." },
  "smoke_e2e": { "...": "..." },
  "spec_verify": { "...": "..." },
  "review": { "...": "..." },
  "rules": { "...": "..." },
  "e2e": { "...": "..." }
}
```

Shared `change.redispatch_count` remains for Layer 3.

### `verdict.json` schema extension

Current format preserved; new optional `findings` array added.

```json
{
  "gate": "spec_verify",
  "verdict": "fail",
  "critical_count": 2,
  "source": "fast_path",
  "summary": "VERIFY_RESULT: FAIL with CRITICAL_COUNT: 2",
  "findings": [
    {
      "id": "CRIT-1",
      "severity": "CRITICAL",
      "title": "Welcome email not triggered on registration",
      "file": "src/app/[locale]/(shop)/regisztracio/actions.ts",
      "line_start": 45,
      "line_end": 67,
      "code_context": "await prisma.user.create(...)\n// ... no email send",
      "fix_block": "After `prisma.user.create`, call `sendWelcomeEmail(user.email)`.",
      "fingerprint": "a3f92c7e",
      "confidence": 0.95
    }
  ],
  "retry_context": {
    "compact_prompt": "<50K passthrough>",
    "structured_findings_markdown": "<rendered findings list>"
  }
}
```

`fingerprint` = 8-hex-char SHA of `(file + ":" + line_start + ":" + title[:50])`. Used for convergence detection.

### `change.extras['finding_fingerprints']`

Tracks how many times each fingerprint has appeared across retry attempts.

```json
{
  "a3f92c7e": {"count": 3, "first_seen": "2026-04-14T19:54:51Z", "last_seen": "2026-04-14T21:11:20Z", "gate": "spec_verify"},
  "b8e1f449": {"count": 2, "first_seen": "...", "last_seen": "...", "gate": "review"}
}
```

At count >= 3, the engine triggers `RETRY_CONVERGENCE_FAIL` and skips to Layer 3.

## Retry layer mechanics

### Layer 1 — in-gate same-session quick fix

**Eligibility:** gate in `{build, test, rules}`, session not stale (>60min), failure is structured (parseable into file+line).

**Flow:**
1. Gate emits `GateResult(..., status="fail", findings=[...])`.
2. Engine checks `in_gate_attempts < max_in_gate` (default 2).
3. Engine invokes `claude --resume <sid>` with a 1-shot prompt:
   ```
   Gate '{gate}' failed. Fix the following and reply with the single word "done":

   {findings_markdown_rendered_minimally}

   Scope rules:
   - Touch ONLY files listed above (plus imports they require).
   - No spec/tasks edits.
   - Commit the fix before replying "done".
   ```
4. Engine waits for agent to commit + respond.
5. Engine re-runs ONLY the failing gate.
6. On pass: continue pipeline from where we left off.
7. On fail: increment `in_gate_attempts`; if under budget, try Layer 1 again (different prompt framing); else escalate to Layer 2.

**Why same-session:** preserves agent's context, faster than cold start, no "you failed" framing.

### Layer 2 — targeted fix-subagent

**Eligibility:** any gate after Layer 1 exhausts, or gates where Layer 1 is skipped (LLM gates).

**Flow:**
1. Engine loads structured findings from `verdict.json`.
2. Engine renders a gate-type-specific prompt template:

   ```
   # fix-subagent-template: review
   You are a focused fix agent for the {change_name} change. Your ONLY job is to
   apply the following reviewer fix blocks verbatim. Do NOT modify specs, tasks,
   or anything outside the files listed.

   {findings_rendered_with_fix_blocks}

   Commit each fix with a descriptive message. When all findings are addressed,
   reply with the single word "done" and stop.

   If any finding seems wrong or inapplicable, reply "blocked: <reason>" and stop.
   Do NOT guess.
   ```

3. Engine invokes a **fresh Claude session** (no --resume):
   ```
   claude -p "{prompt}" --model sonnet --max-turns 15 --cwd {wt_path}
   ```
4. Subagent runs in isolation, commits, exits.
5. Engine inspects `git diff` since subagent started:
   - Touched `.ts`/`.tsx` (source) → re-run `build` + failing gate.
   - Touched only `.spec.ts` → re-run failing gate with `--grep` on affected tests.
   - Touched only `.md`/spec files → re-run `spec_verify` + failing gate.
   - Touched unexpected paths (violation of scope) → abort subagent, mark blocked.
6. On gate + invalidated upstream passes: continue pipeline.
7. On fail: increment `subagent_attempts`; if under budget, try again (different template variation); else Layer 3.

**Why fresh session:** isolated scope; no context pollution from prior attempts; clear mandate ("apply these fixes, nothing more").

**Subagent templates:** 6 total, one per gate type (`build`, `test`, `e2e`, `smoke_e2e`, `spec_verify`, `review`), each with its own scope rules.

### Layer 3 — full redispatch

**Eligibility:** Layers 1–2 exhausted, or convergence detection triggered, or non-recoverable gate error.

**Flow:**
1. Engine sets `status=verify-failed`, increments `redispatch_count`.
2. Engine builds a **consolidated retry_context** from all prior findings across all gates in this change:

   ```
   # Retry after exhausted smart-retry layers

   Prior attempts exhausted targeted fix budgets. You must rethink the approach.

   ## Findings across attempts (by gate)

   ### spec_verify (3 attempts)
   - [CRITICAL x3] Welcome email not triggered on registration
     File: src/app/.../regisztracio/actions.ts:45-67
     Fix block: ...
   - [CRITICAL x2] Password reset email not triggered
     ...

   ### review (2 attempts)
   ...

   ## Convergence failures
   The following findings appeared 3+ times without resolution — consider
   whether the underlying design is correct:
   - a3f92c7e: "Welcome email not triggered..." (3x on spec_verify)

   ## Prior commits
   git log --oneline main..HEAD:
   ...
   ```

3. `resume_change` dispatches the main agent loop with this retry_context.
4. Agent does full iteration, handle_change_done re-runs full pipeline.
5. If this fails too: `status=failed`.

### Convergence detection

Runs after every gate result that has `findings`.

```python
def check_convergence(change, gate, findings) -> bool:
    fps = change.extras.setdefault('finding_fingerprints', {})
    trigger = False
    for f in findings:
        fp = f['fingerprint']
        entry = fps.setdefault(fp, {'count': 0, 'gate': gate})
        entry['count'] += 1
        entry['last_seen'] = now_iso()
        if entry['count'] >= 3:
            trigger = True
            logger.error(
                "[CONVERGENCE] %s finding %s (%s) seen %dx — escalating",
                change.name, fp, f['title'][:60], entry['count']
            )
    return trigger
```

On trigger: skip to Layer 3 regardless of remaining per-gate budgets. The Layer 3 retry_context includes the convergence-flagged fingerprints so the agent sees "these exact findings resisted 3 attempts — rethink".

### Incremental re-verification

After a Layer 1 or Layer 2 fix commits, the engine computes which downstream/upstream gates need re-run.

```python
# git diff since fix started → list of touched files
touched = git_diff_names(wt_path, baseline_sha)

# Map file patterns → affected gates
def affected_gates(touched: list[str]) -> set[str]:
    gates = set()
    for path in touched:
        if path.startswith(('src/', 'lib/', 'app/')) and path.endswith(('.ts', '.tsx', '.js')):
            gates |= {'build', 'test', 'smoke_e2e', 'e2e'}
        elif path.endswith('.spec.ts'):
            gates |= {'e2e'}  # only the tests
        elif path.startswith('openspec/') or path.endswith('.md'):
            gates |= {'spec_verify', 'review'}
        elif path.startswith('prisma/'):
            gates |= {'build', 'smoke_e2e', 'e2e'}
        elif path in ('package.json', 'pnpm-lock.yaml'):
            gates |= {'build', 'test', 'smoke_e2e', 'e2e'}
    return gates

# Re-run only the failing gate + its invalidated upstreams
rerun = {failing_gate} | affected_gates(touched)

# Preserve phase ordering
ordered_rerun = [g for g in PHASE_ORDER if g in rerun]
```

Safety: the merger's integration gate runs the full suite before merge — if incremental re-verification missed something, the integration gate catches it (existing behavior unchanged).

### Infra-fail unified classifier

Extends the existing spec_verify classifier to cover all LLM gates (review, spec_verify):

```python
def classify_gate_outcome(cmd_result, output, gate_name) -> Literal["verdict", "infra", "ambiguous"]:
    # Explicit verdict sentinel present? → verdict (authoritative)
    if has_verdict_sentinel(output, gate_name):
        return "verdict"
    # Timeout marker on subprocess? → infra
    if cmd_result.timed_out:
        return "infra"
    # Stream-JSON terminal_reason = max_turns? → infra
    if parse_terminal_reason(output) == "max_turns":
        return "infra"
    # Exit != 0 AND no sentinel AND no infra marker? → ambiguous (classifier)
    if cmd_result.exit_code != 0:
        return "ambiguous"
    return "ambiguous"
```

Infra outcome → no retry budget consumed; single retry at doubled `--max-turns`; if second attempt also infra → mark gate as `skipped` with `infra_fail=True` on the event.

## Subagent isolation & safety

Each subagent invocation is **ephemeral** — a one-shot Claude session with strict scope:

- `--model sonnet` (cheap, sufficient for targeted fixes)
- `--max-turns 15` (hard cap)
- 300s wall timeout
- Working directory = change worktree only
- Prompt enforces: touch only listed files, no spec/tasks edits, commit before exit, reply "done" or "blocked"
- After return, engine validates via `git diff`:
  - Touched files ⊆ allowlist → accept
  - Touched unexpected paths → `git reset --hard` to baseline_sha, mark subagent-blocked, escalate to Layer 3

Rationale: a poorly-behaved subagent shouldn't be able to corrupt the worktree. Any out-of-scope change is reverted, and the change escalates.

## `RESUME_CONTEXT.md` for resumed changes

On `ISSUE_DIAGNOSED_TIMEOUT` recovery or `MANUAL_RESUME`, the engine writes `<wt>/RESUME_CONTEXT.md` with a consolidated summary:

```markdown
# Resume context

## Why you're resuming
Your previous session timed out at 2026-04-14T19:42 after max_phase_runtime_secs=5400.

## Prior gate findings (to address on resume)

### spec_verify (attempt 3 findings — NOT YET RESOLVED)
- [CRITICAL-1] Welcome email not triggered (src/app/.../regisztracio/actions.ts:45-67)
  Fix: After prisma.user.create, call sendWelcomeEmail(user.email).
- [CRITICAL-2] Password reset email not triggered (...)

### review (attempt 5 findings — NOT YET RESOLVED)
...

## Convergence warnings
- Finding "Welcome email not triggered" has appeared 3 times on spec_verify. 
  Previous attempts' diffs are in git log — don't repeat those approaches.

## Your previous commits (main..HEAD)
<last 30 commits>
```

The dispatcher's resume prompt references this file: "Read RESUME_CONTEXT.md first, then continue."

## Configuration

New `config.yaml` block (all fields optional, defaults match current behavior when disabled):

```yaml
orchestration:
  smart_retry:
    enabled: false  # master switch; default off during rollout

    layer_1_in_gate:
      max_per_gate: 2
      enabled_gates: [build, test, rules]
      session_max_age_secs: 3600  # skip if session older

    layer_2_subagent:
      max_per_gate: 2
      enabled_gates: [build, test, smoke_e2e, spec_verify, review, e2e]
      model: sonnet
      max_turns: 15
      timeout_secs: 300
      scope_violation_policy: abort  # abort | warn

    layer_3_redispatch:
      max_per_change: 1  # reduced from default 2-3 thanks to layers 1-2

    convergence:
      same_finding_threshold: 3
      window_attempts: 10  # only count findings within recent N attempts

    incremental_reverify:
      enabled: true
      include_upstream: true  # re-run build etc. if source files touched

  gate_order:
    # Overridable per-project; default matches the 4-phase ordering.
    phase_1: [build, test, scope_check, test_files, e2e_coverage]
    phase_2: [smoke_e2e]
    phase_3: [spec_verify, review, rules]
    phase_4: [e2e]

  e2e_scope_filter:
    enabled: true  # pre-merge e2e --grep by change.requirements
    # integration gate still runs full suite regardless

  max_phase_runtime_secs: 5400  # 90 min per change per phase; 0 = unlimited
```

## Observability

New event types emitted by the engine:

- `RETRY_LAYER_ATTEMPT` with `{layer, gate, change, attempt_num, budget_remaining}`
- `RETRY_LAYER_RESULT` with `{layer, gate, change, outcome: pass|fail|blocked|timeout}`
- `SUBAGENT_FIX_START` with `{gate, change, model, max_turns, allowlist_files}`
- `SUBAGENT_FIX_END` with `{gate, change, duration_ms, tokens, commits, outcome}`
- `RETRY_CONVERGENCE_FAIL` with `{change, fingerprints: [{fp, count, title}]}`
- `INCREMENTAL_REVERIFY` with `{change, touched_files, gates_rerun}`

Dashboard (`web/`) additions:

- Per-change retry-layer histogram (N resolved at layer 1 vs 2 vs 3).
- Convergence failure count per run.
- Subagent success rate by gate type.
- Average wall-clock savings (computed: time pre-merge pipeline would have taken × retries × (1 - layer_1_2_success_rate)).

## Test strategy

Unit tests per phase:

- **Phase A**: template snapshot tests (generated files match expected), gate-runner port allocation determinism, e2e scope filter construction.
- **Phase B**: gate ordering assertions, per-gate retry counter increment correctness, verdict.json schema extension forward-compat, incremental re-verification diff mapping.
- **Phase C**: Layer 1 prompt construction + session resume call, Layer 2 subagent invocation + scope violation handling, convergence detection state transitions, unified infra-fail classifier coverage for all gates.
- **Phase D**: event emission correctness, RESUME_CONTEXT.md rendering, metrics aggregation.

Integration tests: micro-web E2E run with `smart_retry.enabled: true` — verify retry count drops, no regressions on happy path.

E2E validation: re-run the same craftbrew spec with smart_retry enabled, compare VERIFY_GATE event counts. Success threshold: ≥30% reduction in retries, no new failure modes.
