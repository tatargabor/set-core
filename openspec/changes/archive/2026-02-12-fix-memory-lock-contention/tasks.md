## 1. Banner Suppression

- [x] 1.1 Replace `run_shodh_python` function: remove the `| grep -v "^⭐"` pipe. Instead, prepend `import sys; sys._shodh_star_shown = True;` before the user code in the python3 `-c` argument.
- [x] 1.2 Verify the ⭐ banner no longer appears on stdout for all commands (health, remember, recall, list, status).

## 2. Error Visibility

- [x] 2.1 Replace `2>/dev/null` in `run_shodh_python` with `2>>"$log_file"` where log_file is `${storage_path}/set-memory.log`. Create a helper to resolve the log path.
- [x] 2.2 Ensure `cmd_health` still suppresses stderr (it's expected to fail silently when shodh-memory is not installed).
- [x] 2.3 Verify that Python exceptions during `remember` are written to the log file.

## 3. File Lock Serialization

- [x] 3.1 Add a `run_with_lock` wrapper function that uses `flock --timeout 10` on `/tmp/set-memory-<project>.lock`.
- [x] 3.2 Wrap all `run_shodh_python` calls in commands that open the DB (remember, recall, list, status) with `run_with_lock`.
- [x] 3.3 Ensure `cmd_health` does NOT use the lock (it only imports, doesn't open DB).

## 4. Exit Code Propagation

- [x] 4.1 Remove `|| true` from the `run_shodh_python` call in `cmd_remember`. Instead, check the exit code and log on failure, but still return 0 for graceful degradation (shodh not installed case handled separately).
- [x] 4.2 Verify that `cmd_remember` returns non-zero when the Python script fails (e.g., RocksDB error, bad input) but returns 0 when shodh-memory is not installed.

## 5. Verification

- [x] 5.1 Manual test: run concurrent `set-memory status --json` and `set-memory remember` — both should succeed (second waits for first).
- [x] 5.2 Manual test: verify error log is created at `<storage_path>/set-memory.log` when an error occurs.
- [x] 5.3 Manual test: verify no ⭐ banner appears in any command output.
- [x] 5.4 Clean up test memories created during investigation (PIPEFAIL-TEST, TEST-ENTRY, concurrent access test, duplicate readme-refresh entries).
