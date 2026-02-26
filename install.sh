#!/usr/bin/env bash
# wt-tools installer for Linux and macOS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/bin"

# Source wt-common.sh for shared functions (find_python, save_shodh_python, etc.)
source "$SCRIPT_DIR/bin/wt-common.sh"

# Override color helpers with installer-style prefixes (wt-common.sh defines simpler versions)
info() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# PLATFORM is already set by wt-common.sh (detect_platform)

# Ensure ~/.local/bin is in PATH by adding to shell rc file
ensure_path() {
    local install_dir="$1"

    # Already in PATH? Nothing to do
    if [[ ":$PATH:" == *":$install_dir:"* ]]; then
        return 0
    fi

    # Detect shell rc file
    local rc_file
    case "${SHELL:-/bin/bash}" in
        */zsh)  rc_file="$HOME/.zshrc" ;;
        */bash) rc_file="$HOME/.bashrc" ;;
        *)      rc_file="$HOME/.profile" ;;
    esac

    # Check idempotency marker
    if [[ -f "$rc_file" ]] && grep -q '# WT-TOOLS:PATH' "$rc_file"; then
        info "PATH entry already in $rc_file (marker found)"
        return 0
    fi

    # Append PATH export with marker
    {
        echo ""
        echo '# WT-TOOLS:PATH'
        echo "export PATH=\"\$HOME/.local/bin:\$PATH\""
    } >> "$rc_file"

    success "Added $install_dir to PATH in $rc_file"
    info "Run 'source $rc_file' or open a new terminal to apply"
}

check_command() {
    command -v "$1" &>/dev/null
}

# Check if a Debian/Ubuntu package is installed
check_dpkg() {
    dpkg -s "$1" &>/dev/null
}

# Check if npm global installs need sudo
npm_needs_sudo() {
    if ! check_command npm; then
        return 1
    fi
    local npm_prefix
    npm_prefix=$(npm config get prefix 2>/dev/null)
    # Check if we can write to the npm global directory
    if [[ -w "$npm_prefix/lib/node_modules" ]]; then
        return 1  # No sudo needed
    else
        return 0  # Sudo needed
    fi
}

# Run npm install -g, using sudo if needed
run_npm_global() {
    local package="$1"
    if npm_needs_sudo; then
        echo "  (requires sudo for global npm packages)"
        sudo npm install -g "$package"
    else
        npm install -g "$package"
    fi
}

