## Purpose

Delta spec: Add dev server detection and package manager detection to the orchestration-config capability (absorbed from `server-detect.sh`).

## Requirements

### DELTA: Dev Server Detection
- Add `detect_dev_server(project_dir, overrides)` to `config.py`
- Detection cascade: directive override → package.json scripts.dev → docker-compose → Makefile → manage.py
- Return command string or None

### DELTA: Package Manager Detection
- Add `detect_package_manager(project_dir)` to `config.py`
- Detect from lockfile: `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lockb`/`bun.lock` → bun, `package-lock.json` → npm
- Add `install_dependencies(project_dir, pm)` helper
