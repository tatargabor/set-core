#!/usr/bin/env bash
# lib/orchestration/config.sh — wt/ directory lookup and config file resolution
# Sourced by bin/set-orchestrate before state.sh


# Find a set-core config file using the fallback chain:
#   wt/ location → legacy location → empty
# Usage: wt_find_config <name>
# Names: orchestration, project-knowledge
wt_find_config() {
    local name="$1"
    case "$name" in
        orchestration)
            if [[ -f "wt/orchestration/config.yaml" ]]; then
                echo "wt/orchestration/config.yaml"
            elif [[ -f ".claude/orchestration.yaml" ]]; then
                echo ".claude/orchestration.yaml"
            fi
            ;;
        project-knowledge)
            if [[ -f "wt/knowledge/project-knowledge.yaml" ]]; then
                echo "wt/knowledge/project-knowledge.yaml"
            elif [[ -f "project-knowledge.yaml" ]]; then
                echo "project-knowledge.yaml"
            elif [[ -f "project-knowledge.yml" ]]; then
                echo "project-knowledge.yml"
            fi
            ;;
    esac
}

# Find the runs directory: wt/orchestration/runs/ or docs/orchestration-runs/ or empty
wt_find_runs_dir() {
    if [[ -d "wt/orchestration/runs" ]]; then
        echo "wt/orchestration/runs"
    elif [[ -d "docs/orchestration-runs" ]]; then
        echo "docs/orchestration-runs"
    fi
}

# Find the requirements directory: wt/requirements/ or empty
wt_find_requirements_dir() {
    if [[ -d "wt/requirements" ]]; then
        echo "wt/requirements"
    fi
}
