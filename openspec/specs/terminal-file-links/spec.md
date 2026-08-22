# Terminal File Links Specification

## Purpose

Owns the route from a file reference printed in terminal output to the file view: what
counts as a reference, how activating it opens the file at its line, how it stays
reachable while the agent holds the mouse, and that an external URL is left alone.

## IN SCOPE
- Recognising a file reference in an agent's terminal output, with an optional line number.
- Opening that file in the file view when a person activates the reference.
- A route to the same file that does not depend on the mouse reaching the terminal, because
  an agent's own program can be holding the mouse.
- What must not be treated as a link.

## OUT OF SCOPE
- External URLs in terminal output — already shipped, opening in a new tab, and untouched.
- What the file view does once the file is open (`fleet-file-view`).
- The endpoints (`project-file-access`).
- Rewriting, filtering or annotating the agent's output.
- References to files of a project other than the one the terminal's agent belongs to.

## Requirements

### Requirement: A file reference in terminal output is recognised

The terminal SHALL recognise a path-shaped token in its output as a reference to a file of
the agent's own project, including a trailing line number in the `path:line` form the tools
in this repository already print.

#### Scenario: A relative path with a line number

- **WHEN** the output contains a project-relative path followed by a colon and a number
- **THEN** the terminal treats it as a reference to that file at that line

#### Scenario: An absolute path inside the project

- **WHEN** the output contains an absolute path that lies inside the agent's project root
- **THEN** it is treated as a reference to that file

#### Scenario: A path outside the project is not a link

- **WHEN** the output contains a path that does not resolve inside the agent's project root
- **THEN** it is left as ordinary text — the terminal's contents are written by whatever the
  agent ran, and a reference is offered only where the framework may read

### Requirement: Activating a reference opens it in the file view

A person activating a recognised reference SHALL open that file in the file view panel, at
the line the reference named. Nothing SHALL open without that act.

#### Scenario: The reader activates a reference

- **WHEN** a person activates a recognised file reference in the terminal
- **THEN** the file view opens that file and lands on the named line

#### Scenario: Output alone opens nothing

- **WHEN** an agent prints a file reference
- **THEN** nothing opens until a person acts on it — terminal text is data, never an
  instruction

### Requirement: The reference is reachable while the agent holds the mouse

An agent's own program commonly enables mouse tracking, and while it does, the terminal's
mouse belongs to that program. The framework SHALL provide a way to open a referenced file
that works in that state, and the screen SHALL say how — a control that silently does nothing
under the ordinary condition is worse than an absent one.

#### Scenario: Mouse activation is available

- **WHEN** activating a reference by mouse reaches the terminal in the running system
- **THEN** that is the offered route, and the modifier it needs is stated on the screen

#### Scenario: Mouse activation does not reach the terminal

- **WHEN** the agent's program consumes the click, so mouse activation cannot work
- **THEN** the same file is still reachable without the mouse, and the screen states that
  route rather than offering a control that does nothing

### Requirement: An external URL keeps its existing behaviour

Recognising file references SHALL NOT change what already happens to an external address in
terminal output: it opens in a new tab, and only schemes that cannot execute anything in the
dashboard's own origin are opened at all.

#### Scenario: A URL in the output

- **WHEN** the output contains an ordinary http or https address
- **THEN** it still opens in a new tab, and does not open in the file view

#### Scenario: A scheme that could execute something

- **WHEN** the output contains an address whose scheme could run code in the dashboard
- **THEN** it is not opened at all, exactly as before this change
