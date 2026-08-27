## MODIFIED Requirements

### Requirement: What must never be handed over

The endpoint SHALL refuse a path that the desktop would RUN rather than OPEN, and SHALL
refuse it before any handler is started. Refused are, at minimum:

- a path that is not absolute,
- a path that does not exist,
- a `.desktop` entry,
- any file carrying an executable bit,
- **any file whose type is one a desktop association commonly EXECUTES or interprets, whether
  or not it carries an executable bit.**

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
