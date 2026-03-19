## MODIFIED Requirements

### Requirement: Worktree Creation
The system SHALL create a git worktree for a specified change-id in a standardized location.

#### Scenario: Create worktree for new change
- **WHEN** user runs `wt-open <change-id>` (uses default project or current directory)
- **THEN** a new git worktree is created at `../<repo-name>-wt-<change-id>`
- **AND** a new branch `change/<change-id>` is created if it doesn't exist
- **AND** the worktree path is printed to stdout

#### Scenario: Create worktree for specific project
- **WHEN** user runs `wt-open <change-id> -p <project-name>`
- **THEN** a worktree is created for the specified registered project

#### Scenario: Worktree already exists
- **WHEN** user runs `wt-open <change-id>` and worktree already exists
- **THEN** the existing worktree path is printed
- **AND** no error is raised

#### Scenario: Invalid change-id
- **WHEN** user runs `wt-open` without change-id
- **THEN** an error message is displayed with usage instructions

### Requirement: Add Existing Git Repository
The system SHALL allow users to register any existing git repository (worktree or standalone clone) with set-core via `wt-add`.

#### Scenario: Add a git worktree
- **WHEN** user runs `wt-add /path/to/worktree` where the path is a git worktree (`.git` is a file)
- **THEN** the worktree is registered in projects.json with `is_worktree: true`
- **AND** the main repo is resolved from the `.git` file's gitdir pointer

#### Scenario: Add a standalone git repository
- **WHEN** user runs `wt-add /path/to/repo` where the path is a regular git repo (`.git` is a directory)
- **THEN** the repository is registered in projects.json with `is_worktree: false`
- **AND** the repo itself is treated as its own main repo for project detection

#### Scenario: Add with explicit change-id
- **WHEN** user runs `wt-add /path/to/repo --as my-change`
- **THEN** the repository is registered with "my-change" as the change-id

#### Scenario: Add with explicit project
- **WHEN** user runs `wt-add /path/to/repo -p myproject`
- **THEN** the repository is registered under the "myproject" project

#### Scenario: Change-id derivation for standalone repo
- **WHEN** user runs `wt-add /path/to/repo` without `--as` flag on a standalone git repo
- **THEN** change-id is derived from branch name patterns (`change/X`, `feature/X`) or directory name as fallback

#### Scenario: Directory is not a git repository
- **WHEN** user runs `wt-add /path/to/non-git-dir` where the directory is not a git repository
- **THEN** an error is displayed: "Not a git repository"
- **AND** the directory is NOT registered

#### Scenario: Bare repository rejected
- **WHEN** user runs `wt-add /path/to/bare-repo` where the directory is a bare git repository (no working tree)
- **THEN** an error is displayed indicating bare repositories are not supported

#### Scenario: Already registered
- **WHEN** user runs `wt-add /path/to/repo` and the path is already registered with the same change-id
- **THEN** a warning is shown that it's already registered
- **AND** no duplicate entry is created

### Requirement: Ralph Loop Management

The system SHALL provide CLI commands for managing autonomous Claude Code loops (Ralph loops).

#### Scenario: Start a new loop

- **GIVEN** user is inside a worktree directory (CWD)
- **WHEN** user runs `wt-loop start "task description"`
- **THEN** a new terminal window opens running the Ralph loop
- **AND** loop state is created in `.claude/loop-state.json`
- **AND** the terminal PID is saved to `.claude/ralph-terminal.pid`

#### Scenario: Start with options

- **GIVEN** user is inside a worktree directory (CWD)
- **WHEN** user runs `wt-loop start "task" --max 10 --done tasks`
- **THEN** the loop runs for maximum 10 iterations
- **AND** uses tasks.md completion as done criteria

#### Scenario: Start with fullscreen terminal

- **GIVEN** fullscreen is enabled in config or via flag
- **WHEN** user runs `wt-loop start "task" --fullscreen`
- **THEN** the terminal opens in fullscreen mode

