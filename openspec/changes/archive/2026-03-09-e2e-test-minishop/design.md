## Context

A set-core-nak nincs end-to-end tesztje ami a teljes pipeline-t (project init → spec → plan → dispatch → implement → smoke → merge → archive) futtatná valódi projekten. Az eddigi bugok (opsx:ff→apply chaining, smoke blocking gate, orchestrator kill nem öli gyerekprocesszt, state corruption) mind a komponensek közti interakcióból eredtek — amit unit tesztek nem fednek le.

A teszt egy MiniShop nevű minimális Express.js webshop API-t használ mint "áldozat projekt". A lényeg: a valódi set-core pipeline fut rajta, mock nélkül. Git tag-ekkel checkpoint-olunk, hogy javítás után visszatérhessünk.

Jelenlegi test infra: `tests/unit/` (bash), `tests/orchestrator/` (parse/state), `tests/*.py` (memory, compaction). Ezek maradnak — az e2e ezek fölötti réteg.

## Goals / Non-Goals

**Goals:**
- Működő MiniShop Express API scaffold ami az első `npm test`-től PASS-ol
- Orchestrator-kompatibilis spec (`docs/v1-minishop.md`) 4 change-dzsel és dependency gráffal
- Runner script ami a scaffold-ot friss git repo-ba másolja, `set-project init --project-type web`-et futtat, és git tag-ekkel checkpoint-ol
- A valódi sentinel → orchestrate → wt-loop pipeline tesztelhető rajta
- Kézi edge case injektálás lehetősége (smoke fail, merge conflict) menet közben

**Non-Goals:**
- CI integráció — kézi futtatás, nem automatizált
- Mock infra — nincs mock Claude, mock wt-loop, mock gnome-terminal
- Frontend — tisztán API, nincs UI
- Prod-grade kód a MiniShop-ban — minimális de működő, nem szép
- Automatizált szimuláció — edge case-eket kézzel injektáljuk menet közben

## Decisions

### D1: Express + better-sqlite3 + Jest stack

**Választás:** Express.js, better-sqlite3, Jest
**Alternatívák:** Fastify, SQLite via knex, Vitest
**Indoklás:** Express a legelterjedtebb — az orchestrator és a Ralph biztosan ismeri. better-sqlite3 zero-config, nincs szerver, a teszt bárhol fut. Jest mert a sales-raketa is azt használta és az orchestrator smoke_command-ja is `npm test`-et hív.

### D2: 4 change dependency gráffal

**Választás:**
```
products-crud (alap, nincs dependency)
    ↓
cart (depends: products-crud)
    ↓
orders (depends: cart, products-crud)

auth (cross-cutting, depends: products-crud, cart, orders — runs LAST)
```

**Indoklás:** Ez a minimális gráf ami teszteli: szekvenciális dispatch-ot (products előbb), párhuzamos lehetőséget (cart és auth egyszerre mehet miután products kész), és cross-cutting change-et (auth módosítja a korábbi route-okat). A sales-raketa gráf hasonló struktúrájú volt, csak nagyobb.

### D3: Valódi pipeline, nincs mock

**Választás:** A teljes set-sentinel → set-orchestrate → wt-loop pipeline fut valódi Claude hívásokkal
**Alternatíva:** Mock wt-loop fixture fájlokkal (PATH manipulation)
**Indoklás:** A production bugok a komponensek interakciójából erednek. Mock pont ezt rejti el. Token költség (~600K-1M/futás, ~$6-15) elhanyagolható a megelőzött production bugok költségéhez képest.

### D4: Git tag-alapú checkpoint-ok

**Választás:** Minden fázis után `git tag` a test projektben
**Séma:**
```
v0-scaffold        — friss projekt, npm test PASS
v1-initialized     — set-project init lefutott
v2-ready           — npm install kész, indulásra kész
v3-after-plan      — orchestrator plan elkészült (kézzel tag-eljük)
v4-after-products  — első change merge-ölve
...
```
**Checkpoint-ból folytatás sorrendje** (FONTOS — a sorrend számít!):
1. Fix set-core kódbázisban
2. Test projektben: `git worktree list` → `git worktree remove --force <wt>` mindegyikre
3. `git checkout -b resume-<tag> <tag>` (NEM detached HEAD-re!)
4. `set-project init` — EZUTÁN (a git checkout visszaállítja a .claude/-t, tehát utána kell redeploy)
5. `rm -f orchestration-state.json orchestration-plan.json`
6. Sentinel újraindítás

**Indoklás:** Egyszerűbb mint bármi más megoldás. A sorrend azért fontos mert `git checkout` visszaállítja a `.claude/` könyvtárat a tag állapotára — a `set-project init` utána kell hogy a frissített hook-ok/skill-ek deploy-olva legyenek.

