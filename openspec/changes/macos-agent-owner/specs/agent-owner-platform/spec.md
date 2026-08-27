## IN SCOPE
- Where the owner's control socket lives on each supported platform.
- Which service manager starts the owner, and that the installer places that unit.
- What an operator is told, and shown to run, when the owner is not reachable.
- The refusal the dashboard makes when asked to start the owner itself.

## OUT OF SCOPE
- What the owner does once it is running (holding ptys, replay buffers, drains).
- How an agent is isolated once started — see `agent-isolation-backend`.
- Measuring waiter processes — see `waiter-measurement`.
- Any platform other than Linux and macOS.

## ADDED Requirements

### Requirement: The owner's socket path is resolved per platform

The owner's control socket SHALL be placed in a directory the running platform
actually provides, and the path SHALL be resolved by the same function for the
service that binds it and every client that connects to it, so the two cannot
disagree.

On Linux the path SHALL remain `$XDG_RUNTIME_DIR/set-agent-owner.sock`, falling back
to `/run/user/<uid>` — the expansion the systemd unit's `%t` already produces.

On macOS, where neither `XDG_RUNTIME_DIR` nor `/run/user` exists, the path SHALL be
resolved under the framework's own per-user runtime directory, and that directory
SHALL be created before bind rather than assumed.

#### Scenario: macOS resolves a path that exists
- **WHEN** the socket path is resolved on macOS with `XDG_RUNTIME_DIR` unset
- **THEN** the result is under the framework's per-user runtime directory
- **AND** it does not begin with `/run/user/`

#### Scenario: Linux keeps the unit file's expansion
- **WHEN** the socket path is resolved on Linux with `XDG_RUNTIME_DIR` set
- **THEN** the result is that directory joined with `set-agent-owner.sock`

#### Scenario: The client and the service agree
- **WHEN** the service binds its socket and a client resolves the path to connect
- **THEN** both obtain the same path from the same resolver

### Requirement: An unusable socket path is refused with the reason

The resolver SHALL check the resolved path against the platform's `sun_path` limit
— 104 bytes on macOS, 108 on Linux — and SHALL refuse with a message naming the
path, its byte length and the limit.

This exists because the failure it replaces is misleading: an over-long path fails at
bind with an errno that reads as a missing directory, sending the reader to look for
a directory that is present.

#### Scenario: An over-long path is named as such
- **WHEN** the resolved socket path exceeds the platform's `sun_path` limit
- **THEN** the owner refuses to start with an error naming the path, its byte length
  and the limit
- **AND** the error does not report a missing file or directory

### Requirement: The installer places the owner's service unit on every supported platform

The installer SHALL place, register and start the owner's service unit on macOS as it
already does on Linux, as a job of the service manager rather than as a child of the
dashboard.

The dashboard SHALL NOT start the owner itself. The owner exists because a process
started by the dashboard shares its fate; starting it from the dashboard would return
it to that fate. If the installer does not place the unit, nothing else will, and the
fleet screen's start control is dead.

#### Scenario: macOS install places and loads the job
- **WHEN** the installer runs on macOS
- **THEN** a launchd job for the owner is written to the user's LaunchAgents directory
- **AND** it is loaded, and reported as running or reported as failed — never silently

#### Scenario: The owner is a separate job from the dashboard
- **WHEN** the owner's unit is placed on either platform
- **THEN** it is a distinct unit of the service manager, not spawned by the dashboard
  process

#### Scenario: Restarting the dashboard does not stop the owner
- **WHEN** the dashboard's service is restarted
- **THEN** the owner's service is still running and its socket still answers

### Requirement: The operator is shown a command their machine can run

When the owner is unreachable, the surface SHALL report the reason and SHALL offer a
start command resolved for the running platform.

A command from another platform's service manager is worse than no command: it reads
as an instruction, and following it produces an error that says nothing about the
actual state.

#### Scenario: macOS is not told to run systemctl
- **WHEN** the owner is unreachable on macOS
- **THEN** the offered command is the launchd command for this machine
- **AND** the text does not contain `systemctl`

#### Scenario: Linux keeps its command
- **WHEN** the owner is unreachable on Linux
- **THEN** the offered command is `systemctl --user start set-agent-owner.service`

#### Scenario: The reason is reported, not replaced by the remedy
- **WHEN** the owner is unreachable for any reason
- **THEN** the reported text carries the underlying reason as well as the command
