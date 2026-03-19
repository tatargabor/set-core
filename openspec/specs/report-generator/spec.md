## Purpose

Python module for orchestration HTML report generation, replacing reporter.sh's 9 bash functions with typed data extraction and Jinja2 template rendering.

## Requirements

### Data Model

- `ReportData` dataclass as top-level container with sections: digest, plan, milestones, execution, audit, coverage, timestamp
- `DigestData`: spec_dir, source_hash, file_count, timestamp, req_count, domains (list of name+count), ambiguities (list with id, type, description, resolution, note, resolved_by)
- `PlanData`: total_changes, changes (list with name, req_count, deps, status)
- `MilestoneData`: current_phase, phase_count, phases (list with num, status, total, merged, tokens, server_port, server_pid, completed_at)
- `ExecutionData`: orch_status, e2e_mode, changes (list with all per-change fields: name, status, duration_s, tokens, test_result, e2e_result, smoke_result, test_stats, screenshot counts/dirs, phase, skip_reason), totals (tokens, duration_s, tests), phase_e2e_results (list), smoke_screenshots, e2e_screenshots
- `AuditData`: entries (list with cycle, result, model, duration_ms, gap_count, summary, gaps list)
- `CoverageData`: grand_total, grand_covered, grand_inprogress, grand_prev_merged, domains (list with name, total, merged, inprogress, prev_merged, requirements list with req_id, title, change, status, phase)

### Data Extraction

- `extract_report_data(state_path, plan_path, digest_dir, output_path)` → `ReportData`
- Reads JSON files using `json.load()` (no jq subprocess)
- Handles missing files gracefully — each section returns empty/default data if source file absent
- Token formatting helper: raw int → "1.2M" / "45K" / "123"
- Duration formatting helper: seconds → "5m23s"
- Status class mapping: status string → CSS class name (same classes as current bash)

### Jinja2 Template

- Single `report.html.j2` in `lib/set_orch/templates/`
- Reproduces identical HTML structure: head (meta refresh 15s, dark theme CSS), 6 sections, footer
- Macros: `status_badge(status)`, `token_display(tokens)`, `duration_display(seconds)`, `gate_icon(result)`, `coverage_bar(merged_pct, inprog_pct)`
- Coverage section includes the JS toggle script for "Include previous phases" checkbox
- Screenshot galleries: smoke (collapsible, attempt subdirs reversed) and e2e (collapsible)
- Phase-end E2E results table with inline screenshot gallery for latest cycle

### Rendering

- `generate_report(state_path, plan_path, digest_dir, output_path)` — main entry point
- Loads Jinja2 environment from templates directory
- Extracts data → renders template → atomic write (tempfile + os.rename)
- Returns the output path on success

### Migration Mapping

Bash function → Python function:
- `generate_report()` → `generate_report()`
- `render_html_wrapper_open()` → Jinja2 template head block
- `render_html_wrapper_close()` → Jinja2 template footer block
- `render_digest_section()` → `_extract_digest()` + template digest block
- `render_plan_section()` → `_extract_plan()` + template plan block
- `render_milestone_section()` → `_extract_milestones()` + template milestone block
- `render_execution_section()` → `_extract_execution()` + template execution block
- `render_audit_section()` → `_extract_audit()` + template audit block
- `render_coverage_section()` → `_extract_coverage()` + template coverage block
