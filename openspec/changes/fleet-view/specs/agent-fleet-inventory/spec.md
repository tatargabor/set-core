## IN SCOPE
- Discovering the agent sessions running on this machine, and the project each belongs to
- Resolving a working directory to a project when it is one of several worktrees
- Binding a running process to the session log it is writing
- Determining which agent started another, and the role that follows from it
- Reporting what a project has wired in
- Reporting, per agent, which sources knew about it
- Listing projects from every source that knows of one, not from a single registry

## OUT OF SCOPE
- Sub-agents a session spawns for itself (a session's own task children)
- Agents on another machine
- Starting, stopping or supervising an agent process
- Deciding what an agent is doing (`agent-fleet-state`) or reaching it (`agent-fleet-instruct`)

## ADDED Requirements

### Requirement: An agent is discovered from process state, not from a command line

The framework SHALL identify a running agent session by its process working directory, and SHALL
NOT require the project path to appear in the process command line.

An interactive session's command line names the binary and its flags, and nothing about the project;
only the working directory does. A discovery that matched command lines would find orchestrator-
spawned agents and be structurally blind to every session a person opened by hand — which is most
of them, and exactly the population this capability exists for.

#### Scenario: An interactive session is discovered
- **WHEN** an agent process runs with a working directory inside a known project and a command line
  that names no path
- **THEN** it appears in the inventory, attributed to that project

#### Scenario: A session in an unregistered directory is still discovered
- **WHEN** an agent process runs in a directory belonging to no registered project
- **THEN** it appears in the inventory, and its project is reported as known from the process alone

### Requirement: A process is bound to its session log by recorded fact, and a guess says so

When a messaging registry records the binding between a process and the session it is writing, the
framework SHALL use that binding. When no such record exists, the framework MAY fall back to a
heuristic, and SHALL mark any binding obtained that way as unconfirmed wherever it is shown.

Measured on a live machine, the obvious heuristic — the most recently modified session log in the
project's directory — was correct for 4 of 9 bindings. Every correct answer came from a project
running one session; every failure from the project running six. It fails precisely where the
surface has value, and its failure direction is the costly one: not a missing log, but confidently
*another agent's* log, in the one situation where several agents are working side by side.

#### Scenario: A recorded binding is used
- **WHEN** the registry records a session id and owning process id for a live process
- **THEN** the inventory binds that process to that session log, marked as confirmed

#### Scenario: A heuristic binding is marked
- **WHEN** no registry record exists and a session log is inferred for a process
- **THEN** the binding is reported as unconfirmed, and the surface shows it as a guess

#### Scenario: No binding is better than a wrong one
- **WHEN** several session logs are equally plausible for one process and no record exists
- **THEN** the agent is listed with no session log rather than with an arbitrary one

### Requirement: The inventory is a union of its sources, and names them

The project list SHALL contain every project known to any source — the project registry, the
messaging registry, and the working directory of any live agent process — and each entry SHALL
report which sources knew about it.

Measured on one machine, the project registry and the messaging registry overlapped on 4 of 20
projects; 8 projects held a discovered agent while being absent from the project registry. A list
built from one source hides projects where work is happening right now, which is the same false
absence this whole change exists to remove.

#### Scenario: A project known only to a live process is listed
- **WHEN** an agent runs in a project that appears in neither registry
- **THEN** the project is listed, sourced from process discovery

#### Scenario: A registered project with no agent is listed
- **WHEN** a registered project has no live agent
- **THEN** it is listed as holding no agents, and is not dropped from the list

#### Scenario: Sources are reported rather than merged away
- **WHEN** a project is known to more than one source
- **THEN** the entry names each source that knew about it

### Requirement: An agent that registers nothing is still an agent

The framework SHALL list a live agent process that has no entry in any registry and no session log,
reporting it from process discovery alone, and SHALL NOT treat the absence of a record as the
absence of an agent. Where such an agent's state cannot be derived, it SHALL be reported as unknown
rather than omitted.

Two conditions were measured in which a running session publishes no record at all, and both are
ordinary rather than exotic:

- **A session started as the child of another agent session** inherits a marker that turns its
  transcript off and keeps it out of the registry. Anything an agent launches from inside its own
  session lands here — which is precisely the population a fleet screen is meant to surface.
- **A session sitting at a start-up prompt** — the one asking whether its directory is trusted —
  is alive, is waiting for a person, and has not registered yet. It is the most actionable state on
  the screen and the native source cannot see it.

Both were found by accident while measuring something else: the first because the measuring session
contaminated the session it started, the second because the started session stopped at a prompt
nobody was watching. Both would have shown a fleet screen with fewer agents than the machine was
running, and shown it calmly — which is the false absence this change exists to remove, arriving
through the source that looks the most authoritative.

#### Scenario: A child session appears
- **WHEN** an agent process runs having inherited a marker that suppresses its registration and its
  transcript
- **THEN** it is listed from process discovery, with its project, and its missing sources named

#### Scenario: A session at a start-up prompt appears
- **WHEN** an agent process is alive but has not yet registered because it is waiting at a start-up
  prompt
- **THEN** it is listed, and reported as waiting rather than as unknown-and-idle

#### Scenario: A record's absence is reported, not resolved
- **WHEN** an agent has no registry entry and no session log
- **THEN** the entry states which sources lacked it, rather than presenting a gap as a determined
  state

### Requirement: A working directory resolves to a project through git, not by path matching

The framework SHALL resolve an agent's working directory to a project through the repository's
common git directory, so that every worktree of one repository resolves to the same project. The
branch of the working directory SHALL be reported per agent.

Measured on a live repository: 5 worktrees, one project. Raw path matching scatters one project's
agents across as many phantom projects as it has worktrees — an earlier draft of this design did
exactly that — and the left column then cannot answer how many agents are working on a project,
which is the question it exists for.

#### Scenario: Agents in different worktrees belong to one project
- **WHEN** two agents run in two worktrees of the same repository
- **THEN** both are attributed to that one project, each reporting its own branch

#### Scenario: A worktree is not a project of its own
- **WHEN** a worktree directory sits beside the main checkout with a similar name
- **THEN** no separate project entry is created for it

#### Scenario: A directory that is not a git repository
- **WHEN** an agent runs in a directory under no repository
- **THEN** the directory itself is the project, and no branch is reported

### Requirement: An agent started by another agent is identified as its descendant

The framework SHALL determine the parent of an agent by walking its process ancestry to the first
ancestor that is itself an agent process, and SHALL report the parent by its **seat identity**
rather than by process id. An agent with such a parent is executing; an agent with a descendant is
directing.

The parent's process id is not stable enough to record: measured across two samples minutes apart,
a spawned agent had finished and its parent had started a replacement under a different process id.
A seat is stable for the life of the session; a process id is recycled by the operating system.

#### Scenario: A spawned agent names its parent
- **WHEN** an agent process descends from another agent process
- **THEN** the inventory reports the parent's seat identity

#### Scenario: An agent started by a person has no parent
- **WHEN** an agent process has no agent ancestor
- **THEN** it is reported as having no parent, which is the ordinary case

#### Scenario: Role follows from the relation, not from a guess
- **WHEN** an agent has at least one agent descendant
- **THEN** it is reported as directing, and each descendant as executing

### Requirement: A project reports what it has wired in, and dim is not absent

The framework SHALL report, per project, which framework capabilities are connected. Where a project
carries an install record naming the modules it has and their versions, that record SHALL be the
source, and a version the project expects but does not have SHALL be reported as a mismatch. Only
where no such record exists MAY presence be inferred from files, and an inference SHALL be marked as
one. A capability that is supported but not connected SHALL be reported as not connected, distinctly
from one that is unknown.

The distinction is the point. "Not wired in" invites wiring it in; "unknown" does not. Collapsing
the two produces a screen that quietly stops offering a capability the project could have.

**The source order matters and it was nearly the wrong way round.** An earlier draft of this
requirement derived everything from files present, which is sniffing for a fact the project is about
to state outright: module installation records which modules a project asked for and at which
version, and it is refused at validation time if that declaration is incomplete. Reading the files
instead would re-derive, less reliably, something already written down — and it cannot express a
version mismatch at all, because a file is either there or not. A declaration and a guess are not
two implementations of one check; they answer different questions, and only one of them can be
wrong about a project that is half-upgraded.

#### Scenario: A connected capability
- **WHEN** the files that constitute a capability are present in a project
- **THEN** the project reports that capability as connected

#### Scenario: A capability that could be connected
- **WHEN** those files are absent but the capability applies to any project
- **THEN** the project reports it as not connected, not as absent

#### Scenario: A declared install record is the source
- **WHEN** a project carries a record of the modules it installed
- **THEN** the capability report is taken from that record rather than from the presence of files

#### Scenario: A version mismatch is reported as such
- **WHEN** a project expects a module version it does not have
- **THEN** the mismatch is reported, distinctly from the module being absent

#### Scenario: An inference says it is one
- **WHEN** no install record exists and presence is inferred from files
- **THEN** the report marks that entry as inferred rather than declared

#### Scenario: The capability set is data, not a fixed list
- **WHEN** a new capability is added to the framework
- **THEN** it can be reported without changing the surface's rendering logic

### Requirement: Nothing derived from an agent's session is persisted

The framework SHALL NOT write any content read from a session log, a declared focus, or a message
to disk, to a cache, to a log file, or into this repository.

A session log is the densest domain source on the machine: it carries whatever the agent read,
wrote and was told, verbatim. Reading it at runtime is the point of this capability; keeping any
of it crosses the confidentiality boundary, which is about persistence rather than about naming.

#### Scenario: A log excerpt is read and dropped
- **WHEN** the inventory reads the tail of a session log to derive state
- **THEN** the excerpt is served to the caller and retained nowhere

#### Scenario: A failure reports shape, not content
- **WHEN** reading a session log fails or its content cannot be parsed
- **THEN** the diagnostic names the file and the failure kind, and quotes no line of it
