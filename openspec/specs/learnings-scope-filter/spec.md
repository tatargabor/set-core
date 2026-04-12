## ADDED Requirements

## IN SCOPE
- Category tagging of learnings entries during persistence
- Scope-aware filtering at dispatch time using diff content categories
- Filtering for both agent input.md injection and review gate injection

## OUT OF SCOPE
- LLM-based relevance scoring at dispatch time (too costly per dispatch)
- Per-change custom category definitions
- Filtering of cross-change within-run learnings (those are already change-scoped)

### Requirement: Category tagging at persist time
When persisting a learning entry, the system SHALL assign one or more content categories from the set `{auth, api, database, frontend, general}` based on keyword matching against the pattern text and fix_hint.

#### Scenario: Auth-related pattern tagged
- **WHEN** a pattern contains keywords like "auth", "middleware", "login", "session", "cookie", "password"
- **THEN** the entry SHALL have `categories: ["auth"]` in its JSONL record

#### Scenario: Multi-category pattern tagged
- **WHEN** a pattern like "API endpoint missing authentication" matches both "api" and "auth" keywords
- **THEN** the entry SHALL have `categories: ["auth", "api"]`

#### Scenario: Uncategorizable pattern defaults to general
- **WHEN** a pattern like "Missing trailing newline" matches no specific category keywords
- **THEN** the entry SHALL have `categories: ["general"]`

#### Scenario: Existing entries without categories get backfilled
- **WHEN** `_merge_learnings()` processes entries that lack a `categories` field
- **THEN** it SHALL assign categories based on keyword matching before writing

### Requirement: Scope-filtered checklist at dispatch
The `review_learnings_checklist()` method SHALL accept an optional `content_categories: set[str]` parameter. When provided, only entries whose categories overlap with the provided set (plus "general" always included) SHALL be returned.

#### Scenario: Auth change gets auth+general learnings
- **WHEN** dispatching a change whose diff touches auth files
- **AND** `classify_diff_content()` returns `{"auth"}`
- **AND** the template JSONL has 50 entries: 10 auth, 8 api, 12 database, 15 frontend, 5 general
- **THEN** the checklist SHALL contain the 10 auth + 5 general entries (15 total)
- **AND** api, database, frontend entries SHALL be excluded

#### Scenario: No content categories provided (fallback)
- **WHEN** `content_categories` is None or empty
- **THEN** all entries SHALL be returned (current behavior preserved)

#### Scenario: Foundation change touches all categories
- **WHEN** a change's diff touches auth, api, database, and frontend files
- **AND** `classify_diff_content()` returns `{"auth", "api", "database", "frontend"}`
- **THEN** all entries SHALL be included (all categories match)

### Requirement: Dispatcher passes content categories
The dispatcher SHALL call `classify_diff_content()` on the change's diff at dispatch time and pass the resulting categories to both `review_learnings_checklist()` and `_build_review_learnings()`.

#### Scenario: Dispatcher uses diff categories
- **WHEN** dispatching a change
- **THEN** the dispatcher SHALL read the change's diff or scope description
- **AND** call `classify_diff_content()` to get content categories
- **AND** pass categories to learnings filtering functions
