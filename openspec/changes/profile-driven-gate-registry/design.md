# Design: profile-driven-gate-registry

## Context

The gate pipeline currently has 9 hardcoded gate types in `GateConfig` (build, test, e2e, scope_check, test_files, lint, review, rules, spec_verify) plus smoke in merger.py. Of these, e2e, lint, and smoke are web-specific. The `GatePipeline` in `handle_change_done` registers all 9 gates with hardcoded lambda executors.

The `BUILTIN_GATE_PROFILES` dict maps change_type → GateConfig with fixed field defaults per type. Profile plugins can only override modes via `gate_overrides()` dict — they cannot add new gate types or remove irrelevant ones.

Additionally, merger.py contains ~170 lines of dead smoke pipeline code (`_run_smoke_pipeline`, `_blocking_smoke_pipeline`, `_nonblocking_smoke_pipeline`) that is never called — the ff-only merge strategy made post-merge smoke redundant. The merger also hardcodes web-specific post-merge logic (i18n sidecar merge, deps install) that should be profile-driven.

## Goals / Non-Goals

**Goals:**
- Profile defines which domain-specific gates exist (register_gates)
- Gate executors for domain-specific gates live in modules, not core
- GateConfig supports arbitrary gate names (not fixed dataclass fields)
- BUILTIN_GATE_PROFILES replaced by universal defaults + profile defaults
- Existing web project behavior preserved exactly
- Dead smoke pipeline code removed from merger.py
- Post-merge web-specific logic moved to profile hooks
- commit_results supports dynamic gate names (not hardcoded field_map)

**Non-Goals:**
- GateContext dataclass (separate change — too much blast radius rewriting all executors)
- Dynamic gate ordering at runtime (position hints resolved at registration)
- Changing the GatePipeline execution engine (register + run stays the same)

## Decisions

### D1: GateDefinition dataclass

```python
@dataclass
class GateDefinition:
    name: str
    executor: GateExecutor  # callable → GateResult
    position: str = "end"   # "after:test", "before:review", "end"
    phase: str = "pre-merge"  # "pre-merge" or "post-merge"
    defaults: dict = field(default_factory=dict)
    # defaults: {change_type: mode} e.g. {"infrastructure": "skip", "feature": "run"}
    own_retry_counter: str = ""  # e.g. "build_fix_attempt_count"
    extra_retries: int = 0
    # Optional: field mapping for commit_results (state field name, timing field name)
    result_fields: tuple[str, str] | None = None  # e.g. ("build_result", "gate_build_ms")
```

Lives in `lib/set_orch/gate_runner.py` alongside GateResult and GatePipeline.

### D2: Universal gates defined in core

```python
# lib/set_orch/verifier.py
UNIVERSAL_GATES = [
    GateDefinition("build", _execute_build_gate, position="start",
                   own_retry_counter="build_fix_attempt_count",
                   result_fields=("build_result", "gate_build_ms")),
    GateDefinition("test", _execute_test_gate, position="after:build",
                   result_fields=("test_result", "gate_test_ms")),
    GateDefinition("scope_check", _execute_scope_gate, position="after:test"),
    GateDefinition("test_files", _execute_test_files_gate, position="after:scope_check"),
    GateDefinition("review", _execute_review_gate, position="before:end",
                   extra_retries=3,
                   result_fields=("review_result", "gate_review_ms")),
    GateDefinition("rules", _execute_rules_gate, position="after:review"),
    GateDefinition("spec_verify", _execute_spec_verify_gate, position="end",
                   result_fields=("spec_coverage_result", "gate_verify_ms")),
]
```

### D3: Profile registers domain gates

```python
# modules/web/set_project_web/gates.py
def web_gates(profile) -> list[GateDefinition]:
    return [
        GateDefinition(
            "e2e",
            lambda **ctx: execute_e2e_gate(**ctx),
            position="after:test",
            defaults={
                "infrastructure": "skip", "schema": "skip",
                "foundational": "skip", "feature": "run",
                "cleanup-before": "skip", "cleanup-after": "skip",
            },
            result_fields=("e2e_result", "gate_e2e_ms"),
        ),
        GateDefinition(
            "lint",
            lambda **ctx: execute_lint_gate(**ctx),
            position="after:test_files",
            defaults={
                "infrastructure": "skip", "schema": "warn",
                "foundational": "run", "feature": "run",
                "cleanup-before": "warn", "cleanup-after": "skip",
            },
        ),
    ]
```

