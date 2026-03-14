## Purpose

Migrate `lib/orchestration/builder.sh` (151 LOC) to `lib/wt_orch/builder.py` and absorb `server-detect.sh` (113 LOC) and `orch-memory.sh` (145 LOC). Builder checks base project build health; server-detect identifies dev servers and package managers; orch-memory provides orchestrator-scoped memory helpers.

## Requirements

### BUILD-01: Base Build Health Check
- `check_base_build(project_path)` runs the project's build command
- Auto-detect package manager: npm, pnpm, yarn, bun (from lockfile)
- Auto-detect build command from `package.json` scripts
- Cache result per session: `pass` or `fail` (don't re-run if already checked)
- Return `BuildResult(status, output, package_manager)`

### BUILD-02: LLM-Assisted Build Fix
- `fix_base_build(project_path, error_output)` attempts automated fix
- Call Claude CLI with build error context
- Apply fix, re-run build to verify
- Track fix attempts: max 1 attempt per session (`BASE_BUILD_FIX_ATTEMPTED` flag)
- Emit event on fix attempt (success or failure)

### BUILD-03: Dev Server Detection (from server-detect.sh)
- `detect_dev_server(project_dir, overrides)` detection cascade:
  1. `milestones.dev_server` directive (explicit override)
  2. `smoke_dev_server_command` directive
  3. `package.json` scripts.dev → `<pm> run dev`
  4. `docker-compose.yml` / `compose.yml` → `docker compose up`
  5. `Makefile` dev/serve target → `make dev` / `make serve`
  6. `manage.py` → `python manage.py runserver`
- Return command string or empty if none detected

### BUILD-04: Package Manager Detection (from server-detect.sh)
- `detect_package_manager(project_dir)` from lockfile presence
- `install_dependencies(project_dir, pm)` runs install command
- Support: npm, pnpm, yarn, bun, pip, poetry

### BUILD-05: Orchestrator Memory Helpers (from orch-memory.sh)
- `orch_remember(content, type, tags)` — save to memory with `source:orchestrator` tag
- `orch_recall(query, limit, tags)` — recall from memory
- `orch_gate_stats()` — memory operation statistics for metrics
- All call `wt-memory` CLI under the hood, with timing and operation counting

### BUILD-06: CLI Subcommands
- `wt-orch-core build check [--project <path>]` — run build check
- `wt-orch-core build fix [--project <path>]` — attempt build fix
- `wt-orch-core build detect-server [--project <path>]` — detect dev server
- `wt-orch-core build detect-pm [--project <path>]` — detect package manager
- Registered in `cli.py` under `build` group

### BUILD-07: Unit Tests
- Test package manager detection with mock lockfiles
- Test dev server detection cascade with mock project structures
- Test build result caching behavior
- Test memory helper timing/counting
