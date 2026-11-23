## ADDED Requirements

### IN SCOPE
- The `i18n.mode` axis on the web project type, with two values: `single` and `multi`.
- The default mode at `set-project init` time for the web template.
- Which template files are seeded in each mode.
- Which verification rules and orchestration directives are disabled per mode (overlay-driven).
- The location and shape of the mode flag and its declarative consequences (`set/plugins/project-type.yaml`).
- The single-mode replacement pattern for hardcoded strings (typed copy module).
- The runtime helper for reading the mode (`get_i18n_mode(project_path)`).
- Backwards-compatibility semantics for projects that predate this capability.

### OUT OF SCOPE
- The runtime behavior of `t('key')` calls, locale routing, sidecar files (covered by `i18n-conventions` and `cross-cutting-file-strategy`).
- The runtime hygiene rules that detect hardcoded strings (covered by `design-source-hygiene`, mode-aware).
- A `none` mode permitting hardcoded strings without any centralized copy discipline.
- Auto-detecting mode from spec text or other heuristics.
- Mid-project mode switching automation (codemods, migration tooling).
- External (non-`WebProjectType`) plugins adopting the same axis.
- Removing `next-intl` and `eslint-plugin-i18next` from `package.json` in single mode (cosmetic, deferred).

### Requirement: i18n mode is an explicit axis on the web project type
The web project type SHALL expose an `i18n.mode` axis with exactly two valid values: `single` and `multi`. The mode SHALL be settable at `set-project init` time via a `--i18n single|multi` flag. The mode SHALL be persisted in `set/plugins/project-type.yaml` under an `i18n:` block.

#### Scenario: Mode persisted at init time
- **WHEN** an operator runs `set-project init --project-type web --template nextjs --i18n single`
- **THEN** the resulting `set/plugins/project-type.yaml` SHALL contain a top-level `i18n:` block with `mode: single`

#### Scenario: Multi mode persisted
- **WHEN** an operator runs `set-project init --project-type web --template nextjs --i18n multi`
- **THEN** the resulting `set/plugins/project-type.yaml` SHALL contain `i18n.mode: multi`

#### Scenario: Invalid mode rejected
- **WHEN** an operator passes `--i18n none` or any value other than `single` or `multi`
- **THEN** `set-project init` SHALL exit with a non-zero status and an error message naming the valid values

### Requirement: Default mode is `single`
When `set-project init` is invoked for the web template without an explicit `--i18n` flag, the mode SHALL default to `single`.

#### Scenario: Default applied
- **WHEN** an operator runs `set-project init --project-type web --template nextjs` with no `--i18n` flag
- **THEN** `set/plugins/project-type.yaml` SHALL contain `i18n.mode: single`
- **AND** the project SHALL be seeded with single-mode files (no `messages/` directory, `src/copy/` present)

### Requirement: Single-mode seeded files
When mode is `single` at init time, the deployed project SHALL contain a typed copy module and a primary-locale constant, and SHALL NOT contain locale message files, the i18n completeness script, or the i18n-conventions rule file.

#### Scenario: Single mode files present
- **WHEN** init completes with `--i18n single`
- **THEN** `src/copy/index.ts` SHALL exist with an `as const` typed copy module
- **AND** `src/copy/locale.ts` SHALL exist exporting `PRIMARY_LOCALE`
- **AND** `.claude/rules/copy-module-conventions.md` SHALL exist

#### Scenario: Multi-mode files absent in single mode
- **WHEN** init completes with `--i18n single`
- **THEN** `messages/en.json` SHALL NOT exist
- **AND** `messages/hu.json` SHALL NOT exist
- **AND** `scripts/check-i18n-completeness.ts` SHALL NOT exist
- **AND** `.claude/rules/i18n-conventions.md` SHALL NOT exist

### Requirement: Multi-mode seeded files
When mode is `multi` at init time, the deployed project SHALL contain the existing multi-locale i18n machinery (locale message files, completeness script, i18n-conventions rule), and SHALL NOT contain the single-mode typed copy module.

#### Scenario: Multi mode files present
- **WHEN** init completes with `--i18n multi`
- **THEN** `messages/en.json` and `messages/hu.json` SHALL exist
- **AND** `scripts/check-i18n-completeness.ts` SHALL exist
- **AND** `.claude/rules/i18n-conventions.md` SHALL exist

#### Scenario: Single-mode files absent in multi mode
- **WHEN** init completes with `--i18n multi`
- **THEN** `src/copy/index.ts` SHALL NOT exist
- **AND** `src/copy/locale.ts` SHALL NOT exist
- **AND** `.claude/rules/copy-module-conventions.md` SHALL NOT exist

