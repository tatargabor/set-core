## Why

`set-project init` silently swallows errors during MCP server registration and other deployment steps, reporting "success" even when critical steps fail. This caused a real debugging session where MCP tools weren't working because `claude mcp add` had failed silently — the `2>/dev/null` and `|| true` pattern hid the error while still printing a success message.

## What Changes

- **`_register_mcp_server`**: Remove `2>/dev/null` from `claude mcp add`, capture and check exit codes, only print "success" on actual success, print actionable error message on failure
- **`deploy_set_tools`**: Add error checking to each deployment step (`wt-deploy-hooks`, command copy, skill copy), propagate failures instead of unconditionally printing success
- **`_cleanup_deprecated_memory_refs`**: Replace `2>/dev/null || true` on python3 calls with proper error handling — log warnings on failure instead of silent swallow
- **General**: Keep `2>/dev/null` only where expected (e.g. `claude mcp remove` of non-existent server), remove it from operations that need visibility

## Capabilities

### New Capabilities

- `init-error-handling`: Proper error detection, reporting, and propagation in `set-project init` and its helper functions (`deploy_set_tools`, `_register_mcp_server`, `_cleanup_deprecated_memory_refs`)

### Modified Capabilities

- `project-init-deploy`: The deployment flow now has error checking — steps that fail are reported as warnings/errors instead of success

## Impact

- **Code**: `bin/set-project` — `deploy_set_tools()`, `_register_mcp_server()`, `_cleanup_deprecated_memory_refs()`, `cmd_init()`
- **Behavior**: Users will see actual error messages when `claude mcp add` or other steps fail, instead of a misleading "success" line
- **No breaking changes**: The happy path behavior is identical; only the failure path changes from silent-success to visible-warning
