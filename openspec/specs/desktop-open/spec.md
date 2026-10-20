# desktop-open Specification

## Purpose
TBD - created by archiving change fleet-open-external-path. Update Purpose after archive.

## Requirements

### Requirement: One path can be handed to the desktop

The framework SHALL provide an endpoint that hands a single absolute path to the desktop's
default application for that path, and SHALL do so only in answer to a request a person's
activation produced. Nothing SHALL be opened by the framework on its own initiative.

The path is opened on the machine the framework runs on, and the answer SHALL make that
plain rather than leaving the reader to infer it from a file appearing on the wrong screen.

#### Scenario: An existing file is handed over

- **WHEN** a person activates an absolute path naming an existing regular file
- **THEN** the framework asks the desktop to open it with its default application, and
  answers that it was handed over

#### Scenario: An existing directory is handed over

- **WHEN** the activated path names an existing directory
- **THEN** it is handed over the same way, and the desktop's file manager is what opens

#### Scenario: Nothing opens without an activation

- **WHEN** a path appears anywhere the framework can read — terminal output, a log, a file
- **THEN** nothing is opened until a person activates it

### Requirement: What must never be handed over

The endpoint SHALL refuse a path that the desktop would RUN rather than OPEN, and SHALL
refuse it before any handler is started. Refused are, at minimum:

- a path that is not absolute,
- a path that does not exist,
- a `.desktop` entry,
- a macOS `.app` bundle,
- a file whose association executes it or installs from it, including `.command`, `.terminal`
  and `.dmg` on macOS,
- any file carrying an executable bit — except, on a platform where it was measured, a file whose
  RESOLVED name ends in one of the media suffixes listed below,
- **any file whose type is one a desktop association commonly EXECUTES or interprets, whether
  or not it carries an executable bit.**

The media exception, and why it is safe: on a filesystem that stores no Unix permissions
(exFAT, FAT), every file reads as executable, so the bit refuses every file on such a drive and
says nothing about any of them. For the suffixes below the desktop chooses the handler by the
suffix — measured on Linux by giving a copy of an ELF binary and a shell script each suffix and
mode 755: both `xdg-mime` and `gio` typed every one as the media type, and every handler was a
player, viewer or editor. The suffixes are `.mp4 .m4v .mov .mkv .webm .avi .wmv .mpg .mpeg .ogv
.3gp .flv .mp3 .m4a .aac .wav .flac .ogg .oga .opus .wma .png .jpg .jpeg .gif .webp .bmp .avif
.tif .tiff .heic .ico .pdf`. The exception SHALL apply only on a platform where that measurement
was made — today Linux; on macOS the executable bit still refuses — and SHALL be judged on the
resolved target, like every other rule here, so a link named like a video that points at a
program is still refused.

The list SHALL be platform-complete for every platform the endpoint opens on, and each entry
SHALL rest on a measurement of what that platform's association actually does with the
suffix — never on plausibility. A suffix nothing is registered for on the measured machine
SHALL NOT be added on the strength of its name.

The reason this list exists is the direction it fails in: the text an activated path came
from was written by whatever an agent ran, so a wrong `open` is not a broken link, it is a
program starting. A refusal that lets one of these through is a hole; a refusal that stops an
ordinary file is an inconvenience. When the two are in tension the refusal wins.

**The permission bit is a proxy, and the thing itself is the file association.** Measured
2026-08-27 on a running desktop, with 644 files and no executable bit anywhere:

```
harmless.jar    refusal(): passes  →  handler: openjdk-7-java.desktop
harmless.py     refusal(): passes  →  handler: org.gnome.gedit.desktop
harmless.html   refusal(): passes  →  handler: google-chrome.desktop
```

A `.jar` is data by permission and a program by association: the desktop hands it to a JVM,
which runs it. The same holds for `.appimage`, `.run`, `.jnlp`, `.msi`, an installer package,
and a macro-carrying office document. An `.html` file is not executed but IS interpreted, at
a `file://` origin that can read local files — a different severity, the same class.

That the `.desktop` suffix was already refused by name shows the class was understood; the
list was one item long. This requirement widens the list and, more importantly, **states the
rule by the ACT rather than by the bit**, so a future reader extends the right thing.

The refusal's own wording SHALL name the reason it fired. *"Executable files are not
opened"*, said about a file with no executable bit, sends the reader to inspect permissions
that are not the cause.

