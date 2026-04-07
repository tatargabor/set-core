---
marp: true
theme: default
paginate: true
backgroundColor: #0f172a
color: #e2e8f0
style: |
  section {
    font-family: 'Inter', 'Segoe UI', sans-serif;
    background-color: #0f172a;
    color: #e2e8f0;
  }
  h1 {
    color: #38bdf8;
    font-size: 2.2em;
    border-bottom: 2px solid #1e3a5f;
    padding-bottom: 0.3em;
  }
  h2 {
    color: #7dd3fc;
    font-size: 1.6em;
  }
  h3 {
    color: #93c5fd;
  }
  strong {
    color: #fbbf24;
  }
  code {
    background-color: #1e293b;
    color: #a5f3fc;
    padding: 2px 6px;
    border-radius: 4px;
  }
  pre {
    background-color: #1e293b !important;
    border: 1px solid #334155;
    border-radius: 8px;
  }
  table {
    font-size: 0.85em;
  }
  table th {
    background-color: #1e3a5f;
    color: #7dd3fc;
  }
  table td {
    background-color: #1e293b;
    border-color: #334155;
  }
  blockquote {
    border-left: 4px solid #fbbf24;
    background-color: #1e293b;
    padding: 0.5em 1em;
    border-radius: 0 8px 8px 0;
  }
  img {
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  }
  a {
    color: #38bdf8;
  }
  .hero {
    text-align: center;
  }
  .metric-box {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    display: inline-block;
    margin: 8px;
  }
  .metric-value {
    font-size: 2em;
    color: #fbbf24;
    font-weight: bold;
  }
  .metric-label {
    font-size: 0.8em;
    color: #94a3b8;
  }
  section.title-slide {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
  }
  section.title-slide h1 {
    font-size: 3em;
    border: none;
  }
  section.section-divider {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
  }
  section.section-divider h1 {
    font-size: 2.5em;
    border: none;
  }
  footer {
    color: #475569;
    font-size: 0.7em;
  }
---

<!-- _class: title-slide -->
<!-- _footer: "" -->

# SET

**Autonóm multi-agent orkesztrálás Claude Code-dal**

Adj neki egy spec-et -- kapsz mergelt feature-öket.

*2026. április*

<!-- SPEAKER_NOTES:
Üdvözlés, bemutatkozás. A SET egy keretrendszer, ami markdown specifikációból
kiindulva párhuzamos AI ágensekkel épít működő alkalmazásokat.
Ma egy valós E2E teszten keresztül mutatom be a teljes működést.
-->

---

# Az előadás menete

| Idő | Téma |
|-----|------|
| 5 perc | **A probléma** -- Miért nem elég a "prompt and pray"? |
| 5 perc | **A bemenet** -- Spec + Design = minőségi input |
| 20 perc | **E2E Demo: MiniShop** -- A teljes pipeline végigvezetése |
| 10 perc | **Quality Gates** -- Determinisztikus minőségbiztosítás |
| 5 perc | **Dashboard & Monitoring** -- Valós idejű felügyelet |
| 5 perc | **Architektúra** -- 3 réteg, plugin rendszer |
| 5 perc | **Tanulságok** -- 30+ futtatás tapasztalatai |
| 5 perc | **Roadmap** -- Hová tartunk |

<!-- SPEAKER_NOTES:
Az előadás gerince a MiniShop E2E demo lesz -- egy valós webshop felépítése
specifikációból, nulla emberi beavatkozással. Ezen keresztül mutatom be
az összes komponenst.
-->

---

<!-- _class: section-divider -->

# 1. A probléma

*Miért nem elég promptolni?*

---

# AI kódolás ma -- a kihívások

| Probléma | Tipikus megoldás | Eredmény |
|----------|-----------------|----------|
| **Divergencia** | Prompt 2x futtatás = 2 különböző eredmény | Nem reprodukálható |
| **Hallucináció** | Ágensek kitalálják, amit nem tudnak | Hiányzó funkciók |
| **Minőség-rulett** | LLM ítéli meg a kód minőségét | Inkonzisztens |
| **Spec drift** | "Tesztek futnak" != "spec teljesül" | Részleges implementáció |
| **Amnézia** | Minden session nulláról indul | Ismétlődő hibák |
| **Hibajavítás** | Kézi debugging, órák | Elveszett idő |

> A legtöbb AI kódolóeszköz **nem-determinisztikus** -- ugyanaz a prompt, más eredmény.
> A SET ezt mérnöki problémaként kezeli.

<!-- SPEAKER_NOTES:
Ez nem elméleti probléma. A CraftBrew korai futtatásaiban 3 különböző ágens
3 különböző táblázat-könyvtárat választott, kettő kihagyta a lapozást,
egy pedig megcsinálta a törlést de a szerkesztést nem.
-->

