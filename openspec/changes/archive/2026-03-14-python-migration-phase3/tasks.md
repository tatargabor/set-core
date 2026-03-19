## 1. Jinja2 Dependency

- [x] 1.1 Add `jinja2` to project dependencies (pyproject.toml or equivalent install mechanism)
- [x] 1.2 Verify `import jinja2` works in the project Python environment

## 2. Report Data Model

- [x] 2.1 Create `lib/set_orch/reporter.py` with dataclasses: `ReportData`, `DigestData`, `PlanData`, `MilestoneData`, `ExecutionData`, `AuditData`, `CoverageData` and their nested types
- [x] 2.2 Add helper functions: `_format_tokens(n)` → "1.2M"/"45K"/"123", `_format_duration(seconds)` → "5m23s", `_status_class(status)` → CSS class

## 3. Data Extraction Functions

- [x] 3.1 Implement `_extract_digest(digest_dir)` → `DigestData` — reads index.json, requirements.json, domains; handles missing files
- [x] 3.2 Implement `_extract_plan(plan_path, state_path)` → `PlanData` — reads plan JSON, enriches with status from state
- [x] 3.3 Implement `_extract_milestones(state_path)` → `MilestoneData` — reads phases from state, computes per-phase tokens/merged counts
- [x] 3.4 Implement `_extract_execution(state_path)` → `ExecutionData` — reads changes from state, computes durations, formats tokens, extracts gate results, screenshot info, phase headers, totals
- [x] 3.5 Implement `_extract_audit(state_path)` → `AuditData` — reads phase_audit_results from state
- [x] 3.6 Implement `_extract_coverage(digest_dir, state_path)` → `CoverageData` — reads requirements.json + coverage.json, cross-references with state for effective status, groups by domain
- [x] 3.7 Implement `extract_report_data(state_path, plan_path, digest_dir)` → `ReportData` — orchestrates all extraction functions

## 4. Jinja2 Template

- [x] 4.1 Create `lib/set_orch/templates/` directory and `report.html.j2` with HTML head (meta charset, viewport, refresh 15s, dark theme CSS — identical to bash version)
- [x] 4.2 Add Jinja2 macros: `status_badge(status)`, `token_display(tokens)`, `duration_display(seconds)`, `gate_icon(result)`, `coverage_bar(merged_pct, inprog_pct)`
- [x] 4.3 Add digest section template block (spec source info, requirements count, domain table, ambiguities table)
- [x] 4.4 Add plan section template block (changes table with status from state)
- [x] 4.5 Add milestone section template block (phase table with tokens, server links, completed times)
- [x] 4.6 Add execution section template block (change timeline table with phase headers, gate icons, durations, token counts, screenshot links, summary row, smoke/e2e screenshot galleries, phase-end E2E results)
- [x] 4.7 Add audit section template block (per-cycle audit results with gap tables)
- [x] 4.8 Add coverage section template block (JS toggle script, summary bar, per-domain collapsible details with requirement tables)
- [x] 4.9 Add footer template block (generated timestamp, auto-refresh note)

## 5. Report Generation Entry Point

- [x] 5.1 Implement `generate_report(state_path, plan_path, digest_dir, output_path)` — load Jinja2 env from templates dir, extract data, render template, atomic write via tempfile+rename
- [x] 5.2 Add tests for data extraction functions (mock JSON files, verify dataclass population)
- [x] 5.3 Add tests for template rendering (verify HTML contains expected sections, status classes, token formatting)

## 6. CLI Bridge

- [x] 6.1 Add `set-orch-core report generate` subcommand to `cli.py` with `--state`, `--plan`, `--digest-dir`, `--output` flags
- [x] 6.2 Replace `generate_report()` in `reporter.sh` with thin CLI wrapper calling `set-orch-core report generate`
- [x] 6.3 Add "Migrated to: reporter.py" comments to all 8 render_* functions in reporter.sh
- [x] 6.4 Verify end-to-end: bash caller → CLI → Python → HTML output matches expected structure
