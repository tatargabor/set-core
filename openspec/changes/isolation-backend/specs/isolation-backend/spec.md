## ADDED Requirements

## IN SCOPE
- Abstract `IsolationBackend` interface with create/remove/list/sync operations
- `WorktreeBackend` wrapping existing `git worktree` commands
- `BranchCloneBackend` using `git clone --branch` for full directory isolation
- Configuration via `execution.isolation` in orchestration.yaml
- Backend auto-detection based on config (default: worktree for backward compat)

## OUT OF SCOPE
- Renaming CLI commands (wt-new, wt-close stay as-is)
- Renaming state fields (worktree_path stays as-is)
- Non-git VCS support (e.g., Mercurial, SVN)
- Hybrid mode (mixing backends within a single orchestration run)
- Remote clone backends (SSH/HTTPS clone to different machines)

### Requirement: Backend interface abstraction
The system SHALL provide an `IsolationBackend` abstract base class that defines the contract for all isolation strategies. All orchestration code that currently calls `git worktree` directly SHALL route through the backend interface instead.

#### Scenario: Backend is resolved from config
- **WHEN** the orchestrator starts with `execution.isolation: branch-clone` in orchestration.yaml
- **THEN** all isolation operations use the `BranchCloneBackend` implementation

#### Scenario: Default backend is worktree
- **WHEN** no `execution.isolation` key exists in orchestration.yaml
- **THEN** the system uses `WorktreeBackend` (backward compatible)

### Requirement: Worktree backend
The `WorktreeBackend` SHALL wrap the existing `git worktree add`, `git worktree remove`, and `git worktree list` operations without changing their behavior. This is a refactor-only extraction — no functional changes.

#### Scenario: Create via worktree backend
- **WHEN** `WorktreeBackend.create(project_path, change_name, branch_name)` is called
- **THEN** the system executes `git worktree add <path> -b <branch>` and returns the worktree path

#### Scenario: Remove via worktree backend
- **WHEN** `WorktreeBackend.remove(project_path, wt_path)` is called
- **THEN** the system executes `git worktree remove --force <path>` and cleans up the branch

#### Scenario: List via worktree backend
- **WHEN** `WorktreeBackend.list_active(project_path)` is called
- **THEN** the system executes `git worktree list --porcelain` and returns parsed results

### Requirement: Branch-clone backend
The `BranchCloneBackend` SHALL create isolated directories by cloning the repository with a specific branch, providing full `.git` directory isolation.

#### Scenario: Create via branch-clone backend
- **WHEN** `BranchCloneBackend.create(project_path, change_name, branch_name)` is called
- **THEN** the system creates a new branch from HEAD, then executes `git clone --branch <branch> --single-branch <project_path> <target_path>` and returns the clone path

#### Scenario: Remove via branch-clone backend
- **WHEN** `BranchCloneBackend.remove(project_path, wt_path)` is called
- **THEN** the system removes the clone directory (`shutil.rmtree`) and deletes the branch from the source repo

#### Scenario: List via branch-clone backend
- **WHEN** `BranchCloneBackend.list_active(project_path)` is called
- **THEN** the system scans the expected path pattern (`<project_path>-<change_name>`) and returns active clones with their branch info

#### Scenario: Sync clone with main
- **WHEN** `BranchCloneBackend.sync_with_main(wt_path, change_name)` is called
- **THEN** the system fetches from origin inside the clone and merges/rebases the main branch changes

### Requirement: Path convention preserved
The system SHALL use the same path convention (`<project_path>-<change_name>`) regardless of backend. The `worktree_path` field in state.json SHALL continue to store this path for both backends.

#### Scenario: State compatibility
- **WHEN** a change is dispatched with either backend
- **THEN** `change.worktree_path` in state.json contains the isolation directory path
- **THEN** all downstream code (Ralph loop, verifier, merger, API) works without modification

### Requirement: CLI backend delegation
The `wt-new` and `wt-close` scripts SHALL delegate to the configured backend instead of calling `git worktree` directly. The CLI interface (arguments, output, exit codes) SHALL remain identical.

#### Scenario: wt-new uses configured backend
- **WHEN** user runs `wt-new auth-setup` with `execution.isolation: branch-clone`
- **THEN** the system creates a branch-clone instead of a worktree
- **THEN** the output path format and bootstrap steps are identical

#### Scenario: wt-close uses configured backend
- **WHEN** user runs `wt-close auth-setup` with `execution.isolation: branch-clone`
- **THEN** the system removes the clone directory and branch
- **THEN** the interactive prompts and options (--force, --keep-branch) work identically