#### Scenario: Check loop status

- **GIVEN** a loop is running or has completed
- **WHEN** user runs `wt-loop status` from within the worktree
- **THEN** current status is displayed (running/done/stuck/stopped)
- **AND** iteration count and capacity info are shown

#### Scenario: Stop a running loop

- **GIVEN** a loop is running
- **WHEN** user runs `wt-loop stop` from within the worktree
- **THEN** the loop process is terminated gracefully
- **AND** loop state is updated to "stopped"

#### Scenario: List all active loops

- **GIVEN** one or more loops are active across projects
- **WHEN** user runs `wt-loop list`
- **THEN** all active loops are listed with project, worktree name, status, and iteration

### Requirement: Loop State File

The system SHALL maintain loop state in a JSON file.

#### Scenario: State file structure

- **GIVEN** a loop is started
- **WHEN** the loop runs
- **THEN** `.claude/loop-state.json` contains:
  - worktree_name, task, done_criteria
  - max_iterations, current_iteration
  - status (running/done/stuck/stopped)
  - terminal_pid, started_at
  - iterations array with per-iteration details

#### Scenario: Iteration tracking

- **GIVEN** a loop completes an iteration
- **WHEN** the iteration ends
- **THEN** the iterations array is updated with:
  - iteration number, start/end time
  - exit_reason, commits made
  - done_check result

### Requirement: Installation
The system SHALL provide installation scripts for all supported platforms that install all necessary dependencies.

#### Scenario: Install on Linux/macOS
- **WHEN** user runs `./install.sh`
- **THEN** tool scripts are symlinked to `~/.local/bin/`
- **AND** Claude Code CLI is installed via npm if not present
- **AND** Zed editor installation is offered if not present
- **AND** `~/.local/bin` is automatically added to the user's shell rc file if not already in PATH
- **AND** `wt-skill-start` and `wt-hook-stop` SHALL be included in the installed scripts
- **AND** Claude Code hooks SHALL be deployed to all registered projects

#### Scenario: PATH auto-configuration is idempotent
- **WHEN** user runs `./install.sh` multiple times
- **THEN** the PATH export line SHALL be added only once to the shell rc file
- **AND** a marker comment (`# WT-TOOLS:PATH`) SHALL identify the managed line

#### Scenario: Shell rc file detection
- **WHEN** user's default shell is zsh
- **THEN** PATH is added to `~/.zshrc`
- **WHEN** user's default shell is bash
- **THEN** PATH is added to `~/.bashrc`
- **WHEN** user's default shell is neither zsh nor bash
- **THEN** PATH is added to `~/.profile`

#### Scenario: Skip already installed dependencies
- **WHEN** a dependency is already installed
- **THEN** installation is skipped for that dependency
- **AND** user is informed of current version

#### Scenario: Install on Windows
- **WHEN** user runs `install.ps1` in PowerShell
- **THEN** tool scripts are added to user PATH
- **AND** Claude Code CLI is installed via npm if not present
- **AND** Zed editor installation is offered if not present

#### Scenario: Hook deployment updates existing settings
- **WHEN** user runs `./install.sh` and a project already has `.claude/settings.json`
- **THEN** the hooks section SHALL be merged without overwriting existing settings
- **AND** existing hooks for other events SHALL be preserved

## REMOVED Requirements

### Requirement: OpenSpec auto-initialization in worktree creation
**Reason**: Git worktrees inherit all files from the branch. If OpenSpec is initialized on the branch, the worktree already has it. Users who want OpenSpec can run `openspec init` themselves.
**Migration**: Remove `openspec init` calls from `wt-new` and `wt-add`. Remove `--no-openspec` flag from `wt-new`.

### Requirement: OpenSpec installation via install.sh
**Reason**: OpenSpec is a separate tool that users install independently if they choose to use it. set-core should not mandate or install it.
**Migration**: Remove OpenSpec installation step from `install.sh`. Users install OpenSpec via its own installation method.
