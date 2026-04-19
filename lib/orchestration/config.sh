#!/usr/bin/env bash
# lib/orchestration/config.sh — set/ directory lookup and config file resolution
# Sourced by bin/set-orchestrate before state.sh


# Find a set-core config file using the fallback chain:
#   set/ location → legacy location → empty
# Usage: set_find_config <name>
# Names: orchestration, project-knowledge
set_find_config() {
    local name="$1"
    case "$name" in
        orchestration)
            local _cfg
            if command -v lineage_config_yaml >/dev/null 2>&1; then
                _cfg="$(lineage_config_yaml "$(pwd)")"
            fi
            # Prefer the resolver's cwd-relative view, then absolute, then legacy.
            local _cfg_rel=""
            if [[ -n "$_cfg" ]]; then
                _cfg_rel="${_cfg#$(pwd)/}"
            fi
            if [[ -n "$_cfg_rel" && -f "$_cfg_rel" ]]; then
                echo "$_cfg_rel"
            elif [[ -n "$_cfg" && -f "$_cfg" ]]; then
                echo "$_cfg"
            elif [[ -f ".claude/orchestration.yaml" ]]; then
                echo ".claude/orchestration.yaml"
            fi
            ;;
        project-knowledge)
            if [[ -f "set/knowledge/project-knowledge.yaml" ]]; then
                echo "set/knowledge/project-knowledge.yaml"
            elif [[ -f "project-knowledge.yaml" ]]; then
                echo "project-knowledge.yaml"
            elif [[ -f "project-knowledge.yml" ]]; then
                echo "project-knowledge.yml"
            fi
            ;;
    esac
}

# Find the runs directory: set/orchestration/runs/ or docs/orchestration-runs/ or empty
set_find_runs_dir() {
    if [[ -d "set/orchestration/runs" ]]; then
        echo "set/orchestration/runs"
    elif [[ -d "docs/orchestration-runs" ]]; then
        echo "docs/orchestration-runs"
    fi
}

# Find the requirements directory: set/requirements/ or empty
set_find_requirements_dir() {
    if [[ -d "set/requirements" ]]; then
        echo "set/requirements"
    fi
}
