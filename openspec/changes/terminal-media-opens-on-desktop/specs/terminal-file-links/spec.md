## MODIFIED Requirements

### Requirement: What the internal editor can open, opens in the internal editor

A reference to a FILE of the checkout the agent is standing in SHALL open in the dashboard's
own file view — including a file of a worktree — and only what that view cannot open SHALL be
handed to the desktop.

What the view cannot open, and therefore what the desktop gets, is exactly:

- a DIRECTORY, which no file listing contains;
- a path no listing of that checkout has;
- an absolute path outside that checkout, including one in another checkout of the same
  project.
- a MEDIA file — a name ending in one of the media suffixes the desktop-open capability lists
  (video, audio, raster image, PDF) — wherever it lives, inside a checkout included. The file
  view is an editor; a person activating a video or a picture in a terminal wants the player or
  the viewer, and sending it through the editor first is a detour that, on a drive without Unix
  permissions, ends in two refusals. The list is the SAME list the desktop guard lifts the
  executable bit for, held equal by a test, so a media file routed to the desktop is not then
  refused for a permission its filesystem cannot store. `.ts` is not on it: in a code project it
  is TypeScript.

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

#### Scenario: A media file inside a checkout goes to the desktop

- **WHEN** a person activates a path ending in `.mp4` or `.png` that lies inside a checkout the
  file view serves
- **THEN** it is handed to the desktop, and the file view is not opened

#### Scenario: A TypeScript file is not media

- **WHEN** a person activates a `.ts` file of the agent's checkout
- **THEN** the file view opens it

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
