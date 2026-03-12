## ADDED Requirements

### Requirement: All entry points use strict mode
Every executable script in `bin/wt-*` SHALL have `set -euo pipefail` near the top (after shebang and comments, before any logic).

#### Scenario: Entry point with strict mode
- **WHEN** any `bin/wt-*` file is examined
- **THEN** it contains `set -euo pipefail` before any function calls or logic

#### Scenario: Sourced libraries do not set strict mode independently
- **WHEN** a `lib/**/*.sh` file is examined
- **THEN** it does NOT contain its own `set -euo pipefail` (it inherits from the sourcing entry point)

### Requirement: Error suppression patterns are classified and documented
Every instance of `|| true` and `2>/dev/null` in `lib/orchestration/` SHALL be classified as one of: intentional (with comment), error-hiding (fixed), or unnecessary (removed).

#### Scenario: Intentional suppression has comment
- **WHEN** `|| true` is kept in the code because the error is expected (e.g., git branch check)
- **THEN** it is preceded or followed by a comment explaining why (e.g., `# expected: branch may not exist`)

#### Scenario: Error-hiding suppression is removed
- **WHEN** `|| true` or `2>/dev/null` was hiding a real error (e.g., jq parse failure)
- **THEN** the suppression is removed and proper error handling is added

### Requirement: grep under set -e uses safe patterns
Under `set -euo pipefail`, `grep` commands that may legitimately match zero lines SHALL use `|| true` with a comment, or be wrapped in a conditional.

#### Scenario: grep with no matches does not crash
- **WHEN** `grep -v "pattern"` matches zero lines under `set -euo pipefail`
- **THEN** the script does not exit — the grep is protected with `|| true` and a comment `# expected: may match nothing`

### Requirement: Variable declarations use local in functions
All variable assignments inside functions in `lib/orchestration/` SHALL use `local` to prevent scope leakage.

#### Scenario: Function variable is local
- **WHEN** a function in `lib/orchestration/*.sh` assigns a variable
- **THEN** the variable is declared with `local` (either `local var="value"` or `local var; var=$(...)`)

### Requirement: Unset variable defaults under set -u
Variables that may be unset SHALL use `${var:-default}` syntax to prevent `set -u` failures.

#### Scenario: Optional variable with default
- **WHEN** a variable might not be set (e.g., optional function parameter)
- **THEN** it is accessed as `${var:-""}` or `${var:-0}` rather than bare `$var`