---

# A SET megközelítése

| Kihívás | SET megoldás | Eredmény |
|---------|-------------|----------|
| **Divergencia** | 3 rétegű template rendszer | **83-87%** strukturális konvergencia |
| **Hallucináció** | OpenSpec workflow + elfogadási kritériumok | Spec ellen implementál |
| **Minőség-rulett** | Programozott gate-ek (exit kód, nem LLM ítélet) | Determinisztikus pass/fail |
| **Spec drift** | Coverage tracking + auto-replan | 100% spec lefedettség |
| **Amnézia** | Hook-alapú memória (5 réteg) | 100% kontextus megőrzés |
| **Hibajavítás** | Issue pipeline: detect -> investigate -> fix | **30 másodperc** recovery |

> **"We don't prompt -- we specify."**

<!-- SPEAKER_NOTES:
A kulcs: specifikáció-vezérelt fejlesztés. Nem azt mondjuk az ágensnek hogy
"csinálj egy admin panelt", hanem 8 követelmény, elfogadási kritériumok,
és a verify gate ellenőrzi mind a 8-at.
-->

---

<!-- _class: section-divider -->

# 2. A bemenet

*A spec minősége határozza meg az output minőségét*

---

# Egy jó spec felépítése

```
spec.md
├── Adatmodell         -- entitások, mezők, kapcsolatok, enumok
├── Oldalak            -- szekciók, oszlopok, komponensek
├── Design tokenek     -- hex színek, fontok, spacing értékek
├── Auth & szerepek    -- védett útvonalak, regisztráció
├── Seed data          -- valós nevekkel, nem "Termék 1"
├── i18n               -- lokálék, URL struktúra
└── Üzleti követelmények -- felhasználói történetek, elfogadási kritériumok
```

> **Te vagy a product owner, az ágensek a dev csapat, a spec a sprint backlog.**
> A különbség: ez a sprint órákat vesz igénybe, nem heteket.

<!-- SPEAKER_NOTES:
A spec nem egy vázlat -- ez egy részletes követelményrendszer.
Van interaktív spec-író eszközünk is (/set:write-spec) ami végigkérdezi
a projekt típusra specifikus részleteket.
-->

---

# Spec + Figma Design

<!-- A bemenet két része: markdown spec és Figma design -->

![w:480](../images/auto/cli/spec-preview.png) ![w:480](../images/auto/figma/storefront-design.png)

**Bal:** Markdown spec -- az üzleti követelmények
**Jobb:** Figma Make design -- a vizuális terv

A `set-design-sync` eszköz a Figma-ból kinyeri a design tokeneket (színek, fontok, spacing) és `design-system.md`-be írja -- az ágensek ezt olvassák implementáció előtt.

<!-- SPEAKER_NOTES:
A Figma Make egy egyszerű design eszköz. A set-design-sync kiolvassa belőle
a tokeneket és vizuális leírásokat, amiket a dispatcher az egyes ágenseknek
scope-szerint szétoszt.
-->

---

<!-- _class: section-divider -->

# 3. E2E Demo: MiniShop

*Egy webshop felépítése specifikációból -- élőben*

---

# MiniShop -- a feladat

Egy **Next.js 14 e-commerce alkalmazás** -- teljes egészében spec-ből építve:

- Terméklistázás és részletes termékoldal
- Kosár funkció (hozzáadás, törlés, mennyiség)
- Pénztár és rendelés kezelés
- Admin autentikáció (bejelentkezés, regisztráció)
- Admin CRUD (termékek kezelése)
- Seeded adatbázis valós adatokkal

**Kérdés:** Mennyi idő alatt, hány hibával, mennyi emberi beavatkozással?

<!-- SPEAKER_NOTES:
Ez nem egy toy example -- valós Next.js alkalmazás Prisma ORM-mel,
Playwright E2E tesztekkel, admin panellel. Ezt használjuk regressziós
tesztként minden major release előtt.
-->

---

# A pipeline

```
spec.md ──> digest ──> decompose ──> parallel agents ──> verify ──> merge ──> done
```

```
spec.md + design-snapshot.md (Figma)
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ Sentinel (autonóm szupervizor)                              │
│  ├─ digest: spec → követelmények + domain összefoglalók     │
│  ├─ decompose: független change-ek (DAG)                    │
│  ├─ dispatch: git worktree-kbe párhuzamosan                 │
│  ├─ monitor: 15s polling, crash recovery                    │
│  ├─ verify: quality gate-ek minden change-re                │
│  ├─ merge: FF-only + post-merge smoke                       │
│  └─ replan: amíg a spec 100%-ban lefedett                   │
└─────────────────────────────────────────────────────────────┘
```

