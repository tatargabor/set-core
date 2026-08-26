## ADDED Requirements

### Requirement: Long lines can be wrapped, and the choice is the reader's

The panel SHALL offer a control that turns line wrapping on and off in the editor, and SHALL
start with it OFF.

Off by default because a wrapped line changes what a line NUMBER means on screen: a reference
of the shape `path:line` — which is what this repository's own tools print, and what the
terminal links into this panel — lands on a row whose position no longer matches the ruler.
So the reader asks for wrapping when they want it; they are not given it when they asked to
go to a line.

The state of the control SHALL survive the panel being torn down and rebuilt — docking it to
an edge, enlarging it, closing and reopening it — because none of those acts is the reader
changing their mind about wrapping. It is a preference about the panel and MAY be persisted
in the browser; it is not a project's file, path or content, which
`Nothing about a project's files is kept in the browser` continues to forbid.

#### Scenario: A long line is wrapped on request

- **WHEN** the reader turns the wrap control on while a file with a line wider than the
  editor is open
- **THEN** that line is wrapped within the editor's width and no horizontal scrolling is
  needed to read it

#### Scenario: Wrapping is off until it is asked for

- **WHEN** a file is opened in a panel where the control has never been touched
- **THEN** long lines extend beyond the editor's width, and the control shows that wrapping
  is off

#### Scenario: The choice survives the panel being rebuilt

- **WHEN** the reader turns wrapping on and then docks the panel to an edge or enlarges it
- **THEN** wrapping is still on

### Requirement: Files the project ignores can be shown on request

The panel SHALL offer a control that adds the files the project's own ignore rules exclude to
the structure, SHALL start with it OFF, and SHALL show an entry that is present only because
the control is on differently from one that would be listed anyway.

Reported 2026-08-26 in the reader's own words — *"`.set` and other directories are not
displayed, they simply are not visible"*. The panel showed a complete-looking tree with a
directory of 156 files missing from it, and nothing on the screen distinguished that from a
project that does not have the directory. That is the false-absence shape this repository
already names: an answer that stopped, read as an answer that is complete.

Ignored entries SHALL be visually subordinate to the rest — they are shown because the reader
asked, not promoted to equals — and the control SHALL make its own state visible, because a
tree that is hiding part of itself must say so where the reader is standing.

#### Scenario: An ignored directory appears when asked for

- **WHEN** the reader turns the ignored-files control on for a project that ignores a
  framework directory
- **THEN** that directory and its files appear in the structure, marked as ignored, and can
  be opened like any other file

#### Scenario: The control's state is visible

- **WHEN** the panel is showing only the project's non-ignored files
- **THEN** the control shows that ignored files are being withheld, so their absence is a
  stated choice rather than an apparent fact about the project

### Requirement: The structure marks what is not committed

The panel SHALL mark, in the structure, every file the version control system reports as
carrying uncommitted work — staged, modified, added, deleted, renamed or untracked — and
SHALL distinguish at least *untracked* from *changed*, because a file that was never
committed and one that was edited since are different situations for the reader.

A directory SHALL carry a mark when anything beneath it does, at any depth. Without that, a
modification inside a collapsed folder is invisible until the folder is opened — which is
the [ui-quality](../../../../.claude/rules/ui-quality.md) rule that compacting must never
hide a failure, applied to a tree: every layout that hides something creates a place a
changed thing can sit while the screen looks settled.

When the listing reports no status at all — a directory that is not a repository — the panel
SHALL mark nothing and SHALL NOT present the absence of marks as *everything is clean*.

#### Scenario: A modified file and an untracked file are marked differently

- **WHEN** the structure holds one file edited since its last commit and one that was never
  committed
- **THEN** each carries a mark, and the two marks are distinguishable from one another and
  from an unchanged file

#### Scenario: A collapsed directory shows that something inside it changed

- **WHEN** a file deep inside a collapsed directory is modified
- **THEN** the collapsed directory itself carries a mark, at every level between it and the
  file

#### Scenario: No status means no claim

- **WHEN** the project has no version-control status to report
- **THEN** no row is marked as clean or as changed, and the panel makes no statement about
  what is committed

### Requirement: The structure follows the file that is open

Whenever a file becomes the open one — picked from the structure, opened from a link in a
terminal, or restored when the panel reappears — the panel SHALL expand every directory
between the root and that file and SHALL bring its row into view.

Marking the active row is not enough on its own, and that is the reported defect: a file
opened from a terminal link is usually many levels down a tree whose branches are all
collapsed, so the mark exists on a row that is not rendered and the reader is left to find
by hand the file the panel already has open.

Expanding SHALL NOT collapse what the reader had opened — following the file adds branches,
it never takes away the ones somebody chose to look at.

#### Scenario: A file opened from a terminal link is revealed

- **WHEN** a file several directories deep is opened while the structure shows only the top
  level
- **THEN** each directory on the path to it is expanded and its row is scrolled into view,
  marked as the open file

#### Scenario: Following does not undo the reader's own expansions

- **WHEN** the reader has expanded several unrelated directories and then opens a file
  elsewhere in the tree
- **THEN** the unrelated directories are still expanded
