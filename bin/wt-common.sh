#!/usr/bin/env bash
# wt-tools common functions
# Source this file in other wt-* scripts

set -euo pipefail

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
    # Support WT_CONFIG_DIR override for testing
    if [[ -n "${WT_CONFIG_DIR:-}" ]]; then
        echo "$WT_CONFIG_DIR"
        return
    fi

    case "$PLATFORM" in
        linux|macos)
            echo "${XDG_CONFIG_HOME:-$HOME/.config}/wt-tools"
            ;;
        windows)
            echo "${APPDATA:-$HOME/AppData/Roaming}/wt-tools"
            ;;
        *)
            echo "$HOME/.config/wt-tools"
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

    echo "Error: No project context. Use -p <project> or run 'wt-project init' in a git repo" >&2
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

# Get the main branch name for a project (master, main, etc.)
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
# Multi-Editor Support
# =============================================================================

# Supported editors configuration
# Format: name:command:type (type = ide|terminal)
SUPPORTED_EDITORS=(
    # IDEs (project-based window)
    "zed:zed:ide"
    "vscode:code:ide"
    "cursor:cursor:ide"
    "windsurf:windsurf:ide"
    # Terminal emulators (directory-based)
    "kitty:kitty:terminal"
    "alacritty:alacritty:terminal"
    "wezterm:wezterm:terminal"
    "gnome-terminal:gnome-terminal:terminal"
    "konsole:konsole:terminal"
    "iterm2:open -a iTerm:terminal"
    "terminal-app:open -a Terminal:terminal"
)

# Get editor config file path
get_editor_config_file() {
    echo "$CONFIG_DIR/config.json"
}

# Ensure editor config exists
ensure_editor_config() {
    ensure_config
    local config_file
    config_file=$(get_editor_config_file)
    if [[ ! -f "$config_file" ]]; then
        echo '{"editor":{"name":"auto"},"claude":{"permission_mode":"auto-accept"}}' > "$config_file"
    else
        # Ensure claude section exists
        if ! jq -e '.claude' "$config_file" &>/dev/null; then
            local tmp
            tmp=$(mktemp)
            jq '.claude = {"permission_mode": "auto-accept"}' "$config_file" > "$tmp" && mv "$tmp" "$config_file"
        fi
    fi
}

# Get configured editor name (returns "auto" if not set)
get_configured_editor() {
    ensure_editor_config
    local config_file
    config_file=$(get_editor_config_file)
    local editor_name
    editor_name=$(json_get "$config_file" '.editor.name')
    echo "${editor_name:-auto}"
}

# Set configured editor
set_configured_editor() {
    local editor_name="$1"
    ensure_editor_config
    local config_file
    config_file=$(get_editor_config_file)

    # Validate editor name
    if [[ "$editor_name" != "auto" ]]; then
        local valid=false
        for entry in "${SUPPORTED_EDITORS[@]}"; do
            local name="${entry%%:*}"
            if [[ "$name" == "$editor_name" ]]; then
                valid=true
                break
            fi
        done
        if ! $valid; then
            error "Invalid editor: $editor_name"
            echo "Valid editors: auto, $(get_supported_editor_names | tr '\n' ' ')" >&2
            return 1
        fi
    fi

    local tmp
    tmp=$(mktemp)
    jq --arg name "$editor_name" '.editor.name = $name' "$config_file" > "$tmp" && mv "$tmp" "$config_file"
}

# Get configured Claude permission mode (returns "auto-accept" if not set)
get_claude_permission_mode() {
    ensure_editor_config
    local config_file
    config_file=$(get_editor_config_file)
    local mode
    mode=$(json_get "$config_file" '.claude.permission_mode')
    echo "${mode:-auto-accept}"
}

# Set Claude permission mode
set_claude_permission_mode() {
    local mode="$1"
    ensure_editor_config
    local config_file
    config_file=$(get_editor_config_file)

    # Validate mode
    case "$mode" in
        auto-accept|plan|allowedTools)
            ;;
        *)
            error "Invalid permission mode: $mode"
            echo "Valid modes: auto-accept, plan, allowedTools" >&2
            return 1
            ;;
    esac

    local tmp
    tmp=$(mktemp)
    jq --arg mode "$mode" '.claude.permission_mode = $mode' "$config_file" > "$tmp" && mv "$tmp" "$config_file"
}

