# change-category-resolver Specification

## Purpose
TBD - created by archiving change dynamic-category-injection. Update Purpose after archive.
## Requirements
### Requirement: Resolver runs six deterministic detection layers per change
The change-category-resolver SHALL compute the union of categories from six per-change deterministic layers before considering LLM input. The five primary layers run unconditionally; the project-state fallback runs only when the primary union has at most two categories.

#### Scenario: All five primary layers contribute
- **WHEN** a change has change_type=`feature`, requirements=`[REQ-AUTH-001, REQ-API-USERS-001]`, manifest paths include `src/app/api/users/route.ts`, scope text contains `oauth`, depends_on includes a parent change classified as `database`
- **THEN** the resolver SHALL return a union containing at least `{general, frontend, auth, api, database}`
- **AND** the project-state fallback layer SHALL NOT run (primary union has > 2 categories)

#### Scenario: Project-state fallback engages on thin signal
- **WHEN** a change has change_type=`feature`, no requirements, no path matches, no scope intent matches, no depends_on
- **AND** the primary union yields only `{general, frontend}` (frontend from change_type defaults)
- **THEN** the resolver SHALL invoke `profile.detect_project_categories(project_path)` and union the result
- **AND** the audit log SHALL record that the fallback layer ran

#### Scenario: Layer ordering is union-based, not priority-based
- **WHEN** layer 1 returns `{frontend}` and layer 4 returns `{auth}`
- **THEN** the resolver SHALL return `{frontend, auth}` (both)
- **AND** no layer SHALL override or remove categories produced by another

### Requirement: Resolver invokes profile-supplied LLM classifier as additive layer
The resolver SHALL invoke the profile's configured LLM (default: `claude-sonnet-4-6`) after the deterministic layers complete, passing the scope text, change_type, requirements, manifest paths, depends_on, project summary (from profile), and a project-insights summary (when available). The LLM result SHALL be unioned with the deterministic union — the LLM can only add categories, never remove.

#### Scenario: LLM adds an implicit category the deterministic layers missed
- **WHEN** scope is "Add checkout flow with cart summary"
- **AND** deterministic layers return `{general, frontend}` (no auth/payment keywords matched)
- **AND** Sonnet returns `{frontend, payment, auth}` (implicit-dependency reasoning)
- **THEN** the resolver SHALL return `{general, frontend, payment, auth}`
- **AND** the audit log SHALL record `delta.added_by_llm: ["payment", "auth"]`

#### Scenario: LLM cannot remove a deterministic category
- **WHEN** deterministic returns `{general, frontend, auth}` (matched on `login` keyword)
- **AND** Sonnet returns `{general, frontend}` only (judged auth context too weak)
- **THEN** the resolver SHALL return `{general, frontend, auth}` — the union preserves auth

#### Scenario: LLM returns a category not in the profile's taxonomy
- **WHEN** Sonnet returns `{frontend, rate-limiting}`
- **AND** `profile.category_taxonomy()` does not include `rate-limiting`
- **THEN** the resolver SHALL filter `rate-limiting` out of the final union
- **AND** SHALL append it to `uncovered_categories` in the audit record for harvest

### Requirement: Resolver caches LLM responses by input hash
The resolver SHALL compute `cache_key = sha256(scope || sorted(req_ids) || sorted(deps))` and check `category-classifications.jsonl` for an entry with the same `cache_key` before invoking the LLM. On cache hit, the cached LLM result SHALL be reused; no API call is made.

#### Scenario: Replan reuses cached classification
- **WHEN** a change is dispatched, classified, then replanned with identical scope/requirements/deps
- **THEN** the second dispatch SHALL find a cache entry with matching `cache_key`
- **AND** SHALL skip the Sonnet call
- **AND** SHALL log `cache_hit: true` in the audit record

#### Scenario: Scope edit invalidates cache automatically
- **WHEN** a change's scope text is edited (planner refines a deferred change) and the dispatcher re-runs the resolver
- **THEN** the cache key SHALL differ (scope changed)
- **AND** Sonnet SHALL be invoked fresh

### Requirement: Resolver gracefully degrades on LLM failure
The resolver SHALL apply an 8-second timeout to the Sonnet call. On timeout, network error, or non-2xx HTTP response (after one single-shot retry), the resolver SHALL return the deterministic union unchanged and log the failure to the audit record.

#### Scenario: API timeout
- **WHEN** Sonnet does not respond within 8 seconds (or the retry also times out)
- **THEN** the resolver SHALL return the deterministic union
- **AND** the audit record SHALL include `llm.error: "timeout"` and `llm.duration_ms` reflecting actual elapsed time
- **AND** the dispatch SHALL proceed without blocking

#### Scenario: Malformed JSON response
- **WHEN** Sonnet returns text that fails JSON parsing
- **THEN** the resolver SHALL log the parse error and return the deterministic union
- **AND** the audit record SHALL include `llm.error: "json_parse"` and the raw response (truncated to 500 chars)

#### Scenario: Disabled via config
- **WHEN** `profile.llm_classifier_model` returns `None` or empty string
- **THEN** the resolver SHALL skip the LLM call entirely
- **AND** SHALL return the deterministic union without delay

### Requirement: Resolver writes one audit record per dispatch
For every resolver invocation (cache hit, cache miss, or LLM failure), one JSON line SHALL be appended to `.set/state/category-classifications.jsonl`. The record SHALL contain the change name, scope hash, change_type, deterministic categories with per-layer breakdown, LLM categories with model/duration/cost (or error), final union, and a delta diff between deterministic and LLM.

#### Scenario: Cache miss with successful LLM call
- **WHEN** the resolver runs and the LLM returns categories successfully
- **THEN** a JSONL record SHALL be appended with all fields populated
- **AND** the record SHALL include `cache_hit: false`, `llm.model`, `llm.duration_ms`, `llm.cost_usd`

#### Scenario: Cache hit
- **WHEN** the resolver hits the cache
- **THEN** a record SHALL still be appended (for telemetry on cache effectiveness)
- **AND** the record SHALL include `cache_hit: true` and reference the cached `cache_key`
- **AND** SHALL NOT include LLM duration or cost fields

#### Scenario: Concurrent dispatchers append safely
- **WHEN** two parallel dispatch processes write records simultaneously
- **THEN** both records SHALL appear in the JSONL without corruption (line-atomic append)
- **AND** record ordering SHALL match write timestamp order

### Requirement: Profile contributes seven category-resolver hooks
A `ProjectType` implementation SHALL provide seven hook methods, each with a documented no-op default in the ABC. Profile overrides supply concrete patterns. The resolver MUST invoke profile methods polymorphically and never branch on `isinstance(profile, WebProjectType)` or similar.

#### Scenario: NullProfile returns empty categories
- **WHEN** the resolver runs with `NullProfile` as the active profile
- **THEN** all seven hooks SHALL return their no-op defaults
- **AND** the resolver SHALL produce `{general}` only (the universal baseline)
- **AND** the LLM call SHALL still run if `llm_classifier_model` is set

#### Scenario: Hook signatures are stable
- **WHEN** a profile overrides a subset of the seven hooks (e.g. only `categories_from_paths`)
- **THEN** the resolver SHALL still operate correctly, using ABC defaults for unimplemented hooks
- **AND** SHALL NOT raise NotImplementedError or AttributeError