<!-- SPEAKER_NOTES:
7 lépéses pipeline. Minden lépés automatikus.
A Sentinel a legfelső szintű szupervizor -- figyeli a crasheket,
stall-okat, és automatikusan újraindít.
-->

---

# 1. lépés: Digest -- Követelmények kinyerése

A spec-ből a digest modul kinyeri:
- **Domaineket** (pl. Products, Cart, Auth, Admin)
- **Követelményeket** domain-enként (pl. 32 db)
- **Elfogadási kritériumokat** (pl. 84 db WHEN/THEN)

![w:900](../images/auto/web/tab-digest.png)

> Minden követelmény kap egy `[REQ: ...]` azonosítót -- a teljes pipeline-ban ezt követjük.

<!-- SPEAKER_NOTES:
A digest tab a dashboardon mutatja az összes kinyert követelményt.
Minden REQ-hez később a verify gate ellenőrzi, hogy van-e implementáció.
Ha nincs, auto-replan indul.
-->

---

# 2. lépés: Decompose -- Független change-ek

A planner a követelményekből **függetlenül implementálható change-eket** hoz létre:

| Change | Függőség | Méret |
|--------|---------|-------|
| `project-infrastructure` | -- | Alapstruktúra, konfig |
| `products-page` | infrastructure | Terméklista + részletek |
| `cart-feature` | products | Kosár funkció |
| `admin-auth` | infrastructure | Admin bejelentkezés |
| `orders-checkout` | cart, admin-auth | Rendelés + pénztár |
| `admin-products` | admin-auth, products | Admin CRUD |

**Dependency DAG** -- fázisokra bontva:
- **Fázis 1:** infrastructure (alap)
- **Fázis 2:** products + admin-auth (párhuzamos!)
- **Fázis 3:** cart + orders + admin-products

<!-- SPEAKER_NOTES:
A dependency DAG a kulcs a párhuzamos végrehajtáshoz.
A fázis 2-ben a products és admin-auth egyszerre futhat, mert nincs
köztük függőség. Ez ~40%-kal csökkenti a futási időt.
-->

---

# 3. lépés: Dispatch -- Párhuzamos ágensek

Minden change saját **git worktree**-t kap -- izolált fejlesztési környezet:

```
main/
├── .worktrees/
│   ├── project-infrastructure/   ← Agent 1
│   ├── products-page/            ← Agent 2
│   ├── admin-auth/               ← Agent 3 (párhuzamos a 2-vel!)
│   ├── cart-feature/             ← Agent 4
│   ├── orders-checkout/          ← Agent 5
│   └── admin-products/           ← Agent 6
```

Minden ágensben a **Ralph Loop** fut:
```
proposal → design → spec → tasks → implementáció → tesztek → kész
```

> Egy ágens = egy change = egy worktree = teljes izoláció.

<!-- SPEAKER_NOTES:
A git worktree a kulcs -- minden ágens a saját ágán dolgozik, nem zavarják
egymást. A Ralph Loop az OpenSpec workflow az ágensen belül:
strukturált artifact-ok, nem szabad promptolás.
-->

---

# 4. lépés: Monitor -- Valós idejű felügyelet

A Sentinel **15 másodpercenként** poll-ozza az összes ágenst:

- **Haladás követés** -- hol tart minden change?
- **Stall detekció** -- ha >120s nincs előrelépés → vizsgálat
- **Crash recovery** -- PID eltűnt? → diagnózis → újraindítás
- **Token tracking** -- költség figyelése change-enként

![w:900](../images/auto/web/tab-sessions.png)

<!-- SPEAKER_NOTES:
A sessions tab mutatja az összes agent session-t: időtartam, token felhasználás,
iterációk száma. Ha egy ágens elakad, a sentinel automatikusan vizsgálatot indít.
-->

---

# Közben az ágens dolgozik...

![w:950](../images/auto/web/tab-agent.png)

Az Agent tab mutatja a **valós idejű terminál outputot** -- kódírás, tesztelés, hibakeresés.

<!-- SPEAKER_NOTES:
Itt látható, ahogy az ágens implementál: fájlokat ír, teszteket futtat,
hibákat javít. Ez nem fekete doboz -- minden lépés követhető.
A GIF az agent-session-scroll.gif mutatja ezt mozgásban.
-->

---

# 5. lépés: Verify -- Quality Gates

Minden change **6 gate-en** megy keresztül merge előtt:

```
Jest/Vitest (8s) → Build (35s) → Playwright E2E (45s)
    → Code Review (25s) → Spec Coverage → Post-merge Smoke (15s)
```

