## MODIFIED Requirements

### Requirement: Health check command
The `set-memory health` command SHALL check if shodh-memory is available by using the resolved Python from `find_shodh_python()` (sourced from `wt-common.sh`) to attempt `from shodh_memory import Memory`. It SHALL return exit code 0 and print "ok" on success, or exit code 1 on failure.

#### Scenario: Shodh-memory is importable via resolved python
- **WHEN** `find_shodh_python()` returns a valid python and shodh-memory is importable
- **THEN** `set-memory health` returns exit code 0 and prints "ok"

#### Scenario: Shodh-memory not installed in any python
- **WHEN** `find_shodh_python()` returns exit code 1 (no python with shodh-memory found)
- **THEN** `set-memory health` returns exit code 1 with no output

### Requirement: Installation via install.sh
The `set-memory` script SHALL be included in the `scripts` array of `install_scripts()` in `install.sh`, so it is symlinked to `~/.local/bin/` during installation.

#### Scenario: Fresh install
- **WHEN** `install.sh` is run
- **THEN** `set-memory` is symlinked to `~/.local/bin/set-memory`
