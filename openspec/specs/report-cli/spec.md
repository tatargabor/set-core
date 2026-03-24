## Purpose

CLI bridge subcommands for report generation, enabling bash wrapper to call Python reporter.

## Requirements

### CLI Subcommand

- `set-orch-core report generate` subcommand
- Flags: `--state FILE` (state JSON path), `--plan FILE` (plan JSON path), `--digest-dir DIR` (digest directory), `--output FILE` (output HTML path, default: `set/orchestration/report.html`)
- Calls `reporter.generate_report()` with provided paths
- Exit code 0 on success, 1 on error
- Prints output path to stdout on success

### Bash Wrapper

- Replace `generate_report()` in `lib/orchestration/reporter.sh` with thin wrapper:
  ```
  generate_report() {
      set-orch-core report generate \
          --state "$STATE_FILENAME" \
          --plan "${PLAN_FILENAME:-orchestration-plan.json}" \
          --digest-dir "$DIGEST_DIR" \
          --output "$REPORT_OUTPUT_PATH"
  }
  ```
- All 8 render_* functions become dead code — add "Migrated to: reporter.py" comments
- Keep `REPORT_OUTPUT_PATH` variable (used by callers)

### Dependency Setup

- Add `jinja2` to project dependencies (pyproject.toml or equivalent)
- Verify jinja2 is importable at CLI startup (fail gracefully with clear error if missing)
