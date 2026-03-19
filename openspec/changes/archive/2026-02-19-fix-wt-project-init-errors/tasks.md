## 1. Fix `_register_mcp_server` error handling

- [x] 1.1 Remove `2>/dev/null` from `claude mcp add` command, capture stderr instead
- [x] 1.2 Check exit code of `claude mcp add` — print warning with error output on failure, success only on success
- [x] 1.3 Return 1 from `_register_mcp_server` if any registration failed, 0 if all succeeded

## 2. Fix `deploy_set_tools` step tracking

- [x] 2.1 Add warning counter variable at top of `deploy_set_tools`
- [x] 2.2 Check exit code of `wt-deploy-hooks` — warn on failure instead of unconditional success
- [x] 2.3 Return non-zero from `deploy_set_tools` if warning counter > 0

## 3. Fix `_cleanup_deprecated_memory_refs` error visibility

- [x] 3.1 Replace `2>/dev/null || true` on python3 cleanup calls with stderr capture — warn with file path on failure

## 4. Update `cmd_init` summary

- [x] 4.1 Check return value of `deploy_set_tools` and print "complete with warnings" if non-zero

## 5. Verify

- [x] 5.1 Test happy path: `set-project init` in an existing project — all steps succeed, output unchanged
- [x] 5.2 Test error path: simulate `claude mcp add` failure (e.g. invalid args) — verify warning is visible
