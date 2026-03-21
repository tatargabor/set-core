# Proposal: profile-driven-gate-registry

## Why

The gate system has web-specific gates (e2e, lint, smoke) hardcoded in set-core's `GateConfig` dataclass and `verifier.py`. A Python project doesn't need Playwright E2E or web linting — it needs mypy, ruff, and coverage gates. Currently there's no way for a project-type profile to define its own gate types; it can only override the mode (run/warn/skip) of the hardcoded gates.

This became apparent during the monorepo migration: web-specific gate executors (`_execute_e2e_gate`, `_execute_lint_gate`) were initially placed in set-core core, violating the modular architecture rule. They were partially cleaned up but the gate *definitions* and *executors* still live in core.

## What Changes

### Gate type classification

**Universal gates** (stay in set-core core — every project needs these):
- `build` — compile/transpile check
- `test` — unit/integration test runner
- `scope_check` — verify implementation files exist
- `test_files` — verify test files exist
- `review` — LLM code review
- `rules` — project-knowledge.yaml verification rules
- `spec_verify` — OpenSpec coverage check

**Domain-specific gates** (move to modules — project-type dependent):
- `e2e` → modules/web (Playwright)
- `lint` → modules/web (forbidden patterns for TS/TSX)
- `smoke` → modules/web (post-merge health check)
- Future: `mypy`, `ruff`, `coverage` → modules/python

### Profile gate registration

Profiles gain a `register_gates()` method returning a list of gate definitions:

```python
class WebProjectType(CoreProfile):
    def register_gates(self) -> list[GateDefinition]:
        return [
            GateDefinition(
                name="e2e",
                executor=web_e2e_executor,
                position="after:test",  # pipeline ordering
                defaults={"infrastructure": "skip", "feature": "run", ...},
            ),
            GateDefinition(
                name="lint",
                executor=web_lint_executor,
                position="after:test_files",
                defaults={"infrastructure": "skip", "feature": "run", ...},
            ),
            GateDefinition(
                name="smoke",
                executor=web_smoke_executor,
                phase="post-merge",
                defaults={"feature": "run", ...},
            ),
        ]
```

### GateConfig becomes dynamic

Instead of a `@dataclass` with fixed fields, `GateConfig` becomes a dict-like object that stores `{gate_name: mode}` pairs. Universal gates are always present; profile gates are added at resolution time.

### Gate executors move to modules

- `_execute_e2e_gate` → `modules/web/set_project_web/gates.py`
- `_execute_lint_gate` → `modules/web/set_project_web/gates.py`
- `_execute_smoke_*` (from merger.py) → `modules/web/set_project_web/gates.py`

The core `verifier.py` only keeps universal gate executors (build, test, scope, review, rules, spec_verify).

### GatePipeline accepts dynamic gates

The pipeline registration in `handle_change_done` changes from a hardcoded list to a profile-driven loop:

```python
# Register universal gates
for gate in UNIVERSAL_GATES:
    pipeline.register(gate.name, gate.executor)

# Register profile gates (in defined order)
for gate in profile.register_gates():
    pipeline.register(gate.name, gate.executor)
```

## Capabilities

### New Capabilities
- `gate-registry`: Profile-driven gate type registration with ordering and defaults
- `gate-definition`: GateDefinition dataclass for declaring gates with executors and defaults

### Modified Capabilities
- `gate-profiles`: GateConfig becomes dynamic (dict-based, not fixed dataclass fields)
- `verify-gate`: handle_change_done uses registered gates instead of hardcoded list
- `web-profile`: WebProjectType.register_gates() provides e2e, lint, smoke

## Impact

- **Files modified**: `lib/set_orch/gate_profiles.py` (major refactor), `lib/set_orch/gate_runner.py` (GateDefinition), `lib/set_orch/verifier.py` (remove domain-specific executors, use registry), `lib/set_orch/profile_types.py` (register_gates interface), `modules/web/set_project_web/gates.py` (new — moved executors)
- **Risk**: High — touches the critical verify pipeline. Must preserve exact behavior for existing web projects.
- **Tests**: Existing gate_profiles tests refactored; new tests for dynamic registration
