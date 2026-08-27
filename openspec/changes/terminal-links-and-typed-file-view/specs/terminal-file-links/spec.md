## MODIFIED Requirements

### Requirement: A terminal token is recognised as one of two kinds of reference

The terminal SHALL recognise a path-shaped token in its output as a reference, and SHALL
distinguish two kinds, because they have different destinations:

- an INTERNAL reference — a file or directory the framework may read: one belonging to any
  checkout the file endpoints will serve (a registered project, or a non-prunable worktree of
  one), whether or not it is the checkout the agent is standing in, including a trailing line
  number in the `path:line` form the tools in this repository already print;
- a DESKTOP reference — a path the framework may name but not read: one that lies under no
  such checkout.

Recognition SHALL survive the punctuation agents actually write around a path. Terminal
output is prose with markup in it, so a token SHALL be stripped of markdown emphasis, code
fences, brackets, quotes and a trailing table-cell separator before it is judged, and a
trailing `:<line>` SHALL be kept as the line number rather than stripped as punctuation.
Measured over 30 session transcripts: of 249 distinct tokens that named a file which exists
and were nonetheless left as plain text, **121 were lost to leftover markup alone**.

A token beginning with `~/` SHALL be resolved to the home directory of the account the
framework runs as, and SHALL then be judged as any other absolute path. The browser SHALL NOT
guess at that expansion.

**Recognition SHALL have a CONFIDENCE tier, not a binary link-or-text answer.** A token the
framework can place — inside a served checkout, or shaped unambiguously like a file path —
SHALL be drawn as a link. A token that is merely path-SHAPED and cannot be placed SHALL be
recognised at LOW CONFIDENCE: no underline and no tooltip in ordinary reading, and reachable
only while the activation modifier is held.

Measured over the corpus: **395 distinct single-segment absolute tokens, 1 464 occurrences**
— web routes, this framework's own slash commands, component names — each one currently
underlined and each one answering *no such file or directory* when activated. The fail
direction is what makes this normative rather than cosmetic: an underline that fails teaches
the reader to distrust every underline on the screen, spending the credibility of the links
that do work.

The tier exists so that suppressing the noise does not also remove the capability. An
extensionless path outside every checkout — `/tmp`, `~/bin/mytool` — is a real path a reader
may want, and dropping it to satisfy the first rule would trade one silent loss for another.

A relative token that is not itself in a checkout's listing MAY be resolved by SUFFIX against
that listing, on a path boundary. Where EXACTLY ONE path ends with it, that file is what the
reference names. Where SEVERAL do, the framework SHALL offer the matches and let the reader
choose — it SHALL NOT pick one, because a wrong file that opens looks exactly like a right
one and nothing on screen says otherwise; and it SHALL NOT discard them, because that leaves
the reader with nothing when the framework knew several answers.

A relative token SHALL become a desktop reference only when it is shaped like a path and a
base is known. The shape test is what keeps prose out — a terminal is full of sentences, and
"contains a slash" alone would turn `and/or` and `24/7` into links that fail when activated.
Without a base there is nothing to resolve against, and resolving against a working directory
the reader cannot see would name a stranger's file.

#### Scenario: A relative path with a line number

- **WHEN** the output contains a project-relative path followed by a colon and a number
- **THEN** the terminal treats it as a reference to that file at that line

#### Scenario: An absolute path inside a checkout the framework may read

- **WHEN** the output contains an absolute path that lies inside any registered project or a
  worktree of one
- **THEN** it is treated as an internal reference to that file

#### Scenario: An absolute path under no known checkout

- **WHEN** the output contains an absolute path that lies under no registered project or
  worktree of one
- **THEN** it is recognised as a desktop reference — an agent commonly prints the path of
  what it produced, and it is often outside every registered tree

#### Scenario: A single-segment absolute token

- **WHEN** the output contains a token such as `/opsx:ff`, `/dd` or a web application's route
- **THEN** it carries no underline and no tooltip in ordinary reading — the reader sees prose

#### Scenario: A low-confidence token while the modifier is held

- **WHEN** a person holds the activation modifier over a path-shaped token the framework
  could not place
- **THEN** it becomes activatable, so an extensionless path outside every checkout is still
  reachable

#### Scenario: A token that is not path-shaped at all

- **WHEN** the token contains characters no path may carry here, such as a route parameter's
  brackets
- **THEN** it is left as ordinary text at any confidence, and no modifier makes it a link

#### Scenario: A path wrapped in markdown emphasis

- **WHEN** the output contains a path inside backticks, inside bold markers, or both
- **THEN** the markers are stripped and the path is recognised as if it had been written bare