# Get Claude CLI flags for the configured permission mode
# Usage: get_claude_permission_flags [mode_override]
get_claude_permission_flags() {
    local mode="${1:-}"
    if [[ -z "$mode" ]]; then
        mode=$(get_claude_permission_mode)
    fi

    case "$mode" in
        auto-accept)
            echo "--dangerously-skip-permissions"
            ;;
        allowedTools)
            echo '--allowedTools "Edit,Write,Bash,Read,Glob,Grep,Task"'
            ;;
        plan)
            # No flags - interactive mode
            echo ""
            ;;
        *)
            echo "--dangerously-skip-permissions"
            ;;
    esac
}

# Get list of supported editor names
get_supported_editor_names() {
    for entry in "${SUPPORTED_EDITORS[@]}"; do
        echo "${entry%%:*}"
    done
}

# Get editor property by name
# Usage: get_editor_property <editor_name> <property>
# Properties: command, type
get_editor_property() {
    local editor_name="$1"
    local property="$2"

    for entry in "${SUPPORTED_EDITORS[@]}"; do
        IFS=':' read -r name cmd etype <<< "$entry"
        if [[ "$name" == "$editor_name" ]]; then
            case "$property" in
                command) echo "$cmd" ;;
                type) echo "$etype" ;;
            esac
            return 0
        fi
    done
    return 1
}

# Detect if a specific editor is installed
is_editor_installed() {
    local editor_name="$1"
    local cmd
    cmd=$(get_editor_property "$editor_name" "command") || return 1

    # macOS app bundle checks (open -a <App>)
    case "$editor_name" in
        iterm2)
            [[ -d "/Applications/iTerm.app" ]] && return 0
            return 1
            ;;
        terminal-app)
            [[ -d "/Applications/Utilities/Terminal.app" ]] && return 0
            return 1
            ;;
    esac

    case "$PLATFORM" in
        linux)
            if command -v "$cmd" &>/dev/null; then
                return 0
            fi
            # Check common paths
            case "$editor_name" in
                zed)
                    [[ -x "$HOME/.local/bin/zed" ]] && return 0
                    ;;
                vscode)
                    [[ -x "/usr/bin/code" ]] && return 0
                    [[ -x "/snap/bin/code" ]] && return 0
                    ;;
                cursor)
                    [[ -x "$HOME/.local/bin/cursor" ]] && return 0
                    [[ -x "/opt/cursor/cursor" ]] && return 0
                    ;;
                windsurf)
                    [[ -x "$HOME/.local/bin/windsurf" ]] && return 0
                    ;;
            esac
            ;;
        macos)
            if command -v "$cmd" &>/dev/null; then
                return 0
            fi
            # Check Applications
            case "$editor_name" in
                zed)
                    [[ -x "/Applications/Zed.app/Contents/MacOS/zed" ]] && return 0
                    ;;
                vscode)
                    [[ -x "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ]] && return 0
                    ;;
                cursor)
                    [[ -x "/Applications/Cursor.app/Contents/MacOS/Cursor" ]] && return 0
                    ;;
                windsurf)
                    [[ -x "/Applications/Windsurf.app/Contents/MacOS/Windsurf" ]] && return 0
                    ;;
            esac
            ;;
        windows)
            command -v "$cmd" &>/dev/null && return 0
            command -v "${cmd}.exe" &>/dev/null && return 0
            command -v "${cmd}.cmd" &>/dev/null && return 0
            ;;
    esac
    return 1
}

