## Context

The desktop-open guard refuses by the ACT: a path may be opened, never run. Two of its rules
were proxies that misfired on 2026-10-23: the local-page class (refusing a page a person
deliberately activated) and the executable bit (refusing everything on a filesystem without
Unix permissions).

## Decisions

### D1 — A local page opens on a person's activation

Owner's decision, 2026-10-23, chosen over "lift only the bit" and "leave it": Ctrl+click on a
`.html` in the terminal opens it in the browser. The class was introduced because a page is
*interpreted* at a `file://` origin; what bounds that now is the browser's own `file://`
isolation and the person's click, which is what every other open here rests on. The `viewed`
field existed only to lift this class, so it goes with it rather than staying as a field that
changes no verdict.

### D2 — The bit exception is widened by measurement, not by name

Same method as the media exception: for each candidate suffix, a copy of `/bin/true` and a
`#!/bin/sh` script, mode 755; `xdg-mime query filetype`, `gio info -a standard::content-type`,
and `xdg-mime query default`. Measured 2026-10-23 on Linux (GNOME):

| typed by suffix (both probes) → lifted | handler class |
|---|---|
| `.docx .xlsx .pptx .odt .ods .odp .rtf` | office suite |
| `.epub` | (none registered; typed by suffix) |
| `.zip .tar .gz .7z` | archive manager |
| `.html .htm .xhtml .xml .json` | browser |
| `.svg` | image editor |
| `.txt .md .csv .tsv .log .srt .vtt .yaml .yml` | editor / spreadsheet / none |

| typed by CONTENT → stays under the bit |
|---|
| `.jsonl .toml .ini`, no suffix → `application/x-executable` (ELF), `application/x-shellscript` (script) |

Scripts (`.sh .py .pl .rb .php .js .mjs`) were typed by suffix but are left under the bit: on an
ordinary filesystem the bit on a script is meaningful, and inside a checkout they open in the
file view, which never consults it. Legacy `.doc .xls .ppt` typed by suffix too, but are left
out: unlike `.docx`, those formats can carry macros, and nothing measured what the office
suite does with one.

### D3 — Binary documents join media on the desktop route

The file view is an editor and has no view for an office document, an e-book or an archive;
routing them there first ends in "cannot show". They join the browser's `MEDIA_SUFFIXES`, which
the existing parity test holds equal to the server's list. Text formats (including `.html`)
keep opening in the file view inside a checkout — it can show and edit them, and its own
desktop button still hands them over.

## Risks

- A page opened from agent-printed text runs its script in the browser at a `file://` origin.
  Accepted by the owner; mainstream browsers isolate `file://` documents from each other.