| Gate | Idő | Mit ellenőriz | Típus |
|------|-----|---------------|-------|
| **Test** | 8s | Unit/integration tesztek | Determinisztikus (exit code) |
| **Build** | 35s | Type check + bundle | Determinisztikus (exit code) |
| **E2E** | 45s | Böngésző-alapú tesztek | Determinisztikus (exit code) |
| **Review** | 25s | Kód minőség | LLM (CRITICAL = fail) |
| **Spec Coverage** | -- | Követelmény lefedettség | LLM + pattern match |
| **Smoke** | 15s | Post-merge sanity check | Determinisztikus |

> **Össz gate idő: 422 másodperc** (a build idő 12%-a)

<!-- SPEAKER_NOTES:
A gate-ek sorrendben futnak, a leggyorsabb elöl.
Ha a Jest elhasal, nem vár 45 másodpercet a Playwright-ra.
A lényeg: programozott ellenőrzés, nem LLM ítélet.
Az exit code 0 egyértelmű -- nem lehet "meggyőzni" a gate-et.
-->

---

# Self-Healing: 5 gate hiba, 5 automatikus javítás

A MiniShop futtatásban **5 gate hiba** volt -- mind automatikusan javítva:

| # | Hiba | Gate | Javítás |
|---|------|------|---------|
| 1 | Hiányzó teszt fájl | Test | Agent hozzáadta a teszt fájlt |
| 2 | Jest config hiba | Build | Agent javította a path mapping-et |
| 3 | Playwright auth teszt (3 spec) | E2E | Agent frissítette a redirect-eket |
| 4 | Post-merge type error | Build | Agent szinkronizált main-nel |
| 5 | Kosár teszt race condition | E2E | Agent hozzáadott `waitForSelector`-t |

> Gate-ek nélkül ez az **5 hiba bekerült volna main-be** és kaszkád hibákat okozott volna.

<!-- SPEAKER_NOTES:
Ez a self-healing pipeline lényege: a gate elkapja a hibát, az ágens
elolvassa a hibaüzenetet, kijavítja, és újra futtatja a gate-et.
Emberi beavatkozás nélkül. A 3-as különösen érdekes: 3 Playwright spec-et
kellett frissíteni mert az auth middleware máshova redirect-ált mint amit
a teszt várt.
-->

---

# 6. lépés: Merge -- Integráció

![w:900](../images/auto/web/tab-phases.png)

- **FF-only merge** -- nincs merge commit, tiszta history
- **Szekvenciális merge queue** -- soha nem párhuzamos merge
- **Fázis-rendezés** -- fázis 2 csak fázis 1 merge után indul
- **Post-merge smoke test** -- minden merge után sanity check

> A merge queue az integráció szűk keresztmetszete -- **szándékosan**.
> Egy rossz merge kaszkád hibákat okoz.

<!-- SPEAKER_NOTES:
A phases tab mutatja a gate badge-eket: B=Build, T=Test, E=E2E, R=Review, V=Verify.
Minden zöld = minden gate átment. A fázis-rendezés biztosítja, hogy az ágensek
mindig a legfrissebb main-ről dolgoznak.
-->

---

# 7. lépés: Replan -- 100% lefedettség

```
                    ┌──── coverage < 100%? ────┐
                    │                          │
merge ──► coverage check ──► done          replan
                                              │
                                    decompose újra
                                    a hiányzó REQ-ekre
```

A replan gate ellenőrzi:
- Minden `[REQ: ...]` megvalósult-e?
- Van-e lefedetlen domain?
- Ha igen: **új change-ek automatikus tervezése** a hiányokra

> A rendszer nem áll le amíg a spec 100%-ban nincs lefedve.

<!-- SPEAKER_NOTES:
Ez a replan gate az ami a SET-et megkülönbözteti: nem elég ha a kód lefordul
és a tesztek futnak -- a specifikáció minden pontjának teljesülnie kell.
Ha valami kimarad, automatikusan új change indul rá.
-->

---

<!-- _class: section-divider -->

# Az eredmény

*Amit a pipeline produkált*

---

# MiniShop -- a kész alkalmazás

![w:480](../images/auto/app/products.png) ![w:480](../images/auto/app/product-detail.png)

**Terméklistázás** és **termék részletek** -- valós adatokkal, működő navigációval.

<!-- SPEAKER_NOTES:
Ezek az alkalmazás screenshotjai AUTOMATIKUSAN készültek a futtatás végén.
A seed data valós termékneveket és leírásokat tartalmaz, nem placeholder szöveget.
-->

---

# MiniShop -- Kosár és Admin

![w:480](../images/auto/app/cart.png) ![w:480](../images/auto/app/admin-dashboard.png)

**Bal:** Működő kosár -- mennyiség módosítás, összesítés
**Jobb:** Admin dashboard -- védett route, session-alapú auth

<!-- SPEAKER_NOTES:
A kosár kliens-oldali state management-tel működik, az admin panel
session-alapú autentikációval védett. A middleware automatikusan redirect-el
ha nincs bejelentkezve.
-->

