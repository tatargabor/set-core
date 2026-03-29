#!/usr/bin/env bash
# set-core common functions
# Source this file in other set-* scripts
#
# Editor functions have been extracted to lib/editor.sh.
# Scripts that need editor support must source it explicitly.

set -euo pipefail

# =============================================================================
# Backward Compatibility: WT_* → SET_* env var migration
# =============================================================================
if [[ -n "${WT_TOOLS_ROOT:-}" && -z "${SET_TOOLS_ROOT:-}" ]]; then
    echo "WARNING: WT_TOOLS_ROOT is deprecated, use SET_TOOLS_ROOT" >&2
    SET_TOOLS_ROOT="$WT_TOOLS_ROOT"
fi
if [[ -n "${WT_CONFIG_DIR:-}" && -z "${SET_CONFIG_DIR:-}" ]]; then
    echo "WARNING: WT_CONFIG_DIR is deprecated, use SET_CONFIG_DIR" >&2
    SET_CONFIG_DIR="$WT_CONFIG_DIR"
fi

# SET_TOOLS_ROOT — canonical path to set-core repo root.
# Resolves symlinks so this works from install.sh symlinked bins too.
# Scripts may override before sourcing set-common.sh if needed.
if [[ -z "${SET_TOOLS_ROOT:-}" ]]; then
    SET_TOOLS_ROOT="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")" && cd .. && pwd)"
fi

# Find a Python interpreter that can import set_orch (lib/ on PYTHONPATH)
# and set_project_base (pip-installed). Caches result in _SET_PYTHON.
# Usage: py=$(set_find_python) && "$py" -c "..."
_SET_PYTHON=""
set_find_python() {
    if [[ -n "$_SET_PYTHON" ]]; then
        echo "$_SET_PYTHON"
        return 0
    fi
    local candidates=(
        "/opt/homebrew/bin/python3.13"
        "/opt/homebrew/bin/python3.12"
        "/opt/homebrew/bin/python3.11"
        "/opt/homebrew/bin/python3"
        "/usr/local/bin/python3"
        "$HOME/miniconda3/bin/python"
        "$HOME/.local/share/uv/python/cpython-*/bin/python3"
        "$(command -v python3 2>/dev/null)"
        "$(command -v python 2>/dev/null)"
    )
    for py in "${candidates[@]}"; do
        [[ -z "$py" ]] && continue
        for resolved in $py; do
            [[ -x "$resolved" ]] || continue
            if PYTHONPATH="$SET_TOOLS_ROOT/lib${PYTHONPATH:+:$PYTHONPATH}" \
               "$resolved" -c "import set_orch.profile_loader" 2>/dev/null; then
                _SET_PYTHON="$resolved"
                echo "$resolved"
                return 0
            fi
        done
    done
    echo "python3"
}

# Run a Python command with set_orch on the path.
# Computes PYTHONPATH dynamically so it picks up any SET_TOOLS_ROOT overrides.
# Usage: set_python python3 -c "from set_orch.profile_loader import ..."
#        set_python "$py" -c "..."
set_python() {
    PYTHONPATH="$SET_TOOLS_ROOT/lib${PYTHONPATH:+:$PYTHONPATH}" "$@"
}

# Platform detection
detect_platform() {
    case "$(uname -s)" in
        Linux*)  echo "linux" ;;
        Darwin*) echo "macos" ;;
        MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
        *)       echo "unknown" ;;
    esac
}

PLATFORM=$(detect_platform)

# Config paths
get_config_dir() {
    # Support SET_CONFIG_DIR override for testing
    if [[ -n "${SET_CONFIG_DIR:-}" ]]; then
        echo "$SET_CONFIG_DIR"
        return
    fi

    case "$PLATFORM" in
        linux|macos)
            echo "${XDG_CONFIG_HOME:-$HOME/.config}/set-core"
            ;;
        windows)
            echo "${APPDATA:-$HOME/AppData/Roaming}/set-core"
            ;;
        *)
            echo "$HOME/.config/set-core"
            ;;
    esac
}

CONFIG_DIR=$(get_config_dir)
CONFIG_FILE="$CONFIG_DIR/projects.json"

# Ensure config directory and file exist
ensure_config() {
    if [[ ! -d "$CONFIG_DIR" ]]; then
        mkdir -p "$CONFIG_DIR"
    fi
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo '{"default":null,"projects":{}}' > "$CONFIG_FILE"
    fi
}

