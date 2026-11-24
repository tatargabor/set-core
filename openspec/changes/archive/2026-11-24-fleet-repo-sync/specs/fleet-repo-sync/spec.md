## IN SCOPE
- A fleet header chip that opens a floating, read-only table of recently active projects' git state
- Per project: branch, uncommitted files, ahead/behind upstream, unpushed local branches, worktrees, stash count, remote host, last fetch time
- An activity window (default 30 days) over commits by anybody on any branch, adjustable
- Hiding a project from the table, and a separate view to bring hidden projects back
- A computation that runs only when the table is opened or refreshed
- An explicit fetch control
- A push-may-deploy hint read from the tree's own CI and hosting files

## OUT OF SCOPE
- Pushing, pulling, rebasing, deleting branches or removing worktrees from the screen
- Running the leak scan per row
- Querying a hosting provider's API for its production branch
- Comparing this machine with another machine directly (the remote is the meeting point)
- Background polling or a server-side refresh cycle

## ADDED Requirements

### Requirement: The state is computed only when somebody asks for it
The system SHALL compute the repository state only on a request to `GET /api/fleet/repo-sync`,
which the screen sends when the table is opened and when its refresh control is used. The system
SHALL NOT compute it on a timer, on page load, or as part of the fleet listing.

#### Scenario: Opening the fleet does not scan
- **WHEN** the fleet screen loads and the Repos table is not opened
- **THEN** no request to `GET /api/fleet/repo-sync` is sent and no git command runs for it

#### Scenario: Opening the table scans once
- **WHEN** the owner opens the Repos table
- **THEN** exactly one request to `GET /api/fleet/repo-sync` is sent, and a second one only when the refresh control is used

### Requirement: The listed projects are the recently active registered ones
The system SHALL list every registered project whose tree exists, that the owner has not hidden,
and that is active within the window: a commit by anybody on any local branch or remote-tracking
branch, with a committer date within the last `days` days. Fetch times and session activity SHALL
NOT count as activity. `days` SHALL come from the request, else machine-local
`fleet_repo_sync_days`, else 30. Archived projects, hidden projects and projects under the e2e-run
directory SHALL be left out, and the answer SHALL carry how many were left out for each reason.

#### Scenario: An old project is left out and counted
- **WHEN** a registered project's newest commit on any branch is older than the window
- **THEN** it is not in `projects`, and `excluded.inactive` counts it

#### Scenario: A commit somebody else pushed makes a project active
- **WHEN** the only commit within the window is on a remote-tracking branch, made by another author
- **THEN** the project is listed

#### Scenario: Session activity alone does not list a project
- **WHEN** a project has a session transcript written yesterday and no commit within the window
- **THEN** it is not listed

#### Scenario: A missing tree is reported, not dropped
- **WHEN** a registered, non-archived project's path does not exist
- **THEN** it is counted in `excluded.missing` with its name

### Requirement: The owner can hide a project and bring it back
The system SHALL keep a machine-local list of hidden projects (`fleet_repo_sync_hidden`). A hidden
project SHALL NOT be listed or measured, SHALL be counted in `excluded.hidden`, and its name SHALL
be in the answer's `hidden` list. The screen SHALL offer a hide control on every row and a separate
view of the hidden projects, each with a control that puts it back. Hiding and restoring SHALL
change only this list — never a repository.

#### Scenario: A hidden project leaves the table and appears in the hidden view
- **WHEN** the owner hides a project
- **THEN** the next measurement does not list it, `excluded.hidden` counts it, and the hidden view shows it

#### Scenario: A restored project returns
- **WHEN** the owner restores a hidden project that is active within the window
- **THEN** the next measurement lists it again

### Requirement: Each project row carries its commit and push state
For each listed project the answer SHALL carry: the current branch (or a detached marker); the
number of uncommitted entries; the upstream and the ahead/behind counts against it, or an explicit
`no-upstream`; the local branches that carry commits on no remote ref, each with its count and last
commit age; the stash count; the remote host (never the full URL with credentials); and the age of
the last fetch. A value the system could not read SHALL be `null` with a reason, never `0`.