No smoke gate — the ff-only merge strategy makes post-merge smoke redundant. The dead smoke pipeline code in merger.py is deleted.

### D4: GateConfig becomes dict-based

```python
class GateConfig:
    def __init__(self, gates: dict[str, str] = None, **kwargs):
        self._gates = gates or {}
        self.max_retries = kwargs.get("max_retries")
        self.review_model = kwargs.get("review_model")
        self.review_extra_retries = kwargs.get("review_extra_retries", 3)
        self.test_files_required = kwargs.get("test_files_required", True)

    def should_run(self, gate_name: str) -> bool:
        val = self._gates.get(gate_name, "run")
        return val in ("run", "warn", "soft")

    def is_blocking(self, gate_name: str) -> bool:
        return self._gates.get(gate_name, "run") == "run"

    def is_warn_only(self, gate_name: str) -> bool:
        val = self._gates.get(gate_name, "run")
        return val in ("warn", "soft")

    def get(self, gate_name: str) -> str:
        return self._gates.get(gate_name, "run")

    def set(self, gate_name: str, mode: str):
        self._gates[gate_name] = mode
```

### D5: resolve_gate_config uses registry

```python
def resolve_gate_config(change, profile=None, directives=None):
    change_type = getattr(change, "change_type", "feature")

    # Start with universal defaults (all "run")
    gates = {g.name: "run" for g in UNIVERSAL_GATES}

    # Apply universal change_type defaults
    gates.update(UNIVERSAL_DEFAULTS.get(change_type, {}))

    # Add profile gates with their defaults
    if profile and hasattr(profile, "register_gates"):
        for gd in profile.register_gates():
            if gd.phase != "pre-merge":
                continue
            gates[gd.name] = gd.defaults.get(change_type, "run")

    # Apply profile overrides (existing gate_overrides method)
    if profile and hasattr(profile, "gate_overrides"):
        overrides = profile.gate_overrides(change_type)
        gates.update(overrides)

    # Apply per-change overrides
    # Apply directive overrides

    return GateConfig(gates=gates, ...)
```

### D6: Pipeline registration becomes dynamic

```python
# In handle_change_done:
all_gates = list(UNIVERSAL_GATES)
if profile and hasattr(profile, "register_gates"):
    all_gates.extend(g for g in profile.register_gates() if g.phase == "pre-merge")

# Sort by position hints
ordered = _resolve_gate_order(all_gates)

for gd in ordered:
    if not gc.should_run(gd.name):
        continue
    pipeline.register(
        gd.name,
        lambda gd=gd: gd.executor(change_name=..., change=..., wt_path=..., ...),
        own_retry_counter=gd.own_retry_counter,
        extra_retries=gd.extra_retries,
    )
```

Executors keep their current signatures — no GateContext refactor. The lambda wrappers pass executor-specific params as today.

### D7: Position hint algorithm

Topological sort with these rules:
- `"start"` — index 0
- `"after:X"` — immediately after gate X
- `"before:X"` — immediately before gate X
- `"before:end"` — before the last gate
- `"end"` — last position

Universal gates maintain their relative order. Profile gates are inserted at their position hint. On circular dependency, profile gates append at end.

### D8: Backwards compat — test_files_required

`test_files_required` is a boolean, not a gate mode. It stays as a GateConfig attribute (not in the gates dict). Same for `max_retries`, `review_model`, `review_extra_retries`.

### D9: commit_results becomes dynamic

The hardcoded `gate_field_map` in `GatePipeline.commit_results()` is replaced by reading `result_fields` from GateDefinition. Gates without `result_fields` write to `extras["{gate_name}_result"]`. This allows profile-registered gates to have proper state tracking.

