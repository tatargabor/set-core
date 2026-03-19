## 1. Fix registration

- [x] 1.1 In `bin/set-project` `_register_mcp_server()`: remove `python` from `claude mcp add` command — run script directly via shebang
- [x] 1.2 In `bin/set-project` `_register_mcp_server()`: remove the `_is_mcp_registered` early-return so re-registration always happens (fixes stale configs)

## 2. Update spec

- [x] 2.1 Update `openspec/specs/mcp-memory-tools/spec.md` registration scenario to reflect shebang-based execution

## 3. Worktree-aware MCP registration

- [x] 3.1 In `bin/set-project` `_register_mcp_server()`: when called from a worktree (`$in_worktree == true`), also run `claude mcp add` scoped to the worktree's current path (in addition to the main repo)
- [x] 3.2 In `install.sh` `install_projects()`: after deploying to each main repo, enumerate its git worktrees via `git worktree list --porcelain` and run `set-project init` in each existing worktree directory

## 4. Always-on hook logging

- [x] 4.1 In `bin/wt-hook-memory`: add a lightweight always-on log line per event invocation to `/tmp/wt-hook-memory.log` (event name, timestamp, outcome) — independent of `WT_HOOK_DEBUG`
- [x] 4.2 Keep verbose/detail logging gated on `WT_HOOK_DEBUG=1` as before

## 5. Richer always-on logging

- [x] 5.1 In `bin/wt-hook-memory`: make `_log()` verbose by default — log search query, recall mode, confidence scores, and any key outcomes (memories saved/recalled) without requiring `WT_HOOK_DEBUG=1`

## 6. Fix MEMORY_SNIPPET citation instruction

- [x] 6.1 In `bin/set-project` MEMORY_SNIPPET: update the IMPORTANT instruction to include the "From memory:" citation rule (matching set-core' own CLAUDE.md) — the deployed snippet was missing `cite it explicitly (e.g., "From memory: ...")` and instead had the weaker `summarize what you know` wording
