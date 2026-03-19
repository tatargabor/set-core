# Gate Profiles — Specification

> **Status**: Draft
> **Date**: 2026-03-15
> **Scope**: set-core core + set-project-base + set-project-web

## Problem Statement

The current verification pipeline runs **the same 7 gates for every change**, regardless of its nature. This causes:

1. **False failures** — infrastructure/setup changes fail smoke/build/e2e gates because there's no running app yet
2. **Wasted tokens** — e2e runs on schema changes, build runs on doc changes, smoke runs on test-setup changes
3. **Wasted wall-clock** — unnecessary gate execution adds 2-10 minutes per change
4. **Lost retries** — a false-positive gate failure consumes a retry from the shared `max_verify_retries` budget

### Evidence from E2E runs

| Run | Change | Type | Wasted Gate | Impact |
|-----|--------|------|-------------|--------|
| #14 | test-infrastructure-setup | infrastructure | smoke (post-merge) | False fail — no app to smoke test |
| #14 | products-page | feature | spec_coverage retry | 81k extra tokens for soft misalignment |
| #4  | project-infrastructure | infrastructure | test (2 retries) | No test files initially, retry wasted |
| #13 | cart-feature | feature | review (2-5 retries) | Expected — security fixes need iteration |
| CraftBrew | user-auth-and-accounts | feature (14 REQ) | verify (3 retries) | 708k tokens wasted on too-large change |

**Pattern**: infrastructure, schema, and test-setup changes consistently fail gates that only make sense for feature changes.

## Design

### Core Concept: Gate Profile

A **gate profile** is a named configuration that determines which gates run for a change and how they behave (blocking vs warning).

```
┌──────────────────────────────────────────────────────────────────┐
│                     GATE PROFILE RESOLUTION                      │
│                                                                  │
│   ┌─────────────┐     ┌──────────────┐     ┌─────────────────┐  │
│   │ Plan output  │────▶│ Profile      │────▶│ Verifier        │  │
│   │ change_type  │     │ gate_config_ │     │ runs gates per  │  │
│   │ (+ optional  │     │ for_change() │     │ resolved config │  │
│   │  gate hints) │     │              │     │                 │  │
│   └─────────────┘     └──────┬───────┘     └─────────────────┘  │
│                              │                                   │
│                   ┌──────────▼───────────┐                       │
│                   │  Resolution chain:   │                       │
│                   │  1. Explicit override │                       │
│                   │  2. Profile plugin   │                       │
│                   │  3. Built-in default │                       │
│                   └──────────────────────┘                       │
└──────────────────────────────────────────────────────────────────┘
```

### Gate Config Dataclass

```python
@dataclass
class GateConfig:
    """Per-change gate configuration resolved from profile + defaults."""

    # Pre-merge gates (in handle_change_done)
    build: str = "run"         # "run" | "skip" | "warn"
    test: str = "run"          # "run" | "skip" | "warn"
    test_files_required: bool = True  # Block if no .test./.spec. files
    e2e: str = "run"           # "run" | "skip" | "warn"
    scope_check: str = "run"   # "run" | "skip"
    review: str = "run"        # "run" | "skip"
    spec_verify: str = "run"   # "run" | "skip" | "soft"
    rules: str = "run"         # "run" | "skip"

    # Post-merge gates (in merger.py)
    smoke: str = "run"         # "run" | "skip" | "warn"

    # Retry budget override (None = use global max_verify_retries)
    max_retries: Optional[int] = None

    # Review model override (None = use global review_model)
    review_model: Optional[str] = None
```

**Gate modes**:
- `"run"` — Execute gate. Failure blocks merge (retryable).
- `"skip"` — Don't execute this gate at all.
- `"warn"` — Execute gate. Failure logged as warning, does NOT block merge, does NOT consume retry budget.
- `"soft"` — (spec_verify only) Execute, but treat failure as non-blocking if other gates passed.

### Built-in Gate Profiles

These are the defaults in set-core core. Project type plugins can override.

