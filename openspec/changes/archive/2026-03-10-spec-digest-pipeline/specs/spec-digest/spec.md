## ADDED Requirements

### Requirement: Directory spec input
The system SHALL accept a directory path as spec input to `wt-orchestrate plan --spec <path>` and `wt-orchestrate digest --spec <path>`. When the path is a directory, the system SHALL discover all `.md` files recursively and treat them as a multi-file specification. The directory branch SHALL be added to `find_input()` in `lib/orchestration/utils.sh`.

#### Scenario: Directory input resolves all markdown files
- **WHEN** user runs `wt-orchestrate plan --spec docs/v1-project/`
- **THEN** `find_input()` sets `INPUT_MODE="digest"` and `INPUT_PATH` to the absolute directory path

#### Scenario: Single file input unchanged
- **WHEN** user runs `wt-orchestrate plan --spec docs/v1.md`
- **THEN** the existing single-file flow is used (`INPUT_MODE="spec"`) with no digest phase
- **AND** planner prompt construction, plan output schema, and downstream dispatch are unaffected

#### Scenario: Master file detection
- **WHEN** the spec directory contains a file matching `v*-*.md` or `README.md` at root level
- **THEN** the system identifies it as the master file and reads it first for structure context

#### Scenario: Empty spec directory
- **WHEN** user runs `wt-orchestrate digest --spec docs/empty-dir/` and the directory contains no `.md` files
- **THEN** the system exits with error: "No .md files found in <path>" and exit code 1

#### Scenario: Non-existent path
- **WHEN** user runs `wt-orchestrate digest --spec docs/nonexistent/`
- **THEN** the system exits with error: "Path not found: <path>" and exit code 1

### Requirement: Spec file classification
The digest SHALL classify each spec file into one of four categories: `convention` (project-wide rules), `feature` (behavioral requirements), `data` (entity definitions/catalogs), or `execution` (implementation plans/checklists). Classification determines which digest output each file contributes to.

#### Scenario: Convention files identified
- **WHEN** the spec directory contains files defining i18n routing patterns, design system tokens, or SEO rules that apply across all features
- **THEN** the digest classifies them as `convention` and extracts rules into `conventions.json`

#### Scenario: Feature files identified
- **WHEN** the spec directory contains files describing specific feature behaviors (cart operations, user registration flows, admin CRUD)
- **THEN** the digest classifies them as `feature` and extracts behavioral requirements into `requirements.json`

#### Scenario: Data files identified
- **WHEN** the spec directory contains files listing product catalogs, seed data, or entity inventories with attributes
- **THEN** the digest classifies them as `data` and summarizes them in `data-definitions.md`
- **AND** individual data entries (e.g., each product) do NOT generate REQ-* IDs

#### Scenario: Execution files identified
- **WHEN** the spec directory contains files describing implementation order, change scope, or verification checklists
- **THEN** the digest classifies them as `execution` and stores references in `index.json` `execution_hints`
- **AND** they do NOT generate REQ-* IDs

#### Scenario: Mixed-content file
- **WHEN** a single spec file contains both convention rules and feature behaviors (e.g., i18n routing rules + feature-specific i18n requirements)
- **THEN** the convention portions go to `conventions.json` and the feature behaviors go to `requirements.json`

### Requirement: Digest generation
The system SHALL process a multi-file spec into a structured digest at `wt/orchestration/digest/`. The digest contains: `index.json` (file manifest with `spec_base_dir`), `conventions.json` (project-wide rules), `data-definitions.md` (entity/catalog summaries), `requirements.json` (behavioral requirements with IDs), `dependencies.json` (requirement cross-references), `coverage.json` (initially empty `{}`), `ambiguities.json` (detected spec issues), and `domains/*.md` (domain summaries).

