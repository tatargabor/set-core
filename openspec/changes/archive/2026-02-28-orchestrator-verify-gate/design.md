## Context

set-orchestrate decomposes specs into changes, dispatches Ralph loops in parallel worktrees, monitors progress, and merges results. Currently there is no verification between Ralph completing and merge — `handle_change_done` goes straight from "done" to merge (with an optional but unused `test_command`). The `run_claude` function always uses the default model (Opus), even for cheap tasks like summarization.

Key functions in `bin/set-orchestrate`:
- `cmd_plan()` — LLM decomposes spec into changes (lines ~900-1070)
- `summarize_spec()` — hierarchical spec summarization for large docs
- `dispatch_change()` — creates worktree + starts Ralph loop
- `handle_change_done()` — called when Ralph marks loop as done
- `merge_change()` — merges branch into target
- `monitor_loop()` — main poll loop (30s interval)
- `run_claude()` — sends prompt to Claude CLI, returns output
- `resolve_directives()` / `parse_directives()` — reads orchestration config

## Goals / Non-Goals

**Goals:**
- Auto-detect test infrastructure and `test_command` from the target project
- Include test requirements in every planned change scope via planner prompt
- Run tests after Ralph completes, before merge (verify gate)
- Support model tiering: cheaper models for summarization, review, fix
- Optional LLM code review gate before merge

**Non-Goals:**
- E2E / Playwright test orchestration (too slow for verify gate, belongs in CI/CD)
- Modifying the Ralph loop itself (test requirements flow through change scope)
- Building test infrastructure tooling (Ralph builds it as a change)
- Modifying OpenSpec schemas or skills

## Decisions

### D1: Test infra detection — filesystem scan, not LLM

Scan for known patterns before planning:
```bash
detect_test_infra() {
    # Check: vitest.config.*, jest.config.*, *.test.*, *.spec.*
    # Check: package.json "test" script
    # Check: test helper dirs (src/test/, __tests__/, etc.)
    # Output: JSON with {framework, config_path, test_count, test_command, has_helpers}
}
```

This is deterministic and free (no LLM). Results injected into planner context.

### D2: Planner prompt augmentation — inject test context + instructions

Add to the plan decomposition prompt:
1. Test infra scan results
2. Rule: "Every change scope MUST include test requirements"
3. Rule: "If no test infrastructure exists, the FIRST change must be `test-infrastructure-setup` with all others depending on it"

### D3: test_command auto-detection — package.json fallback chain

```
Priority:
1. CLI flag: --test-command "..."
2. orchestration.yaml: test_command: "..."
3. package.json scripts: "test" → "test:unit" → "test:ci"
4. Default: "" (skip test gate)
```

### D4: Verify gate — test + optional review, one retry

In `handle_change_done()`, before calling `merge_change()`:

```
Ralph done → run test_command in worktree
  → pass → (optional: LLM review) → merge
  → fail → restart Ralph with "fix these test failures: <output>"
            (verify_retried flag, max 1 retry)
  → fail again → mark as "verify-failed", notify, skip merge
```

The existing `verify_retried` flag already exists in the code — extend it.

### D5: Model tiering — run_claude gets model parameter

```bash
run_claude() {
    local prompt="$1"
    local model="${2:-}"  # empty = default (Opus)
    local model_flag=""
    [[ -n "$model" ]] && model_flag="--model $model"
    echo "$prompt" | script -f -q /dev/null -c "claude -p $model_flag"
}
```

Usage map:
| Task | Model | Directive key |
|------|-------|---------------|
| Spec summarization | `summarize_model` (default: haiku) | `summarize_model: haiku` |
| Plan decomposition | always Opus | n/a |
| Code review gate | `review_model` (default: sonnet) | `review_model: sonnet` |
| Test failure fix | same as review_model | n/a |

### D6: Code review gate — optional Sonnet review before merge

When `review_before_merge: true` in directives:
1. After tests pass, run a Sonnet-based code review prompt
2. Prompt includes: diff of changes, original scope, known patterns to check (security, auth, tenant isolation)
3. If review finds critical issues → treat like test failure (retry Ralph once)
4. If review passes → proceed to merge

### D7: New directives in orchestration.yaml

```yaml
# Verify gate
test_command: ""          # auto-detected if empty
review_before_merge: false
max_verify_retries: 1

# Model tiering
summarize_model: haiku
review_model: sonnet
```

## Alternatives Considered

- **Test in a separate phase**: Rejected — the whole problem is that Phase 2 tests come too late to catch Phase 1 bugs.
- **Always run E2E tests**: Rejected — too slow (2-10min per change), belongs in CI/CD not the orchestrator verify gate.
- **LLM review WITHOUT tests**: Considered — useful but tests are more reliable for catching runtime bugs. LLM review is complementary, not a replacement.