```python
BUILTIN_GATE_PROFILES: dict[str, GateConfig] = {

    # ── Infrastructure: test framework, build config, CI/CD ──
    # No app to build/test/smoke yet. Only verify scope + review.
    "infrastructure": GateConfig(
        build="skip",
        test="skip",
        test_files_required=False,
        e2e="skip",
        scope_check="run",
        review="run",
        spec_verify="soft",
        rules="run",
        smoke="skip",
    ),

    # ── Schema: DB migrations, model definitions ──
    # May have a buildable app but no runnable features yet.
    # Tests if they exist, no e2e, no smoke.
    "schema": GateConfig(
        build="run",
        test="warn",            # run if exists, warn-only on failure
        test_files_required=False,
        e2e="skip",
        scope_check="run",
        review="run",
        spec_verify="run",
        rules="run",
        smoke="skip",
    ),

    # ── Foundational: auth, shared types, base components ──
    # App buildable, unit tests expected, no e2e yet.
    "foundational": GateConfig(
        build="run",
        test="run",
        test_files_required=True,
        e2e="skip",             # foundational code rarely has e2e
        scope_check="run",
        review="run",
        spec_verify="run",
        rules="run",
        smoke="skip",           # too early for smoke usually
    ),

    # ── Feature: user-facing functionality ──
    # Full pipeline. Everything runs.
    "feature": GateConfig(
        build="run",
        test="run",
        test_files_required=True,
        e2e="run",
        scope_check="run",
        review="run",
        spec_verify="run",
        rules="run",
        smoke="run",
    ),

    # ── Cleanup-before: refactoring before features ──
    # Build+test to confirm no regressions. No e2e, no smoke.
    "cleanup-before": GateConfig(
        build="run",
        test="warn",            # run if exists, warn-only
        test_files_required=False,
        e2e="skip",
        scope_check="run",
        review="run",
        spec_verify="soft",
        rules="run",
        smoke="skip",
    ),

    # ── Cleanup-after: dead code, cosmetic ──
    # Lightest profile. Build to check nothing broke.
    "cleanup-after": GateConfig(
        build="run",
        test="warn",
        test_files_required=False,
        e2e="skip",
        scope_check="run",
        review="skip",          # cosmetic changes don't need review
        spec_verify="soft",
        rules="skip",
        smoke="skip",
    ),
}

# Default fallback for unknown change_type
DEFAULT_GATE_PROFILE = BUILTIN_GATE_PROFILES["feature"]
```

### Gate Profile Matrix (visual)

```
                 BUILD  TEST  TEST_FILES  E2E  SCOPE  REVIEW  SPEC   RULES  SMOKE
infrastructure    ─      ─      ─         ─     ✓      ✓      soft    ✓      ─
schema            ✓     warn    ─         ─     ✓      ✓      ✓       ✓      ─
foundational      ✓      ✓      ✓         ─     ✓      ✓      ✓       ✓      ─
feature           ✓      ✓      ✓         ✓     ✓      ✓      ✓       ✓      ✓
cleanup-before    ✓     warn    ─         ─     ✓      ✓      soft    ✓      ─
cleanup-after     ✓     warn    ─         ─     ✓      ─      soft    ─      ─

✓ = run (blocking)   warn = run but non-blocking   soft = run, non-blocking if other gates pass   ─ = skip
```

## Architecture

### Resolution Chain

```
resolve_gate_config(change: Change, profile, directives) -> GateConfig
    │
    ├── 1. Start with BUILTIN_GATE_PROFILES[change.change_type]
    │      (or DEFAULT_GATE_PROFILE if unknown type)
    │
    ├── 2. Apply profile.gate_overrides(change.change_type)
    │      (project-type plugin can override any field)
    │
    ├── 3. Apply per-change explicit overrides from plan
    │      change.skip_test=True  → config.test = "skip"
    │      change.skip_review=True → config.review = "skip"
    │      (new: change.gate_hints dict for fine-grained)
    │
    └── 4. Apply orchestration.yaml directive overrides
           gate_override_<change_type>_<gate> = "skip|run|warn"
           (e.g., gate_override_infrastructure_build = "run")
```

### Where Each Piece Lives

