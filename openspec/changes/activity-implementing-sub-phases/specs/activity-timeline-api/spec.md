## ADDED Requirements

### Requirement: Implementing spans carry a `sub_spans` field

The activity-timeline API SHALL include a `sub_spans` field on every `implementing` span in the response, regardless of whether any classifiable drilldown sub-spans were available for that span's window.

#### Scenario: Implementing span with no classifiable drilldown sub-spans

- **WHEN** the API returns an `implementing` span whose drilldown sub-span window contains only excluded categories (waits, gaps, overhead) or contains no sub-spans at all
- **THEN** the span SHALL include `sub_spans: []` (an empty list, not `null` and not omitted)

#### Scenario: Implementing span with classifiable drilldown sub-spans

- **WHEN** the API returns an `implementing` span whose drilldown sub-span window contains classifiable categories
- **THEN** the span SHALL include `sub_spans` as a non-empty list
- **AND** every entry SHALL have the keys `category`, `start`, `end`, `duration_ms`, `trigger_tool`, and `trigger_detail`
- **AND** `category` SHALL be one of `spec`, `code`, `test`, `build`, `subagent`, `other`
- **AND** the entries SHALL be ordered by `start` ascending and SHALL not overlap

#### Scenario: Sub-spans are confined to the parent's time window

- **WHEN** the API returns an `implementing` span with `sub_spans`
- **THEN** every sub-span's `start` SHALL be greater than or equal to the parent's `start`
- **AND** every sub-span's `end` SHALL be less than or equal to the parent's `end`

#### Scenario: Sub-spans need not cover the parent's full duration

- **WHEN** the API returns an `implementing` span with `sub_spans`
- **THEN** the union of sub-span durations MAY be less than the parent's `duration_ms` (waits, gaps, and excluded categories are intentionally not represented)
- **AND** the API consumer SHALL NOT assume the entries sum to the parent's duration

### Requirement: Sub-spans produced by the existing enrichment pass

The reducer SHALL populate the `sub_spans` field by calling the sub-phase classifier on the same drilldown sub-span data that is already loaded by the existing `implementing`-span enrichment block (the block currently producing the `llm_calls` / `tool_calls` / `subagent_count` aggregates), and SHALL share the per-change cache with that block to avoid loading the drilldown data twice.

#### Scenario: Drilldown cache is loaded at most once per change

- **GIVEN** an API response covering multiple `implementing` spans for the same change
- **WHEN** the enrichment pass runs
- **THEN** `_build_sub_spans_for_change` SHALL be called at most once for that change
- **AND** the resulting drilldown sub-spans SHALL be reused for both the existing aggregates and the new sub-phase classification

#### Scenario: Classifier failure does not break the enrichment pass

- **WHEN** the sub-phase classifier raises an exception while processing one change's data
- **THEN** the enrichment pass SHALL log the failure at DEBUG level
- **AND** that change's `implementing` spans SHALL still receive `sub_spans: []`
- **AND** other changes' `implementing` spans in the same response SHALL still be classified normally

### Requirement: Sub-span trigger metadata preservation

Every entry in a parent's `sub_spans` list SHALL carry the `trigger_tool` and `trigger_detail` fields drawn from the first contributing drilldown sub-span (after consecutive-merge), so the frontend can render tooltips and detail modals.

#### Scenario: Trigger metadata flows from drilldown `detail.preview`

- **WHEN** a drilldown sub-span has `category = "agent:tool:edit"` and `detail.preview = "openspec/changes/foo/proposal.md"` and `detail.tool = "Edit"`
- **THEN** the resulting rollup sub-span SHALL carry `trigger_tool = "Edit"` and `trigger_detail = "openspec/changes/foo/proposal.md"`

#### Scenario: Merged range carries the first sub-span's trigger only

- **GIVEN** five drilldown `agent:tool:edit` sub-spans contributing to one merged `code` rollup entry
- **WHEN** the rollup is produced
- **THEN** the entry's `trigger_tool` and `trigger_detail` SHALL be those of the first contributing drilldown sub-span
- **AND** the subsequent four sub-spans' triggers SHALL NOT be reflected (the merged range gets one representative trigger)

#### Scenario: Missing trigger metadata in source

- **WHEN** the contributing drilldown sub-span has no `detail.tool` or no `detail.preview`
- **THEN** the resulting rollup sub-span SHALL still be produced
- **AND** the missing field(s) SHALL be set to `null` in the API output (not omitted)
