# Tasks: fix-dedup-orphan-process

## 1. MCP server process group kill

- [x] 1.1 Refactor `_run_memory()` in `mcp-server/set_mcp_server.py` to use `subprocess.Popen` with `start_new_session=True` instead of `subprocess.run` [REQ: mcp-subprocess-cleanup-kills-process-groups]
- [x] 1.2 Add timeout handling with `os.killpg(proc.pid, signal.SIGKILL)` in the except block [REQ: mcp-subprocess-cleanup-kills-process-groups]
- [x] 1.3 Preserve existing return value behavior (stdout on success, error message on failure) [REQ: mcp-subprocess-cleanup-kills-process-groups]

## 2. Bash-level timeout in maintenance.sh

- [x] 2.1 Add `timeout 25` wrapper to `run_shodh_python` call in `cmd_dedup()` in `lib/memory/maintenance.sh` [REQ: dedup-process-timeout-prevents-orphan-processes]
- [x] 2.2 Handle timeout exit code (124) — return JSON `{"error": "timeout", "deleted_count": 0}` [REQ: dedup-process-timeout-prevents-orphan-processes]
- [x] 2.3 Add same `timeout 25` wrapper to `cmd_audit()` Python call [REQ: dedup-process-timeout-prevents-orphan-processes]
- [x] 2.4 Handle timeout exit code in audit — return JSON `{"error": "timeout", "total": 0}` [REQ: dedup-process-timeout-prevents-orphan-processes]

## 3. Testing

- [x] 3.1 Add unit test: `_run_memory()` kills process group on timeout (mock slow subprocess) [REQ: mcp-subprocess-cleanup-kills-process-groups]
- [x] 3.2 Add unit test: `_run_memory()` normal call returns expected output [REQ: mcp-subprocess-cleanup-kills-process-groups]
- [x] 3.3 Add shell test: verify `cmd_dedup` timeout returns correct JSON [REQ: dedup-process-timeout-prevents-orphan-processes]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `set-memory dedup` runs and Python computation exceeds 25 seconds THEN process is killed and returns `{"error": "timeout", "deleted_count": 0}` [REQ: dedup-process-timeout-prevents-orphan-processes, scenario: dedup-times-out-on-large-memory-store]
- [x] AC-2: WHEN `set-memory audit` runs and Python computation exceeds 25 seconds THEN process is killed and returns timeout indicator [REQ: dedup-process-timeout-prevents-orphan-processes, scenario: audit-times-out-on-large-memory-store]
- [x] AC-3: WHEN MCP tool calls `set-memory dedup` and subprocess exceeds timeout THEN entire process group is terminated with no orphans [REQ: mcp-subprocess-cleanup-kills-process-groups, scenario: mcp-dedup-timeout-kills-all-children]
- [x] AC-4: WHEN MCP `dedup()` completes within timeout THEN behavior is identical to before [REQ: mcp-subprocess-cleanup-kills-process-groups, scenario: normal-mcp-calls-unaffected]
