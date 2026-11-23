## 1. webServer log in retry context

- [ ] 1.1 Add `_extract_webserver_lines(output, max_lines=30)` helper in `modules/web/set_project_web/gates.py` — extracts lines matching `[WebServer]` prefix from combined e2e output [REQ: e2e-gate-retry-context-includes-webserver-log]
- [ ] 1.2 In timeout path (gates.py ~line 1501), append webServer log section to retry_context [REQ: e2e-gate-retry-context-includes-webserver-log]
- [ ] 1.3 In "no parseable failures" path (gates.py ~line 1636), append webServer log section to retry_context [REQ: e2e-gate-retry-context-includes-webserver-log]
- [ ] 1.4 Fallback: if no `[WebServer]` lines, append last 50 lines of raw output [REQ: e2e-gate-retry-context-includes-webserver-log]
- [ ] 1.5 Test: verify webServer lines extracted correctly from sample output [REQ: e2e-gate-retry-context-includes-webserver-log]

## 2. No-commit retry guard

- [ ] 2.1 In `verifier.py` `handle_change_done()`, before the verify gate pipeline starts, get HEAD commit and `last_gate_commit` from extras [REQ: no-commit-retry-does-not-consume-retry-budget]
- [ ] 2.2 If HEAD == last_gate_commit, log warning and re-dispatch without incrementing `verify_retry_count` [REQ: no-commit-retry-does-not-consume-retry-budget]
- [ ] 2.3 Test: mock worktree with same HEAD as last_gate_commit — verify retry count not incremented [REQ: no-commit-retry-does-not-consume-retry-budget]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN e2e gate times out AND output has [WebServer] lines THEN retry_context includes webServer log section [REQ: e2e-gate-retry-context-includes-webserver-log, scenario: webserver-timeout-includes-server-log]
- [ ] AC-2: WHEN e2e gate fails without parseable failures AND output has [WebServer] lines THEN retry_context includes webServer log [REQ: e2e-gate-retry-context-includes-webserver-log, scenario: crash-without-parseable-failures-includes-server-log]
- [ ] AC-3: WHEN e2e gate fails AND output has zero [WebServer] lines THEN retry_context includes last 50 raw lines [REQ: e2e-gate-retry-context-includes-webserver-log, scenario: no-webserver-lines-falls-back-to-raw-tail]
- [ ] AC-4: WHEN agent commits new work THEN verify_retry_count incremented normally [REQ: no-commit-retry-does-not-consume-retry-budget, scenario: agent-commits-new-work-normal-retry]
- [ ] AC-5: WHEN agent declares done without committing THEN verify_retry_count NOT incremented [REQ: no-commit-retry-does-not-consume-retry-budget, scenario: agent-declares-done-without-committing]
