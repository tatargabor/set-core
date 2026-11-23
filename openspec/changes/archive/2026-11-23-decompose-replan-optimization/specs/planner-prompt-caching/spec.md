## ADDED Requirements

<!--
IN SCOPE:
- Layered Anthropic `cache_control` breakpoints on every planner-side Claude call.
- Refactor of `render_planning_prompt`, `render_brief_prompt`, `render_domain_decompose_prompt`, `render_merge_prompt`, and `_DIGEST_PROMPT_TEMPLATE` to return `list[ContentBlock]` instead of a single string.
- Per-layer TTL selection (1 h for tools/system/rules; 5 min for digest; uncached for spec tail / replan delta).
- Cascade-invalidation discipline: order of cached blocks is stable and codified.
- Observability: cache hit/miss tokens recorded in `LLM_CALL` events.

OUT OF SCOPE:
- Caching of agent-side prompts (covered by separate session-resume work).
- Anthropic SDK upgrades.
- Custom cache backends — Anthropic prompt cache only.
-->

### Requirement: Planner prompts return content blocks
Every planner-side prompt builder (`render_planning_prompt`, `render_brief_prompt`, `render_domain_decompose_prompt`, `render_merge_prompt`, `_DIGEST_PROMPT_TEMPLATE`) SHALL return a list of message content blocks (`list[ContentBlock]`) instead of a single concatenated string. Each block SHALL be one of `TextBlock`, `SystemBlock`, or equivalent SDK type accepted by `subprocess_utils.run_claude`.

#### Scenario: Planning prompt builder returns blocks
- **WHEN** `render_planning_prompt(...)` is called
- **THEN** it SHALL return a list with at least four blocks ordered: tools/output-skeleton block, system+rules block, digest-stable block, spec-tail block
- **AND** each block SHALL be a content-block dict with `type`, `text`, and optional `cache_control` keys

#### Scenario: Caller passes blocks to Claude
- **WHEN** `planner.run_planning_pipeline()` invokes Claude with the rendered blocks
- **THEN** `subprocess_utils.run_claude()` SHALL pass the blocks through to the Anthropic SDK without flattening to a string

### Requirement: Cache breakpoints on stable layers
The system SHALL place `cache_control: {"type": "ephemeral", "ttl": "1h"}` on the tools/output-skeleton block and on the system+rules block of every planner-side prompt.

#### Scenario: Tools layer cached with 1h TTL
- **WHEN** any planner-side prompt is built
- **THEN** the first content block (tools schema + JSON output skeleton) SHALL carry `cache_control={"type": "ephemeral", "ttl": "1h"}`

#### Scenario: System+rules layer cached with 1h TTL
- **WHEN** any planner-side prompt is built
- **THEN** the system+rules block (containing `_PLANNING_RULES_CORE` and project conventions) SHALL carry `cache_control={"type": "ephemeral", "ttl": "1h"}`

### Requirement: Cache breakpoint on digest layer
The system SHALL place `cache_control: {"type": "ephemeral", "ttl": "5m"}` on the digest-stable block of any prompt that includes the digest (planning, domain decompose, merge).

#### Scenario: Digest layer cached with 5m TTL
- **WHEN** a prompt includes the digest content (requirements.json, conventions.json, domains/*.md)
- **THEN** the digest-stable block SHALL carry `cache_control={"type": "ephemeral", "ttl": "5m"}`

### Requirement: Spec-tail and replan delta uncached
The system SHALL NOT place `cache_control` on the volatile spec-tail / replan-delta block of any planner-side prompt.

#### Scenario: Volatile block has no cache_control
- **WHEN** a prompt is built with replan context (Already Completed, E2E Failures, audit gaps) or with the per-cycle spec tail
- **THEN** that block SHALL be emitted without a `cache_control` field

### Requirement: Cascade-invalidation order is stable
The system SHALL preserve a single canonical block order: tools → system+rules → digest → volatile. Reorderings SHALL fail a CI assertion.

#### Scenario: Block order assertion in CI
- **WHEN** the test suite runs the planner-prompt block-order test
- **THEN** every render function output SHALL match the canonical order
- **AND** any deviation SHALL fail the test with a diagnostic listing the first out-of-order block

### Requirement: Phase 2 fan-out shares cache
The Phase 2 parallel domain decompose prompts SHALL share their tools and system+rules blocks (BP1, BP2) byte-for-byte across all parallel domain calls so that the Anthropic prefix cache hits.

#### Scenario: Per-domain prompts differ only in volatile section
- **WHEN** `_phase2_parallel_decompose` builds prompts for N domains
- **THEN** the first two blocks (tools, system+rules) SHALL be identical across all N prompts
- **AND** the per-domain content (domain summary, requirements subset) SHALL be in the digest-stable or volatile blocks only

### Requirement: Cache observability in LLM_CALL events
The system SHALL record `cache_read_tokens` and `cache_create_tokens` for every planner-side LLM call in the `LLM_CALL` event payload, sourced from the Anthropic SDK response.

#### Scenario: LLM_CALL event includes cache token fields
- **WHEN** the planner emits an `LLM_CALL` event after a Claude response
- **THEN** the event payload SHALL include `cache_read_tokens` and `cache_create_tokens` integer fields
- **AND** when the SDK reports zero, the field SHALL be `0` (not absent)