# Find editor command path
find_editor_command() {
    local editor_name="$1"
    local cmd
    cmd=$(get_editor_property "$editor_name" "command") || return 1

    case "$PLATFORM" in
        linux)
            if command -v "$cmd" &>/dev/null; then
                echo "$cmd"
                return 0
            fi
            case "$editor_name" in
                zed)
                    [[ -x "$HOME/.local/bin/zed" ]] && echo "$HOME/.local/bin/zed" && return 0
                    ;;
                vscode)
                    [[ -x "/usr/bin/code" ]] && echo "/usr/bin/code" && return 0
                    [[ -x "/snap/bin/code" ]] && echo "/snap/bin/code" && return 0
                    ;;
                cursor)
                    [[ -x "$HOME/.local/bin/cursor" ]] && echo "$HOME/.local/bin/cursor" && return 0
                    [[ -x "/opt/cursor/cursor" ]] && echo "/opt/cursor/cursor" && return 0
                    ;;
                windsurf)
                    [[ -x "$HOME/.local/bin/windsurf" ]] && echo "$HOME/.local/bin/windsurf" && return 0
                    ;;
            esac
            ;;
        macos)
            if command -v "$cmd" &>/dev/null; then
                echo "$cmd"
                return 0
            fi
            case "$editor_name" in
                zed)
                    [[ -x "/Applications/Zed.app/Contents/MacOS/zed" ]] && echo "/Applications/Zed.app/Contents/MacOS/zed" && return 0
                    ;;
                vscode)
                    [[ -x "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ]] && echo "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" && return 0
                    ;;
                cursor)
                    [[ -x "/Applications/Cursor.app/Contents/MacOS/Cursor" ]] && echo "/Applications/Cursor.app/Contents/MacOS/Cursor" && return 0
                    ;;
                windsurf)
                    [[ -x "/Applications/Windsurf.app/Contents/MacOS/Windsurf" ]] && echo "/Applications/Windsurf.app/Contents/MacOS/Windsurf" && return 0
                    ;;
            esac
            ;;
        windows)
            if command -v "$cmd" &>/dev/null; then
                echo "$cmd"
                return 0
            fi
            if command -v "${cmd}.exe" &>/dev/null; then
                echo "${cmd}.exe"
                return 0
            fi
            if command -v "${cmd}.cmd" &>/dev/null; then
                echo "${cmd}.cmd"
                return 0
            fi
            ;;
    esac
    echo ""
    return 1
}

# Detect all available editors
detect_available_editors() {
    local available=()
    for entry in "${SUPPORTED_EDITORS[@]}"; do
        local name="${entry%%:*}"
        if is_editor_installed "$name"; then
            available+=("$name")
        fi
    done
    printf '%s\n' "${available[@]}"
}

# Get the active editor (configured or auto-detected)
# Returns: editor_name or empty if none available
get_active_editor() {
    local configured
    configured=$(get_configured_editor)

    if [[ "$configured" != "auto" ]]; then
        if is_editor_installed "$configured"; then
            echo "$configured"
            return 0
        else
            warn "Configured editor '$configured' not found, falling back to auto-detect"
        fi
    fi

    # Auto-detect in priority order
    for entry in "${SUPPORTED_EDITORS[@]}"; do
        local name="${entry%%:*}"
        if is_editor_installed "$name"; then
            echo "$name"
            return 0
        fi
    done

    echo ""
    return 1
}

# Find editor - main function
# Returns: command path for the active editor
find_editor() {
    local editor_name
    editor_name=$(get_active_editor) || return 1

    if [[ -z "$editor_name" ]]; then
        return 1
    fi

    find_editor_command "$editor_name"
}

# Get editor type for active editor (ide or terminal)
get_editor_type() {
    local editor_name
    editor_name=$(get_active_editor) || return 1
    get_editor_property "$editor_name" "type"
}

# Get the command to open an editor/terminal at a specific directory
# Usage: get_editor_open_command <editor_name> <directory>
get_editor_open_command() {
    local editor_name="$1"
    local dir="$2"
    local etype
    etype=$(get_editor_property "$editor_name" "type") || return 1
    local cmd
    cmd=$(find_editor_command "$editor_name") || cmd=$(get_editor_property "$editor_name" "command")

    if [[ "$etype" == "ide" ]]; then
        # IDEs open a project directory directly
        echo "$cmd \"$dir\""
    else
        # Terminal emulators have specific flags for working directory
        case "$editor_name" in
            kitty)          echo "$cmd --directory \"$dir\"" ;;
            alacritty)      echo "$cmd --working-directory \"$dir\"" ;;
            wezterm)        echo "$cmd start --cwd \"$dir\"" ;;
            gnome-terminal) echo "$cmd -- bash -c 'cd \"$dir\" && exec bash'" ;;
            konsole)        echo "$cmd --workdir \"$dir\"" ;;
            iterm2)         echo "open -a iTerm \"$dir\"" ;;
            terminal-app)   echo "open -a Terminal \"$dir\"" ;;
            *)              echo "$cmd \"$dir\"" ;;
        esac
    fi
}

# Get Claude shortcut tip for a given editor
# Usage: get_editor_claude_tip <editor_name>
get_editor_claude_tip() {
    local editor_name="$1"
    local etype
    etype=$(get_editor_property "$editor_name" "type") || return 1

    if [[ "$etype" == "terminal" ]]; then
        echo "run \`claude\` in the terminal"
    else
        case "$editor_name" in
            zed)      echo "Ctrl+Shift+L (Zed inline assistant)" ;;
            cursor)   echo "Ctrl+L (Cursor chat)" ;;
            vscode)   echo "open terminal and run \`claude\`" ;;
            windsurf) echo "open terminal and run \`claude\`" ;;
            *)        echo "run \`claude\` in the integrated terminal" ;;
        esac
    fi
}

