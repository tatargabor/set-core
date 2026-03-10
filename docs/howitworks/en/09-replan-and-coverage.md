# Replan and Coverage

## Auto-Replan

Auto-replan handles multi-phase specifications. When all changes in a phase are completed, the system automatically plans and starts the next phase.

### Activation

```yaml
auto_replan: true
```

### Process

1. The monitor loop detects that every change is `merged` or `failed`
2. If `auto_replan: true` → `cmd_replan()` call
3. The planner receives the updated specification + the list of completed phases
4. A new plan is generated for the next phase
5. Previous token counters are saved (`prev_total_tokens`)
6. State is reset with the new plan
7. The monitor loop continues execution

### Retry Logic

If replan fails (e.g., the LLM can't generate a good plan):

- Max `MAX_REPLAN_RETRIES` (3) consecutive attempts
- Failed replan → warning + wait for next poll
- If it fails 3 times → the orchestrator stops

### All-Done Detection

The orchestrator considers the run "done" when:

1. There are no `pending` or `running` changes
2. There are no merge queue items
3. `auto_replan` is false OR the replan signals "no more phases"

```
Phase 1: [A, B, C] → merged → replan
Phase 2: [D, E]    → merged → replan
Phase 3: no more   → done
```

## Manual Replan

The user can request a replan at any time:

```bash
wt-orchestrate replan
```

This is useful when:

- The specification changed during execution
- The user added new tasks
- Some changes failed and a new approach is needed

Manual replan:

1. Preserves the state of `merged` changes
2. Takes `failed` changes into account
3. Generates changes only for new/modified tasks

## Requirement Coverage

The coverage system is based on the REQ-XXX identifiers from the digest. Its purpose: ensure that every requirement in the specification is covered by implementation.

### Coverage Report

```bash
wt-orchestrate coverage
```

Output:

```
━━━ Requirement Coverage ━━━

Coverage: 12/15 (80.0%)

Status breakdown:
  ✓ merged:     8
  ◐ running:    3
  ○ pending:    1
  ✗ failed:     1
  · unassigned: 2

Details:
  REQ-001  ✓  JWT authentication      → auth-system (merged)
  REQ-002  ✓  User profile            → user-profile (merged)
  REQ-003  ◐  Avatar upload           → user-profile (running)
  REQ-004  ✓  Token refresh           → auth-system (merged)
  ...
  REQ-014  ·  Admin audit log         → (not assigned)
  REQ-015  ·  Export function          → (not assigned)
```

### Coverage Tracking Lifecycle

```
Plan generation:
  change.requirements = ["REQ-001", "REQ-004"]
  → populate_coverage() → coverage state init

During change execution:
  status = "running" → REQ-001 status = "running"

Change merge:
  update_coverage_status("auth-system", "merged")
  → REQ-001 status = "merged"
  → REQ-004 status = "merged"

Change failed:
  → REQ-XXX status = "failed"
  → check_coverage_gaps(): warning

Replan:
  Gaps (unassigned, failed) are included in the planner prompt
```

### Coverage Gap Detection

`check_coverage_gaps()` watches for:

- **Unassigned**: No change is assigned to a REQ-XXX
- **Failed**: The change that owns the requirement has failed
- **Orphaned**: The requirement is in the digest but missing from the plan

These gaps are taken into account during replan, generating new changes to cover them.

### Cross-Cutting Requirements

Some requirements may affect multiple changes. The `also_affects_reqs` field signals this:

```json
{
  "name": "api-endpoints",
  "requirements": ["REQ-005"],
  "also_affects_reqs": ["REQ-012"]
}
```

REQ-012 (e.g., "Logging") is not the primary task of `api-endpoints`, but it's affected. The review gate takes this into account during evaluation.

## Final Coverage Check

At the end of a run (done, time-limit), `final_coverage_check()` generates a summary report:

```
Final Coverage: 14/15 (93.3%)
  Uncovered: REQ-015 (Export function)
```

This summary is included in:

- The summary email
- The HTML report
- The orchestration-summary.md file

\begin{keypoint}
Coverage tracking is not a guarantee of correct implementation — it only indicates that a change "attempted" to cover the requirement. Actual quality is ensured by the verify and review gates. The main value of the coverage system: replan doesn't forget anything from the specification.
\end{keypoint}

## Summary Reports

### HTML Report

`generate_report()` (in `reporter.sh`) generates a detailed HTML report:

- Per-change summary (status, token usage, time)
- Coverage matrix
- Gate statistics (pass/fail ratios)
- Timeline visualization

### Summary Email

If email notification is configured, a summary email is sent at the end of a run:

- Runtime (active and wall)
- Change results
- Coverage summary
- Next steps (if replan is active)

### orchestration-summary.md

A human-readable markdown summary generated at the end of a run.