---

# MiniShop -- Admin CRUD és rendelések

![w:480](../images/auto/app/admin-products.png) ![w:480](../images/auto/app/orders.png)

**Bal:** Termék CRUD (létrehozás, szerkesztés, törlés)
**Jobb:** Rendelés kezelés -- státuszok, szűrés

> Minden oldal **működő adatbázissal**, **funkcionális navigációval** és **reszponzív layouttal**.

<!-- SPEAKER_NOTES:
Ez nem scaffolding vagy stub -- működő alkalmazás. A Prisma ORM kezeli
az adatbázist, a seed script feltölti valós adatokkal.
-->

---

# A számok

<!-- A MiniShop benchmark eredményei -->

| Metrika | Érték |
|---------|-------|
| Tervezett change-ek | **6** |
| Sikeresen mergelt | **6/6 (100%)** |
| Össz futási idő | **1 óra 45 perc** |
| Aktív build idő | ~1 óra 25 perc |
| Emberi beavatkozás | **0** |
| Merge konfliktus | **0** |
| Jest unit tesztek | 38 (6 suite) |
| Playwright E2E tesztek | 32 (6 spec fájl) |
| Git commitok | 39 |
| Össz token | 2.7M |
| Gate újrapróbálkozás | 5 (mind self-healed) |

<!-- SPEAKER_NOTES:
1 óra 45 perc alatt 6 change, 0 beavatkozás, 70 teszt (38 unit + 32 E2E).
Ez kb. 3-4 senior fejlesztő egy napos munkájának felel meg.
-->

---

# Token felhasználás

![w:900](../images/auto/web/tab-tokens.png)

| Change | Input | Output | Cache | Összesen |
|--------|-------|--------|-------|----------|
| project-infrastructure | 367K | 42K | 12.3M | 410K |
| products-page | 378K | 28K | 7.2M | 406K |
| cart-feature | 460K | 39K | 12.6M | 499K |
| admin-auth | 329K | 41K | 10.5M | 370K |
| orders-checkout | 312K | 36K | 10.5M | 348K |
| admin-products | 568K | 87K | 18.3M | 655K |
| **Összesen** | **2.4M** | **273K** | **71.4M** | **2.7M** |

> Cache ratio: **26:1** -- a prompt caching drámaian csökkenti a költséget.

<!-- SPEAKER_NOTES:
Az admin-products a legtöbb tokent használta (655K) mert a dependency lánc
végén volt -- az összes korábbi change kódját meg kellett értenie.
A cache read tokenek (71.4M) nem számlázottak -- a prompt caching újrahasznosítja
a már cachelt kontextust.
-->

---

<!-- _class: section-divider -->

# 4. Quality Gates

*Determinisztikus minőségbiztosítás*

---

# Miért nem elég az LLM code review?

