## ADDED Requirements

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
