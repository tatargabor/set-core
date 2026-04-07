# Tasks: design-brief-matcher

## 1. Stem matching in bridge.sh

- [x] 1.1 Add stem bidir matching as Check 3 in `design_brief_for_dispatch()` after existing Check 1 (exact) and Check 2 (alias). Split page name into words (3+ chars), stem to first 4 chars, grep each stem in scope. Match only if ALL stems found. [REQ: stem-bidirectional-matching]
- [x] 1.2 Test stem matching with minishop page names against realistic decompose scopes [REQ: stem-bidirectional-matching]

## 2. Alias externalization

- [x] 2.1 Create `tests/e2e/scaffolds/craftbrew/docs/design-brief-aliases.txt` with current `_DESIGN_BRIEF_ALIASES` entries [REQ: alias-externalization]
- [x] 2.2 Create `tests/e2e/scaffolds/minishop/docs/design-brief-aliases.txt` with minishop-specific aliases [REQ: alias-externalization]
- [x] 2.3 Empty the `_DESIGN_BRIEF_ALIASES` array in bridge.sh (keep the variable declaration) [REQ: alias-externalization]
- [x] 2.4 Add auto-discovery: when `DESIGN_BRIEF_ALIASES_FILE` is unset, check for `docs/design-brief-aliases.txt` before falling back to empty [REQ: alias-externalization]

## 3. Runner deployment

- [x] 3.1 ~~Add alias file copy step~~ Already deployed via existing `cp -r docs/*` in runners [REQ: alias-externalization]
- [x] 3.2 ~~Add alias file copy step~~ Same — craftbrew runner copies docs/ recursively [REQ: alias-externalization]

## 4. Verification

- [x] 4.1 Test full matching chain: exact → alias → stem for minishop pages [REQ: matching-layer-priority]
- [x] 4.2 Test that craftbrew aliases load from file (not hardcoded) [REQ: alias-externalization]
- [x] 4.3 Test that no-alias projects (micro-web) still work with exact + stem only [REQ: matching-layer-priority]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN page "Admin Products" and scope "admin product management CRUD table" THEN match succeeds via stem [REQ: stem-bidirectional-matching, scenario: multi-word-page-name-with-all-words-in-scope]
- [x] AC-2: WHEN page "Product Grid" and scope "admin product management" THEN match fails (grid not in scope) [REQ: stem-bidirectional-matching, scenario: multi-word-page-name-with-partial-words-in-scope]
- [x] AC-3: WHEN page "Cart" and scope "shopping cart with checkout" THEN match succeeds [REQ: stem-bidirectional-matching, scenario: single-word-page-name]
- [x] AC-4: WHEN page name has words <3 chars THEN those words are skipped [REQ: stem-bidirectional-matching, scenario: short-words-are-excluded]
- [x] AC-5: WHEN matching THEN comparison is case-insensitive [REQ: stem-bidirectional-matching, scenario: stem-matching-is-case-insensitive]
- [x] AC-6: WHEN exact match succeeds THEN stem layer is not needed [REQ: matching-layer-priority, scenario: exact-match-takes-priority]
- [x] AC-7: WHEN alias matches THEN alias takes priority over stem [REQ: matching-layer-priority, scenario: alias-match-takes-priority-over-stem]
- [x] AC-8: WHEN no alias file and empty defaults THEN only exact + stem layers active [REQ: alias-externalization, scenario: no-alias-file-configured]
- [x] AC-9: WHEN scaffold alias file deployed THEN aliases load from file [REQ: alias-externalization, scenario: scaffold-alias-file-deployed]
