# Spec: Profile Hooks (delta)

## ADDED Requirements

### Requirement: Profile shall expose design-source provider methods

The `ProjectType` ABC SHALL define three new abstract methods that profiles implement to provide design source content to the dispatcher. Layer 1 (`lib/set_orch/`) SHALL NOT contain v0-specific or stack-specific logic — it only orchestrates calls to the profile.

```python
def detect_design_source(self, project_path: Path) -> str:
    """Return identifier of the design source for this project, or "none".
    Convention: known identifiers include "v0". Returning "none" means no design source detected.
    Returned as plain str (not Literal) to keep the ABC forward-compatible with future plugins."""

def copy_design_source_slice(
    self,
    change_name: str,
    scope: str,
    dest_dir: Path,
) -> list[Path]:
    """Populate dest_dir with scope-matched design source files for the named change.
    Return list of copied file paths. The dest_dir is computed by the dispatcher
    (typically `openspec/changes/<change_name>/design-source/`)."""

def get_design_dispatch_context(
    self,
    change_name: str,
    scope: str,
    project_path: Path,
) -> str:
    """Return the markdown block to inject into agent input.md as the Design Source section.
    Receives change_name so the block can reference `openspec/changes/<change_name>/design-source/` accurately."""
```

#### Scenario: NullProfile design-source defaults
- **WHEN** `NullProfile().detect_design_source(any_path)` is called
- **THEN** it returns the string `"none"`
- **AND** `copy_design_source_slice(any_change, any_scope, any_dest)` returns `[]` (no files copied)
- **AND** `get_design_dispatch_context(any_change, any_scope, any_path)` returns an empty string

#### Scenario: CoreProfile inherits NullProfile design-source defaults
- **WHEN** `CoreProfile().detect_design_source(any_path)` is called
- **THEN** it returns `"none"` (CoreProfile is universal, design source is per-stack)
- **AND** subclasses (e.g. WebProjectType) override these methods to provide concrete implementations

#### Scenario: Layer 1 has no v0 references
- **WHEN** any module under `lib/set_orch/` is grepped for the literal string `"v0"`
- **THEN** the only matches SHALL be in test files OR comments referring to design-source provider semantics
- **AND** there SHALL be no `import` of v0-specific helpers in Layer 1 code

#### Scenario: detect_design_source returns plain str for forward-compat
- **WHEN** a future plugin returns `"figma-v2"` or `"storybook"` from `detect_design_source`
- **THEN** the ABC SHALL accept it without type errors (return type is `str`, not `Literal`)
- **AND** the dispatcher's branching logic SHALL handle unknown values by treating them as "design source present, profile-handled" (call `copy_design_source_slice` + `get_design_dispatch_context` regardless of the specific identifier)

### Requirement: Removal of legacy design provider methods

The `ProjectType` ABC SHALL REMOVE three legacy design provider methods replaced by the new design-source provider interface. All concrete profiles SHALL stop implementing them and all callers SHALL stop calling them, in the same atomic change.

Removed methods:
- `build_per_change_design(change_name, scope, wt_path, snapshot_dir) -> bool` — replaced by `copy_design_source_slice`
- `build_design_review_section(snapshot_dir) -> str` — replaced by the standalone `design-fidelity` integration gate (web module)
- `get_design_dispatch_context(scope, snapshot_dir) -> str` (old signature, no `change_name`) — replaced by the new signature `get_design_dispatch_context(change_name, scope, project_path) -> str`

#### Scenario: Old methods removed from ABC
- **WHEN** `ProjectType` ABC is inspected after the change
- **THEN** `build_per_change_design`, `build_design_review_section`, and the old-signature `get_design_dispatch_context` are NOT present
- **AND** `dir(ProjectType)` does not list them

#### Scenario: Concrete profiles do not retain old methods
- **WHEN** `NullProfile`, `CoreProfile`, `WebProjectType`, and any external profile in tests are inspected
- **THEN** none of them implement the removed method names
- **AND** any calls to the old method names raise `AttributeError`

#### Scenario: Dispatcher does not call removed methods
- **WHEN** `dispatcher.py` (and any code under `lib/set_orch/`) is inspected
- **THEN** no call sites to `build_per_change_design`, `build_design_review_section`, or the old-signature `get_design_dispatch_context` remain
- **AND** the dispatcher's design-context section uses ONLY the three new ABC methods

### Requirement: Dispatcher uses design-source provider methods

The dispatcher SHALL use the new ABC methods instead of any direct Figma / bridge.sh design extraction.

#### Scenario: Dispatcher orchestrates design-source population
- **WHEN** `dispatch_change()` runs
- **AND** the loaded profile's `detect_design_source(project_path)` returns a non-`"none"` value
- **THEN** the dispatcher computes `dest = openspec/changes/<change_name>/design-source/`
- **AND** calls `profile.copy_design_source_slice(change_name, scope, dest)`
- **AND** calls `profile.get_design_dispatch_context(change_name, scope, project_path)` for the markdown block
- **AND** the markdown block is written to a `## Design Source` section in `input.md`

#### Scenario: Dispatcher gracefully handles "none"
- **GIVEN** the profile reports `detect_design_source() == "none"`
- **WHEN** the dispatcher runs
- **THEN** it does NOT call `copy_design_source_slice` or `get_design_dispatch_context`
- **AND** dispatch proceeds without a Design Source section in input.md

#### Scenario: Profile method exception when design declared (HARD FAIL)
- **GIVEN** `profile.detect_design_source(project_path)` returns a non-`"none"` value
- **WHEN** any subsequent design provider method (`copy_design_source_slice` or `get_design_dispatch_context`) raises an exception during dispatch
- **THEN** the exception is logged at ERROR level with change_name + stack trace
- **AND** the dispatcher FAILS the change (not silent — design subsystem is broken; do not proceed with empty content masquerading as success)
- **AND** the change is marked failed with reason `design-provider-error` so the orchestration engine handles it via normal failure path (retry, escalation, etc.)
- **RATIONALE** (per design D8): when design is declared, exceptions in design code are real errors. Soft-failing here would silently dispatch the agent with no design context, producing wrong output that pixel-diff might not even catch (different content from a different starting point).

#### Scenario: Profile method exception when design absent (graceful)
- **GIVEN** `profile.detect_design_source(project_path)` returns `"none"`
- **WHEN** any design provider method is called at all (defensive code path) and raises
- **THEN** the exception is logged at DEBUG (not WARNING — no design declared, this is a no-op path bug if anything)
- **AND** dispatch proceeds (the methods should have returned empty in the first place; raising is itself the bug to log, but no design content was expected anyway)
