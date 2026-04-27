# Proposal: Diagnostic Pipeline

## Motivation

Across 6 CraftBrew E2E runs, the same failure patterns recur and block the orchestration pipeline for hours until human intervention:

| Bug | Pattern | Runs Affected | Lost Time |
|-----|---------|---------------|-----------|
| #29 | Post-merge Prisma generate missing → build_broken_on_main | Run #5, #6 | ~30min each |
| #28 | Merge-blocked → no agent rebase → stuck forever | Run #6 | ~2h |
| #26 | Dependency cascade deadlock → all downstream blocked | Run #4, #5, #6 | total deadlock |
| #27 | Context overflow (200K vs 1M) → change fails | Run #5 | 1h + cascade |
| #30 | Artifact loop — agent creates artifacts but doesn't implement | Run #5, #6 | ~1h each |

The framework currently handles failures with simple retry loops and flag-based blocking (`build_broken_on_main`). When retries exhaust, the pipeline deadlocks. There is no root-cause analysis, no pattern matching against known issues, and no self-healing capability.

## Capabilities

### 1. diagnostic-framework (set-core)
Abstract diagnostic rule system integrated into the orchestration failure path. When a change fails (verify exhausted, merge-blocked, build broken), a diagnostic runner executes registered rules before giving up. Rules can:
- Analyze failure output (build logs, review output, merge conflicts)
- Apply config-level fixes (orchestration config, .gitattributes, directives)
- Reset/retry with enriched context
- Report findings to memory and E2E logs
- Skip/propagate failed dependencies to unblock downstream changes

### 2. web-diagnostics (set-project-web)
Concrete diagnostic rules for web projects (Next.js, Prisma, npm ecosystem):
- Prisma client regeneration after schema merges
- Missing npm dependency detection and install
- TypeScript/ESLint error pattern matching
- Cross-branch i18n/config merge gap detection
- Context window overflow → model upgrade recommendation

### 3. config-integration
Declarative failure policy in `orchestration config.yaml`:
```yaml
on_failure:
  verify_exhausted: diagnose    # run diagnostic rules before marking failed
  merge_blocked: diagnose       # try auto-fix before giving up
  build_broken_on_main: diagnose # analyze and fix before blocking dispatch
  dependency_failed: skip_downstream  # propagate failure, don't deadlock
```

## Scope

### In Scope
- DiagnosticRule abstract base class in set-core
- DiagnosticRunner that executes rules on failure events
- Profile interface extension: `diagnostic_rules() → list[DiagnosticRule]`
- 6 concrete web diagnostic rules in set-project-web
- Config-level fix capabilities (config.yaml, .gitattributes, directives)
- Dependency cascade handling (skip/propagate on failure)
- Findings reporting (memory + findings files)
- Integration into engine.py monitor loop failure paths

### Out of Scope
- Source code modification (agents don't write src/ files — only config)
- LLM-based root cause analysis (future — would use Claude to diagnose)
- Cross-project learning (sharing diagnostics between different projects)
- UI/dashboard for diagnostic results
