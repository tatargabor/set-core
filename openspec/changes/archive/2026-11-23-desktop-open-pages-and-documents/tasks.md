## 1. Guard (core: `lib/set_orch/api/desktop.py`)

- [x] 1.1 Retire the local-page refusal class and the `viewed` field [REQ: what-must-never-be-handed-over]
- [x] 1.2 Widen the executable-bit exception to the measured document and text suffixes [REQ: what-must-never-be-handed-over]
- [x] 1.3 Keep content-typed suffixes (`.jsonl`, `.toml`, `.ini`, none) and scripts under the bit [REQ: what-must-never-be-handed-over]

## 2. Routing (web)

- [x] 2.1 Binary documents join `MEDIA_SUFFIXES` in `web/src/lib/fleetFiles.ts`, equal to the server list [REQ: a-file-of-a-readable-checkout-opens-in-the-internal-editor]
- [x] 2.2 Drop the `viewed` flag from `FleetFileView` [REQ: what-must-never-be-handed-over]

## 3. Proof

- [x] 3.1 Tests: page handed over without any flag; 755 `.html`/`.docx` handed over on Linux; 755 `.jsonl`/`.sh`/no-suffix refused; macOS keeps the bit; parity test green
- [x] 3.2 Mutation: re-adding the page class, and dropping the new suffixes, each fail a test
- [x] 3.3 Rebuild `web/dist`, restart set-web, and open the refused HTML report live by Ctrl+click (visual check). Done 2026-10-23: the terminal header read "handed to the desktop: …/index.html" in green, and the server logged the hand-over.
