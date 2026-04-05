# Design: e2e-smoke-functional-split

## Core Principle

**Smoke inherited, full own.** Prior changes get a single smoke test each (first test per file — catches 404s, routing breaks, render crashes). The current change gets its full test suite. Smoke is non-blocking (warns), own is blocking (redispatches).

## Real Data (craftbrew-run22)

| Change | Inherited tests | Own tests | Today's gate time |
|--------|----------------|-----------|-------------------|
| foundation-setup | 0 | 18 | skipped |
| auth-and-profile | 18 | 6 | 43s |
| product-catalog | 24 | 6 | 14s |
| content-email-wishlist | 30 | 7 | 64s |
| cart-and-promotions | 37 | 7 | 67s |
| admin-panel | 44 | 9 | **130s** |

With smoke split (1 test per inherited file):
| Change | Smoke (inherited) | Own | Expected time |
|--------|-------------------|-----|---------------|
| admin-panel | **6 tests** (~10s) | 9 tests (~25s) | **~35s** |

First test per file = natural smoke test:
```
foundation.spec.ts → "REQ-I18N-001: / redirects to /hu"
auth.spec.ts       → "unauthenticated visit to /hu/fiokom redirects to login"
cart.spec.ts       → "cold visit to /hu/kosar shows empty state"
catalog.spec.ts    → "11.1 cold visit to /hu loads homepage sections"
content.spec.ts    → "story listing page loads with grid"
wishlist.spec.ts   → "toggle wishlist on product card"
```

These catch: 404s, routing breaks, i18n redirects broken, rendering crashes, auth middleware misconfigured.

## Design Decisions

### 1. Core/Module separation preserved

**The merger (core) orchestrates phases. The profile (module) constructs commands.**

Core (`lib/set_orch/merger.py`) knows:
- Git diff to detect own vs inherited spec files
- Two-phase execution flow (smoke → own)
- State recording, redispatch logic, non-blocking semantics

Core does NOT know:
- `--grep` syntax (Playwright-specific)
- `-- <files>` syntax (Playwright-specific)
- How to parse test names from spec files (framework-specific)

Two new profile methods bridge this:

```python
# In ProfileType ABC (profile_types.py)
def e2e_smoke_command(self, base_cmd: str, test_names: list[str]) -> Optional[str]:
    """Construct command to run only named tests (smoke subset).
    
    Args:
        base_cmd: The detected e2e command (e.g., "npx playwright test")
        test_names: List of test names to run as smoke
    Returns:
        Full command string, or None if not supported.
    """
    return None

def e2e_scoped_command(self, base_cmd: str, spec_files: list[str]) -> Optional[str]:
    """Construct command to run only specific spec files.
    
    Args:
        base_cmd: The detected e2e command
        spec_files: Relative paths to spec files to run
    Returns:
        Full command string, or None (falls back to base_cmd).
    """
    return None

def extract_first_test_name(self, spec_path: str) -> Optional[str]:
    """Extract the first test name from a spec file for smoke selection.
    
    Framework-specific parsing (regex for test() in Playwright,
    def test_ in pytest, etc.)
    """
    return None
```

Web module (`modules/web/project_type.py`) implements:
```python
def e2e_smoke_command(self, base_cmd, test_names):
    grep = "|".join(re.escape(n) for n in test_names)
    return f'{base_cmd} --grep "{grep}"'

def e2e_scoped_command(self, base_cmd, spec_files):
    return f'{base_cmd} -- {" ".join(spec_files)}'

def extract_first_test_name(self, spec_path):
    with open(spec_path) as f:
        for line in f:
            m = re.search(r'test\(["\'](.+?)["\']', line)
            if m:
                return m.group(1)
    return None
```

**Merger stays framework-agnostic:**
```python
# In merger.py — core orchestration, no Playwright knowledge
smoke_names = []
for spec in inherited_specs:
    name = profile.extract_first_test_name(spec)
    if name:
        smoke_names.append(name)

if smoke_names:
    smoke_cmd = profile.e2e_smoke_command(e2e_cmd, smoke_names)
    if smoke_cmd:
        result = run_command(["bash", "-c", smoke_cmd], ...)
```

A future Python project type could implement the same interface with `pytest -k "name1 or name2"` syntax.

### 2. Git diff for ownership detection

**Decision:** `git diff $(git merge-base HEAD main) --name-only --diff-filter=AM | grep '.spec.ts$'`

**Why:** Spec file names DON'T match change names (`cart-and-promotions` → `cart.spec.ts`). Git diff is deterministic, works retroactively, handles multi-file changes.

This logic stays in core (merger.py) — git diff is framework-agnostic.

**Fallback chain:**
1. Git diff (primary)
2. `e2e-manifest.json` (future, written by dispatcher)
3. Run all tests as single phase (legacy behavior)

### 3. Smoke failures are non-blocking but visible

**Decision:** When smoke tests fail, log warning + record in state. Don't block merge, don't redispatch.

**Why:** The cart agent can't fix a broken foundation test. But the regression must be visible — sentinel can create an investigation issue.

**State fields:**
- `smoke_e2e_result`: "pass" | "fail" | "skip"
- `smoke_e2e_output`: last 1000 chars
- `smoke_e2e_ms`: timing

### 4. Redispatch scoped to own tests only

**Decision:** Retry context includes ONLY Phase 2 (own test) output + list of own spec files.

**Why:** Current behavior dumps all test output to the agent — including inherited failures the agent can't fix.

### 5. Forward-looking: @smoke tag

**Decision:** Future agents use `{ tag: '@smoke' }` on first happy-path test. When detected, Phase 1 uses tag-based filtering instead of parse-based.

**Detection in web module:** Grep inherited files for `tag:.*@smoke`. If found → `e2e_smoke_command()` returns `--grep @smoke`. If not → falls back to first-test parsing.

**Not required retroactively.**

### 6. Coverage tracking: smoke + own breakdown

`TestCoverage` gains `smoke_passed`, `smoke_failed`, `own_passed`, `own_failed`.

## Data Flow

```
┌─ MERGE GATE (merger.py — core) ───────────────────────────────┐
│                                                                │
│ _detect_own_spec_files(wt_path)  ← git diff, framework-free   │
│   → own_specs, inherited_specs                                 │
│                                                                │
│ Phase 1: SMOKE (inherited, non-blocking)                       │
│   profile.extract_first_test_name(spec)  ← module parses      │
│   profile.e2e_smoke_command(cmd, names)  ← module builds cmd   │
│   run_command(smoke_cmd)                                       │
│   → 1 test per prior change (~6 tests, ~10-15s)               │
│   → fail? log + record, DON'T block                           │
│                                                                │
│ Phase 2: OWN (blocking)                                        │
│   profile.e2e_scoped_command(cmd, own_specs) ← module builds   │
│   run_command(scoped_cmd)                                      │
│   → full test suite for this change                            │
│   → fail? redispatch with scoped context                       │
│                                                                │
│ Future: @smoke tags → Phase 1 uses --grep @smoke               │
└────────────────────────────────────────────────────────────────┘
```

## Migration

- **Existing runs**: git diff + first-test parsing works immediately. No tags, no manifest, no agent changes.
- **Future runs**: agents tag `@smoke` → Phase 1 uses tags. Manifest provides ownership.
- **Backward compat**: all new fields default to safe values. No profile methods → single-phase fallback (current behavior).
