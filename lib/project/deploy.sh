#!/usr/bin/env bash
# set-project deploy functions: split from deploy_wt_tools() monolith
# Dependencies: set-common.sh must be sourced, SET_TOOLS_ROOT and SCRIPT_DIR must be set

# Runtime guards
[[ -n "${SCRIPT_DIR:-}" ]] || { echo "deploy.sh: SCRIPT_DIR not set" >&2; return 1; }
[[ -n "${SET_TOOLS_ROOT:-}" ]] || { echo "deploy.sh: SET_TOOLS_ROOT not set" >&2; return 1; }

# Provenance ledger — guards every copy below against clobbering consumer edits.
source "$SET_TOOLS_ROOT/lib/project/deploy_provenance.sh"

# Register set-core MCP server for given project paths
_register_mcp_server() {
    if ! command -v claude &>/dev/null; then
        return 0  # claude CLI not available, skip
    fi
    local mcp_server_dir="$SET_TOOLS_ROOT/mcp-server"
    [[ -d "$mcp_server_dir" ]] || return 0
    local had_failure=0
    for reg_path in "$@"; do
        [[ -d "$reg_path" ]] || continue
        # Remove old server names (may not exist — stderr suppressed intentionally)
        (cd "$reg_path" && claude mcp remove set-memory 2>/dev/null; claude mcp remove set-core 2>/dev/null) || true
        # Register — capture errors, do NOT suppress stderr
        local mcp_err
        mcp_err=$(cd "$reg_path" && claude mcp add set-core -- env CLAUDE_PROJECT_DIR="$reg_path" uv --directory "$mcp_server_dir" run python set_mcp_server.py 2>&1)
        if [[ $? -ne 0 ]]; then
            warn "  MCP registration failed for $reg_path: $mcp_err"
            had_failure=1
        fi
    done
    if [[ $had_failure -eq 0 ]]; then
        success "  Registered set-core MCP server"
    fi
    return $had_failure
}

# Strip one deprecated-memory pattern from a file set-core owns.
#   $1 project-relative key   $2 file   $3 mode: "block" | "line"   $4 human label
#
# Ownership is decided by the provenance ledger, never by the content: a file whose
# hash still matches what we deployed is ours to migrate; anything else is the
# project's and is left exactly as found, even when it matches the pattern. The old
# implementation edited every match it found — including hand-authored command files
# the consumer wrote itself, with no backup and no report.
#
# Rewrites the ledger hash after a successful edit. Without that the very next deploy
# would read its own change as "modified by the project" and skip the file forever.
_pv_strip_memory_refs() {
    local key="$1" file="$2" mode="$3" label="$4"
    local removed

    if ! _pv_is_ours "$key" "$file"; then
        warn "    Left $key untouched — $label present but the file is project-owned"
        return 0
    fi

    removed=$(python3 -c "
import re, sys

path, mode, dry = sys.argv[1], sys.argv[2], sys.argv[3] == 'true'
with open(path) as fh:
    content = fh.read()

if mode == 'block':
    # The markers set-core actually wrote are `start`/`end` comments, not a
    # closing `/set-memory` tag. A regex demanding the slash matched nothing,
    # so this migration reported success while removing zero blocks and the
    # unguarded external tool was doing the real work. Both spellings are
    # accepted now; only the first has ever been emitted.
    cleaned = re.sub(
        r'<!--\s*set-memory hooks\s+start[^>]*-->.*?<!--\s*set-memory hooks\s+end[^>]*-->\s*\n?',
        '', content, flags=re.DOTALL,
    )
    cleaned = re.sub(
        r'<!--\s*set-memory hooks[^>]*-->.*?<!--\s*/set-memory hooks[^>]*-->\s*\n?',
        '', cleaned, flags=re.DOTALL,
    )
    removed = 0 if cleaned == content else content.count('<!-- set-memory hooks')
else:
    lines = content.split('\n')
    kept = [l for l in lines if not re.search(r'set-memory\s+(recall|remember)', l)]
    removed = len(lines) - len(kept)
    cleaned = '\n'.join(kept)

if cleaned != content and not dry:
    with open(path, 'w') as fh:
        fh.write(cleaned)
print(removed)
" "$file" "$mode" "${DRY_RUN:-false}" 2>/dev/null) || {
        warn "    Failed to clean $label in $key"
        return 0
    }

    [[ "${removed:-0}" -gt 0 ]] || return 0

    if [[ "${DRY_RUN:-false}" == "true" ]]; then
        info "    Would remove $removed deprecated $label line(s) from $key"
    else
        warn "    Removed $removed deprecated $label line(s) from $key"
        _pv_record "$key" "$file"
    fi
}

