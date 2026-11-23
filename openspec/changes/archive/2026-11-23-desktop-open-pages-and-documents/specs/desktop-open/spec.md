## MODIFIED Requirements

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
  RESOLVED name ends in one of the media or document suffixes listed below,
- **any file whose type is one a desktop association commonly EXECUTES or interprets, whether
  or not it carries an executable bit.**

The media exception, and why it is safe: on a filesystem that stores no Unix permissions
(exFAT, FAT), every file reads as executable, so the bit refuses every file on such a drive and
says nothing about any of them. For the suffixes below the desktop chooses the handler by the
suffix — measured on Linux by giving a copy of an ELF binary and a shell script each suffix and
mode 755: both `xdg-mime` and `gio` typed every one as the media type, and every handler was a
player, viewer or editor. The suffixes are `.mp4 .m4v .mov .mkv .webm .avi .wmv .mpg .mpeg .ogv
.3gp .flv .mp3 .m4a .aac .wav .flac .ogg .oga .opus .wma .png .jpg .jpeg .gif .webp .bmp .avif
.tif .tiff .heic .ico .pdf`.

The same measurement, repeated on 2026-10-23 for documents, widens the exception to the suffixes
the desktop also typed by NAME: office documents and e-books `.docx .xlsx .pptx .odt .ods .odp
.rtf .epub`, archives `.zip .tar .gz .7z`, and text formats `.html .htm .xhtml .xml .json .svg
.txt .md .csv .tsv .log .srt .vtt .yaml .yml`. Suffixes the desktop typed by CONTENT SHALL stay
under the bit — measured: `.jsonl`, `.toml`, `.ini` and a name with no suffix were typed
`application/x-executable` when they held a binary. Script suffixes (`.sh .py .pl .rb .php .js
.mjs`) SHALL stay under it too: on an ordinary filesystem the bit on a script means what it
says. Legacy `.doc .xls .ppt` are left out: those formats can carry macros.

The exception SHALL apply only on a platform where that measurement
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
and a macro-carrying office document. An `.html` file is not executed but IS interpreted; it
was refused as its own class until 2026-10-23, when the owner decided a person's activation
opens it (see the removed local-page requirement).

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

- **WHEN** the activated path names an office document of a macro-carrying format, with no
  executable bit set
- **THEN** it is refused — a macro document is a program its application is willing to run

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

#### Scenario: A document on a drive without Unix permissions

- **WHEN** the activated path names a `.html`, `.docx` or `.zip` file whose mode is 755, on Linux
- **THEN** it is handed to the desktop

#### Scenario: A content-typed suffix keeps the bit

- **WHEN** the activated path names a `.jsonl` file, or a file with no suffix, whose mode is 755
- **THEN** it is refused, and the reason names the executable bit — the desktop types such a
  file by its content, so a binary given that name is typed as a program

#### Scenario: A script keeps the bit

- **WHEN** the activated path names a `.sh` file whose mode is 755, on Linux
- **THEN** it is refused, and the reason names the executable bit

#### Scenario: A local page is handed over

- **WHEN** a person activates an absolute path naming a `.html` or `.svg` file with no
  executable bit, from any surface
- **THEN** it is handed to the platform's opener

#### Scenario: The media exception is not taken on an unmeasured platform

- **WHEN** the activated path names a `.mp4` file whose mode is 755, on macOS
- **THEN** it is refused, and the reason names the executable bit

## REMOVED Requirements

### Requirement: A local page is its own refusal class

**Reason**: The owner decided on 2026-10-23 that a person's Ctrl+click opens a local page in the
browser, from the terminal as well as from the file view. With no route that refuses it, the
class only produced a dead end: a page outside every project could not be opened at all.

**Migration**: None. Pages are handed over like any other document; the launcher,
run-or-install and executable-bit refusals are unchanged.

### Requirement: A caller may declare the page is already open, and that lifts this class alone

**Reason**: The field existed only to lift the local-page class, which is removed. Kept, it would
be a field that changes no verdict.

**Migration**: Callers stop sending `viewed`; an old caller that still sends it is unaffected
(the request model ignores unknown fields).
