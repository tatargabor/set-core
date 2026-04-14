# Design: fix-retry-context-signal-loss

## Context

A long-running E2E orchestration surfaced a failure pattern in which a single change exhausted its `max_verify_retries` budget while the implementation agent repeatedly modified shared files outside its scope. Analysis of the journal, orchestration-events JSONL, and stored retry_context payloads identified three compounding root causes, all rooted in the same class of defect: **the signal that the impl agent needs in order to converge on a fix is truncated, missing, or drowned in LLM-transcript noise before it reaches the agent prompt**.

This design document walks through each bug with concrete log evidence and explains the structural fix and the test coverage that would have caught each regression.

## Goals

- Preserve the tail of Playwright output in every retry_context so assertion errors reach the impl agent.
- Stop treating LLM `max_turns` / timeout / crash as a code-level spec_verify failure.
- Ensure fresh consumer projects exercise the unit test gate by default.
- Unify all LLM-bound output truncation on `smart_truncate_structured` and detect regressions automatically.

## Non-Goals

- Redesigning the spec_verify prompt, the planner, or the scope_check gate. Out of scope.
- Changing verify retry arithmetic or the review gate (both work correctly).
- Adding new failure classification types beyond the minimum needed (PASS / FAIL / skipped-infra).

## Evidence Summary

All evidence references come from the same orchestration run and the `promotions-and-email` change journal/events. References are by field name + event timestamp and `seq` in the change journal, which map directly to lines stored under `journals/<change>.jsonl` and `orchestration-events.jsonl`.

### Bug A — head-only truncation of e2e retry_context

The retry_context string stored on the change after the second E2E failure (`seq=49`, total length 4741 chars) contains:
- A ~1500 char failing-test header listing 33 test file:line entries.
- An `E2E output:` section of about ~500 chars, ending inside prisma generate output with the sentence `"Running generate... ["` (literal mid-line cut).

Source of the cut: `modules/web/set_project_web/gates.py:645`:

```python
f"E2E command: {e2e_command}\nE2E output:\n{e2e_output[:2000]}\n"
```

The Playwright failure stack traces and `expected/got` messages live near the tail of the 32 000-char raw output (we verified this by reading the stored `e2e_output` field in state, which uses `smart_truncate_structured` with a 8000-char budget and does contain the tail content). The retry_context path alone head-slices and drops that evidence.

**Downstream symptom — scope creep**: over the subsequent fix iterations, the impl agent authored commits 67feac8, 989f522, 5e2f65a, fb4ebf0, 30bd3d7 that modified `src/app/api/auth/login/route.ts`, `src/app/api/cart/update-qty/route.ts`, `src/app/[locale]/(shop)/belepes/actions.ts`, `src/app/[locale]/(shop)/belepes/login-form.tsx`, `src/app/[locale]/(shop)/regisztracio/register-form.tsx`, `src/app/[locale]/(shop)/kavek/FilterSidebar.tsx`, and `src/app/[locale]/(shop)/page.tsx` — none of which were declared in the change's proposal Impact section. The final diff against `main` showed 76 files changed / +4529 lines. When the agent cannot distinguish "my new code broke these tests" from "these tests were always broken", it guesses, and the guess is often to rewrite the test's target module.

### Bug B — spec_verify treats max_turns as gate FAIL

LLM_CALL events for the `promotions-and-email` change across the final iteration:

```
17:04 LLM_CALL spec_verify sonnet  exit=1  0/0 tokens     (immediate crash)
17:09 LLM_CALL spec_verify opus    exit=0  ~2M tokens     (verdict: PASS)
17:15 LLM_CALL review      opus    exit=0  ~480K tokens   (verdict: FAIL, 3 critical)
17:41 LLM_CALL spec_verify sonnet  exit=1  0/0 tokens     (immediate crash)
17:48 LLM_CALL spec_verify opus    exit=1  471s  0 tokens (max_turns)
```

Entry 17:48: the `retry_context` persisted on the change (`seq=91`, 3631 chars) is the partial stream-json output of the LLM itself. The tail contains:

```
{"tool_name":"Bash","tool_input":{"command":"npx tsc --noEmit 2>&1 | tail -20"}},
{"tool_name":"Bash","tool_input":{"command":"npx tsc --noEmit 2>&1 | tail -30"}},
{"tool_name":"Bash","tool_input":{"command":"npx tsc --noEmit 2>&1 | tail -30"}},
{"tool_name":"Bash","tool_input":{"command":"npx tsc --noEmit"}}
...
"terminal_reason":"max_turns","errors":["Reached maximum number of turns (40)"]
```

