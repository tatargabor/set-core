## Why

The orchestration HTML report generator (`lib/orchestration/reporter.sh`, 748 LOC) is the most complex bash module in terms of output generation — it builds an entire HTML dashboard by concatenating strings via echo/cat heredocs with embedded jq queries. This produces fragile, unreadable code where HTML structure, CSS styling, data extraction, and presentation logic are interleaved. Migrating to Python with Jinja2 templates separates concerns cleanly: data extraction becomes typed Python, presentation becomes a maintainable HTML template.

## What Changes

- **New**: `lib/set_orch/reporter.py` — Python module extracting report data from state/digest/plan JSON files into typed dataclasses, then rendering via Jinja2
- **New**: `lib/set_orch/templates/report.html.j2` — Jinja2 template replacing 400+ lines of inline HTML/CSS string concatenation
- **New**: CLI subcommand `set-orch-core report generate` bridging bash→Python
- **Modified**: `lib/orchestration/reporter.sh` — replace `generate_report()` with thin CLI wrapper calling Python, keep as launcher
- **Modified**: `lib/set_orch/cli.py` — add report subcommand group

## Capabilities

### New Capabilities
- `report-generator`: Python report data extraction and Jinja2-based HTML rendering
- `report-cli`: CLI bridge subcommands for report generation

### Modified Capabilities
- `typed-state`: Extended with report data extraction helpers (reading state for report context)

## Impact

- `lib/orchestration/reporter.sh` — 9 functions replaced with 1 CLI wrapper
- `lib/set_orch/cli.py` — new `report` subcommand group
- New dependency: Jinja2 (already commonly available, no heavy deps)
- `pyproject.toml` or setup — add jinja2 dependency
- Report output format (`wt/orchestration/report.html`) unchanged — consumers see identical HTML
