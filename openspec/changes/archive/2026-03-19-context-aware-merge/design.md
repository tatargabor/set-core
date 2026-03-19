# Design: Context-Aware Merge

## Architecture

### Current flow (context-free)
```
merger.py → wt-merge --llm-resolve change-name
  → git merge → conflicts
  → llm_resolve_conflicts(hunks_only)
  → Claude: "resolve these" (no context)
  → often fails → merge-blocked
```

### New flow (context-aware)
```
merger.py → WT_MERGE_SCOPE="..." wt-merge --llm-resolve change-name
  → git merge → conflicts
  → auto_resolve_structural_conflicts()    ← NEW: delete/modify, rename
  → if remaining conflicts:
      gather_merge_context()               ← NEW: branch history, file roles
      llm_resolve_conflicts(hunks + context)
      → Claude: "source branch implemented auth, resolve accordingly"
```

## Component Changes

### 1. merger.py — Pass scope via environment

```python
# In merge_change(), before calling wt-merge:
scope = change.scope or ""
env = dict(os.environ)
env["WT_MERGE_SCOPE"] = scope[:2000]  # truncate for safety
merge_result = run_command(
    ["wt-merge", change_name, "--no-push", "--llm-resolve"],
    timeout=600, env=env,
)
```

### 2. wt-merge — Structural conflict auto-resolve (pre-LLM)

New function called BEFORE `llm_resolve_conflicts`:

```bash
auto_resolve_structural_conflicts() {
    local conflicted_files="$1"
    local resolved=0

    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        local status
        status=$(git status --porcelain "$file" 2>/dev/null | head -1)

        [[ -z "$status" ]] && continue  # empty status = special conflict state, skip

        case "$status" in
            # DU = HEAD (main) deleted, feature modified → keep feature's version
            # UD = feature deleted, HEAD (main) modified → accept feature's deletion
            # Verified with actual git status --porcelain output:
            #   DU = "deleted in HEAD and modified in feature"
            #   UD = "deleted in feature and modified in HEAD"
            DU*)
                # Main deleted, feature modified → keep feature (they implemented something)
                git checkout --theirs "$file" 2>/dev/null && git add "$file"
                resolved=$((resolved + 1))
                info "Auto-resolved DU (keep feature): $file"
                ;;
            UD*)
                # Feature deleted, main modified → accept feature's deletion
                git rm "$file" 2>/dev/null
                resolved=$((resolved + 1))
                info "Auto-resolved UD (accept deletion): $file"
                ;;
                resolved=$((resolved + 1))
                info "Auto-resolved delete/modify: $file"
                ;;
            # Rename conflicts in tmp/, .claude/, generated dirs
            *)
                if [[ "$file" == tmp/* || "$file" == .claude/* ]]; then
                    git checkout --theirs "$file" 2>/dev/null && git add "$file"
                    resolved=$((resolved + 1))
                    info "Auto-resolved runtime file: $file"
                fi
                ;;
        esac
    done <<< "$conflicted_files"

    return $((resolved > 0 ? 0 : 1))
}
```

### 3. wt-merge — Context-enriched LLM prompt

Modify `llm_resolve_conflicts()` to include:

```bash
# Read scope from environment (set by merger.py)
local scope="${WT_MERGE_SCOPE:-}"

# Gather branch history
local source_log target_log
source_log=$(git log --oneline "$target_branch..$source_branch" 2>/dev/null | head -10)
target_log=$(git log --oneline "$source_branch..$target_branch" 2>/dev/null | head -10)

# Build context section
local context=""
if [[ -n "$scope" ]]; then
    context+="
CONTEXT — What the source branch implemented:
$scope

Source branch commits:
$source_log

Target branch recent commits:
$target_log

RESOLUTION STRATEGY:
- The source branch is a FEATURE being merged into main
- Prefer source branch changes for feature-specific code
- Keep both sides for additive changes (imports, config entries)
- For config files: use target (main) as base, add source's additions
"
fi
```

### 4. File role hints (extend existing `get_llm_hint`)

`wt-merge` already has `get_llm_hint()` (line 866) reading from `STRATEGY_LLM_HINTS[]`.
Instead of adding a new function, extend `get_llm_hint` with a fallback: if no
strategy hint exists, return a path-based default hint.

```bash
# In get_llm_hint(), after checking STRATEGY_LLM_HINTS:
if [[ -z "$hint" ]]; then
    # Fallback: path-based role hints
    case "$file" in
        *.test.* | *.spec.* | __tests__/*) hint="TEST file — prefer source (feature tests)" ;;
        prisma/* | *.prisma) hint="DATABASE SCHEMA — merge both model definitions" ;;
        src/app/* | src/pages/*) hint="PAGE/ROUTE — prefer source (new feature page)" ;;
        *.config.* | next.config.* | tailwind.*) hint="CONFIG — use target as base, add source's new entries" ;;
        *) ;;
    esac
fi
```

This avoids duplication — strategy hints take priority, path-based hints are fallback.

## Decision Log

- **Scope via env var** (not CLI flag): simpler, no wt-merge interface change, merger.py already has scope
- **Structural auto-resolve before LLM**: saves tokens, handles cases LLM can't (delete/modify)
- **File role hints**: lightweight, pattern-based, no LLM call needed
- **Branch history in prompt**: gives LLM temporal context about what happened
