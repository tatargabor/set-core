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
  RESOLVED name ends in one of the media suffixes listed below.

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

#### Scenario: An executable file

- **WHEN** the activated path names a file with an executable bit set
- **THEN** it is refused, nothing is started, and the answer names the reason

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

#### Scenario: A desktop entry

- **WHEN** the activated path names a `.desktop` file
- **THEN** it is refused, whatever its permissions are

#### Scenario: A file the desktop executes or installs from

- **WHEN** the activated path names a file whose association runs it or installs from it —
  `.command`, `.terminal` and `.dmg` among them
- **THEN** it is refused whatever its permissions say, and the reason names the association
  rather than the permissions

#### Scenario: A path that is not there

- **WHEN** the activated path does not exist
- **THEN** it is refused with a reason naming that, and no handler is started

#### Scenario: A relative path

- **WHEN** the request carries a path that is not absolute
- **THEN** it is refused — the framework does not resolve it against a working directory the
  caller cannot see
