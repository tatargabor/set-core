## Context

We have per-iteration token data (`in`, `out`, `cr`, `cc`) in `loop-state.json` but no visibility into what **consumes** those tokens. The gitchen project shows single iterations using 1M–15M input tokens while the fixed context (rules, CLAUDE.md) is only ~50K tokens. Without component-level breakdown, we can't make informed decisions about context optimization (lazy rule loading, skill pruning, memory injection tuning).

### Current state
- `loop-state.json` tracks: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_create_tokens` per iteration
- `context-window-metrics` spec tracks start/end totals in orchestration state
- No breakdown of what the input tokens represent

### Constraints
- We can't instrument Claude Code internals — only measure from outside
- Token counting is approximate (chars/4 heuristic for text we control)
- Hook output is the only measurable memory injection point

## Goals / Non-Goals

**Goals:**
- Know what percentage of context is "fixed overhead" vs "productive work"
- Identify changes that waste tokens on over-injection
- Provide actionable data for context optimization decisions

**Non-Goals:**
- Automatically optimize context (this change only measures)
- Modify Claude Code's rule/skill loading behavior
- Achieve exact token counts (approximations are fine)

## Decisions

### D1: Measurement approach — estimate from what we control

We can't intercept Claude Code's system prompt loading, but we CAN measure:

1. **Prompt size**: We build the prompt string in `build_prompt()` — measure its char length → tokens
2. **Hook output**: Memory hooks return `<system-reminder>` text — capture and measure their output
3. **Base context**: Use iteration 1's `cache_create_tokens` as the baseline (first iteration creates the cache for system prompt + CLAUDE.md + rules + our prompt)
4. **Tool output**: Residual = `input_tokens - base - memory - prompt`

**Why not intercept the API?** We'd need to modify Claude Code or add a proxy. Too invasive. The estimation approach gives 80% accuracy with 0% invasiveness.

**Alternative considered:** Adding a `--dry-run` flag to Claude that reports context size without running. Not available in Claude Code CLI.

### D2: Hook output measurement — wrapper approach

Wrap memory hook calls to capture their output size:

```
Original: set-hook-memory UserPromptSubmit < stdin
Wrapped:  set-hook-memory UserPromptSubmit < stdin | tee >(wc -c >> .set/hook-output-size.txt)
```

But hooks run inside Claude Code, not our loop. Instead: **post-hoc estimation**.

After each iteration, scan the iter log for `<system-reminder>` blocks (memory hook output appears in verbose Claude output). Count their total size.

**Why this works:** With `--verbose`, Claude Code logs the injected system-reminder content. We grep the iter log post-iteration.

### D3: Storage — extend iteration records in loop-state.json

Add `context_breakdown` as a nested object in each iteration record:

```json
{
  "iteration": 1,
  "input_tokens": 402000,
  "output_tokens": 12000,
  "cache_create_tokens": 52000,
  "context_breakdown": {
    "base_context": 52000,
    "memory_injection": 8000,
    "prompt_overhead": 2000,
    "tool_output": 340000
  }
}
```

**Why in loop-state?** It's already the per-iteration data store. Adding a nested object keeps backwards compatibility (old readers ignore unknown fields).

### D4: API design — single aggregation endpoint

`GET /api/<project>/context-analysis` returns:

```json
{
  "project": "gitchen",
  "run_id": "latest",
  "changes": [
    {
      "name": "kitchen-devices",
      "iterations": 1,
      "base_context_tokens": 52000,
      "total_input_tokens": 15080525,
      "total_output_tokens": 40988,
      "context_breakdown_avg": {
        "base_context": 52000,
        "memory_injection": 15000,
        "prompt_overhead": 2000,
        "tool_output": 14971525
      },
      "efficiency_ratio": 0.0027
    }
  ],
  "summary": {
    "total_input": 80000000,
    "avg_base_ratio": 0.04,
    "most_expensive": "kitchen-devices",
    "avg_efficiency": 0.005
  }
}
```

**Why a separate endpoint?** The existing `/api/<project>/changes` already returns token data. But context breakdown requires reading loop-state files from worktrees, which is expensive. Separate endpoint = lazy loading.

### D5: Dashboard — new Context tab with stacked bars

Stacked horizontal bar chart (one bar per change):
- Blue: base_context
- Green: memory_injection
- Gray: prompt_overhead
- Orange: tool_output

Plus summary cards at top. Uses the same charting library already in set-web (recharts).

**Why stacked bar over treemap?** Stacked bars allow easy comparison across changes. Treemaps are better for single-change deep-dive (future enhancement).

### D6: CLI tool — simple table output

`set-context-report` reads loop-state.json(s) and prints a formatted table. No dependencies beyond bash + jq. Follows the pattern of `set-status` and `set-compare`.

## Risks / Trade-offs

- **[Risk] Token estimation inaccuracy** → The chars/4 heuristic can be off by 20-30% for non-English text or code. Mitigation: label all numbers as "estimated" in UI, use `cache_create_tokens` (exact) for base_context.
- **[Risk] Log parsing fragility** → Grep for `<system-reminder>` in verbose logs may break if Claude Code changes output format. Mitigation: treat as best-effort, fall back to 0.
- **[Risk] Large loop-state files** → Adding `context_breakdown` to each iteration adds ~100 bytes/iteration. At 30 iterations, +3KB. Negligible.

## Open Questions

- Should we also track **output token** breakdown (code written vs explanation vs tool calls)? Deferred — input tokens are the bigger cost driver.
- Should the Context tab be in the main dashboard or a separate "Analytics" page? Start in main dashboard, move if it gets crowded.
