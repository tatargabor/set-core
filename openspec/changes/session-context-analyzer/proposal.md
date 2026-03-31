## Why

Orchestration runs consume massive token budgets but we have no visibility into **what** consumes those tokens. The gitchen project shows single iterations using 1M–15M input tokens, yet the fixed context (rules, CLAUDE.md) is only ~50K tokens. We can't optimize what we can't measure — we need per-component context breakdown to identify the biggest cost drivers and make informed decisions about context diet, lazy loading, or session reuse.

## What Changes

- **New hook**: A `SessionStart` measurement hook that captures the baseline context size (system prompt + CLAUDE.md + rules + memory injection) before the agent does any work
- **Per-iteration breakdown**: Extend `loop-state.json` iterations with component-level token categories: `base_context`, `tool_output`, `memory_injection`, `prompt_overhead`
- **API endpoint**: New `/api/<project>/context-analysis` endpoint that aggregates context data across changes for a given orchestration run
- **Dashboard tab**: New "Context" tab in set-web showing per-change context breakdown with visualizations (treemap or stacked bar) and cross-run comparison
- **CLI tool**: `set-context-report` for quick terminal analysis of context composition from loop-state data

## Capabilities

### New Capabilities
- `session-context-analysis` — Measuring and categorizing context token usage within sessions

### Modified Capabilities
- `context-window-metrics` — Extend with per-component breakdown (currently only tracks start/end totals)
- `ralph-loop-logging` — Add context category fields to iteration records

## Impact

- **lib/loop/state.sh**: New fields in iteration JSON (`context_breakdown` object)
- **lib/loop/engine.sh**: Capture baseline tokens before first tool call, categorize token growth
- **lib/set_orch/monitor.py**: Read new fields from loop-state, expose via orchestration state
- **web/**: New Context tab with treemap/stacked bar visualization
- **lib/set_orch/api.py**: New endpoint for context analysis aggregation
- **bin/set-context-report**: New CLI tool
