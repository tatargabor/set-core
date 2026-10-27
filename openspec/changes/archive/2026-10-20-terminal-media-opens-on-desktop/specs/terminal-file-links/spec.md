## MODIFIED Requirements

### Requirement: A file of a readable checkout opens in the internal editor

A reference to a file the file endpoints will serve SHALL open in the dashboard's own file
view, and only what those endpoints refuse SHALL be handed to the desktop.

The set the file view covers is **every checkout the endpoints already accept** — a
registered project root, and a non-prunable worktree of one — and not merely the checkout the
agent is standing in. A worktree agent printing an absolute path into the main checkout, and
an agent naming a file of a second registered project, are the same case: the framework may
read it, so the framework opens it. Measured over 30 session transcripts: **125 distinct text
files under a registered project root** were handed to the desktop instead, where the reading
guard exists on the server and would have served every one of them.

Whether a file carries an executable bit SHALL NOT affect this route. Reading is not running:
the file view opens a file to display its bytes and never executes anything, so the guard
that refuses an executable belongs to the desktop route alone. Measured: **12 distinct
existing files were plain UTF-8 text AND executable**, and were refused at both ends —
unopenable anywhere in the product.

What the desktop gets is therefore exactly:

- a path under no registered project or worktree of one;
- a MEDIA file — a name ending in one of the media suffixes the desktop-open capability lists
  (video, audio, raster image, PDF) — wherever it lives, inside a checkout included. The file
  view is an editor; a person activating a video or a picture in a terminal wants the player or
  the viewer, and sending it through the editor first is a detour that, on a drive without Unix
  permissions, ends in two refusals. The list is the SAME list the desktop guard lifts the
  executable bit for, held equal by a test, so a media file routed to the desktop is not then
  refused for a permission its filesystem cannot store. `.ts` is not on it: in a code project it
  is TypeScript.

Where the file view reads a checkout other than the project's own, it SHALL SAY SO on screen.
A panel silently showing another branch is the same defect this requirement exists to fix,
pointing the other way: the file is right and the reader's belief about it is not.

#### Scenario: A file of the agent's worktree

- **WHEN** a person activates a relative path that is a file of the agent's worktree
- **THEN** the file view opens it, reading that worktree

#### Scenario: An executable text file

- **WHEN** a person activates a path naming a shell script, or any other text file with an
  executable bit, inside a checkout the endpoints serve
- **THEN** the file view opens it as text, and the desktop route is not involved

#### Scenario: A file of the main checkout, printed by a worktree agent

- **WHEN** a worktree agent prints an absolute path into the project's main checkout and a
  person activates it
- **THEN** the file view opens the main checkout's file, and names that checkout on screen

#### Scenario: A file of another registered project

- **WHEN** the activated path lies inside a registered project other than the agent's own
- **THEN** the file view opens it, reading that project, and names it on screen

#### Scenario: The panel names the checkout it is reading

- **WHEN** the file view is reading a checkout other than the project root
- **THEN** the panel names that checkout where the reader is standing

#### Scenario: A save goes back where the file came from

- **WHEN** a file read from a worktree is edited and saved
- **THEN** it is written back to that worktree, never to the project root

#### Scenario: A path under no known checkout

- **WHEN** the activated reference names a path under no registered project or worktree
- **THEN** it is handed to the desktop, unchanged from today

#### Scenario: A worktree of a known project may be read

- **WHEN** the file endpoints are asked for a non-prunable worktree of a project the screen
  knows
- **THEN** they serve it, with the same confinement, limits and refusals as the project root

#### Scenario: An unrelated directory is still refused

- **WHEN** the file endpoints are asked for a directory that is neither a known project root
  nor a worktree of one — including a subdirectory of a known root
- **THEN** they refuse it

#### Scenario: A media file inside a checkout goes to the desktop

- **WHEN** a person activates a path ending in `.mp4` or `.png` that lies inside a checkout the
  file view serves
- **THEN** it is handed to the desktop, and the file view is not opened

#### Scenario: A TypeScript file is not media

- **WHEN** a person activates a `.ts` file of the agent's checkout
- **THEN** the file view opens it
