## Why

Three related gaps in MCP registration and hook visibility:

1. `set-project init` hardcoded `python` as the MCP interpreter — broken on Linux where only `python3` exists (shebang fix already landed)
2. When `set-project init` runs from a worktree, MCP only gets registered for the worktree path, not the main repo — and `install.sh` never deploys to worktrees at all
3. Hook debug logging requires `WT_HOOK_DEBUG=1` or a sentinel file — there's no always-on lightweight log for production debugging

## What Changes

- ~~Remove hardcoded `python` — shebang-based execution~~ *(done)*
- Register MCP for both main repo AND current PWD when called from a worktree
- `install.sh::install_projects()` enumerates all git worktrees per project and deploys to each
- `wt-hook-memory`: always write a lightweight event line to `/tmp/wt-hook-memory.log`; verbose detail still gated on `WT_HOOK_DEBUG=1`

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `mcp-memory-tools`: registration now covers both main repo and worktree paths; always-on hook log
- `project-init-deploy`: `set-project init` from a worktree registers MCP for the worktree scope too; `install.sh` deploys to all worktrees

## Impact

- `bin/set-project`: `_register_mcp_server()` — register under both paths
- `install.sh`: `install_projects()` — add worktree enumeration per project
- `bin/wt-hook-memory`: lightweight always-on log line, verbose detail unchanged
