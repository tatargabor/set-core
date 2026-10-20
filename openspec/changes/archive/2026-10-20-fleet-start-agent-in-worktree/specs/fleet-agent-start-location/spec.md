## IN SCOPE
- Enumerating, for one known project, every directory the fleet screen may start an agent in: the main checkout and each git worktree.
- Carrying each location's branch, whether it is the main checkout, and whether git reports it `prunable`.
- The start endpoint's rule for which `cwd` values it accepts and which it refuses.
- The start form's worktree selector: its default, its labels, and when it is not shown.

## OUT OF SCOPE
- Creating, removing or pruning a worktree from the dashboard — `set-new` and `set-close` keep that.
- Starting an agent anywhere other than a known project root or one of its worktrees.
- Resuming a recorded session (`agent-fleet-restore` covers that) and the engine's own dispatch of agents into worktrees.
- Any change to how the owner service starts a process once a directory has been chosen.

## ADDED Requirements

### Requirement: A project's startable locations are enumerable
The system SHALL answer, for one project the fleet screen knows, the list of directories an
agent may be started in. The list SHALL contain the project's main checkout and every git
worktree `git worktree list` reports for it. Each entry SHALL carry its absolute path, its
branch (empty when the worktree is on a detached HEAD), whether it is the main checkout, and
whether git reports it `prunable`.

#### Scenario: A project with worktrees lists all of them
- **WHEN** the startable locations of a project whose repository has a main checkout and two worktrees are requested
- **THEN** three entries are returned, exactly one of them marked as the main checkout, each carrying its path and branch

#### Scenario: A project with no worktrees lists only its main checkout
- **WHEN** the startable locations of a project whose repository has no additional worktree are requested
- **THEN** exactly one entry is returned, marked as the main checkout

#### Scenario: A prunable worktree is reported as prunable rather than omitted
- **WHEN** git reports a worktree as `prunable` because its directory no longer exists
- **THEN** the entry is present in the answer and carries `prunable: true`

#### Scenario: A project that is not known is refused
- **WHEN** startable locations are requested for a project name this screen does not list
- **THEN** the request is refused with a 404 naming it, and no list is returned

### Requirement: A prunable worktree is never offered and never accepted
A worktree git reports as `prunable` no longer has a working directory, so an agent cannot
run in it. The system SHALL NOT offer such a location on the start form, and the start
endpoint SHALL refuse it with the same refusal it gives any other unstartable directory.

#### Scenario: The selector omits a prunable worktree
- **WHEN** the start form renders for a project whose repository has one live worktree and one prunable worktree
- **THEN** the selector offers the main checkout and the live worktree only

#### Scenario: Starting in a prunable worktree is refused
- **WHEN** a start is requested with the path of a worktree git reports as prunable
- **THEN** the request is refused with a 400 and no agent is started

### Requirement: The start endpoint accepts a known root or one of its worktrees, and nothing else
`POST /api/fleet/agents` SHALL accept a `cwd` that is a known project root, or a
non-prunable worktree that `git worktree list` reports for one of those roots. Every other
existing directory SHALL be refused with a 400, including a subdirectory of a known root
that is not itself a worktree. The refusal text SHALL name the directory.

#### Scenario: A known project root is still accepted
- **WHEN** a start is requested with a registered project's root as `cwd`
- **THEN** the owner service is asked to start an agent there

#### Scenario: A worktree of a known project is accepted
- **WHEN** a start is requested with the path of a live worktree of a known project
- **THEN** the owner service is asked to start an agent in that worktree

#### Scenario: An arbitrary subdirectory of a known project is refused
- **WHEN** a start is requested with a directory that exists inside a known project root but is not one of its worktrees
- **THEN** the request is refused with a 400 and the owner service is not asked

#### Scenario: A directory belonging to no known project is refused
- **WHEN** a start is requested with an existing directory outside every known root and every worktree of one
- **THEN** the request is refused with a 400 and the owner service is not asked

### Requirement: The start form lets the reader choose the location
The start form SHALL let the reader choose which of the project's startable locations the
agent starts in. The main checkout SHALL be the default. Each worktree SHALL be labelled by
its branch, falling back to the directory's name when the branch is empty. When a project
has no startable location besides its main checkout, the selector SHALL NOT be rendered.

#### Scenario: A project with worktrees offers a choice defaulting to the main checkout
- **WHEN** the start form is opened for a project that has at least one live worktree
- **THEN** a location selector is shown with the main checkout selected

#### Scenario: The chosen worktree is what the start requests
- **WHEN** the reader selects a worktree and submits the form
- **THEN** the start request carries that worktree's path as `cwd`

#### Scenario: A single-checkout project shows no selector
- **WHEN** the start form is opened for a project whose only startable location is its main checkout
- **THEN** no location selector is rendered and the start request carries the project root

#### Scenario: The locations being unreadable does not remove the ability to start
- **WHEN** the startable locations cannot be read for a project
- **THEN** the form still starts an agent in the project root, and says the worktree list could not be read
