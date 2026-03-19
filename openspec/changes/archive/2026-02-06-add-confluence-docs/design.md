## Context
The documentation needs to serve two target audiences:
1. New users who are just starting to use the tools (tutorial)
2. Experienced users looking for reference (detailed command descriptions)

The documentation must automatically update as spec files change, to prevent drift between actual functionality and documentation.

## Goals / Non-Goals
**Goals:**
- Documentation generated from spec files, always up-to-date
- Tutorial + reference structure in a single Markdown file
- Format easily copyable to Confluence
- Generation can be automated (CI/CD hook)

**Non-Goals:**
- Confluence API integration (automatic publish) - manual copy-paste is sufficient initially
- Multiple language support
- Interactive documentation

## Decisions

### Generation Source
**Decision:** Generate from `openspec/specs/*/spec.md` and `openspec/changes/*/specs/*/spec.md` files

**Structure:**
- Requirement → Documentation section
- Scenario → Example block in documentation
- WHEN/THEN → Usage example

**Rationale:** Spec files already contain the precise behavior, no duplication.

### Documentation Structure
**Decision:** Single `docs/confluence.md` file, with logical sections

```markdown
# set-core Documentation

## Introduction
[What is this, why was it created]

## Quick Start (Tutorial)
### 1. Installation
### 2. Registering a project
### 3. Creating first worktree
### 4. Editing and saving

## Command Reference
### set-project
[Detailed description, every scenario]

### wt-open
[Detailed description, every scenario]

### wt-edit
...

## Troubleshooting
[Common errors and solutions]
```

### Script Language
**Decision:** Bash script for generation, `sed`/`awk` or simple text processing

**Alternatives:**
- Node.js: dependency, but richer parsing
- Python: markdown libraries
- Pandoc: too complex

**Rationale:** Consistent with other wt-* scripts, no extra dependency.

### Scenario → Example Conversion
**Decision:** Transform WHEN/THEN pairs into code blocks

**Input format (spec.md):**
```markdown
#### Scenario: Create worktree for new change
- **WHEN** user runs `wt-open <change-id>`
- **THEN** a new git worktree is created at `../<repo-name>-wt-<change-id>`
```

**Output format (confluence.md):**
```markdown
**Example: Create worktree for new change**
```bash
wt-open add-auth
# Result: worktree created at ../myproject-wt-add-auth
```
```

### Update Workflow
**Decision:**
1. Spec changes → `docs-gen` runs → `docs/confluence.md` updates
2. Developer copies to Confluence (manual)
3. Optionally: GitHub Action that automatically runs generation on PR

## Risks / Trade-offs
- **Risk:** Spec format changes and parser breaks → **Mitigation:** Simple regex-based parsing, easy to fix
- **Trade-off:** Manual Confluence update vs API integration → Simpler initially, can be extended later
- **Risk:** Confluence formatting differences → **Mitigation:** Basic Markdown, avoid fancy formatting

## Open Questions
- Should there be a version number in the documentation?
- Should there be a changelog section?
