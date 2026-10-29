## Why

The board could show what an item waits on, but whoever was asked still had to answer somewhere
else (chat, mail), and a status could only change through an agent. The user asked (2026-10-29) for
the statuses to be settable on the page and for answer buttons on the waits: Igen/Nem, A/B/C, and
"Egyéb: ___" free text.

## What Changes

- **Status on the page.** The status pill becomes a select. A pick goes to `board/statuses`
  (`{item: {status, at}}`) and shows over the pushed status while it is newer than the item's last
  change, marked "set on the page".
- **Answers on the page.** A wait may carry `options` (`wait --options A,B`). In the "Waiting on
  people" panel each wait gets one button per option plus a free-text "Other" field. An answer goes
  to `board/answers` (`{"<item>|<ref or #index>": {answer, at}}`) and shows on the wait, with "change".
- **Back into the repository.** `import <job> --dir DIR` reads the two documents (ArtifactData output)
  and applies newer status picks as manual `set`s and newer answers as `answer`/`answered` on the
  wait. `answer <job> <item> [--ref] TEXT` records one by hand.
- **Page language.** `lang <job> hu` puts `lang` in the payload, and the page's own labels switch to
  Hungarian (status names, panel, "Egyéb", "Küldés"). The field is left out when unset, so other boards
  keep their hash.
- The page still never writes `board/state`.
