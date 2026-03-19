#!/usr/bin/env bash
# lib/orchestration/builder.sh — Thin wrapper: logic lives in lib/set_orch/builder.py
#
# Sourced by bin/set-orchestrate for backward compatibility.
# Python implementation: lib/set_orch/builder.py, cli.py:cmd_build()

# Run build on main project. Delegates to Python.
check_base_build() {
    local project_path="$1"
    local result
    result=$(set-orch-core build check --project "$project_path" 2>/dev/null) || return 1
    local status
    status=$(echo "$result" | jq -r '.status // "fail"')
    [[ "$status" == "pass" || "$status" == "skip" ]]
}

# LLM-assisted build fix with model escalation. Delegates to Python.
fix_base_build_with_llm() {
    local project_path="$1"
    local result
    result=$(set-orch-core build fix --project "$project_path" 2>/dev/null) || return 1
    local status
    status=$(echo "$result" | jq -r '.status // "fail"')
    [[ "$status" == "pass" ]]
}
