# Contributing to set-core

Thank you for your interest in contributing. This document covers setup, testing, architecture, and how to create plugins.

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.10+ | Core engine, API server, MCP server |
| Git | 2.30+ | Worktree management, merge pipeline |
| Node.js | 18+ | Claude Code CLI, web dashboard |
| pnpm | 9+ | Web dashboard package manager |
| jq | Any | JSON processing in shell scripts |
| Claude Code | Latest | Agent runtime (for E2E testing) |

## Development Setup

### 1. Clone and install

```bash
git clone https://github.com/tatargabor/set-core.git
cd set-core
./install.sh
```

The installer:
- Symlinks `set-*` CLI tools to `~/.local/bin/`
- Installs the Python package in editable mode
- Sets up shell completions (bash/zsh)

### 2. Install the web module (for web project type development)

```bash
pip install -e modules/web
```

### 3. Install the web dashboard dependencies

```bash
cd web && pnpm install
```

### 4. Start the API server and dashboard

```bash
# API server (from project root)
set-core server

# Web dashboard (from web/)
cd web && pnpm dev
```

Dashboard runs at `http://localhost:7400`, API at `http://localhost:7300`.

## Project Structure

```
set-core/
├── lib/set_orch/              # Layer 1: Core engine (abstract)
│   ├── engine.py              #   Orchestration state machine
│   ├── dispatcher.py          #   Agent dispatch to worktrees
│   ├── merger.py              #   Integration gate pipeline
│   ├── gate_runner.py         #   Quality gate execution
│   ├── gate_profiles.py       #   Per-change gate configuration
│   ├── profile_types.py       #   ProjectType ABC + dataclasses
│   ├── profile_loader.py      #   NullProfile, CoreProfile, resolution
│   ├── digest.py              #   Spec → requirements extraction
│   ├── api/                   #   FastAPI endpoints
│   └── issues/                #   Issue pipeline (detect → investigate → fix)
├── modules/                   # Layer 2: Project-type plugins
│   ├── web/                   #   WebProjectType — Next.js, Prisma, Playwright
│   │   ├── set_project_web/   #     Python package
│   │   └── pyproject.toml     #     Standalone installable
│   └── example/               #   DungeonProjectType — reference implementation
├── bin/                       # CLI tools (set-new, set-merge, set-status, etc.)
├── web/                       # Web dashboard (React + TypeScript + Tailwind)
├── mcp-server/                # MCP server (FastMCP — memory, worktrees, team)
├── .claude/                   # Claude Code integration
│   ├── rules/                 #   Development rules (NOT deployed to consumers)
│   ├── skills/                #   Slash command implementations
│   └── commands/              #   Command definitions
├── templates/core/rules/      # Rules deployed to consumer projects
├── openspec/                  # Capability specifications
│   ├── specs/                 #   Feature specs
│   └── changes/               #   Active changes
├── tests/                     # Test suite
│   ├── unit/                  #   Unit tests
│   ├── integration/           #   Integration tests
│   ├── orchestrator/          #   Orchestrator-specific tests
│   ├── merge/                 #   Merge pipeline tests
│   └── e2e/                   #   End-to-end orchestration runs
└── docs/                      # Documentation
```

## Running Tests

### Unit and integration tests

```bash
# All tests (excludes e2e/)
cd /path/to/set-core
python -m pytest tests/ --ignore=tests/e2e

# Specific test file
python -m pytest tests/test_gate_profiles.py

# Specific test directory
python -m pytest tests/unit/
python -m pytest tests/merge/
```

### Web dashboard E2E tests

```bash
cd web/

# Requires: running API server + a project with completed orchestration
E2E_PROJECT=minishop-run-20260315-0930 pnpm test:e2e

# View HTML report with screenshots
pnpm test:e2e:report

# Single test file
E2E_PROJECT=minishop-run-20260315-0930 npx playwright test changes-data
```

### Full orchestration E2E