The LLM ran `npx tsc --noEmit` four times with slightly different flags, exhausted its 40-turn budget, and never produced a `VERIFY_RESULT` sentinel. The gate code at `lib/set_orch/verifier.py:2948` sees `exit_code != 0` and classifies this as a real failure:

```python
if verify_cmd_result.exit_code != 0:
    return GateResult(
        "spec_verify", "fail",
        retry_context=f"Verify failed. Fix the issues.\n\nVerify output:\n{verify_tail}\n\n..."
    )
```

Consequence: `verify_retry_count` incremented from 3 to 4, status set to `verify-failed` → `running`, impl agent re-dispatched with the useless transcript as its fix prompt. The change was one retry away from terminal failure when the run was halted.

### Bug C — unit test gate is off by default

The directives file written at orchestration start (`set/orchestration/directives.json` in the run directory) contained `test_command = ""`. Consequently every change in the run reported `test_result: skipped`, including `promotions-and-email` which introduced pure-function modules (`src/lib/gift-card-code.ts` — a code generator; `src/server/promotions/coupon-validator.ts` — a validator). Unit tests would have executed in seconds and exercised logic that otherwise has to be rediscovered through e2e failure.

Source of the default: `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` line 8:

```yaml
# test_command: pnpm test
```

Commented out. The `package.json` the scaffold writes contains `"test": "vitest run"` and `"vitest": "^3.0.0"`, so the command is runnable — the default simply does not request it.

### Truncation audit

`grep` over `lib/set_orch/` and `modules/` for head-only slice patterns on stdout/stderr/output identified:

| File:line | Slice | Bound for LLM? | Fix priority |
|---|---|---|---|
| `modules/web/set_project_web/gates.py:645` | `e2e_output[:2000]` | yes (retry_context) | HIGH — Bug A |
| `lib/set_orch/verifier.py:2008` | `e2e_output[:8000]` | yes (phase_e2e_failure_context, feeds replan) | MEDIUM |
| `lib/set_orch/verifier.py:2764` | `review_output[:1500]` | yes (review_history, shown to subsequent review rounds) | MEDIUM |
| `lib/set_orch/cli.py:693` | `result.output[:2000]` | no (CLI JSON echo) | LOW |
| `lib/set_orch/orch_memory.py:150` | `result.stdout[:2000]` | no (memory recall fallback) | LOW |
| `lib/set_orch/planner.py:1949` | `result.stdout[:10000]` | no (planner debug file) | OK |
| `lib/set_orch/chat.py:490` | `output[:500]` | no (chat echo) | OK |

The repository already has `lib/set_orch/truncate.py` with `smart_truncate_structured(text, max_chars, head_ratio=0.3, keep_patterns=...)`. This utility preserves head + tail + a capped middle selection of lines matching an error-pattern regex. Every LLM-bound call site in the audit should route through it. The plain-logging sites can remain as-is.

## Decisions

### D1: Single unified truncation utility (not per-call-site hand-rolling)

Reuse `smart_truncate_structured`. It was purpose-built for exactly this (see `openspec/specs/smart-truncate/spec.md`) but the web module's gates were added later and the call site at gates.py:645 was never migrated. Migrating the remaining sites in verifier.py at the same time closes the audit gap.

Alternative considered: build a Playwright-specific reporter parser that extracts the structured failure JSON and formats it into retry_context. Rejected as a larger scope — this change is about signal preservation; a structured reporter is a legitimate future improvement but not prerequisite to fixing the bug. Note, however: if `--reporter=list,json` were the default for Playwright in the scaffold, `smart_truncate_structured` would have richer tail content to preserve, so this is a complement rather than an alternative.

### D2: Classify spec_verify outcomes instead of extending exit_code semantics

Three outcome categories (LLM verdict / infrastructure / ambiguous) as described in the `spec-verify` delta. Infrastructure failure gets ONE retry at doubled budget, then abstains. Rationale:

- Infrastructure failures don't map to "fix the code"; retrying with the same budget just consumes the retry slot for nothing.
- Doubling the budget on ONE retry gives sonnet/opus a chance to recover from rare cases where 40 turns genuinely wasn't enough.
- Abstaining (gate skipped with anomaly event) is preferable to false-failing; the merge is blocked by other gates anyway (review, e2e), and the anomaly event surfaces the infra problem for operator attention rather than silently wasting retry budget.
- The `retry_context` field on an abstain is empty. The impl agent is not re-dispatched when the gate returns `skipped`.

Alternative considered: make every gate fallback conservative (fail on any non-PASS). Rejected because it compounds the problem this change exists to solve.

