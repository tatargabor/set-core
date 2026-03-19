## Context

`set-memory` calls `python3` directly, which resolves via PATH. On systems with multiple Python environments (PlatformIO venv, pyenv, conda), the first `python3` in PATH often lacks `shodh-memory`. The `wt-control` script already solves this with an inline `find_python()` — but `set-memory` and `install.sh` don't.

Current state:
- `wt-control`: has `find_python()` with fallback to miniconda/anaconda paths
- `set-memory`: uses bare `python3` — breaks when PATH python3 ≠ shodh-memory python3
- `install.sh`: uses `pip3` / `pip` — may install into wrong environment

## Goals / Non-Goals

**Goals:**
- All set-core scripts find and use the correct Python interpreter consistently
- `install.sh` installs Python deps into the same Python that scripts will use at runtime
- The resolved Python path is persisted so subsequent runs skip probing
- Backwards-compatible: works without config file (probe fallback)

**Non-Goals:**
- Creating a virtualenv for set-core (too heavy, users may want system Python)
- Supporting Windows Python path resolution (out of scope for now)
- Changing the shodh-memory package itself

## Decisions

### Decision 1: Shared `find_python` in `wt-common.sh`

Add two functions to `bin/wt-common.sh`:

1. `find_python()` — finds a working `python3` binary (checks PATH, then well-known locations). Same logic as current `wt-control` inline version.
2. `find_shodh_python()` — finds a `python3` that can `import shodh_memory`. Checks saved config first, then probes.

**Why in wt-common.sh**: Already sourced by multiple scripts. Avoids duplication. The `wt-control` inline version will be replaced with a call to `source wt-common.sh`.

**Alternative considered**: Separate `wt-python-resolve` script. Rejected — adds another file and subprocess for what's a simple function.

### Decision 2: Config file `~/.config/set-core/shodh-python`

A single-line file containing the absolute path to the Python binary that has shodh-memory installed. Created/updated by `install.sh` after successful shodh-memory installation.

**Resolution order in `find_shodh_python()`:**
1. Read `$CONFIG_DIR/shodh-python` — if it exists and the python there can still import shodh_memory → use it
2. Try `python3` from PATH → if import succeeds → save to config and use it
3. Try well-known paths: `$HOME/miniconda3/bin/python3`, `$HOME/anaconda3/bin/python3`, `/usr/bin/python3`
4. If none work → return 1

**Why validate saved path**: The python binary could be removed, or shodh-memory uninstalled. A stale config shouldn't cause silent failures.

### Decision 3: `install.sh` uses `$PYTHON -m pip` instead of `pip3`

The `install_shodh_memory()` and `install_gui_dependencies()` functions will:
1. Call `find_python()` to get the target Python
2. Install with `$PYTHON -m pip install ...` instead of `pip3 install ...`
3. After successful shodh-memory install, write the Python path to `$CONFIG_DIR/shodh-python`

**Why `-m pip`**: Guarantees pip belongs to the same Python that will run the code. `pip3` is a separate binary that may point to a different Python.

### Decision 4: `set-memory` sources `wt-common.sh` for Python resolution

`set-memory` will source `wt-common.sh` to get `find_shodh_python()`, then use the resolved Python binary for all `python3 -c` calls instead of bare `python3`.

The `run_shodh_python()` function will use the resolved Python path. Resolution happens once at script startup and is cached in a variable for the duration of the script.

### Decision 5: `wt-control` delegates to shared `find_python()`

Replace the inline `find_python()` in `wt-control` with sourcing `wt-common.sh`. The existing behavior is preserved, just deduplicated.

## Risks / Trade-offs

- **[Risk] Sourcing wt-common.sh adds startup overhead to set-memory** → Minimal, wt-common.sh is a few KB of function definitions. The probe only runs once.
- **[Risk] Config file could point to a deleted/broken Python** → Mitigated by validation: we check `import shodh_memory` before using saved path.
- **[Risk] wt-common.sh may not be in PATH when set-memory runs** → set-memory already resolves its own script directory via readlink; source relative to that.
- **[Trade-off] Probe adds ~200ms on first run** → Acceptable; subsequent runs read from config file.