#### Scenario: Digest from directory spec
- **WHEN** user runs `wt-orchestrate digest --spec docs/v1-project/`
- **THEN** the system creates `wt/orchestration/digest/` with all eight output types (index.json, conventions.json, data-definitions.md, requirements.json, dependencies.json, coverage.json, ambiguities.json, domains/*.md)
- **AND** `index.json` contains `spec_base_dir` (absolute path), `source_hash`, file list, file classifications, and timestamp

#### Scenario: Digest from single file spec
- **WHEN** user runs `wt-orchestrate digest --spec docs/v1.md`
- **THEN** the system creates a digest with one domain and treats the single file as the only spec source

#### Scenario: Digest with dry-run
- **WHEN** user runs `wt-orchestrate digest --spec docs/v1-project/ --dry-run`
- **THEN** the system prints the digest output to stdout without writing files

#### Scenario: Digest output uses JSON for structured data
- **WHEN** digest generates structured files (index, requirements, dependencies, coverage)
- **THEN** all structured files use JSON format parseable by `jq`
- **AND** domain summaries use Markdown format

#### Scenario: Empty coverage.json skeleton
- **WHEN** digest creates `coverage.json`
- **THEN** the file contains `{"coverage": {}, "uncovered": []}` (valid JSON, not a zero-byte file)

### Requirement: Digest prompt construction
The digest SHALL use a single Claude API call with all spec files concatenated in the prompt. The prompt SHALL instruct the model to: identify discrete independently-testable requirements, assign IDs in `REQ-{DOMAIN}-{NNN}` format, group files into domains, and detect cross-file dependencies.

#### Scenario: Prompt includes all spec files
- **WHEN** the spec directory contains 34 files totaling 3500 lines
- **THEN** the digest prompt includes all file contents with file path headers

#### Scenario: Prompt instructs granular requirement extraction
- **WHEN** the digest prompt is constructed
- **THEN** it contains the instruction: "One requirement = one independently testable behavior. If it needs its own test case, it is a separate requirement."

#### Scenario: Prompt instructs classification
- **WHEN** the digest prompt is constructed
- **THEN** it contains classification instructions: "Classify each file as convention (project-wide rules), feature (specific behaviors), data (entity catalogs/seed data), or execution (implementation plans/checklists). Convention rules go to conventions.json. Data summaries go to data-definitions.md. Only feature behaviors get REQ-* IDs. Execution files become execution_hints."

#### Scenario: Prompt instructs cross-cutting detection
- **WHEN** the digest prompt is constructed
- **THEN** it contains the instruction: "Identify cross-cutting requirements that span multiple features (i18n integration, responsive layout, auth checks). Mark them with `cross_cutting: true` and list which domains they affect."

#### Scenario: Prompt instructs implicit dependency detection
- **WHEN** the digest prompt is constructed
- **THEN** it contains the instruction: "Also identify IMPLICIT dependencies: cases where implementing feature A requires data or state from feature B, even if there is no explicit text reference between the source files."

#### Scenario: Prompt instructs de-duplication
- **WHEN** the digest prompt is constructed
- **THEN** it contains the instruction: "If a master file contains a verification checklist or acceptance criteria that restates requirements from feature files, do NOT create duplicate REQ-* IDs. Each unique behavior gets exactly one ID, sourced from the most detailed description."

#### Scenario: Prompt instructs ambiguity detection
- **WHEN** the digest prompt is constructed
- **THEN** it contains the instruction: "Report underspecified behaviors, contradictory definitions across files, and missing cross-references (e.g., feature A references a template in feature B that does not exist) in a separate ambiguities section."

#### Scenario: Prompt instructs embedded rule extraction
- **WHEN** the digest prompt is constructed
- **THEN** it contains the instruction: "Data files (catalogs, seed data) may contain embedded behavioral rules (business logic, calculations, validation rules). Extract these as separate REQ-* IDs even though the file is classified as data. Individual data entries (each product, each item) are NOT requirements."

### Requirement: Requirement identification
The digest agent SHALL identify discrete, independently testable requirements from the spec files. Each requirement gets a unique ID in format `REQ-{DOMAIN}-{NNN}`.

#### Scenario: Requirements extracted with IDs
- **WHEN** digest processes a spec directory containing cart and subscription features
- **THEN** `requirements.json` contains entries with IDs like `REQ-CART-001`, `REQ-SUB-001`
- **AND** each entry has: `id`, `title`, `source` (file path), `source_section`, `domain`, `brief` (1-2 sentence summary), and optionally `cross_cutting` (boolean) + `affects_domains` (list)

#### Scenario: Cross-cutting requirement identified
- **WHEN** a requirement like "all routes must support HU/EN language switching" spans multiple features
- **THEN** the requirement entry has `"cross_cutting": true` and `"affects_domains": ["commerce", "content", "admin"]`
- **AND** the requirement is listed in `requirements.json` with its primary domain

### Requirement: Re-digest ID stability
When re-running digest on modified specs, the system SHALL preserve existing requirement IDs where possible by matching on `source` + `source_section`.

#### Scenario: Existing requirements keep their IDs
- **WHEN** re-digest runs and `requirements.json` already exists
- **AND** a requirement with `source: "features/cart.md"` and `source_section: "Anonymous cart"` matches an existing ID `REQ-CART-001`
- **THEN** the requirement retains `REQ-CART-001` in the new output

#### Scenario: New requirements get new IDs
- **WHEN** re-digest finds a requirement not matching any existing entry
- **THEN** it assigns the next available ID in that domain (e.g., `REQ-CART-004` if 001-003 exist)

#### Scenario: Removed requirements marked as removed
- **WHEN** re-digest runs and an existing requirement ID has no matching entry in the new spec
- **THEN** the requirement is kept in `requirements.json` with `"status": "removed"`
- **AND** `coverage.json` references remain valid (not deleted)

#### Scenario: Section rename produces new ID
- **WHEN** a user renames a spec section heading and re-runs digest
- **THEN** the old requirement becomes `status: removed` and a new requirement with a new ID is created
- **AND** `wt-orchestrate coverage` reports the orphaned coverage entry

### Requirement: Domain grouping
The digest SHALL group spec files into domains based on directory structure (if present) or topic similarity. Each domain produces a markdown summary. Domain count is not enforced — it follows the natural spec structure.

#### Scenario: Directory-based domains
- **WHEN** spec files are organized in subdirectories (`catalog/`, `features/`, `admin/`)
- **THEN** domains map to these directories (one domain per directory)

#### Scenario: Domain summary content
- **WHEN** a domain summary is generated for `commerce` (covering cart, checkout, subscription)
- **THEN** `domains/commerce.md` contains: overview paragraph, list of features, key cross-references to other domains, and count of requirements in this domain

#### Scenario: Empty dependencies
- **WHEN** a spec has a single domain with no cross-file references
- **THEN** `dependencies.json` contains `{"dependencies": []}` (valid JSON, not missing)

### Requirement: Cross-reference detection
The digest SHALL identify dependencies between requirements across files.

#### Scenario: Cross-file dependency detected
- **WHEN** `subscription.md` references cart session handling defined in `cart-checkout.md`
- **THEN** `dependencies.json` contains an entry: `{"from": "REQ-SUB-001", "to": "REQ-CART-001", "type": "depends_on"}`

### Requirement: Stale digest detection
The system SHALL detect when the raw spec has changed since last digest by comparing source hashes.

#### Scenario: Spec modified after digest
- **WHEN** planner runs and `index.json` `source_hash` does not match current spec files hash
- **THEN** the system warns "Digest is stale" and auto-re-digests before proceeding with planning

#### Scenario: Spec unchanged
- **WHEN** planner runs and source hash matches
- **THEN** the existing digest is reused without re-processing

### Requirement: Automatic digest trigger
When the planner detects a directory input without an existing fresh digest, it SHALL automatically run the digest phase before planning.

#### Scenario: Auto-digest on first plan
- **WHEN** user runs `wt-orchestrate plan --spec docs/v1-project/` and no `wt/orchestration/digest/` exists
- **THEN** the system runs digest automatically, then proceeds with planning using the digest

#### Scenario: Auto-digest skipped when digest exists and fresh
- **WHEN** `wt/orchestration/digest/index.json` exists and `source_hash` matches
- **THEN** the planner skips digest and uses existing digest directly

### Requirement: Verification checklist de-duplication
The digest SHALL de-duplicate requirements that appear both in a master file's verification checklist and in detailed feature files. Each independently testable behavior SHALL produce exactly one REQ-* ID.

#### Scenario: Checklist item matches feature requirement
- **WHEN** the master file's verification checklist says "Coffee catalog shows 8 products in responsive grid"
- **AND** product-catalog.md describes the same behavior in detail
- **THEN** only one REQ-* ID is created (from the detailed source), not two

#### Scenario: Checklist item with no feature file match
- **WHEN** the master file's verification checklist describes a behavior not found in any feature file
- **THEN** a new REQ-* ID is created with `source` pointing to the master file

### Requirement: Ambiguity detection
The digest SHALL identify underspecified, contradictory, or missing-reference issues in the spec and report them in `ambiguities.json`.

#### Scenario: Underspecified behavior detected
- **WHEN** a spec file describes a behavior without sufficient detail (e.g., "cart merge on login" without specifying duplicate handling strategy)
- **THEN** `ambiguities.json` contains an entry with `type: "underspecified"` and a description of what is missing

#### Scenario: Missing cross-reference detected
- **WHEN** feature A references a template/entity/behavior in feature B that does not exist in B's spec file (e.g., subscription.md references "payment failure email" but email-notifications.md has no such template)
- **THEN** `ambiguities.json` contains an entry with `type: "missing_reference"` listing both source and target files

#### Scenario: Contradictory definitions detected
- **WHEN** two spec files define the same concept differently (e.g., shipping rates defined in both cart-checkout.md and subscription.md with different values)
- **THEN** `ambiguities.json` contains an entry with `type: "contradictory"` listing both sources

#### Scenario: Ambiguities shown in dry-run
- **WHEN** user runs `wt-orchestrate digest --dry-run`
- **THEN** detected ambiguities are printed to stdout in a human-readable format

### Requirement: Embedded behavioral rules in data files
The digest SHALL extract behavioral rules embedded in data-classified files as separate REQ-* IDs, even though the file is primarily `data`.

#### Scenario: Behavioral rule in catalog file
- **WHEN** a catalog file (classified as `data`) contains business logic like "bundle stock = minimum of component stocks" or "gift card code format GC-XXXX-XXXX"
- **THEN** each behavioral rule gets a REQ-* ID in `requirements.json` with `source` pointing to the data file
- **AND** the data file's entity definitions still go to `data-definitions.md` (not duplicated as requirements)

#### Scenario: Variant system rules in product catalog
- **WHEN** a catalog file defines a variant matrix (form × size combinations, price modifiers per variant type)
- **THEN** the variant system rules get REQ-* IDs (e.g., "REQ-CATALOG-001: Variant price modifier for ground coffee")
- **AND** individual product entries (each coffee, each equipment) remain as data definitions only

### Requirement: Digest CLI error handling
The `wt-orchestrate digest` command SHALL handle errors gracefully.

#### Scenario: Write permission error
- **WHEN** `wt/orchestration/digest/` cannot be created due to permissions
- **THEN** the system exits with error: "Cannot create digest directory: <path>" and exit code 1

#### Scenario: Claude API failure during digest
- **WHEN** the Claude API call fails or returns unparseable output
- **THEN** the system exits with error: "Digest generation failed: <reason>" and exit code 1
- **AND** no partial files are written to `wt/orchestration/digest/`
