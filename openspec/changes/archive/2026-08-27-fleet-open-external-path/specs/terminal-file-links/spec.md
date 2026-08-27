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

### Requirement: A relative reference belongs to the agent's own working directory

A relative token SHALL be resolved against the working directory of the agent whose terminal
printed it, never against the project root when the two differ, and the destination SHALL
carry WHICH checkout it meant.

The failure this prevents has two halves, and the quiet one is the reason for the rule:

- the path may not exist in the project root, and the reader gets a refusal for a file that
  is plainly in front of the agent;
- the path may exist in BOTH, and the reader is then shown a different file with the same
  name, from another branch, with nothing on screen to say so.

Where no working directory is reported the project root SHALL be used, and the framework
SHALL NOT refuse the reference on that ground — the fallback is wrong only for a worktree,
which is exactly the case the payload reports.

#### Scenario: An agent working in a worktree

- **WHEN** an agent whose working directory is a worktree of the project prints a relative
  path
- **THEN** it is resolved against that worktree

#### Scenario: The same relative path exists in both checkouts

- **WHEN** the relative path is also a file of the project root's own listing
- **THEN** the worktree's copy is still what is opened, and the project root's copy is never
  what the reader gets

#### Scenario: An agent standing in the project itself

- **WHEN** the agent's working directory is the project root
- **THEN** a relative path behaves exactly as before

#### Scenario: No working directory reported

- **WHEN** the payload carries no working directory for an agent
- **THEN** the project root is used, and the reference is still offered

### Requirement: What the internal editor can open, opens in the internal editor

A reference to a FILE of the checkout the agent is standing in SHALL open in the dashboard's
own file view — including a file of a worktree — and only what that view cannot open SHALL be
handed to the desktop.

What the view cannot open, and therefore what the desktop gets, is exactly:

- a DIRECTORY, which no file listing contains;
- a path no listing of that checkout has;
- an absolute path outside that checkout, including one in another checkout of the same
  project.

The framework SHALL therefore read the file listing of the checkout the agent is standing in,
not only of the project root, and SHALL be able to serve the files of a worktree of a project
it knows. A screen that offers to start an agent in a worktree and then refuses to open that
agent's files is two guards that were meant to agree and did not.

Where the file view reads a checkout other than the project's own, it SHALL SAY SO on screen.
A panel silently showing another branch is the same defect this requirement exists to fix,
pointing the other way: the file is right and the reader's belief about it is not.

#### Scenario: A file of the agent's worktree

- **WHEN** a person activates a relative path that is a file of the agent's worktree
- **THEN** the file view opens it, reading that worktree

#### Scenario: The panel names the checkout it is reading

- **WHEN** the file view is reading a checkout other than the project root
- **THEN** the panel names that checkout where the reader is standing

#### Scenario: A save goes back where the file came from

- **WHEN** a file read from a worktree is edited and saved
- **THEN** it is written back to that worktree, never to the project root

#### Scenario: A directory still goes to the desktop

- **WHEN** the activated reference names a directory
- **THEN** it is handed to the desktop — no listing contains a directory, so the file view
  has nothing to open

#### Scenario: A worktree of a known project may be read

- **WHEN** the file endpoints are asked for a non-prunable worktree of a project the screen
  knows
- **THEN** they serve it, with the same confinement, limits and refusals as the project root

#### Scenario: An unrelated directory is still refused

- **WHEN** the file endpoints are asked for a directory that is neither a known project root
  nor a worktree of one — including a subdirectory of a known root
- **THEN** they refuse it

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