```
┌─────────────────────────────────────────────────────────────────┐
│  set-core core                                                  │
│  ├── lib/set_orch/gate_profiles.py    ← NEW: GateConfig,        │
│  │                                      BUILTIN_GATE_PROFILES,  │
│  │                                      resolve_gate_config()   │
│  ├── lib/set_orch/verifier.py         ← MODIFY: use GateConfig  │
│  ├── lib/set_orch/merger.py           ← MODIFY: smoke uses GC   │
│  ├── lib/set_orch/state.py            ← MODIFY: gate_hints fld  │
│  ├── lib/set_orch/templates.py        ← MODIFY: planning rules  │
│  ├── lib/set_orch/profile_loader.py   ← MODIFY: gate_overrides  │
│  └── lib/set_orch/config.py           ← MODIFY: new directives  │
├─────────────────────────────────────────────────────────────────┤
│  set-project-base                                                │
│  └── wt_project_base/base.py         ← MODIFY: gate_overrides  │
│                                         method on ProjectType   │
├─────────────────────────────────────────────────────────────────┤
│  set-project-web                                                 │
│  └── wt_project_web/project_type.py  ← MODIFY: web-specific    │
│                                         gate overrides          │
└─────────────────────────────────────────────────────────────────┘
```

## Detailed Changes

### 1. New file: `lib/set_orch/gate_profiles.py`

**Purpose**: Single source of truth for gate profile logic.

```python
"""Gate profiles — per-change-type verification gate configuration.

Resolves which gates run for each change based on:
1. Built-in defaults (keyed by change_type)
2. Project-type plugin overrides
3. Per-change explicit overrides from plan
4. Orchestration directive overrides
"""

from dataclasses import dataclass, fields, replace
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class GateConfig:
    """Resolved gate configuration for a single change."""

    build: str = "run"
    test: str = "run"
    test_files_required: bool = True
    e2e: str = "run"
    scope_check: str = "run"
    review: str = "run"
    spec_verify: str = "run"
    rules: str = "run"
    smoke: str = "run"
    max_retries: Optional[int] = None
    review_model: Optional[str] = None

    def should_run(self, gate_name: str) -> bool:
        """Whether a gate should execute at all."""
        val = getattr(self, gate_name, "run")
        return val in ("run", "warn", "soft")

    def is_blocking(self, gate_name: str) -> bool:
        """Whether gate failure should block merge."""
        val = getattr(self, gate_name, "run")
        return val == "run"

    def is_warn_only(self, gate_name: str) -> bool:
        """Whether gate failure is warning-only (non-blocking)."""
        val = getattr(self, gate_name, "run")
        return val in ("warn", "soft")


BUILTIN_GATE_PROFILES: dict[str, GateConfig] = {
    # ... (as defined above)
}

DEFAULT_GATE_PROFILE = GateConfig()  # all "run", feature-equivalent


def resolve_gate_config(
    change,                          # Change dataclass
    profile=None,                    # ProjectType plugin or NullProfile
    directives: dict | None = None,  # from orchestration.yaml
) -> GateConfig:
    """Resolve the gate configuration for a change.

    Resolution chain:
    1. Built-in profile for change_type
    2. Profile plugin overrides
    3. Per-change explicit flags (skip_test, skip_review, gate_hints)
    4. Orchestration directive overrides
    """
    change_type = change.change_type or "feature"

    # Step 1: Built-in defaults
    config = replace(BUILTIN_GATE_PROFILES.get(change_type, DEFAULT_GATE_PROFILE))

    # Step 2: Profile plugin overrides
    if profile is not None and hasattr(profile, "gate_overrides"):
        overrides = profile.gate_overrides(change_type)
        if overrides:
            for key, val in overrides.items():
                if hasattr(config, key):
                    setattr(config, key, val)

    # Step 3: Per-change explicit overrides
    if change.skip_test:
        config.test = "skip"
        config.test_files_required = False
    if change.skip_review:
        config.review = "skip"

    # gate_hints: fine-grained per-change overrides from plan
    gate_hints = getattr(change, "gate_hints", None) or {}
    for key, val in gate_hints.items():
        if hasattr(config, key):
            setattr(config, key, val)

    # Step 4: Directive overrides (e.g., gate_override_infrastructure_build=run)
    if directives:
        prefix = f"gate_override_{change_type}_"
        for key, val in directives.items():
            if key.startswith(prefix):
                gate_name = key[len(prefix):]
                if hasattr(config, gate_name):
                    setattr(config, gate_name, val)

    logger.debug(
        "Gate config for %s (type=%s): build=%s test=%s e2e=%s review=%s smoke=%s",
        change.name, change_type,
        config.build, config.test, config.e2e, config.review, config.smoke,
    )
    return config
```

### 2. Modify: `lib/set_orch/state.py`