#### Scenario: A path at the end of a table row

- **WHEN** the output contains `docs/x.md:12|` as a markdown table cell
- **THEN** the cell separator is stripped, and the reference is `docs/x.md` at line 12

#### Scenario: A home-relative path

- **WHEN** the output contains a token beginning with `~/`
- **THEN** it is resolved against the framework account's home directory and judged as an
  absolute path

#### Scenario: A relative token that uniquely suffixes one known file

- **WHEN** the output contains a relative token that no listing has as a whole path, and
  exactly one path in the checkout's listing ends with it on a path boundary
- **THEN** that file is what the reference names

#### Scenario: A relative token that suffixes more than one known file

- **WHEN** two or more paths in the listing end with the token and the reader activates it
- **THEN** the matches are offered for the reader to choose from, and none is opened until
  they do — no file is guessed at

#### Scenario: A relative directory

- **WHEN** the output contains a relative path that names a directory of a checkout the
  framework may read
- **THEN** it is recognised as an internal reference to that directory

#### Scenario: Prose that merely contains a slash

- **WHEN** the output contains a word such as `and/or` or `24/7`
- **THEN** it is left as ordinary text — an underline that fails when activated costs the
  reader's trust in every other underline on the screen

#### Scenario: A relative token with no project context

- **WHEN** a relative token appears in a terminal whose project root is not known
- **THEN** it is left as ordinary text

#### Scenario: A line, a token or a row count beyond the recogniser's limits

- **WHEN** a terminal row, a single token, or the number of references on one row exceeds the
  recogniser's stated limits
- **THEN** recognition stops for that row rather than degrading the terminal — an unbounded
  scan stutters exactly while an agent is producing output fastest, and a stuttering terminal
  is indistinguishable from a stalled agent

### Requirement: What the internal editor can open, opens in the internal editor

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

What the desktop gets is therefore exactly: a path under no registered project or worktree of
one.

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

### Requirement: Activating a desktop reference hands it to the desktop

A person activating a recognised DESKTOP reference SHALL cause that path to be handed to the
desktop's default application, through the framework's desktop-open capability and its
refusals. This change relaxes none of them and widens one — see `desktop-open`.

The dashboard SHALL NOT attempt to read or display such a path — the file endpoints refuse
everything outside a registered checkout, so pretending otherwise would produce a panel that
opens empty.

Activation SHALL require the same deliberate act as an internal reference, and no other: what
a plain click does in the terminal is unchanged.

#### Scenario: The reader activates an external path

- **WHEN** a person activates an absolute path under no registered project or worktree
- **THEN** the path is handed to the desktop, and nothing is opened inside the dashboard

#### Scenario: A plain click still belongs to the terminal

- **WHEN** a person clicks a recognised reference without the activation modifier
- **THEN** the click is the terminal's — focus, cursor, selection — and nothing opens

#### Scenario: The desktop guards refuse at least as much as before

- **WHEN** a desktop reference names something the desktop would run or interpret — an
  executable, a desktop entry, or a file whose association executes it despite carrying no
  executable bit
- **THEN** it is refused and nothing is started; this change widens that list and relaxes no
  part of it

## ADDED Requirements

### Requirement: Activating a directory reveals it in the structure pane

A person activating a reference to a DIRECTORY of a checkout the framework may read SHALL
have it revealed in the file view's structure pane — its ancestors expanded and the node
scrolled into view — rather than handed to a desktop file manager.

The structure pane is built from a listing of files, so a directory is not an entry that can
be looked up; the panel SHALL derive the node from the paths beneath it. A directory the
listing has nothing beneath SHALL be reported as such in the panel, never silently ignored:
an activation that appears to do nothing is indistinguishable from a broken control.

Measured over 30 session transcripts: **431 distinct directory tokens reached the desktop
route, 209 of them under a registered project root** — each one opening a file manager window
over the dashboard the reader was already looking at.

#### Scenario: A directory of the agent's checkout

- **WHEN** a person activates a relative path naming a directory of the checkout
- **THEN** the file view opens with that node expanded and scrolled into view, and no desktop
  application is launched

#### Scenario: A directory with nothing beneath it in the listing

- **WHEN** the activated directory has no files under it in the listing — because it is
  empty, or because the listing excludes what it holds
- **THEN** the panel says so where the reader is standing, and does not silently do nothing

#### Scenario: A directory under no known checkout

- **WHEN** the activated directory lies under no registered project or worktree
- **THEN** it is handed to the desktop, exactly as today
