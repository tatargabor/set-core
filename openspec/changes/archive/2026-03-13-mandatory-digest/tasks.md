## 1. Unify find_input() routing

- [x] 1.1 In `lib/orchestration/utils.sh` `find_input()`: change `--spec <file>` branch (line 162) from `INPUT_MODE="spec"` to `INPUT_MODE="digest"`
- [x] 1.2 Change short-name resolution branches (lines 170, 174) from `INPUT_MODE="spec"` to `INPUT_MODE="digest"`
- [x] 1.3 Update the function comment (line 151) from `"spec" or "brief"` to `"digest" or "brief"`

## 2. Remove dead spec-mode code paths in planner.sh

- [x] 2.1 In `cmd_plan()`: remove the `elif [[ "$INPUT_MODE" == "spec" ]]` branch (around line 845) that reads raw spec content — digest mode now handles this
- [x] 2.2 In `cmd_plan()`: simplify the decompose prompt condition at line 923 — change `"spec" || "digest"` to just `"digest"`
- [x] 2.3 In `cmd_plan()`: remove `INPUT_MODE=="spec"` branch at line 1168 that logs spec-mode plan info
- [x] 2.4 In `cmd_replan()`: verify no spec-mode references remain
- [x] 2.5 Grep entire `lib/orchestration/` for remaining `INPUT_MODE.*spec` references and remove or update (found + fixed one in dispatcher.sh)

## 3. Verify existing digest pipeline handles single files

- [x] 3.1 `scan_spec_directory()` handles single file input (lines 166-169) — sets files array and master_file correctly
- [x] 3.2 Verify `scan_spec_directory()` sets `master_file` correctly for single-file input — confirmed: `master_file=$(basename "$spec_path")`
- [x] 3.3 Verify `check_digest_freshness()` works with single-file hash comparison — confirmed: calls `scan_spec_directory()` which handles both