Add `gate_hints` field to `Change` dataclass:

```python
@dataclass
class Change:
    # From plan (always present)
    name: str = ""
    scope: str = ""
    complexity: str = "M"
    change_type: str = "feature"
    depends_on: list[str] = field(default_factory=list)
    roadmap_item: str = ""
    model: Optional[str] = None
    skip_review: bool = False
    skip_test: bool = False
    has_manual_tasks: bool = False
    phase: int = 1
    gate_hints: Optional[dict] = None   # ← NEW: per-change gate overrides
    # ...
```

Hydration in `from_dict()`:
```python
gate_hints=c.get("gate_hints", None),
```

Serialization in `to_dict()`: include `gate_hints` if not None.

### 3. Modify: `lib/set_orch/verifier.py` — `handle_change_done()`

Replace the current gate-by-gate logic with GateConfig-driven execution:

```python
def handle_change_done(self, change_name, state_file, ...):
    # ... existing preamble ...

    # ── Resolve gate config ──
    from .gate_profiles import resolve_gate_config
    from .profile_loader import load_profile

    profile = load_profile(project_path)
    directives = state.extras.get("directives", {})
    gc = resolve_gate_config(change, profile, directives)

    # Use gc.max_retries if set, otherwise global
    effective_max_retries = gc.max_retries if gc.max_retries is not None else max_verify_retries

    # ── VG-BUILD ──
    if gc.should_run("build") and wt_path and os.path.isfile(...):
        # ... existing build logic ...
        if build_result.exit_code != 0:
            if gc.is_blocking("build"):
                # existing retry logic with effective_max_retries
            else:
                logger.warning("Build failed for %s — non-blocking (gate=%s)", change_name, gc.build)
    elif not gc.should_run("build"):
        logger.info("Verify gate: build SKIPPED for %s (gate_profile)", change_name)

    # ── VG-TEST ──
    if gc.should_run("test") and test_command and wt_path:
        # ... existing test logic ...
        if test_result_str == "fail":
            if gc.is_blocking("test"):
                # existing retry logic
            else:
                logger.warning("Tests failed for %s — non-blocking (gate=%s)", change_name, gc.test)
                test_result_str = "warn-fail"
    elif not gc.should_run("test"):
        test_result_str = "skipped"
        logger.info("Verify gate: test SKIPPED for %s (gate_profile)", change_name)

    # ── VG-E2E ──
    if gc.should_run("e2e") and e2e_command and wt_path:
        # ... existing e2e logic ...
    elif not gc.should_run("e2e"):
        e2e_result_str = "skipped"
        logger.info("Verify gate: e2e SKIPPED for %s (gate_profile)", change_name)

    # ── SCOPE CHECK ──
    if gc.should_run("scope_check") and wt_path:
        # ... existing scope logic ...

    # ── TEST FILES ──
    if gc.test_files_required and wt_path:
        # ... existing test file check ...
    else:
        logger.info("Verify gate: test file check SKIPPED for %s (not required)", change_name)

    # ── REVIEW ──
    if gc.should_run("review") and review_before_merge and wt_path:
        # ... existing review logic, using gc.review_model if set ...
    elif not gc.should_run("review"):
        logger.info("Verify gate: review SKIPPED for %s (gate_profile)", change_name)

    # ── RULES ──
    if gc.should_run("rules") and wt_path:
        # ... existing rules logic ...

    # ── SPEC VERIFY ──
    if gc.should_run("spec_verify") and wt_path:
        # ... existing verify logic ...
        # Use gc.is_blocking("spec_verify") instead of hardcoded soft-pass
```

### 4. Modify: `lib/set_orch/merger.py` — `post_merge_smoke()`

Add gate config check before running smoke:

```python
def post_merge_smoke(change_name, state_file, ...):
    # Load change to check gate config
    state = load_state(state_file)
    change = state.get_change(change_name)

    from .gate_profiles import resolve_gate_config
    from .profile_loader import load_profile
    profile = load_profile(project_path)
    directives = state.extras.get("directives", {})
    gc = resolve_gate_config(change, profile, directives)

    if not gc.should_run("smoke"):
        logger.info("Post-merge smoke SKIPPED for %s (gate_profile)", change_name)
        return "skipped"

    # ... existing smoke logic, respecting gc.is_blocking("smoke") ...
```

