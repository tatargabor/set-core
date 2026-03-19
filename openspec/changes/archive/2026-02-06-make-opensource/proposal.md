# Change: Convert set-core to Open Source

JIRA Key: TBD
Story: TBD

## Why

Convert the internal set-core project to a public open-source project on GitHub. This enables:
- Community contributions
- Wider adoption
- Portfolio/showcase value
- Knowledge sharing in the AI-assisted development space

## What Changes

### Phase 1: Proprietary Content Removal
- Updated `.gitignore` to exclude `.set-core/*.json` config files
- Created example config templates (`.set-core/jira.json.example`, `confluence.json.example`)
- Replaced all Zengo URLs with `github.com/anthropic-tools/set-core`
- Replaced all EXAMPLE references with MYPROJECT
- Removed personal paths from CLAUDE.md and bin/wt-jira

### Phase 2: English Translation
- Rewrote README.md in English with full documentation
- Translated docs/config.md to English
- Removed Confluence-specific docs (moved to plugin)
- Translated active OpenSpec proposals to English
- Updated example names (Personal names → Generic examples)

### Phase 3: Plugin Architecture
- Created `set_tools/plugins/` package with:
  - `base.py`: Plugin, PluginInfo, MenuItem, ColumnInfo, PluginRegistry
  - Entry point discovery via `pyproject.toml`
- Updated `JiraMixin` to gracefully handle missing JIRA configuration
- Created `pyproject.toml` with dependencies and entry points
- Created `LICENSE` (MIT)
- Created `CONTRIBUTING.md`

### Phase 4: Cross-Platform Support
- Created `gui/platform/` abstraction layer:
  - `base.py`: Platform interface base class
  - `linux.py`: xdotool, /proc filesystem, fcntl/select
  - `macos.py`: osascript/AppleScript, psutil
  - `windows.py`: pywin32, wmic/PowerShell, msvcrt
- Updated `install.sh` to make xdotool optional
- Enhanced `install.ps1` for full Windows support

### Phase 5: Testing & Documentation
- Created `tests/` directory with pytest tests
- Created `.github/workflows/ci.yml` for Linux, macOS, Windows CI
- Created GitHub issue templates (bug report, feature request)
- Created pull request template

### Phase 6: GitHub Release Preparation
- Repository: https://github.com/anthropic-tools/set-core
- Strategy: Private first for internal testing, then public
- Clean history before public release (squash to single commit)

## Impact

- Affected files: 50+ files modified/created
- New directories: `set_tools/`, `gui/platform/`, `tests/`, `.github/`
- Removed: `docs/confluence.md`, `docs/confluence-upload.md`
- No breaking changes to existing functionality

## Related Projects

Documented in README.md:
- worktrunk - CLI for AI agent parallel workflows
- gwq - Fuzzy finder worktree manager
- git-worktree-runner - CodeRabbit's tool
- crystal - Desktop app for Claude/Codex
- ccmanager - Multi-agent session manager

## Verification

```bash
# Proprietary content check (should return 0)
grep -r "zengo" --include="*.md" --include="*.sh" --include="*.py" . | grep -v archive | wc -l
grep -r "EXAMPLE" --include="*.md" --include="*.sh" --include="*.py" . | grep -v archive | wc -l
grep -r "tatargabor" . | wc -l
```

All checks pass: 0 proprietary references in non-archived files.
