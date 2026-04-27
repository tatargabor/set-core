# project-insights-aggregator Specification

## Purpose
TBD - created by archiving change dynamic-category-injection. Update Purpose after archive.
## Requirements
### Requirement: Aggregator runs after each successful change merge
The orchestrator SHALL invoke the project-insights aggregator after every change transitions to the `merged` state. The aggregator SHALL read `category-classifications.jsonl` for the project, compute aggregate statistics, and write the result atomically to `.set/state/project-insights.json`.

#### Scenario: First merge populates insights
- **WHEN** the first change of a run merges
- **AND** `project-insights.json` does not exist yet
- **THEN** the aggregator SHALL create `project-insights.json` with `samples_n: 1`
- **AND** the file SHALL contain at least `by_change_type[<change_type>]` derived from the merged change

#### Scenario: Subsequent merges update incrementally
- **WHEN** a subsequent change merges
- **THEN** the aggregator SHALL re-read all JSONL records for the project
- **AND** SHALL recompute aggregates from the full record set (not incrementally apply)
- **AND** SHALL bump `samples_n` to match record count

#### Scenario: Aggregator failure does not block merge
- **WHEN** the aggregator raises an exception (e.g. JSONL read error, disk full)
- **THEN** the orchestrator SHALL log the error
- **AND** the merge SHALL still complete successfully
- **AND** subsequent dispatches SHALL behave as if no insights exist (cold start)

### Requirement: Insights record common categories per change_type
`project-insights.json` SHALL contain a `by_change_type` map keyed on change_type (`foundational`, `feature`, `infrastructure`, `schema`, `cleanup-before`, `cleanup-after`). Each entry SHALL list `common_categories` (categories appearing in ≥ 50 % of samples), `rare_categories` (categories appearing but in < 50 %), and `category_frequency` (count map normalized to ratio).

#### Scenario: Common categories computed correctly
- **WHEN** 4 of 5 `feature` changes in the project resolved to `frontend`
- **AND** 1 of 5 resolved to `frontend, auth`
- **THEN** `by_change_type.feature.common_categories` SHALL include `frontend` (100 %)
- **AND** SHALL NOT include `auth` (only 20 %)
- **AND** `by_change_type.feature.rare_categories` SHALL include `auth`
- **AND** `by_change_type.feature.category_frequency.auth` SHALL be `0.2`

#### Scenario: Empty change_type bucket is omitted
- **WHEN** no `schema` changes have merged in the project
- **THEN** `by_change_type` SHALL NOT contain a `schema` key

### Requirement: Resolver consults insights for bias
The change-category-resolver SHALL read `project-insights.json` (when present) and add `by_change_type[<current_change_type>].common_categories` to the deterministic union, BEFORE the per-change layers run.

#### Scenario: Common categories seed the deterministic baseline
- **WHEN** a new `feature` change dispatches
- **AND** `project-insights.json` lists `frontend` as common for `feature`
- **THEN** the resolver SHALL include `frontend` in the deterministic union even before per-change layers run
- **AND** the audit record SHALL include `signals.insights_layer: ["frontend"]`

#### Scenario: Insights bias does not override per-change negation
- **WHEN** insights mark `auth` as common, but the current change has change_type=`schema` (which has its own defaults)
- **THEN** the resolver SHALL NOT add `auth` (insights bias is keyed on the current change_type, not the project as a whole)

### Requirement: Sonnet prompt receives insights summary
When invoking the LLM classifier, the resolver SHALL include a one-paragraph project-insights summary in the prompt context, derived from `project-insights.json`.

#### Scenario: Insights summary present in prompt
- **WHEN** `project-insights.json` exists and shows the project rarely involves auth
- **THEN** the Sonnet prompt SHALL include a line like "This project's prior changes rarely involve auth/database/api"
- **AND** Sonnet SHALL be instructed to weight per-change scope over project pattern when they conflict

#### Scenario: Cold start without insights
- **WHEN** `project-insights.json` does not exist
- **THEN** the Sonnet prompt SHALL omit the project-insights summary block
- **AND** SHALL still be invoked normally with the per-change inputs

### Requirement: Aggregator records LLM agreement telemetry
`project-insights.json` SHALL include `deterministic_vs_llm` with `agreement_rate` (fraction of records where the two sets are equal) and `llm_added_categories` (count map of categories the LLM added beyond deterministic).

#### Scenario: Agreement rate computed across records
- **WHEN** 8 of 10 records show identical deterministic and LLM category sets
- **THEN** `deterministic_vs_llm.agreement_rate` SHALL be `0.8`
- **AND** `deterministic_vs_llm.llm_added_categories` SHALL aggregate the deltas from the 2 disagreeing records

#### Scenario: Cache-hit records excluded from agreement metric
- **WHEN** an audit record has `cache_hit: true`
- **THEN** the aggregator SHALL skip it for agreement calculations
- **AND** SHALL count it only in `samples_n`

### Requirement: Uncovered-category register tracks taxonomy gaps
The aggregator SHALL maintain `uncovered_categories` — a count map of categories the LLM proposed that were NOT in the profile's taxonomy at evaluation time. Entries persist across runs to support cross-run discovery via `set-harvest`.

#### Scenario: LLM proposes a non-taxonomy category
- **WHEN** Sonnet returns `rate-limiting` and the taxonomy does not include it
- **THEN** the audit record's `uncovered_categories` SHALL list it
- **AND** the aggregator SHALL increment `project-insights.uncovered_categories["rate-limiting"]`

#### Scenario: Operator adds the category to taxonomy
- **WHEN** an operator extends `category_taxonomy()` to include `rate-limiting`
- **AND** subsequent classifications include it
- **THEN** new audit records SHALL NOT mark it as uncovered
- **AND** the aggregator SHALL leave the historical `uncovered_categories["rate-limiting"]` count in place (historical record)

