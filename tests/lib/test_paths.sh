#!/usr/bin/env bash
# Test-only path helpers that mirror the production `LineagePaths` resolver.
#
# Production code uses `LineagePaths(project)` which resolves paths under the
# XDG runtime location (~/.local/share/set-core/runtime/<basename>/).  Most
# orchestrator test fixtures, however, build a disposable git repo in
# `$TMPDIR` and want the legacy project-root layout (state next to plan,
# archive next to state).  These helpers return the project-root paths
# while still naming the lineage concept explicitly so the audit gate
# (and human readers) can grep for them.
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/../lib/test_paths.sh"
#   STATE_FILE="$(tp_state_file "$REPO")"
#   ARCHIVE="$(tp_state_archive "$REPO")"
#
# Helper names use a `tp_` prefix (test-paths) instead of the bare
# `state_file` / `plan_file` style so they cannot be confused with the
# bash unit-test framework's `test_*` auto-discovery convention in
# tests/unit/helpers.sh.

# shellcheck shell=bash

tp_state_file()        { echo "$1/orchestration-state.json"; }
tp_state_archive()     { echo "$1/state-archive.jsonl"; }
tp_plan_file()         { echo "$1/orchestration-plan.json"; }
tp_plan_domains_file() { echo "$1/orchestration-plan-domains.json"; }
tp_events_file()       { echo "$1/orchestration-events.jsonl"; }
tp_state_events_file() { echo "$1/orchestration-state-events.jsonl"; }
tp_coverage_history()  { echo "$1/spec-coverage-history.jsonl"; }
tp_e2e_history()       { echo "$1/e2e-manifest-history.jsonl"; }
tp_worktrees_history() { echo "$1/worktrees-history.json"; }
tp_directives_file()   { echo "$1/orchestration-directives.yaml"; }
tp_coverage_report()   { echo "$1/spec-coverage-report.json"; }
tp_review_learnings()  { echo "$1/review-learnings.jsonl"; }
tp_review_findings()   { echo "$1/review-findings.jsonl"; }
