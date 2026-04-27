# Design: Diagnostic Pipeline

## Technical Decisions

### 1. DiagnosticRule as Abstract Base Class in set-core

The core framework provides `DiagnosticRule` ABC and `DiagnosticRunner`. Project types (set-project-web, etc.) implement concrete rules via the profile interface.

```
set-core (lib/set_orch/diagnostic.py)
  ├─ DiagnosticContext     — failure data (build output, review, state)
  ├─ DiagnosticResult      — action + config changes + report
  ├─ DiagnosticRule (ABC)  — abstract diagnose() method
  ├─ DiagnosticRunner      — executes rules, applies fixes
  └─ Built-in rules:
      ├─ DependencyCascadeRule    — skip downstream on dep failure
      ├─ ContextOverflowRule      — detect overflow, upgrade model
      └─ StaleWorktreeRule        — detect artifact-only branch

set-project-web (diagnostics/)
  ├─ PrismaClientRule      — detect missing prisma generate
  ├─ MissingDepsRule       — detect npm module not found
  └─ MergeGapRule          — detect cross-branch type/i18n gaps
```

**Why ABC, not config-only**: Config can declare policy ("diagnose on failure") but can't analyze build output or match error patterns. Python rules can parse TypeScript errors, detect Prisma-specific patterns, and decide the right fix.

### 2. Profile Interface Extension

Add `diagnostic_rules()` to the existing `NullProfile` in `profile_loader.py`:

```python
class NullProfile:
    # ... existing methods ...

    def diagnostic_rules(self) -> list:
        """Return project-type-specific diagnostic rules.

        Rules are executed in order when a failure occurs.
        First rule that returns a non-None result wins.
        """
        return []
```

set-project-web's profile implements this with web-specific rules:

```python
class WebProfile(NullProfile):
    def diagnostic_rules(self):
        from .diagnostics import prisma_client, missing_deps, merge_gap
        return [
            prisma_client.PrismaClientRule(),
            missing_deps.MissingDepsRule(),
            merge_gap.MergeGapRule(),
        ]
```

### 3. DiagnosticContext — What the Rule Sees

```python
@dataclass
class DiagnosticContext:
    change_name: str
    failure_type: str          # "verify_exhausted", "merge_blocked", "build_broken", "smoke_failed"
    build_output: str          # last build/smoke stderr (up to 10K)
    review_output: str         # last review gate output
    merge_output: str          # last merge attempt output
    state_file: str            # path to orchestration-state.json
    wt_path: str               # worktree path (if exists)
    config_path: str           # path to config.yaml
    change: Change             # full change object from state
    verify_retry_count: int
    tokens_used: int
```

### 4. DiagnosticResult — What the Rule Can Do

```python
@dataclass
class DiagnosticResult:
    action: str                # "fix_config", "retry", "skip", "escalate", "skip_downstream"

    # Config-level fixes (the rule's "safe zone")
    config_patches: dict       # key-value patches for config.yaml
    gitattributes_rules: list  # .gitattributes lines to add
    directive_overrides: dict  # directives.json patches
    state_patches: dict        # orchestration-state.json field updates

    # Retry enrichment
    retry_context: str         # inject into agent's retry prompt
    model_override: str        # e.g., "opus-1m" for context overflow

    # Reporting
    report: str                # human-readable finding
    severity: str              # "fix", "workaround", "escalate"
    bug_number: int            # reference to known bug (e.g., 29)
```

**What rules CAN do**:
- Modify config.yaml (post_merge_command, model routing, retry limits)
- Add .gitattributes merge strategies
- Reset change status (pending, retry)
- Skip downstream changes (dependency cascade fix)
- Inject retry context for the agent
- Override model for a specific change
- Write findings to E2E report files

**What rules CANNOT do**:
- Modify source code (src/, app/, components/)
- Change the orchestration Python code itself
- Delete or create git branches
- Merge changes

### 5. Integration Points in Engine

Three failure paths in the monitor loop trigger diagnostics:

```
engine.py monitor_loop:
  │
  ├─ verify exhausted (change.status = "failed")
  │   └─ BEFORE marking failed: run_diagnostics(ctx)
  │      ├─ result.action == "retry"  → reset retry count, resume
  │      ├─ result.action == "fix_config" → apply patches, retry
  │      ├─ result.action == "skip_downstream" → propagate failure
  │      └─ result.action == "escalate" → mark failed (existing behavior)
  │
  ├─ merge-blocked (merge retries exhausted)
  │   └─ BEFORE giving up: run_diagnostics(ctx)
  │      (same action handling)
  │
  └─ build_broken_on_main (post-merge smoke fails)
      └─ INSTEAD of simple retry: run_diagnostics(ctx)
         ├─ PrismaClientRule → config_patches: {post_merge_command: "npx prisma generate"}
         ├─ MissingDepsRule → run pnpm install, retry
         └─ escalate → set flag (existing behavior)
```

### 6. Dependency Cascade Handling (Built-in Rule)

The `DependencyCascadeRule` is a core built-in (not project-type-specific):

```
When change X fails:
  1. Find all changes that depend on X (directly or transitively)
  2. For each dependent:
     a. If all other deps are met → mark "dep_blocked" (new status)
     b. If config says skip_downstream → mark "skipped" with reason
  3. Emit DEPENDENCY_CASCADE event
  4. If auto_replan enabled → trigger replan without the failed change
```

This directly fixes Bug #26 (dependency cascade deadlock) — instead of leaving 12 changes pending forever, they get explicitly marked.

### 7. Config Integration

```yaml
# config.yaml
diagnostics:
  enabled: true                    # default: true
  on_verify_exhausted: diagnose    # diagnose | fail (default: diagnose)
  on_merge_blocked: diagnose       # diagnose | fail
  on_build_broken: diagnose        # diagnose | fail
  on_dependency_failed: skip       # skip | block | replan
  max_diagnostic_retries: 1        # how many times diagnostic can retry a change
```

### 8. Findings Reporting

When a diagnostic rule fires, it writes:
1. **Memory** (`set-memory remember`) — for future sessions
2. **State extras** — `change.extras.diagnostic_history` array
3. **Log** — structured log line for the monitor
4. **Event** — `DIAGNOSTIC_FIRED` event in events.jsonl