# Install system packages on Linux
install_system_packages() {
    local packages=("$@")
    if [[ ${#packages[@]} -eq 0 ]]; then
        return 0
    fi

    info "Installing system packages: ${packages[*]}"
    echo "  (requires sudo)"

    if check_command apt-get; then
        sudo apt-get update -qq
        sudo apt-get install -y "${packages[@]}"
    elif check_command dnf; then
        sudo dnf install -y "${packages[@]}"
    elif check_command pacman; then
        sudo pacman -S --noconfirm "${packages[@]}"
    else
        error "No supported package manager found (apt/dnf/pacman)"
        return 1
    fi
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."

    local missing=()
    local to_install=()

    # Required: git (usually pre-installed)
    if ! check_command git; then
        missing+=("git")
    fi

    # Required: jq (can be auto-installed)
    if ! check_command jq; then
        to_install+=("jq")
    fi

    # Platform-specific packages
    if [[ "$PLATFORM" == "linux" ]]; then
        if ! check_command xdotool; then
            to_install+=("xdotool")
        fi
        # Qt6 xcb plugin requires libxcb-cursor0 for GUI
        if ! check_dpkg libxcb-cursor0; then
            to_install+=("libxcb-cursor0")
        fi
    fi

    # Fail on truly missing prerequisites (git)
    if [[ ${#missing[@]} -gt 0 ]]; then
        error "Missing required tools: ${missing[*]}"
        echo ""
        echo "Install them first:"
        case "$PLATFORM" in
            linux)
                echo "  sudo apt install ${missing[*]}  # Debian/Ubuntu"
                echo "  sudo dnf install ${missing[*]}  # Fedora"
                echo "  sudo pacman -S ${missing[*]}    # Arch"
                ;;
            macos)
                echo "  brew install ${missing[*]}"
                ;;
        esac
        exit 1
    fi

    # Auto-install missing packages on Linux
    if [[ ${#to_install[@]} -gt 0 ]]; then
        case "$PLATFORM" in
            linux)
                install_system_packages "${to_install[@]}"
                ;;
            macos)
                warn "Missing packages: ${to_install[*]}"
                echo "  Install with: brew install ${to_install[*]}"
                ;;
        esac
    fi

    success "Prerequisites OK"
}

# Install wt-tools scripts
install_scripts() {
    info "Installing wt-tools scripts to $INSTALL_DIR..."

    mkdir -p "$INSTALL_DIR"

    local scripts=(wt-common.sh wt-project wt-new wt-work wt-add wt-list wt-merge wt-close wt-version wt-status wt-focus wt-config wt-control wt-control-gui wt-control-init wt-control-sync wt-control-chat wt-loop wt-usage wt-skill-start wt-hook-stop wt-hook-skill wt-hook-activity wt-hook-memory wt-hook-memory-save wt-hook-memory-recall wt-hook-memory-warmstart wt-hook-memory-pretool wt-hook-memory-posttool wt-deploy-hooks wt-memory wt-openspec wt-audit)

    for script in "${scripts[@]}"; do
        local src="$SCRIPT_DIR/bin/$script"
        local dst="$INSTALL_DIR/$script"

        if [[ -f "$src" ]]; then
            ln -sf "$src" "$dst"
            success "  Linked: $script"
        else
            warn "  Not found: $src"
        fi
    done

    # Ensure INSTALL_DIR is in PATH
    ensure_path "$INSTALL_DIR"
}

# Install Claude Code CLI
install_claude_code() {
    info "Checking Claude Code CLI..."

    if check_command claude; then
        local version
        version=$(claude --version 2>/dev/null | head -1 || echo "unknown")
        success "Claude Code CLI already installed: $version"
        return 0
    fi

    if ! check_command npm; then
        warn "npm not found. Skipping Claude Code CLI installation."
        echo "  Install Node.js first, then run: [sudo] npm install -g @anthropic-ai/claude-code"
        return 1
    fi

    echo "Installing Claude Code CLI..."
    run_npm_global @anthropic-ai/claude-code

    if check_command claude; then
        success "Claude Code CLI installed"
    else
        warn "Claude Code CLI installation may have failed"
    fi
}


# Install Zed editor
install_zed() {
    info "Checking Zed editor..."

    local zed_found=false

    if check_command zed; then
        zed_found=true
    elif [[ -x "$HOME/.local/bin/zed" ]]; then
        zed_found=true
    elif [[ "$PLATFORM" == "macos" && -x "/Applications/Zed.app/Contents/MacOS/zed" ]]; then
        zed_found=true
    fi

    if $zed_found; then
        success "Zed editor already installed"
        return 0
    fi

    echo ""
    read -p "Zed editor not found. Install it? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        warn "Skipping Zed installation"
        return 0
    fi

    case "$PLATFORM" in
        linux)
            info "Installing Zed for Linux..."
            curl -f https://zed.dev/install.sh | sh
            ;;
        macos)
            if check_command brew; then
                info "Installing Zed via Homebrew..."
                brew install --cask zed
            else
                info "Opening Zed download page..."
                open "https://zed.dev/download"
                echo "Please download and install Zed manually."
            fi
            ;;
    esac

    if check_command zed || [[ -x "$HOME/.local/bin/zed" ]]; then
        success "Zed editor installed"
    else
        warn "Zed installation may require manual steps"
    fi
}

# Install Shodh-Memory (optional — developer memory for OpenSpec workflow)
install_shodh_memory() {
    info "Checking Shodh-Memory..."

    # Use find_python() to locate the target Python (shared from wt-common.sh)
    local PYTHON=""
    if ! PYTHON=$(find_python); then
        warn "No python3 found. Skipping Shodh-Memory."
        return 0
    fi

    # Read version pin from pyproject.toml (single source of truth)
    local shodh_pkg=""
    local pyproject="$SCRIPT_DIR/pyproject.toml"
    if [[ -f "$pyproject" ]]; then
        shodh_pkg=$(grep 'shodh-memory' "$pyproject" | head -1 | sed 's/.*"\(shodh-memory[^"]*\)".*/\1/')
    fi
    if [[ -z "$shodh_pkg" ]]; then
        shodh_pkg='shodh-memory>=0.1.81'  # fallback
    fi

    # Already installed? Check if version satisfies the pin.
    if "$PYTHON" -c "import sys; sys._shodh_star_shown = True; from shodh_memory import Memory" 2>/dev/null; then
        save_shodh_python "$PYTHON"
        # Try upgrade to satisfy the pin (pip handles "already satisfied" cheaply)
        if "$PYTHON" -m pip install "$shodh_pkg" >/dev/null 2>&1; then
            success "Shodh-Memory up to date ($(basename "$PYTHON"))"
        else
            success "Shodh-Memory already installed ($(basename "$PYTHON"))"
        fi
        return 0
    fi

    echo ""
    echo "  Shodh-Memory provides local cognitive memory for the OpenSpec workflow."
    echo "  It's optional — without it, all memory operations are silently skipped."
    echo ""
    read -p "Install Shodh-Memory? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "Skipping Shodh-Memory (wt-memory will work in no-op mode)"
        return 0
    fi

    info "Installing Shodh-Memory into $PYTHON..."
    # Use $PYTHON -m pip to guarantee pip matches the target Python
    if "$PYTHON" -m pip install "$shodh_pkg" >/dev/null 2>&1; then
        :
    elif "$PYTHON" -m pip install --user "$shodh_pkg" >/dev/null 2>&1; then
        :
    elif "$PYTHON" -m pip install --break-system-packages "$shodh_pkg" 2>&1; then
        :
    else
        warn "Shodh-Memory installation failed. Install manually: $PYTHON -m pip install '$shodh_pkg'"
        return 0
    fi

    # Verify and persist
    if "$PYTHON" -c "import sys; sys._shodh_star_shown = True; from shodh_memory import Memory" 2>/dev/null; then
        save_shodh_python "$PYTHON"
        success "Shodh-Memory installed"
        echo "  Python: $PYTHON"
        echo "  Check status with: wt-memory status"
    else
        warn "Shodh-Memory installed but import verification failed"
    fi
}

# Install shell completions
install_completions() {
    info "Installing shell completions..."

    # Bash completions
    local bash_completion_dir="${HOME}/.local/share/bash-completion/completions"
    mkdir -p "$bash_completion_dir"

    if [[ -f "$SCRIPT_DIR/bin/wt-completions.bash" ]]; then
        ln -sf "$SCRIPT_DIR/bin/wt-completions.bash" "$bash_completion_dir/wt-completions"
        success "  Bash completions installed"
        echo "    Add to ~/.bashrc: source ~/.local/share/bash-completion/completions/wt-completions"
    fi

    # Zsh completions
    local zsh_completion_dir="${HOME}/.local/share/zsh/site-functions"
    mkdir -p "$zsh_completion_dir"

    if [[ -f "$SCRIPT_DIR/bin/wt-completions.zsh" ]]; then
        ln -sf "$SCRIPT_DIR/bin/wt-completions.zsh" "$zsh_completion_dir/_wt"
        success "  Zsh completions installed"
        echo "    Add to ~/.zshrc: fpath=(~/.local/share/zsh/site-functions \$fpath)"
    fi
}

# Install GUI Python dependencies
install_gui_dependencies() {
    info "Installing GUI Python dependencies..."

    local requirements_file="$SCRIPT_DIR/gui/requirements.txt"

    if [[ ! -f "$requirements_file" ]]; then
        warn "GUI requirements.txt not found at $requirements_file"
        return 1
    fi

    # Use find_python() to locate the target Python (shared from wt-common.sh)
    local PYTHON=""
    if ! PYTHON=$(find_python); then
        warn "No python3 found. Skipping GUI dependencies."
        echo "  Install Python 3 first, then run: python3 -m pip install -r $requirements_file"
        return 1
    fi

    # Install from requirements.txt using $PYTHON -m pip
    info "Installing from $requirements_file into $PYTHON..."
    if "$PYTHON" -m pip install -r "$requirements_file" >/dev/null 2>&1; then
        success "GUI dependencies installed (PySide6, psutil, PyNaCl)"
    elif "$PYTHON" -m pip install --user -r "$requirements_file" >/dev/null 2>&1; then
        success "GUI dependencies installed with --user (PySide6, psutil, PyNaCl)"
    elif "$PYTHON" -m pip install --break-system-packages -r "$requirements_file" 2>&1; then
        success "GUI dependencies installed (PySide6, psutil, PyNaCl)"
    else
        warn "Some GUI dependencies may have failed to install"
        echo "  Try manually: $PYTHON -m pip install -r $requirements_file"
    fi
}

# Install desktop entry for Alt+F2 / application menu
install_desktop_entry() {
    info "Installing desktop entry..."

    local apps_dir="$HOME/.local/share/applications"
    mkdir -p "$apps_dir"

    # Use wt-control wrapper script (handles PYTHONPATH)
    local wt_control_path="$INSTALL_DIR/wt-control"

    # Install custom icon
    local icon_dir="$HOME/.local/share/icons"
    local icon_path="utilities-terminal"
    local icon_src="$SCRIPT_DIR/assets/icon.png"
    if [[ -f "$icon_src" ]]; then
        mkdir -p "$icon_dir"
        cp "$icon_src" "$icon_dir/wt-control.png"
        icon_path="$icon_dir/wt-control.png"
    fi

    cat > "$apps_dir/wt-control.desktop" << EOF
[Desktop Entry]
Name=Worktree Control Center
Comment=Manage git worktrees and Claude agents
Exec=$wt_control_path
Icon=$icon_path
Terminal=false
Type=Application
Categories=Development;
Keywords=worktree;git;claude;
EOF

    chmod +x "$apps_dir/wt-control.desktop"

    # Update desktop database
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$apps_dir" 2>/dev/null
    fi

    # Add friendly symlinks so Alt+F2 "Worktree" or "worktree" works
    ln -sf "$wt_control_path" "$INSTALL_DIR/Worktree"
    ln -sf "$wt_control_path" "$INSTALL_DIR/worktree"

    success "Desktop entry installed (Activities: 'Worktree', Alt+F2: 'wt-control' or 'Worktree')"
}

# Install macOS .app bundle for Spotlight/Alfred/Raycast/Dock discovery
install_macos_app_bundle() {
    info "Installing macOS app bundle..."

    local app_dir="$HOME/Applications/WT Control.app"
    local contents_dir="$app_dir/Contents"
    local macos_dir="$contents_dir/MacOS"
    local resources_dir="$contents_dir/Resources"

    # Create directory structure
    mkdir -p "$macos_dir" "$resources_dir"

    # Generate Info.plist
    cat > "$contents_dir/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>WT Control</string>
    <key>CFBundleIdentifier</key>
    <string>com.wt-tools.control</string>
    <key>CFBundleExecutable</key>
    <string>wt-control</string>
    <key>CFBundleIconFile</key>
    <string>app</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

    # Generate executable wrapper
    cat > "$macos_dir/wt-control" << 'WRAPPER'
#!/bin/bash
WT_CONTROL="$HOME/.local/bin/wt-control"
if [[ ! -x "$WT_CONTROL" ]]; then
    osascript -e 'display dialog "wt-tools is not installed.\n\nRun install.sh from the wt-tools directory first." buttons {"OK"} default button "OK" with title "WT Control" with icon stop'
    exit 1
fi
exec "$WT_CONTROL" "$@"
WRAPPER
    chmod +x "$macos_dir/wt-control"

    # Copy app icon if available
    local icon_src="$SCRIPT_DIR/assets/icon.icns"
    if [[ -f "$icon_src" ]]; then
        cp "$icon_src" "$resources_dir/app.icns"
    fi

    # Trigger Spotlight indexing
    mdimport "$app_dir" 2>/dev/null || true

    success "macOS app bundle installed — search 'WT Control' in Spotlight (Cmd+Space)"
}

# Verify GUI can start
verify_gui_startup() {
    info "Verifying GUI startup..."

    local PYTHON=""
    if ! PYTHON=$(find_python); then
        warn "No python3 found — cannot verify GUI"
        return 1
    fi

    # Test Python imports
    local project_root="$SCRIPT_DIR"
    if ! PYTHONPATH="$project_root" "$PYTHON" -c "from gui.control_center import ControlCenter" 2>/dev/null; then
        warn "GUI import test failed"
        echo "  Try: PYTHONPATH=$project_root $PYTHON -c 'from gui.control_center import ControlCenter'"
        return 1
    fi

    # Test PySide6
    if ! "$PYTHON" -c "from PySide6.QtWidgets import QApplication" 2>/dev/null; then
        warn "PySide6 import test failed"
        echo "  Try: $PYTHON -m pip install PySide6"
        return 1
    fi

    success "GUI startup verification passed"
}

# Install Claude Code skills and commands
# Note: wt commands/skills are deployed per-project by wt-project init.
# No global symlinks needed — per-project deployment enables version pinning.
install_skills() {
    info "Claude Code skills and commands..."
    info "  wt commands/skills deployed per-project via wt-project init"

    # Clean up legacy global symlinks if present
    local legacy_wt_commands="$HOME/.claude/commands/wt"
    local legacy_wt_skills="$HOME/.claude/skills/wt"
    if [[ -L "$legacy_wt_commands" ]]; then
        rm "$legacy_wt_commands"
        info "  Removed legacy global symlink: $legacy_wt_commands"
    fi
    if [[ -L "$legacy_wt_skills" ]]; then
        rm "$legacy_wt_skills"
        info "  Removed legacy global symlink: $legacy_wt_skills"
    fi
}

# Deploy wt-tools (hooks, commands, skills) to all registered projects
# Uses wt-project init which handles both registration and deployment
install_projects() {
    info "Deploying wt-tools to registered projects..."

    local projects_file="$HOME/.config/wt-tools/projects.json"
    if [[ ! -f "$projects_file" ]]; then
        info "  No projects.json found, skipping"
        return 0
    fi

    local project_paths
    project_paths=$(jq -r '.projects // {} | to_entries[] | .value.path' "$projects_file" 2>/dev/null)

    if [[ -z "$project_paths" ]]; then
        info "  No registered projects, skipping"
        return 0
    fi

    while IFS= read -r project_path; do
        if [[ -d "$project_path" ]]; then
            info "  Updating: $project_path"
            (cd "$project_path" && "$SCRIPT_DIR/bin/wt-project" init) || warn "  Failed: $project_path"

            # Also deploy to each worktree of this project
            local worktree_paths
            worktree_paths=$(git -C "$project_path" worktree list --porcelain 2>/dev/null \
                | grep '^worktree ' | cut -d' ' -f2- | grep -v "^$project_path$")
            while IFS= read -r wt_path; do
                [[ -z "$wt_path" ]] && continue
                if [[ -d "$wt_path" ]]; then
                    info "  Updating worktree: $wt_path"
                    (cd "$wt_path" && "$SCRIPT_DIR/bin/wt-project" init) || warn "  Failed worktree: $wt_path"
                fi
            done <<< "$worktree_paths"
        else
            warn "  Project path not found: $project_path"
        fi
    done <<< "$project_paths"
}

# Install MCP server and status line
install_mcp_statusline() {
    info "Installing MCP server and status line..."

    local claude_dir="$HOME/.claude"
    mkdir -p "$claude_dir"

    # Copy statusline script
    local src="$SCRIPT_DIR/mcp-server/statusline.sh"
    local dst="$claude_dir/statusline.sh"

    if [[ -f "$src" ]]; then
        cp "$src" "$dst"
        chmod +x "$dst"
        success "  Installed: statusline.sh"
    else
        # Create statusline.sh if not in repo
        cat > "$dst" << 'STATUSLINE_EOF'
#!/bin/bash
# Claude Code Status Line Script - wt-tools
# Shows: folder, branch, model, context usage, wt-loop status

input=$(cat)

model=$(echo "$input" | jq -r '.model.display_name')
dir=$(echo "$input" | jq -r '.workspace.current_dir')
folder=$(basename "$dir")

branch=$(cd "$dir" 2>/dev/null && git -c core.useBuiltinFSMonitor=false rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')
git_info=""
if [ -n "$branch" ]; then git_info=" ($branch)"; fi

remaining=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
ctx_size=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
total_input=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_output=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
agents=$(echo "$input" | jq -r '.agents // [] | length')

# wt-loop status
ralph_status=""
state_file="$dir/.claude/loop-state.json"
if [ -f "$state_file" ]; then
    status=$(jq -r '.status // empty' "$state_file" 2>/dev/null)
    iteration=$(jq -r '.current_iteration // 0' "$state_file" 2>/dev/null)
    max_iter=$(jq -r '.max_iterations // 0' "$state_file" 2>/dev/null)
    case "$status" in
        running) ralph_status=" | 🔄 Ralph: $iteration/$max_iter" ;;
        done) ralph_status=" | ✅ Ralph: done" ;;
        stuck) ralph_status=" | ⚠️ Ralph: stuck" ;;
        stopped) ralph_status=" | ⏹️ Ralph: stopped" ;;
    esac
fi

if [ -n "$remaining" ]; then
    total_tokens=$((total_input + total_output))
    ctx_size_k=$((ctx_size / 1000))
    printf "[%s] %s%s | %s | Ctx: %s%% (%s/%sk)%s | Agents: %s" \
        "$folder" "$folder" "$git_info" "$model" "$used" "$total_tokens" "$ctx_size_k" "$ralph_status" "$agents"
else
    printf "[%s] %s%s | %s%s | Agents: %s" \
        "$folder" "$folder" "$git_info" "$model" "$ralph_status" "$agents"
fi
STATUSLINE_EOF
        chmod +x "$dst"
        success "  Created: statusline.sh"
    fi

    # Update settings.json to use statusline
    local settings_file="$claude_dir/settings.json"
    if [[ -f "$settings_file" ]]; then
        # Backup existing
        cp "$settings_file" "$settings_file.bak"
        # Add statusLine if not present
        if ! grep -q '"statusLine"' "$settings_file"; then
            # Add statusLine to existing JSON
            jq '. + {"statusLine": {"type": "command", "command": "~/.claude/statusline.sh"}}' "$settings_file" > "$settings_file.tmp" && mv "$settings_file.tmp" "$settings_file"
            success "  Updated: settings.json (added statusLine)"
        else
            info "  settings.json already has statusLine config"
        fi
    else
        # Create new settings.json
        cat > "$settings_file" << 'EOF'
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh"
  }
}
EOF
        success "  Created: settings.json"
    fi

    # Install MCP server
    if check_command claude; then
        local mcp_server_dir="$SCRIPT_DIR/mcp-server"
        if [[ -d "$mcp_server_dir" ]]; then
            # Check if uv is available
            # Auto-install uv if not available
            if ! check_command uv; then
                info "  Installing uv (Python package manager)..."
                curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null
                # Add to current PATH so we can use it immediately
                export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
            fi

            if check_command uv; then
                info "  Setting up MCP server dependencies..."
                (cd "$mcp_server_dir" && uv sync 2>/dev/null) || true

                # Clean up legacy global MCP registrations (now per-project via wt-project init)
                claude mcp remove --scope user wt-tools 2>/dev/null || true
                claude mcp remove --scope user wt-memory 2>/dev/null || true
                info "  MCP server is registered per-project via wt-project init"
            else
                warn "  uv installation failed. MCP server requires uv."
                echo "    Try manually: curl -LsSf https://astral.sh/uv/install.sh | sh"
            fi
        fi
    fi
}

