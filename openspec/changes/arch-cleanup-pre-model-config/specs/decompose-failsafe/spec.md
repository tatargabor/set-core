## ADDED Requirements

### Requirement: profile-load failure in test-bundling helpers is logged at WARNING

`lib/set_orch/templates.py::_get_test_bundling_directives` and `lib/set_orch/planner.py::_assert_no_standalone_test_changes` SHALL emit a `logger.warning(...)` message including `exc_info=True` whenever `load_profile(project_path)` raises an exception, then continue with neutral defaults. Silent fallback (bare `except: pass`) SHALL NOT remain in either helper.

#### Scenario: profile-load exception in templates is logged
- **WHEN** `_get_test_bundling_directives` is called with a `project_path` that causes `load_profile` to raise
- **THEN** a WARNING-level log record is emitted with the exception details captured via `exc_info=True`
- **AND** the function returns the documented neutral-default directives

#### Scenario: profile-load exception in post-merge guard is logged
- **WHEN** `_assert_no_standalone_test_changes` is called and `load_profile` raises
- **THEN** a WARNING-level log record is emitted with `exc_info=True`
- **AND** the guard proceeds with the universal-prefix backstop instead of becoming a no-op

### Requirement: post-merge guard enforces a universal test-prefix backstop

`_assert_no_standalone_test_changes` SHALL apply the union of profile-supplied prefixes (when available) and the universal backstop set `{"test-", "e2e-", "playwright-", "vitest-"}`. The singleton-exception name (`profile.singleton_test_infrastructure_change_name()` or default `"test-infrastructure-setup"`) SHALL still be exempt from the prefix check.

#### Scenario: standalone playwright change rejected with empty profile prefixes
- **WHEN** the profile returns an empty `standalone_test_change_prefixes()` list AND the merged plan contains a change named `playwright-smoke`
- **THEN** `_assert_no_standalone_test_changes` raises `RuntimeError` whose message names `playwright-smoke` and the capability `decompose-test-bundling`

#### Scenario: standalone test- change rejected on core profile
- **WHEN** the profile is CoreProfile (no profile-supplied prefixes) AND the merged plan contains a change named `test-validation-suite`
- **THEN** `_assert_no_standalone_test_changes` raises `RuntimeError` whose message names `test-validation-suite`

#### Scenario: singleton exception still passes
- **WHEN** the merged plan contains only a single change named `test-infrastructure-setup` (the default singleton name)
- **THEN** `_assert_no_standalone_test_changes` does not raise

#### Scenario: union of profile prefixes and universal backstop applied
- **WHEN** the profile supplies `["playwright-", "vitest-"]` AND the merged plan contains a change named `e2e-coverage-suite` (matched only by the universal `e2e-` backstop)
- **THEN** `_assert_no_standalone_test_changes` raises `RuntimeError` naming `e2e-coverage-suite`
