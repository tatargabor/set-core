#!/usr/bin/env bash
# set-project deploy functions: split from deploy_wt_tools() monolith
# Dependencies: set-common.sh must be sourced, SET_TOOLS_ROOT and SCRIPT_DIR must be set

# Runtime guards
[[ -n "${SCRIPT_DIR:-}" ]] || { echo "deploy.sh: SCRIPT_DIR not set" >&2; return 1; }
[[ -n "${SET_TOOLS_ROOT:-}" ]] || { echo "deploy.sh: SET_TOOLS_ROOT not set" >&2; return 1; }

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

# Clean up deprecated memory references from skill/command files
_cleanup_deprecated_memory_refs() {
    local project_path="$1"

    # Remove <!-- set-memory hooks --> blocks from SKILL.md files
    if [[ -d "$project_path/.claude/skills" ]]; then
        find "$project_path/.claude/skills" -name "SKILL.md" -type f 2>/dev/null | while read -r f; do
            if grep -q '<!-- set-memory hooks' "$f" 2>/dev/null; then
                if ! python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
# Remove all set-memory hooks blocks (including variants like hooks-midflow, hooks-remember, etc.)
cleaned = re.sub(r'<!--\s*set-memory hooks[^>]*-->.*?<!--\s*/set-memory hooks[^>]*-->\s*\n?', '', content, flags=re.DOTALL)
if cleaned != content:
    with open(sys.argv[1], 'w') as f:
        f.write(cleaned)
" "$f" 2>&1; then
                    warn "  Failed to clean up memory hooks in $f"
                fi
            fi
        done
    fi

    # Remove manual set-memory recall/remember instructions from command .md files
    # Exclude commands/set/ — those are set-core's own commands that legitimately use set-memory
    if [[ -d "$project_path/.claude/commands" ]]; then
        find "$project_path/.claude/commands" -name "*.md" -type f 2>/dev/null | while read -r f; do
            # Skip set-core command files (commands/set/*.md) — they use set-memory intentionally
            [[ "$f" == */commands/set/*.md ]] && continue
            if grep -qE 'set-memory (recall|remember)' "$f" 2>/dev/null; then
                if ! python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
# Remove lines containing set-memory recall or set-memory remember instructions
lines = content.split('\n')
cleaned_lines = [l for l in lines if not re.search(r'set-memory\s+(recall|remember)', l)]
cleaned = '\n'.join(cleaned_lines)
if cleaned != content:
    with open(sys.argv[1], 'w') as f:
        f.write(cleaned)
" "$f" 2>&1; then
                    warn "  Failed to clean up memory refs in $f"
                fi
            fi
        done
    fi

    # Delete .claude/hot-topics.json if it exists
    if [[ -f "$project_path/.claude/hot-topics.json" ]]; then
        rm -f "$project_path/.claude/hot-topics.json"
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

# Deploy /set:* and /opsx:* commands (copy)
_deploy_commands() {
    local project_path="$1"
    local claude_dir="$project_path/.claude"

    # /set:* commands
    local src_commands="$SET_TOOLS_ROOT/.claude/commands/set"
    local dst_commands="$claude_dir/commands/set"
    if [[ -d "$src_commands" ]]; then
        [[ -L "$dst_commands" ]] && rm -f "$dst_commands"
        mkdir -p "$dst_commands"
        if [[ "$(realpath "$src_commands")" != "$(realpath "$dst_commands")" ]]; then
            cp -r "$src_commands"/* "$dst_commands/"
        fi
        local cmd_count
        cmd_count=$(ls -1 "$src_commands"/*.md 2>/dev/null | wc -l)
        success "  Deployed $cmd_count command(s) to .claude/commands/set/"
    else
        warn "  Source commands not found: $src_commands"
    fi

    # /opsx:* commands
    local src_opsx_commands="$SET_TOOLS_ROOT/.claude/commands/opsx"
    local dst_opsx_commands="$claude_dir/commands/opsx"
    if [[ -d "$src_opsx_commands" ]]; then
        [[ -L "$dst_opsx_commands" ]] && rm -f "$dst_opsx_commands"
        mkdir -p "$dst_opsx_commands"
        if [[ "$(realpath "$src_opsx_commands")" != "$(realpath "$dst_opsx_commands")" ]]; then
            cp -r "$src_opsx_commands"/* "$dst_opsx_commands/"
        fi
        local opsx_cmd_count
        opsx_cmd_count=$(ls -1 "$src_opsx_commands"/*.md 2>/dev/null | wc -l)
        success "  Deployed $opsx_cmd_count command(s) to .claude/commands/opsx/"
    fi
}

# Deploy skills (set, openspec-*), rules, and agents
_deploy_skills() {
    local project_path="$1"
    local claude_dir="$project_path/.claude"

    # set skills
    local src_skills="$SET_TOOLS_ROOT/.claude/skills/set"
    local dst_skills="$claude_dir/skills/set"
    if [[ -d "$src_skills" ]]; then
        [[ -L "$dst_skills" ]] && rm -f "$dst_skills"
        mkdir -p "$dst_skills"
        if [[ "$(realpath "$src_skills")" != "$(realpath "$dst_skills")" ]]; then
            cp -r "$src_skills"/* "$dst_skills/"
        fi
        success "  Deployed skills to .claude/skills/set/"
    else
        warn "  Source skills not found: $src_skills"
    fi

    # openspec-* skills
    local openspec_skill_count=0
    for src_skill_dir in "$SET_TOOLS_ROOT/.claude/skills"/openspec-*/; do
        [[ -d "$src_skill_dir" ]] || continue
        local skill_name
        skill_name=$(basename "$src_skill_dir")
        local dst_skill_dir="$claude_dir/skills/$skill_name"
        [[ -L "$dst_skill_dir" ]] && rm -f "$dst_skill_dir"
        mkdir -p "$dst_skill_dir"
        if [[ "$(realpath "$src_skill_dir")" != "$(realpath "$dst_skill_dir")" ]]; then
            cp -r "$src_skill_dir"/* "$dst_skill_dir/"
            openspec_skill_count=$((openspec_skill_count + 1))
        fi
    done
    if [[ $openspec_skill_count -gt 0 ]]; then
        success "  Deployed $openspec_skill_count openspec skill(s) to .claude/skills/"
    fi

    # Rules (path-scoped)
    local src_rules="$SET_TOOLS_ROOT/.claude/rules"
    local dst_rules="$claude_dir/rules"
    if [[ -d "$src_rules" ]]; then
        local is_self=false
        if [[ -d "$dst_rules" ]] && [[ "$(realpath "$src_rules")" == "$(realpath "$dst_rules")" ]]; then
            is_self=true
        fi
        if [[ "$is_self" == "false" ]]; then
            local rule_count=0
            while IFS= read -r -d '' src_file; do
                local rel_path="${src_file#"$src_rules/"}"
                local dir_part
                dir_part=$(dirname "$rel_path")
                [[ "$dir_part" == gui ]] && continue  # gui/ rules are for set-core' own GUI, not consumer projects
                [[ "$dir_part" == web ]] && continue  # web/ rules come from set-project-web templates, not set-core
                local base_name
                base_name=$(basename "$rel_path")
                local dst_dir="$dst_rules"
                [[ "$dir_part" != "." ]] && dst_dir="$dst_rules/$dir_part"
                mkdir -p "$dst_dir"
                cp "$src_file" "$dst_dir/set-$base_name"
                rule_count=$((rule_count + 1))
            done < <(find "$src_rules" -name '*.md' -print0)
            success "  Deployed $rule_count rule(s) to .claude/rules/ (set-* prefix)"
        else
            success "  Rules: self-deploy detected, skipping"
        fi
    fi

    # Agents
    local src_agents="$SET_TOOLS_ROOT/.claude/agents"
    local dst_agents="$claude_dir/agents"
    if [[ -d "$src_agents" ]]; then
        [[ -L "$dst_agents" ]] && rm -f "$dst_agents"
        mkdir -p "$dst_agents"
        if [[ "$(realpath "$src_agents")" != "$(realpath "$dst_agents")" ]]; then
            cp "$src_agents"/*.md "$dst_agents/" 2>/dev/null || true
        fi
        local agent_count
        agent_count=$(ls -1 "$src_agents"/*.md 2>/dev/null | wc -l)
        success "  Deployed $agent_count agent(s) to .claude/agents/"
    fi
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

    # Remove deprecated inline memory hooks from OpenSpec skill/command files
    if command -v set-memory-hooks &>/dev/null; then
        (cd "$project_path" && set-memory-hooks remove --quiet) 2>/dev/null || true
    fi

    # Clean up deprecated memory references
    _cleanup_deprecated_memory_refs "$project_path"

    # Ensure CLAUDE.md has the Persistent Memory section
    local claude_md="$project_path/CLAUDE.md"
    local memory_marker="## Persistent Memory"
    if [[ ! -f "$claude_md" ]] || ! grep -q "$memory_marker" "$claude_md" 2>/dev/null; then
        local snippet
        snippet=$(cat << 'MEMORY_SNIPPET'

## Persistent Memory
<!-- set-core:managed — DO NOT edit or remove this section. It is auto-generated by `set-project init`. -->

This project uses persistent memory (shodh-memory) across sessions. Memory context is automatically injected into `<system-reminder>` tags in your conversation — **you MUST read and use this context**.

**IMPORTANT — On EVERY prompt, follow these steps:**
1. **Scan** `<system-reminder>` tags for "PROJECT MEMORY", "PROJECT CONTEXT", or "MEMORY: Context for this command"
2. **Match** — check if any injected memory directly answers the user's question or provides a known fix
3. **Cite** — if a match is found, use it: "From memory: ..." — do NOT re-investigate problems with known solutions in memory
4. **Proceed** — only after checking memory context, do independent research

**This applies to every turn, not just the first one.**

**How it works:**
- Session start → relevant memories loaded as system-reminder
- Every prompt → topic-based recall injected as system-reminder
- After Read/Bash → relevant past experience injected as system-reminder
- Tool errors → past fixes surfaced automatically
- Session end → raw conversation filter extracts and saves insights

**Active (MCP tools):** You also have MCP memory tools available (`remember`, `recall`, `proactive_context`, etc.) for deeper memory interactions when automatic context isn't enough.

**Emphasis (use sparingly):**
- `echo "<insight>" | set-memory remember --type <Decision|Learning|Context> --tags source:user,<topic>` — mark something as HIGH IMPORTANCE
- `set-memory forget <id>` — suppress or correct a wrong memory
- Most things are remembered automatically. Only use `remember` for emphasis.
MEMORY_SNIPPET
)
        if [[ -f "$claude_md" ]]; then
            echo "$snippet" >> "$claude_md"
        else
            echo "${snippet#$'\n'}" > "$claude_md"
        fi
        success "  Added Persistent Memory section to CLAUDE.md"
    elif ! grep -q '1\. \*\*Scan\*\*' "$claude_md" 2>/dev/null; then
        # Upgrade old IMPORTANT paragraph to numbered action list
        python3 -c "
import re, sys
path = sys.argv[1]
with open(path) as f:
    content = f.read()
# Match old single-paragraph IMPORTANT block
old_pattern = r'\*\*IMPORTANT:.*?This applies to every turn, not just the first one\.\*\*'
new_text = '''**IMPORTANT — On EVERY prompt, follow these steps:**
1. **Scan** \`<system-reminder>\` tags for \"PROJECT MEMORY\", \"PROJECT CONTEXT\", or \"MEMORY: Context for this command\"
2. **Match** — check if any injected memory directly answers the user's question or provides a known fix
3. **Cite** — if a match is found, use it: \"From memory: ...\" — do NOT re-investigate problems with known solutions in memory
4. **Proceed** — only after checking memory context, do independent research

**This applies to every turn, not just the first one.**'''
result = re.sub(old_pattern, new_text, content, count=1, flags=re.DOTALL)
if result != content:
    with open(path, 'w') as f:
        f.write(result)
" "$claude_md" 2>/dev/null || true
        success "  Updated Persistent Memory citation instruction in CLAUDE.md"
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

    # Auto-import memory seeds if memory store is empty and seed file exists
    local seed_file="$project_path/wt/knowledge/memory-seed.yaml"
    if [[ -f "$seed_file" ]] && command -v set-memory &>/dev/null; then
        local mem_count
        mem_count=$(cd "$project_path" && set-memory list --limit 1 2>/dev/null | grep -c "^[0-9a-f]" || true)
        if [[ "$mem_count" -eq 0 ]]; then
            (cd "$project_path" && set-memory seed 2>/dev/null) && \
                success "  Auto-imported memory seeds from wt/knowledge/memory-seed.yaml" || \
                warn "  Failed to import memory seeds"
        fi
    fi
}
