## Why

Az orchestráció jelenleg három ponton tér el a szabványos OpenSpec lifecycle-tól: (1) a dispatcher-injektált kontextus a `proposal.md`-be kerül ahelyett, hogy külön input fájlban lenne; (2) a `merger.py::archive_change()` nem futtatja az `openspec archive` CLI-t, így a spec sync soha nem történik meg és az `openspec/specs/` könyvtár üres marad; (3) a git-staging bug miatt az archivált change-ek az eredeti helyükön is megmaradnak. Ezek együtt azt okozzák, hogy az OpenSpec auditálhatósága és reprodukálhatósága nem működik.

## What Changes

- **`input.md` bevezetése**: a dispatcher az összegyűjtött kontextust (scope, project knowledge, sibling changes, design tokens, retry context) `openspec/changes/<name>/input.md` fájlba írja, nem a `proposal.md`-be; a `proposal.md` az agent eredménye marad
- **`/opsx:ff` pre-read fázis**: az ff skill első lépése az `input.md` elolvasása és a kapcsolódó kódbázis-fájlok azonosítása, mielőtt artifact-okat ír
- **`archive_change()` javítása**: a `merger.py` az `openspec archive` CLI parancsot hívja (spec sync-kel), és javítja a git-staging bug-ot (forrás törlésének stage-elése)

## Capabilities

### New Capabilities
- `dispatch-input-context`: az orchestráció dispatch fázisában az agent számára szánt indítókontextus strukturált MD fájlként kerül a change könyvtárba, és a ff skill ebből dolgozik

### Modified Capabilities
- `merge-worktree`: az archive pipeline kiegészül spec sync-kel és a git-staging helyesen stage-eli a forrás törlését is

## Impact

- `lib/set_orch/dispatcher.py`: `_setup_change_in_worktree()`, `_build_proposal_content()` — input.md írás
- `lib/set_orch/merger.py`: `archive_change()` — git fix + spec sync hívás
- `.claude/skills/openspec-ff-change/SKILL.md` — pre-read fázis hozzáadása
- Worktree-k: `openspec/changes/<name>/input.md` új fájl (gitignore-ba NEM kerül — archívával együtt utazik)
