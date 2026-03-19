# JSON Translation Merge

Programmatic deep-merge for JSON files during set-merge, resolving additive conflicts without LLM involvement.

## Requirements

### Requirement: Programmatic JSON file conflict resolution
set-merge SHALL automatically resolve merge conflicts in `.json` files using jq deep-merge before falling back to LLM resolution.

#### Scenario: JSON files among conflicted files
- **WHEN** `git merge` fails with conflicts
- **AND** conflicted files include one or more `.json` files
- **THEN** `auto_resolve_json_files()` SHALL attempt programmatic resolution for each `.json` file
- **AND** this SHALL run AFTER `auto_resolve_package_json()` and BEFORE `llm_resolve_conflicts()`

#### Scenario: Successful deep-merge of JSON file
- **WHEN** a conflicted `.json` file has valid JSON on both sides (ours and theirs)
- **THEN** the resolver SHALL extract ours (`:2:`) and theirs (`:3:`) via `git show`
- **AND** validate both are valid JSON via `jq empty`
- **AND** deep-merge using recursive object merge: both sides' keys are preserved
- **AND** on scalar conflict (same key, different value), theirs (feature branch) wins
- **AND** write the merged result to the working tree file
- **AND** `git add` the resolved file

#### Scenario: Invalid JSON on either side
- **WHEN** either the ours or theirs version of a `.json` file fails `jq empty` validation
- **THEN** the resolver SHALL skip that file (return non-zero for that file)
- **AND** leave the conflict markers in place for subsequent resolvers (LLM fallback)

#### Scenario: package.json excluded
- **WHEN** a conflicted file is `package.json`
- **THEN** `auto_resolve_json_files()` SHALL skip it
- **AND** let the existing `auto_resolve_package_json()` handle it (already runs earlier in the flow)

#### Scenario: All JSON conflicts resolved
- **WHEN** `auto_resolve_json_files()` resolves all conflicted `.json` files
- **AND** no other conflicted files remain
- **THEN** the merge flow SHALL `git commit --no-edit` to complete the merge

#### Scenario: Mixed conflicts (JSON + non-JSON)
- **WHEN** some but not all conflicted files are `.json`
- **THEN** the resolver SHALL resolve the JSON files it can
- **AND** leave remaining non-JSON conflicts for subsequent resolvers
