## ADDED Requirements

### Requirement: Automated results collector
Create `benchmark/evaluator/collect-results.sh` that gathers metrics from a completed benchmark run.

For each run (A and B):
- Total iterations from `wt-loop history`
- Total tokens from loop state JSON
- Commits per change (parse git log)
- Per-change iteration count (how many iterations each change took)
- Run all eval-*.sh scripts and collect results

For Run B additionally:
- Total memories from `set-memory status`
- Memory list from `set-memory list`

Output: `results/run-{a,b}-metrics.json` with structured data.

#### Scenario: Collect Run A results
- **WHEN** `collect-results.sh ~/benchmark/run-a/craftbazaar A` is run
- **THEN** creates `results/run-a-metrics.json` with iterations, tokens, commits, eval scores

---

### Requirement: Comparison report generator
Create `benchmark/evaluator/compare.sh` that takes both metrics files and generates a markdown comparison report.

Report sections:
- **Summary table**: iterations, tokens, time, eval scores side by side
- **Per-change breakdown**: which changes each agent spent more/fewer iterations on
- **Revision change analysis**: how each agent handled C07-C09 (the memory-critical changes)
- **Eval score comparison**: schema, API, behavior, coherence scores per run
- **Memory utilization** (Run B only): recall count, save count, quality assessment

#### Scenario: Generate comparison
- **WHEN** `compare.sh results/run-a-metrics.json results/run-b-metrics.json` is run
- **THEN** creates `results/comparison-report.md` with full analysis
