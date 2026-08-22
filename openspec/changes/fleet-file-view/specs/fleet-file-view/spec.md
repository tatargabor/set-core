## IN SCOPE
- A file view panel on the fleet screen: the project's structure on one side, one opened
  file on the other.
- Syntax highlighting of the opened file.
- Opening at a named line, and marking that line.
- Editing the opened file and saving it back.
- What the panel must SAY when a file cannot be shown, or a save is refused.
- What the panel must never keep in the browser.

## OUT OF SCOPE
- The endpoints themselves — `project-file-access` owns listing, reading, writing and the
  path guard.
- How a file reference gets here from a terminal — `terminal-file-links` owns that.
- Docking, edges, panel typing and the grid's remaining space — `fleet-dockable-views`
  already owns those, and this panel is one more type under it.
- Creating, renaming or deleting files; multi-file search; find-and-replace across files.
- Diffing against git, blame, or history.
- More than one file open at a time.

## ADDED Requirements

### Requirement: The panel shows a project's structure and one opened file

The fleet screen SHALL offer a file view panel that renders the registered project's file
structure and, beside it, the content of the file the reader opened, with syntax highlighting
appropriate to the file's type.

#### Scenario: A file is opened from the structure

- **WHEN** the reader picks a file from the structure
- **THEN** its content appears beside the structure, highlighted, and the structure marks
  which file is open

#### Scenario: A type with no highlighting still renders

- **WHEN** the opened file's type has no highlighting available
- **THEN** the content is shown as plain text — an unknown type is a file with no colours,
  never a file that fails to open

### Requirement: The panel opens at a named line and marks it

A caller SHALL be able to open a file at a particular line. The panel SHALL bring that line
into view and mark it, so a reader arriving from a reference lands on the thing that was
referred to rather than at the top of the file.

#### Scenario: Opening at a line inside the file

- **WHEN** a file is opened with a line number
- **THEN** the panel scrolls that line into view and marks it distinctly from the rest

#### Scenario: A line beyond the end of the file

- **WHEN** the named line is past the file's last line
- **THEN** the file still opens, at its end, and the panel says the line was not there —
  neither a silent jump to the top nor a failure to open

### Requirement: What cannot be shown is stated in the panel

A file that is too large, is not text, or cannot be read SHALL produce a sentence in the
panel saying which of those it is. The panel SHALL NOT render an empty editor for a file it
could not read.

#### Scenario: A file the endpoint refused

- **WHEN** the endpoint refuses a file as too large or not text
- **THEN** the panel states the reason where the content would be, naming the file

#### Scenario: An empty file is not a failure

- **WHEN** an opened file has no content
- **THEN** the panel shows an empty file and says so, and does not report it as unreadable

### Requirement: An edited file is visibly unsaved until it is saved

The panel SHALL let the reader edit the opened file and save it. While edits are unsaved the
panel SHALL show that, and SHALL NOT let the edits disappear silently: switching away from a
file with unsaved edits SHALL require the reader to decide.

#### Scenario: Editing marks the file as unsaved

- **WHEN** the reader changes the content of the opened file
- **THEN** the panel marks the file as having unsaved changes, and the save control becomes
  available

#### Scenario: Leaving a file with unsaved edits

- **WHEN** the reader opens another file while the current one has unsaved changes
- **THEN** the panel asks first — losing an edit silently is indistinguishable from never
  having made it

#### Scenario: A save that succeeded says so

- **WHEN** a save is accepted
- **THEN** the panel clears the unsaved mark and adopts the identity the endpoint returned,
  so the next save is checked against what was actually written

### Requirement: A refused save is reported, never discarded

When the endpoint refuses a save because the file changed on disk, the panel SHALL keep the
reader's text, SHALL say that the file changed underneath, and SHALL offer to show what is
on disk now. It SHALL NOT overwrite, and SHALL NOT drop the reader's edits.

#### Scenario: An agent changed the file while the reader was typing

- **WHEN** a save is refused because the file changed
- **THEN** the reader's text is still in the editor, the panel says the file changed, and
  nothing was written

#### Scenario: The reader asks to see the current file

- **WHEN** the reader chooses to load what is on disk after a refused save
- **THEN** the panel makes it explicit that this replaces their text, and does it only on
  that choice

### Requirement: Nothing about a project's files is kept in the browser

The panel SHALL NOT write file content, file paths, or anything derived from them into
browser storage of any kind. What the panel holds SHALL live only for as long as it is on
screen.

#### Scenario: A reload starts from nothing

- **WHEN** the dashboard is reloaded after a file was opened
- **THEN** no file content and no path from the previous session is recovered from storage

### Requirement: Closing the panel keeps where the reader was, for this screen only

The panel SHALL come back to the file the reader last had open in that project when it is
opened again with no file named, and SHALL open the named file instead whenever one is
named. What it remembers SHALL live in memory for as long as the screen is open, and SHALL
NOT be written to browser storage — a path belongs to the consumer's domain.

#### Scenario: The panel is closed and opened again

- **WHEN** the reader closes the file view and opens it again from the project header
- **THEN** the file they were reading is open again, at the line it was opened at

#### Scenario: A file is named while another is remembered

- **WHEN** a reference names a file and another file is remembered
- **THEN** the named file opens, and the remembered one does not

#### Scenario: The dashboard is reloaded

- **WHEN** the dashboard is reloaded
- **THEN** nothing about the previously open file is recovered, because none of it was stored