### 5. Modify: `lib/set_orch/profile_loader.py` — NullProfile

Add `gate_overrides` method:

```python
class NullProfile:
    # ... existing methods ...

    def gate_overrides(self, change_type: str) -> dict:
        """Return gate config overrides for a change_type.

        Returns a dict of field_name → value to override on GateConfig.
        Empty dict means use built-in defaults.
        """
        return {}
```

### 6. Modify: `set-project-base/wt_project_base/base.py` — ProjectType

Add `gate_overrides` to the abstract base:

```python
class ProjectType(ABC):
    # ... existing methods ...

    def gate_overrides(self, change_type: str) -> dict:
        """Return gate config overrides for a change_type.

        Project-type plugins override this to customize gate behavior.
        Returns dict of GateConfig field names → values.

        Example:
            def gate_overrides(self, change_type):
                if change_type == "foundational":
                    return {"e2e": "run"}  # web projects want e2e on auth
                return {}
        """
        return {}
```

### 7. Modify: `set-project-web/wt_project_web/project_type.py`

Web-specific gate overrides:

```python
class WebProjectType(BaseProjectType):
    # ... existing methods ...

    def gate_overrides(self, change_type: str) -> dict:
        """Web-specific gate overrides.

        Web projects differ from defaults:
        - foundational (auth) DOES need e2e (cold visit tests)
        - schema DOES need build (Prisma generate)
        - cleanup-after DOES need smoke (CSS regressions)
        """
        overrides = {
            "foundational": {
                "e2e": "run",           # auth middleware needs e2e
                "smoke": "warn",        # run smoke but non-blocking
            },
            "schema": {
                "build": "run",         # Prisma generate is a build step
                "test": "run",          # migration tests are important
                "test_files_required": False,  # but not always present
            },
            "cleanup-after": {
                "smoke": "warn",        # CSS changes can break visually
            },
        }
        return overrides.get(change_type, {})
```

### 8. Modify: `lib/set_orch/templates.py` — Planning rules

Update `_PLANNING_RULES_CORE` to inform the LLM about gate profiles:

Add after the existing `change_type` classification section:

```
Gate profiles — each change_type has a default verification gate configuration:
- infrastructure: NO build, test, e2e, or smoke gates. Only scope+review+rules. The app doesn't exist yet.
- schema: build+test(warn-only), NO e2e or smoke. Database changes are verified structurally.
- foundational: build+test, NO e2e or smoke by default. Project plugins may enable e2e for auth.
- feature: ALL gates run (build, test, e2e, review, smoke). Full verification pipeline.
- cleanup-before: build+test(warn-only), NO e2e or smoke. Regression checks only.
- cleanup-after: build+test(warn-only), NO review/rules/e2e/smoke. Lightest profile.

The planner does NOT need to set gate configuration — it's derived from change_type automatically.
If a change needs unusual gate behavior, set "gate_hints" in the change JSON:
  "gate_hints": {"e2e": "skip", "smoke": "skip"}
Only use gate_hints for exceptions — the defaults handle 95% of cases.
```

Update the JSON schema examples to include the optional field:

```json
{
    "name": "change-name",
    "scope": "...",
    "change_type": "infrastructure|schema|foundational|feature|cleanup-before|cleanup-after",
    "gate_hints": {"e2e": "skip"}
}
```

### 9. Modify: `lib/set_orch/config.py` — New directives

Add directive overrides for gate profiles:

```python
# In DIRECTIVE_DEFAULTS:
"gate_override_infrastructure_build": "",
"gate_override_infrastructure_test": "",
"gate_override_infrastructure_e2e": "",
"gate_override_infrastructure_smoke": "",
# ... (pattern: gate_override_{type}_{gate})
# Validators: enum of "run|skip|warn|soft" or empty string (= no override)
```

**Alternative** (less verbose): A single YAML directive:

```yaml
gate_overrides:
  infrastructure:
    build: run
  schema:
    smoke: warn
```

Parsed as a nested dict in config, applied in `resolve_gate_config()`.

### 10. Modify: `/opsx:ff` awareness

The `/opsx:ff` skill creates changes interactively (not via planner). It should:
1. When creating `proposal.md`, include the change_type
2. The OpenSpec CLI `openspec new change` should accept `--change-type` flag
3. When the LLM creates artifacts via `/opsx:ff`, the planning rules about gate profiles should be in context so the LLM picks the right change_type

