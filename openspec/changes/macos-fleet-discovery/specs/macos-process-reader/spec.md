## IN SCOPE
- Which macOS command answers each of the six process facts.
- How a batched read stays cheap on the fleet's polling path.
- How `lsof`'s exit code is treated, and why it is not trusted.
- What macOS answers less precisely than `/proc` does, stated rather than hidden.
- What happens when a required binary is missing, slow, or refuses.

## OUT OF SCOPE
- The contract itself and backend selection — see `fleet-process-source`.
- The Linux backend, which is the existing `/proc` reader moved unedited.
- Reading another user's process state, which macOS does not permit without privilege
  and which this backend never asks for.
- Windows.

## ADDED Requirements

### Requirement: Each fact is read from a measured macOS source

The macOS backend SHALL answer the six contract questions from the following sources, each
of which was run on a real machine against live agent processes before being specified:

| fact | source |
|---|---|
| live pids by identity | `ps -A -o pid=,comm=`, basename compared for equality |
| working directory | `lsof -a -d cwd -Fpn -p <pid[,pid...]>` |
| argument vector | `ps -ww -A -o pid=,args=` (or `-p <pid>` for one) |
| parent pid | `ps -o pid=,ppid=` |
| one environment variable | `ps -E -p <pid> -o command=` |
| executable identity | `ps -p <pid> -o comm=` |

`ps -o comm=` on macOS prints a full executable path for many processes and a bare name for
others, so the backend SHALL compare the **basename**. Linux truncates `comm` to 15
characters and macOS does not; the backend SHALL NOT rely on the two producing identical
strings for a name longer than 15 characters.

#### Scenario: A live agent is found by identity
- **GIVEN** at least one live process whose executable identity is the agent binary
- **WHEN** live pids for that identity are requested
- **THEN** that pid is among them

#### Scenario: A full path is matched by its basename
- **GIVEN** a process table row whose `comm` is an absolute path ending in the requested name
- **WHEN** live pids for that name are requested
- **THEN** that pid is among them

#### Scenario: The working directory of a live pid is resolved
- **WHEN** the cwd of a live agent pid is requested
- **THEN** the absolute path of that process's working directory is returned

#### Scenario: The parent pid of a live pid is resolved
- **WHEN** the parent pid of a live pid is requested
- **THEN** an integer pid is returned

### Requirement: Whole-table questions are answered by one command, not one per pid

The backend SHALL read the whole process table in a single `ps` invocation when a whole-table
question is asked, and SHALL batch `lsof` over all pids of interest in a single invocation
rather than calling it once per pid. Where `/proc` answers per pid at the cost of a file read,
macOS answers at the cost of a process spawn, so a per-pid implementation would spawn one
process per question asked of each agent.

A snapshot taken this way SHALL be scoped to one reading pass and SHALL NOT be cached across
calls. A cached snapshot would report an exited process as live, which is the direction that
lets the resume guard resume onto a live session.

#### Scenario: One process table read per pass
- **WHEN** the fleet enumerates every live agent in one pass
- **THEN** the process table is read once, not once per agent

#### Scenario: Working directories are resolved in one batch
- **WHEN** the working directories of several pids are requested together
- **THEN** a single `lsof` invocation is made carrying all of the pids

#### Scenario: A new pass re-reads rather than reusing
- **WHEN** two separate reading passes are performed
- **THEN** the second reads the process table again rather than answering from the first

### Requirement: lsof output is parsed regardless of its exit code

The backend SHALL parse `lsof`'s standard output whatever its exit code, and SHALL conclude
failure only when the command could not be run at all — it was missing, it raised an
`OSError`, or it timed out. A non-zero exit with parseable output SHALL be treated as a
successful partial answer, and pids absent from the output SHALL be reported as unknown
individually rather than failing the batch.

The reason is that `lsof` exits non-zero when **any** pid in a batch cannot be examined,
including a pid that has simply exited, and does so even when it answered correctly for every
other pid in the same call. Measured: a batch of one live and one dead pid printed the live
pid's working directory and exited 1.

An implementation that returned "could not measure" on a non-zero exit would report the whole
machine as unmeasurable whenever one process exited mid-pass, which during a discovery pass is
ordinary rather than exceptional.

#### Scenario: A dead pid in the batch does not discard the live one
- **GIVEN** a batch containing one live pid and one pid that does not exist
- **WHEN** working directories are requested for the batch
- **THEN** the live pid's working directory is returned
- **AND** the missing pid is reported as unknown

#### Scenario: A missing binary is a failure, an exit code is not
- **WHEN** `lsof` cannot be executed at all
- **THEN** the working directory of every requested pid is reported as unknown
- **AND** the fleet still lists those pids

### Requirement: An environment variable is read only where macOS permits it

The backend SHALL extract one named environment variable by matching `NAME=` against the
whitespace-separated tokens of `ps -E` output, which prints a process's environment after its
command line and which macOS permits for a process the caller owns.

Where the variable cannot be read — the process belongs to another user, `ps` failed, or the
assignment is absent — the backend SHALL return `None`, meaning **unknown**, and SHALL NOT
return an empty string or otherwise imply the variable is set to nothing. The callers act on
that distinction: a waiter whose session is unknown is treated as alive and is never offered
for removal, which is the direction that cannot kill a working one.

#### Scenario: A variable of an owned process is read
- **GIVEN** a process owned by the current user that has the variable set
- **WHEN** that variable is requested
- **THEN** its value is returned

#### Scenario: An unreadable environment is unknown, not empty
- **WHEN** the environment of a pid cannot be read
- **THEN** `None` is returned
- **AND** an empty string is not returned

### Requirement: The loss of argument separation is stated, not hidden

The backend SHALL split an argument vector on whitespace and SHALL document the resulting
loss as a known limitation of the platform rather than presenting the result as an exact
argument vector. `ps` joins an argument vector with spaces, so an argument that itself
contains a space cannot be recovered from macOS at all.

The limitation is acceptable for every current consumer and SHALL remain acceptable only
while that is true: the consumers test fixed positions and flag membership, neither of which
a space breaks. A future consumer needing exact arguments on macOS SHALL be treated as a
change to this capability, not as a bug in it.

#### Scenario: A flag is still detected
- **GIVEN** a process started with a one-shot flag among its arguments
- **WHEN** its argument vector is read on macOS
- **THEN** the flag is present in the result

#### Scenario: Positional structure survives
- **GIVEN** a process whose arguments contain no spaces
- **WHEN** its argument vector is read on macOS
- **THEN** the result equals the argument vector the process was started with

### Requirement: Every external command is bounded and logged on failure

Every `ps` and `lsof` invocation SHALL carry a timeout, and a failure SHALL be logged at
WARNING with the command's identity and its exit status. No failure path SHALL be silent.

Log output SHALL name the shape of what failed and SHALL NOT include a working directory, a
command line or an environment value, because those carry consumer project paths and other
domain content that must not be persisted by this framework.

#### Scenario: A hung command does not hang the fleet
- **WHEN** an external command exceeds its timeout
- **THEN** the call returns the "could not answer" value for that fact
- **AND** a warning is logged

#### Scenario: A failure log carries no path
- **WHEN** a command fails and the failure is logged
- **THEN** the log line contains no working directory and no command line of the inspected
  process
