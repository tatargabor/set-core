#!/usr/bin/env bash
# migrate-to-set.sh — Migrate from wt-tools to SET (ShipExactlyThis)
#
# This script handles:
#   1. Per-project migration (.wt/ → .set/, .gitignore, MCP)
#   2. Global migration (config dirs, symlinks, systemd, shell rc)
#
# Safe to run multiple times (idempotent).
# Run from the set-core repo root, or pass --global for global-only migration.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ─── Per-Project Migration ───────────────────────────────────────────

migrate_project() {
    local project_dir="$1"
    info "Migrating project: $project_dir"

    # 1. Rename .wt/ → .set/ (per-worktree agent dir)
    if [[ -d "$project_dir/.wt" ]]; then
        if [[ -d "$project_dir/.set" ]]; then
            warn "  Both .wt/ and .set/ exist in $project_dir — skipping .wt/ rename"
        else
            mv "$project_dir/.wt" "$project_dir/.set"
            success "  Renamed .wt/ → .set/"
        fi
    fi

    # 2. Update .gitignore
    local gitignore="$project_dir/.gitignore"
    if [[ -f "$gitignore" ]]; then
        if grep -q '/.wt/' "$gitignore" && ! grep -q '/.set/' "$gitignore"; then
            sed -i 's|/\.wt/|/.set/|g' "$gitignore"
            success "  Updated .gitignore: /.wt/ → /.set/"
        fi
        # Also update wt-tools references
        if grep -q 'wt-tools' "$gitignore"; then
            sed -i 's/wt-tools/set-core/g' "$gitignore"
            success "  Updated .gitignore: wt-tools → set-core"
        fi
    fi

    # 3. MCP server migration
    if command -v claude &>/dev/null; then
        if claude mcp list 2>/dev/null | grep -q 'wt-tools'; then
            claude mcp remove wt-tools 2>/dev/null || true
            info "  Removed old 'wt-tools' MCP registration"
            info "  Run 'set-project init' to register new 'set-core' MCP server"
        fi
    fi

    # 4. Redeploy .claude/ files via set-project init
    local set_project=""
    if command -v set-project &>/dev/null; then
        set_project="set-project"
    elif [[ -x "$SCRIPT_DIR/bin/set-project" ]]; then
        set_project="$SCRIPT_DIR/bin/set-project"
    fi

    if [[ -n "$set_project" ]]; then
        info "  Running set-project init..."
        (cd "$project_dir" && "$set_project" init 2>/dev/null) || warn "  set-project init failed for $project_dir"
    else
        warn "  set-project not found — run 'set-project init' manually in $project_dir"
    fi

    # 5. Update orchestration.yaml wt- references
    local orch_yaml="$project_dir/orchestration.yaml"
    if [[ -f "$orch_yaml" ]]; then
        if grep -q 'wt-' "$orch_yaml"; then
            sed -i \
                -e 's/wt-orchestrate/set-orchestrate/g' \
                -e 's/wt-sentinel/set-sentinel/g' \
                -e 's/wt-orch-core/set-orch-core/g' \
                -e 's/wt-memory/set-memory/g' \
                -e 's/wt-project/set-project/g' \
                -e 's/wt-tools/set-core/g' \
                "$orch_yaml"
            success "  Updated orchestration.yaml"
        fi
    fi

    # 6. Migrate worktrees too
    if command -v git &>/dev/null && git -C "$project_dir" rev-parse --git-dir &>/dev/null 2>&1; then
        local worktrees
        worktrees=$(git -C "$project_dir" worktree list --porcelain 2>/dev/null | grep '^worktree ' | cut -d' ' -f2- | grep -v "^$project_dir$")
        while IFS= read -r wt_path; do
            [[ -z "$wt_path" ]] && continue
            if [[ -d "$wt_path/.wt" && ! -d "$wt_path/.set" ]]; then
                mv "$wt_path/.wt" "$wt_path/.set"
                success "  Worktree: renamed .wt/ → .set/ in $wt_path"
            fi
        done <<< "$worktrees"
    fi

    success "Project migrated: $project_dir"
}

# ─── Global Migration ────────────────────────────────────────────────