### D10: Merger cleanup — dead code and web-specific logic

**Dead smoke code removed:**
- `_run_smoke_pipeline`, `_blocking_smoke_pipeline`, `_nonblocking_smoke_pipeline` — never called (ff-only merge made them obsolete)
- `_collect_smoke_screenshots` in merger.py — only called by the dead smoke functions
- `GateConfig.smoke` field — not needed in dict-based config (no pre-merge smoke gate)

**Web-specific post-merge logic moved to profile:**
- `merge_i18n_sidecars()` → `modules/web/set_project_web/post_merge.py` — called via `profile.post_merge_hooks()`
- `_post_merge_deps_install()` simplified — delegates to `profile.post_merge_install()` which already exists

**Merger ff-success path becomes:**
```python
# After ff merge succeeds:
1. status = "merged", git tag, coverage update     # merge mechanics
2. profile.post_merge_install(".")                  # profile handles deps
3. _post_merge_custom_command(state_file)            # directives (thin)
4. profile.post_merge_hooks(change_name, state_file) # profile hooks (i18n, etc.)
5. _run_hook("post_merge", ...)                      # hook system
6. cleanup + archive + sync                          # merge mechanics
```

**New profile method:**
```python
# In ProjectType ABC:
def post_merge_hooks(self, change_name: str, state_file: str) -> None:
    """Run profile-specific post-merge operations (i18n, codegen, etc.)."""
    pass

# In WebProjectType:
def post_merge_hooks(self, change_name: str, state_file: str) -> None:
    from .post_merge import merge_i18n_sidecars
    count = merge_i18n_sidecars(".")
    if count > 0:
        # git add + commit handled by caller or here
        ...
```

### D11: Merge queue simplification — integrate-then-ff

The current merge flow has bugs and unnecessary complexity:
- `_try_merge` integrates main into branch but **doesn't check** if integration succeeded
- On ff-fail, `merge_change` sets status="done" → re-queue → retry loop
- `merge_retry_count`, `ff_retry_count`, conflict fingerprint dedup add complexity for a case that shouldn't happen

**Key insight:** if integration succeeds (no conflict), ff-only MUST succeed because the branch is now a descendant of main. So ff-fail retry logic is unnecessary.

**New merge queue flow:**
```python
def execute_merge_queue(state_file, event_bus=None):
    """Drain merge queue. Each change integrates fresh main before ff-only."""
    state = load_state(state_file)
    merged = 0
    for name in list(state.merge_queue):
        change = _find_change(state, name)
        wt_path = change.worktree_path if change else ""

        # Step 1: Integrate current main into branch (CHECKED)
        if wt_path and os.path.isdir(wt_path):
            integration = _integrate_for_merge(wt_path, name)
            if integration == "conflict":
                update_change_field(state_file, name, "status", "merge-blocked")
                _remove_from_merge_queue(state_file, name)
                continue
            # integration == "ok" → branch is now ahead of main → ff will work

        # Step 2: ff-only merge (guaranteed to succeed after clean integration)
        result = _ff_merge(name, state_file, event_bus=event_bus)
        if result.success:
            merged += 1
            # main has advanced — next change will integrate against fresh main

        # Re-read state for next iteration (main changed)
        state = load_state(state_file)
    return merged
```

**Removed:**
- `_try_merge()` — replaced by integrate-then-ff in queue loop
- `merge_retry_count` / `MAX_MERGE_RETRIES` — no retries needed
- `ff_retry_count` / `max_ff_retries` — ff always works after integration
- `_compute_conflict_fingerprint()` / fingerprint dedup — conflict = blocked immediately
- `merge_change` ff-fail path (status="done" re-queue) — no ff-fail possible

**Kept:**
- `merge_change()` simplified to only handle the ff-only + post-merge steps (no integration, no ff-fail path)
- `retry_merge_queue()` still retries merge-blocked with fresh integration
- Conflict handling: integration conflict → `merge-blocked` → `retry_merge_queue` can retry later (after other merges may have resolved the conflict source)
