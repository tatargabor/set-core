#!/usr/bin/env bash
# lib/orchestration/reporter.sh — HTML report generator for orchestration dashboard
# Sourced by bin/set-orchestrate after digest.sh.
# Provides: generate_report()
#
# Migrated to: lib/wt_orch/reporter.py + lib/wt_orch/templates/report.html.j2
# All render_* functions replaced by Python Jinja2 template rendering.

REPORT_OUTPUT_PATH="wt/orchestration/report.html"

# ─── Entry Point ────────────────────────────────────────────────────

generate_report() {
    # Migrated to: reporter.py generate_report()
    set-orch-core report generate \
        --state "$STATE_FILENAME" \
        --plan "${PLAN_FILENAME:-orchestration-plan.json}" \
        --digest-dir "$DIGEST_DIR" \
        --output "$REPORT_OUTPUT_PATH" \
        > /dev/null
}

# ─── Migrated Functions (kept as comments for reference) ─────────────
#
# render_html_wrapper_open()   — Migrated to: reporter.py + report.html.j2 head block
# render_html_wrapper_close()  — Migrated to: reporter.py + report.html.j2 footer block
# render_digest_section()      — Migrated to: reporter.py _extract_digest() + template digest block
# render_plan_section()        — Migrated to: reporter.py _extract_plan() + template plan block
# render_milestone_section()   — Migrated to: reporter.py _extract_milestones() + template milestone block
# render_execution_section()   — Migrated to: reporter.py _extract_execution() + template execution block
# render_audit_section()       — Migrated to: reporter.py _extract_audit() + template audit block
# render_coverage_section()    — Migrated to: reporter.py _extract_coverage() + template coverage block