# Ensure a project path is registered in projects.json.
# Usage: ensure_project_registered "project-name" "/path/to/project"
ensure_project_registered() {
    local name="$1"
    local path="$2"
    [[ -z "$name" || -z "$path" ]] && return 1
    local pfile="$CONFIG_DIR/projects.json"
    if [[ ! -f "$pfile" ]]; then
        mkdir -p "$CONFIG_DIR"
        echo '{"default":null,"projects":{}}' > "$pfile"
    fi
    # Check if already registered (by path)
    local existing
    existing=$(jq -r --arg p "$path" '.projects | to_entries[] | select(.value.path == $p) | .key' "$pfile" 2>/dev/null | head -1)
    if [[ -n "$existing" ]]; then
        return 0  # already registered
    fi
    # Add it
    local tmp
    tmp=$(mktemp)
    if jq --arg n "$name" --arg p "$path" \
        '.projects[$n] = {path: $p, addedAt: (now | todate)}' \
        "$pfile" > "$tmp" 2>/dev/null; then
        mv "$tmp" "$pfile"
    else
        rm -f "$tmp"
    fi
}

# Read JSON value using jq or fallback
json_get() {
    local file="$1"
    local path="$2"
    if command -v jq &>/dev/null; then
        jq -r "$path // empty" "$file" 2>/dev/null || echo ""
    else
        # Basic fallback for simple cases - not recommended
        echo "Error: jq is required but not installed" >&2
        exit 1
    fi
}

# Update JSON using jq
json_set() {
    local file="$1"
    local path="$2"
    local value="$3"
    local tmp
    tmp=$(mktemp)
    jq "$path = $value" "$file" > "$tmp" && mv "$tmp" "$file"
}

# Cross-platform process/file helpers
# Get the current working directory of a process by PID
get_proc_cwd() {
    local pid="$1"
    case "$PLATFORM" in
        macos)
            lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | grep '^n' | cut -c2-
            ;;
        *)
            readlink "/proc/$pid/cwd" 2>/dev/null
            ;;
    esac
}

# Get modification time of a file as epoch seconds
get_file_mtime() {
    local file="$1"
    case "$PLATFORM" in
        macos)
            stat -f "%m" "$file" 2>/dev/null
            ;;
        *)
            stat -c %Y "$file" 2>/dev/null
            ;;
    esac
}

# Get git root directory (main repo, not worktree)
get_git_root() {
    # Get the main worktree (first in the list), not the current worktree
    git worktree list --porcelain 2>/dev/null | grep '^worktree ' | head -1 | cut -d' ' -f2-
}

# Get current directory's git root (may be a worktree)
get_current_git_root() {
    git rev-parse --show-toplevel 2>/dev/null
}

# Check if directory is a git repo
is_git_repo() {
    local dir="${1:-.}"
    git -C "$dir" rev-parse --git-dir &>/dev/null
}

# Get repo name from path
get_repo_name() {
    local path="$1"
    basename "$(cd "$path" && get_git_root)"
}

# Get project by name
get_project_path() {
    local name="$1"
    ensure_config
    json_get "$CONFIG_FILE" ".projects.\"$name\".path"
}

# Get default project name
get_default_project() {
    ensure_config
    json_get "$CONFIG_FILE" ".default"
}

