## Why

`set-memory` and `install.sh` use `python3` (via `#!/usr/bin/env bash` → `python3 -c ...`), but on many Linux systems the first `python3` in PATH may belong to a venv (PlatformIO, pyenv, conda base) that doesn't have `shodh-memory` or `PySide6` installed. This causes `set-memory health` to fail and GUI deps to install into the wrong environment. The `wt-control` wrapper already has a `find_python()` fallback — but `set-memory` and `install.sh` don't.

## What Changes

- Extract a shared `find_python()` / `find_shodh_python()` helper into `wt-common.sh` so all scripts use the same resolution logic
- `set-memory`: resolve Python via a saved config path first, then fallback to probing for a python3 that can `import shodh_memory`
- `install.sh` (`install_shodh_memory`): detect the "right" python3, install shodh-memory into it with `$PYTHON -m pip install`, and persist the path to `~/.config/set-core/shodh-python`
- `install.sh` (`install_gui_dependencies`): use the same `find_python()` logic and install with `$PYTHON -m pip install -r requirements.txt`
- `wt-control`: refactor to use the shared `find_python()` from `wt-common.sh` instead of its own inline copy

## Capabilities

### New Capabilities
- `python-path-resolution`: Shared logic for finding the correct Python interpreter across all set-core scripts, with config persistence at `~/.config/set-core/shodh-python`

### Modified Capabilities
- `memory-cli`: `set-memory` uses resolved Python instead of bare `python3`
- `opensource`: `install.sh` installs shodh-memory and GUI deps into the correct Python environment and persists the path

## Impact

- **Files**: `bin/wt-common.sh`, `bin/set-memory`, `bin/wt-control`, `install.sh`
- **Config**: new file `~/.config/set-core/shodh-python` (single line: absolute path to python3 binary)
- **Behavior**: existing users who re-run `install.sh` will get the fix; `set-memory` will auto-probe if no config exists (backwards-compatible)
