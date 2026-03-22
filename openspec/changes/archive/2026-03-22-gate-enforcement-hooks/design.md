# Design: gate-enforcement-hooks

## Context

The orchestration pipeline has 4 lifecycle hook points configured via orchestration.yaml directives:
- `hook_pre_dispatch`: shell script before worktree creation
- `hook_post_verify`: shell script after gate pipeline passes
- `hook_pre_merge`: shell script before merge execution
- `hook_post_merge`: shell script after merge

These are single shell scripts per hook point. Project-type plugins cannot programmatically inject hooks, and there's no composition mechanism for combining multiple hook sources.

## Goals / Non-Goals

**Goals:**
- Profile plugins can register pre-dispatch validation checks
- Profile plugins can register post-verify hooks (e.g., screenshot archival)
- Hook composition: directive hooks (shell) + profile hooks (Python callables) at each lifecycle point
- Web profile validates Playwright availability at dispatch time for feature changes

**Non-Goals:**
- Async hook execution (hooks run synchronously, blocking the pipeline)
- Hook priority/ordering within a hook point (directive first, then profile — fixed order)
- User-facing hook configuration UI
- Replacing the existing directive hook mechanism

## Decisions

### D1: Profile hook interface — methods returning callables

**Decision:** Add two methods to the profile interface:

```python
class NullProfile:
    def pre_dispatch_checks(self, change_type: str, wt_path: str) -> list[str]:
        """Return list of error messages. Empty = all checks pass."""
        return []

    def post_verify_hooks(self, change_name: str, wt_path: str, gate_results: list) -> None:
        """Run post-verify side effects (screenshots, cleanup, etc.)."""
        pass
```

**Why methods, not registered callables?** Simpler. The profile is already loaded; calling a method is more natural than a registration API. The profile implementation decides what to check/do based on change_type.

### D2: Pre-dispatch validation — blocking on non-empty errors

**Decision:** In `dispatch_change()` (dispatcher.py), after worktree creation but before starting the Ralph loop:

```python
errors = profile.pre_dispatch_checks(change.change_type, wt_path)
if errors:
    logger.error("Pre-dispatch check failed for %s: %s", change_name, errors)
    # Clean up worktree, mark change as dispatch-failed
    return
```

For web profiles, this would check:
- playwright.config.ts exists (for feature changes)
- node_modules/.bin/playwright exists (Playwright installed)

### D3: Post-verify hooks — non-blocking side effects

**Decision:** In `handle_change_done()` (verifier.py), after the gate pipeline returns "continue" (all gates passed), before adding to merge queue:

```python
if action == "continue":
    profile.post_verify_hooks(change_name, wt_path, pipeline.results)
    # Then add to merge queue as before
```

Post-verify hooks are non-blocking — exceptions are caught and logged but don't prevent merge. These are for side effects like screenshot archival, not validation.

### D4: Hook composition order

**Decision:** At each lifecycle point:
1. Directive hook (shell script) runs first
2. Profile hook (Python) runs second

Both run independently. A directive hook failure blocks the pipeline (existing behavior). A profile pre-dispatch check failure blocks dispatch. A profile post-verify hook failure is logged but doesn't block.

### D5: Web profile hooks — concrete implementation notes

The actual web profile hooks would be implemented in `set-project-web`, not in set-core. Set-core only provides the interface (NullProfile methods). But the design should anticipate:

**Pre-dispatch checks (web):**
```python
def pre_dispatch_checks(self, change_type, wt_path):
    errors = []
    if change_type == "feature":
        pw = Path(wt_path) / "playwright.config.ts"
        if not pw.exists() and not (Path(wt_path) / "playwright.config.js").exists():
            errors.append("Feature change requires playwright.config.ts — E2E tests are mandatory for web projects")
    return errors
```

**Post-verify hooks (web):**
```python
def post_verify_hooks(self, change_name, wt_path, gate_results):
    # Archive E2E screenshots to run directory
    e2e_result = next((r for r in gate_results if r.gate_name == "e2e"), None)
    if e2e_result and e2e_result.status == "pass":
        _archive_screenshots(change_name, wt_path)
```
