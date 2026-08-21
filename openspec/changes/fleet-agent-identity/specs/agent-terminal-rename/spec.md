## IN SCOPE
- Changing the name of an agent whose terminal this framework holds, while it keeps running.
- Refusing a name that another held agent already carries, and saying which one holds it.
- Carrying the new name into everything that addresses an agent by name: the terminal socket, the stop action, the durable record, the docked panel.
- The surface control that performs the rename, and what it reports.
- Storing the scope unit as a fact, so that a name is no longer welded to a systemd unit name.

## OUT OF SCOPE
- Renaming an agent this framework does not hold. There is no name to change — the runtime derived it, and this framework cannot write to the runtime's record.
- Renaming a session, a project, a transcript or a git branch. This is the agent's terminal identity only.
- Changing what an agent is *doing*. A rename is a metadata change and must be invisible to the process.
- Recovering a name that was never recorded. Restoring a lost name is a human act performed *through* this capability, not something the framework can derive.

## ADDED Requirements

### Requirement: A framework-held agent can be renamed while it runs

The framework SHALL provide an operation that changes the label of an agent whose terminal
it holds, without stopping the agent, without resuming its session, and without restarting
its scope. After the rename the same process SHALL still be running, with its terminal
history intact and any unsent input in its prompt untouched.

An agent the framework does not hold SHALL NOT be renamable, and the refusal SHALL say that
the name belongs to the runtime rather than to this framework.

#### Scenario: A running agent takes a new name and keeps running

- **WHEN** an agent held under label `L` with pid `P` is renamed to `N`
- **THEN** the operation succeeds, the agent is afterwards held under `N`, and pid `P` is still the live process

#### Scenario: A rename does not resume, stop or re-create anything

- **WHEN** an agent is renamed
- **THEN** no session is resumed, no scope is stopped or started, and the agent's transcript gains no new session

#### Scenario: An agent the framework does not hold cannot be renamed

- **WHEN** a rename is requested for an agent whose population is not `started-here`
- **THEN** the request is refused with a reason stating the framework does not hold that agent's terminal

### Requirement: The scope unit is a stored fact, not a name derived from the label

The framework SHALL store the systemd unit of each agent it starts and SHALL address that
agent's unit by the stored value. It MUST NOT re-derive a unit name from a label at the
point of use.

The reason is the rename above: a unit name cannot be changed once the unit exists, so a
label that a unit name is computed from is a label that cannot change without destroying
and re-creating the agent. Deriving the unit at start time is correct; deriving it again
later is what welds the two together.

#### Scenario: A renamed agent is still addressed by its original unit

- **WHEN** an agent started as unit `U` under label `L` is renamed to `N`, and is then stopped
- **THEN** unit `U` is the unit that is stopped, and the stop succeeds

#### Scenario: A label whose derived unit name differs from the stored one does not lose the agent

- **WHEN** an agent's label is such that deriving a unit name from it would produce something other than its stored unit
- **THEN** every operation on that agent still reaches it

### Requirement: A rename refuses a name another held agent carries

The framework SHALL refuse a rename to a label another held agent already carries, and the
refusal SHALL name the collision. It MUST NOT silently derive a variant of the requested
name: a rename is a deliberate act by a person who is looking at the screen, and a name
they did not choose appearing instead is a false value they have no reason to question.

This is deliberately different from restore, which MAY derive a free label — there, the
alternative is losing an agent, and nobody is watching.

#### Scenario: A taken name is refused with the holder named

- **WHEN** a rename to `N` is requested while another held agent carries `N`
- **THEN** the request is refused, the answer states that `N` is already held, and neither agent's label changes

#### Scenario: Renaming an agent to the name it already has changes nothing and is not an error

- **WHEN** an agent held under `L` is renamed to `L`
- **THEN** the operation succeeds and nothing changes

### Requirement: A rename carries into everything that addresses the agent by name

After a successful rename the framework SHALL address the agent under the new label
everywhere a label is the address: the terminal relay, the stop action, the durable record
of what the fleet has seen, and any docked panel bound to that agent. A panel docked to the
agent under its old label SHALL follow the rename rather than becoming an empty panel.

The old label SHALL NOT remain addressable. Two names for one agent is the divergence this
change exists to end.

#### Scenario: The terminal and the stop action follow the new name

- **WHEN** an agent is renamed from `L` to `N`
- **THEN** the terminal relay and the stop action for `N` reach that agent, and requests under `L` do not

#### Scenario: A docked panel follows its agent's rename

- **WHEN** an agent docked to an edge is renamed
- **THEN** the panel is still docked to the same edge for the same agent, and does not report a missing agent

#### Scenario: The durable record carries the new name

- **WHEN** an agent is renamed and the record is written again
- **THEN** the entry for that session carries the new label, so a later restore brings it back under that name

### Requirement: The surface offers rename where the agent's name is shown

The fleet screen SHALL offer a rename control on an agent whose terminal the framework
holds, SHALL show the current name as the starting value, and SHALL report the outcome —
including a refusal and its reason — where the reader is standing.

The control SHALL NOT be offered for an agent the framework does not hold, rather than being
offered and failing.

#### Scenario: A held agent offers rename

- **WHEN** an agent's tile is shown and its population is `started-here`
- **THEN** a rename control is available on that tile

#### Scenario: A refusal is shown on the tile, not swallowed

- **WHEN** a rename is refused because the name is taken
- **THEN** the tile shows the refusal and the reason, and the displayed name is unchanged