#### Scenario: Ahead and behind are counted against the upstream
- **WHEN** the current branch has 2 commits not on its upstream and the upstream has 3 not on it
- **THEN** the row says ahead 2, behind 3, and is flagged diverged

#### Scenario: A branch with no remote copy is listed
- **WHEN** a local branch other than the current one has 4 commits that no remote ref contains
- **THEN** it appears under the row's unpushed branches with count 4

#### Scenario: An unreadable repository is a gap, not a clean row
- **WHEN** a git command for a project fails or times out
- **THEN** the affected fields are `null` with the reason, and the row is flagged as a problem

### Requirement: Worktrees are listed with what decides whether they are worth keeping
For each listed project the answer SHALL list its additional worktrees with: path, branch, age of
the last commit, uncommitted entry count, whether the branch is merged into the main worktree's
branch, and whether the worktree's directory still exists.

#### Scenario: A merged, clean worktree is marked removable
- **WHEN** a worktree's branch is an ancestor of the main branch and it has no uncommitted entries
- **THEN** the worktree is marked `merged` and clean

#### Scenario: A worktree whose directory is gone is marked prunable
- **WHEN** git lists a worktree whose path no longer exists
- **THEN** it is marked `missing`

### Requirement: A push that may deploy is hinted, naming its source
The system SHALL mark a project `push_may_deploy` when its own tree shows that a push to its
current branch may start a deployment: a CI job in a deploy stage, or with a production
environment, whose rules match that branch and which is not gated by a manual step; or a linked
hosting project whose production branch cannot be read locally. The hint SHALL name the file it was
read from and SHALL say `unknown` rather than `no` when the files cannot settle it.

#### Scenario: An automatic production deploy on the current branch is hinted
- **WHEN** a CI file has a deploy job with a production environment that runs on the current branch without a manual gate
- **THEN** the row carries `push_may_deploy: yes` with that file's path

#### Scenario: A manual production gate is not a deploy-on-push
- **WHEN** the only production deploy job on the current branch is gated `when: manual`
- **THEN** the row does not carry `push_may_deploy: yes`

#### Scenario: A linked hosting project is unknown, not safe
- **WHEN** the tree has a hosting link file and no CI deploy job
- **THEN** the row carries `push_may_deploy: unknown` naming the link file

### Requirement: Fetching is explicit and bounded
The system SHALL fetch remote refs only on `POST /api/fleet/repo-sync/fetch`, for the listed
projects or the ones named in the request, with bounded concurrency and a per-repository timeout,
and SHALL answer per project whether the fetch succeeded, timed out or failed.

#### Scenario: A slow remote does not hold the others
- **WHEN** one project's remote does not answer within the timeout
- **THEN** that project is reported `timeout` and every other project's fetch result is still returned

### Requirement: The chip never shows a calm it did not measure
The header chip SHALL show the problem count and the age of the most recent measurement made in
this browser session, and SHALL read "not measured" before the first one. A problem is: uncommitted
entries, ahead, behind, no upstream, an unpushed branch, an unreadable field, or a deploy hint of
`yes`. Problem rows SHALL sort above clean ones in the table.

#### Scenario: Before the first opening the chip makes no claim
- **WHEN** the fleet loads and the table has not been opened
- **THEN** the chip shows no count and reads "not measured"

#### Scenario: After a measurement the chip carries its count and age
- **WHEN** a measurement found 5 problem projects 10 minutes ago
- **THEN** the chip shows 5 and "10 min ago"

### Requirement: The table floats and is read-only
The table SHALL be absolutely positioned under the header, push nothing in the layout, close on
its own control, on Escape and on an outside click, and SHALL offer no control that changes a
repository other than the fetch (hiding changes only the machine-local hidden list).

#### Scenario: Opening the table moves nothing
- **WHEN** the owner opens the Repos table
- **THEN** the header height and the agent area's position are unchanged

### Requirement: Nothing read from a project is persisted
The system SHALL NOT write any value read from a project tree — branch names, file names, commit
messages, remote URLs — to disk, to a cache file or to the log; logs SHALL carry counts and
registered project names only.

#### Scenario: A scan leaves no derived file
- **WHEN** a scan completes
- **THEN** no file under the set-core state or cache directories was created or changed by it