**Korai kísérletek** (CraftBrew run #3):
- LLM-alapú code review gate
- Ágensek "gaming"-elték a reviewer-t (részletes kommentek = jó kód)
- Átment egy `TODO: implement later` ami eltörte a checkout-ot
- Inkonzisztens pass/fail döntések

**A megoldás:**
- **Test, Build, E2E** = exit kód 0 vagy nem = **determinisztikus**
- Egy elbukó Jest teszt egyértelmű -- nem lehet "meggyőzni"
- Egy `next build` ami 1-es exit kóddal tér vissza nem hazudik
- Csak a spec coverage maradt LLM-alapú (explicit PASS/FAIL parsing)

> **Gate-ek gyors sorrendben futnak** -- ha a Jest elhasal, nem vár a Playwright-ra.

<!-- SPEAKER_NOTES:
Ez egy fontos architekturális döntés volt: a minőségbiztosítás nem LLM ítélet.
Az exit kód objektív, nem szubjektív. Ez teszi lehetővé az autonóm működést --
nem kell emberi review minden change-hez.
-->

---

# Gate Profiles -- testreszabhatóság

Nem minden change-hez kell minden gate:

| Change típus | Test | Build | E2E | Review | Coverage |
|-------------|------|-------|-----|--------|----------|
| Feature | HARD | HARD | HARD | HARD | HARD |
| Bugfix | HARD | HARD | SOFT | HARD | SOFT |
| Cleanup | SOFT | HARD | SKIP | SOFT | SKIP |
| Config | SKIP | HARD | SKIP | SOFT | SKIP |

- **HARD** -- fail = block merge
- **SOFT** -- fail = warning, nem block
- **SKIP** -- nem fut

> A profile rendszer a `ProjectType` ABC-n keresztül bővíthető.

<!-- SPEAKER_NOTES:
A gate profile-ok csökkentik a felesleges gate futtatásokat.
Egy config change-hez nem kell Playwright E2E teszt.
A profile-t a planner határozza meg a change típusa alapján.
-->

---

# Playwright E2E tesztek

![w:900](../images/auto/web/playwright-report.png)

Az ágensek **maguk írják a Playwright teszteket** az implementáció részeként.
A gate futtatja őket -- ha elbukik, az ágens javítja.

> 32 E2E teszt a MiniShop-ban -- terméklistázás, kosár, checkout, admin, auth.

<!-- SPEAKER_NOTES:
A Playwright report screenshot automatikusan készült. A tesztek valódi
böngészőben futnak, valódi HTTP kérésekkel. Ez nem mock -- ez a tényleges
alkalmazás tesztelése.
-->

---

<!-- _class: section-divider -->

# 5. Dashboard & Monitoring

*Valós idejű rálátás mindenre*

---

# Web Dashboard -- Áttekintés

![w:950](../images/auto/web/dashboard-overview.png)

A dashboard a **http://localhost:7400** címen érhető el -- valós idejű orkesztrációs felügyelet.

<!-- SPEAKER_NOTES:
A dashboard Next.js + React + Tailwind CSS alapú.
A manager felület mutatja az összes regisztrált projektet és azok státuszát.
-->

---

# Dashboard tabok

| Tab | Mit mutat |
|-----|-----------|
| **Changes** | Összes change státusza, fázis, merge sorrend |
| **Phases** | Függőségi fa, gate badge-ek (B/T/E/R/V) |
| **Tokens** | Per-change token felhasználás chart |
| **Sessions** | Agent session lista, időtartam, tokenek |
| **Sentinel** | Szupervizor döntések, restart, stall |
| **Log** | Nyers orkesztrátor output, kereshető |
| **Agent** | Élő agent terminál |
| **Learnings** | Tanulságok, gate hibák |
| **Digest** | Követelmények + lefedettség |

![w:480](../images/auto/web/tab-changes.png) ![w:480](../images/auto/web/tab-learnings.png)

<!-- SPEAKER_NOTES:
A Changes tab a leggyakrabban használt -- egy pillantással látszik
hol tart minden change. A Learnings tab a tanulságokat gyűjti: gate hibák,
agent megoldások, pattern-ek amiket a rendszer megtanult.
-->

---

# Sentinel felügyelet

![w:900](../images/auto/web/tab-sentinel.png)

A Sentinel **3 szintű felügyeleti modell**:
1. **Ágensek** kezelik a kód hibákat
2. **Orkesztrátor** kezeli a workflow hibákat
3. **Sentinel** kezeli az infrastruktúra hibákat

| Esemény | Sentinel akció |
|---------|---------------|
| `done` | Leállás |
| `checkpoint` | Auto-approve vagy eszkaláció |
| `crash` | Diagnózis → újraindítás |
| `stale` (>120s) | Vizsgálat indítása |

<!-- SPEAKER_NOTES:
A sentinel a "night watchman" -- ha éjszaka futtatjuk, ő figyeli hogy
semmi ne álljon le. Egy crash 30 másodpercen belül detektálva van,
diagnózis fut, és újraindítás történik.
-->

---

<!-- _class: section-divider -->

# 6. Architektúra

*3 réteg, bővíthető plugin rendszer*

---

# 3 rétegű architektúra

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: External Plugins (külön repók)                     │
│  └─ pl. set-project-fintech (IDOR, PCI compliance)         │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Built-in Modules (modules/)                        │
│  ├─ web/    → WebProjectType: Next.js, Prisma, Playwright   │
│  └─ example/ → DungeonProjectType: referencia implementáció │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Core (lib/set_orch/)                               │
│  ├─ engine.py      → Állapotgép, orkesztrálás               │
│  ├─ dispatcher.py  → Worktree létrehozás, agent dispatch    │
│  ├─ merger.py      → Merge queue, integration gate-ek       │
│  ├─ verifier.py    → Quality gate-ek (test/build/E2E/...)   │
│  ├─ planner.py     → Spec dekompozíció, DAG generálás       │
│  └─ digest.py      → Követelmény kinyerés                   │
└─────────────────────────────────────────────────────────────┘
```

> **Layer 1** soha nem tartalmaz projekt-specifikus logikát.
> Minden web/framework specifikus dolog a **Layer 2**-ben van.

<!-- SPEAKER_NOTES:
Ez a legfontosabb architekturális szabály: a core abstract marad.
Ha valaki fintech projektet akar, készít egy set-project-fintech plugint
ami IDOR ellenőrzéseket és PCI compliance rule-okat ad hozzá.
A core erről mit sem tud.
-->

---

# Projekt méret

```
set-core/
├── lib/set_orch/     59K sor Python     ← Core engine
├── modules/web/       5K sor Python     ← Web plugin
├── mcp-server/       30K sor            ← MCP szerver
├── web/              14K sor TypeScript  ← Dashboard
├── bin/              15K sor Shell       ← 57 CLI eszköz
├── openspec/specs/   23K sor            ← 376 specifikáció
├── docs/             22K sor            ← Dokumentáció
└── templates/core/    3K sor            ← Deploy-olt szabályok
                    ─────
                    134K LOC összesen
```

| Statisztika | Érték |
|-------------|-------|
| Fejlesztési idő | 950+ óra |
| Commitok | 1,295 (~16/nap) |
| Specifikációk | 376 |
| E2E futtatások | 30+ |

> **Saját magával fejlesztve** -- a set-core saját orkesztrálási pipeline-jával készült.

<!-- SPEAKER_NOTES:
Ez a "dogfooding" -- a set-core-t magát a set-core-ral fejlesztjük.
Minden feature OpenSpec workflow-val készül, quality gate-eken megy át,
és a sentinel felügyeli. Ha valami nem működik az orkesztrálásban,
mi magunk futunk bele először.
-->

---

<!-- _class: section-divider -->

# 7. Tanulságok

*30+ futtatás, valós production tapasztalatok*

---

# 8 tanulság az élesből

**1. Ágenseknek struktúra kell, nem prompt**
- OpenSpec artifacts (proposal → spec → tasks) tartja a fókuszt
- Nélküle: 3 ágens, 3 különböző táblázat-könyvtár

**2. Quality gate-eknek determinisztikusnak kell lenni**
- Exit kód > LLM ítélet
- LLM review-t gaming-elték az ágensek

**3. Merge konfliktusok a #1 kaszkád hiba**
- Fázis-rendezés + dependency DAG + szekvenciális merge queue
- Cross-cutting fájlok: Prisma schema, i18n bundle, middleware

**4. Memória hook nélkül használhatatlan**
- 15+ session, **0 önkéntes mentés** az ágensektől
- 5 rétegű hook infra: +34% javulás

<!-- SPEAKER_NOTES:
Ezeket mind a kemény úton tanultuk meg. A 4-es különösen meglepő volt:
az ágensek soha nem mentenek önként memóriát, hiába kérjük.
A hook infrastruktúra automatikusan extraktálja és menti a tanulságokat.
-->

---

# 8 tanulság (folytatás)

**5. E2E tesztelés feltár amit unit test nem**
- Stale lock fájlok, zombie worktree-k, race condition a poll ciklusban
- Token counter overflow 10M+ cache token-nél

**6. Stall detekció grace period kell**
- `pnpm install` >60s stdout nélkül → watchdog megölte
- Kontextus-tudatos timeout: install=120s, codegen=90s, MCP=60s

**7. A Sentinel megtérül**
- 3 éjszakai futtatás elveszett crash miatt a sentinel előtt
- 5-10 LLM hívás/futtatás, órákat spórol

**8. Template-ek > konvenciók**
- "Csinálj Next.js projektet" = 5 különböző könyvtárstruktúra
- 3 rétegű template rendszer: **0% strukturális divergencia**

<!-- SPEAKER_NOTES:
A 7-es a legfontosabb ROI szempontból: egy sentinel ~5-10 LLM hívásba kerül
futtatásonként, de egy crash nélküle 4-6 óra elvesztett compute.
A 8-as pedig a reprodukálhatóság kulcsa: nem elég mondani az ágensnek
hova tegye a fájlokat -- oda kell adni a struktúrát.
-->

---

# Skálázás: MiniShop vs CraftBrew

| Metrika | MiniShop | CraftBrew #7 | Szorzó |
|---------|----------|-------------|--------|
| Change-ek | 6 | 15 | 2.5x |
| Forrás fájlok | 47 | 150+ | 3x |
| DB modellek | ~8 | 28 | 3.5x |
| Merge konfliktus | 0 | 4 (mind resolved) | -- |
| Emberi beavatkozás | 0 | 0 | -- |
| Futási idő | 1h 45m | ~6h | 3.4x |
| Tokenek | 2.7M | ~11M | **4x** |

> A token skálázás **szuperlineáris** (4x token 2.5x change-re) -- a későbbi change-eknek
> egyre több kontextust kell megérteniük.

<!-- SPEAKER_NOTES:
A CraftBrew validálta hogy a rendszer nagyobb projekteknél is működik,
de rámutatott a merge konfliktus kezelés fontosságára.
A 4 merge konfliktust automatikusan oldotta meg, de ehhez kellett
a conservation check és entity counting amit a korábbi futtatások
tapasztalatai alapján fejlesztettünk.
-->

---

# Konvergencia -- reprodukálhatóság mérése

Két független MiniShop futtatás összehasonlítása:

| Dimenzió | Egyezés |
|----------|---------|
| **DB séma** (modellek, mezők, relációk) | **100%** |
| **Konvenciók** (naming, struktúra) | **100%** |
| **Route-ok** (URL-ek, API végpontok) | **83%** |
| **Összesített** | **83/100** |

A 83%-os score kontextusa:
- A maradék 17% **stilisztikai**, nem strukturális
- Pl. `/api/products` vs `/api/product` (egyes vs többes szám)
- A séma és konvenció **teljesen determinisztikus**

> A `set-compare` eszköz automatikusan méri a konvergenciát futtatások között.

<!-- SPEAKER_NOTES:
Ez az egyik legfontosabb metrikánk: ha kétszer lefuttatjuk ugyanazt a spec-et,
mennyire hasonló az eredmény? 83% azt jelenti hogy a struktúra megegyezik,
csak apró stilisztikai különbségek vannak. A séma 100%-os egyezése azt jelenti
hogy az adatmodell determinisztikus.
-->

---

<!-- _class: section-divider -->

# 8. Roadmap

*Hová tartunk*

---

# Fejlesztési irányok

| Irány | Cél | Státusz |
|-------|-----|---------|
| **Divergencia csökkentés** | Template optimalizálás, scaffold tesztelés | Egyszerű projekteknél mérhető javulás |
| **Build idő optimalizálás** | Párhuzamos gate-ek, inkrementális build, cache | Jelenleg szekvenciális; kutatás alatt |
| **Session context reuse** | Kontextus újrahasznosítás iterációk között | Cold-start token overhead csökkentés |
| **Memória optimalizálás** | Relevancia scoring, dedup, auto-rule konverzió | Dedup + konszolidáció működik |
| **Gate intelligence** | Adaptív threshold-ok múltbeli pass rate-ek alapján | Gate profile-ok működnek |
| **Merge conflict prevention** | Proaktív cross-cutting fájl konfliktus detekció | Fázis rendezés működik |

---

# Nagyobb tervek

**Core/Web szétválasztás**
- 170+ web-specifikus referencia szivárgott a core-ba
- Áthelyezés `modules/web/`-be új `ProjectType` ABC metódusokon keresztül
- Cél: külső pluginek ne függjenek web logikától

**NIS2 Compliance Layer**
- EU 2022/2555 irányelv támogatás
- Template rule-ok, verifikációs szabályok, dedikált gate
- Opt-in konfigurációs flag-gel

**shadcn/ui Design Connector**
- `components.json`, `tailwind.config.ts`, `globals.css` parsing
- Lokális `design-system.md` generálás (nincs MCP szükség)

<!-- SPEAKER_NOTES:
A Core/Web szétválasztás a legmagasabb prioritás -- amíg web-specifikus
kód van a core-ban, nehéz külső plugineket fejleszteni.
A NIS2 egy érdekes enterprise irány -- szabályozási megfelelőség
automatikus ellenőrzése a quality gate-eken keresztül.
-->

---

# A teljes ökoszisztéma

| Repository | Leírás |
|------------|--------|
| **set-core** | Core engine, web modul, dashboard, CLI |
| **set-spec-capture** | Spec kinyerés webből, PDF-ből, beszélgetésből |
| **set-voice-agent-delivery** | Hang-alapú agent delivery |
| **set-project-example** | Referencia plugin (Dungeon Builder) |

**Technológiai stack:**

| Komponens | Technológia |
|-----------|-------------|
| Agent runtime | Claude Code (Anthropic) |
| Workflow | OpenSpec |
| Izoláció | Git worktree-k |
| Engine | Python + FastAPI + uvicorn |
| Dashboard | Next.js + React + Tailwind CSS |
| Memória | shodh-memory (RocksDB + vector embeddings) |
| CLI eszközök | Bash (zero dependency) |
| State | JSON fájlok + git (nincs adatbázis) |

---

<!-- _class: title-slide -->

# Összefoglalás

**Spec → Digest → Decompose → Dispatch → Verify → Merge → Done**

6 change | 1h 45m | 0 beavatkozás | 70 teszt | 100% spec coverage

---

# Kérdések?

**Források:**
- Repo: `git.setcode.dev/root/set-core`
- Web: `setcode.dev`
- Benchmarks: `docs/learn/benchmarks.md`
- Lessons learned: `docs/learn/lessons-learned.md`

**Próbáld ki:**
```bash
# Telepítés
pip install -e .
pip install -e modules/web

# Első futtatás
./tests/e2e/runners/run-micro-web.sh

# Dashboard
open http://localhost:7400
```

<!-- SPEAKER_NOTES:
Kérdések és válaszok. Ha valaki ki akarja próbálni, a micro-web scaffold
a legegyszerűbb indulás -- 5 oldalas weboldal, ~20 perc alatt kész.
-->
