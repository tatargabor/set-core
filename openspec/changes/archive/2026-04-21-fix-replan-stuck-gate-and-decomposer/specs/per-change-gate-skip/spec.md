## ADDED Requirements

### Requirement: Content-aware gate selector
The gate registry SHALL select gates for a change by scanning BOTH the change's declared `touched_file_globs` (from the decomposer) AND the actual files touched by the agent's first commit. Selection SHALL be additive: a gate is included if the static `gate_hints` OR the content scan flags it as relevant. Selection SHALL NEVER subtract gates that `gate_hints` explicitly enables.

The prior behavior — gate set determined solely by `change_type` — SHALL be replaced by this content-aware selector. `change_type` may still inform defaults but does not override content signals.

#### Scenario: Foundation change with UI content activates design+e2e
- **WHEN** a change has `change_type=infrastructure` and `gate_hints={}` but the scope contains globs matching `src/app/**/*.tsx` or `src/components/**/*.tsx`
- **THEN** the gate registry SHALL include `design-fidelity`, `e2e`, and `i18n_check`
- **AND** the selection SHALL be logged: `Gate selection: UI content detected for <change> — added design-fidelity, e2e, i18n_check`

#### Scenario: Server-only change activates unit tests
- **WHEN** a change's globs match only `src/server/**` or `src/lib/**` with no UI globs
- **THEN** the gate registry SHALL include `test` (unit)
- **AND** SHALL NOT include `design-fidelity`

#### Scenario: gate_hints wins over content scan
- **WHEN** a change has `gate_hints={"e2e": "require"}` and content scan would skip e2e
- **THEN** the gate registry SHALL include `e2e`

### Requirement: Re-detection on first-commit poll
Re-detection SHALL be triggered by the engine's monitor poll loop at the exact point when `new_commits_since_dispatch` transitions from 0 to a positive integer for the first time on a change. This is a one-shot operation per change: subsequent polls SHALL NOT re-run content detection even as more commits arrive. Re-detection MAY add gates to the active set. It SHALL NOT remove gates that are already registered.

#### Scenario: Monitor poll observes first commit
- **WHEN** `engine.monitor_loop()` polls a change whose prior snapshot had `new_commits_since_dispatch == 0` and the current git state shows `new_commits_since_dispatch == 1`
- **AND** the change has not yet been re-detected (`gate_recheck_done == False`)
- **THEN** the engine SHALL invoke `gate_registry.redetect(change)` BEFORE running the verify pipeline on the current poll
- **AND** `change.gate_recheck_done` SHALL be set to `True` so subsequent polls skip re-detection

#### Scenario: Agent commits UI file not in original scope
- **WHEN** the original scope listed only server-path globs (e.g. `src/server/promotions/**`) but the agent's first commit includes a UI file (e.g. `src/app/admin/promotions/page.tsx`)
- **THEN** the gate registry SHALL add `design-fidelity`, `e2e`, `i18n_check` to the active gate set
- **AND** SHALL emit a `GATE_SET_EXPANDED` event with fields `{change, added_gates: [...], reason: "post-commit content detection"}`

#### Scenario: Re-detection does not remove existing gates
- **WHEN** re-detection runs and the content scan flags fewer gates than the current set
- **THEN** the active gate set SHALL remain unchanged
- **AND** no `GATE_SET_EXPANDED` event SHALL be emitted

### Requirement: Content-tag to gate-name mapping
The gate registry SHALL define a single authoritative mapping from `classify_content()` tags to concrete gate names. The default mapping (provided by core) SHALL be:

- `"ui"` → `{"design-fidelity", "i18n_check"}`
- `"e2e_ui"` → `{"e2e"}`
- `"server"` → `{"test"}` (unit tests)
- `"schema"` → `{"build"}` (prisma generate + build)
- `"docs"` → `{}` (no gates)
- `"config"` → `{"build"}`
- `"i18n_catalog"` → `{"i18n_check"}`

Profiles MAY extend the mapping via `ProjectType.content_tag_to_gates() -> dict[str, set[str]]` but SHALL NOT remove core entries.

#### Scenario: Web profile inherits core mapping
- **WHEN** the active profile is `WebProjectType` and `classify_content()` returns `{"ui", "e2e_ui"}`
- **THEN** the gate selector SHALL resolve the tags to `{"design-fidelity", "i18n_check", "e2e"}`

#### Scenario: Profile can add but not remove mappings
- **WHEN** a profile overrides `content_tag_to_gates()` to add `"ui" → {"accessibility"}`
- **THEN** the effective mapping for `"ui"` SHALL be the union `{"design-fidelity", "i18n_check", "accessibility"}`
- **AND** profiles SHALL NOT be able to cause `"ui"` to exclude `"design-fidelity"`

### Requirement: Content classifier
The gate registry SHALL use a content classifier module that maps globs to gate-relevance flags. The classifier SHALL live in `lib/set_orch/gate_registry.py` as `classify_content(globs) -> set[str]` returning a set of `{"ui", "e2e_ui", "server", "schema", "docs", "config", "i18n_catalog"}`. The mapping SHALL be defined per-profile in `ProjectType.content_classifier_rules()` so the web module can supply web-specific rules while core provides safe defaults.

#### Scenario: Web profile classifier
- **WHEN** `classify_content(["src/app/[locale]/**/*.tsx"])` is called with the `WebProjectType` active
- **THEN** the returned set SHALL include `"ui"` and `"e2e_ui"`

#### Scenario: Core profile classifier fallback
- **WHEN** the active profile is `CoreProfile` (NullProfile-like) and no module classifier is registered
- **THEN** `classify_content()` SHALL return an empty set
- **AND** gate selection SHALL fall back to `gate_hints` only
