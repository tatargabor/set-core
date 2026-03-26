## no-op-detection

### Requirements

- REQ-1: In execute_merge_queue, detect changes with 0 new commits beyond the integration merge base
- REQ-2: No-op changes skip integration gates (build/test/e2e) — no point testing unchanged code
- REQ-3: No-op changes are marked "merged" and archived normally (they satisfied the orchestrator's request even if nothing was needed)
- REQ-4: Log a warning when a no-op is detected so it's visible in the run report

### Scenarios

**no-op-skip-gates**
GIVEN a change "home-and-about-pages" in merge queue
AND the worktree branch has 0 commits beyond the integration merge base
WHEN execute_merge_queue processes this change
THEN integration gates are skipped
AND the change is marked "merged" with gate_total_ms=0
AND a warning is logged: "No-op change home-and-about-pages — 0 new commits, skipping gates"

**real-change-normal-flow**
GIVEN a change "contact-page" in merge queue
AND the worktree branch has 3 commits beyond the integration merge base
WHEN execute_merge_queue processes this change
THEN integration gates run normally (build + test + e2e)
