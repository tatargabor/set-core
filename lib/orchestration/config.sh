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
            if [[ -f "set/orchestration/config.yaml" ]]; then
                echo "set/orchestration/config.yaml"
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
