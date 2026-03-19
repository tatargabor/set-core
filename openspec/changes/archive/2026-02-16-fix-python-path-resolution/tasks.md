## 1. Shared Python resolution in wt-common.sh

- [x] 1.1 Add `find_python()` function to `bin/wt-common.sh` — checks PATH, then well-known locations (miniconda3, anaconda3, /usr/bin/python3), returns absolute path or exit 1
- [x] 1.2 Add `find_shodh_python()` function to `bin/wt-common.sh` — reads `$CONFIG_DIR/shodh-python` first (validates import), then probes PATH and well-known paths, saves result to config on success
- [x] 1.3 Add `save_shodh_python()` helper that writes the resolved path to `$CONFIG_DIR/shodh-python`

## 2. Update set-memory to use resolved Python

- [x] 2.1 Source `wt-common.sh` at the top of `bin/set-memory` (resolve script dir via readlink, source relative `wt-common.sh`)
- [x] 2.2 Replace all bare `python3` calls in `run_shodh_python()` with the resolved `$SHODH_PYTHON` variable
- [x] 2.3 Update `cmd_health()` to use `find_shodh_python()` — return 1 if no suitable python found
- [x] 2.4 Initialize `SHODH_PYTHON` once at script startup using `find_shodh_python()`, cache in global variable

## 3. Update install.sh to install into correct Python

- [x] 3.1 Source `wt-common.sh` in `install.sh` (after SCRIPT_DIR is set)
- [x] 3.2 Rewrite `install_shodh_memory()` to use `find_python()` + `$PYTHON -m pip install shodh-memory`, then verify import and save path to config
- [x] 3.3 Rewrite `install_gui_dependencies()` to use `find_python()` + `$PYTHON -m pip install -r requirements.txt`

## 4. Refactor wt-control to use shared function

- [x] 4.1 Source `wt-common.sh` in `bin/wt-control` and replace the inline `find_python()` with the shared version
- [x] 4.2 Verify wt-control still resolves PySide6 correctly after refactor

## 5. Verification

- [x] 5.1 Test: `set-memory health` succeeds when shodh-memory is in miniconda but PlatformIO python3 is first in PATH
- [x] 5.2 Test: config file `~/.config/set-core/shodh-python` is created after first successful probe
- [x] 5.3 Test: stale config (pointing to removed python) falls through to re-probe
