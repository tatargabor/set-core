## Purpose

Migrate `lib/loop/prompt.sh` (305 LOC) to `lib/set_orch/loop_prompt.py`. Detects the next change action needed and assembles Claude prompts with context injection.

## Requirements

### PROMPT-01: Change Action Detection
- `detect_next_change_action(wt_path, target_change)` returns action type
- Return values: `ff:<change-name>`, `apply:<change-name>`, `done`, `none`
- Check: does tasks.md exist? All tasks complete? Change archived?
- For targeted changes: only inspect the specified change
- For untargeted: scan all changes in `openspec/changes/`

### PROMPT-02: Claude Prompt Assembly
- `build_claude_prompt(action, wt_path, config)` builds the full prompt
- Include: action instruction (ff or apply), change context, spec context
- Include: permission flags, model selection, timeout
- Output: list of CLI arguments for `claude` command

### PROMPT-03: Context Injection
- Inject relevant spec files into prompt when available
- Inject design.md and proposal.md for context
- Inject previous iteration summary if continuation
- Respect context size limits (truncate if needed)

### PROMPT-04: Unit Tests
- Test action detection with mock worktree structures (no tasks, partial tasks, all done, archived)
- Test prompt assembly output format