# Configure Zed with Claude Code task and keybinding
configure_editor_choice() {
    info "Detecting available editors..."

    local available=()
    local labels=()
    local i=1

    for entry in "${SUPPORTED_EDITORS[@]}"; do
        IFS=':' read -r name cmd etype <<< "$entry"
        if is_editor_installed "$name"; then
            available+=("$name")
            labels+=("$i) $name ($etype)")
            ((i++))
        fi
    done

    if [[ ${#available[@]} -eq 0 ]]; then
        warn "No supported editors found. Using auto-detect."
        return
    fi

    echo ""
    echo "Available editors:"
    for label in "${labels[@]}"; do
        echo "  $label"
    done
    echo "  $i) auto (detect at runtime)"
    echo ""

    local choice
    read -r -p "Select editor [1-$i, default: $i]: " choice
    choice="${choice:-$i}"

    if [[ "$choice" -eq "$i" ]]; then
        set_configured_editor "auto"
        success "Editor set to: auto-detect"
    elif [[ "$choice" -ge 1 && "$choice" -lt "$i" ]]; then
        local selected="${available[$((choice-1))]}"
        set_configured_editor "$selected"
        success "Editor set to: $selected"
    else
        warn "Invalid choice, using auto-detect"
        set_configured_editor "auto"
    fi
}

configure_permission_mode() {
    info "Configure Claude permission mode..."

    echo ""
    echo "Claude Code permission modes:"
    echo "  1) auto-accept   - Full autonomy (--dangerously-skip-permissions)"
    echo "  2) allowedTools   - Selective permissions (Edit, Write, Bash, etc.)"
    echo "  3) plan           - Interactive, approve each action"
    echo ""

    local choice
    read -r -p "Select permission mode [1-3, default: 1]: " choice
    choice="${choice:-1}"

    case "$choice" in
        1) set_claude_permission_mode "auto-accept"; success "Permission mode: auto-accept" ;;
        2) set_claude_permission_mode "allowedTools"; success "Permission mode: allowedTools" ;;
        3) set_claude_permission_mode "plan"; success "Permission mode: plan" ;;
        *) warn "Invalid choice, using auto-accept"; set_claude_permission_mode "auto-accept" ;;
    esac
}

