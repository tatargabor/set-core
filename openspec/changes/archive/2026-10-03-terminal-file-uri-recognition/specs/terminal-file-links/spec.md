## MODIFIED Requirements

### Requirement: The reference is reachable while the agent holds the mouse

An agent's own program commonly enables mouse tracking, and while it does, the terminal's
mouse belongs to that program: xterm hands every mouse event to the pty and never activates
a link, so a drawn link does nothing at click time. The framework SHALL provide a way to
open a referenced file that works in that state, and the screen SHALL say how — a control
that silently does nothing under the ordinary condition is worse than an absent one. The
route SHALL be the same gesture in both tracking states — the reader holding CTRL means the
link, not the application — so what works does not depend on which mode the agent's program
left behind, a state the reader cannot see and the terminal does not announce.

#### Scenario: Mouse activation is available

- **WHEN** activating a reference by mouse reaches the terminal in the running system
- **THEN** that is the offered route, and the modifier it needs is stated on the screen

#### Scenario: Mouse activation does not reach the terminal

- **WHEN** the agent's program consumes the click, so mouse activation cannot work
- **THEN** the same modifier-gesture still activates a confirmed reference, because the
  terminal recognises the reference itself before the mouse event can reach the program

#### Scenario: The gesture does not take the program's mouse away

- **WHEN** the reader presses the mouse without the modifier, or where no confirmed
  reference sits under the pointer
- **THEN** the event reaches the terminal's ordinary handling untouched — the program keeps
  its mouse, and selection keeps its own modifier

### Requirement: A terminal token is recognised as one of two kinds of reference

The terminal SHALL recognise a path-shaped token in its output as a reference, and SHALL
distinguish two kinds, because they have different destinations:

- a FILE-VIEW reference — a file of the agent's own project: a project-relative path the
  project actually has, or an absolute path inside the project root, including a trailing
  line number in the `path:line` form the tools in this repository already print;
- a DESKTOP reference — everything else the framework can still name: an absolute path
  outside the project root, and a relative path the project does not have as a file, which
  is resolved against the project root.

The second kind covers the case no listing can ever answer: a DIRECTORY. A file listing
carries files, so `openspec/changes/<name>/` is not in it and never will be.

A relative token SHALL become a desktop reference only when it is shaped like a path and a
project root is known. The shape test is what keeps prose out — a terminal is full of
sentences, and "contains a slash" alone would turn `and/or` and `24/7` into links that fail
when activated. Without a root there is nothing to resolve against, and resolving against a
working directory the reader cannot see would name a stranger's file.

A `file:` URI SHALL be recognised as the path it names — it is the desktop's spelling of a
path, which desktop tools print as readily as the bare form. The translation accepts only a
local file: the URI's host must be empty or `localhost`, the pathname must be absolute, and
a percent-escape that cannot be decoded leaves the token as text. Every other scheme keeps
the behaviour the recognition rules already give it, and the destination rules run on the
translated PATH unchanged, so the hand-over guard rules on exactly the string the bare form
would have produced.

#### Scenario: A relative path with a line number

- **WHEN** the output contains a project-relative path followed by a colon and a number
- **THEN** the terminal treats it as a reference to that file at that line

#### Scenario: An absolute path inside the project

- **WHEN** the output contains an absolute path that lies inside the agent's project root
- **THEN** it is treated as a reference to that file

#### Scenario: An absolute path outside the project

- **WHEN** the output contains an absolute path that does not lie inside the project root
- **THEN** it is recognised as a desktop reference — an agent commonly prints the path of
  what it produced, and it is almost never inside the tree it is working in

#### Scenario: A relative directory

- **WHEN** the output contains a relative path that names a directory of the project
- **THEN** it is recognised as a desktop reference, resolved against the project root — no
  listing contains directories, so this is the only route that can reach one

#### Scenario: A relative path the project's listing does not have

- **WHEN** the output contains a path-shaped relative token that is not a file of the
  listing
- **THEN** it is recognised as a desktop reference rather than left as text

#### Scenario: Prose that merely contains a slash

- **WHEN** the output contains a word such as `and/or` or `24/7`
- **THEN** it is left as ordinary text — an underline that fails when activated costs the
  reader's trust in every other underline on the screen

#### Scenario: A relative token with no project context

- **WHEN** a relative token appears in a terminal whose project root is not known
- **THEN** it is left as ordinary text

#### Scenario: A file: URI spelling of a path

- **WHEN** the output contains a `file:` URI whose host is empty or `localhost` and whose
  pathname is absolute
- **THEN** it is recognised as the path it names — the same reference the bare path would
  produce, destination and guards included

#### Scenario: A file: URI that names another machine

- **WHEN** the output contains a `file:` URI carrying another host, such as
  `file://server/share/report.pdf`
- **THEN** it is left as ordinary text — the path it names is on a machine this framework
  does not hold

#### Scenario: A file: URI with an undecodable escape

- **WHEN** the output contains a `file:` URI whose pathname carries a percent-escape that
  cannot be decoded
- **THEN** it is left as ordinary text — a half-parsed URI is a guess, and a guess that
  opens is worse than text that does nothing