```bash
# Scaffold + init + register + start sentinel
./tests/e2e/run.sh minishop

# Register only (start from manager UI)
./tests/e2e/run.sh minishop --no-start
```

## Architecture Rules

1. **Layer 1 (`lib/set_orch/`) is abstract** — never put project-specific logic (web patterns, framework detection) here. It belongs in `modules/`.

2. **Profile system is the extension point** — new project-aware behavior goes through `ProjectType` ABC in `profile_types.py`, then gets implemented in the appropriate module.

3. **CoreProfile provides universal rules only** — file-size limits, no-secrets check, todo-tracking. Framework-specific rules go in modules.

4. **Modules inherit from CoreProfile** — `WebProjectType(CoreProfile)`, not `ProjectType` directly.

5. **All merges go through integration gates** — never `git merge` manually. The engine's `execute_merge_queue` runs dep install, build, test, and E2E before merging.

6. **OpenSpec lives only in set-core root** — modules do not have their own `openspec/` directory.

## Creating a Plugin

Project-type plugins add domain-specific rules, gates, templates, and conventions.

### Built-in module (in this repo)

1. Create `modules/your-type/` with a `pyproject.toml`
2. Create a class inheriting from `CoreProfile`:

```python
from set_orch.profile_loader import CoreProfile

class YourProjectType(CoreProfile):
    """Domain-specific project type."""

    def detect_test_command(self, project_dir: str) -> str | None:
        # Return the test command for this project type
        return "pytest"

    def detect_e2e_command(self, project_dir: str) -> str | None:
        return None

    def get_forbidden_patterns(self) -> list:
        # Domain-specific forbidden patterns
        return super().get_forbidden_patterns() + [
            {"pattern": "your_pattern", "severity": "CRITICAL", "message": "..."}
        ]
```

3. Register via entry point in `modules/your-type/pyproject.toml`:

```toml
[project.entry-points."set_core.project_types"]
your-type = "your_package:YourProjectType"
```

### External plugin (separate repo)

Same pattern, but in its own repository. Install with `pip install -e /path/to/plugin`. Entry points take priority over built-in modules.

See [`modules/example/`](modules/example/) for a complete reference implementation (DungeonProjectType).

## Code Style

- **Python:** PEP 8, type hints where practical. No formatter is enforced but consistency with existing code is expected.
- **Shell:** ShellCheck-clean. Use `set -euo pipefail`. Source `bin/set-common.sh` for shared functions.
- **TypeScript (web/):** ESLint config in `web/eslint.config.js`. Tailwind CSS for styling.
- **Markdown:** ATX headers, consistent table formatting, no trailing whitespace.

## Making Changes

### Using set-core itself

```bash
# Create a worktree for your change
set-new my-feature

# Work on it
set-work my-feature

# Merge through integration gates
set-merge my-feature
```

### Traditional git workflow

```bash
git checkout -b feature/my-feature
# ... make changes, write tests ...
git push origin feature/my-feature
# Open a pull request
```

## Commit Messages

Use conventional-style prefixes:

```
feat: add new gate type for HIPAA compliance
fix: merger retries on transient git lock
refactor: extract digest parsing into separate module
docs: add plugin development walkthrough
test: cover edge case in merge conflict resolution
```

## Reporting Issues

Include:
- Operating system and version
- Python version (`python3 --version`)
- Steps to reproduce
- Expected vs actual behavior
- Relevant log output (check `~/.local/share/set-core/logs/`)

## Pull Requests

1. Fork the repository
2. Create a feature branch
3. Make focused, minimal changes
4. Ensure tests pass
5. Submit a pull request

### PR Checklist

- [ ] Tests pass (`python -m pytest tests/ --ignore=tests/e2e`)
- [ ] No project-specific logic in `lib/set_orch/`
- [ ] New features have tests
- [ ] Documentation updated if user-facing behavior changed
- [ ] Commit messages are clear and use conventional prefixes

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
