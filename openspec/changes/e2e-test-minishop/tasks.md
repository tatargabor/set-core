## 1. Scaffold alap fájlok

- [x] 1.1 Create `tests/e2e/scaffold/package.json` — express, better-sqlite3, cookie-parser, jsonwebtoken, bcryptjs deps + jest, supertest devDeps + scripts (test, start)
- [x] 1.2 Create `tests/e2e/scaffold/src/app.js` — Express app config: json body parser, cookie-parser middleware, health route mount, error handler mount. Exportálja az app-ot `.listen()` nélkül
- [x] 1.3 Create `tests/e2e/scaffold/src/index.js` — `require('./app')` + `.listen(PORT)`, `require.main === module` guard
- [x] 1.4 Create `tests/e2e/scaffold/src/db.js` — better-sqlite3 init, `DATABASE_PATH` env var (default `./minishop.db`), `PRAGMA foreign_keys = ON`, CREATE IF NOT EXISTS mind az 5 táblára (products, cart_items, orders, order_items, users), seed 3 termék ha üres
- [x] 1.5 Create `tests/e2e/scaffold/src/routes/health.js` — Express Router, `GET /api/health` → `{"status": "ok"}`
- [x] 1.6 Create `tests/e2e/scaffold/src/middleware/errors.js` — global error handler `(err, req, res, next)` → 500 JSON

## 2. Scaffold teszt és config fájlok

- [x] 2.1 Create `tests/e2e/scaffold/tests/health.test.js` — supertest-tel: GET /api/health → 200, body.status === "ok"
- [x] 2.2 Create `tests/e2e/scaffold/jest.config.js` — `testEnvironment: 'node'`, `testMatch: ['**/tests/**/*.test.js']`
- [x] 2.3 Create `tests/e2e/scaffold/.gitignore` — node_modules, *.sqlite, .env, .claude/orchestration.log
- [x] 2.4 Create `tests/e2e/scaffold/.env.example` — PORT=3000, JWT_SECRET=test-secret-change-me, DATABASE_PATH=./minishop.db

## 3. CLAUDE.md és orchestrator spec

- [x] 3.1 Create `tests/e2e/scaffold/CLAUDE.md` — tech stack, test command, fájl konvenciók (routes, tests, middleware), DB access pattern (inline SQL, direct require, DATABASE_PATH env var), error handling (try/catch + next(err)), session mechanizmus (cookie-parser, session_id cookie, UUID). Auth konvenció `## Future: Auth (change 4)` szekció alatt — clearly marked "do NOT implement until auth change"
- [x] 3.2 Create `tests/e2e/scaffold/docs/v1-minishop.md` — orchestrator spec: v0 Status tábla (health ✅ Done), 4 numbered feature szekció (products-crud, cart, orders, auth), kebab-case `> depends_on:` hivatkozások, auth `depends_on: products-crud, cart, orders` (runs last), endpoint-ok, adatmodellek, elfogadási kritériumok, fájl hivatkozások, `## Orchestrator Directives` (H2!) blokk (max_parallel:2, smoke_command, smoke_blocking, test_command, merge_policy:checkpoint, auto_replan:true)

## 4. Runner script

- [x] 4.1 Create `tests/e2e/run.sh` — futtatható bash script: előfeltétel check (wt-project, node, npm, web project type), scaffold másolás `$TMPDIR/minishop-e2e/`-be (vagy megadott path), `cp .env.example .env`, git init + tag v0-scaffold, `wt-project init --name minishop-e2e --project-type web` + ellenőrzés, `wt/orchestration/config.yaml` létrehozás (smoke_command, test_command, max_parallel, merge_policy, smoke_blocking, auto_replan) — config.yaml BEFORE v1-initialized commit!, git add + commit + tag v1-initialized, npm install + npm test + git add + commit + tag v2-ready, sentinel indítási parancs kiírás
- [x] 4.2 Add meglévő dir detektálás a runner-be — ha target dir-ben van .git, ne inicializáljon újra, tag-eket és folytatási parancsot írjon ki
- [x] 4.3 Add név konfliktus kezelés — ha "minishop-e2e" más path-hoz regisztrálva, `wt-project remove minishop-e2e` futtatás az újra-regisztrálás előtt
- [x] 4.4 Add cleanup jelzés a runner végére — kiírja a test dir és registry cleanup parancsokat

## 5. Validálás

- [ ] 5.1 Scaffold teszt: másolás friss tmp dir-be, `npm install && npm test` — PASS kell legyen
- [x] 5.2 Runner teszt: `./tests/e2e/run.sh` futtatás, ellenőrzés hogy v0/v1/v2 tag-ek létrejöttek, .claude/ deployed, config.yaml létezik, npm test PASS
- [x] 5.3 Spec validálás: a `docs/v1-minishop.md` dependency gráf ellenőrzés — products-crud (no deps), cart (depends: products-crud), orders (depends: cart, products-crud), auth (depends: products-crud, cart, orders). Formátum megfelel a sample-spec.md konvenciónak, `## Orchestrator Directives` H2 heading
