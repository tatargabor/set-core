# Proposal: Context-Aware Merge

## Problem

`wt-merge --llm-resolve` sends conflict hunks to Claude with zero context about what the branches implemented. The LLM prompt says "resolve these conflicts" but doesn't explain WHY each side made changes. Result: LLM guesses wrong, merge stays blocked, sentinel needs manual intervention.

Evidence from E2E runs:
- auth-system merge-blocked despite `--llm-resolve` being enabled
- Conflicts in `auth.ts`, `tailwind.config.ts` (delete/modify), `postcss.config` (rename) — all required manual resolution
- The orchestrator has full context (change scope, requirements, branch history) but doesn't pass it to wt-merge

## Solution

Enrich the merge LLM prompt with contextual information gathered dynamically:

1. **Change scope injection**: merger.py passes the change's scope/description to wt-merge via env var or flag
2. **Branch history**: wt-merge runs `git log --oneline source..target` to understand what each side did
3. **File role detection**: for each conflicted file, determine if it's config, component, test, or generated
4. **Delete/modify auto-resolve**: pattern-based rules for common conflict types that don't need LLM

## Scope

### In Scope
- merger.py passes change scope to wt-merge (env var `WT_MERGE_SCOPE`)
- wt-merge `llm_resolve_conflicts()` includes scope + branch history in prompt
- New `auto_resolve_structural_conflicts()` for delete/modify and rename patterns
- File role hints in LLM prompt based on path patterns

### Out of Scope
- Changing verify gate logic
- Cross-run learning from merge outcomes
- Interactive merge resolution UI
