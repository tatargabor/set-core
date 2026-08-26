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
as before, and still open in the file view. What changes is what used to be ordinary text: an
absolute path outside the project root, and a path-shaped relative token the listing does not
have — most importantly a DIRECTORY, which no listing can ever contain. Nothing stored, no API
shape, and no URL handling is affected.

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

### Requirement: Activating a desktop reference hands it to the desktop

A person activating a recognised DESKTOP reference SHALL cause that path to be handed to the
desktop's default application, through the framework's desktop-open capability and its
refusals. A directory reaches the desktop the same way a file does; what opens it is the
desktop's own association, which for a directory is a file manager.

The dashboard SHALL NOT attempt to read or display the path itself — the file view may read
only inside a registered project, and it has no way to show a directory at all, so pretending
otherwise would produce a panel that opens empty.

Activation SHALL require the same deliberate act as an in-project reference, and no other:
what a plain click does in the terminal is unchanged.

#### Scenario: The reader activates an external path

- **WHEN** a person activates an absolute path outside the project root
- **THEN** the path is handed to the desktop, and nothing is opened inside the dashboard

#### Scenario: The reader activates a directory

- **WHEN** a person activates a relative directory of the project
- **THEN** the resolved absolute path is handed to the desktop, and the desktop's file
  manager is what opens

#### Scenario: A plain click still belongs to the terminal

- **WHEN** a person clicks a recognised desktop reference without the activation modifier
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

- **WHEN** a person activates a desktop reference whose file does not exist
- **THEN** the terminal reports the refusal and its reason, and stays where it was

#### Scenario: The path is something that would be run

- **WHEN** the activated desktop reference names an executable or a desktop entry
- **THEN** the terminal reports that it was refused, and nothing is started

#### Scenario: No advance probing

- **WHEN** terminal output is rendered
- **THEN** the framework does not ask the server whether the paths in it exist