The list SHALL be treated as a floor and never as proof of completeness. Desktop associations
are per-machine and per-user, so the framework cannot enumerate what a given desktop will
run. The refusals therefore fail toward not starting anything, and the endpoint SHALL NOT
attempt to decide by querying the local association — an answer that varies per machine would
make the guard untestable, and a guard that passes on the developer's machine and fails on
another is worse than a fixed list that is honest about being a floor.

#### Scenario: An executable file

- **WHEN** the activated path names a file with an executable bit set
- **THEN** it is refused, nothing is started, and the answer names the reason

#### Scenario: A desktop entry

- **WHEN** the activated path names a `.desktop` file
- **THEN** it is refused, whatever its permissions are

#### Scenario: An archive a runtime executes

- **WHEN** the activated path names a `.jar`, `.appimage`, `.run`, `.jnlp` or an installer
  package, with NO executable bit set
- **THEN** it is refused, and the reason names the association rather than the permissions

#### Scenario: A document that carries active content

- **WHEN** the activated path names an HTML file, or an office document of a macro-carrying
  format, with no executable bit set
- **THEN** it is refused — an HTML file opens at a `file://` origin that can read local
  files, and a macro document is a program its application is willing to run

#### Scenario: An ordinary file is still handed over

- **WHEN** the activated path names an image, a video, a PDF, a plain document or any other
  type not on the refusal list, with no executable bit
- **THEN** it is handed to the desktop exactly as before — the widening refuses more, and
  refuses nothing that was already working

#### Scenario: A path that is not there

- **WHEN** the activated path does not exist
- **THEN** it is refused with a reason naming that, and no handler is started

#### Scenario: A relative path

- **WHEN** the request carries a path that is not absolute
- **THEN** it is refused — the framework does not resolve it against a working directory the
  caller cannot see

#### Scenario: The refusal does not query the local desktop

- **WHEN** the endpoint decides whether to refuse a path
- **THEN** it decides from the path alone, and never from what this machine's associations
  happen to be — the same input gives the same verdict on every machine and in every test

#### Scenario: A file the desktop executes or installs from

- **WHEN** the activated path names a file whose association runs it or installs from it —
  `.command`, `.terminal` and `.dmg` among them
- **THEN** it is refused whatever its permissions say, and the reason names the association
  rather than the permissions

#### Scenario: A media file carrying an executable bit

- **WHEN** the activated path names a `.mp4` file whose mode is 755, on Linux
- **THEN** it is handed to the desktop

#### Scenario: A link named like a video that points at a program

- **WHEN** the activated path is a link named `clip.mp4` whose target is an executable with no
  media suffix
- **THEN** it is refused, and the reason names the executable bit

#### Scenario: The media exception is not taken on an unmeasured platform

- **WHEN** the activated path names a `.mp4` file whose mode is 755, on macOS
- **THEN** it is refused, and the reason names the executable bit

### Requirement: The endpoint reads nothing and persists nothing

The endpoint SHALL NOT read the content of the path it hands over, SHALL NOT copy it, and
SHALL NOT record it anywhere that outlives the request other than the framework's own
operational log. What it logs SHALL be the shape and the outcome — the path, whether it was
opened or refused, and the reason — and never file content.

#### Scenario: A file is opened

- **WHEN** a path is handed to the desktop
- **THEN** no content of that file is read by the framework and none is stored

### Requirement: A refusal is an answer, not a silence

Every outcome SHALL be reported to the caller: opened, or refused with a reason. A request
that fails because no desktop handler is available on this platform SHALL say so rather than
answering as if it had succeeded.

An opened-but-nothing-happened outcome is the failure this requirement exists to prevent: the
handler runs detached, so the endpoint answers on hand-over, and it SHALL NOT claim more than
that — it reports that the desktop was asked, never that a window appeared.

#### Scenario: No handler on this platform

- **WHEN** the machine has no desktop-open program available
- **THEN** the answer is a refusal naming that, not a success

#### Scenario: The answer is about hand-over

- **WHEN** the path is handed over successfully
- **THEN** the answer states that the desktop was asked to open it, and does not assert that
  an application window opened

### Requirement: The opener is the host platform's, not one platform's

The endpoint SHALL hand the path to the program that knows the file associations **of the
platform the framework is running on** — `open` on macOS, `xdg-open` on Linux and other
platforms — resolved on `PATH` at request time.

The endpoint SHALL NOT fall back from one platform's opener to another's. A platform whose
opener is absent SHALL be refused as it is today; a fallback would hand a path to a program
that means something different, and the refusal exists so that outcome is reported rather
than guessed at.

