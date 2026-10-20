## Context

`lib/set_orch/` is the abstract orchestration core (Layer 1). `modules/web/` is the web-stack plugin (Layer 2). Per `.claude/rules/modular-architecture.md`, Layer 1 must never reference web-specific patterns (Playwright, Next.js, Prisma, package.json, v0-export). Recent commits (`e452b785` test-bundling rewrite; `c156f6ff`/`53c885cd`/`66d8f289` design-fidelity expansions; `1db82a40` v0 importer wire-up) added or kept several Layer 1 references that violate this rule:

- `planner.py:241-242,268` — `if list(p.glob("vitest.config.*"))` and a `["vitest","jest","mocha"]` membership test.
- `planner.py:338,422` — `prisma/` path checks for schema-migration detection.
- `planner.py:2802` — `Path("v0-export") / "app" / "globals.css"` lookup for design-token import.
- `templates.py::_get_test_bundling_directives` and `planner.py::_assert_no_standalone_test_changes` — both wrap `load_profile()` in bare `except Exception` and degrade to empty prefixes/empty tokens. CoreProfile users (or any profile-load failure) silently lose the test-bundling enforcement.
- `templates.py::render_domain_decompose_prompt` — JSON output schema requires `change_type` but the prompt body never instructs the LLM to set it. Empirically, the LLM sometimes drops it; downstream `dispatcher.resolve_change_model` then falls through to the default model and the change-type-aware routing is lost.
- `chat.py:_run_claude` — when resuming a session (`--resume <id>`), the command does not pass `--model`. The Claude CLI carries the model from session creation, but this is implicit and breaks the upcoming model-config invariant ("every claude invocation passes --model explicitly").

The next change (`model-config-unified`) introduces a central `models:` block in `orchestration.yaml` and replaces every model-name hardcode with a config lookup. Landing it on the current foundation would inherit the silent-fail paths and the Layer 1 leaks; we'd be auditing the same defects again from a config edit.

## Goals / Non-Goals

**Goals:**
- Layer 1 (`lib/set_orch/`) holds zero web-specific tokens after this change. The four hardcodes in `planner.py` move to `ProjectType` hooks.
- Profile-load failure in test-bundling guards is observable (logger.warning) and partially defended (universal prefix backstop), instead of silently disabled.
- The domain decompose prompt explicitly requires `change_type` so the dispatcher's routing always has the input it needs.
- `chat.py` invocations always carry `--model`; no Claude CLI invocation in this codebase relies on implicit model carry-over.

**Non-Goals:**
- No new `models:` config block. That is Phase B (`model-config-unified`).
- No change to which model is used at any touch point. Only the *plumbing* changes; behavior on existing profiles and existing inputs is preserved.
- No change to OpenSpec's existing `decompose-test-bundling` capability. Its requirements stay; only its enforcement surface gains a backstop.
- No change to the design-fidelity gate's check set (skeleton/token-guard/classname/optional-pixel-diff). That review belongs in a future change.

## Decisions

### D1 — Three new ProjectType hooks, neutral defaults in CoreProfile

Add to `ProjectType` ABC in `lib/set_orch/profile_types.py`:

```python
def detect_test_framework(self, project_dir: Path) -> Optional[str]:
    """Return short name of detected test framework or None.
    Core default: None. Web override: "vitest"|"jest"|"mocha" via config glob."""
    return None

def detect_schema_provider(self, project_dir: Path) -> Optional[str]:
    """Return short name of detected schema/migration tool or None.
    Core default: None. Web override: "prisma" if prisma/schema.prisma exists, else None."""
    return None

def get_design_globals_path(self, project_dir: Path) -> Optional[Path]:
    """Return path to the canonical design-tokens CSS file or None.
    Core default: None. Web override: project_dir/'v0-export/app/globals.css' if file exists, else None."""
    return None
```

`CoreProfile` (in `profile_loader.py`) inherits the `None` defaults — Core projects lose nothing because they never had this code path activate for them anyway (the planner currently always tested filesystem unconditionally; we preserve only the *web* behavior).

`WebProjectType` (in `modules/web/set_project_web/project_type.py`) supplies concrete logic mirroring the moved code.

**Alternative considered**: a single `arch_hints` dict returning all three. Rejected — three independent concerns, three separate hooks read more clearly and let plugins override one without touching the others.

### D2 — Universal prefix backstop in `_assert_no_standalone_test_changes`

The post-merge guard currently:
```python
prefixes = profile.standalone_test_change_prefixes()  # may be empty
if not prefixes:
    return  # silent no-op
```

After:
```python
profile_prefixes = profile.standalone_test_change_prefixes()  # may be empty
universal_prefixes = ["test-", "e2e-", "playwright-", "vitest-"]
prefixes = list(set(profile_prefixes) | set(universal_prefixes))
# now non-empty unconditionally; universal set is the safety net.
```

The singleton-exception (`infra_name` defaults to `"test-infrastructure-setup"`) still applies. Web projects keep their stricter, profile-supplied prefix list which is a *superset* of the universal backstop.

