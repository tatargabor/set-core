## ADDED Requirements

## IN SCOPE
- Profile-driven spec section generation (core + project-type sections)
- Web module spec sections: data model, seed catalog, per-feature files, wireframes, test strategy
- Anti-pattern detection before spec assembly (LLM review, not regex linter)
- REQ-ID enforcement on every requirement (format compatible with decomposer's REQ-* parsing)
- WHEN/THEN scenario enforcement on every requirement
- Modular spec output (main + features/ + catalog/)
- Verification checklist auto-generation
- Orchestrator directives section
- Backwards compatibility with existing flat specs

## OUT OF SCOPE
- CLI spec tools (only the write-spec skill is modified)
- API/CLI/pipeline project types (only web implemented now, others can follow)
- Design MCP integration (existing design-bridge handles this separately)
- Decomposer changes (the spec format change is backwards-compatible — decomposer already parses REQ-* IDs)
- Programmatic spec linter (anti-pattern detection is advisory, performed by the Claude agent)

### Requirement: ProjectType ABC has spec_sections method
The `ProjectType` ABC SHALL define a `spec_sections()` method returning a list of spec section descriptors.

#### Scenario: Core profile returns core sections
- **WHEN** `CoreProfile.spec_sections()` is called
- **THEN** it SHALL return sections: `overview`, `requirements`, `orchestrator_directives`, `verification_checklist`
- **AND** each section SHALL have: `id`, `title`, `description`, `required` (bool), `phase` (int)
- **AND** the `requirements` section SHALL be project-type agnostic (asks "What are the main features?" not "What are the pages?")

#### Scenario: Web profile extends core sections
- **WHEN** `WebProjectType.spec_sections()` is called
- **THEN** it SHALL return core sections PLUS: `data_model`, `seed_catalog`, `pages_routes`, `auth_roles`, `i18n`, `design_tokens`, `test_strategy`
- **AND** web-specific sections SHALL have `required=True` for `data_model` and `pages_routes`

#### Scenario: NullProfile uses core only with generic prompts
- **WHEN** no profile is detected (NullProfile)
- **THEN** only core sections SHALL be presented
- **AND** the `requirements` section prompt SHALL be: "What are the main features/capabilities of this project?"
- **AND** no project-type-specific questions SHALL be asked

#### Scenario: Profile detection fails gracefully
- **WHEN** `python3 -c "from set_orch.profile_loader import ..."` fails (set-core not installed as package)
- **THEN** write-spec SHALL fall back to hardcoded core sections
- **AND** SHALL NOT error or abort

### Requirement: write-spec generates modular output
The write-spec skill SHALL generate a modular spec structure instead of a single flat file.

#### Scenario: Web project with multiple features
- **WHEN** the user describes 3+ features
- **THEN** write-spec SHALL create:
  - `docs/spec.md` — main file with overview, conventions, verification checklist
  - `docs/features/<feature-name>.md` — one file per feature with requirements and scenarios
- **AND** spec.md SHALL reference feature files with relative links
- **AND** `<feature-name>` SHALL be the kebab-case name the user gives (e.g., user describes "User Auth" → `docs/features/user-auth.md`)

#### Scenario: Web project with Prisma
- **WHEN** the project has `prisma/schema.prisma`
- **AND** the user defines seed data
- **THEN** write-spec SHALL create `docs/catalog/*.md` files for structured seed data
- **AND** spec.md SHALL reference catalog files in the Seed Data section

#### Scenario: Small project (fewer than 3 features)
- **WHEN** the user describes 1-2 features
- **THEN** write-spec MAY use a single `docs/spec.md` file with all sections inline
- **AND** SHALL still enforce REQ-IDs and scenarios

#### Scenario: Existing spec.md — ask before overwriting
- **WHEN** `docs/spec.md` already exists
- **THEN** write-spec SHALL ask the user: "A spec already exists. Overwrite, update in-place, or create alongside as docs/spec-v2.md?"
- **AND** SHALL NOT silently overwrite

### Requirement: Anti-pattern detection before assembly
The write-spec skill (Claude agent) SHALL review the assembled content for anti-patterns before writing files. This is an LLM advisory review, not a deterministic regex scanner.

#### Scenario: Code block detected in requirement
- **WHEN** a requirement section contains a fenced code block (triple backtick)
- **THEN** write-spec SHALL warn: "Requirements should describe WHAT, not HOW. Move code examples to design notes."
- **AND** SHALL ask the user whether to keep or remove the code block

#### Scenario: File path detected in requirement
- **WHEN** a requirement section references specific file paths (e.g., `src/lib/`, `app/api/`, `.ts`, `.tsx`, `.py`)
- **THEN** write-spec SHALL warn: "File paths lock implementation. Describe the behavior instead."

#### Scenario: Requirement without scenario
- **WHEN** a requirement has no WHEN/THEN scenario
- **THEN** write-spec SHALL block assembly and prompt: "Every requirement needs at least one scenario. Add a WHEN/THEN for: [requirement name]"

#### Scenario: Placeholder seed data
- **WHEN** seed data contains names like "Product 1", "Test Item", "Lorem ipsum", "Foo", "Bar"
- **THEN** write-spec SHALL warn: "Use realistic names. Generic placeholders produce generic apps."

### Requirement: REQ-ID and scenario enforcement
Every requirement in the spec output SHALL have an explicit REQ-ID and at least one WHEN/THEN scenario. The ID format SHALL be compatible with the decomposer's `REQ-*` parsing (templates.py).

#### Scenario: REQ-ID format
- **WHEN** write-spec generates a requirement
- **THEN** it SHALL have format `REQ-<DOMAIN>-<NN>` (e.g., `REQ-AUTH-01`, `REQ-CART-03`)
- **AND** the domain slug SHALL match the feature file name (e.g., `features/user-auth.md` → `REQ-USER-AUTH-01`)
- **AND** this format SHALL be parseable by the decomposer's existing `REQ-*` regex matching

#### Scenario: Scenario format
- **WHEN** write-spec generates a scenario
- **THEN** it SHALL use the format:
  - `#### Scenario: <description>`
  - `- **WHEN** <condition>`
  - `- **THEN** <expected outcome>`
- **AND** optionally include **AND** clauses for additional conditions/outcomes

### Requirement: Verification checklist auto-generation
The spec output SHALL include a verification checklist derived from requirements.

#### Scenario: Checklist generated from requirements
- **WHEN** spec assembly completes
- **THEN** a `## Verification Checklist` section SHALL be appended to spec.md
- **AND** each requirement SHALL have at least one checkbox item (`- [ ] ...`)
- **AND** items SHALL be grouped by feature/domain

### Requirement: Orchestrator directives section
The spec output SHALL include an orchestrator directives section with deployment hints.

#### Scenario: Web project directives
- **WHEN** the project type is web
- **THEN** the directives SHALL include: `max_parallel`, `review_before_merge`, `e2e_mode`
- **AND** write-spec SHALL ask the user for preferred values or use defaults (max_parallel: 3, review: true, e2e: per_change)

#### Scenario: Non-web project directives
- **WHEN** the project type is not web (or unknown)
- **THEN** the directives SHALL include only: `max_parallel`, `review_before_merge`
- **AND** defaults SHALL be: max_parallel: 2, review: true