**No code change needed** in the skill itself — the planning rules update (section 8) ensures the LLM has gate profile context when working through `/opsx:ff`.

### 11. Event logging

Update the `VERIFY_GATE` event to include gate profile info:

```python
if event_bus:
    event_bus.emit("VERIFY_GATE", change=change_name, data={
        # ... existing fields ...
        "gate_profile": change_type,
        "gates_skipped": [g for g in ["build","test","e2e","review","smoke","rules","spec_verify"]
                          if not gc.should_run(g)],
        "gates_warn_only": [g for g in ["build","test","e2e","review","smoke"]
                            if gc.is_warn_only(g)],
    })
```

## Integration Points Checklist

| Component | File | Change | Priority |
|-----------|------|--------|----------|
| Gate profiles module | `lib/set_orch/gate_profiles.py` | **NEW** | P0 |
| Change dataclass | `lib/set_orch/state.py` | Add `gate_hints` field | P0 |
| Verifier pipeline | `lib/set_orch/verifier.py` | Use GateConfig for all gates | P0 |
| Merger smoke gate | `lib/set_orch/merger.py` | Check GateConfig for smoke | P0 |
| NullProfile | `lib/set_orch/profile_loader.py` | Add `gate_overrides()` | P0 |
| ProjectType ABC | `set-project-base/base.py` | Add `gate_overrides()` | P1 |
| WebProjectType | `set-project-web/project_type.py` | Web gate overrides | P1 |
| Planning rules | `lib/set_orch/templates.py` | Gate profile docs for LLM | P1 |
| Config directives | `lib/set_orch/config.py` | `gate_overrides` directive | P2 |
| Event logging | `lib/set_orch/verifier.py` | Gate profile in events | P2 |
| JSON schema | `lib/set_orch/templates.py` | `gate_hints` in output schema | P2 |
| Tests | `tests/test_gate_profiles.py` | Unit tests for resolution | P0 |
| Docs | `docs/howitworks/en/07-quality-gates.md` | Update gate docs | P2 |

## Migration & Backward Compatibility

### Zero-breaking-change migration

1. **Default behavior unchanged**: `resolve_gate_config()` for `change_type="feature"` returns all-`"run"` — identical to current behavior
2. **Existing skip flags honored**: `skip_test=True` and `skip_review=True` still work, mapped to GateConfig
3. **NullProfile returns empty**: No profile plugin → no overrides → built-in defaults
4. **Unknown change_type → feature**: Safest default, all gates run

### Rollout plan

1. **Phase 1** (set-core core): Add `gate_profiles.py`, wire into verifier/merger. All existing behavior preserved.
2. **Phase 2** (project plugins): Add `gate_overrides()` to base.py and web. Deploy via `set-project init`.
3. **Phase 3** (planner awareness): Update planning rules so LLM knows about gate profiles. Add `gate_hints` to JSON schema.
4. **Phase 4** (directive overrides): Add `gate_overrides` directive for runtime tuning without code changes.

## Test Plan

### Unit tests (`tests/test_gate_profiles.py`)

