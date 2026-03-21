# Design: e2e-gate-fix

## Context

The E2E verify gate in `lib/set_orch/verifier.py` has three compounding bugs that prevent Playwright tests from ever running during orchestration:

1. `_count_e2e_tests()` hardcodes `tests/e2e/` as the search directory, but agents may write tests to `e2e/` or other directories configured in `playwright.config.ts`
2. The health check probes a random port (3100+rand) where no server listens — meanwhile Playwright's own `webServer` config would auto-start a dev server if we let it
3. The cleanup logic pkills on the wrong port pattern

The phase-end E2E function (`run_phase_end_e2e()`) has similar port management issues.

## Goals / Non-Goals

**Goals:**
- E2E tests actually run when `e2e_command` is configured and Playwright tests exist
- Skip reasons are always diagnostic (visible in state file)
- Backward compatible with projects that don't use Playwright's `webServer`

**Non-Goals:**
- Adding new orchestration directives (no `e2e_dev_server_command` — Playwright handles this)
- Changing E2E test framework support beyond Playwright
- Fixing agent dispatch to write tests in the right directory (separate concern)

## Decisions

### D1: Parse Playwright config for testDir (lightweight regex)

Parse `testDir` from `playwright.config.ts` using a simple regex (`testDir:\s*["']([^"']+)["']`), not a full TypeScript parser. If not found, search multiple fallback directories.

**Why not a TS parser?** Adding a Node.js subprocess call to parse config adds latency and a dependency. The `testDir` field is always a simple string literal in practice.

**Alternatives considered:**
- Full TS eval via `node -e` — too heavy, adds 500ms+ per gate
- Only searching multiple hardcoded dirs — misses custom `testDir` values

### D2: Detect webServer block via regex, not full parse

Check for `webServer` in the Playwright config file content using string search (`"webServer" in config_content` or regex). This determines whether Playwright manages the dev server.

**Why?** The presence of `webServer` is a binary signal. We don't need to parse its fields — if it exists, Playwright handles server lifecycle.

### D3: Two execution paths based on webServer detection

```
_execute_e2e_gate()
    │
    ├── webServer detected?
    │   ├── YES: run e2e_command directly (no port, no health check, no pkill)
    │   └── NO:  allocate port → health check → run with PW_PORT → pkill cleanup
    │
    └── Both paths: collect screenshots, parse output, return GateResult
```

### D4: Extract config parsing into a helper function

New function `_parse_playwright_config(wt_path)` returns a dict:
```python
{
    "config_path": str,        # path to config file found
    "test_dir": str | None,    # parsed testDir value
    "has_web_server": bool,    # whether webServer block exists
}
```

This is used by both `_count_e2e_tests()` and `_execute_e2e_gate()`.

### D5: Phase-end E2E gets the same webServer-aware logic

`run_phase_end_e2e()` uses the same `_parse_playwright_config()` helper and follows the same two-path pattern. No port allocation or pkill when Playwright manages the server.

## Risks / Trade-offs

- **[Risk] Regex parsing misses edge cases** (e.g., `testDir` in a comment, dynamic `testDir` from env var) → Mitigation: fallback to multi-directory search when regex fails
- **[Risk] webServer detection false positive** (commented out webServer block) → Mitigation: acceptable — worst case, health check is skipped and Playwright fails with a clear error
- **[Risk] Port conflict** when multiple E2E gates run concurrently without PW_PORT → Mitigation: Playwright's `webServer` respects `reuseExistingServer` and picks its own port; concurrent worktrees are isolated

## Open Questions

*(none — design is straightforward)*
