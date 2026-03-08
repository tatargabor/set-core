## ADDED Requirements

### Requirement: MiniShop Express API scaffold

A `tests/e2e/scaffold/` könyvtár SHALL tartalmazzon egy működő, minimális Express.js webshop API projektet. A projekt az első `npm install && npm test` hívástól PASS-oló tesztekkel SHALL rendelkezzen.

#### Scenario: Scaffold tartalom

- **WHEN** a scaffold könyvtár tartalmát vizsgáljuk
- **THEN** az alábbi fájlok léteznek:
  - `package.json` — express, better-sqlite3, jest, supertest dependencies
  - `src/app.js` — Express app konfigurálás és exportálás (NEM hív `.listen()`-t)
  - `src/index.js` — Server entry point: `require('./app')` + `.listen()` (csak `require.main === module` esetén)
  - `src/db.js` — SQLite adatbázis init, `PRAGMA foreign_keys = ON`, tábla létrehozás, seed data
  - `src/routes/health.js` — `GET /api/health` endpoint
  - `src/middleware/errors.js` — global error handler `(err, req, res, next) => res.status(500).json({error: err.message})`
  - `tests/health.test.js` — health endpoint teszt (supertest-tel)
  - `jest.config.js` — Jest konfiguráció, `testEnvironment: 'node'`
  - `docs/v1-minishop.md` — orchestrator spec (az e2e-spec capability definiálja a tartalmát)
  - `.env.example` — `PORT=3000` és `JWT_SECRET=test-secret-change-me`
  - `.gitignore` — node_modules, *.sqlite, .env, stb
  - `CLAUDE.md` — agent instrukciók

### Requirement: App/Server szétválasztás

A `src/app.js` SHALL exportálja az Express app objektumot `.listen()` hívás nélkül. A `src/index.js` SHALL importálja és indítsa a szervert. Ez lehetővé teszi hogy supertest közvetlenül az app-ot tesztelje port foglalás nélkül.

#### Scenario: App exportálás

- **WHEN** `const app = require('./app')` hívjuk
- **THEN** egy Express app objektumot kapunk ami NEM hallgat semmilyen porton
- **THEN** a supertest `request(app).get('/api/health')` működik port nélkül

#### Scenario: Server indítás

- **WHEN** `node src/index.js`-t futtatunk
- **THEN** a szerver elindul a `PORT` env var-ban megadott porton (default 3000)
- **THEN** `GET /api/health` 200-as státuszt ad `{"status": "ok"}` body-val

### Requirement: SQLite adatbázis séma

A `src/db.js` SHALL inicializáljon egy SQLite adatbázist a következő táblákkal. A táblák az első szerver induláskor jönnek létre (CREATE IF NOT EXISTS). A `PRAGMA foreign_keys = ON` SHALL aktív legyen. Az adatbázis path a `DATABASE_PATH` env var-ból jön, default: `./minishop.db`.

NOTE: Mind az 5 tábla a scaffold-ban jön létre (nem az egyes change-ek adják hozzá), mert a FK constraint-ok az összes tábla létezését igénylik. Az auth change-nek NEM kell a `users` táblát létrehoznia — az már létezik.

#### Scenario: Alap tábla struktúra

- **WHEN** az adatbázis inicializálódik
- **THEN** `PRAGMA foreign_keys = ON` be van állítva
- **THEN** a `products` tábla létezik: `id` (INTEGER PRIMARY KEY), `name` (TEXT NOT NULL), `price` (REAL NOT NULL), `stock` (INTEGER DEFAULT 0), `created_at` (DATETIME DEFAULT CURRENT_TIMESTAMP)
- **THEN** a `cart_items` tábla létezik: `id` (INTEGER PRIMARY KEY), `session_id` (TEXT NOT NULL), `product_id` (INTEGER REFERENCES products(id)), `quantity` (INTEGER DEFAULT 1)
- **THEN** az `orders` tábla létezik: `id` (INTEGER PRIMARY KEY), `session_id` (TEXT), `total` (REAL), `status` (TEXT DEFAULT 'pending'), `created_at` (DATETIME DEFAULT CURRENT_TIMESTAMP)
- **THEN** az `order_items` tábla létezik: `id` (INTEGER PRIMARY KEY), `order_id` (INTEGER REFERENCES orders(id)), `product_id` (INTEGER REFERENCES products(id)), `quantity` (INTEGER), `price` (REAL)
- **THEN** a `users` tábla létezik: `id` (INTEGER PRIMARY KEY), `email` (TEXT UNIQUE NOT NULL), `password_hash` (TEXT NOT NULL), `created_at` (DATETIME DEFAULT CURRENT_TIMESTAMP)

