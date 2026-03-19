## ADDED Requirements

### Requirement: E2E runner script

A `tests/e2e/run.sh` SHALL legyen egy futtatható bash script ami a MiniShop scaffold-ot friss git repo-ba másolja, felkészíti a sentinel futtatásra, és git tag-ekkel checkpoint-ol.

#### Scenario: Előfeltétel ellenőrzés

- **WHEN** a runner script elindul
- **THEN** ellenőrzi hogy `set-project` elérhető a PATH-ban
- **THEN** ellenőrzi hogy `set-project list-types` tartalmazza a `web` típust
- **THEN** ellenőrzi hogy `node` és `npm` elérhető
- **THEN** ha bármelyik hiányzik, hibaüzenettel megáll

#### Scenario: Új teszt projekt inicializálás

- **WHEN** `./tests/e2e/run.sh` futtatjuk argumentum nélkül
- **THEN** létrehoz egy `$TMPDIR/minishop-e2e/` könyvtárat (fix path, nem timestamped)
- **THEN** bemásolja a scaffold fájlokat
- **THEN** `cd` a test könyvtárba (minden további parancs onnan fut)
- **THEN** `git init` + initial commit
- **THEN** `git tag v0-scaffold`
- **THEN** `set-project init --name minishop-e2e --project-type web` futtat
- **THEN** ellenőrzi hogy `.claude/` könyvtár létrejött
- **THEN** `git add -A && git commit` + `git tag v1-initialized`
- **THEN** `npm install` futtat
- **THEN** `npm test` futtat és ellenőrzi hogy PASS
- **THEN** `git add -A && git commit` + `git tag v2-ready`
- **THEN** kiírja a könyvtár elérési útját
- **THEN** kiírja a sentinel indítási parancsot: `cd $TMPDIR/minishop-e2e && set-sentinel --spec docs/v1-minishop.md`

#### Scenario: Megadott könyvtárba inicializálás

- **WHEN** `./tests/e2e/run.sh /path/to/dir` futtatjuk
- **THEN** a megadott könyvtárba inicializál (nem $TMPDIR/minishop-e2e-be)

#### Scenario: Meglévő teszt projekt folytatás

- **WHEN** `./tests/e2e/run.sh` (vagy explicit path-szal) futtatjuk és a target könyvtár már inicializált (van .git)
- **THEN** NEM inicializál újra
- **THEN** kiírja a meglévő git tag-eket
- **THEN** kiírja a folytatási parancsot

#### Scenario: set-project init hiba kezelés

- **WHEN** a `set-project init` parancs hibával tér vissza
- **THEN** a script hibaüzenettel megáll (nem folytatja npm install-lal)
- **THEN** a könyvtár megmarad vizsgálatra

### Requirement: Név konfliktus kezelés

A runner SHALL kezelje azt az esetet amikor a "minishop-e2e" projekt név már regisztrálva van más path-szal a set-project registryben.

#### Scenario: Régi regisztráció cleanup

- **WHEN** a runner inicializálna de "minishop-e2e" már más path-hoz van regisztrálva
- **THEN** `set-project remove minishop-e2e`-t futtat a régi regisztráció eltávolítására
- **THEN** folytatja az inicializálást normálisan

### Requirement: Git checkpoint rendszer

A runner script SHALL git tag-eket használjon minden fázis után, hogy javítás után visszatérhessünk egy korábbi állapotba.

#### Scenario: Tag konvenció

- **WHEN** a runner végigfut
- **THEN** a következő tag-ek jönnek létre:
  - `v0-scaffold` — friss scaffold, git init után
  - `v1-initialized` — set-project init lefutott
  - `v2-ready` — npm install kész, tesztek futnak

#### Scenario: Checkpoint-ból folytatás workflow (kézi, nem automatizált)

- **WHEN** a fejlesztő bugot talál a pipeline-ban és kézzel akar folytatni
- **THEN** a helyes sorrend:
  1. Javítás a set-core kódbázisban
  2. A test projektben: worktree cleanup (`git worktree list` → `git worktree remove --force <wt>` mindegyikre)
  3. `git checkout -b resume-<tag> <tag>` (NEM detached HEAD!)
  4. `set-project init --name minishop-e2e --project-type web` — EZUTÁN, nem előtte (mert a git checkout visszaállítja a .claude/-t)
  5. Orchestration state cleanup: `rm -f orchestration-state.json orchestration-plan.json`
  6. Sentinel újraindítás

### Requirement: Orchestration config létrehozás

A runner SHALL létrehozza a `wt/orchestration/config.yaml` fájlt a szükséges directives-szel a `set-project init` UTÁN.

#### Scenario: Config tartalom

- **WHEN** a runner létrehozza a config.yaml-t
- **THEN** tartalmazza:
  - `smoke_command: npm test`
  - `smoke_blocking: true`
  - `test_command: npm test`
  - `max_parallel: 2`
  - `merge_policy: checkpoint`
  - `auto_replan: true`
- **THEN** a fájl létrehozása MEGELŐZI a v1-initialized git commit-ot és tag-et

### Requirement: MCP cleanup

A runner SHALL figyelmeztessen a stale MCP regisztrációkra ha azok felhalmozódnának.

#### Scenario: Cleanup jelzés

- **WHEN** a teszt véget ér (sikeres vagy kézi leállítás)
- **THEN** a script kiírja: "Test dir: $TMPDIR/minishop-e2e — delete with: rm -rf $TMPDIR/minishop-e2e"
- **THEN** kiírja: "Registry cleanup: set-project remove minishop-e2e"

### Requirement: .env fájl létrehozás

A runner SHALL másolja a `.env.example`-t `.env`-be ha az még nem létezik — biztosítva hogy `JWT_SECRET` és más env var-ok elérhetőek legyenek az auth change futásakor.

#### Scenario: .env másolás

- **WHEN** a runner a scaffold-ot bemásolta és `.env` nem létezik
- **THEN** `cp .env.example .env` futtatódik
- **THEN** a `.env` a `.gitignore`-ban van (nem commitolódik)

### Requirement: Sikertelen futás kezelés

#### Scenario: Sikertelen futás utáni állapot

- **WHEN** a runner script bármely lépésben hibával megáll
- **THEN** a könyvtár és az eddig létrehozott git history megmarad
- **THEN** a script kiírja melyik lépésnél állt meg és a könyvtár elérési útját
