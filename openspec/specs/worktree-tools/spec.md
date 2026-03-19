# worktree-tools Specification

## Purpose
Core worktree lifecycle tools, project management, editor integration, Ralph Loop, installation, and cross-platform support.
## Requirements
### Requirement: Project Management
The system SHALL manage multiple git projects through a central registry.

#### Scenario: Initialize current directory as project
- **WHEN** user runs `set-project init` inside a git repository
- **THEN** the repository is registered with its directory name as project name
- **AND** the project path is stored in `~/.config/set-core/projects.json`
- **AND** set-core hooks, commands, and skills are deployed to `<project>/.claude/`

#### Scenario: Initialize with custom name
- **WHEN** user runs `set-project init --name myproject` inside a git repository
- **THEN** the repository is registered with "myproject" as its name
- **AND** set-core hooks, commands, and skills are deployed to `<project>/.claude/`

#### Scenario: Init outside git repository
- **WHEN** user runs `set-project init` outside a git repository
- **THEN** an error is shown indicating the current directory is not a git repository

#### Scenario: Re-init already registered project
- **WHEN** user runs `set-project init` in an already-registered project
- **THEN** registration is skipped
- **AND** set-core hooks, commands, and skills are updated to the current version

#### Scenario: List registered projects
- **WHEN** user runs `set-project list`
- **THEN** all registered projects are displayed with name and path
- **AND** the default project is marked

#### Scenario: Remove project from registry
- **WHEN** user runs `set-project remove myproject`
- **THEN** the project is removed from the registry
- **AND** existing worktrees are NOT deleted

#### Scenario: Set default project
- **WHEN** user runs `set-project default myproject`
- **THEN** "myproject" becomes the default for other set-* commands

### Requirement: Worktree Creation
The system SHALL create a git worktree for a specified change-id in a standardized location with full project bootstrapping.

#### Scenario: Create worktree for new change
- **WHEN** user runs `set-new <change-id>` (uses default project or current directory)
- **THEN** a new git worktree is created at `../<repo-name>-wt-<change-id>`
- **AND** a new branch `change/<change-id>` is created if it doesn't exist
- **AND** the worktree path is printed to stdout

#### Scenario: Create worktree for specific project
- **WHEN** user runs `set-new <change-id> -p <project-name>`
- **THEN** a worktree is created for the specified registered project

#### Scenario: Worktree already exists
- **WHEN** user runs `set-new <change-id>` and worktree already exists
- **THEN** the existing worktree path is printed
- **AND** no error is raised

#### Scenario: Invalid change-id
- **WHEN** user runs `set-new` without change-id
- **THEN** an error message is displayed with usage instructions

#### Scenario: Custom branch name
- **WHEN** user runs `set-new <change-id> --branch <name>`
- **THEN** the system SHALL use `<name>` as branch name instead of `change/<change-id>`

#### Scenario: Skip git fetch
- **WHEN** user runs `set-new <change-id> --skip-fetch`
- **THEN** the system SHALL skip `git fetch` before creating the worktree

#### Scenario: Force new branch
- **WHEN** user runs `set-new <change-id> --new`
- **THEN** the system SHALL create a new branch even if a remote branch with the same name exists

#### Scenario: Environment file bootstrap
- **WHEN** a worktree is created
- **THEN** the system SHALL copy `.env`, `.env.local`, `.env.development`, `.env.development.local` from the main project if they exist

#### Scenario: Dependency bootstrap
- **WHEN** a worktree is created
- **THEN** the system SHALL auto-detect the package manager (npm, pnpm, yarn, bun) and install dependencies

#### Scenario: Editor configuration setup
- **WHEN** a worktree is created
- **THEN** the system SHALL create editor-specific task files (`.zed/tasks.json` for Zed, `.vscode/tasks.json` for VS Code/Cursor/Windsurf)

#### Scenario: Hook deployment
- **WHEN** a worktree is created
- **THEN** the system SHALL call `set-deploy-hooks` to deploy Claude Code hooks to the new worktree

#### Scenario: CLAUDE.md creation
- **WHEN** a worktree is created for an OpenSpec change
- **THEN** the system SHALL create a `CLAUDE.md` file with change context information

