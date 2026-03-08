## ADDED Requirements

### Requirement: Orchestrator-kompatibilis spec dokumentum

A `tests/e2e/scaffold/docs/v1-minishop.md` SHALL tartalmazzon egy orchestrator-kompatibilis specifikációt ami 4 change-re bontható szét. A formátum a `tests/orchestrator/sample-spec.md` konvenciót SHALL követi: numbered sections, prioritás csoportok, `## Orchestrator Directives` (H2!) záró blokk.

#### Scenario: Spec struktúra

- **WHEN** a v1-minishop.md fájlt vizsgáljuk
- **THEN** tartalmaz egy v0 Status táblát ami a health endpoint-ot mint "✅ Done" feature-t listázza
- **THEN** tartalmaz numbered feature szekciók-at a következő change-ekhez:
  1. Products CRUD (`products-crud`) — alap, nincs dependency
  2. Cart kezelés (`cart`) — `depends_on: products-crud`
  3. Orders kezelés (`orders`) — `depends_on: cart, products-crud`
  4. Auth / JWT (`auth`) — `depends_on: products-crud, cart, orders` (cross-cutting, MUST run last)
- **THEN** minden szekció tartalmaz: endpoint-okat, adatmodell leírást, elfogadási kritériumokat, és érintett fájlokat
- **THEN** egy `## Orchestrator Directives` (H2 heading!) záró blokkot tartalmaz

NOTE: A dependency hivatkozások a kebab-case change neveket MUST használják — nem a human-readable neveket. A planner ezeket fordítás nélkül átveszi a `depends_on` mezőbe. A formátum egy bullet a feature szekció elején:
```
> depends_on: products-crud, cart
```

#### Scenario: Products CRUD szekció

- **WHEN** a Products CRUD szekciót vizsgáljuk
- **THEN** definiálja a `GET /api/products`, `GET /api/products/:id`, `POST /api/products`, `PUT /api/products/:id`, `DELETE /api/products/:id` endpoint-okat
- **THEN** hivatkozik a `src/routes/products.js` és `tests/products.test.js` fájlokra
- **THEN** nincs dependency más feature-re
- **THEN** elfogadási kritérium: `npm test` PASS-ol a products tesztekkel

#### Scenario: Cart szekció dependency-vel

- **WHEN** a Cart szekciót vizsgáljuk
- **THEN** explicit dependency: `depends_on: products-crud`
- **THEN** definiálja a `GET /api/cart`, `POST /api/cart`, `DELETE /api/cart/:id` endpoint-okat
- **THEN** leírja hogy a session_id a `session_id` cookie-ból jön (cookie-parser middleware)
- **THEN** hivatkozik a `src/routes/cart.js` és `tests/cart.test.js` fájlokra

#### Scenario: Orders szekció multiple dependency

- **WHEN** az Orders szekciót vizsgáljuk
- **THEN** explicit dependency: `depends_on: cart, products-crud`
- **THEN** definiálja a `POST /api/orders` (kosár → rendelés konverzió) és `GET /api/orders` endpoint-okat
- **THEN** leírja a stock csökkentés logikát rendeléskor (tranzakcióban)
- **THEN** hivatkozik a `src/routes/orders.js` és `tests/orders.test.js` fájlokra

#### Scenario: Auth szekció cross-cutting

- **WHEN** az Auth szekciót vizsgáljuk
- **THEN** explicit dependency: `depends_on: products-crud, cart, orders` (futtatás utolsónak — módosítja a meglévő route-okat)
- **THEN** megjegyzi: "Cross-cutting: adds auth middleware to existing routes. Runs last because it modifies routes created by earlier changes. NOTE: scope overlap warnings are expected and intentional."
- **THEN** definiálja: `POST /api/register`, `POST /api/login` endpoint-okat
- **THEN** leírja a JWT middleware-t (`src/middleware/auth.js`) és a védett route-ok koncepcióját (POST/PUT/DELETE protected, GET public)
- **THEN** hivatkozik: `src/routes/auth.js`, `src/middleware/auth.js`, `tests/auth.test.js`

#### Scenario: Orchestrator Directives blokk

- **WHEN** az `## Orchestrator Directives` blokkot vizsgáljuk (MUST be H2 heading — `##` not `###`)
- **THEN** tartalmazza:
  - `max_parallel: 2`
  - `smoke_command: npm test`
  - `smoke_blocking: true`
  - `test_command: npm test`
  - `merge_policy: checkpoint`
  - `auto_replan: true`

### Requirement: Dependency gráf az orchestrator számára

A spec MUST tartalmazzon elég információt ahhoz, hogy az orchestrator planner felismerje a dependency-ket és helyes sorrendben dispatch-olja a change-eket. A dependency-k kebab-case change neveket használnak.

#### Scenario: Helyes dispatch sorrend

- **WHEN** az orchestrator a spec-et feldolgozza
- **THEN** a `products-crud` change-et először dispatch-olja (nincs dependency)
- **THEN** a `cart` change-et csak `products-crud` UTÁN dispatch-olja
- **THEN** az `orders` change-et csak `cart` ÉS `products-crud` UTÁN dispatch-olja
- **THEN** az `auth` change-et UTOLSÓNAK dispatch-olja (miután products-crud, cart, orders mind kész)

#### Scenario: Szekvenciális dispatch (cross-cutting auth miatt)

- **WHEN** `products-crud` elkészült és `max_parallel: 2`
- **THEN** `cart` dispatch-olható (orders megvárja cart-ot)
- **THEN** `auth` NEM dispatch-olható párhuzamosan más change-dzsel — megvárja hogy products-crud, cart, orders mind kész legyen