configure_zed() {
    info "Configuring Zed for Claude Code..."

    local zed_config_dir="$HOME/.config/zed"
    mkdir -p "$zed_config_dir"

    # Add Claude Code task (reads permission mode from config)
    local perm_mode
    perm_mode=$(get_claude_permission_mode 2>/dev/null || echo "auto-accept")
    local perm_args=""
    case "$perm_mode" in
        auto-accept)  perm_args='"--dangerously-skip-permissions"' ;;
        allowedTools) perm_args='"--allowedTools", "Edit,Write,Bash,Read,Glob,Grep,Task"' ;;
        plan)         perm_args="" ;;
    esac

    if [[ -n "$perm_args" ]]; then
        cat > "$zed_config_dir/tasks.json" << EOF
[
  {
    "label": "Claude Code",
    "command": "claude",
    "args": [$perm_args],
    "working_directory": "\$ZED_WORKTREE_ROOT",
    "use_new_terminal": true,
    "reveal": "always"
  }
]
EOF
    else
        cat > "$zed_config_dir/tasks.json" << 'EOF'
[
  {
    "label": "Claude Code",
    "command": "claude",
    "args": [],
    "working_directory": "$ZED_WORKTREE_ROOT",
    "use_new_terminal": true,
    "reveal": "always"
  }
]
EOF
    fi
    success "Created Zed tasks.json"

    # Add keybinding for Claude Code
    cat > "$zed_config_dir/keymap.json" << 'EOF'