#### Scenario: Auto-open editor
- **WHEN** a worktree is created and `--skip-open` is NOT set
- **THEN** the system SHALL automatically call `set-work` to open the editor

### Requirement: Add Existing Git Repository
The system SHALL allow users to register any existing git repository (worktree or standalone clone) with set-core via `set-add`.

#### Scenario: Add a git worktree
- **WHEN** user runs `set-add /path/to/worktree` where the path is a git worktree (`.git` is a file)
- **THEN** the worktree is registered in projects.json with `is_worktree: true`
- **AND** the main repo is resolved from the `.git` file's gitdir pointer

#### Scenario: Add a standalone git repository
- **WHEN** user runs `set-add /path/to/repo` where the path is a regular git repo (`.git` is a directory)
- **THEN** the repository is registered in projects.json with `is_worktree: false`
- **AND** the repo itself is treated as its own main repo for project detection

#### Scenario: Add with explicit change-id
- **WHEN** user runs `set-add /path/to/repo --as my-change`
- **THEN** the repository is registered with "my-change" as the change-id

#### Scenario: Add with explicit project
- **WHEN** user runs `set-add /path/to/repo -p myproject`
- **THEN** the repository is registered under the "myproject" project

#### Scenario: Change-id derivation
- **WHEN** user runs `set-add /path/to/repo` without `--as` flag
- **THEN** change-id is derived using multi-pattern matching:
  1. `*-wt-<change-id>` directory naming pattern
  2. `*-<change-id>` with repo name stripping
  3. Branch name patterns (`change/X`, `feature/X`)
  4. Directory name as fallback

#### Scenario: Directory is not a git repository
- **WHEN** user runs `set-add /path/to/non-git-dir` where the directory is not a git repository
- **THEN** an error is displayed: "Not a git repository"
- **AND** the directory is NOT registered

#### Scenario: Hook deployment after add
- **WHEN** a repository is successfully added
- **THEN** the system SHALL call `set-deploy-hooks` to deploy hooks

#### Scenario: Already registered
- **WHEN** user runs `set-add /path/to/repo` and the path is already registered with the same change-id
- **THEN** a warning is shown that it's already registered
- **AND** no duplicate entry is created

### Requirement: GUI Add Button Accepts Git Repositories
The GUI "Add" button SHALL accept any valid git repository, not just worktrees.

#### Scenario: Add button opens folder browser
- **WHEN** user clicks the "Add" button in Control Center
- **THEN** a folder browser dialog opens with title "Select Git Repository"

#### Scenario: Add button tooltip
- **WHEN** user hovers over the "Add" button
- **THEN** the tooltip reads "Add existing repository or worktree"

#### Scenario: Successfully add a non-worktree repo via GUI
- **WHEN** user selects a standalone git repository directory in the folder browser
- **THEN** `set-add` is called with the selected path
- **AND** the repo appears in the Control Center table after refresh

### Requirement: Editor Integration
The system SHALL open the Zed editor for a specified worktree.

#### Scenario: Open Zed for worktree
- **WHEN** user runs `set-work <change-id>` with Zed as the active editor
- **THEN** Zed opens the worktree directory without the `-n` (new window) flag
- **AND** if the worktree path is already open in Zed, the existing window SHALL be focused
- **AND** if the worktree path is not open, a new window SHALL be created

#### Scenario: Zed not installed
- **WHEN** user runs `set-work` and Zed is not found
- **THEN** an informative error message is displayed with installation instructions

### Requirement: Worktree Listing
The system SHALL list all active worktrees for projects.

#### Scenario: List worktrees for default project
- **WHEN** user runs `set-list`
- **THEN** all worktrees for the default project are listed
- **AND** each entry shows the change-id and path

#### Scenario: List all worktrees across projects
- **WHEN** user runs `set-list --all`
- **THEN** all worktrees for all registered projects are listed
- **AND** each entry shows the project name, change-id and path

#### Scenario: List worktrees for specific project
- **WHEN** user runs `set-list -p <project-name>`
- **THEN** worktrees for the specified project are listed

