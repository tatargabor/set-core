## Context

The orchestration verification pipeline (verifier.py `handle_change_done()`) runs 7 sequential gates for every change: build → test → e2e → scope → test-files → review → rules → spec-verify. The only change_type-aware logic is a single check at line 1406 that blocks on missing test files for feature/infrastructure/foundational types.

Post-merge smoke runs in merger.py unconditionally if `smoke_command` is configured.

This means infrastructure changes (test framework setup, CI config) run build/test/e2e/smoke gates against a non-existent app, causing false failures that consume the shared `max_verify_retries=2` budget. E2E runs #4, #13, #14 confirm 200-400k wasted tokens per run from these false positives.

The project-type plugin system (profile_loader.py → ProjectType ABC in set-project-base) already provides extension points for project-specific behavior (planning_rules, security_rules_paths, detect_test_command, etc.) but has no gate configuration hook.

## Goals / Non-Goals

**Goals:**
- Map each `change_type` to a gate configuration that determines which gates run, skip, or warn
- Provide a 4-level override chain: built-in defaults → profile plugin → per-change hints → directive overrides
- Zero breaking changes — feature type behaves identically to current all-gates-run behavior
- Project-type plugins (set-project-web) can customize gate behavior per change_type
- Planner LLM understands gate profiles are automatic from change_type (no extra burden)

**Non-Goals:**
- Runtime gate decisions based on app state (e.g., "is dev server running?") — too complex, fragile
- New change_types beyond the existing 6 — start with current types, add later based on data
- Per-file or per-directory gate configuration — change_type granularity is sufficient
- Automatic change_type detection from diff — planner already assigns this

## Decisions

### D1: GateConfig dataclass as single resolution output

**Decision**: A `GateConfig` dataclass with one field per gate (build, test, e2e, scope_check, review, spec_verify, rules, smoke) plus `test_files_required`, `max_retries`, `review_model`.

**Why**: Simple, inspectable, serializable. Each field is a string mode (`"run"`, `"skip"`, `"warn"`, `"soft"`) which is more expressive than boolean skip flags.

**Alternative considered**: Dict-based config — rejected because no IDE autocomplete, no default values, easy to typo keys.

### D2: Built-in profiles keyed by change_type string

**Decision**: `BUILTIN_GATE_PROFILES: dict[str, GateConfig]` in a new `gate_profiles.py` module. Unknown types fall back to feature profile (all gates run).

**Why**: The 6 change_types already exist in the planner output. No new metadata needed — just map existing types to gate configs. Feature as default is the safest fallback (never accidentally skip gates).

**Alternative considered**: Separate `gate_profile` field in plan JSON — rejected because it duplicates change_type. The LLM already decides change_type; deriving gates from it avoids a second decision point.

### D3: Profile plugin override via gate_overrides() method

**Decision**: Add `gate_overrides(change_type: str) -> dict` to ProjectType ABC. Returns a dict of GateConfig field names → values to override on the built-in profile.

**Why**: Follows existing profile extension pattern (planning_rules, security_checklist, etc.). Web projects need different gate behavior than Python projects (e.g., Prisma generate requires build for schema changes, auth middleware needs e2e for foundational changes).

**Alternative considered**: Full GateConfig return — rejected because plugins would need to repeat all default values. Dict merge is simpler and more maintainable.

### D4: Per-change gate_hints dict (optional, from planner)

**Decision**: Add optional `gate_hints: dict` to Change dataclass. Planner can set individual gate overrides for exceptional cases (e.g., `{"smoke": "skip"}` for a feature change that's known to not need smoke).

**Why**: 95% of changes don't need hints — change_type is sufficient. But edge cases exist (e.g., a feature change that only adds API endpoints with no UI needs `smoke: "skip"`). gate_hints provides an escape hatch without adding new change_types.

**Alternative considered**: More skip_* boolean fields — rejected because adding skip_build, skip_smoke, skip_e2e, skip_rules etc. pollutes the Change dataclass. A single dict is cleaner.

### D5: Directive overrides as last-resort runtime tuning

**Decision**: `gate_overrides` nested dict in orchestration.yaml, applied last in the resolution chain.

**Why**: Allows users to tune gate behavior without code changes or plugin updates. Useful for debugging ("force-enable smoke for infrastructure to diagnose a specific issue") or project-specific needs.

**Alternative considered**: Flat `gate_override_<type>_<gate>` keys — more verbose but simpler parsing. Start with nested dict since orchestration.yaml already supports nested structures.

### D6: Warn mode — execute but non-blocking

**Decision**: Gates set to `"warn"` execute normally but failures are logged as warnings without consuming retry budget or blocking merge.

**Why**: Some gates provide useful signal even when they shouldn't block. Schema changes benefit from seeing test results (warn) without failing the change if tests break due to migration timing. This is strictly more useful than binary run/skip.

### D7: Resolution in gate_profiles.py, consumption in verifier.py and merger.py

**Decision**: `resolve_gate_config()` lives in the new `gate_profiles.py` module. Verifier and merger call it once at the start and use the result to guard each gate.

**Why**: Single resolution point, consumed in two places. The verifier handles pre-merge gates (build, test, e2e, scope, review, rules, spec_verify). The merger handles post-merge gates (smoke). Clean separation of concerns.

## Risks / Trade-offs

**[Risk] Wrong gate profile skips a gate that would have caught a real bug**
→ Mitigation: Feature profile (all gates run) is the default. Only well-understood change types get relaxed profiles. Unknown types always get full pipeline. Profile can be overridden via directives.

**[Risk] Profile plugin gate_overrides() returns invalid field names**
→ Mitigation: `resolve_gate_config()` uses `hasattr()` check — unknown fields silently ignored. Log a debug warning for unknown keys.

**[Risk] LLM assigns wrong change_type → wrong gate profile**
→ Mitigation: This risk exists today for test-file blocking (line 1406). Gate profiles make the consequence larger but also more transparent (logged in VERIFY_GATE event). Planning rules already guide change_type assignment well.

**[Trade-off] Added complexity in verifier.py**
→ The verifier gets a GateConfig check before each gate section. This adds ~20 lines of `if gc.should_run()` / `if gc.is_blocking()` checks but replaces ad-hoc conditionals (skip_test, skip_review, hardcoded change_type checks) with a uniform pattern.

**[Trade-off] Three-repo change (set-core + set-project-base + set-project-web)**
→ Phase 1 (set-core only) provides full value with built-in profiles. Plugin overrides (Phase 2) enhance but are not required. Each phase is independently deployable.
