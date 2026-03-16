## Context

Az orchestráció OpenSpec-et használ a change lifecycle-hoz (ff → apply → archive), de három ponton tér el a szabványos flow-tól:

1. **Proposal contamination**: a `dispatcher.py::_setup_change_in_worktree()` a scope-ot, memory context-et, sibling context-et és design token-eket a `proposal.md`-be írja. A proposal az agent munkája kellene legyen — az orchestráció injektált tartalma eltemeti az agent által írt szöveget és megakadályozza az auditálhatóságot.

2. **Archive git-staging bug**: `merger.py::archive_change()` `shutil.move()`-val mozgatja a könyvtárat, majd `git add <dest>`-et hív. A forrás törlése nincs stage-elve, ezért a commitban mindkét hely (forrás + archive) szerepel. Merge után a forrás visszakerül a worktree-k branch-jébe.

3. **Spec sync soha nem fut**: az orchestráció saját `archive_change()` funkciót használ az `openspec archive` CLI helyett. Az `openspec/specs/` könyvtár üres marad — a specs sosem kumulálódnak.

## Goals / Non-Goals

**Goals:**
- Dispatcher kontextus legyen külön `input.md` fájlban, `proposal.md` maradjon clean agent artifact
- `archive_change()` hívja az `openspec archive` CLI-t (spec sync-kel)
- Git-staging bug legyen javítva (forrás törlése is stage-elve)
- `/opsx:ff` skill `input.md`-t olvassa először (pre-read fázis)

**Non-Goals:**
- OpenSpec CLI módosítása (az orchestráció alkalmazkodik a CLI-hez)
- `/opsx:explore` bevezetése kötelező lépésként
- Más skill-ek (apply, verify, archive) módosítása

## Decisions

### D1: `input.md` helye és tartalma

`openspec/changes/<name>/input.md` — a change könyvtárban van, az archívával együtt utazik, gitbe kerül.

Tartalom:
```markdown
## Scope
<a change célja, amit a planner adott>

## Project Context
<memory recall eredménye>

## Sibling Changes
<párhuzamosan futó/nemrég mergelt changes>

## Design Context
<design tokens ha van>

## Retry Context  ← csak ha retry
<mi ment rosszul az előző futásnál>
```

**Miért nem `.claude/` alá?** Az input az OpenSpec change része — auditálható, reprodukálható. A `.claude/` ephemeral context, nem perzisztens artifact.

### D2: `proposal.md` tartalma

Az agent a `input.md`-t felhasználva írja — de a proposal a saját munkája marad. Nem másolja a kontextust, hanem szintetizálja:
- `## Why` — miért kell ez a change (scope + project context alapján)
- `## What Changes` — mit módosít
- `## Capabilities` — spec fájlok
- `## Impact` — érintett kód

### D3: ff skill pre-read fázis

Az ff skill 0. lépése az `input.md` elolvasása, majd az ebből következő kódbázis-fájlok azonosítása (pl. ha auth-ról szól → `middleware.ts`, `lib/auth.ts`, stb.). Ezután írja az artifactokat.

Ez **nem** külön explore iteráció — egy wt-loop iteráción belül történik.

### D4: archive_change() átírása

**Opció A** (választott): `merger.py::archive_change()` maga csinálja a javítást:
```python
shutil.move(change_dir, dest)
run_command(["git", "add", "-A", "openspec/changes/"])  # stage both add+delete
run_command(["git", "commit", ...])
# + spec sync: openspec archive <name> --skip-move (ha ilyen flag létezik)
```

**Opció B**: `merger.py` az `openspec archive` CLI-t hívja.

Preferált: **Opció A részlegesen** — a git bug fix mindenképpen szükséges, a spec sync-et az `openspec archive` CLI-vel csináljuk ha az támogatja a `--already-moved` vagy hasonló flag-et, különben implementáljuk Python-ban.

Ellenőrizni: `openspec archive --help` — ha van skip-move opció, azt használjuk. Ha nincs, a spec sync logikát implementáljuk a merger.py-ban.

## Risks / Trade-offs

- [Risk] `openspec archive` CLI esetleg nem támogat `--already-moved` flag-et → Mitigation: implementáljuk a spec sync-et Python-ban a merger.py-ban (az openspec specs könyvtárstruktúrája ismert)
- [Risk] `input.md` bevezetése után régi worktree-k (ahol nincs `input.md`) nem törnek el — az ff skill gracefully kezeli a hiányzó `input.md`-t
- [Risk] `git add -A openspec/changes/` más, folyamatban lévő change-ek fájljait is stage-elheti → Mitigation: csak a konkrét `change_dir` és `dest` path-okat add-oljuk

## Open Questions

- Az `openspec archive` CLI-nek van-e `--skip-move` vagy `--already-moved` flag-je? → implementáció előtt ellenőrizni
- Kell-e az `input.md`-t `.gitignore`-ba tenni a worktree-kben (ha a spec-context-hez hasonlóan kezeljük)? → Nem, az `input.md` auditálható artifact, gitbe kerül
