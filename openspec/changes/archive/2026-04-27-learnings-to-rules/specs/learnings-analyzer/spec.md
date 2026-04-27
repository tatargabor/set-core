## ADDED Requirements

## IN SCOPE
- Pattern extraction from review-findings.jsonl (recurring issues across changes and runs)
- Pattern extraction from persistent memory (source:orchestrator,type:review-patterns)
- Rule candidate generation with structured metadata (severity, occurrence count, affected changes, suggested rule text)
- Scope classification: core (universal), plugin (web/base), project-specific (skip)
- Confidence scoring based on occurrence frequency and cross-run persistence
- Rule text generation from clustered patterns (markdown format with frontmatter)

## OUT OF SCOPE
- Auto-deploying rules without user approval (always requires explicit accept)
- LLM-based rule generation (use template-based generation from pattern data)
- Modifying existing rules (only creates new rule candidates)
- Cross-project pattern aggregation (analyzes one project's findings at a time)

### Requirement: Extract recurring patterns from findings
The analyzer SHALL read review-findings.jsonl and extract patterns that recur across multiple changes or multiple runs.

#### Scenario: Patterns across changes in one run
- **WHEN** the JSONL contains entries where the same normalized issue summary appears in 2+ different changes
- **THEN** the pattern SHALL be extracted with occurrence count, list of affected changes, and representative issue details (file, line, fix)

#### Scenario: Patterns across runs via memory
- **WHEN** persistent memory contains entries tagged `source:orchestrator,type:review-patterns` from prior runs
- **AND** the current run's findings overlap with memorized patterns
- **THEN** the pattern confidence SHALL be increased (cross-run recurrence is stronger signal)

#### Scenario: No recurring patterns
- **WHEN** all findings are unique to individual changes with no repetition
- **THEN** no rule candidates SHALL be generated

### Requirement: Generate rule candidates from patterns
The analyzer SHALL produce structured rule candidates that can be written as `.claude/rules/*.md` files.

#### Scenario: Rule candidate structure
- **WHEN** a recurring pattern qualifies as a rule candidate (≥3 occurrences across ≥2 changes)
- **THEN** the candidate SHALL include: id (kebab-case slug), title, description, severity, occurrence_count, affected_changes list, suggested_rule_text (markdown with optional globs frontmatter), and classification (core/web/base/project)

#### Scenario: Rule text format
- **WHEN** generating rule text from a pattern
- **THEN** the text SHALL follow the existing rule file format: optional YAML frontmatter with globs, markdown body with the guideline, and generalized examples (no project-specific paths or entity names)

### Requirement: Classify rule candidates by scope
The analyzer SHALL classify each candidate to determine where the rule should be deployed.

#### Scenario: Core classification
- **WHEN** a pattern is about generic coding practices (unused imports, missing error handling, type safety)
- **THEN** classification SHALL be "core" (goes to set-core/.claude/rules/)

#### Scenario: Plugin classification
- **WHEN** a pattern references framework-specific concepts (React components, API routes, middleware, CSS)
- **AND** a profile plugin is loaded that matches the framework
- **THEN** classification SHALL be the plugin name (e.g., "web") and the rule goes to the plugin's template

#### Scenario: Project-specific classification
- **WHEN** a pattern references specific file paths, entity names, or business logic unique to one project
- **THEN** classification SHALL be "project" and the rule goes to the project's local `.claude/rules/` only

### Requirement: Confidence thresholds
The analyzer SHALL apply minimum thresholds before generating rule candidates.

#### Scenario: Minimum threshold for suggestion
- **WHEN** a pattern has ≥3 occurrences across ≥2 changes
- **THEN** a rule candidate SHALL be generated with confidence "suggested"

#### Scenario: Higher threshold for strong recommendation
- **WHEN** a pattern has ≥5 occurrences across ≥3 changes OR appears in memory from ≥2 prior runs
- **THEN** the candidate SHALL have confidence "recommended"
