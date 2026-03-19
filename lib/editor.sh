#!/usr/bin/env bash
# set-core editor detection and configuration
# Dependencies: set-common.sh must be sourced first (provides PLATFORM, CONFIG_DIR, ensure_config, json_get, warn, error)

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
