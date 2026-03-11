## 1. State Management

- [x] 1.1 Add `cmd_skip` function in `bin/wt-orchestrate` — parse `<name>` and optional `--reason` flag, validate change exists, validate status is skippable, update status to "skipped" with `skipped_at` timestamp and optional `skip_reason`
- [x] 1.2 Register `skip` subcommand in the case dispatch block in `bin/wt-orchestrate` (around line 605)
- [x] 1.3 Modify `deps_satisfied()` in `lib/orchestration/state.sh` — accept "skipped" alongside "merged" (change `!= "merged"` to `!= "merged" && != "skipped"`)
- [x] 1.4 Verify `deps_failed()` in `lib/orchestration/state.sh` does NOT treat "skipped" as failed (no change needed, just verify)

## 2. Monitor Integration

- [x] 2.1 Update `truly_complete` jq query in `lib/orchestration/monitor.sh` (line 324) to include "skipped": `select(.status == "done" or .status == "merged" or .status == "skipped")`
- [x] 2.2 Add `skipped_count` variable alongside `failed_count` in monitor completion check
- [x] 2.3 Update `all_resolved` calculation to include skipped count
- [x] 2.4 Update completion log message to include skipped count (e.g., "3 succeeded, 1 skipped, 1 failed")

## 3. Reporter

- [x] 3.1 Add `.status-skipped { color: #ffc107; }` CSS class in `lib/orchestration/reporter.sh` (after line 53)
- [x] 3.2 Add skipped count to summary statistics display
- [x] 3.3 Display `skip_reason` as tooltip or inline text when present on a skipped change

## 4. State Summary

- [x] 4.1 Add "skipped" to `print_state_summary()` in `lib/orchestration/state.sh` if it counts statuses (alongside merged/failed counts)
