## MODIFIED Requirements

### Requirement: Scope-filtered checklist at dispatch
The `review_learnings_checklist()` method SHALL accept an optional `content_categories: set[str]` parameter. When provided as a non-empty set, only entries whose categories overlap with the provided set (plus `"general"` always included) SHALL be returned. When provided as an empty set (a positive signal that no domain surface applies), only `"general"`-tagged entries SHALL be returned. When `None` (uncategorized fallback only), the legacy "include all" behavior SHALL apply.

#### Scenario: Auth change gets auth+general learnings
- **WHEN** dispatching a change whose category-resolver returns `{"auth"}`
- **AND** the template JSONL has 50 entries: 10 auth, 8 api, 12 database, 15 frontend, 5 general
- **THEN** the checklist SHALL contain the 10 auth + 5 general entries (15 total)
- **AND** api, database, frontend entries SHALL be excluded

#### Scenario: Empty set is a positive "no domain surface" signal
- **WHEN** `content_categories` is an empty set `set()` (not `None`)
- **THEN** only `"general"`-tagged entries SHALL be returned
- **AND** auth, api, database, frontend, payment entries SHALL be excluded
- **AND** this branch SHALL be the resolver's signal that the change has no domain surface to inject for

#### Scenario: None falls back to legacy include-all
- **WHEN** `content_categories` is `None` (caller did not run a resolver, e.g. legacy code path)
- **THEN** all entries SHALL be returned (current pre-resolver behavior preserved for backwards compatibility)

#### Scenario: Foundation change touches multiple domains
- **WHEN** a change's category-resolver returns `{"auth", "api", "database", "frontend"}`
- **THEN** entries tagged with any of those four (plus general) SHALL be included
- **AND** entries tagged only with payment SHALL be excluded

### Requirement: Dispatcher passes content categories
The dispatcher SHALL invoke the change-category-resolver at dispatch time and pass its result to both `review_learnings_checklist()` and `_build_review_learnings()`. The legacy `classify_diff_content(scope)` call at dispatch SHALL be removed — that classifier remains correct only on actual diff text and SHALL continue to be used by the verifier on post-implementation diffs.

#### Scenario: Dispatcher uses resolver output, not diff classifier
- **WHEN** dispatching a change
- **THEN** the dispatcher SHALL call `category_resolver.resolve_change_categories(change, profile, project_path, manifest_paths)`
- **AND** SHALL pass the returned set to learnings filtering functions
- **AND** SHALL NOT call `classify_diff_content(scope)` at dispatch (which always returned `set()` due to scope-not-being-a-diff)

#### Scenario: Verifier still uses classify_diff_content on actual diff
- **WHEN** the verifier runs post-implementation gates and has access to the change's actual git diff
- **THEN** it MAY call `classify_diff_content(diff_text)` for diff-time category detection (its original correct use)
- **AND** that call path is unaffected by this change
