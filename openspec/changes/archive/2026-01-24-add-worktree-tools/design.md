## Context
The project's goal is to provide simple CLI tools for OpenSpec-driven development, where git worktrees enable working on multiple spec changes in parallel.

Target platforms:
- Linux (primary)
- macOS
- Windows (Git Bash, WSL, or native PowerShell)

## Goals / Non-Goals
**Goals:**
- Simple, easy-to-use CLI commands
- Minimal dependencies (only git, shell)
- Cross-platform operation
- Zed editor integration

**Non-Goals:**
- GUI
- Other editor support (for now)
- Automating git operations within worktrees

## Decisions

### Script Language Selection
**Decision:** POSIX shell (bash) for Linux/macOS, PowerShell for Windows

**Alternatives:**
- Node.js: too large a dependency
- Python: not always available by default
- Go/Rust binary: build complexity

**Rationale:** Shell scripts have minimal dependencies, are easily auditable, and simple to modify.

### Project Registry
**Decision:** JSON config file at `~/.config/set-core/projects.json`

**Structure:**
```json
{
  "default": "myproject",
  "projects": {
    "myproject": {
      "path": "/home/user/myproject",
      "addedAt": "2025-01-09T12:00:00Z"
    }
  }
}
```

**Alternatives:**
- SQLite: too complex for a simple registry
- YAML: extra dependency
- Plain text: harder to manage

**Rationale:** JSON is natively supported, simple, human-readable.

### Project Context Resolution
**Decision:** Priority order for project determination:
1. `-p <name>` explicit flag
2. If we're in a git repo that's registered → use it
3. Default project (if set)
4. Error if none is available

### Project Registration
**Decision:** `set-project init` while standing in the repo root (not with path argument)

**Rationale:** More intuitive workflow - the user stands in the project and "initializes" it for set-core use. Similar to the `git init` or `npm init` pattern.

### Worktree Naming Convention
**Decision:** `../<repo-name>-wt-<change-id>` pattern

**Example:** If the repo is at `/home/user/myproject`, and the change-id is `add-auth`, then the worktree is: `/home/user/myproject-wt-add-auth`

**Rationale:**
- In parent directory, not inside the repo (avoids nested git problems)
- Clear naming convention for identifying source repo and change

### Zed Launch
**Decision:** Use `zed <path>` command, with platform-specific fallbacks

**Linux:** `zed` or `~/.local/bin/zed`
**macOS:** `zed` or `/Applications/Zed.app/Contents/MacOS/zed`
**Windows:** `zed.exe` or AppData path

### Install Mechanism
**Decision:** Symlink-based install to `~/.local/bin/` directory (Linux/macOS), or PATH modification (Windows)

## Risks / Trade-offs
- **Risk:** Zed not installed → **Mitigation:** Check and informative error message
- **Risk:** Windows compatibility issues → **Mitigation:** Recommend WSL, Git Bash support
- **Trade-off:** POSIX shell vs PowerShell duplication → Simplicity over cross-platform compatibility

## Open Questions
- Is a `wt-status` command needed for querying active worktree state?
- Should we support other editors as well (VS Code, Cursor)?