```python
def test_builtin_profile_feature():
    """Feature changes get all gates enabled."""
    change = Change(name="add-cart", change_type="feature")
    gc = resolve_gate_config(change)
    assert gc.build == "run"
    assert gc.test == "run"
    assert gc.e2e == "run"
    assert gc.smoke == "run"

def test_builtin_profile_infrastructure():
    """Infrastructure changes skip build/test/e2e/smoke."""
    change = Change(name="test-setup", change_type="infrastructure")
    gc = resolve_gate_config(change)
    assert gc.build == "skip"
    assert gc.test == "skip"
    assert gc.e2e == "skip"
    assert gc.smoke == "skip"
    assert gc.review == "run"  # review still runs

def test_skip_test_overrides_profile():
    """Explicit skip_test=True overrides profile's test=run."""
    change = Change(name="add-cart", change_type="feature", skip_test=True)
    gc = resolve_gate_config(change)
    assert gc.test == "skip"
    assert gc.test_files_required == False

def test_profile_plugin_overrides():
    """Profile plugin gate_overrides() applied on top of built-in."""
    class MockProfile:
        def gate_overrides(self, change_type):
            if change_type == "foundational":
                return {"e2e": "run"}
            return {}

    change = Change(name="add-auth", change_type="foundational")
    gc = resolve_gate_config(change, profile=MockProfile())
    assert gc.e2e == "run"  # overridden from "skip"
    assert gc.build == "run"  # kept from built-in

def test_directive_overrides():
    """Orchestration directives override everything."""
    change = Change(name="test-setup", change_type="infrastructure")
    directives = {"gate_override_infrastructure_build": "run"}
    gc = resolve_gate_config(change, directives=directives)
    assert gc.build == "run"  # overridden from "skip"

def test_gate_hints_from_plan():
    """Per-change gate_hints override profile defaults."""
    change = Change(name="add-e2e", change_type="feature", gate_hints={"smoke": "skip"})
    gc = resolve_gate_config(change)
    assert gc.smoke == "skip"
    assert gc.e2e == "run"  # not overridden

def test_unknown_change_type_defaults_to_feature():
    """Unknown change_type gets feature profile (safest)."""
    change = Change(name="mystery", change_type="unknown-type")
    gc = resolve_gate_config(change)
    assert gc.build == "run"
    assert gc.test == "run"
    assert gc.e2e == "run"

def test_should_run_and_is_blocking():
    """Helper methods work correctly for all modes."""
    gc = GateConfig(test="warn", e2e="skip", spec_verify="soft")
    assert gc.should_run("test") == True
    assert gc.is_blocking("test") == False
    assert gc.should_run("e2e") == False
    assert gc.should_run("spec_verify") == True
    assert gc.is_blocking("spec_verify") == False

def test_resolution_chain_priority():
    """Later overrides win: directive > gate_hints > skip_flags > profile > builtin."""
    class MockProfile:
        def gate_overrides(self, ct):
            return {"test": "warn"}

    change = Change(name="x", change_type="feature", gate_hints={"test": "skip"})
    directives = {"gate_override_feature_test": "run"}

    gc = resolve_gate_config(change, profile=MockProfile(), directives=directives)
    assert gc.test == "run"  # directive wins
```

### Integration test (E2E validation)

After deploying to a consumer project, run one orchestration with mixed change types and verify:
- infrastructure change: smoke/e2e/build gates show "skipped" in events
- feature change: all gates run
- Token savings visible in event log comparison vs previous runs

## Expected Impact

### Token savings estimate (per orchestration run)

Based on E2E run data:

| Scenario | Before | After | Saving |
|----------|--------|-------|--------|
| infrastructure smoke false-fail + retry | 80-150k tokens | 0 (skipped) | 100% |
| schema e2e (unnecessary) | 50-100k tokens | 0 (skipped) | 100% |
| cleanup-after review (unnecessary) | 30-50k tokens | 0 (skipped) | 100% |
| infrastructure build false-fail | 40-80k tokens retry | 0 (skipped) | 100% |
| **Per-run total estimated saving** | | | **~200-400k tokens** |

### Wall-clock savings

| Gate | Time per execution | Skipped for types | Saving per change |
|------|--------------------|-------------------|-------------------|
| Build | 30-120s | infrastructure | 30-120s |
| Smoke | 30-60s + health check | infra, schema, foundational, cleanup | 30-60s |
| E2E | 60-180s | infra, schema, cleanup-before, cleanup-after | 60-180s |
| Review | 30-90s (LLM call) | cleanup-after | 30-90s |

### Retry budget savings

Currently, false-positive gate failures (e.g., smoke on infrastructure) consume from the shared `max_verify_retries=2` budget. After gate profiles, those retries are preserved for gates that actually matter for the change type.

## Open Questions

1. **Should `gate_hints` be in the planner JSON output or only settable via orchestration.yaml?**
   Recommendation: Both. Planner can set hints for exceptions, orchestration.yaml for global overrides.

2. **Should we add more change_types?**
   Potential additions: `e2e-setup`, `config`, `docs`. Currently all map to existing types. Start with the 6 existing types and add more based on E2E data.

3. **Should profile.gate_overrides() receive the full Change object, not just change_type?**
   Pro: Can inspect scope/name for smarter decisions. Con: Couples profile to Change internals.
   Recommendation: Start with change_type only. Add Change param later if needed.

4. **Should warn-mode gate failures appear in the VERIFY_GATE event differently?**
   Yes — add `gates_warned` list alongside `gates_skipped` for observability.
