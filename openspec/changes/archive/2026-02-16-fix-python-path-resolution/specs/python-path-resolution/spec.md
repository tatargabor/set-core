## ADDED Requirements

### Requirement: find_python function in wt-common.sh
`wt-common.sh` SHALL export a `find_python()` function that returns the absolute path to a working `python3` binary. It SHALL check PATH first, then well-known locations (`$HOME/miniconda3/bin/python3`, `$HOME/anaconda3/bin/python3`, `/usr/bin/python3`). It SHALL return exit code 1 if no python3 is found.

#### Scenario: python3 in PATH
- **WHEN** `python3` is available in PATH
- **THEN** `find_python` returns its absolute path and exit code 0

#### Scenario: python3 not in PATH but in miniconda
- **WHEN** `python3` is not in PATH but `$HOME/miniconda3/bin/python3` exists
- **THEN** `find_python` returns `$HOME/miniconda3/bin/python3` and exit code 0

#### Scenario: no python3 found
- **WHEN** no python3 is found in PATH or well-known locations
- **THEN** `find_python` returns exit code 1

### Requirement: find_shodh_python function in wt-common.sh
`wt-common.sh` SHALL export a `find_shodh_python()` function that returns the absolute path to a `python3` binary capable of `import shodh_memory`. It SHALL follow this resolution order:
1. Read `$CONFIG_DIR/shodh-python` — if file exists and the referenced python can import shodh_memory, return it
2. Try `python3` from PATH — if import succeeds, save to config and return it
3. Try well-known paths (`$HOME/miniconda3/bin/python3`, `$HOME/anaconda3/bin/python3`, `/usr/bin/python3`) — if import succeeds, save to config and return it
4. Return exit code 1 if none work

#### Scenario: Saved config points to valid python
- **WHEN** `~/.config/set-core/shodh-python` contains `/home/user/miniconda3/bin/python3`
- **AND** that python can import shodh_memory
- **THEN** `find_shodh_python` returns `/home/user/miniconda3/bin/python3` and exit code 0

#### Scenario: Saved config is stale
- **WHEN** `~/.config/set-core/shodh-python` contains a path to a python that can no longer import shodh_memory
- **THEN** `find_shodh_python` SHALL fall through to probing other python3 locations

#### Scenario: No config, python3 in PATH has shodh-memory
- **WHEN** no config file exists and `python3` in PATH can import shodh_memory
- **THEN** `find_shodh_python` returns the PATH python3, saves it to config, and exits 0

#### Scenario: No config, shodh-memory in miniconda only
- **WHEN** no config file exists and only `$HOME/miniconda3/bin/python3` can import shodh_memory
- **THEN** `find_shodh_python` returns the miniconda python3, saves it to config, and exits 0

### Requirement: Config persistence at shodh-python
The resolved shodh-memory Python path SHALL be persisted at `$CONFIG_DIR/shodh-python` (typically `~/.config/set-core/shodh-python`). The file SHALL contain a single line: the absolute path to the python3 binary. The file SHALL be created or updated whenever a successful probe finds a new Python.

#### Scenario: Config file created after probe
- **WHEN** `find_shodh_python` probes and finds a working python
- **THEN** the absolute path is written to `~/.config/set-core/shodh-python`

#### Scenario: Config file updated after re-probe
- **WHEN** the saved config is stale and a new python is found via probing
- **THEN** the config file is overwritten with the new path