# Resolve project context
# Returns project name based on: 1) -p flag, 2) current dir, 3) default
resolve_project() {
    local explicit_project="${1:-}"

    # 1. Explicit -p flag
    if [[ -n "$explicit_project" ]]; then
        if [[ -z "$(get_project_path "$explicit_project")" ]]; then
            echo "Error: Project '$explicit_project' not found" >&2
            return 1
        fi
        echo "$explicit_project"
        return 0
    fi

    # 2. Current directory is a registered project (or its worktree)
    if is_git_repo; then
        local git_root
        git_root=$(get_git_root)  # Gets main repo, even from worktree
        ensure_config
        local project_name
        project_name=$(jq -r --arg path "$git_root" '.projects | to_entries[] | select(.value.path == $path) | .key' "$CONFIG_FILE" 2>/dev/null | head -1)
        if [[ -n "$project_name" ]]; then
            echo "$project_name"
            return 0
        fi

        # 2b. Auto-register current git repo if not registered
        local repo_name
        repo_name=$(basename "$git_root")
        info "Auto-registering project '$repo_name' from $git_root"

        # Add to config
        local tmp_file
        tmp_file=$(mktemp)
        if jq --arg name "$repo_name" --arg path "$git_root" \
            '.projects[$name] = {"path": $path, "addedAt": (now | strftime("%Y-%m-%dT%H:%M:%SZ"))}' \
            "$CONFIG_FILE" > "$tmp_file" 2>/dev/null; then
            mv "$tmp_file" "$CONFIG_FILE"
        else
            rm -f "$tmp_file"
            error "Failed to register project"
            return 1
        fi

        # Verify registration worked
        local verify_path
        verify_path=$(get_project_path "$repo_name")
        if [[ -z "$verify_path" ]]; then
            error "Project registration failed - path not found after save"
            return 1
        fi

        echo "$repo_name"
        return 0
    fi

    # 3. Default project
    local default_project
    default_project=$(get_default_project)
    if [[ -n "$default_project" && "$default_project" != "null" ]]; then
        echo "$default_project"
        return 0
    fi

    echo "Error: No project context. Use -p <project> or run 'set-project init' in a git repo" >&2
    return 1
}

# Get worktree path for a change-id (new worktree)
get_worktree_path() {
    local project_path="$1"
    local change_id="$2"
    local repo_name
    repo_name=$(basename "$project_path")
    local parent_dir
    parent_dir=$(dirname "$project_path")
    echo "$parent_dir/${repo_name}-wt-${change_id}"
}

# Get the main branch name for a project
# Returns the currently checked-out branch of the main repo
# Falls back to short commit hash if in detached HEAD state
get_main_branch() {
    local project_path="$1"
    local branch
    branch=$(git -C "$project_path" symbolic-ref --short HEAD 2>/dev/null)
    if [[ -n "$branch" ]]; then
        echo "$branch"
    else
        # Detached HEAD - return short hash
        git -C "$project_path" rev-parse --short HEAD 2>/dev/null
    fi
}

# Find existing worktree by name (matches any pattern containing the change-id)
find_existing_worktree() {
    local project_path="$1"
    local change_id="$2"
    local repo_name
    repo_name=$(basename "$project_path")

    # Get all worktrees
    local worktrees
    worktrees=$(git -C "$project_path" worktree list --porcelain 2>/dev/null)

    while IFS= read -r line; do
        if [[ "$line" =~ ^worktree\ (.+)$ ]]; then
            local wt_path="${BASH_REMATCH[1]}"
            local wt_name
            wt_name=$(basename "$wt_path")

            # Skip main repo
            [[ "$wt_path" == "$project_path" ]] && continue

            # Match: exact name, or repo-name-change-id, or repo-wt-change-id
            if [[ "$wt_name" == "$change_id" ]] || \
               [[ "$wt_name" == "${repo_name}-${change_id}" ]] || \
               [[ "$wt_name" == "${repo_name}-wt-${change_id}" ]]; then
                echo "$wt_path"
                return 0
            fi
        fi
    done <<< "$worktrees"

    echo ""
}

# Find a worktree across ALL registered projects.
# Tries current project first (fast path), then scans all projects.
# Usage: find_worktree_across_projects <change_id>
# Outputs: worktree path (or empty string if not found)
find_worktree_across_projects() {
    local change_id="$1"

    # Fast path: try current project first
    if is_git_repo; then
        local git_root
        git_root=$(get_git_root)
        local result
        result=$(find_existing_worktree "$git_root" "$change_id")
        if [[ -n "$result" ]]; then
            echo "$result"
            return 0
        fi
    fi

    # Fallback: scan all registered projects
    ensure_config
    local projects
    projects=$(jq -r '.projects | keys[]' "$CONFIG_FILE" 2>/dev/null)

    while IFS= read -r project_name; do
        [[ -z "$project_name" ]] && continue
        local project_path
        project_path=$(get_project_path "$project_name")
        [[ -z "$project_path" ]] && continue

        local result
        result=$(find_existing_worktree "$project_path" "$change_id")
        if [[ -n "$result" ]]; then
            echo "$result"
            return 0
        fi
    done <<< "$projects"

    echo ""
}

# =============================================================================
# Editor Support — extracted to lib/editor.sh
# =============================================================================
# Scripts that need editor functions must source lib/editor.sh explicitly.
# Resolve lib dir: source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/editor.sh"

# Resolve lib directory for sourcing by other scripts
_SET_TOOLS_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)"

