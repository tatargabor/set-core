# A szoftverfejlesztés jövője

## Hol tartunk most?

2026 elején a szoftverfejlesztés egy történelmi átmenet közepén van. Az AI ágensek már képesek:

- Önállóan megoldani valós hibákat (SWE-bench: ~50%)
- Specifikáció alapján implementálni feature-öket
- Párhuzamosan, koordináltan dolgozni
- Tanulni korábbi tapasztalatokból

De még nem képesek:

- Komplex architektúrákat tervezni az üzleti kontextus teljes megértésével
- Emberi csapatdinamikát kezelni
- Kreatív, újszerű megoldásokat kitalálni ahol nincs precedens
- 100%-ban megbízható, production-ready kódot írni review nélkül

Hol tartunk tehát? Valahol a „hasznos eszköz" és az „önálló fejlesztő" között.

## Három időhorizont

### Rövid táv: 2025--2026 — AI mint páros programozó

```
  ┌────────────────────────────────────────────┐
  │  MA: AI Pair Programming                    │
  │                                            │
  │  Fejlesztő ◀──────────▶ AI Ágens          │
  │     │                      │               │
  │     │  "Javítsd ki ezt"    │               │
  │     │───────────────────▶  │               │
  │     │                      │  javít        │
  │     │  ◀───────────────────│  tesztel      │
  │     │  "Kész, nézd meg"    │               │
  │     │                      │               │
  │  Ember irányít, AI végrehajt               │
  │  Ember review-ol minden változtatást       │
  └────────────────────────────────────────────┘
```

**Ez van most.** A fejlesztő megmondja mit kell csinálni, az AI megcsinálja, a fejlesztő ellenőrzi. A PM a fejlesztővel egyeztet, aki az AI-t irányítja.

**PM feladata**: Ugyanaz mint eddig, de a fejlesztő gyorsabb. A becsléseket le kell kalibráld — ami eddig 3 nap volt, most 1 nap lehet.

### Közép táv: 2026--2028 — AI csapatok emberi felügyelettel

```
  ┌────────────────────────────────────────────┐
  │  HOLNAP: AI Csapatok                       │
  │                                            │
  │           Ember (Architect / PM)            │
  │                   │                         │
  │          Spec + Review                      │
  │                   │                         │
  │     ┌─────────────┼─────────────┐          │
  │     │             │             │          │
  │     ▼             ▼             ▼          │
  │  ┌──────┐    ┌──────┐    ┌──────┐         │
  │  │AI Ág.│    │AI Ág.│    │AI Ág.│         │
  │  │  #1  │    │  #2  │    │  #3  │         │
  │  │front │    │back  │    │test  │         │
  │  └──────┘    └──────┘    └──────┘         │
  │                                            │
  │  Ember ad specifikációt, AI csapat          │
  │  dolgozik, ember review-olja a végén       │
  └────────────────────────────────────────────┘
```

**Ez felé tartunk.** Az orchestrációs réteg (V. fejezet) ennek az előfutára. Egy ember ír egy specifikációt, az AI csapat implementálja, az ember a végeredményt ellenőrzi.

**PM feladata**: A specifikáció minősége kritikussá válik. Eddig ha a spec pontatlan volt, a fejlesztő megkérdezte. Az AI nem mindig kérdez — megpróbálja értelmezni. Jobb spec = jobb eredmény.

### Hosszú táv: 2028+ — AI-vezérelt fejlesztés emberi irányítással

```
  ┌────────────────────────────────────────────┐
  │  HOLNAPUTÁN: AI-vezérelt fejlesztés        │
  │                                            │
  │  Ember: Vízió + Minőség + Üzleti döntés   │
  │                   │                         │
  │          "Mit akarunk?"                     │
  │          "Ez elég jó?"                      │
  │                   │                         │
  │                   ▼                         │
  │         ┌─────────────────┐                │
  │         │  AI Orchestrátor │                │
  │         │  (spec, design,  │                │
  │         │   tasks, impl.,  │                │
  │         │   test, deploy)  │                │
  │         └─────────────────┘                │
  │                   │                         │
  │          Ember: szúrópróba review           │
  │          Ember: release döntés              │
  │                                            │
  └────────────────────────────────────────────┘
```