### Requirement: Single-mode overlay disables i18n-specific rules and directives
When mode is `single`, `set-project init` SHALL write a `set/plugins/project-type.yaml` overlay that disables the `i18n-completeness` verification rule and the `no-parallel-i18n` and `consolidate-i18n` orchestration directives via the existing `disabled_rules` / `disabled_directives` overlay keys consumed by `ProjectTypeResolver`.

#### Scenario: Disabled lists present in single mode
- **WHEN** init completes with `--i18n single`
- **THEN** `set/plugins/project-type.yaml` SHALL contain `disabled_rules` listing at least `i18n-completeness`
- **AND** SHALL contain `disabled_directives` listing at least `no-parallel-i18n` and `consolidate-i18n`

#### Scenario: Resolver honors single-mode overlay
- **WHEN** `ProjectTypeResolver.resolve_rules()` is called for a single-mode project
- **THEN** the returned rule list SHALL NOT include the `i18n-completeness` rule

#### Scenario: Resolver honors single-mode overlay (directives)
- **WHEN** `ProjectTypeResolver.resolve_directives()` is called for a single-mode project
- **THEN** the returned directive list SHALL NOT include `no-parallel-i18n` or `consolidate-i18n`

### Requirement: Multi-mode overlay leaves i18n rules and directives enabled
When mode is `multi`, `set-project init` SHALL NOT add `i18n-completeness`, `no-parallel-i18n`, or `consolidate-i18n` to any `disabled_rules` or `disabled_directives` list it writes.

#### Scenario: Multi mode preserves rules
- **WHEN** init completes with `--i18n multi`
- **AND** `ProjectTypeResolver.resolve_rules()` is called
- **THEN** the rule list SHALL include `i18n-completeness`

#### Scenario: Multi mode preserves directives
- **WHEN** init completes with `--i18n multi`
- **AND** `ProjectTypeResolver.resolve_directives()` is called
- **THEN** the directive list SHALL include both `no-parallel-i18n` and `consolidate-i18n`

### Requirement: `cross_cutting_files.i18n` reflects mode
The `cross_cutting_files.i18n` list in `project-knowledge.yaml` SHALL reference the mode-appropriate files: `["messages/*.json"]` in multi mode, `["src/copy/index.ts", "src/copy/locale.ts"]` in single mode.

#### Scenario: Single-mode cross-cutting list
- **WHEN** init completes with `--i18n single`
- **THEN** `project-knowledge.yaml` `cross_cutting_files.i18n` SHALL be `["src/copy/index.ts", "src/copy/locale.ts"]`

#### Scenario: Multi-mode cross-cutting list
- **WHEN** init completes with `--i18n multi`
- **THEN** `project-knowledge.yaml` `cross_cutting_files.i18n` SHALL be `["messages/*.json"]`

#### Scenario: Cross-cutting-review directive remains active in single mode
- **WHEN** an agent's change modifies `src/copy/index.ts` in a single-mode project
- **THEN** the `cross-cutting-review` directive SHALL flag the change (because the file is listed in `cross_cutting_files.i18n`)

### Requirement: `primary_locale` is captured at init and propagated to the copy module
`set-project init --i18n single` SHALL accept an optional `--primary-locale <BCP-47-tag>` flag, default `en-US`. The chosen locale SHALL be written to `set/plugins/project-type.yaml` under `i18n.primary_locale` AND substituted into `src/copy/locale.ts` as the value of the `PRIMARY_LOCALE` constant.

#### Scenario: Default locale used
- **WHEN** init completes with `--i18n single` and no `--primary-locale` flag
- **THEN** `set/plugins/project-type.yaml` SHALL contain `i18n.primary_locale: en-US`
- **AND** `src/copy/locale.ts` SHALL export `PRIMARY_LOCALE = "en-US"`

#### Scenario: Custom locale captured
- **WHEN** init completes with `--i18n single --primary-locale hu-HU`
- **THEN** `set/plugins/project-type.yaml` SHALL contain `i18n.primary_locale: hu-HU`
- **AND** `src/copy/locale.ts` SHALL export `PRIMARY_LOCALE = "hu-HU"`

#### Scenario: Locale ignored in multi mode
- **WHEN** init completes with `--i18n multi --primary-locale hu-HU`
- **THEN** the locale value SHALL be recorded in `set/plugins/project-type.yaml` for documentation purposes
- **AND** SHALL NOT alter any seeded file (multi mode handles locale via next-intl middleware, not a constant)

### Requirement: `get_i18n_mode(project_path)` runtime helper with default-multi fallback
A helper function SHALL be exposed from `lib/set_orch/profile_loader.py` named `get_i18n_mode(project_path)` that reads `set/plugins/project-type.yaml` for the project and returns `"single"` or `"multi"`. The helper SHALL return `"multi"` when the file is missing, the `i18n` block is absent, the `mode` key is absent, or the value is not exactly the string `"single"`.

