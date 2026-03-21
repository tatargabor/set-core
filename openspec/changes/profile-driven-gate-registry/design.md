# Design: profile-driven-gate-registry

## Context

The gate pipeline currently has 9 hardcoded gate types in `GateConfig` (build, test, e2e, scope_check, test_files, lint, review, rules, spec_verify) plus smoke in merger.py. Of these, e2e, lint, and smoke are web-specific. The `GatePipeline` in `handle_change_done` registers all 9 gates with hardcoded lambda executors.

The `BUILTIN_GATE_PROFILES` dict maps change_type → GateConfig with fixed field defaults per type. Profile plugins can only override modes via `gate_overrides()` dict — they cannot add new gate types or remove irrelevant ones.

## Goals / Non-Goals

**Goals:**
- Profile defines which domain-specific gates exist (register_gates)
- Gate executors for domain-specific gates live in modules, not core
- GateConfig supports arbitrary gate names (not fixed dataclass fields)
- BUILTIN_GATE_PROFILES replaced by universal defaults + profile defaults
- Existing web project behavior preserved exactly

**Non-Goals:**
- Dynamic gate ordering (position hints are enough)
- Runtime gate type modification (gates are fixed per profile load)
- Changing the GatePipeline execution engine (register + run stays the same)
- Moving post-merge smoke to pre-merge (stays in merger.py)

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
```

Lives in `lib/set_orch/gate_runner.py` alongside GateResult and GatePipeline.

### D2: Universal gates defined in core

```python
# lib/set_orch/verifier.py (or new gate_executors.py)
UNIVERSAL_GATES = [
    GateDefinition("build", _execute_build_gate, position="start", own_retry_counter="build_fix_attempt_count"),
    GateDefinition("test", _execute_test_gate, position="after:build"),
    GateDefinition("scope_check", _execute_scope_gate, position="after:test"),
    GateDefinition("test_files", _execute_test_files_gate, position="after:scope_check"),
    GateDefinition("review", _execute_review_gate, position="before:end", extra_retries=3),
    GateDefinition("rules", _execute_rules_gate, position="after:review"),
    GateDefinition("spec_verify", _execute_spec_verify_gate, position="end"),
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

# In WebProjectType:
def register_gates(self) -> list[GateDefinition]:
    from .gates import web_gates
    return web_gates(self)
```

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
    all_gates.extend(profile.register_gates())

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

### D7: Gate executor context

Gate executors receive a standard context dict:
```python
@dataclass
class GateContext:
    change_name: str
    change: Change
    wt_path: str
    profile: Any
    state_file: str
    gc: GateConfig
    verify_retry_count: int
    event_bus: Any
    # Plus gate-specific kwargs
```

This replaces the per-gate lambda parameter lists.

### D8: Backwards compat — test_files_required

`test_files_required` is a boolean, not a gate mode. It stays as a GateConfig attribute (not in the gates dict). Same for `max_retries`, `review_model`, `review_extra_retries`.

### D9: Smoke gate (post-merge)

Smoke gates are `phase="post-merge"` in the GateDefinition. The merger.py collects post-merge gates from the profile separately and runs them after merge. This is a separate pipeline from pre-merge gates.