[
  {
    "bindings": {
      "ctrl-shift-l": ["task::Spawn", { "task_name": "Claude Code" }]
    }
  }
]
EOF
    success "Created Zed keymap.json (Ctrl+Shift+L for Claude)"
}

# Main
main() {
    echo ""
    echo "================================"
    echo "  wt-tools Installer"
    echo "================================"
    echo ""

    check_prerequisites
    echo ""

    install_scripts
    echo ""

    install_completions
    echo ""

    install_claude_code
    echo ""

    install_zed
    echo ""

    # Source wt-common.sh for editor/permission config functions
    # (SUPPORTED_EDITORS, set_configured_editor, set_claude_permission_mode, etc.)
    source "$SCRIPT_DIR/bin/wt-common.sh"

    configure_editor_choice
    echo ""

    configure_permission_mode
    echo ""

    configure_zed
    echo ""

    install_skills
    echo ""

    install_mcp_statusline
    echo ""

    install_projects
    echo ""

    install_gui_dependencies
    echo ""

    install_shodh_memory
    echo ""

    if [[ "$PLATFORM" == "linux" ]]; then
        install_desktop_entry
        echo ""
    fi

    if [[ "$PLATFORM" == "macos" ]]; then
        install_macos_app_bundle
        echo ""
    fi

    verify_gui_startup
    echo ""

    echo "================================"
    success "Installation complete!"
    echo "================================"
    echo ""
    echo "Quick start:"
    echo "  cd /path/to/your/project"
    echo "  wt-project init"
    echo "  wt-new my-change"
    echo "  wt-work my-change"
    echo ""
    echo "GUI Control Center:"
    echo "  wt-control            # Launch from terminal"
    if [[ "$PLATFORM" == "linux" ]]; then
        echo "  Alt+F2 → 'Worktree'   # Launch from anywhere"
    elif [[ "$PLATFORM" == "macos" ]]; then
        echo "  Cmd+Space → 'WT Control'  # Launch from Spotlight"
    fi
    echo ""
}

main "$@"
