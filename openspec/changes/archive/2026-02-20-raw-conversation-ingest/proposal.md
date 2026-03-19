## Why

The Stop handler's Haiku LLM extraction loses information (only last 80 entries, compressed to 5-9 insights) and costs ~$0.001/session with 2-5s latency. Meanwhile, PreToolUse hooks fire on every tool call (~50/session) adding ~25s cumulative overhead for marginal value since PostToolUse timing is more useful. PostToolUse saves noisy "Modified FILE" memories that pollute recall results.

## What Changes

- **Stop handler**: Replace Haiku LLM transcript extraction with rule-based raw conversation filter that saves all meaningful user+assistant pairs directly via `set-memory remember` with `raw` tag
- **PreToolUse**: Remove memory recall hooks entirely (keep activity-track.sh for Skill matcher)
- **PostToolUse**: Remove "Modified FILE" memory saves, remove proactive recall, keep only for Read + Bash tools
- **PostToolUse**: Keep error tracking in PostToolUseFailure (unchanged)
- **settings.json**: Update hook matchers to reflect reduced PreToolUse/PostToolUse scope
- **Recall side**: Hook injections exclude `raw`-tagged memories by default; raw memories available for deep search

## Capabilities

### New Capabilities
- `raw-transcript-filter`: Rule-based transcript filter replacing Haiku LLM extraction — processes full JSONL transcript, applies word-count/pattern filters, saves meaningful turns with `raw` tag and context prefix

### Modified Capabilities
- `unified-memory-hook`: Remove PreToolUse memory recall, simplify PostToolUse to Read+Bash only without proactive recall or "Modified" saves
- `save-hook-staging`: Replace `_stop_extract_from_transcript()` Haiku flow with raw filter; remove staging/debounce (no longer needed without LLM)
- `posttool-memory-surfacing`: Reduce scope from 6 tool matchers to 2 (Read, Bash), remove write-side saves

## Impact

- **bin/wt-hook-memory**: Major rewrite of `handle_stop()`, `handle_pre_tool()`, `handle_post_tool()` functions
- **.claude/settings.json**: Remove PreToolUse matchers for Read/Edit/Write/Bash/Task/Grep; reduce PostToolUse to Read+Bash only
- **Memory DB**: Higher volume of `raw`-tagged memories (~15-25/session vs 5-9 curated); offset by better recall filtering
- **Recall hooks**: Must add `--exclude-tags raw` or equivalent to prevent noise in injection results
- **No external dependencies changed**: shodh-memory API used as-is, no Haiku/LLM dependency