#### Scenario: No worktrees exist
- **WHEN** user runs `set-list` and no worktrees exist
- **THEN** an informative message is displayed

#### Scenario: List remote branches
- **WHEN** user runs `set-list --remote`
- **THEN** remote `change/*` branches are listed
- **AND** branches with local worktrees are distinguished from "remote only" branches

### Requirement: Worktree Removal
The system SHALL remove a worktree and optionally its branch. For non-worktree repositories, the system SHALL only deregister them.

#### Scenario: Remove worktree
- **WHEN** user runs `set-close <change-id>` on an entry with `is_worktree: true`
- **THEN** the worktree is removed via `git worktree remove`
- **AND** user is prompted whether to delete the branch

#### Scenario: Remove with force
- **WHEN** user runs `set-close <change-id> --force` on an entry with `is_worktree: true`
- **THEN** the worktree and branch are removed without prompts

#### Scenario: Keep branch after removal
- **WHEN** user runs `set-close <change-id> --keep-branch`
- **THEN** the worktree is removed but the branch is preserved

#### Scenario: Delete remote branch
- **WHEN** user runs `set-close <change-id> --delete-remote`
- **THEN** the remote branch is also deleted after local removal

#### Scenario: Non-TTY context
- **WHEN** `set-close` is run in a non-TTY context (piped, scripted)
- **THEN** the system SHALL auto-select "delete local branch only" without interactive prompts

#### Scenario: Uncommitted changes detection
- **WHEN** user runs `set-close <change-id>` and the worktree has uncommitted changes
- **THEN** the system SHALL block removal unless `--force` is used

#### Scenario: Deregister non-worktree repository
- **WHEN** user runs `set-close <change-id>` on an entry with `is_worktree: false`
- **THEN** the entry is removed from projects.json
- **AND** the repository directory is NOT deleted
- **AND** `git worktree remove` is NOT called

### Requirement: Ralph Loop Management

The system SHALL provide CLI commands for managing autonomous Claude Code loops (Ralph loops).

#### Scenario: Start a new loop

- **GIVEN** a worktree with a change-id exists
- **WHEN** user runs `set-loop start <change-id> "task description"`
- **THEN** a new terminal window opens running the Ralph loop
- **AND** loop state is created in `.claude/loop-state.json`
- **AND** the terminal PID is saved to `.claude/ralph-terminal.pid`

#### Scenario: Start with options

- **GIVEN** a worktree exists
- **WHEN** user runs `set-loop start <change-id> "task" --max 10 --done tasks`
- **THEN** the loop runs for maximum 10 iterations
- **AND** uses tasks.md completion as done criteria

#### Scenario: Start with fullscreen terminal

- **GIVEN** fullscreen is enabled in config or via flag
- **WHEN** user runs `set-loop start <change-id> "task" --fullscreen`
- **THEN** the terminal opens in fullscreen mode

#### Scenario: Check loop status

- **GIVEN** a loop is running or has completed
- **WHEN** user runs `set-loop status [change-id]`
- **THEN** current status is displayed (running/done/stuck/stopped)
- **AND** iteration count and capacity info are shown

#### Scenario: Stop a running loop

- **GIVEN** a loop is running
- **WHEN** user runs `set-loop stop <change-id>`
- **THEN** the loop process is terminated gracefully
- **AND** loop state is updated to "stopped"

#### Scenario: List all active loops

- **GIVEN** one or more loops are active across projects
- **WHEN** user runs `set-loop list`
- **THEN** all active loops are listed with project, change-id, status, and iteration

### Requirement: Loop State File

The system SHALL maintain loop state in a JSON file.

#### Scenario: State file structure

- **GIVEN** a loop is started
- **WHEN** the loop runs
- **THEN** `.claude/loop-state.json` contains:
  - change_id, task, done_criteria
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

### Requirement: Done Detection

The system SHALL support multiple methods to detect loop completion.

#### Scenario: Tasks.md completion

- **GIVEN** done criteria is "tasks"
- **WHEN** checking if done
- **THEN** loop is done when all `- [ ]` in tasks.md become `- [x]`

#### Scenario: Manual done

