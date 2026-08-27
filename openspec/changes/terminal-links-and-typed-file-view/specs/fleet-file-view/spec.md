## MODIFIED Requirements

### Requirement: What cannot be shown is stated in the panel

A file that is too large, cannot be read, or is of a type the panel cannot render SHALL
produce a sentence in the panel saying WHICH of those it is. The panel SHALL NOT render an
empty editor for a file it could not read.

The reasons SHALL stay distinguishable from each other. *Too large*, *cannot be rendered* and
*unreadable* send the reader to three different places, and a panel that collapses them into
one sentence sends two of the three to the wrong one. In particular, a large image is refused
for its SIZE, not for its type, and saying otherwise would report a limit the framework does
not have.

#### Scenario: A file the endpoint refused

- **WHEN** the endpoint refuses a file — as too large, as a type with no view, or as
  unreadable
- **THEN** the panel states the reason where the content would be, naming the file

#### Scenario: A file the endpoint refused as too large

- **WHEN** the endpoint refuses a file for exceeding the size cap
- **THEN** the panel states that, naming the file, its size and the cap

#### Scenario: A file of a type the panel cannot render

- **WHEN** the endpoint answers with a media type the panel has no view for
- **THEN** the panel states the media type and the size, and offers the desktop hand-over —
  it does not report the file as unreadable

#### Scenario: An empty file is not a failure

- **WHEN** an opened file has no content
- **THEN** the panel shows an empty file and says so, and does not report it as unreadable

## ADDED Requirements

### Requirement: The panel renders a file by its type

The panel SHALL render what the endpoint gave it according to the type in that answer, in one
place: text in the editor, an image as an image, and a document format the panel supports in
its own view. The reader SHALL NOT have to know which kind of file they activated — the same
act opens all of them, in the same panel, and the panel decides what to draw.

Saving SHALL be offered for TEXT only. A binary the panel merely displays has no editor
behind it, so a save control there would either do nothing or write back something the reader
never edited. The control SHALL be absent rather than present-and-inert.

The panel SHALL NOT decide the type from the file's name. The endpoint answered with what the
bytes are; a second, weaker classifier in the browser would disagree with it eventually, and
the disagreement would show as a file that renders one way and saves another.

#### Scenario: A text file

- **WHEN** the endpoint answers with text
- **THEN** the editor opens it, with the wrap, marker and save behaviour unchanged from before
  this change

#### Scenario: An image

- **WHEN** the endpoint answers with an image media type
- **THEN** the panel displays the image where the editor would be, scaled to fit the panel
  without overflowing it, and offers no save control

#### Scenario: A shell script

- **WHEN** the activated file is a shell script inside a checkout the endpoint serves
- **THEN** it opens in the editor as text, and is editable and saveable like any other text
  file

#### Scenario: A binary with no view

- **WHEN** the endpoint refuses a file as a media type the panel cannot render
- **THEN** the panel names the type and size and offers the desktop hand-over, and shows no
  editor

#### Scenario: Switching from a binary back to text

- **WHEN** the reader opens an image and then opens a text file
- **THEN** the editor returns with the save control, and no state from the image view remains

### Requirement: A directory can be revealed in the structure pane

The panel SHALL be able to reveal a directory: expand its ancestors, scroll the node into
view, and mark it as the current position, without opening any file. This is what an
activated directory reference resolves to.

A reveal that finds nothing SHALL say so. The structure pane is built from a listing of
files, so a directory holding nothing the listing carries has no node — and a control that
silently does nothing is indistinguishable from a broken one.

#### Scenario: A directory that has files beneath it

- **WHEN** a directory of the opened checkout is revealed
- **THEN** its ancestors are expanded, the node is scrolled into view and marked, and no file
  is opened

#### Scenario: A directory the listing has nothing beneath

- **WHEN** the revealed directory has no files under it in the current listing
- **THEN** the panel states that, and mentions that the listing may be excluding what it
  holds rather than implying the directory is empty

#### Scenario: Revealing does not disturb an unsaved edit

- **WHEN** a directory is revealed while the opened file has unsaved edits
- **THEN** the edits are untouched and the file stays open — a reveal is a move in the
  structure pane, not a change of what is open