#### Scenario: Seed data

- **WHEN** az adatbázis inicializálódik és a products tábla üres
- **THEN** 3 alap termék kerül bele:
  - "Laptop" — price: 299999, stock: 10
  - "Egér" — price: 4999, stock: 50
  - "Billentyűzet" — price: 12999, stock: 30

### Requirement: Package.json dependencies és scripts

A `package.json` SHALL tartalmazzon minden szükséges dependency-t és scriptet.

#### Scenario: Dependencies

- **WHEN** a package.json dependencies szekciót vizsgáljuk
- **THEN** `dependencies` tartalmazza: `express`, `better-sqlite3`, `cookie-parser`, `jsonwebtoken`, `bcryptjs`
- **THEN** `devDependencies` tartalmazza: `jest`, `supertest`

#### Scenario: Scripts

- **WHEN** a package.json scripts szekciót vizsgáljuk
- **THEN** `test` script létezik: `jest --forceExit --detectOpenHandles`
- **THEN** `start` script létezik: `node src/index.js`

### Requirement: Global error handler

A `src/middleware/errors.js` SHALL exportáljon egy Express error middleware-t ami elkapja a route-okban keletkező hibákat és 500-as JSON választ ad.

#### Scenario: Async hiba kezelés

- **WHEN** egy route handler-ben hiba keletkezik és `next(err)` hívódik
- **THEN** a middleware 500-as státuszt ad `{"error": "<hiba üzenet>"}` body-val
- **THEN** a request nem lóg — azonnal válaszol

### Requirement: CLAUDE.md a scaffold-ban

A scaffold SHALL tartalmazzon egy `CLAUDE.md` fájlt ami a projektnek megfelelő agent instrukciókat ad. A CLAUDE.md-nek elég részletesnek kell lennie hogy a Ralph agent konzisztens kódot produkáljon a 4 change alatt.

#### Scenario: CLAUDE.md tartalom

- **WHEN** a CLAUDE.md fájlt vizsgáljuk
- **THEN** tartalmazza a tech stack leírást (Express, better-sqlite3, Jest, supertest)
- **THEN** tartalmazza a test command-ot (`npm test`)
- **THEN** tartalmazza a fájl konvenciókat:
  - Route fájlok: `src/routes/<feature>.js` — Express Router exportálás
  - Tesztek: `tests/<feature>.test.js` — supertest-tel
  - Middleware: `src/middleware/<name>.js`
- **THEN** tartalmazza a DB access pattern-t: közvetlen `require('../db')` a route-okban, inline SQL, nincs service layer
- **THEN** tartalmazza az error handling konvenciót: `try/catch` + `next(err)` async route-okban
- **THEN** tartalmazza a session/cookie mechanizmust: `cookie-parser` middleware, session_id a `session_id` cookie-ból, ha nincs cookie akkor UUID generálás és set-cookie
- **THEN** tartalmazza az auth konvenciót CLEARLY MARKED `## Future: Auth (change 4)` szekció alatt: JWT token `Authorization: Bearer <token>` header-ben, `src/middleware/auth.js` exportálja az `authMiddleware`-t, védett route-ok `router.use(authMiddleware)` hívással. A szekció elején: "Do NOT implement auth until the auth change — this section describes conventions for when that change runs."
- **THEN** tartalmazza a .env kezelést: `process.env.PORT` (default 3000), `process.env.JWT_SECRET` (kötelező auth-hoz)

### Requirement: Jest konfiguráció

A `jest.config.js` SHALL explicit `testEnvironment: 'node'`-ot használjon — a jsdom default eltörné a better-sqlite3 native modult.

#### Scenario: Jest config tartalom

- **WHEN** a jest.config.js fájlt vizsgáljuk
- **THEN** `testEnvironment` értéke `'node'`
- **THEN** a konfiguráció működik better-sqlite3-al (native Node.js modulok támogatása)