migrate_global() {
    info "Running global migration..."

    # 1. Config directory: ~/.config/wt-tools → ~/.config/set-core
    local old_config="${XDG_CONFIG_HOME:-$HOME/.config}/wt-tools"
    local new_config="${XDG_CONFIG_HOME:-$HOME/.config}/set-core"
    if [[ -d "$old_config" ]]; then
        if [[ -d "$new_config" ]]; then
            warn "Both $old_config and $new_config exist — merging manually may be needed"
        else
            mv "$old_config" "$new_config"
            success "Moved config: $old_config → $new_config"
        fi
    fi

    # 2. Data directory: ~/.local/share/wt-tools → ~/.local/share/set-core
    local old_data="${XDG_DATA_HOME:-$HOME/.local/share}/wt-tools"
    local new_data="${XDG_DATA_HOME:-$HOME/.local/share}/set-core"
    if [[ -d "$old_data" ]]; then
        if [[ -d "$new_data" ]]; then
            warn "Both $old_data and $new_data exist — merging manually may be needed"
        else
            mv "$old_data" "$new_data"
            success "Moved data: $old_data → $new_data"
        fi
    fi

    # 3. Remove old symlinks and create new ones
    local bin_dir="$HOME/.local/bin"
    if [[ -d "$bin_dir" ]]; then
        info "Cleaning old wt-* symlinks from $bin_dir..."
        local count=0
        for f in "$bin_dir"/wt-*; do
            [[ -e "$f" ]] || continue
            # Only remove if it's a symlink pointing to our old bin/
            if [[ -L "$f" ]]; then
                local target
                target=$(readlink "$f" 2>/dev/null)
                if [[ "$target" == *"/wt-tools/bin/"* ]] || [[ "$target" == *"/set-core/bin/"* ]]; then
                    rm "$f"
                    ((count++))
                fi
            fi
        done
        [[ $count -gt 0 ]] && success "Removed $count old wt-* symlinks"

        # Install compat wrappers
        if [[ -d "$SCRIPT_DIR/bin/compat" ]]; then
            for f in "$SCRIPT_DIR/bin/compat"/wt-*; do
                [[ -f "$f" ]] || continue
                local name
                name=$(basename "$f")
                ln -sf "$f" "$bin_dir/$name"
            done
            success "Installed backward-compat wrappers (wt-* → set-*)"
        fi
    fi

    # 4. systemd service
    if command -v systemctl &>/dev/null; then
        local service_dir="$HOME/.config/systemd/user"
        if [[ -f "$service_dir/wt-web.service" ]]; then
            systemctl --user stop wt-web.service 2>/dev/null || true
            systemctl --user disable wt-web.service 2>/dev/null || true
            rm -f "$service_dir/wt-web.service"
            success "Removed old wt-web.service"
            info "Run install.sh to set up set-web.service"
        fi
    fi

    # 5. Shell rc file: update PATH marker
    for rc_file in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
        [[ -f "$rc_file" ]] || continue
        if grep -q '# WT-TOOLS:PATH' "$rc_file"; then
            sed -i 's/# WT-TOOLS:PATH/# SET-CORE:PATH/' "$rc_file"
            success "Updated PATH marker in $rc_file"
        fi
    done

    # 6. shodh-memory project rename
    local old_mem="$HOME/.local/share/wt-memory/wt-tools"
    local new_mem="$HOME/.local/share/wt-memory/set-core"
    if [[ -d "$old_mem" ]]; then
        if [[ -d "$new_mem" ]]; then
            warn "Both $old_mem and $new_mem exist — skipping"
        else
            mv "$old_mem" "$new_mem"
            success "Moved memory data: wt-tools → set-core"
        fi
    fi

    success "Global migration complete!"
}

# ─── Main ────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
    echo "Usage: migrate-to-set.sh [OPTIONS] [PROJECT_DIR...]"
    echo ""
    echo "Migrate from wt-tools to SET (ShipExactlyThis)."
    echo ""
    echo "Options:"
    echo "  --global       Run global migration (config, data, symlinks, systemd)"
    echo "  --project DIR  Migrate a specific project directory"
    echo "  --all          Run global + migrate all registered projects"
    echo "  -h, --help     Show this help"
    echo ""
    echo "Examples:"
    echo "  migrate-to-set.sh --all              # Full migration"
    echo "  migrate-to-set.sh --global           # Global only"
    echo "  migrate-to-set.sh --project /path    # Single project"
    echo "  migrate-to-set.sh /path1 /path2      # Multiple projects"
}

do_global=false
do_all=false
projects=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --global)  do_global=true; shift ;;
        --all)     do_all=true; do_global=true; shift ;;
        --project) projects+=("$2"); shift 2 ;;
        -h|--help) usage; exit 0 ;;
        -*)        error "Unknown option: $1"; usage; exit 1 ;;
        *)         projects+=("$1"); shift ;;
    esac
done

if ! $do_global && ! $do_all && [[ ${#projects[@]} -eq 0 ]]; then
    error "No action specified. Use --all, --global, or provide project paths."
    usage
    exit 1
fi

echo ""
echo "================================"
echo "  SET Migration (wt-tools → set-core)"
echo "================================"
echo ""

if $do_global; then
    migrate_global
    echo ""
fi

if $do_all; then
    # Migrate all registered projects
    local_config="${XDG_CONFIG_HOME:-$HOME/.config}/set-core"
    # Also check old config location
    [[ ! -f "$local_config/projects.json" ]] && local_config="${XDG_CONFIG_HOME:-$HOME/.config}/wt-tools"

    if [[ -f "$local_config/projects.json" ]]; then
        while IFS= read -r project_path; do
            [[ -z "$project_path" ]] && continue
            [[ -d "$project_path" ]] && migrate_project "$project_path"
        done < <(jq -r '.projects // {} | to_entries[] | .value.path' "$local_config/projects.json" 2>/dev/null)
    else
        warn "No projects.json found — specify project paths manually"
    fi
fi

for p in "${projects[@]}"; do
    [[ -d "$p" ]] && migrate_project "$p" || warn "Directory not found: $p"
done

echo ""
echo "================================"
success "Migration complete!"
echo "================================"
echo ""
echo "Next steps:"
echo "  1. Run install.sh to set up new set-* symlinks"
echo "  2. Rename GitHub repos (manually on github.com):"
echo "     wt-tools → set-core"
echo "     wt-project-base → set-project-base"
echo "     wt-project-web → set-project-web"
echo "  3. Update git remotes:"
echo "     git remote set-url origin git@github.com:tatargabor/set-core.git"
echo ""
