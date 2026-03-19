## Context

The orchestration pipeline has a complete lifecycle for changes (plan → dispatch → Ralph → verify gate → merge) but the verification layer operates only at the code-quality level (tests pass, build passes, no security issues in diff). There is no requirement-level verification — the system never checks whether the code that was written actually implements the specific REQ-* IDs assigned to the change by the digest/planner.

Current state of verification:
- `review_change()` receives only `$scope` (free text) — no structured requirement list
- `validate_plan()` warns on uncovered requirements but does not block
- `monitor_loop()` exits without checking final coverage state
- No visual reporting exists beyond the TUI (`set-orchestrate status`)
- `init_state()` does not copy `requirements[]` or `also_affects_reqs[]` from the plan to state — these fields are unavailable to downstream verification
- `populate_coverage()` always returns 0 — its call site in `cmd_plan` discards the return value

The digest pipeline (`spec-digest-pipeline` change, recently completed) provides the structured requirement data — this change leverages it.

## Goals / Non-Goals

**Goals:**
- Requirement-level verification: every REQ-* assigned to a change is checked against the implementation diff
- Coverage completeness: the system blocks or loudly warns when requirements are unassigned or unimplemented
- Visual reporting: a self-contained HTML file shows the full pipeline state (digest → plan → execution → coverage) in a browser
- Finer requirement granularity from digest to reduce the chance of lumped, untestable requirements

**Non-Goals:**
- Token budget enforcement changes (explicitly excluded per user direction)
- Automated functional/E2E test generation per requirement (would be a separate change)
- Real-time websocket dashboard (static HTML with meta-refresh is sufficient)
- Changes to the `opsx:verify` skill integration (could be wired in later, not in this change)
- Merge-blocked recovery improvements (separate concern, not verification)

## Decisions

### D1: Requirement injection into review prompt (per-change, not global)

**Decision:** Inject only the **current change's** assigned REQ-* list (typically 3-15 items) into `review_change()` prompt, with an explicit question asking the reviewer to identify unimplemented requirements.

**How:** `review_change()` reads `requirements[]` and `also_affects_reqs[]` from `$STATE_FILENAME` for the current change (using `change_name` which it already receives). Looks up each REQ-ID's title and brief from `$DIGEST_DIR/requirements.json`. Appends to the review prompt:

```
## Assigned Requirements (this change owns these)
- REQ-CART-001: Add to cart — anonymous and authenticated users can add items
- REQ-CART-002: Cart persistence — cart survives session restart

## Cross-Cutting Requirements (awareness only)
- REQ-I18N-001: All pages respond to /hu and /en routes

## Requirement Coverage Check
For each ASSIGNED requirement above, verify the diff contains implementation evidence.
If a requirement has NO corresponding code in the diff, report:
  ISSUE: [CRITICAL] REQ-CART-002 has no implementation in the diff
Cross-cutting requirements are for awareness — do not flag them as missing.
```

**Key constraint:** This is always **per-change** (3-15 REQs), never the full digest (100+ REQs). Sonnet can reliably handle 3-15 semantic matches against a 30K diff. The previous design version incorrectly suggested 100+ REQs could go into a single review — that would cause attention dilution.

**Prerequisite — D0 (init_state fix):** `init_state()` must copy `requirements[]` and `also_affects_reqs[]` from the plan JSON to `orchestration-state.json` per change. Currently these fields are not in state. Without this, `review_change()` has nothing to read. The dispatcher already expects these fields in state (dispatcher.sh reads them), but `init_state()` never writes them — this is a latent bug that this change fixes.

**`review_change()` signature:** No signature change needed. The function already receives `change_name` as `$1` and can read state internally. The helper `build_req_review_section()` takes `change_name` and returns the formatted section, or empty string if not in digest mode.

**Digest mode detection:** Check `[[ -f "$DIGEST_DIR/requirements.json" ]]` as proxy. This is consistent with how other functions detect digest mode outside of `cmd_plan` (where `$INPUT_MODE` is available).