# Auto-source editor.sh for backward compatibility
# Scripts that source set-common.sh expect editor functions to be available.
# This will be removed once all scripts explicitly source lib/editor.sh.
if [[ -f "$_SET_TOOLS_LIB/editor.sh" ]]; then
    source "$_SET_TOOLS_LIB/editor.sh"
fi

# =============================================================================
# Python Resolution
# =============================================================================

# Well-known python3 locations to probe (after PATH)
# Homebrew python first (macOS — versioned binaries), then common managed installations
_PYTHON_PROBE_PATHS=(
    "/opt/homebrew/bin/python3.13"
    "/opt/homebrew/bin/python3.12"
    "/opt/homebrew/bin/python3.11"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3.13"
    "/usr/local/bin/python3.12"
    "/usr/local/bin/python3.11"
    "/usr/local/bin/python3"
    "$HOME/miniconda3/bin/python3"
    "$HOME/anaconda3/bin/python3"
    "$HOME/.pyenv/shims/python3"
    "/usr/bin/python3"
)

# Check if a python binary meets minimum version (3.10+)
# Usage: _python_version_ok /usr/bin/python3
_python_version_ok() {
    local py="$1"
    "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null
}

# Find a working python3 binary (>= 3.10).
# Checks well-known locations first (prefer managed installs), then PATH.
# Returns: absolute path to python3 (stdout), exit 1 if not found
find_python() {
    # Check well-known locations first (prefer brew/managed over system)
    for p in "${_PYTHON_PROBE_PATHS[@]}"; do
        if [[ -x "$p" ]] && _python_version_ok "$p"; then
            echo "$p"
            return 0
        fi
    done
    # Fallback to PATH
    if command -v python3 &>/dev/null && _python_version_ok "$(command -v python3)"; then
        command -v python3
        return 0
    fi
    return 1
}

# Write the resolved shodh-memory Python path to config
save_shodh_python() {
    local python_path="$1"
    mkdir -p "$CONFIG_DIR"
    echo "$python_path" > "$CONFIG_DIR/shodh-python"
}

# Find a python3 that can import shodh_memory.
# Resolution order:
#   1. Saved config ($CONFIG_DIR/shodh-python) — validated
#   2. python3 in PATH
#   3. Well-known locations
# On success: saves path to config (if not already saved) and prints it.
# Returns: absolute path (stdout), exit 1 if not found
find_shodh_python() {
    local saved_python=""

    # 1. Check saved config
    if [[ -f "$CONFIG_DIR/shodh-python" ]]; then
        saved_python=$(cat "$CONFIG_DIR/shodh-python" 2>/dev/null)
        if [[ -n "$saved_python" && -x "$saved_python" ]] && \
           "$saved_python" -c "import sys; sys._shodh_star_shown = True; from shodh_memory import Memory" 2>/dev/null; then
            echo "$saved_python"
            return 0
        fi
        # Stale config — fall through to probing
    fi

    # 2. Try python3 in PATH
    local path_python=""
    if command -v python3 &>/dev/null; then
        path_python=$(command -v python3)
        if "$path_python" -c "import sys; sys._shodh_star_shown = True; from shodh_memory import Memory" 2>/dev/null; then
            save_shodh_python "$path_python"
            echo "$path_python"
            return 0
        fi
    fi

    # 3. Probe well-known locations
    for p in "${_PYTHON_PROBE_PATHS[@]}"; do
        if [[ -x "$p" ]] && "$p" -c "import sys; sys._shodh_star_shown = True; from shodh_memory import Memory" 2>/dev/null; then
            save_shodh_python "$p"
            echo "$p"
            return 0
        fi
    done

    return 1
}

# Color output helpers
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    MAGENTA=''
    NC=''
fi

info() { echo -e "${BLUE}$*${NC}"; }
success() { echo -e "${GREEN}$*${NC}"; }
warn() { echo -e "${YELLOW}$*${NC}" >&2; }
error() { echo -e "${RED}Error: $*${NC}" >&2; }

# =============================================================================
# Model ID Resolution
# =============================================================================

# Get configured model prefix from config.json (e.g. "cc/" for router setups, "" for direct API)
# Falls back to "" (no prefix) if not configured.
get_model_prefix() {
    local config_file
    config_file="$(get_config_dir)/config.json"
    if [[ -f "$config_file" ]]; then
        local prefix
        prefix=$(json_get "$config_file" '.claude.model_prefix')
        echo "${prefix:-}"
    else
        echo ""
    fi
}