Alternative considered: extend max-turns to 100 unconditionally. Rejected because a runaway prompt (e.g., repeating `tsc --noEmit`) will saturate any budget; doubling once is a sensible one-shot recovery but we should NOT keep doubling.

### D3: Observability via new event field, not new event type

Prefer `data.infra_fail=True` on the existing `VERIFY_GATE` event. Rationale: existing dashboards, log filters, and the supervisor consume `VERIFY_GATE`; a new `GATE_INFRA_FAIL` event type would require updates in all those consumers. A single boolean field is additive and backward-compatible.

If a future change needs a distinct event type for broader use (e.g., build/test infra failures), that event can be introduced alongside the field.

### D4: test_command default-on, not opt-in

The scaffold already installs vitest; the script already exists. Turning the command on by default is a one-character YAML change and the gate gracefully skips when no tests exist. Alternative: make it a prompt during `set-project init`. Rejected — init flows are already long; opt-in defaults for "obviously-should-be-on" settings tend to stay off forever.

## Risks and Trade-offs

| Risk | Mitigation |
|---|---|
| `smart_truncate_structured` with a 6000-char budget prints larger retry_context → larger LLM prompt → more tokens per retry | Playwright output is rarely near that budget in practice, and the signal value more than offsets the extra tokens. The current budget was 2000; increasing to 6000 trades about 4K extra prompt chars for actionable error messages. |
| Doubling max-turns on retry could increase LLM cost on runaway prompts | Only doubles ONCE. After that, abstain. The current behavior loops on max-turns indefinitely until `verify_retry_count` is exhausted — each iteration costs 900s timeout budget — so the new behavior is cheaper, not more expensive. |
| `GATE_INFRA_FAIL` / `infra_fail: true` might hide real code failures if the classification logic mis-detects | `terminal_reason: max_turns` is a deterministic string from the stream-json header and cannot be mistaken for a `VERIFY_RESULT: FAIL` sentinel. The classifier fallback path still runs for ambiguous output without a sentinel and without a detectable infra cause. |
| `test_command: pnpm test` default might fail noisily on consumer projects that don't ship vitest | The scaffolds we ship do install vitest; external plugins can override. The existing skipped-on-no-tests handling is robust. If a project has `"test"` that genuinely fails, that's already a project problem surfaced earlier rather than later. |
| Audit test over source files (forbid new `[:N]` slices bound for LLM) adds friction for contributors | The test can be scoped to files matching `**/gates.py`, `**/verifier.py`, `**/engine.py`, `**/dispatcher.py`, `**/merger.py` + an opt-in regex. A contributor adding a new head-only slice will see a clear failure pointing to the truncation utility. |

## Migration Plan

All changes are additive or backward-compatible at the behavioral level. There is no consumer-visible config migration.

1. **gates.py** — the E2E retry_context swap from `e2e_output[:2000]` to `smart_truncate_structured(e2e_output, 6000)` is a drop-in with no contract change. The return shape of GateResult is unchanged; only the content of retry_context differs.
2. **verifier.py spec_verify** — the three-category classification replaces the `exit_code != 0` blanket branch. The existing sentinel-based paths are unchanged. New behavior kicks in only when the existing branch would have fired (i.e., no new gate failures, only better classification of existing failures).
3. **verifier.py audit sites** — `[:8000]` and `[:1500]` swaps to `smart_truncate_structured`. Preserves behavior for small inputs; improves evidence preservation for large inputs.
4. **config.yaml** — uncomments one line. Existing consumer projects are not touched (this template runs at `set-project init` time only).

Rollback: revert the PR. The only state-touching side effect is the addition of `infra_fail` to event data payloads; rolling back simply stops emitting that field.

## Open Questions

- Should the infra-retry budget (`--max-turns 80` on retry) be configurable via `directives.json`? Default seems sensible; making it configurable adds a knob we may never need. Deferring unless an operator asks.
- Should the `skipped` gate result block merge? Current policy is: skipped gates do not block. Infra-failed spec_verify is `skipped`, so the merge proceeds if all other gates pass. This is consistent with existing behavior for genuinely-skipped gates (e.g., no tests → test gate skipped → merge OK). If operators want a stricter policy, that's a follow-up.
- Should we write the Playwright JSON reporter change (configure `--reporter=list,json` in the scaffold) as part of this change or a follow-up? Argument for here: it materially improves what `smart_truncate_structured` has to work with. Argument against: it's orthogonal and could be tackled independently. Leaning toward a follow-up for scope hygiene.