# Clean up deprecated memory references from files SET-CORE DEPLOYED.
#
# This is a migration pass, not a linter: it exists to retire an inline-instruction
# format set-core itself shipped, now superseded by the settings.json hook layer. It
# therefore has no business touching a file the project wrote — and until the
# provenance ledger existed it could not tell the difference. It edited every
# `.claude/commands/**/*.md` outside `commands/set/`, project-authored files included.
_cleanup_deprecated_memory_refs() {
    local project_path="$1"
    local f key

    _pv_begin "$project_path"

    # Inline hook blocks in skills set-core deployed (openspec-*, set).
    if [[ -d "$project_path/.claude/skills" ]]; then
        while IFS= read -r -d '' f; do
            grep -q '<!-- set-memory hooks' "$f" 2>/dev/null || continue
            key="${f#"$project_path"/}"
            _pv_strip_memory_refs "$key" "$f" block "memory-hook block"
        done < <(find "$project_path/.claude/skills" -name "SKILL.md" -type f -print0 2>/dev/null)
    fi

    # Command files carry the same deprecated content in two shapes: a marked
    # block (what the old installer wrote) and bare instruction lines. Marked
    # blocks are removed whole — stripping only the matching lines would leave
    # the `start`/`end` comments behind, and a later pass would then see a block
    # marker with nothing in it.
    #
    # `commands/set/*` is skipped by intent: those are set-core's own commands and
    # they call set-memory deliberately.
    if [[ -d "$project_path/.claude/commands" ]]; then
        while IFS= read -r -d '' f; do
            [[ "$f" == */commands/set/*.md ]] && continue
            key="${f#"$project_path"/}"
            if grep -q '<!-- set-memory hooks' "$f" 2>/dev/null; then
                _pv_strip_memory_refs "$key" "$f" block "memory-hook block"
            elif grep -qE 'set-memory (recall|remember)' "$f" 2>/dev/null; then
                _pv_strip_memory_refs "$key" "$f" line "set-memory instruction"
            fi
        done < <(find "$project_path/.claude/commands" -name "*.md" -type f -print0 2>/dev/null)
    fi

    _pv_end

    # set-core's own cache artifact — no consumer content, safe to drop, still reported.
    if [[ -f "$project_path/.claude/hot-topics.json" ]]; then
        if [[ "${DRY_RUN:-false}" == "true" ]]; then
            info "    Would remove .claude/hot-topics.json (superseded set-core cache)"
        else
            rm -f "$project_path/.claude/hot-topics.json"
            info "    Removed .claude/hot-topics.json (superseded set-core cache)"
        fi
    fi
}

# Deploy hooks via set-deploy-hooks
_deploy_hooks() {
    local project_path="$1"
    if "$SCRIPT_DIR/set-deploy-hooks" --quiet "$project_path"; then
        success "  Deployed hooks to .claude/settings.json"
    else
        warn "  Failed to deploy hooks to .claude/settings.json"
        return 1
    fi
}

# Deploy /set:* and /opsx:* commands.
# Every copy goes through the provenance guard: a command the project edited is kept,
# an untouched one receives the framework update. See deploy_provenance.sh.
_deploy_commands() {
    local project_path="$1"
    local claude_dir="$project_path/.claude"

    _pv_begin "$project_path"

    # /set:* commands
    local src_commands="$SET_TOOLS_ROOT/.claude/commands/set"
    local dst_commands="$claude_dir/commands/set"
    if [[ -d "$src_commands" ]]; then
        _pv_deploy_tree "$src_commands" "$dst_commands" "$project_path"
        success "  $(_pv_verb) ${_PV_DEPLOYED:-0} command(s) to .claude/commands/set/"
    else
        warn "  Source commands not found: $src_commands"
    fi

    # /opsx:* commands
    local src_opsx_commands="$SET_TOOLS_ROOT/.claude/commands/opsx"
    local dst_opsx_commands="$claude_dir/commands/opsx"
    local before="${_PV_DEPLOYED:-0}"
    if [[ -d "$src_opsx_commands" ]]; then
        _pv_deploy_tree "$src_opsx_commands" "$dst_opsx_commands" "$project_path"
        success "  $(_pv_verb) $(( ${_PV_DEPLOYED:-0} - before )) command(s) to .claude/commands/opsx/"
    fi

    _pv_report_skips "Commands"
    _pv_end
}

# Deploy skills (set, openspec-*), rules, and agents.
# Provenance-guarded throughout — see _deploy_commands and deploy_provenance.sh.
_deploy_skills() {
    local project_path="$1"
    local claude_dir="$project_path/.claude"

    _pv_begin "$project_path"

    # set skills
    local src_skills="$SET_TOOLS_ROOT/.claude/skills/set"
    local dst_skills="$claude_dir/skills/set"
    if [[ -d "$src_skills" ]]; then
        _pv_deploy_tree "$src_skills" "$dst_skills" "$project_path"
        success "  $(_pv_verb) ${_PV_DEPLOYED:-0} skill file(s) to .claude/skills/set/"
    else
        warn "  Source skills not found: $src_skills"
    fi

    # openspec-* skills
    local openspec_skill_count=0
    for src_skill_dir in "$SET_TOOLS_ROOT/.claude/skills"/openspec-*/; do
        [[ -d "$src_skill_dir" ]] || continue
        local skill_name
        skill_name=$(basename "$src_skill_dir")
        _pv_deploy_tree "${src_skill_dir%/}" "$claude_dir/skills/$skill_name" "$project_path"
        openspec_skill_count=$((openspec_skill_count + 1))
    done
    if [[ $openspec_skill_count -gt 0 ]]; then
        success "  Processed $openspec_skill_count openspec skill(s) in .claude/skills/"
    fi

    # Core rules (from templates/core/rules/ — explicit deploy source)
    # Skip when deploying to set-core itself (rules already exist without prefix)
    local src_rules="$SET_TOOLS_ROOT/templates/core/rules"
    local dst_rules="$claude_dir/rules"
    if [[ -d "$src_rules" ]]; then
        local is_self=false
        local target_git_root
        target_git_root=$(git -C "$(dirname "$claude_dir")" rev-parse --show-toplevel 2>/dev/null || true)
        if [[ -n "$target_git_root" ]] && [[ "$(realpath "$target_git_root" 2>/dev/null)" == "$(realpath "$SET_TOOLS_ROOT" 2>/dev/null)" ]]; then
            is_self=true
        fi
        if [[ "$is_self" == "false" ]] && _pv_prepare_dir "$src_rules" "$dst_rules"; then
            local rules_before="${_PV_DEPLOYED:-0}"
            local rule_count=0
            while IFS= read -r -d '' src_file; do
                local base_name dst_rule
                base_name=$(basename "$src_file")
                dst_rule="$dst_rules/set-$base_name"
                _pv_deploy_file "${dst_rule#"$project_path"/}" "$src_file" "$dst_rule"
                rule_count=$((rule_count + 1))
            done < <(find "$src_rules" -maxdepth 1 -name '*.md' -print0)
            if [[ $rule_count -gt 0 ]]; then
                success "  $(_pv_verb) $(( ${_PV_DEPLOYED:-0} - rules_before )) core rule(s) to .claude/rules/ (set-* prefix)"
            fi
        else
            success "  Rules: self-deploy detected, skipping"
        fi
    fi

    # Agents. These deploy by bare basename into a shared directory, so a project agent
    # named like one of ours (e.g. code-reviewer.md) collides head-on. The provenance
    # guard is what keeps the project's version — renaming ours would break every
    # existing deployment that already references the current names.
    local src_agents="$SET_TOOLS_ROOT/.claude/agents"
    local dst_agents="$claude_dir/agents"
    if [[ -d "$src_agents" ]] && _pv_prepare_dir "$src_agents" "$dst_agents"; then
        local agents_before="${_PV_DEPLOYED:-0}"
        local agent_count=0
        local src_agent dst_agent
        for src_agent in "$src_agents"/*.md; do
            [[ -f "$src_agent" ]] || continue
            dst_agent="$dst_agents/$(basename "$src_agent")"
            _pv_deploy_file "${dst_agent#"$project_path"/}" "$src_agent" "$dst_agent"
            agent_count=$((agent_count + 1))
        done
        if [[ $agent_count -gt 0 ]]; then
            success "  $(_pv_verb) $(( ${_PV_DEPLOYED:-0} - agents_before )) agent(s) to .claude/agents/"
        fi
    fi

    _pv_report_skips "Skills/rules/agents"
    _pv_end
}

# Deploy MCP server registration
_deploy_mcp() {
    local project_path="$1"
    shift
    _register_mcp_server "$project_path" "$@"
}

# Deploy memory-related setup: clean deprecated refs, CLAUDE.md sections, seed import
_deploy_memory() {
    local project_path="$1"
    local claude_dir="$project_path/.claude"

    # Deprecated inline memory hooks are retired by _cleanup_deprecated_memory_refs
    # below, and by nothing else. The deploy used to ALSO shell out to
    # `set-memory-hooks remove` here; that call is gone, and its absence is the point:
    #
    #   - it resolved its own target with `git rev-parse --show-toplevel`, so deploying
    #     into a directory that is not its own repository root walked UP and edited an
    #     ancestor repository's `.claude/` — files outside the deploy target entirely;
    #   - it had no notion of ownership, so a SKILL.md the project wrote itself was
    #     edited exactly like one set-core deployed.
    #
    # The in-process pass has neither problem: it is scoped to $project_path by path,
    # never by git, and every edit goes through the provenance ledger. `set-memory-hooks`
    # remains available as a CLI — run deliberately by a person, which is consent the
    # deploy cannot give on their behalf.
    _cleanup_deprecated_memory_refs "$project_path"

    # Ensure CLAUDE.md has the Persistent Memory section
    local claude_md="$project_path/CLAUDE.md"
    local memory_marker="## Persistent Memory"
    local snippet
    snippet=$(cat << 'MEMORY_SNIPPET'

## Persistent Memory
<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by `set-project init`. -->

This project uses Claude Code's own per-repository memory: Markdown files under
`~/.claude/projects/<project-slug>/memory/`, indexed by `MEMORY.md`.

**How it actually loads — the limit matters:**
- Only the **first 200 lines, or 25 KB**, of `MEMORY.md` are injected at session start.
  Content past that cut loads for nobody, and nothing warns you. Keep the index to one
  line per memory.
- The individual topic files are **not** loaded at startup. Read them with ordinary file
  tools when the index says one is relevant.
- Use `/memory` to browse and edit, `/context` to see what actually loaded this session.

**What it does NOT do**, so you reach for a documented absence rather than a missing
feature: no semantic search, no tag filtering, no temporal queries, no full-text search,
no cross-device sync, no version history, and no automatic session-end extraction.
Searching means reading the index and opening the file it points at.

**Writing a memory:** one fact per file, with a `name`, a one-line `description`, and a
`type` of user / feedback / project / reference. Add a one-line pointer to `MEMORY.md`.
Never store a harness artifact verbatim — a task notification, another agent's prompt, a
transcript fragment — and never record a claim about the user's emotional state.

**Confidentiality:** no memory file may carry a consumer project name, a partner name, a
personal name, or content derived from a customer's data. Generalise before saving; a
memory naming a real entity is a defect to correct, not harmless content.
MEMORY_SNIPPET
)
    if [[ ! -f "$claude_md" ]] || ! grep -q "$memory_marker" "$claude_md" 2>/dev/null; then
        if [[ -f "$claude_md" ]]; then
            echo "$snippet" >> "$claude_md"
        else
            echo "${snippet#$'\n'}" > "$claude_md"
        fi
        success "  Added Persistent Memory section to CLAUDE.md"
    elif grep -q 'shodh-memory\|PROJECT MEMORY' "$claude_md" 2>/dev/null; then
        # A stale Persistent Memory section describes the REMOVED subsystem. It tells the
        # session, on every prompt, to scan for an injected block that nothing emits any
        # more — a wrong instruction outlives wrong code, because the code stops running
        # and the instruction keeps being followed. Drop the stale section; the next line
        # writes the current one, so a single run converges.
        python3 - "$claude_md" << 'UPGRADE_PY' 2>/dev/null || true
import re, sys
path = sys.argv[1]
with open(path) as f:
    content = f.read()
# The section runs from its own heading to the next top-level heading, or EOF.
m = re.search(r'## Persistent Memory\n.*?(?=\n## |\Z)', content, flags=re.DOTALL)
if m and ('shodh' in m.group(0) or 'PROJECT MEMORY' in m.group(0)):
    with open(path, 'w') as f:
        f.write((content[:m.start()] + content[m.end():]).rstrip() + '\n')
UPGRADE_PY
        if ! grep -q "$memory_marker" "$claude_md" 2>/dev/null; then
            printf '%s\n' "$snippet" >> "$claude_md"
            success "  Replaced stale Persistent Memory section in CLAUDE.md (it described the removed subsystem)"
        fi
    fi

    # Ensure managed markers are present (upgrade path for existing deployments)
    local managed_marker="set-core:managed"
    if [[ -f "$claude_md" ]] && grep -q "$memory_marker" "$claude_md" 2>/dev/null && ! grep -q "$managed_marker" "$claude_md" 2>/dev/null; then
        sed -i "s|^## Persistent Memory$|## Persistent Memory\n<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by \`set-project init\`. -->|" "$claude_md"
        sed -i "s|^## Auto-Commit After Apply$|## Auto-Commit After Apply\n<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by \`set-project init\`. -->|" "$claude_md"
        success "  Added managed markers to CLAUDE.md sections"
    fi

    # Ensure CLAUDE.md has the Auto-Commit After Apply section
    local commit_marker="## Auto-Commit After Apply"
    if [[ -f "$claude_md" ]] && ! grep -q "$commit_marker" "$claude_md" 2>/dev/null; then
        local commit_snippet
        commit_snippet=$(cat << 'COMMIT_SNIPPET'

## Auto-Commit After Apply
<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by `set-project init`. -->

After a skill-driven apply (e.g. `/opsx:apply`) finishes or pauses, automatically commit all changes. Follow the standard commit flow (stage relevant files, write a concise commit message).
COMMIT_SNIPPET
)
        echo "$commit_snippet" >> "$claude_md"
        success "  Added Auto-Commit After Apply section to CLAUDE.md"
    fi

    # Ensure CLAUDE.md has the Getting Started reference to START.md
    local start_marker="## Getting Started"
    if [[ -f "$claude_md" ]] && ! grep -q "$start_marker" "$claude_md" 2>/dev/null; then
        local start_snippet
        start_snippet=$(cat << 'START_SNIPPET'

## Getting Started
<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by `set-project init`. -->

See [START.md](START.md) for application startup commands (install, dev server, database, tests).
START_SNIPPET
)
        echo "$start_snippet" >> "$claude_md"
        success "  Added Getting Started reference to CLAUDE.md"
    fi

    # Generate smoke E2E test from project-type plugin (if available)
    if command -v python3 &>/dev/null; then
        local smoke_content
        smoke_content=$(cd "$project_path" && python3 -c "
from set_orch.profile_loader import load_profile
p = load_profile('.')
content = p.generate_smoke_e2e('.')
if content:
    print(content)
" 2>/dev/null) || true
        if [[ -n "$smoke_content" ]]; then
            mkdir -p "$project_path/e2e"
            echo "$smoke_content" > "$project_path/e2e/smoke-routes.spec.ts"
            success "  Generated e2e/smoke-routes.spec.ts from project-type plugin"
        fi
    fi

    # Auto-import memory seeds if memory store is empty and seed file exists
    local seed_file="$project_path/set/knowledge/memory-seed.yaml"
    if [[ -f "$seed_file" ]] && command -v set-memory &>/dev/null; then
        local mem_count
        mem_count=$(cd "$project_path" && set-memory list --limit 1 2>/dev/null | grep -c "^[0-9a-f]" || true)
        if [[ "$mem_count" -eq 0 ]]; then
            (cd "$project_path" && set-memory seed 2>/dev/null) && \
                success "  Auto-imported memory seeds from set/knowledge/memory-seed.yaml" || \
                warn "  Failed to import memory seeds"
        fi
    fi
}
