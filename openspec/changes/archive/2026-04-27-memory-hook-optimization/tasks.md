# Tasks: Memory Hook Optimization

## 1. Hook mode environment variable

- [x] 1.1 Add `HOOK_MODE` constant to `lib/set_hooks/util.py` that reads `SET_MEMORY_HOOKS` env var, defaulting to `"lite"` [REQ: hook-mode-environment-variable]
- [x] 1.2 Add early-return guard in `handle_post_tool()` — return None if mode is not `full` [REQ: hook-mode-environment-variable]
- [x] 1.3 Add early-return guard in `handle_post_tool_failure()` — return None if mode is not `full` [REQ: hook-mode-environment-variable]
- [x] 1.4 Add early-return guard in `handle_subagent_start()` — return None if mode is not `full` [REQ: hook-mode-environment-variable]
- [x] 1.5 Add early-return guard in `handle_subagent_stop()` — return None if mode is not `full` [REQ: hook-mode-environment-variable]
- [x] 1.6 Add early-return in `handle_session_start()` and `handle_user_prompt()` — return None if mode is `off` [REQ: hook-mode-environment-variable]
- [x] 1.7 Ensure `handle_stop()` always executes regardless of mode (transcript extraction, commit save, metrics flush) [REQ: hook-mode-environment-variable]

## 2. Relevance threshold and limits

- [x] 2.1 Change `MIN_RELEVANCE` from 0.3 to 0.55 in `lib/set_hooks/memory_ops.py` [REQ: relevance-threshold-filtering]
- [x] 2.2 Change `proactive_context` limit from 5 to 3 in `handle_session_start()` [REQ: reduced-injection-limits]
- [x] 2.3 Change `proactive_context` limit from 5 to 3 in `handle_user_prompt()` [REQ: reduced-injection-limits]
- [x] 2.4 Change `recall_memories` limit from 3 to 2 in `handle_post_tool_failure()` [REQ: reduced-injection-limits]

## 3. Content-based dedup

- [x] 3.1 Add `_content_seen` set (session-level) in `memory_ops.py` using `md5(content[:100])` as key [REQ: content-based-dedup]
- [x] 3.2 Check `_content_seen` in `_format_memories()` before including a memory — skip if hash already seen [REQ: content-based-dedup]
- [x] 3.3 Add `clear_content_seen()` function, call it from `dedup_clear()` in session.py [REQ: content-based-dedup]

## 4. Display truncation and token budget

- [x] 4.1 Truncate displayed content to 300 chars + "..." in `_format_memories()` line 289 (change `{c}` to `{c[:300]}...` when len > 300) [REQ: display-content-truncation]
- [x] 4.2 Add token budget tracking in `_format_memories()` — accumulate `len(line) // 4` per memory, break loop when cumulative > 800 [REQ: per-injection-token-budget]

## 5. Metrics improvements

- [x] 5.1 Add `memory_count` field to `metrics_append()` calls in events.py [REQ: hit-rate-metrics]
- [x] 5.2 In `flush_metrics()`, compute per-layer aggregates (total injections, total tokens, total dedup hits, total empty results) and include in flushed output [REQ: hit-rate-metrics]

## 6. Tests

- [x] 6.1 Create `tests/test_hook_modes.py` — test that `SET_MEMORY_HOOKS=off` returns None for all handlers except Stop [REQ: hook-mode-environment-variable]
- [x] 6.2 Create `tests/test_hook_modes.py` — test that `SET_MEMORY_HOOKS=lite` returns None for PostToolUse/SubagentStart/SubagentStop [REQ: hook-mode-environment-variable]
- [x] 6.3 Create `tests/test_hook_modes.py` — test that `SET_MEMORY_HOOKS=full` enables all handlers [REQ: hook-mode-environment-variable]
- [x] 6.4 Add test for content-based dedup: same content with different IDs → only first included [REQ: content-based-dedup]
- [x] 6.5 Add test for relevance threshold: memory with score 0.4 filtered out, score 0.6 passes [REQ: relevance-threshold-filtering]
- [x] 6.6 Add test for token budget: 4 large memories → only first 2-3 fit within 800 token budget [REQ: per-injection-token-budget]
- [x] 6.7 Add test for display truncation: 500-char memory → output contains 300 chars + "..." [REQ: display-content-truncation]

## 7. Integration validation

- [x] 7.1 Create `tests/test_hook_replay.py` — replay 20 sample entries from `/tmp/set-hook-memory.log` through new pipeline, assert total tokens < 50% of old pipeline [REQ: hit-rate-metrics]
- [ ] 7.2 Manual validation: run a set-core interactive session with `SET_MEMORY_HOOKS=lite`, verify PostToolUse hooks no longer inject [REQ: hook-mode-environment-variable]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `SET_MEMORY_HOOKS` is unset THEN PostToolUse/SubagentStart/SubagentStop return None [REQ: hook-mode-environment-variable, scenario: lite-mode-default]
- [x] AC-2: WHEN `SET_MEMORY_HOOKS=full` THEN all hooks inject memory context [REQ: hook-mode-environment-variable, scenario: full-mode]
- [x] AC-3: WHEN `SET_MEMORY_HOOKS=off` THEN no hooks inject; Stop still executes [REQ: hook-mode-environment-variable, scenario: off-mode]
- [x] AC-4: WHEN memory relevance_score < 0.55 THEN it is excluded [REQ: relevance-threshold-filtering, scenario: threshold-filters-low-relevance-memories]
- [x] AC-5: WHEN same content (first 100 chars) injected by SessionStart THEN UserPromptSubmit skips it [REQ: content-based-dedup, scenario: dedup-persists-across-hook-types]
- [x] AC-6: WHEN memory content > 300 chars THEN display truncated to 300 + "..." [REQ: display-content-truncation, scenario: long-memory-content]
- [x] AC-7: WHEN cumulative tokens > 800 per hook fire THEN remaining memories skipped [REQ: per-injection-token-budget, scenario: budget-exceeded]
- [x] AC-8: WHEN session ends THEN metrics include per-layer aggregates [REQ: hit-rate-metrics, scenario: aggregate-stats-available]
