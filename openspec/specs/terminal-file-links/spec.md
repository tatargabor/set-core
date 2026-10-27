# Terminal File Links Specification

## Purpose

Owns the route from a file reference printed in terminal output to the file view: what
counts as a reference, how activating it opens the file at its line, how it stays
reachable while the agent holds the mouse, and that an external URL is left alone.

## IN SCOPE
- Recognising a file reference in an agent's terminal output, with an optional line number.
- Opening that file in the file view when a person activates the reference.
- A route to the same file that does not depend on the mouse reaching the terminal, because
  an agent's own program can be holding the mouse.
- What must not be treated as a link.

## OUT OF SCOPE
- External URLs in terminal output — already shipped, opening in a new tab, and untouched.
- What the file view does once the file is open (`fleet-file-view`).
- The endpoints (`project-file-access`).
- Rewriting, filtering or annotating the agent's output.
- References to files of a project other than the one the terminal's agent belongs to.

## Requirements

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

### Requirement: An external URL keeps its existing behaviour

Recognising file references SHALL NOT change what already happens to an external address in
terminal output: it opens in a new tab, and only schemes that cannot execute anything in the
dashboard's own origin are opened at all.

#### Scenario: A URL in the output

- **WHEN** the output contains an ordinary http or https address
- **THEN** it still opens in a new tab, and does not open in the file view

#### Scenario: A scheme that could execute something

- **WHEN** the output contains an address whose scheme could run code in the dashboard
- **THEN** it is not opened at all, exactly as before this change

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

### Requirement: A terminal token is recognised as an internal or a desktop reference

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

### Requirement: A desktop reference is handed to the desktop

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