### D5: A scaffold a tests/e2e/scaffold/ alatt él, fix path-ra másolva

**Választás:** `tests/e2e/scaffold/` template + runner ami `$TMPDIR/minishop-e2e/`-be másolja (fix path, nem timestamped)
**Alternatíva:** Külön git repo, timestamped temp dir
**Indoklás:** Fix path megoldja a set-project registry név-konfliktust (mindig ugyanaz a path) és a stale MCP regisztrációk felhalmozódását. Ha bug van, a dir megmarad vizsgálatra. Második futáshoz a meglévő dirt detektáljuk és folytatást ajánlunk.

### D6: Orchestrator spec formátum

**Választás:** A `docs/v1-minishop.md` a `sample-spec.md` formátumát követi — numbered sections, prioritás csoportok, fájl hivatkozások, Orchestrator Directives blokk
**Indoklás:** Az orchestrator planner Claude hívása ezt a formátumot ismeri. A spec-nek elég részletesnek kell lennie hogy a planner szétbontsa, de nem túl részletesnek hogy a Ralph-nak ne legyen mozgástere.

## Risks / Trade-offs

**[R1: Token költség]** → Futásonként ~$6-15. Mitigation: ritkán futtatjuk, nem CI. Megéri mert egy production bug ennek sokszorosába kerül.

**[R2: Claude output nem determinisztikus]** → Két futás különböző kódot produkál. Mitigation: a lényeg nem a kód minősége hanem a pipeline működése. Ha a smoke PASS-ol és a merge sikeres, a teszt PASS.

**[R3: Smoke fail ha a generált kód rossz]** → A Ralph rosszul implementál és a smoke fail-el. Mitigation: ez pont jó — teszteli a smoke recovery path-ot. Ha a Ralph 5 iteráción belül nem javítja, az bug amiért érdemes javítani.

**[R4: better-sqlite3 native dependency]** → Kompilálás kell, nem mindenhol megy. Mitigation: a dev gépen van C compiler, és ez a legegyszerűbb SQL opció. Fallback: `sql.js` (WASM, nincs native build) ha probléma van.

### D7: App/Server szétválasztás (supertest kompatibilitás)

**Választás:** `src/app.js` (Express app, exportálva, nincs `.listen()`) + `src/index.js` (server start, `require.main === module` guard)
**Alternatíva:** Egyetlen `index.js` ami exportál és listen-el is
**Indoklás:** supertest közvetlenül az app objektumot kéri, port nélkül. Ha a module-body-ban `.listen()` fut, Jest `--detectOpenHandles` warning-ot ad és port-leak-et okoz párhuzamos teszt futásnál.

### D8: Session mechanizmus (cookie-parser + UUID)

**Választás:** `cookie-parser` middleware, `session_id` cookie, UUID generálás ha nincs
**Alternatíva:** `express-session` (session store-ral), custom header
**Indoklás:** A legkönnyebb megoldás ami elegendő a cart + orders funkcionalitáshoz. Nem kell session store, nem kell server-side state — a session_id csak a cart_items tábla kulcsa. Az auth change-nél a JWT token lesz a fő azonosítás, a session_id megmarad a guest kosárhoz.

### D10: Auth deps és DB táblák pre-loaded a scaffold-ban

**Választás:** `jsonwebtoken`, `bcryptjs` deps és a `users` tábla a scaffold-ban vannak, nem az auth change adja hozzá
**Alternatíva:** Auth change add-olja a saját deps-eit és tábláját
**Indoklás:** (1) FK constraint-ok (order_items → products, cart_items → products) az összes tábla létezését igénylik — ha change-enként adnánk hozzá, ideiglenes FK hibák lennének. (2) Auth deps pre-loading megakadályozza hogy az auth Ralph-nak `npm install` kellessen mid-pipeline, ami merge conflict-ot okozhat package-lock.json-ban. A trade-off: a korábbi agentek látnak "unused" deps-eket, de a CLAUDE.md `## Future: Auth` szekció jelzi hogy nem kell használniuk.

### D9: Orchestration config explicit létrehozása

**Választás:** A runner script létrehozza a `wt/orchestration/config.yaml`-t explicit `smoke_command: npm test` és egyéb directives-szel
**Alternatíva:** A spec `## Orchestrator Directives` blokkjára hagyatkozni
**Indoklás:** A spec directives blokk a planner prompt-on keresztül érvényesül (nem garantált). A config.yaml direkt a shell kódból olvasódik — biztos hogy érvényesül. Mindkettőben megadjuk a redundancia kedvéért.