**Retry context for REQ CRITICAL:** When a review flags a REQ as unimplemented, the retry context must include the specific REQ-IDs that were flagged (not just the truncated review output). The retry prompt should say: "The code review found these requirements have no implementation evidence: REQ-CART-002, REQ-CART-003. Implement them or explain why they are already covered."

**Alternative considered:** Wire `opsx:verify` into the gate. Rejected because: (1) it runs in a full Claude session (expensive), (2) it checks artifact coherence, not diff-vs-requirements, (3) it would need refactoring to work non-interactively in the orchestrator.

### D2: Coverage enforcement as configurable gate (default: false)

**Decision:** Add `require_full_coverage` directive (default: `false`). When true and in digest mode, `populate_coverage()` returns non-zero if `uncovered[]` is non-empty, which makes `cmd_plan` fail.

**Why default false?** The planner can legitimately leave convention-only or data-definition REQs unassigned. With finer granularity (D4) producing 100+ REQs, the planner will almost certainly miss some. A `true` default would break every first-time digest-mode plan on complex specs, contradicting "no breaking changes." Users opt in when they are confident their spec structure supports full coverage.

**Implementation — two changes required:**

1. In `populate_coverage()` (digest.sh), after computing `uncovered[]`:
```bash
if [[ "$REQUIRE_FULL_COVERAGE" == "true" && ${#uncovered[@]} -gt 0 ]]; then
    error "Coverage incomplete: $unc_count requirement(s) not assigned: $unc_list"
    error "Re-run plan or set require_full_coverage: false to proceed"
    return 1
fi
```

2. In `cmd_plan` (planner.sh), the call site must check the return:
```bash
if ! populate_coverage "$PLAN_FILENAME"; then
    error "Plan validation failed: incomplete requirement coverage"
    return 1
fi
```
Currently the call site is `populate_coverage "$PLAN_FILENAME"` with no return code check.

**Directive wiring:** `REQUIRE_FULL_COVERAGE` is read from `directives` JSON in `cmd_plan` (same pattern as other directives like `review_before_merge`). No new CLI flag mechanism needed — it goes through the existing YAML config:
```yaml
require_full_coverage: true
```

### D3: Final coverage report at ALL completion paths

**Decision:** Call `final_coverage_check()` at every exit path in `monitor_loop()`. There are **5 distinct break paths**, not 2:

| Line | Condition | Coverage check needed? |
|------|-----------|----------------------|
| ~139 | time_limit reached | YES — most common non-happy exit |
| ~145 | external stop/done | YES — user stopped, should see progress |
| ~365 | auto-replan: no new work | YES — final happy path |
| ~383 | replan-exhausted | YES — partial completion |
| ~399 | normal completion (no auto-replan) | YES — final happy path |

**Coverage status categories:** The final check must distinguish between:
- **uncovered** — no change was assigned this REQ (planner gap)
- **merge-blocked** — a change was assigned but could not merge (conflict)
- **failed** — a change was assigned but failed verification
- **merged** — successfully implemented

This requires cross-referencing `coverage.json` (REQ→change mapping) with `orchestration-state.json` (change→status). A requirement whose owning change is `failed` or `merge-blocked` is not "uncovered" — it was attempted.

**Summary email:** `send_summary_email()` currently reads only state. Add a `build_coverage_summary()` helper that reads `$DIGEST_DIR/coverage.json` + state, returns a formatted string, and is passed to the email function. The email function does not need to know `DIGEST_DIR`.

### D4: Digest prompt refinement for granularity

**Decision:** Extend the existing granularity paragraph in `build_digest_prompt()` (around line 288 which already says "One requirement = one independently testable behavior") with additional rules:

```
REQUIREMENT GRANULARITY RULES:
- Each requirement MUST describe exactly ONE testable behavior
- CRUD operations on an entity = minimum 4 separate requirements (create, read, update, delete)
- If a spec section lists multiple distinct user actions, create one REQ per action
- Edge cases and error handling explicitly mentioned in spec = separate requirements
- "Users can X and Y" = TWO requirements, not one
- A requirement is too coarse if you cannot write a single test for it without covering multiple behaviors
```

**Note:** The existing prompt already has a partial example ("Cart supports coupons" → too broad). The new rules extend, not replace, that existing text. Implementation must find the existing section and append to it rather than creating a duplicate.

