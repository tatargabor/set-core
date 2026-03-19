## Why

The current A-B benchmark (CraftBazaar, 12 changes, 14 traps) has three problems:

1. **Slow**: ~2 hours per run, ~4-5 hours total for A+B comparison. Setting up, running, and scoring takes a full day.
2. **Noisy**: Agent coding ability dominates the signal. A better coder without memory can outperform a worse coder with memory — obscuring memory's actual value. v6 result: Run A (no memory) scored *higher* than Run B.
3. **Manual scoring**: Most trap scoring requires transcript review. Only test pass/fail is automated.

We need a benchmark that **isolates memory value** from agent coding ability, runs in under an hour, and scores itself automatically.

## What Changes

A new synthetic micro-benchmark ("MemoryProbe") that:

- Uses **5 small changes** instead of 12 large ones (each ~20 lines of requirements)
- Runs each change as a **separate Claude session** (fresh context = memory is the ONLY bridge)
- Tests **6 non-standard project conventions** that no LLM would guess without being told
- Scores with **fully automated grep** — no transcript review needed
- Supports **3 test modes**: baseline (A), full-memory (B), pre-seeded recall-only (C)

### Key Insight: Non-Standard Conventions

Standard patterns (like `{data, total, page, limit}` pagination) are in LLM training data — agents get them right without memory. MemoryProbe uses **deliberately non-standard conventions** that are specified in Change 01 and must be followed in Changes 03-05. Without memory, agents fall back to standard patterns. With memory, agents recall the project conventions.

### Key Insight: Separate Sessions

CraftBazaar runs all 12 changes in one long loop — conventions stay in context. MemoryProbe runs each change as a **fresh Claude invocation**. The only way to "remember" C01's conventions in C03 is through shodh-memory or by reading existing code. This makes the memory signal much clearer.

## Capabilities

### New Capabilities
- `trap-design`: 6 non-standard convention traps with exact grep patterns
- `scoring-system`: Automated convention compliance scoring via grep
- `execution-model`: Multi-session benchmark runner with 3 test modes

### Modified Capabilities
(none)

## Impact

- New directory: `benchmark/synthetic/` — all benchmark files
- No changes to existing `benchmark/` files (CraftBazaar benchmark stays intact)
- Reuses existing infrastructure: `set-memory`, Claude Code CLI
- Does NOT use OpenSpec or wt-loop — simpler execution model
