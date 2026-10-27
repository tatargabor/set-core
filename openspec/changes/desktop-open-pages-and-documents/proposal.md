## Why

Two reports on 2026-10-23, after Ctrl+click on paths an agent printed:

- A generated HTML report outside every project was refused: *"a .html file opens as a local
  page that can read this machine's files"*. The file view cannot reach it either (it is under
  no registered project), so the dashboard had **no way at all** to open it.
- The same file sat on an exFAT drive, where every file reads as mode 755. Had the page rule
  allowed it, the executable-bit rule would have refused it next. The bit exception covered
  media only, so on such a drive every document, sheet, text file and archive was refused for a
  permission the filesystem cannot store.

The owner decided (2026-10-23, asked with the trade-off stated): a person's Ctrl+click opens a
local page in the browser from the terminal too; files that RUN stay refused. Asked to think
through *which other files must work*, the answer is a measurement, not a list of names.

## What Changes

- **The local-page refusal class is retired.** `.html`, `.htm`, `.xhtml`, `.svg`, … are handed
  to the desktop on a person's activation, from any surface. The `viewed` request field, which
  existed only to lift that class, is removed — a field that changes no verdict is a false value.
- **The executable-bit exception is widened by measurement** (Linux only, as before), to every
  suffix the desktop typed by NAME in a sweep with an ELF binary and a shell script given the
  suffix and mode 755: office documents, e-books, archives, and plain-text formats.
- **Suffixes the desktop types by CONTENT stay under the bit**, and the measurement names them:
  `.jsonl`, `.toml`, `.ini` and a file with no suffix typed as `application/x-executable` when
  they held a binary. Script suffixes (`.sh`, `.py`, `.js`, …) also stay under it: there the bit
  is meaningful on an ordinary filesystem.
- **Binary documents route to the desktop from inside a checkout too**, like media: office
  documents, e-books and archives have no view in the editor.
- Launchers, run-or-install associations and macro-enabled office formats are unchanged.

## Capabilities

### Modified Capabilities

- `desktop-open`: page class retired; bit exception widened; `viewed` removed.
- `terminal-file-links`: binary documents join media on the desktop route inside a checkout.

## Impact

- `lib/set_orch/api/desktop.py` (core), `web/src/lib/fleetFiles.ts`,
  `web/src/components/FleetFileView.tsx`, their tests, `web/dist`.
