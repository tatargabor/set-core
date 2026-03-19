## Why

`set-memory proactive` (used by all hook layers for memory recall) relies on shodh-memory's `proactive_context()` which uses pure semantic similarity scoring. This fails for short queries, non-English text, and abbreviated terms — queries like "levelibéka" or "mac alwaysontop" return 0 relevant results despite `recall --mode hybrid` finding them immediately. The hook layers silently inject nothing, making memory invisible when it should surface.

## What Changes

- Add hybrid recall fallback to `cmd_proactive` in `bin/set-memory`: when `proactive_context()` returns fewer results than requested (or all below threshold), run `recall --mode hybrid` as fallback and merge/deduplicate results
- Unify the scoring: assign synthetic relevance scores to hybrid fallback results so the hook's 0.3 filter can apply consistently
- No changes to hook code (`wt-hook-memory`) — the fix is entirely in the proactive command

## Capabilities

### New Capabilities
- `proactive-hybrid-fallback`: Hybrid recall fallback mechanism for `set-memory proactive` when semantic-only results are insufficient

### Modified Capabilities
- `smart-memory-recall`: The proactive recall pathway now includes a hybrid fallback, improving recall quality for short/non-English queries

## Impact

- `bin/set-memory` — `cmd_proactive` function (lines ~706-729)
- All hook layers benefit automatically (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStop) since they all call `set-memory proactive`
- No API changes — proactive still returns the same JSON format