# Set model prefix in config
set_model_prefix() {
    local prefix="$1"
    ensure_editor_config
    local config_file
    config_file=$(get_editor_config_file)
    local tmp
    tmp=$(mktemp)
    jq --arg prefix "$prefix" '.claude.model_prefix = $prefix' "$config_file" > "$tmp" && mv "$tmp" "$config_file"
}

# Resolve short model name to full model ID using configured prefix.
# Usage: resolve_model_id haiku|sonnet|opus|<full-id>
# Examples with prefix "cc/":    haiku → cc/claude-haiku-4-5-20251001
# Examples with prefix "":       haiku → claude-haiku-4-5-20251001
resolve_model_id() {
    local name="$1"
    local prefix
    prefix=$(get_model_prefix)

    case "$name" in
        haiku)    echo "${prefix}claude-haiku-4-5-20251001" ;;
        sonnet)   echo "${prefix}claude-sonnet-4-6" ;;
        opus)     echo "${prefix}claude-opus-4-6" ;;
        opus-1m)  echo "${prefix}claude-opus-4-6[1m]" ;;
        sonnet-1m) echo "${prefix}claude-sonnet-4-6[1m]" ;;
        *)        echo "$name" ;;  # pass through full IDs
    esac
}

# =============================================================================
# Claude CLI Helper
# =============================================================================

# Run claude CLI safely from non-interactive context (e.g. inside Claude Code session)
# Uses script(1) to provide a PTY, strips terminal escape codes, unsets CLAUDECODE.
# Reads prompt from stdin, passes extra flags as arguments.
# Usage: echo "$prompt" | run_claude [extra claude flags...]
#   e.g.: echo "$prompt" | run_claude --output-format json
#         echo "$prompt" | run_claude --model haiku
# Set RUN_CLAUDE_TIMEOUT (seconds) to override the default 180s timeout.
run_claude() {
    local tmpprompt tmpscript
    tmpprompt=$(mktemp)
    tmpscript=$(mktemp --suffix=.sh)
    # Ensure cleanup on any exit path (signal, set -e, normal return)
    trap 'rm -f "$tmpprompt" "$tmpscript"' RETURN

    # Read prompt from stdin
    cat > "$tmpprompt"

    # Safely quote extra args for embedding in wrapper script
    local quoted_args=""
    if [[ $# -gt 0 ]]; then
        printf -v quoted_args '%q ' "$@"
    fi

    # Design MCP passthrough: if DESIGN_MCP_CONFIG is set, add --mcp-config
    local mcp_arg=""
    if [[ -n "${DESIGN_MCP_CONFIG:-}" && -f "${DESIGN_MCP_CONFIG:-}" ]]; then
        mcp_arg="--mcp-config $(printf '%q' "$DESIGN_MCP_CONFIG")"
    fi

    # No-MCP mode: cd to /tmp so Claude won't read .claude/settings.json MCP registrations.
    # Use RUN_CLAUDE_NO_MCP=1 when Claude must produce structured output (JSON) without
    # wasting turns on MCP tool calls (e.g. Figma) registered in project settings.
    local cd_prefix=""
    if [[ -n "${RUN_CLAUDE_NO_MCP:-}" ]]; then
        cd_prefix="cd /tmp && "
        mcp_arg=""  # Also clear explicit MCP config
    fi

    # Build wrapper script (avoids quoting hell with script -c)
    cat > "$tmpscript" <<WRAPPER
#!/bin/bash
${cd_prefix}exec env -u CLAUDECODE claude -p "\$(cat '$tmpprompt')" --dangerously-skip-permissions $mcp_arg $quoted_args
WRAPPER
    chmod +x "$tmpscript"

    local timeout_secs="${RUN_CLAUDE_TIMEOUT:-180}"
    local output rc=0
    output=$(timeout --foreground "$timeout_secs" script -f -q /dev/null -c "$tmpscript" 2>/dev/null) || rc=$?
    [[ $rc -ne 0 ]] && return $rc
    # Strip terminal escape codes (CSI sequences, OSC sequences, carriage returns)
    printf '%s' "$output" | sed 's/\x1b\[[^a-zA-Z]*[a-zA-Z]//g; s/\x1b\][^\x07]*\x07//g; s/\r//g'
}