# Print editor installation instructions
print_editor_install_instructions() {
    local editor_name="$1"
    echo ""
    echo "Install $editor_name:"
    case "$editor_name" in
        zed)
            case "$PLATFORM" in
                linux) echo "  curl -f https://zed.dev/install.sh | sh" ;;
                macos) echo "  brew install --cask zed" ;;
                windows) echo "  Download from https://zed.dev/download" ;;
            esac
            ;;
        vscode)
            case "$PLATFORM" in
                linux) echo "  sudo snap install code --classic" ;;
                macos) echo "  brew install --cask visual-studio-code" ;;
                windows) echo "  Download from https://code.visualstudio.com/" ;;
            esac
            ;;
        cursor)   echo "  Download from https://cursor.sh/" ;;
        windsurf) echo "  Download from https://windsurf.com/" ;;
        kitty)    echo "  https://sw.kovidgoyal.net/kitty/binary/" ;;
        alacritty) echo "  https://github.com/alacritty/alacritty/releases" ;;
        wezterm)  echo "  https://wezfurlong.org/wezterm/install/linux.html" ;;
        gnome-terminal) echo "  sudo apt install gnome-terminal" ;;
        konsole)  echo "  sudo apt install konsole" ;;
        iterm2)   echo "  brew install --cask iterm2" ;;
        terminal-app) echo "  Built-in on macOS" ;;
    esac
}

# =============================================================================
# Python Resolution
# =============================================================================

# Well-known python3 locations to probe (after PATH)
_PYTHON_PROBE_PATHS=(
    "$HOME/miniconda3/bin/python3"
    "$HOME/anaconda3/bin/python3"
    "$HOME/.pyenv/shims/python3"
    "/usr/bin/python3"
)

# Find a working python3 binary.
# Checks PATH first, then well-known locations.
# Returns: absolute path to python3 (stdout), exit 1 if not found
find_python() {
    if command -v python3 &>/dev/null; then
        command -v python3
        return 0
    fi
    for p in "${_PYTHON_PROBE_PATHS[@]}"; do
        if [[ -x "$p" ]]; then
            echo "$p"
            return 0
        fi
    done
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

# =============================================================================
# Legacy wrapper for backward compatibility
# =============================================================================

# Find Zed editor (legacy wrapper)
find_zed() {
    # If zed is configured or available, use the new system
    local active
    active=$(get_active_editor)
    if [[ "$active" == "zed" ]]; then
        find_editor_command "zed"
    else
        # Fallback to direct zed detection for scripts that specifically need zed
        case "$PLATFORM" in
            linux)
                if command -v zed &>/dev/null; then
                    echo "zed"
                elif [[ -x "$HOME/.local/bin/zed" ]]; then
                    echo "$HOME/.local/bin/zed"
                else
                    echo ""
                fi
                ;;
            macos)
                if command -v zed &>/dev/null; then
                    echo "zed"
                elif [[ -x "/Applications/Zed.app/Contents/MacOS/zed" ]]; then
                    echo "/Applications/Zed.app/Contents/MacOS/zed"
                else
                    echo ""
                fi
                ;;
            windows)
                if command -v zed &>/dev/null; then
                    echo "zed"
                elif command -v zed.exe &>/dev/null; then
                    echo "zed.exe"
                else
                    echo ""
                fi
                ;;
            *)
                echo ""
                ;;
        esac
    fi
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

    # Build wrapper script (avoids quoting hell with script -c)
    cat > "$tmpscript" <<WRAPPER
#!/bin/bash
exec env -u CLAUDECODE claude -p "\$(cat '$tmpprompt')" --dangerously-skip-permissions $quoted_args
WRAPPER
    chmod +x "$tmpscript"

    local timeout_secs="${RUN_CLAUDE_TIMEOUT:-180}"
    local output rc=0
    output=$(timeout --foreground "$timeout_secs" script -f -q /dev/null -c "$tmpscript" 2>/dev/null) || rc=$?
    [[ $rc -ne 0 ]] && return $rc
    # Strip terminal escape codes (CSI sequences, OSC sequences, carriage returns)
    printf '%s' "$output" | sed 's/\x1b\[[^a-zA-Z]*[a-zA-Z]//g; s/\x1b\][^\x07]*\x07//g; s/\r//g'
}
