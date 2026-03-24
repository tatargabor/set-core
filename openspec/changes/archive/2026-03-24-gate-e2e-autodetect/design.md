# Design: gate-e2e-autodetect

## Context

The E2E gate (`_execute_e2e_gate` in verifier.py) requires an explicit `e2e_command` string passed through the directive chain: `orchestration.yaml → engine.py Directives → handle_change_done()`. If this string is empty, the gate returns "skipped" regardless of the gate profile configuration.

The profile loader (`profile_loader.py`) uses `importlib.metadata.entry_points()` to find project-type plugins. With editable pip installs, entry_points registration can silently fail, causing `load_profile()` to return NullProfile even when the plugin package is installed and importable.

Current resolution chain:
```
orchestration.yaml e2e_command → explicit (preferred)
  ↓ (if empty)
profile.detect_e2e_command() → NullProfile returns None
  ↓ (if None)
e2e_command = "" → gate skips
```

## Goals / Non-Goals

**Goals:**
- Fix profile loader to find installed plugins even when entry_points is broken
- Auto-detect e2e_command from playwright config and package.json
- Make E2E gate fail (not skip) for feature changes in web projects when E2E infrastructure exists but no tests run

**Non-Goals:**
- Support non-Playwright E2E frameworks (Cypress, etc.) — future extension via profile
- Change the gate profile defaults (feature e2e="run" is already correct)
- Modify how explicit e2e_command from orchestration.yaml works

## Decisions

### D1: Profile loader — direct import fallback

**Decision:** After entry_points lookup fails, try direct import using a naming convention: `set_project_{type_name}` module with `{TypeName}ProjectType` class.

**Why not fix entry_points registration?** That's an environment issue (pip editable install state). The loader should be resilient to it since it's the most common development setup.

**Fallback chain:**
```
1. entry_points(group='set_tools.project_types') → match by name
2. importlib.import_module(f"set_project_{type_name}") → convention-based
3. NullProfile (unchanged fallback)
```

### D2: E2E auto-detect in verifier, not profile

**Decision:** Auto-detect logic lives in `_execute_e2e_gate()` as a fallback when e2e_command is empty, not in the profile.

**Why?** The profile may not be loaded (NullProfile), and the auto-detect needs access to the worktree path which the profile doesn't have at load time. The verifier already has `_parse_playwright_config()` which checks for playwright.config.ts.

**Auto-detect chain:**
```
1. e2e_command from directives (explicit — always preferred)
2. profile.detect_e2e_command(wt_path) (if profile supports it)
3. _auto_detect_e2e_command(wt_path):
   a. Find playwright.config.ts/js → confirms Playwright project
   b. Read package.json scripts → find test:e2e, e2e, or playwright
   c. Fall back to "npx playwright test"
```

### D3: NullProfile gets detect_e2e_command method

**Decision:** Add `detect_e2e_command(project_path: str) -> Optional[str]` to NullProfile (returns None). Web profile overrides it.

**Why?** Consistent interface. The verifier checks `profile.detect_e2e_command()` before falling back to auto-detect.

### D4: Feature + playwright config + no e2e = FAIL not skip

**Decision:** In `_execute_e2e_gate`, when:
- e2e_command was auto-detected (not explicitly configured)
- playwright.config.ts exists
- But no e2e test files found in worktree

Return GateResult("fail") with retry_context telling the agent to write E2E tests.

**Why?** Web projects with Playwright MUST have E2E coverage for feature changes. Silent skip defeats the purpose of the gate. The agent gets a clear instruction to add tests.

**Current behavior (3 skip paths):**
```python
# verifier.py:2162 — skip if no command
if not e2e_command: return skipped

# verifier.py:2166 — skip if no config
if not pw_config["config_path"]: return skipped

# verifier.py:2171 — skip if no test files
if e2e_test_count == 0: return skipped
```

**New behavior:**
```python
# 1. Auto-detect if no explicit command
if not e2e_command:
    e2e_command = _auto_detect_e2e_command(wt_path, profile)
    if not e2e_command:
        return skipped  # genuinely no E2E framework

# 2. Config check (unchanged)
if not pw_config["config_path"]: return skipped

# 3. Test file check — FAIL if Playwright exists but no tests
if e2e_test_count == 0:
    if auto_detected:  # had to auto-detect = web project
        return GateResult("fail", retry_context="...")
    return skipped  # explicit config chose to skip
```
