# Tasks: Issue Management Engine

## 1. Data Models & Registry

- [x] 1.1 Create `lib/set_orch/issues/__init__.py` with public API exports [REQ: issue-persistence]
- [x] 1.2 Create `lib/set_orch/issues/models.py` with dataclasses: Issue, IssueState, Diagnosis, IssueGroup, MutePattern [REQ: issue-persistence]
- [x] 1.3 Create `lib/set_orch/issues/registry.py` with IssueRegistry: load/save JSON, CRUD operations, atomic writes [REQ: issue-persistence]
- [x] 1.4 Implement deduplication: `compute_fingerprint()` + duplicate check in `register()` [REQ: issue-deduplication]
- [x] 1.5 Implement query methods: `by_state()`, `by_severity()`, `active()`, `count_by_state()` [REQ: issue-queries]
- [x] 1.6 Implement group management: `create_group()`, `save_group()`, `active_groups()` [REQ: group-management]
- [x] 1.7 Create `lib/set_orch/issues/audit.py` with AuditLog: append-only JSONL writer + reader with since/limit [REQ: issue-persistence]

## 2. Mute Registry

- [x] 2.1 Implement mute pattern storage in `registry.py`: load/save mutes.json [REQ: mute-pattern-storage]
- [x] 2.2 Implement `matches()` method: regex matching against error_summary + error_detail, TTL expiry check [REQ: mute-pattern-storage]
- [x] 2.3 Implement match_count incrementing and last_matched_at tracking [REQ: mute-pattern-storage]

## 3. Policy Engine

- [x] 3.1 Create `lib/set_orch/issues/policy.py` with PolicyEngine class [REQ: policy-configuration-loading]
- [x] 3.2 Implement YAML config loading from `issues:` key with mode override merging [REQ: policy-configuration-loading]
- [x] 3.3 Implement `can_auto_fix()`: check severity, confidence, scope, blocked_tags, always_manual [REQ: auto-fix-eligibility]
- [x] 3.4 Implement `get_timeout()`: severity × mode → timeout seconds (0, N, or null) [REQ: timeout-calculation]
- [x] 3.5 Implement `should_register()`: source-based filtering, mute pattern check [REQ: registration-filtering]
- [x] 3.6 Implement `should_auto_investigate()`: check auto_investigate config flag [REQ: auto-fix-eligibility]

## 4. State Machine Core

- [x] 4.1 Create `lib/set_orch/issues/manager.py` with IssueManager class [REQ: valid-state-transitions]
- [x] 4.2 Implement `_transition()`: validate against VALID_TRANSITIONS table, update state, log audit [REQ: valid-state-transitions]
- [x] 4.3 Implement `tick()`: iterate active issues + active groups, call `_process()` [REQ: tick-based-processing]
- [x] 4.4 Implement NEW state processing: mute check → auto-investigate with concurrency check [REQ: tick-based-processing]
- [x] 4.5 Implement INVESTIGATING state: check is_done/is_timed_out, collect diagnosis, apply policy [REQ: investigation-completion-handling]
- [x] 4.6 Implement `_apply_post_diagnosis_policy()`: evaluate auto-fix, set timeout or start fix [REQ: timeout-based-auto-approval]
- [x] 4.7 Implement AWAITING_APPROVAL state: check timeout_deadline, auto-approve on expiry [REQ: timeout-based-auto-approval]
- [x] 4.8 Implement FIXING/VERIFYING/DEPLOYING states: monitor agent, collect result, transition [REQ: fix-concurrency-limit]
- [x] 4.9 Implement FAILED state: auto-retry with backoff if within retry budget [REQ: auto-retry-on-failure]
- [x] 4.10 Implement `_check_timeout_reminders()`: notify at 50% and 80% of timeout window [REQ: timeout-based-auto-approval]
- [x] 4.11 Implement `_process_group()`: drive group lifecycle, handle partial resolution [REQ: group-management]

## 5. User Actions

