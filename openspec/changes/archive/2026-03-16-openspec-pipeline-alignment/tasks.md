## 1. dispatcher.py — input.md bevezetése

- [x] 1.1 Írj `_build_input_content()` függvényt a `dispatcher.py`-ban: scope, project knowledge, sibling context, design context, retry context szekciókkal — ez a jelenlegi `_build_proposal_content()` injektált részei
- [x] 1.2 `_setup_change_in_worktree()`-ban a `proposal.md` írása helyett hívd az `_build_input_content()`-et és írd az eredményt `input.md`-be (`openspec/changes/<name>/input.md`)
- [x] 1.3 A `proposal.md` pre-creation logikát (`if not os.path.isfile(proposal_path)`) távolítsd el — az agensre bízzuk
- [x] 1.4 A retry_context injektálást (`with open(proposal_path, "a")`) irányítsd át `input.md`-re, ne `proposal.md`-re

## 2. ff skill — pre-read fázis hozzáadása

- [x] 2.1 `.claude/skills/openspec-ff-change/SKILL.md`-ban add hozzá a 0. lépést: "Ha `input.md` létezik a change könyvtárban, olvasd el először. Azonosítsd a scope alapján a releváns kódbázis-fájlokat, és olvasd el azokat mielőtt bármilyen artifactot írsz."
- [x] 2.2 A step szöveg tartalmazza: ha `input.md` nem létezik, folytasd az artifact-írást a szokásos módon (CLAUDE.md + codebase exploration)

## 3. merger.py — archive_change() átírása openspec CLI-re

- [x] 3.1 `archive_change()`-ben távolítsd el a `shutil.move()`, `git add <dest>`, és `git commit` blokkot
- [x] 3.2 Cseréld le: `run_command(["openspec", "archive", change_name, "--yes"], timeout=60)` — ez kezeli a move-ot, spec sync-et, és git commit-ot
- [x] 3.3 Ha a CLI hibával tér vissza, logold warningként és `return False` (mint a jelenlegi kód)

## 4. Ellenőrzés

- [x] 4.1 `grep -n "proposal_path\|proposal.md" lib/set_orch/dispatcher.py` — nem marad write logika proposal.md-re
- [x] 4.2 `grep -n "shutil.move\|git add" lib/set_orch/merger.py` — a shutil.move és régi git add eltűnt, `openspec archive` van helyette