**Alternative considered**: leaving CoreProfile profiles unprotected on the theory that they "don't have e2e tests anyway". Rejected — the failure mode is asymmetric: a non-web project that happens to produce a `test-foo` change name has no protection and the guard's job is exactly to catch that.

### D3 — Fail-loud profile load

Both `templates.py::_get_test_bundling_directives` and `planner.py::_assert_no_standalone_test_changes` use `try: load_profile() except Exception: …`. Replace with:

```python
try:
    profile = load_profile(project_path)
except Exception:
    logger.warning(
        "Profile load failed in <site>; falling back to universal defaults.",
        exc_info=True,
    )
    profile = None
```

Caller code then handles `profile is None` with explicit defaults. The exception is no longer swallowed; debugging becomes possible.

### D4 — Explicit textual `change_type` instruction in domain decompose prompt

In `render_domain_decompose_prompt`, the existing `## Constraints` block adds one bullet:

> Each emitted change MUST set `change_type` to one of: `infrastructure`, `schema`, `foundational`, `feature`, `cleanup-before`, `cleanup-after`. The dispatcher's per-change model routing reads this field.

Schema already requires the field; this aligns the textual instruction with the schema.

**Alternative considered**: enforce post-hoc via planner validation rejecting plans without `change_type`. Rejected for now — fail at planning time confuses the agent loop more than a stricter prompt; we may add the validator in Phase B.

### D5 — `chat.py` always passes `--model`

Current `_run_claude` (lines 102-109):
```python
cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose"]
if context: cmd.extend(["--append-system-prompt", context])
if self.session_id:
    cmd.extend(["--resume", self.session_id])
else:
    cmd.extend(["--model", self.model, "--permission-mode", "auto"])
```

After:
```python
cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose",
       "--model", self.model]
if context: cmd.extend(["--append-system-prompt", context])
if self.session_id:
    cmd.extend(["--resume", self.session_id])
else:
    cmd.extend(["--permission-mode", "auto"])
```

`--model` is always present. `--permission-mode auto` stays only on fresh sessions where it was always set.

**Alternative considered**: Keep current behavior and rely on Claude CLI's session-side model persistence. Rejected — the upcoming model-config rollout's invariant is "every model-using invocation reads from config and passes --model explicitly"; an exception path here weakens that invariant and creates a future audit hole.

## Risks / Trade-offs

- [Behavior change in `chat.py` resume] If the Claude CLI's resume path previously honored a model different from `self.model` (e.g., a session created with `opus` resumed with a current `self.model` of `sonnet`), the new path now forces `self.model`. → **Mitigation**: `self.model` is always set at `ChatSession.__init__`; it equals what the session was originally configured with. The change is functionally a no-op unless a caller mutates `self.model` between create and resume. Tests cover the case `self.model` is preserved across resume cycles.
- [Profile-load fail surfaces logs] Adding logger.warning may produce noise in environments where `load_profile()` benignly fails (e.g., during set-project init before profile-types.yaml is written). → **Mitigation**: include a sentinel one-shot suppression: warn once per process per project_path. Already aligned with existing `logger.warning` patterns elsewhere in `lib/set_orch/`.
- [Universal prefix backstop affects Core projects with intentional test-* change names] A Core project that legitimately creates a change called `test-only-cleanup` will now trip the guard. → **Mitigation**: the singleton-exception (`test-infrastructure-setup` by default) is profile-overridable via `singleton_test_infrastructure_change_name()` — Core projects can rename their exception. We add this to the docstring.
- [Hook signature change for downstream plugins] External plugins that currently subclass `ProjectType` (private repos) will get the new hooks via inheritance with safe defaults; no breakage. → **Mitigation**: defaults return `None`, behavior is preserved.

## Migration Plan

1. Add hooks + defaults to `ProjectType` and `CoreProfile`. Tests confirm None defaults.
2. Add concrete overrides to `WebProjectType` mirroring the moved code. Tests confirm web-specific detection still works.
3. Replace the `planner.py` hardcodes with `profile.detect_test_framework(...)`, `profile.detect_schema_provider(...)`, `profile.get_design_globals_path(...)` calls. Run the existing decompose unit tests; they pass on web fixtures, return None-paths on core fixtures.
4. Apply the fail-loud + universal-prefix-backstop edits in `templates.py` and `planner.py`. Extend `tests/unit/test_decompose_test_bundling.py` for the new paths.
5. Apply the change_type prompt edit. Add a unit test that the rendered prompt contains the new instruction.
6. Apply the `chat.py` edit. Add a unit test that the constructed cmd always contains `--model`.
7. Run full unit suite. No expected behavior change on existing inputs; only previously-silent paths gain visibility.

**Rollback**: revert the commit. The change is mechanical and self-contained; no migrations or data shape changes.

## Open Questions

- Whether `detect_test_framework` should distinguish between "no framework detected" and "config exists but unparseable". For now, both → `None` and the planner treats it as "no framework". Defer to Phase B where the routing actually uses this field.
- Whether to treat the singleton-exception name as a Core-default that Web inherits, or have CoreProfile expose it more loudly. Current default `"test-infrastructure-setup"` is set at the ProjectType ABC level; revisited only if a project needs to override it (none observed).