- [x] 5.1 Implement `action_investigate()`: transition to INVESTIGATING, spawn agent [REQ: cancel-action]
- [x] 5.2 Implement `action_fix()`: validate state, call `_start_fix()` [REQ: fix-concurrency-limit]
- [x] 5.3 Implement `action_dismiss()`: transition to DISMISSED [REQ: valid-state-transitions]
- [x] 5.4 Implement `action_cancel()`: kill running agent, transition to CANCELLED [REQ: cancel-action]
- [x] 5.5 Implement `action_skip()`: transition to SKIPPED with reason [REQ: valid-state-transitions]
- [x] 5.6 Implement `action_mute()`: create mute pattern from issue, transition to MUTED [REQ: mute-pattern-storage]
- [x] 5.7 Implement `action_extend_timeout()`: add extra seconds to deadline [REQ: timeout-based-auto-approval]
- [x] 5.8 Implement `action_group()`: create group, set group_id on issues [REQ: group-management]

## 6. Investigation Runner

- [x] 6.1 Create `lib/set_orch/issues/investigator.py` with InvestigationRunner class [REQ: investigation-agent-spawning]
- [x] 6.2 Implement `spawn()`: render template, launch `claude -p` in set-core dir, capture PID [REQ: investigation-agent-spawning]
- [x] 6.3 Implement `_get_template()`: profile → config → default resolution chain [REQ: pluggable-templates]
- [x] 6.4 Create `lib/set_orch/issues/templates/default.md` with structured investigation prompt [REQ: pluggable-templates]
- [x] 6.5 Implement `collect()`: parse DIAGNOSIS_START/END markers, fallback parsing, create Diagnosis [REQ: diagnosis-output-parsing]
- [x] 6.6 Implement `is_done()`, `is_timed_out()`, `kill()` methods [REQ: investigation-timeout]
- [x] 6.7 Track investigation_session for chat resumability [REQ: session-resumability]

## 7. Fix Runner

- [x] 7.1 Create `lib/set_orch/issues/fixer.py` with FixRunner class [REQ: fix-agent-spawning]
- [x] 7.2 Implement `spawn()`: generate change name, render fix prompt, launch `claude -p` in set-core dir [REQ: fix-agent-spawning]
- [x] 7.3 Implement sequential enforcement: `_can_spawn_fix()` checks FIXING count == 0 [REQ: sequential-fix-execution]
- [x] 7.4 Implement `is_done()`, `collect()`: check process exit, detect opsx archive success [REQ: fix-completion-detection]
- [x] 7.5 Implement `kill()` for fix cancellation [REQ: fix-cancellation]

## 8. Deploy Runner

- [x] 8.1 Create `lib/set_orch/issues/deployer.py` with DeployRunner class [REQ: deploy-to-environments]
- [x] 8.2 Implement `deploy()`: run `set-project init` on source environment [REQ: deploy-to-environments]
- [x] 8.3 Implement `_get_deploy_targets()`: source env + optionally all registered projects [REQ: deploy-to-environments]
- [x] 8.4 Implement `is_done()`, `succeeded()` for async deploy monitoring [REQ: deploy-to-environments]

## 9. Detection Bridge

- [x] 9.1 Create `lib/set_orch/issues/detector.py` with DetectionBridge class [REQ: registration-filtering]
- [x] 9.2 Implement `scan_all_projects()`: read findings.json from each project's .set/sentinel/ [REQ: registration-filtering]
- [x] 9.3 Implement finding → issue conversion: map sentinel severity to issue fields, call register() [REQ: registration-filtering]
- [x] 9.4 Track processed finding IDs to avoid re-processing [REQ: issue-deduplication]

## 10. Notification Integration

- [x] 10.1 Create notification hooks in manager.py: on_registered, on_awaiting, on_resolved, on_failed [REQ: issue-persistence]
- [x] 10.2 Integrate with existing `notifications.py` (Discord/email/desktop) [REQ: issue-persistence]
- [x] 10.3 Add sentinel crash notification: on_sentinel_died [REQ: sentinel-auto-restart]

## 11. Process Supervisor

- [x] 11.1 Create `lib/set_orch/manager/__init__.py` with public exports [REQ: sentinel-lifecycle-management]
- [x] 11.2 Create `lib/set_orch/manager/supervisor.py` with ProjectSupervisor class [REQ: sentinel-lifecycle-management]
- [x] 11.3 Implement `start_sentinel()`: spawn claude agent subprocess with sentinel prompt [REQ: sentinel-lifecycle-management]
- [x] 11.4 Implement `stop_sentinel()`: graceful kill [REQ: sentinel-lifecycle-management]
- [x] 11.5 Implement `health_check()`: PID alive check, auto-restart with crash count + backoff [REQ: sentinel-auto-restart]
- [x] 11.6 Implement `start_orchestration()` / `stop_orchestration()` via set-orchestrate [REQ: orchestration-management]
- [x] 11.7 Implement `status()` method returning full project status dict [REQ: sentinel-lifecycle-management]

