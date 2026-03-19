## MODIFIED Requirements

### Requirement: Index health check
`set-memory health --index` SHALL check the integrity of the shodh-memory index. When shodh-memory >= 0.1.81, it SHALL also call `verify_index()` to check for orphaned memories alongside the existing `index_health()` check.

#### Scenario: Healthy index on 0.1.81+
- **WHEN** user runs `set-memory health --index`
- **AND** shodh-memory >= 0.1.81 is installed
- **THEN** stdout prints combined JSON from `index_health()` and `verify_index()` with both health metrics and orphan status

#### Scenario: Healthy index on older version
- **WHEN** user runs `set-memory health --index`
- **AND** shodh-memory < 0.1.81 is installed (no `verify_index`)
- **THEN** stdout prints only `index_health()` result (graceful fallback)

#### Scenario: Basic health without --index
- **WHEN** user runs `set-memory health` (without `--index`)
- **THEN** behavior is unchanged (prints "ok" or exits non-zero)

## ADDED Requirements

### Requirement: Version pin at 0.1.81
The `pyproject.toml` SHALL pin shodh-memory to `>=0.1.81`. The previous `>=0.1.75,!=0.1.80` pin SHALL be replaced.

#### Scenario: pyproject.toml version constraint
- **WHEN** inspecting `pyproject.toml`
- **THEN** the shodh-memory dependency reads `shodh-memory>=0.1.81`

#### Scenario: Install succeeds with 0.1.81
- **WHEN** `pip install -e .` is run
- **THEN** shodh-memory 0.1.81 or later is installed
