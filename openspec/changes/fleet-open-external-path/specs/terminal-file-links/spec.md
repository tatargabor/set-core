## REMOVED Requirements

### Requirement: A file reference in terminal output is recognised

**Reason**: Its scenario *"A path outside the project is not a link"* asserts, by name, the
behaviour this change reverses. Rewriting that scenario's body while keeping its heading would
leave the name contradicting the check — the defect class this repository already refuses (a
name is the copy people actually read). The requirement is therefore removed and replaced by
*"A terminal token is recognised as one of two kinds of reference"* below, which keeps every
other scenario unchanged, word for word.

**Migration**: recognition of the agent's own project files does not change — a relative path
the project has, an absolute path inside the root, and the `path:line` form all behave exactly
as before. What changes is one case that used to be ordinary text: an absolute path outside
the project root. Nothing stored, no API shape, and no URL handling is affected.

## MODIFIED Requirements

### Requirement: Activating a reference opens it in the file view

A person activating a recognised reference to a file of the agent's OWN project SHALL open
that file in the file view panel, at the line the reference named. Nothing SHALL open without
that act.

#### Scenario: The reader activates a reference

- **WHEN** a person activates a recognised file reference in the terminal
- **THEN** the file view opens that file and lands on the named line

#### Scenario: Output alone opens nothing

- **WHEN** an agent prints a file reference
- **THEN** nothing opens until a person acts on it — terminal text is data, never an
  instruction

## ADDED Requirements

### Requirement: A terminal token is recognised as one of two kinds of reference

The terminal SHALL recognise a path-shaped token in its output as a reference, and SHALL
distinguish two kinds, because they have different destinations:

- a reference to a file of the agent's OWN project — a project-relative path the project
  actually has, or an absolute path inside the project root — including a trailing line
  number in the `path:line` form the tools in this repository already print;
- an EXTERNAL reference — an absolute path that does not lie inside the project root.

A relative path the project does not have SHALL remain ordinary text. The known-file set is
what keeps `12:30` and a dotted word out; without it the terminal would offer links to files
that do not exist, and a control that fails when activated is worse than an absent one.

#### Scenario: A relative path with a line number

- **WHEN** the output contains a project-relative path followed by a colon and a number
- **THEN** the terminal treats it as a reference to that file at that line

#### Scenario: An absolute path inside the project

- **WHEN** the output contains an absolute path that lies inside the agent's project root
- **THEN** it is treated as a reference to that file

#### Scenario: An absolute path outside the project

- **WHEN** the output contains an absolute path that does not lie inside the project root
- **THEN** it is recognised as an external reference — an agent commonly prints the path of
  what it produced, and it is almost never inside the tree it is working in

#### Scenario: A relative path the project does not have

- **WHEN** the output contains a token that looks path-shaped but names nothing the project
  has, and is not absolute
- **THEN** it is left as ordinary text

### Requirement: Activating an external reference hands it to the desktop

A person activating a recognised EXTERNAL reference SHALL cause that path to be handed to the
desktop's default application, through the framework's desktop-open capability and its
refusals. The dashboard SHALL NOT attempt to read or display the file itself — the file view
may read only inside a registered project, and pretending otherwise would produce a panel
that opens empty.

Activation SHALL require the same deliberate act as an in-project reference, and no other:
what a plain click does in the terminal is unchanged.

#### Scenario: The reader activates an external path

- **WHEN** a person activates an absolute path outside the project root
- **THEN** the path is handed to the desktop, and nothing is opened inside the dashboard

#### Scenario: A plain click still belongs to the terminal

- **WHEN** a person clicks a recognised external reference without the activation modifier
- **THEN** the click is the terminal's — focus, cursor, selection — and nothing opens

### Requirement: An activation that cannot be honoured says why

Because a path printed in terminal output may name nothing, or may name something the
framework must refuse to run, an activation SHALL be able to fail — and when it does, the
terminal SHALL show the reason where the reader is standing. A link that does nothing when
activated is indistinguishable from a broken screen.

The framework SHALL NOT close this gap by asking in advance whether each path exists. Such a
probe would answer "is there a file at X" for any path on the machine, one request at a time,
which is the oracle `project-file-access` exists to refuse. The trade is deliberate and
stated: some underlined tokens will fail on activation, and they will say why.

#### Scenario: The path names nothing

- **WHEN** a person activates an external reference whose file does not exist
- **THEN** the terminal reports the refusal and its reason, and stays where it was

#### Scenario: The path is something that would be run

- **WHEN** the activated external reference names an executable or a desktop entry
- **THEN** the terminal reports that it was refused, and nothing is started

#### Scenario: No advance probing

- **WHEN** terminal output is rendered
- **THEN** the framework does not ask the server whether the paths in it exist