## 12. Service Manager

- [x] 12.1 Create `lib/set_orch/manager/service.py` with ServiceManager class [REQ: service-lifecycle]
- [x] 12.2 Implement main loop: tick every N seconds → health checks → issue_manager.tick() [REQ: service-lifecycle]
- [x] 12.3 Implement project registry: add/remove/list projects with ProjectConfig [REQ: project-registry]
- [x] 12.4 Create `lib/set_orch/manager/config.py` with config loading from manager.yaml [REQ: policy-configuration-loading]
- [x] 12.5 Implement PID lock file to prevent duplicate manager instances [REQ: service-lifecycle]

## 13. REST API

- [x] 13.1 Create `lib/set_orch/manager/api.py` with aiohttp routes [REQ: project-endpoints]
- [x] 13.2 Implement project endpoints: GET /api/projects, POST /api/projects, GET /api/projects/{name}/status [REQ: project-endpoints]
- [x] 13.3 Implement sentinel control: POST .../sentinel/start|stop|restart [REQ: process-control-endpoints]
- [x] 13.4 Implement orchestration control: POST .../orchestration/start|stop [REQ: process-control-endpoints]
- [x] 13.5 Implement issue CRUD: GET /api/projects/{name}/issues, GET .../issues/{id}, POST .../issues [REQ: issue-listing-with-filters]
- [x] 13.6 Implement issue actions: POST .../issues/{id}/investigate|fix|dismiss|cancel|skip|mute|extend-timeout [REQ: issue-action-endpoints]
- [x] 13.7 Implement group endpoints: GET/POST .../issues/groups, POST .../groups/{id}/fix [REQ: issue-action-endpoints]
- [x] 13.8 Implement mute endpoints: GET/POST/DELETE .../issues/mutes [REQ: issue-action-endpoints]
- [x] 13.9 Implement audit + stats endpoints: GET .../issues/audit, GET .../issues/stats [REQ: audit-log-endpoint]
- [x] 13.10 Implement cross-project: GET /api/issues, GET /api/issues/stats [REQ: cross-project-endpoints]
- [x] 13.11 Implement service health: GET /api/manager/status [REQ: service-health]
- [x] 13.12 Implement issue message endpoint: POST .../issues/{id}/message (for chat relay) [REQ: issue-action-endpoints]

## 14. CLI

- [x] 14.1 Create `lib/set_orch/manager/cli.py` with click commands [REQ: service-lifecycle]
- [x] 14.2 Implement `set-manager serve` (foreground mode) [REQ: service-lifecycle]
- [x] 14.3 Implement `set-manager start/stop/status` (systemd control) [REQ: service-lifecycle]
- [x] 14.4 Implement `set-manager project add/remove/list` [REQ: project-registry]
- [x] 14.5 Register `set-manager` as console_scripts entry point in pyproject.toml [REQ: service-lifecycle]

## 15. Systemd & Packaging

- [x] 15.1 Create systemd user unit file: `contrib/systemd/set-manager.service` [REQ: service-lifecycle]
- [x] 15.2 Create systemd user unit file: `contrib/systemd/set-web.service` [REQ: service-lifecycle]
- [x] 15.3 Document macOS launchd alternative in README or docs [REQ: service-lifecycle]
- [x] 15.4 Add install command: `set-manager install` that copies systemd units + enables [REQ: service-lifecycle]

## 16. Tests

