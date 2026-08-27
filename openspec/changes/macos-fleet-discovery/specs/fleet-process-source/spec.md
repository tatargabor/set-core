## IN SCOPE
- The six process facts the fleet reads, and the one place it reads them from.
- The value that means "could not answer", separately from "answered, nothing there".
- How a backend is selected: by platform, by an explicit `/proc` root, or by name.
- That callers above the package never branch on platform.

## OUT OF SCOPE
- How macOS answers any of the six — see `macos-process-reader`.
- What `discovery`, `instruct` and `purpose` do with the answers — see
  `fleet-platform-neutral-readers`.
- Starting, stopping or isolating an agent — that is the `scopes` package.
- Any platform other than Linux and macOS.

## ADDED Requirements

### Requirement: One source answers six named questions about a process

The fleet SHALL read process state through a single source object rather than by opening
platform paths at each call site. That source SHALL answer exactly six questions, and a
question the fleet needs on every platform SHALL be part of the contract rather than an
attribute of one backend:

- the pids of every live process whose executable identity is a given name,
- the working directory of a pid,
- the argument vector of a pid,
- the parent pid of a pid,
- the value of one named environment variable of a pid,
- the executable identity (`comm`) of a pid.

Identity SHALL be compared as the **basename**, for equality, never as a substring of a
command line. A backend SHALL NOT be asked for a fact outside this set; asking SHALL raise
an error naming the backend and the missing operation rather than returning a value that
reads as an answer.

#### Scenario: Every backend answers the same six
- **WHEN** each backend is inspected for the operations it provides
- **THEN** both provide all six named operations

#### Scenario: A fact outside the contract is refused, by name
- **WHEN** an operation the contract does not name is requested from the source
- **THEN** an `AttributeError` is raised whose message names the backend in use and the
  operation requested

#### Scenario: Identity is not a substring
- **GIVEN** a process whose command line contains the agent's name inside a longer path
- **AND** whose executable identity is a shell
- **WHEN** live pids for the agent's name are requested
- **THEN** that pid is not among them

### Requirement: "Could not answer" is a distinct value from "nothing there"

For every question in the contract, the source SHALL return `None` when the question could
not be answered, and an empty container or a documented empty value when it was answered and
the answer is nothing. These SHALL NOT be collapsed into one value at any level of the
package.

The reason is a caller that already acts on the difference in the opposite direction to a
listing: the resume guard refuses to resume a session something is already running, and there
an empty set means *go ahead*. An unreadable process table flattened to empty would clear the
way for a resume onto a live session, which forks its conversation silently.

#### Scenario: An unreadable process table is not an empty one
- **WHEN** the process table cannot be read at all
- **THEN** the live-pids query returns `None`
- **AND** it does not return an empty list

#### Scenario: A readable table with no matches is empty, not unknown
- **WHEN** the process table is readable and contains no process with the requested identity
- **THEN** the live-pids query returns an empty list
- **AND** it does not return `None`

#### Scenario: A pid that exists but whose cwd cannot be read
- **WHEN** the cwd of a live pid cannot be determined
- **THEN** the cwd query returns `None` for that pid
- **AND** the pid is still reported as live

### Requirement: The backend is selected at access time, never bound at import

The dispatcher SHALL resolve each operation against the selected backend **at attribute
access**, not by binding names when the package is first imported.

Import-time binding freezes the exported names to the function objects the backend held at
import, which makes delegation one-way: replacing a function on the backend module changes
what the backend's own internals see and not what reaches callers, so two halves of one call
chain run different implementations. This was measured in the preceding platform split, where
twelve tests failed in exactly that way.

The dispatcher SHALL also expose which backend is in use, so a diagnostic can report it rather
than leaving a reader to infer it from the platform.

#### Scenario: Replacing a backend function is visible through the dispatcher
- **GIVEN** a test replaces an operation on the selected backend module
- **WHEN** that operation is called through the dispatcher
- **THEN** the replacement runs

#### Scenario: The backend in use is reportable
- **WHEN** the package is asked which backend is active
- **THEN** it names one of the two backends

### Requirement: A backend can be selected explicitly, in three ways

Backend selection SHALL support all three of:

- **by platform** — the default when nothing is specified,
- **by `/proc` root** — an explicit root selects the Linux backend rooted there, on any
  platform, which is how a test drives it against a tree it built,
- **by name** — an explicit backend name, on any platform, so a macOS backend can be
  exercised on Linux and the reverse.

A `/proc` root passed as an argument SHALL select the Linux backend even when running on
macOS. The absence of a root SHALL mean platform dispatch.

Existing call sites SHALL keep their current `proc_root` parameter and its current default,
so that no test which builds a fake `/proc` tree needs editing. An edit to such a test is a
signal that a contract moved, not a routine adjustment.

#### Scenario: An explicit root wins over the platform
- **WHEN** a `/proc` root is passed while running on macOS
- **THEN** the Linux backend is used, rooted at that path

#### Scenario: A backend can be named on the other platform
- **WHEN** the macOS backend is requested by name while running on Linux
- **THEN** the macOS backend is returned

#### Scenario: No root means dispatch by platform
- **WHEN** no root and no name are given
- **THEN** the backend matching the running platform is returned

### Requirement: Callers above the package do not branch on platform

No module outside `procsource` SHALL test `sys.platform` in order to read a process fact, and
no module outside it SHALL construct a path under `/proc`.

The existing `sys.platform == "darwin"` branch inside `live_session_ids()` SHALL be removed
and its behaviour provided by the dispatcher. It was written as a single-function exception
before this package existed; leaving it would keep one function's platform knowledge outside
the one place that is supposed to hold it.

#### Scenario: No platform branch survives in the readers
- **WHEN** the fleet's reader modules are searched for a `sys.platform` test guarding a
  process read
- **THEN** none is found

#### Scenario: No /proc path is built outside the package
- **WHEN** the fleet's reader modules are searched for a literal `/proc` path construction
- **THEN** none is found outside the `procsource` package