- **GIVEN** done criteria is "manual"
- **WHEN** checking if done
- **THEN** loop continues until user stops it manually

### Requirement: Loop Output Logging

The system SHALL log all loop output.

#### Scenario: Log file creation

- **GIVEN** a loop is started
- **WHEN** the loop runs
- **THEN** all output is logged to `.claude/ralph-loop.log`

#### Scenario: View log after completion

- **GIVEN** a loop has finished
- **WHEN** user wants to review the session
- **THEN** the log file contains full terminal output for all iterations

### Requirement: Installation
The system SHALL provide installation scripts for all supported platforms that install all necessary dependencies.

#### Scenario: Install on Linux/macOS
- **WHEN** user runs `./install.sh`
- **THEN** tool scripts are symlinked to `~/.local/bin/`
- **AND** Claude Code CLI is installed via npm if not present
- **AND** OpenSpec CLI is installed if not present
- **AND** Zed editor installation is offered if not present
- **AND** `~/.local/bin` is automatically added to the user's shell rc file if not already in PATH
- **AND** `set-skill-start` and `set-hook-stop` SHALL be included in the installed scripts
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
- **AND** OpenSpec CLI is installed if not present
- **AND** Zed editor installation is offered if not present

#### Scenario: Hook deployment updates existing settings
- **WHEN** user runs `./install.sh` and a project already has `.claude/settings.json`
- **THEN** the hooks section SHALL be merged without overwriting existing settings
- **AND** existing hooks for other events SHALL be preserved

### Requirement: Cross-Platform Support
The system SHALL work on Linux, macOS, and Windows. All shell scripts SHALL use platform-appropriate system calls for process inspection and file metadata queries.

#### Scenario: Platform detection
- **WHEN** any tool script is executed
- **THEN** the current platform is detected
- **AND** platform-specific paths and commands are used

#### Scenario: Windows Git Bash
- **WHEN** tools are used from Git Bash on Windows
- **THEN** POSIX shell scripts work correctly

#### Scenario: Agent status detection on macOS
- **WHEN** `set-status` runs on macOS (Darwin)
- **AND** a Claude process is running in a worktree
- **THEN** the process working directory SHALL be resolved using `lsof`
- **AND** the file modification time SHALL be resolved using BSD `stat -f`
- **AND** the correct agent status (running, waiting, compacting) SHALL be returned

#### Scenario: Agent status detection on Linux
- **WHEN** `set-status` runs on Linux
- **AND** a Claude process is running in a worktree
- **THEN** the process working directory SHALL be resolved using `/proc/$pid/cwd`
- **AND** the file modification time SHALL be resolved using GNU `stat -c`
- **AND** the correct agent status (running, waiting, compacting) SHALL be returned

#### Scenario: No Claude processes running
- **WHEN** `set-status` runs on any supported platform
- **AND** no Claude processes are found
- **THEN** the agent status SHALL be "idle"

#### Scenario: Cross-platform helper functions
- **WHEN** shell scripts need process working directory or file modification time
- **THEN** they SHALL use shared helper functions from `set-common.sh`
- **AND** the helpers SHALL abstract platform differences internally

### Requirement: set-openspec documented in CLI Reference
The README CLI Reference SHALL include `set-openspec` as a user-facing command with its subcommands.

#### Scenario: set-openspec in CLI table
- **WHEN** a user reads the CLI Reference section
- **THEN** they SHALL see `set-openspec init`, `set-openspec status`, and `set-openspec update` in the Project Management or a dedicated OpenSpec category

### Requirement: readme-guide.md CLI rules include new commands
The `docs/readme-guide.md` CLI Documentation Rules SHALL include `set-openspec` in the user-facing commands list and `set-hook-memory-recall`, `set-hook-memory-save` in the internal/hook scripts list.

#### Scenario: Guide lists all user-facing commands
- **WHEN** a documentation author reads the CLI Documentation Rules in readme-guide.md
- **THEN** `set-openspec` SHALL be listed among user-facing commands
- **AND** `set-hook-memory-recall` and `set-hook-memory-save` SHALL be listed among internal/hook scripts
