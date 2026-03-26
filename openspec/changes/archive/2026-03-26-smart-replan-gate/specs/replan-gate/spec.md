## replan-gate

### Requirements

- REQ-1: When all changes succeeded (0 failed, 0 stalled) AND all requirements have coverage status "merged", skip replan and go directly to "done"
- REQ-2: reconcile_coverage() must run BEFORE the replan gate decision (already exists at line 1098, but must also inform the gate)
- REQ-3: When coverage gaps exist but no failures, replan with "coverage_gap" trigger (only uncovered domains) — not full re-decompose
- REQ-4: "batch_complete" trigger must NOT cause full Phase 2+3 re-decompose — it should check coverage first and only replan uncovered domains

### Scenarios

**all-green-skip-replan**
GIVEN 3/3 changes merged, 0 failed
AND all requirements in coverage.json have status "merged"
WHEN _check_all_done triggers auto_replan
THEN replan is skipped and status is set to "done"

**coverage-gap-selective-replan**
GIVEN 3/3 changes merged, 0 failed
AND 2 requirements in coverage.json still "uncovered"
WHEN _check_all_done triggers auto_replan
THEN replan runs with "coverage_gap" trigger (only uncovered domains)

**failed-changes-replan**
GIVEN 2/3 merged, 1/3 failed
WHEN _check_all_done triggers auto_replan
THEN replan runs with "domain_failure" trigger (unchanged behavior)
