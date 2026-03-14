## Why

The orchestration planner (`lib/orchestration/planner.sh`, 1456 LOC) is the most complex bash module in terms of logic density — it orchestrates spec summarization, test infrastructure detection, triage gate evaluation, multi-mode decomposition prompt assembly (digest/spec/brief), plan validation with dependency graph analysis, scope overlap detection via Jaccard similarity, agent-based planning via worktree dispatch, and multi-cycle auto-replanning with state preservation. Much of this logic involves JSON manipulation via 30+ jq calls, string-based set operations (comm, sort -u), and arithmetic computed in shell. Migrating to Python replaces fragile bash data processing with typed Python, leveraging existing infrastructure from Phases 1-3 (config.py, state.py, events.py, templates.py).

## What Changes

- **New**: `lib/wt_orch/planner.py` — Python module containing: spec summarization, test infrastructure detection, plan validation (structure, kebab-case, dependency graph, scope overlap, coverage), triage gate checks, decomposition prompt assembly, plan metadata enrichment, and auto-replan cycle logic
- **New**: CLI subcommands `wt-orch-core plan decompose`, `wt-orch-core plan validate`, `wt-orch-core plan detect-test-infra`, `wt-orch-core plan check-triage`, `wt-orch-core plan check-scope-overlap`, `wt-orch-core plan summarize-spec`, `wt-orch-core plan replan-context` bridging bash to Python
- **Modified**: `lib/orchestration/planner.sh` — replace function bodies with thin CLI wrappers calling `wt-orch-core plan *`, keep cmd_plan/cmd_replan/auto_replan_cycle/plan_via_agent as bash orchestration flow (these call external tools like run_claude, wt-new, wt-loop, wt-close)
- **Modified**: `lib/wt_orch/cli.py` — add `plan` subcommand group
- **Modified**: `lib/wt_orch/templates.py` — extend with triage template rendering if not already present

## Capabilities

### New Capabilities

- `plan-validation`: Plan JSON validation — structure checks, kebab-case enforcement, dependency graph cycle detection, scope overlap detection (Jaccard similarity), digest-mode requirement coverage verification, cross-cutting file hazard detection
- `plan-decomposition`: Decomposition support — test infrastructure scanning, spec summarization, triage gate evaluation, prompt context assembly (memory, design, project knowledge, requirements), plan metadata enrichment, replan context collection
- `plan-cli`: CLI bridge subcommands for planner operations

### Modified Capabilities

## Impact

- `lib/orchestration/planner.sh` — 12 functions replaced with CLI wrappers; cmd_plan/cmd_replan/auto_replan_cycle/plan_via_agent remain as bash flow orchestrators calling run_claude, wt-new, wt-loop
- `lib/wt_orch/cli.py` — new `plan` subcommand group (~8 subcommands)
- Existing Python modules used: config.py (directives, find_input), state.py (topological_sort, init_state), events.py (emit), templates.py (render_planning_prompt)
- No new dependencies — all functionality uses stdlib (json, pathlib, hashlib, collections) plus existing deps (PyYAML for project-knowledge.yaml)
- Plan output format unchanged — consumers see identical JSON structure
