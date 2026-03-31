## 1. Loop State Schema Extension

- [ ] 1.1 Add `context_breakdown` object to `add_iteration()` in `lib/loop/state.sh` with fields: `base_context`, `memory_injection`, `prompt_overhead`, `tool_output` [REQ: per-iteration-context-breakdown]
- [ ] 1.2 Add `base_context_tokens` field to loop-state initial JSON template in `init_loop_state()` [REQ: baseline-context-measurement-at-session-start]
- [ ] 1.3 Ensure backwards compatibility — old loop-state files without `context_breakdown` parse without errors [REQ: per-iteration-context-breakdown]

## 2. Baseline Context Measurement

- [ ] 2.1 In `engine.sh`, after iteration 1 completes, extract `cache_create_tokens` as `base_context_tokens` and store in loop-state [REQ: baseline-context-measurement-at-session-start]
- [ ] 2.2 For resumed iterations (N > 1), carry forward `base_context_tokens` from iteration 1 [REQ: baseline-context-measurement-at-session-start]

## 3. Prompt Size Measurement

- [ ] 3.1 In `engine.sh`, measure `effective_prompt` string length after `build_prompt()`, convert to token estimate (chars/4), store as `prompt_overhead` [REQ: per-iteration-context-breakdown]

## 4. Memory Injection Estimation

- [ ] 4.1 After iteration completes, scan iter log file for `<system-reminder>` blocks and sum their character counts [REQ: memory-injection-size-tracking]
- [ ] 4.2 Convert character count to token estimate (chars/4) and store as `memory_injection` in context_breakdown [REQ: memory-injection-size-tracking]
- [ ] 4.3 Handle case where no system-reminder blocks found (set to 0) [REQ: memory-injection-size-tracking]

## 5. Tool Output Calculation

- [ ] 5.1 Compute `tool_output` as residual: `input_tokens - base_context - memory_injection - prompt_overhead`, clamped to 0 [REQ: per-iteration-context-breakdown]
- [ ] 5.2 Write complete `context_breakdown` object into iteration record via `add_iteration()` [REQ: per-iteration-context-breakdown]

## 6. Monitor Integration

- [ ] 6.1 In `monitor.py`, read `context_breakdown` from iteration 1 of loop-state and store as `context_breakdown_start` in change's orchestration state [REQ: context-tokens-captured-at-first-iteration-completion]
- [ ] 6.2 Ensure existing `context_tokens_start` / `context_tokens_end` logic still works alongside new fields [REQ: context-tokens-captured-at-first-iteration-completion]

## 7. API Endpoint

- [ ] 7.1 Add `GET /api/<project>/context-analysis` route in `lib/set_orch/api.py` [REQ: context-analysis-api-endpoint]
- [ ] 7.2 Implement aggregation: read loop-state.json from each change's worktree, compute per-change breakdown averages [REQ: context-analysis-api-endpoint]
- [ ] 7.3 Include summary statistics: total_input, avg_base_ratio, most_expensive, avg_efficiency [REQ: context-analysis-api-endpoint]
- [ ] 7.4 Handle missing/old loop-state files gracefully (return null breakdown, still show basic totals) [REQ: context-analysis-api-endpoint]

## 8. Dashboard Context Tab

- [ ] 8.1 Add "Context" tab to set-web project view (alongside existing Changes, Timeline, etc.) [REQ: dashboard-context-visualization]
- [ ] 8.2 Fetch data from `/api/<project>/context-analysis` endpoint [REQ: dashboard-context-visualization]
- [ ] 8.3 Implement stacked horizontal bar chart (recharts) with color-coded components: base (blue), memory (green), prompt (gray), tools (orange) [REQ: dashboard-context-visualization]
- [ ] 8.4 Add summary cards: total input tokens, avg base ratio, most expensive change, avg efficiency [REQ: dashboard-context-visualization]
- [ ] 8.5 Add run selector dropdown for cross-run comparison [REQ: dashboard-context-visualization]
- [ ] 8.6 Add tooltip on context metric showing component breakdown [REQ: set-web-change-list-shows-context-metrics]

## 9. CLI Report Tool

- [ ] 9.1 Create `bin/set-context-report` bash script with jq-based loop-state parsing [REQ: cli-context-report]
- [ ] 9.2 Implement per-iteration table output (Iter, Base, Memory, Prompt, Tools, Total, Base%) [REQ: cli-context-report]
- [ ] 9.3 Implement `--project <name>` flag for cross-change summary from orchestration directory [REQ: cli-context-report]
- [ ] 9.4 Add "Recommendations" section identifying optimization targets (base>30%, memory>20%, efficiency<0.05) [REQ: cli-context-report]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN iteration 1 completes THEN iteration record contains `base_context_tokens` from `cache_create_tokens` [REQ: baseline-context-measurement-at-session-start, scenario: first-iteration-captures-baseline]
- [ ] AC-2: WHEN iteration N>1 runs with --resume THEN `base_context_tokens` copied from iteration 1 [REQ: baseline-context-measurement-at-session-start, scenario: resumed-iterations-skip-baseline]
- [ ] AC-3: WHEN iteration completes THEN `context_breakdown` object present with all 4 fields [REQ: per-iteration-context-breakdown, scenario: breakdown-fields-present-after-iteration]
- [ ] AC-4: WHEN tool_output computed as negative THEN clamped to 0 [REQ: per-iteration-context-breakdown, scenario: tool-output-is-the-residual-category]
- [ ] AC-5: WHEN GET /api/project/context-analysis called THEN response contains per-change breakdown array [REQ: context-analysis-api-endpoint, scenario: endpoint-returns-per-change-breakdown]
- [ ] AC-6: WHEN change has no context_breakdown THEN still appears with null breakdown [REQ: context-analysis-api-endpoint, scenario: endpoint-handles-missing-data-gracefully]
- [ ] AC-7: WHEN user views Context tab THEN stacked bar chart shows per-change breakdown [REQ: dashboard-context-visualization, scenario: stacked-bar-chart-per-change]
- [ ] AC-8: WHEN set-context-report runs in worktree THEN prints per-iteration table [REQ: cli-context-report, scenario: report-from-worktree-loop-state]
- [ ] AC-9: WHEN report runs THEN Recommendations section identifies optimization targets [REQ: cli-context-report, scenario: report-identifies-optimization-targets]