Choosing by platform is what makes the guard below meaningful: a refusal list is a claim about
what a *particular* desktop runs, so the platform that decides the opener and the platform
whose launcher classes are refused SHALL be the same one.

#### Scenario: A path is opened on macOS

- **WHEN** the framework runs on macOS and a person activates an absolute path naming an
  existing document
- **THEN** it is handed to `open`, and the answer states it was handed over

#### Scenario: A path is opened on Linux

- **WHEN** the framework runs on a non-macOS platform and a person activates such a path
- **THEN** it is handed to `xdg-open`, unchanged from before

#### Scenario: The platform's opener is missing

- **WHEN** the platform's own opener is not on `PATH`
- **THEN** the request is refused, the reason names **that platform's** opener, and no other
  program is tried

### Requirement: A macOS application bundle is a launcher, not a document

The endpoint SHALL refuse a path whose resolved target ends in `.app`, and SHALL do so by the
suffix rather than by any permission check.

This is stated separately because the general executable-bit rule cannot reach it: a `.app` is
a **directory**, and the bit rule deliberately exempts directories (every traversable directory
carries the bit, so a uniform check would refuse every folder). An application bundle is
therefore the one launcher class that a correct Linux-shaped guard waves through.

#### Scenario: An application bundle

- **WHEN** the activated path names a `.app` bundle
- **THEN** it is refused, nothing is started, and the reason says it is a launcher

#### Scenario: An ordinary directory still opens

- **WHEN** the activated path names a directory that is not a `.app`
- **THEN** it is handed over as before — refusing bundles SHALL NOT refuse folders

### Requirement: A local page is its own refusal class

The endpoint SHALL refuse a path whose resolved target is a document the desktop opens as a
**local page** — one a browser renders at a `file://` origin, with any script in it running.
At minimum `.html`, `.htm`, `.xhtml`, `.xht`, `.shtml`, `.mhtml`, `.svg` and `.svgz`.

The reason returned SHALL name what makes this class different from the run-or-install class,
because the two are refused for different facts and a reader sent to the wrong one inspects
the wrong thing. Nothing here is executed and nothing is installed: the file is *interpreted*,
by a program that can then read this machine's files.

Membership SHALL rest on what the desktop's association actually does with the suffix, never
on the suffix looking like markup. `.svg` is the worked example in both directions: it was
excluded on the stated ground that an image must keep opening, and it was added after a sweep
of one machine's association table showed every other handed-over suffix resolving to a viewer
or an editor while `.svg` and `.svgz` resolved to the browser. An SVG on that desktop is not
an image a viewer shows; it is a document a browser renders.

#### Scenario: A local page is refused by default

- **WHEN** a person activates an absolute path naming a local page
- **THEN** it is refused, nothing is started, and the reason says it opens as a local page that
  can read this machine's files

#### Scenario: A document format that a browser renders counts as one

- **WHEN** the activated path names an `.svg` or `.svgz`
- **THEN** it is refused as a local page, not handed over as an image

#### Scenario: A file the desktop merely displays or edits is not one

- **WHEN** the activated path names a document whose association opens a viewer or an editor —
  an image, a video, a PDF, a word-processor document, source text
- **THEN** it is handed over as before; this class SHALL NOT grow to cover anything a browser
  does not render

### Requirement: A caller may declare the page is already open, and that lifts this class alone

The request SHALL accept a field declaring that the reader has this very file open and pressed
a control whose only job is to hand it to the desktop. When it is set, the endpoint SHALL lift
the local-page refusal **and nothing else**: a launcher, a file whose association runs or
installs it, and a file carrying an executable bit SHALL be refused exactly as without it.

The endpoint SHALL NOT claim to verify the declaration — any caller can set it. What it rests
on is what every open here rests on, a person's activation; the difference the field carries is
that the person was looking at the file's contents rather than at a path some text named. A
route that only has the path SHALL NOT send it.

#### Scenario: The reader hands over a page they have open

- **WHEN** the field is set and the activated path names a local page
- **THEN** it is handed to the platform's opener, the same as any other document

#### Scenario: The declaration does not reach the other refusals

- **WHEN** the field is set and the activated path names a `.app` bundle, a file the
  association runs or installs from, or a file with an executable bit
- **THEN** it is refused exactly as it would be without the field

#### Scenario: A path that was only named is not a page the reader has open

- **WHEN** a path is activated from a surface that has the path and not the file's contents
- **THEN** the field is absent and the local-page refusal applies
