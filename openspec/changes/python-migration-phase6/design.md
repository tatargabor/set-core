## Architecture

### Module: `lib/wt_orch/verifier.py`

1:1 function migration from `lib/orchestration/verifier.sh` (1453 lines). Four logical groups:

**Gate Pipeline** — the core verify gate (`handle_change_done`) orchestrates:
build → test → e2e → scope check → test file check → code review → verification rules → spec verify → merge queue

**Test & Review** — `run_tests_in_worktree`, `review_change`, `build_req_review_section`, `evaluate_verification_rules`

**Smoke & E2E** — `extract_health_check_url`, `health_check`, `smoke_fix_scoped`, `run_phase_end_e2e`

**Polling** — `poll_change` reads loop-state.json and dispatches to `handle_change_done` or marks stalled

### Function Mapping

| Bash function | Python function | Notes |
|---|---|---|
| `run_tests_in_worktree` | `run_tests_in_worktree()` | Returns `TestResult` dataclass |
| `build_req_review_section` | `build_req_review_section()` | JSON stdlib instead of jq |
| `review_change` | `review_change()` | Returns `ReviewResult` dataclass |
| `evaluate_verification_rules` | `evaluate_verification_rules()` | yq → yaml.safe_load |
| `verify_merge_scope` | `verify_merge_scope()` | Post-merge check |
| `verify_implementation_scope` | `verify_implementation_scope()` | Pre-merge check |
| `extract_health_check_url` | `extract_health_check_url()` | Pure regex |
| `health_check` | `health_check()` | urllib instead of curl |
| `smoke_fix_scoped` | `smoke_fix_scoped()` | Subprocess orchestration |
| `run_phase_end_e2e` | `run_phase_end_e2e()` | Phase-end Playwright on main |
| `poll_change` | `poll_change()` | Loop-state parser + dispatcher |
| `handle_change_done` | `handle_change_done()` | Full gate pipeline |
| `_collect_smoke_screenshots` | `_collect_smoke_screenshots()` | Internal helper |

### Data Structures

```python
@dataclass
class TestResult:
    passed: bool
    output: str
    exit_code: int
    stats: dict | None = None  # {passed: N, failed: N, suites: N, type: "jest"|"playwright"}

@dataclass
class ReviewResult:
    has_critical: bool
    output: str

@dataclass
class ScopeCheckResult:
    has_implementation: bool
    first_impl_file: str = ""
    all_files: list[str] = field(default_factory=list)

@dataclass
class VerifyGateResult:
    passed: bool
    build_ms: int = 0
    test_ms: int = 0
    e2e_ms: int = 0
    review_ms: int = 0
    verify_ms: int = 0
    total_ms: int = 0
```

### CLI Bridge

New `wt-orch-core verify` subcommand group:

```
wt-orch-core verify run-tests --wt-path PATH --command CMD [--timeout N] [--max-chars N]
wt-orch-core verify review --change NAME --wt-path PATH --scope SCOPE [--model MODEL]
wt-orch-core verify evaluate-rules --change NAME --wt-path PATH
wt-orch-core verify check-merge-scope --change NAME
wt-orch-core verify check-impl-scope --change NAME --wt-path PATH
wt-orch-core verify health-check --url URL [--timeout N]
wt-orch-core verify poll --change NAME --state-file PATH [full args]
wt-orch-core verify handle-done --change NAME --state-file PATH [full args]
wt-orch-core verify smoke-fix --change NAME --smoke-cmd CMD [opts]
wt-orch-core verify phase-e2e --command CMD [--timeout N] --state-file PATH
wt-orch-core verify build-req-section --change NAME --state-file PATH
wt-orch-core verify extract-health-url --smoke-cmd CMD
```

### Dependencies

- `wt_orch.state` — `locked_state`, `update_change_field`, `update_state_field`, `Change`, `OrchestratorState`
- `wt_orch.events` — `EventBus.emit()`
- `wt_orch.subprocess_utils` — `run_command()`, `run_git()`, `CommandResult`
- `wt_orch.process` — `check_pid()`
- `wt_orch.notifications` — `send_notification()`
- `wt_orch.dispatcher` — `resume_change()`, `sync_worktree_with_main()`

### Design Decisions

1. **`poll_change` and `handle_change_done` stay callable from bash** — the monitor_loop (phase 7) calls these per-change. Thin bash wrappers delegate to Python via CLI bridge.
2. **No yaml dependency for `evaluate_verification_rules`** — use subprocess `yq` call like bash does, or attempt `yaml.safe_load` with fallback. Since project-knowledge.yaml is optional, graceful degradation if neither available.
3. **Test output parsing** — regex patterns for Jest/Vitest/Playwright output format preserved exactly from bash.
4. **Health check** — `urllib.request` replaces `curl`, with timeout parameter.
5. **Smoke fix** — subprocess orchestration for `run_claude` calls, same retry loop structure.