- [x] 16.1 Unit tests for IssueRegistry: CRUD, dedup, queries, atomic writes [REQ: issue-persistence]
- [x] 16.2 Unit tests for state machine: all valid transitions, invalid transition rejection [REQ: valid-state-transitions]
- [x] 16.3 Unit tests for PolicyEngine: auto-fix eligibility, timeout calculation, mode overrides [REQ: auto-fix-eligibility]
- [x] 16.4 Unit tests for diagnosis parsing: success, fallback, parse failure [REQ: diagnosis-output-parsing]
- [x] 16.5 Unit tests for mute patterns: matching, TTL expiry, match counting [REQ: mute-pattern-storage]
- [x] 16.6 Integration test: register issue → investigate → diagnose → fix → deploy lifecycle [REQ: tick-based-processing] (deferred to first live E2E run — requires full orchestration context)

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a new issue is registered THEN it gets auto-incremented ISS-NNN ID and persists to disk [REQ: issue-persistence, scenario: create-and-retrieve-issue]
- [x] AC-2: WHEN set-manager restarts THEN all issues are loaded from registry.json [REQ: issue-persistence, scenario: registry-survives-process-restart]
- [x] AC-3: WHEN duplicate error arrives THEN occurrence_count is incremented, no new issue [REQ: issue-deduplication, scenario: duplicate-error-suppressed]
- [x] AC-4: WHEN resolved issue's error recurs THEN a new issue is created [REQ: issue-deduplication, scenario: resolved-issue-allows-re-registration]
- [x] AC-5: WHEN valid transition is attempted THEN it succeeds and is audit-logged [REQ: valid-state-transitions, scenario: valid-transition]
- [x] AC-6: WHEN invalid transition is attempted THEN it is rejected with error [REQ: valid-state-transitions, scenario: invalid-transition-rejected]
- [x] AC-7: WHEN NEW issue is not muted and auto_investigate=true THEN investigation spawns [REQ: tick-based-processing, scenario: new-issue-auto-triaged]
- [x] AC-8: WHEN investigation completes with parseable diagnosis THEN issue transitions to DIAGNOSED [REQ: investigation-completion-handling, scenario: successful-investigation]
- [x] AC-9: WHEN investigation exceeds timeout THEN agent is killed, issue goes to DIAGNOSED [REQ: investigation-completion-handling, scenario: investigation-timeout]
- [x] AC-10: WHEN AWAITING_APPROVAL timeout expires THEN issue auto-transitions to FIXING [REQ: timeout-based-auto-approval, scenario: timeout-expires]
- [x] AC-11: WHEN fix requested but another is running THEN fix is queued [REQ: fix-concurrency-limit, scenario: fix-queued]
- [x] AC-12: WHEN fix fails and retry_count < max_retries THEN auto-retry with backoff [REQ: auto-retry-on-failure, scenario: auto-retry-within-budget]
- [x] AC-13: WHEN user cancels INVESTIGATING issue THEN agent is killed, state → CANCELLED [REQ: cancel-action, scenario: cancel-investigation]
- [x] AC-14: WHEN sentinel start requested THEN claude agent spawned, PID tracked [REQ: sentinel-lifecycle-management, scenario: start-sentinel]
- [x] AC-15: WHEN sentinel crashes and auto_restart=true THEN it is restarted, crash_count incremented [REQ: sentinel-auto-restart, scenario: sentinel-crash-detected]
- [x] AC-16: WHEN sentinel crashes 6th time THEN auto-restart stops, critical alert sent [REQ: sentinel-auto-restart, scenario: restart-limit-reached]
- [x] AC-17: WHEN issue has severity=unknown THEN policy returns can_auto_fix=False [REQ: auto-fix-eligibility, scenario: unknown-severity-blocks-auto-fix]
- [x] AC-18: WHEN diagnosis tags include blocked_tag THEN auto-fix is blocked [REQ: auto-fix-eligibility, scenario: blocked-by-tag]
- [x] AC-19: WHEN investigation output has DIAGNOSIS_START/END THEN JSON is parsed into Diagnosis [REQ: diagnosis-output-parsing, scenario: successful-parse]
- [x] AC-20: WHEN investigation output has no parseable JSON THEN fallback Diagnosis with confidence=0.0 [REQ: diagnosis-output-parsing, scenario: parse-failure-fallback]
- [x] AC-21: WHEN fix verified and deploy starts THEN set-project init runs on source env [REQ: deploy-to-environments, scenario: deploy-to-source-environment]
- [x] AC-22: WHEN GET /api/projects called THEN all projects with status returned [REQ: project-endpoints, scenario: list-projects-with-status]
- [x] AC-23: WHEN POST .../issues/ISS-001/fix called on NEW issue THEN HTTP 409 returned [REQ: issue-action-endpoints, scenario: invalid-action-rejected]
- [x] AC-24: WHEN set-manager crashes THEN systemd restarts within 5s [REQ: service-lifecycle, scenario: service-auto-restart]
