## Context

`set-project init` registers a project in `~/.config/set-core/projects.json`. Separately, `wt-deploy-hooks` deploys hooks to a project's `.claude/settings.json`, and `install.sh` creates global symlinks for `/wt:*` commands and skills.

The global symlink approach means all projects share one set-core version. Different projects can't pin to different set-core versions (e.g. from different worktrees/branches).

Claude Code resolves skills/commands with project-local `.claude/` overriding `~/.claude/` (global). So per-project copies are the correct approach.

## Goals / Non-Goals

**Goals:**
- `set-project init` becomes the single command to fully set up or update a project's set-core integration
- Re-running `init` on an already-registered project updates deployed files without re-registering
- Deployed files are copies, enabling per-project version pinning
- `install.sh` stops creating global `/wt:*` symlinks; uses `set-project init` for each registered project instead

**Non-Goals:**
- Deploying opsx commands/skills (managed by openspec, not set-core)
- Auto-updating projects when set-core changes (explicit `set-project init` required)
- Version tracking (no manifest of deployed version — just overwrite)

## Decisions

### D1: Copy, not symlink

Deploy files as copies (`cp -r`), not symlinks. This pins each project to the set-core version it was initialized from. User runs `set-project init` again to update.

Why not symlink: symlinks couple the project to a specific worktree path. If that worktree is removed or the user switches to a different set-core branch, the symlink breaks.

### D2: Resolve source from script location

The set-core repo path is resolved from `set-project`'s own location (`BASH_SOURCE[0]`). This way, running `set-project init` from set-core v6 deploys v6 files, and running it from v5 deploys v5 files. The `SCRIPT_DIR` variable already exists in the script.

### D3: Idempotent init — detect already-registered and deploy anyway

Currently `cmd_init` exits early if the project is already registered ("already registered at ..."). Change this to: skip registration, proceed to deploy. Print "Project already registered. Updating set-core deployment..." and deploy hooks + commands + skills.

### D4: Deploy order

1. Hooks via `wt-deploy-hooks "$git_root"` (existing, proven)
2. Commands: `cp -r $SCRIPT_DIR/../.claude/commands/wt/ $git_root/.claude/commands/wt/`
3. Skills: `cp -r $SCRIPT_DIR/../.claude/skills/wt/ $git_root/.claude/skills/wt/`

Create `.claude/commands/` and `.claude/skills/` dirs if they don't exist.

### D5: install.sh changes

- `install_skills()`: Remove the global symlink creation for `commands/wt` and `skills/wt`
- `install_project_hooks()`: Rename to `install_projects()` and call `set-project init` (which now does hooks + commands + skills) for each project in `projects.json`

## Risks / Trade-offs

- **[Stale copies]** → Projects don't auto-update. User must re-run `set-project init`. This is intentional — explicit is better than magic.
- **[Global symlinks removed]** → After this change, projects not yet init'd won't have `/wt:*` commands. Mitigated by `install.sh` calling init on all registered projects.
- **[.claude/ in .gitignore]** → Most projects gitignore `.claude/`. The deployed files won't be version-controlled in the user's project. This is fine — they're tooling config, not project code.
