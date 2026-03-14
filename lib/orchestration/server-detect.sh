#!/usr/bin/env bash
# lib/orchestration/server-detect.sh — Auto-detect dev server and package manager
# Sourced by bin/wt-orchestrate after merger.sh
# Provides: detect_dev_server(), detect_package_manager(), install_dependencies()

# Detect dev server command for a project directory.
# Detection order:
#   1. milestones.dev_server directive (explicit override)
#   2. smoke_dev_server_command directive (reuse existing smoke config)
#   3. package.json scripts.dev → npm/bun/pnpm/yarn run dev
#   4. docker-compose.yml or compose.yml → docker compose up
#   5. Makefile dev/serve target → make dev or make serve
#   6. manage.py → python manage.py runserver
# Args: project_dir [milestone_dev_server] [smoke_dev_server_command]
# Returns: command string on stdout, or empty if none detected
detect_dev_server() {
    local project_dir="${1:-.}"
    local milestone_dev_server="${2:-}"
    local smoke_dev_server_cmd="${3:-}"

    # 1. Explicit milestone override
    if [[ -n "$milestone_dev_server" ]]; then
        echo "$milestone_dev_server"
        return 0
    fi

    # 2. Reuse smoke_dev_server_command if set
    if [[ -n "$smoke_dev_server_cmd" ]]; then
        echo "$smoke_dev_server_cmd"
        return 0
    fi

    # 3. package.json scripts.dev
    if [[ -f "$project_dir/package.json" ]]; then
        local has_dev
        has_dev=$(jq -r '.scripts.dev // empty' "$project_dir/package.json" 2>/dev/null)
        if [[ -n "$has_dev" ]]; then
            local pm
            pm=$(detect_package_manager "$project_dir")
            echo "$pm run dev"
            return 0
        fi
    fi

    # 4. docker-compose.yml or compose.yml
    if [[ -f "$project_dir/docker-compose.yml" || -f "$project_dir/compose.yml" ]]; then
        echo "docker compose up"
        return 0
    fi

    # 5. Makefile with dev or serve target
    if [[ -f "$project_dir/Makefile" ]]; then
        if grep -qE '^dev:' "$project_dir/Makefile" 2>/dev/null; then
            echo "make dev"
            return 0
        fi
        if grep -qE '^serve:' "$project_dir/Makefile" 2>/dev/null; then
            echo "make serve"
            return 0
        fi
    fi

    # 6. manage.py (Django)
    if [[ -f "$project_dir/manage.py" ]]; then
        echo "python manage.py runserver"
        return 0
    fi

    # No server detected
    return 1
}

# Detect package manager from lock files.
# Returns: bun, pnpm, yarn, or npm (default)
detect_package_manager() {
    local project_dir="${1:-.}"

    if [[ -f "$project_dir/bun.lockb" || -f "$project_dir/bun.lock" ]]; then
        echo "bun"
    elif [[ -f "$project_dir/pnpm-lock.yaml" ]]; then
        echo "pnpm"
    elif [[ -f "$project_dir/yarn.lock" ]]; then
        echo "yarn"
    else
        echo "npm"
    fi
}

# Install dependencies using detected package manager.
# Args: project_dir
# Returns: 0 on success, 1 on failure (non-blocking)
install_dependencies() {
    local project_dir="${1:-.}"
    local pm
    pm=$(detect_package_manager "$project_dir")

    # Skip if no package.json
    if [[ ! -f "$project_dir/package.json" ]]; then
        return 0
    fi

    log_info "Installing dependencies in $project_dir with $pm"
    local install_cmd="$pm install"
    [[ "$pm" == "bun" ]] && install_cmd="bun install"

    if timeout 120 bash -c "cd '$project_dir' && $install_cmd" >/dev/null 2>&1; then
        log_info "Dependencies installed successfully ($pm)"
        return 0
    else
        log_warn "Dependency install failed ($pm) — non-blocking"
        return 1
    fi
}