#### Scenario: Helper returns single
- **GIVEN** `set/plugins/project-type.yaml` contains `i18n.mode: single`
- **WHEN** `get_i18n_mode(project_path)` is called
- **THEN** it SHALL return `"single"`

#### Scenario: Helper returns multi when explicitly set
- **GIVEN** `set/plugins/project-type.yaml` contains `i18n.mode: multi`
- **WHEN** `get_i18n_mode(project_path)` is called
- **THEN** it SHALL return `"multi"`

#### Scenario: Helper falls back to multi when file missing
- **GIVEN** `set/plugins/project-type.yaml` does not exist
- **WHEN** `get_i18n_mode(project_path)` is called
- **THEN** it SHALL return `"multi"`

#### Scenario: Helper falls back to multi when block absent
- **GIVEN** `set/plugins/project-type.yaml` exists but contains no `i18n:` block
- **WHEN** `get_i18n_mode(project_path)` is called
- **THEN** it SHALL return `"multi"`

#### Scenario: Helper falls back to multi for unknown values
- **GIVEN** `set/plugins/project-type.yaml` contains `i18n.mode: none` (or any string other than `single`/`multi`)
- **WHEN** `get_i18n_mode(project_path)` is called
- **THEN** it SHALL return `"multi"` and log a warning at WARNING level naming the unknown value

### Requirement: Backwards compatibility for projects predating this capability
Projects whose `set/plugins/project-type.yaml` was generated before this capability existed (and therefore lack the `i18n` block) SHALL retain the full multi-mode pipeline behavior with no migration step required.

#### Scenario: Pre-existing project keeps multi behavior
- **GIVEN** a project initialized before this change, with `set/plugins/project-type.yaml` containing only `type: web` and `template: nextjs`
- **WHEN** the orchestration engine runs against the project
- **THEN** all current i18n verification rules and orchestration directives SHALL be applied (i.e., the project behaves identically to before this capability shipped)

#### Scenario: Pre-existing project with messages/ keeps gates working
- **GIVEN** a pre-existing project with populated `messages/en.json` and `messages/hu.json`
- **WHEN** an agent dispatches a change in that project
- **THEN** the dispatch context SHALL include i18n sidecar instructions
- **AND** the verify pipeline SHALL include the `i18n_check` gate

### Requirement: Single-mode typed copy module is the canonical UI string location
In single-mode projects, all user-visible strings (labels, buttons, messages, errors, empty states, tooltips, aria-label values) SHALL be referenced via the typed `copy` import from `src/copy/index.ts`. The pattern SHALL be: declare the string as a property of the `as const` `copy` object; consume via `import { copy } from "@/copy"` and a typed property reference.

#### Scenario: Component uses typed copy
- **WHEN** a component renders a user-visible string in a single-mode project
- **THEN** the source SHALL contain `copy.<namespace>.<key>` rather than a hardcoded string literal

#### Scenario: Locale-aware Intl call uses PRIMARY_LOCALE
- **WHEN** a single-mode component formats a date or currency
- **THEN** the source SHALL pass `PRIMARY_LOCALE` from `src/copy/locale.ts` to the `Intl.*` or `toLocale*` call rather than a hardcoded locale string

#### Scenario: Migration-ready structure preserved
- **WHEN** strings are added to `src/copy/index.ts`
- **THEN** they SHALL be organized in nested namespaces matching the structure that `messages/<locale>.json` would use in multi-mode (so a future single → multi migration is a 1:1 dictionary serialization)

### Requirement: CLI flag flow into manifest module selection
The `--i18n` flag SHALL be implemented by translating the value into the manifest module list passed to `deploy_templates()`: `--i18n single` SHALL select the `i18n-single` manifest module; `--i18n multi` SHALL select the `i18n-multi` manifest module. This selection composes with any explicit `--modules` passed by the operator (the i18n-derived module is added, not substituted).

#### Scenario: Single mode adds i18n-single module
- **WHEN** `set-project init --i18n single --modules integrations` is invoked
- **THEN** the deployed manifest modules SHALL be exactly `{i18n-single, integrations}`

#### Scenario: Multi mode adds i18n-multi module
- **WHEN** `set-project init --i18n multi --modules integrations` is invoked
- **THEN** the deployed manifest modules SHALL be exactly `{i18n-multi, integrations}`

#### Scenario: Conflict raises error
- **WHEN** an operator passes both `--i18n single` and `--modules i18n-multi` (contradictory selection)
- **THEN** `set-project init` SHALL exit with a non-zero status and an error message naming the conflict
