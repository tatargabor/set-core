## Context

`set-project init` orchestrates project setup via `deploy_set_tools()` which calls several sub-steps: hook deployment, command/skill copying, deprecated ref cleanup, and MCP server registration. Currently, failures in these steps are silently swallowed through `2>/dev/null` and `|| true` patterns, always printing "success" regardless of outcome. This caused a real issue where MCP registration failed silently — the user spent a debugging session discovering `claude mcp list` was empty.

The `_register_mcp_server` function (lines 124-138 in `bin/set-project`) is the worst offender: the entire `claude mcp add` command has its stderr suppressed, and `|| true` prevents the exit code from propagating. The function unconditionally prints success on line 137.

## Goals / Non-Goals

**Goals:**
- Report actual errors/warnings when deployment steps fail
- Keep `2>/dev/null` only where the output is genuinely expected noise (e.g. removing a non-existent MCP server)
- Make `cmd_init` report a summary: N steps succeeded, M warnings
- Ensure the happy path output is unchanged

**Non-Goals:**
- Changing the init to abort on first error (it should continue and report all issues)
- Adding retry logic
- Changing the deployment steps themselves (hooks, commands, skills structure)

## Decisions

### D1: Warn-and-continue model (not fail-fast)

`deploy_set_tools` will continue through all steps even if some fail, collecting warnings. At the end, `cmd_init` prints a summary. Rationale: a partial deployment (e.g. hooks work but MCP failed) is still useful — the user can fix the one failing step.

Alternative considered: fail-fast (abort on first error) — rejected because it would leave deployment in a half-done state.

### D2: Use a `warnings` counter pattern

Each helper function returns 0 on success, 1 on failure. `deploy_set_tools` tracks a warning counter. At the end it returns 0 if all succeeded, 1 if any warnings. `cmd_init` uses this to print either "complete" or "complete with N warnings".

Alternative considered: collecting error messages in an array — overkill for this scope.

### D3: Keep `2>/dev/null` only for expected-to-fail commands

- `claude mcp remove set-memory 2>/dev/null` — keep (may not exist, that's fine)
- `claude mcp remove set-core 2>/dev/null` — keep (same reason)
- `claude mcp add ... 2>/dev/null` — **remove** (this is the critical command, errors must be visible)
- `python3 ... 2>/dev/null || true` in cleanup — **replace** with stderr capture to warn

### D4: stderr capture pattern for `claude mcp add`

```bash
local mcp_err
mcp_err=$(claude mcp add set-core -- env ... 2>&1 >/dev/null)
if [[ $? -ne 0 ]]; then
    warn "  MCP registration failed for $reg_path: $mcp_err"
    return 1
fi
```

This captures stderr while suppressing stdout (which is just the JSON confirmation), and shows the error on failure.

## Risks / Trade-offs

- **[Risk] Verbose output on already-known issues** → Mitigation: only warn on actual failures, not expected removals
- **[Risk] `claude mcp add` may output to stdout not stderr** → Mitigation: capture both with `2>&1`, the success JSON is harmless in the warning if it somehow includes it
- **[Risk] Hook deployment (`wt-deploy-hooks`) doesn't return meaningful exit codes** → Mitigation: check exit code, if it already returns proper codes we use them; if not, leave as-is with a TODO
