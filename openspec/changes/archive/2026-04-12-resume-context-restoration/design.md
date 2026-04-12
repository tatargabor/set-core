# Design: Resume Context Restoration

## Current resume flow

```
Initial dispatch:
  dispatch_change()
    → builds full input.md (scope + design context + Figma source + rules + tests)
    → set-loop start "$task_desc"  (task_desc = "Implement {scope}")
    → claude --resume new session
  Agent reads input.md fully ✓

Retry (review fail / merge conflict / e2e fail):
  resume_change()
    → task_desc = retry_ctx ONLY  ← bug
    → set-loop start "$retry_ctx" --max 5
    → claude --resume continues PREVIOUS session
  Agent sees only fix instructions
  Conversation history may have been compacted
  Design context drift → wrong implementation
```

## New flow

```
Retry:
  resume_change()
    → task_desc = build_resume_preamble() + retry_ctx
    → set-loop start "$task_desc"
  Agent receives:
    1. "Re-read input.md, design.md, skeleton spec, rules"
    2. "Use exact design tokens, do not fall back to defaults"
    3. Original retry_ctx (the fix instructions)
```

## Implementation

In `lib/set_orch/dispatcher.py`, modify `resume_change()` (L2374-2389):

```python
if retry_ctx:
    preamble = _build_resume_preamble(change_name, wt_path)
    task_desc = preamble + "\n\n" + retry_ctx
    logger.info("resuming %s with retry context (%d chars + %d preamble)",
                change_name, len(retry_ctx), len(preamble))
    update_change_field(state_path, change_name, "retry_context", None)
    update_change_field(state_path, change_name, "current_step", "fixing")
    # ... existing logic
```

New helper function:

```python
def _build_resume_preamble(change_name: str, wt_path: str) -> str:
    """Build context restoration preamble for resume_change.
    
    Lists files the agent should re-read to refresh design/conventions/tests
    context that may have been lost from the conversation history.
    """
    parts = [
        "## Context Restoration",
        "",
        "Before fixing the issue below, RE-READ these files to refresh your context:",
        "",
    ]

    # Required files (always included)
    file_list = []
    input_md = f"openspec/changes/{change_name}/input.md"
    if os.path.isfile(os.path.join(wt_path, input_md)):
        file_list.append(f"1. `{input_md}` — original task scope, requirements, design context")

    design_md = f"openspec/changes/{change_name}/design.md"
    if os.path.isfile(os.path.join(wt_path, design_md)):
        file_list.append(f"2. `{design_md}` — design tokens and Figma source code")

    skeleton_spec = f"tests/e2e/{change_name}.spec.ts"
    if os.path.isfile(os.path.join(wt_path, skeleton_spec)):
        file_list.append(f"3. `{skeleton_spec}` — test skeleton (fill bodies, do NOT recreate structure)")

    # Convention rules
    rules_dir = os.path.join(wt_path, ".claude", "rules")
    if os.path.isdir(rules_dir):
        convention_files = [f for f in os.listdir(rules_dir) if f.endswith("-conventions.md")]
        if convention_files:
            file_list.append(f"4. `.claude/rules/{convention_files[0]}` — project conventions (UI library, styling)")

    parts.extend(file_list)
    parts.extend([
        "",
        "**Key reminders:**",
        "- Use EXACT design tokens from design.md — do NOT fall back to shadcn defaults",
        "- Follow the Figma source code structure for components (sidebar, layout, colors)",
        "- Keep the test skeleton structure intact — only fill in test bodies",
        "",
        "## Fix Required",
    ])

    return "\n".join(parts)
```

## Edge cases

1. **No design.md exists** (e.g., minishop has design-snapshot.md instead): only include files that exist
2. **No skeleton spec**: skip that line
3. **Multiple convention files**: include all (or first one with most matches)
4. **Plain Tailwind project (no shadcn)**: the "shadcn defaults" reminder is still useful — generic fallback warning
5. **Initial dispatch path unchanged**: the preamble is ONLY added on resume, not initial dispatch

## What can degrade between resumes (audit list)

This change addresses ALL of these:

| Item | Initial dispatch | Lost on resume? | Fix |
|------|------------------|-----------------|-----|
| Design Context (Figma source) | input.md L13+ | YES (compaction) | re-read input.md |
| Per-change design.md | path in input.md | YES | re-read design.md |
| Test skeleton | path in tasks.md | YES (agent may recreate) | re-read skeleton |
| Convention rules | `.claude/rules/` | maybe | re-read rules file |
| Required Tests (test plan) | input.md section | YES (long list compacted) | re-read input.md |
| Assigned Requirements | input.md AC list | YES | re-read input.md |
| Project knowledge | input.md | maybe | re-read input.md |
| Sibling context (related changes) | input.md | maybe | re-read input.md |

The single instruction "re-read input.md" covers most of these.

## Why a preamble (not full re-injection)

Alternative: re-inject the entire input.md at every resume.
- Pros: agent sees full context fresh
- Cons: massive token cost, defeats `claude --resume` cache benefit

The preamble approach:
- ~300 chars overhead per retry
- Forces agent to re-read files (cheap with cache)
- Triggers a fresh "design awareness" phase before the fix