**Ez a legvalószínűbb hosszú távú kép.** Az AI nemcsak implementál, hanem tervez is — az ember az üzleti víziót adja, és a minőségi kaput kontrollálja.

**PM feladata**: A PM szerepe a „mit" és „miért" kérdésekre fókuszálódik. Kevesebb „ki csinálja meg?" és „hol tartunk?" — több „mit csinálunk és miért?" és „elég jó ez a felhasználóknak?"

## A PM szerep evolúciója

```
  2024:     PM ──▶ Jira ticket ──▶ Dev ──▶ Review ──▶ Deploy
                   (részletes)    (kódol)  (kézi)

  2026:     PM ──▶ Proposal ──▶ AI Agent ──▶ Auto-review ──▶ PM OK ──▶ Deploy
                   (mit+miért)  (spec→kód)  (tesztek)       (check)

  2028+:    PM ──▶ Vízió doc ──▶ AI Orchestr. ──▶ AI Review ──▶ PM spot-check
                   (nagy kép)    (minden auto.)   (auto.)       (szúrópróba)
```

**Ami változik:**

| Terület | Régi PM | Új PM |
|---------|---------|-------|
| **Becslések** | Napokban/hetekben gondolkodik | Órákban gondolkodik, kapacitást ágensekben méri |
| **Státusz meeting** | Napi standup, hetente retro | Dashboard nézegetés, ritkább sync |
| **Spec írás** | „Nice to have" | Kritikus — a spec minősége = a kód minősége |
| **Review** | Kódot nem néz, ticketet mozgat | Artifact-okat review-ol (proposal, spec) |
| **Koordináció** | Ember -- ember | Ember → spec → AI csapat |
| **Minőség** | „A devek megoldják" | Minőségi kapu-t definiál és betartatja |

## Iparági szereplők

Nem csak az Anthropic dolgozik ezen. Íme a főbb szereplők:

| Eszköz | Fejlesztő | Fő megközelítés | Állapot (2026 eleje) |
|--------|-----------|-----------------|----------------------|
| **Claude Code** | Anthropic | Agentic CLI/IDE, hookrendszer, MCP, subágensek | Production, széles körben használt |
| **GitHub Copilot** | Microsoft/GitHub | IDE kiegészítés → agent mode | Copilot agent élesben |
| **Cursor** | Cursor Inc. | AI-natív IDE | Népszerű, aktívan fejlődik |
| **Devin** | Cognition Labs | Teljesen autonóm AI fejlesztő | Korlátozott hozzáférés |
| **Amazon Q Dev** | Amazon/AWS | AWS-integrált AI fejlesztő | AWS ökoszisztémán belül |
| **Google Jules** | Google | AI kódoló ágens | Korai fázis |

```
  Autonómia szint:

  Alacsony                                          Magas
  ├─────────────┼────────────────┼─────────────────┤
  │             │                │                  │
  Copilot    Cursor        Claude Code          Devin
  (kiegészít)  (szerkeszt)   (ágens)          (autonóm)
```

**A trend egyértelmű**: minden szereplő az autonómia felé mozog. A kérdés nem az, hogy az AI ágensek át fogják-e venni a rutin kódolási feladatokat, hanem **mikor** és **milyen szinten**.

## Kockázatok és kihívások

Minden technológiai forradalomnál vannak kockázatok. Ezeket fontos ismerni:

### 1. AI hallucináció
Az AI néha magabiztosan állít olyasmit, ami nem igaz. Kitalál API-kat, hivatkozik nem létező függvényekre, vagy logikusnak tűnő de hibás megoldásokat ad.

**Mitigáció**: Automatikus tesztek, kód review, és a spec-driven megközelítés (ami mérhető követelményeket ad).

### 2. Biztonsági kérdések
Az AI ágens hozzáfér a fájlrendszerhez, futtat parancsokat, és potenciálisan érzékeny adatokkal dolgozik. Ha rosszindulatú input-ot kap (prompt injection), nem kívánt műveleteket végezhet.

