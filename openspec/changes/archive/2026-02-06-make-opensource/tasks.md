## Phase 1: Proprietary Content Removal
- [x] 1.1 Update `.gitignore` to exclude `.set-core/*.json`
- [x] 1.2 Create example config templates
- [x] 1.3 Replace Zengo URLs with GitHub URL
- [x] 1.4 Replace EXAMPLE with MYPROJECT
- [x] 1.5 Remove personal paths from CLAUDE.md
- [x] 1.6 Update bin/wt-jira to use dynamic paths

## Phase 2: English Translation
- [x] 2.1 Rewrite README.md in English
- [x] 2.2 Translate docs/config.md
- [x] 2.3 Remove docs/confluence.md, docs/confluence-upload.md
- [x] 2.4 Translate openspec/changes/add-ralph-loop/proposal.md
- [x] 2.5 Translate openspec/changes/add-confluence-docs/*.md
- [x] 2.6 Update example names in specs

## Phase 3: Plugin Architecture
- [x] 3.1 Create `set_tools/plugins/__init__.py`
- [x] 3.2 Create `set_tools/plugins/base.py` with Plugin, PluginRegistry
- [x] 3.3 Update JiraMixin with `is_jira_available()` check
- [x] 3.4 Create `pyproject.toml` with entry points
- [x] 3.5 Create LICENSE (MIT)
- [x] 3.6 Create CONTRIBUTING.md

## Phase 4: Cross-Platform Support
- [x] 4.1 Create `gui/platform/__init__.py` with detection
- [x] 4.2 Create `gui/platform/base.py` interface
- [x] 4.3 Create `gui/platform/linux.py`
- [x] 4.4 Create `gui/platform/macos.py`
- [x] 4.5 Create `gui/platform/windows.py`
- [x] 4.6 Update install.sh (xdotool optional)
- [x] 4.7 Enhance install.ps1 for Windows

## Phase 5: Testing & Documentation
- [x] 5.1 Create `tests/__init__.py`
- [x] 5.2 Create `tests/test_plugins.py`
- [x] 5.3 Create `tests/test_platform.py`
- [x] 5.4 Create `.github/workflows/ci.yml`
- [x] 5.5 Create issue templates
- [x] 5.6 Create PR template

## Phase 6: GitHub Release
- [x] 6.1 Update all URLs to github.com/anthropic-tools/set-core
- [x] 6.2 Add Related Projects section to README
- [ ] 6.3 Push to private GitHub repo
- [ ] 6.4 Add collaborators for testing
- [ ] 6.5 Squash history before public release
- [ ] 6.6 Make repository public
