## Context

The desktop guard (`desktop-open`) refuses any file with an executable bit because the text that
named it was written by whatever an agent ran, and a wrong open is a program starting. Its own
spec ranks the two failure directions: a refusal that lets a program through is a hole, one that
stops an ordinary file is an inconvenience. On a filesystem without Unix permissions the
inconvenience is total — every file is "executable" — so the bit carries no information there.

## Decisions

### D1. Lift the bit by SUFFIX, not by filesystem

Two ways to stop the false refusal:

- **by filesystem**: ignore the bit on exFAT/FAT/NTFS mounts. Covers every file type, but it also
  lifts the bit for an extensionless binary on such a drive, which is the case the bit exists for.
- **by suffix**: ignore the bit for a closed list of media suffixes, everywhere. An extensionless
  binary is still refused on every filesystem.

The suffix route is chosen. It is narrower, it needs no mount-table parsing, and it rests on a
measurement of the one question that matters — what the desktop does with such a file.

### D2. The measurement the list rests on

On the Linux desktop where the report came from, 2026-10-19, each suffix was tested with two
files given that name and mode 755: a copy of an ELF binary (`/bin/true`) and a `#!/bin/sh`
script. For every suffix both `xdg-mime query filetype` and `gio info -a standard::content-type`
returned the MEDIA type the suffix names (`video/mp4`, `image/png`, `application/pdf`, ...), never
an executable or script type, and `xdg-mime query default <type>` named a player, viewer or
editor (mpv, VLC, Totem, Rhythmbox, Audacity, Eye of GNOME, GIMP). No handler runs the file.
`xdg-open` reaches the handler through one of those two (`gio open`, or `xdg-mime` on a generic
session), so both were measured.

The list: `mp4 m4v mov mkv webm avi wmv mpg mpeg ogv 3gp flv` · `mp3 m4a aac wav flac ogg oga
opus wma` · `png jpg jpeg gif webp bmp avif tif tiff heic ico` · `pdf`.

**`.ts` was measured (`video/mpeg`) and is deliberately ABSENT**: in a code project it is
TypeScript, and routing it to a video player would make every TypeScript file unopenable in the
editor. `.svg` stays out too: it is already refused as a local page, and it is text the editor
opens.

### D3. macOS keeps the bit

Nothing was measured on macOS for this question, and the spec says an entry rests on a
measurement, never on plausibility. The lift applies where `_opener_name()` is `xdg-open`.

### D4. Two lists, held equal by a test

The routing list lives in the browser (`fleetFiles.ts`), the guard list on the server. A drift
fails safe in one direction only — a suffix the browser routes but the server does not lift is
refused when it carries the bit, never opened when it should not be. A unit test reads the
TypeScript constant and asserts it equals the Python tuple, so the drift cannot happen silently.

## Risks / Trade-offs

- [A media file the panel used to draw now opens outside the dashboard] → that is the request;
  the file view still draws an image opened from its own tree.
- [A desktop whose association for a media type is a program that executes its input] → none was
  found on the measured machine; the guard does not ask the local desktop (by design, so the same
  input gives the same verdict everywhere), so this rests on the measurement and is stated here.