**Mitigáció**: Sandboxing (elszigetelt futtatás), jogosultsági rendszerek, és a hookrendszer ami blokkolhatja a veszélyes műveleteket.

### 3. Vendor lock-in
Ha egy csapat teljesen egy AI provider-re (pl. Anthropic, OpenAI) épít, annak kiesése megbéníthatja a munkát.

**Mitigáció**: A specifikáció-vezérelt megközelítés provider-független — a specek, design-ok, és taskok szöveges fájlok, amik bármely AI-val használhatók. Az MCP szabvány szintén provider-független.

### 4. Szabályozási kérdések
Az EU AI Act és más szabályozások hatással lehetnek arra, hogyan használhatók AI ágensek a szoftverfejlesztésben, különösen kritikus infrastruktúrát érintő projektekben.

**Mitigáció**: A spec-driven megközelítés teljes audit trail-t biztosít — minden döntés, változás, és AI-művelet dokumentálva van git-ben.

### 5. Munkaerőpiaci hatás
Az AI ágensek csökkentik a rutin kódolási feladatokat. Ez egyes fejlesztői pozíciókat átalakíthat.

**Mitigáció**: A fejlesztői szerep átalakulása — kevesebb kódírás, több architektúra, review, és AI-felügyelet. Hasonló ahhoz, ahogy a számítógépek nem szüntették meg a könyvelést, hanem átalakították.

## Ami NEM fog eltűnni

Az AI forradalom közepén fontos tisztán látni, mi marad változatlanul értékes:

```
  ┌──────────────────────────────────────────────┐
  │  EMBERI ÉRTÉKEK AMIK MEGMARADNAK             │
  │                                              │
  │  ✓ Üzleti gondolkodás                       │
  │    "Mit akar a felhasználó?"                 │
  │    "Melyik feature hoz bevételt?"            │
  │                                              │
  │  ✓ Architektúrális döntések                  │
  │    "Monolitikus vagy mikroszervizes?"         │
  │    "Cloud vagy on-premise?"                   │
  │                                              │
  │  ✓ Csapat és kultúra                         │
  │    "Hogyan dolgozunk együtt?"                │
  │    "Mi a csapat erőssége?"                   │
  │                                              │
  │  ✓ Minőségi mérce                            │
  │    "Elég jó ez a felhasználóknak?"           │
  │    "Megbízhatunk ebben?"                      │
  │                                              │
  │  ✓ Etikai és üzleti ítélőképesség            │
  │    "Szabad ezt csinálnunk?"                  │
  │    "Mi a kockázat?"                          │
  │                                              │
  └──────────────────────────────────────────────┘
```

**A szoftverfejlesztés nem a kódolásról szól** — a problémamegoldásról szól. Az AI átveszi a kódolás jelentős részét, de a probléma meghatározása, a prioritások felállítása, és a végeredmény értékelése emberi feladat marad.

## Összefoglalás: mit tegyen most egy PM?

| Lépés | Mit | Miért |
|-------|-----|-------|
| **1. Ismerd meg** | Próbáld ki a Claude Code-ot (lásd Függelék) | Személyes tapasztalat nélkül nem értheted meg |
| **2. Gondolkodj spec-ben** | Kezdj részletesebb specifikációkat írni | A spec minősége = az AI output minősége |
| **3. Kalibráld újra** | A becslési modelleket igazítsd | Ami 5 nap volt, lehet 1 nap + review |
| **4. Fókuszálj minőségre** | Definiáld a „kész" definícióját | Az AI gyorsan ír kódot — de jót? |
| **5. Kísérletezz** | Egy kisebb feladaton próbáld ki a flow-t | Alacsony kockázat, nagy tanulság |

\begin{kulcsuzenat}
A PM szerep nem tűnik el — átalakul. Kevesebb „ki csinálja meg?" és „mikor lesz kész?" — több „mit csinálunk és miért?" és „elég jó ez?". A legjobb PM-ek azok lesznek, akik értik az AI ágensek képességeit és korlátait, és tudják hogyan kell jó specifikációkat írni. Ez a könyv az első lépés ezen az úton.
\end{kulcsuzenat}
