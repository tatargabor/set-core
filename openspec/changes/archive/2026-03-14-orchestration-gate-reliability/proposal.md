## Why

The orchestration quality gate pipeline has several reliability issues discovered across v9-v11 production runs. Smoke gates have 60-71% false failure rates due to stale dev servers, the ff→apply chaining never fires (wasting ~120K tokens/run), the verify gate silently passes when its sentinel line is missing, and orchestrator stalls require manual SIGKILL intervention. These issues compound to waste ~200K+ tokens and ~30-45 minutes per run while requiring 2-4 sentinel interventions.

## What Changes

- **Fix ff→apply in-iteration chaining** — the `has_artifact_progress` condition in engine.sh:669 is always false after ff commits artifacts, so chaining never triggers. Fix the condition to detect ff→apply transition instead of checking dirty files.
- **Make verify sentinel line mandatory** — when `/opsx:verify` output lacks the `VERIFY_RESULT:` sentinel line, the gate currently passes silently. Change to treat missing sentinel as FAIL.
- **Add orchestrator self-watchdog** — detect "all idle" state in the monitor loop (no active changes, no merge queue progress) and auto-recover instead of requiring sentinel SIGKILL.
- **Add "done" status to monitor safety net** — the suspended-change safety net checks paused/waiting/budget_exceeded but not "done", allowing changes to get stuck without being merged.
- **Improve smoke gate reliability** — when health_check() fails (dev server not responding), attempt auto-start before falling back to smoke_blocked. Add configurable dev server start command.
- **Default review_model to opus** — Sonnet review fails 50% of the time on large projects, causing +360s escalation overhead. Change default from "sonnet" to "opus".
- **Add merge operation timeout** — prevent indefinite blocking when merge_change() hangs.
- **Fix verify output truncation** — the 2000-char limit on verify output can lose the sentinel line. Parse sentinel from full output before truncating for storage.

## Capabilities

### New Capabilities
- `gate-ff-apply-chaining`: Fix the broken ff→apply in-iteration chaining condition in the Ralph loop engine
- `gate-verify-sentinel-strict`: Make verify gate sentinel line mandatory — missing sentinel = FAIL
- `gate-monitor-self-watchdog`: Self-watchdog for the orchestrator monitor loop to detect and recover from all-idle stalls
- `gate-smoke-auto-restart`: Auto-start dev server when health_check fails, with configurable start command directive
- `gate-merge-timeout`: Timeout wrapper for merge operations to prevent indefinite blocking

### Modified Capabilities
- `orchestration-watchdog`: Add "done" status to the suspended-change safety net in the monitor loop
- `orchestration-smoke-blocking`: Add `smoke_dev_server_command` directive for auto-starting dev server
- `verify-gate`: Fix output truncation — parse sentinel from full output before truncating; treat missing sentinel as FAIL
- `verify-retry-context`: Ensure verify retry includes the specific gate that failed and its output
- `ff-exhausted-recovery`: Fix chaining condition so ff→apply transition works when artifacts are committed (not just dirty files)

## Impact

- **lib/loop/engine.sh**: Fix `has_artifact_progress` condition for ff→apply chaining (~5 lines)
- **lib/orchestration/verifier.sh**: Verify sentinel parsing, output truncation fix, review model default
- **lib/orchestration/monitor.sh**: Self-watchdog logic, "done" safety net addition
- **lib/orchestration/merger.sh**: Merge timeout wrapper, smoke dev server auto-start
- **lib/orchestration/utils.sh**: New `smoke_dev_server_command` directive parsing
- **bin/wt-orchestrate**: `DEFAULT_REVIEW_MODEL` change (1 line)
- **docs/howitworks/en/07-quality-gates.md**: Documentation updates for new behavior