**No "prefer 100+" instruction.** The previous design version included "prefer 100+ fine-grained requirements" which is counterproductive — it encourages quantity over quality and creates downstream problems with planner assignment. The granularity rules above produce naturally finer-grained REQs without an arbitrary count target.

### D5: HTML report architecture

**Decision:** Self-contained HTML file at `wt/orchestration/report.html` with `<meta http-equiv="refresh" content="15">`. Generated by a new `lib/orchestration/reporter.sh` module.

**Architecture:**
```
reporter.sh
  ├── generate_report()           — main entry, reads state + digest, writes HTML
  ├── render_digest_section()     — domain breakdown, REQ counts, ambiguities
  ├── render_plan_section()       — change table, dependency graph
  ├── render_execution_section()  — change timeline, gate results matrix
  ├── render_coverage_section()   — per-REQ traceability with status colors
  └── render_html_wrapper()       — head/style/body/footer with timestamp
```

**Atomic file write:** Use `tmp=$(mktemp)` + write to `$tmp` + `mv "$tmp" "$REPORT_PATH"`. This prevents browsers from reading a partially-written file during a meta-refresh poll. This pattern is already used in digest.sh for coverage.json.

**Data sources (full paths):**
| Section | Reads from |
|---------|-----------|
| Digest | `wt/orchestration/digest/index.json`, `wt/orchestration/digest/requirements.json`, `wt/orchestration/digest/domains/`, `wt/orchestration/digest/ambiguities.json` |
| Plan | `orchestration-plan.json`, `orchestration-state.json` |
| Execution | `orchestration-state.json` (change statuses, gate results, tokens_used) |
| Coverage | `wt/orchestration/digest/coverage.json` cross-referenced with `orchestration-state.json` (for failed/merge-blocked status) |

**Coverage status cross-reference for colors:**
- green (#4caf50) = merged (coverage status=merged AND change status=merged/done)
- blue (#2196f3) = running (coverage status=running)
- yellow (#ff9800) = planned/dispatched
- red (#f44336) = uncovered (not in coverage.json at all)
- orange (#ff5722) = failed/merge-blocked (coverage has change, but change status=failed/merge-blocked)
- gray (#757575) = skipped/removed

**When generated:**
- After `cmd_digest` completes → called directly in digest.sh
- After `cmd_plan` / `populate_coverage()` → called directly in planner.sh
- Every `monitor_loop` poll cycle → called in monitor.sh after processing changes
- On every terminal exit point in monitor_loop → called before break

**Graceful degradation:** If digest data doesn't exist (brief/spec mode), the digest and coverage sections show "Not available — running in brief/spec mode." The plan and execution sections still render from state.

## Risks / Trade-offs

**[Risk] False positive CRITICAL from requirement review** → The LLM may flag a requirement as unimplemented when it's actually implemented in a non-obvious way (e.g., via a shared utility). Mitigation: This triggers a retry (not a permanent failure). The retry context includes the specific REQ-IDs flagged, allowing the agent to either implement them or commit a comment explaining coverage. With per-change REQ counts of 3-15, Sonnet can handle the semantic matching reliably.

**[Risk] `require_full_coverage: true` blocks plans where Claude omitted a requirement** → If the planner misses assigning a REQ to any change, the plan fails. Mitigation: Default is `false` (opt-in). When enabled, the error message lists specific uncovered REQ-IDs so the user can fix the plan or disable the gate.

**[Risk] Report file I/O every 15 seconds** → With atomic write (tmp + mv), this is a single syscall per poll. A 150-200KB HTML file is negligible I/O overhead.

**[Trade-off] Merge-blocked is visible but not fixed** → The HTML report shows merge-blocked changes and the coverage section distinguishes "merge-blocked" from "uncovered." But this change does not improve merge conflict resolution itself — that remains a separate concern.

**[Trade-off] Coverage tracks lifecycle, not semantic correctness** → Even after this change, coverage status only means "the assigned change merged." It does not prove the implementation is semantically correct — only that code was written and passed the review's REQ check. Full semantic verification would require runtime tests per requirement (out of scope).
