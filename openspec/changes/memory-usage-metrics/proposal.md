## Why

Memory hooks inject ~3,761 tokens/session across 4 layers, but we have no way to measure whether injected memories actually influenced agent behavior. The citation rate (0.59% — scanning for "From memory:" patterns) is unreliable because agents use memories without explicit attribution. We need a context_id-based inject+cite mechanism to measure true usage rate, plus a unified TUI dashboard that shows memory DB stats, hook overhead metrics, and usage signals in one place.

## What Changes

- Add short context IDs (`[MEM#xxxx]`) to each injected memory fragment in hook output
- Add passive transcript matching in Stop hook: compare injected memory keywords against agent responses to detect actual usage without agent burden
- Continue detecting legacy explicit citation patterns ("From memory:") as bonus signal
- Store inject/cite pairs in SQLite metrics DB (new `mem_citations` table)
- Create `wt-memory tui` command: unified dashboard showing memory DB stats, hook metrics, and usage signals
- Extend `lib/metrics.py` with usage rate calculations (cited/injected ratio)

## Capabilities

### New Capabilities
- `memory-context-id`: Context ID injection into memory fragments and cite tracking through transcript scanning
- `memory-tui-dashboard`: Unified terminal dashboard combining memory DB stats, hook overhead metrics, and usage signal analysis

### Modified Capabilities
- `metrics-collection`: Add context_id generation and tracking to injection records
- `metrics-reporting`: Add usage rate (cite/inject ratio) to reports and extend citation scanning for MEM_CITE markers

## Impact

- `bin/wt-hook-memory` — modify `proactive_and_format()` and `recall_and_format()` to tag each result with `[MEM#xxxx]`
- `bin/wt-hook-memory` — modify Stop handler transcript scanning to detect `[MEM_CITE:xxxx]`
- `lib/metrics.py` — new table, new queries for usage rate
- `bin/wt-memory` — new `tui` subcommand
- `bin/wt-project` — no changes needed (passive approach requires no CLAUDE.md modifications)
- `.claude/settings.json` — no changes (hooks already in place)
