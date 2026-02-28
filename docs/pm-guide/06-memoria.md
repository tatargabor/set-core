# Memória és tanulás

## A probléma: az amnéziás kolléga

Képzeld el, hogy van egy rendkívül tehetséges gyakornokod. Minden nap bejön, brilliánsan dolgozik — de másnap reggel **mindenre elfelejtett**. Nem emlékszik mit csinált tegnap, milyen döntéseket hozott, milyen hibákba futott, vagy milyen konvenciókat tanult meg.

Minden reggel mindent elölről kell elmagyarázni.

Ez volt az AI ágensek alapproblémája egészen 2025 közepéig. Minden session (munkamenet) egy üres lappal indult. A Claude Code megnyílt, és az ágens semmit sem tudott a korábbi beszélgetésekről, döntésekről, vagy a projekt történetéről.

## A megoldás: Developer Memory

A Developer Memory rendszer megoldja ezt a problémát. Minden fontos döntést, tanulságot, és kontextust **automatikusan ment**, és a következő session-ben **automatikusan betölti** ami releváns.

### Előtte / utána

```
  ┌──────────────── MEMÓRIA NÉLKÜL ──────────────────┐
  │                                                    │
  │  Session 1:                                        │
  │  Fejlesztő: "A Redis timeout legyen 30 másodperc" │
  │  AI: "Rendben, beállítom 30s-re." ✓                │
  │                                                    │
  │  Session 2 (másnap):                               │
  │  Fejlesztő: "Mi a Redis timeout?"                  │
  │  AI: "Az alapértelmezett 5 másodperc."             │
  │  Fejlesztő: "Nem, tegnap 30-ra állítottuk!"       │
  │  AI: "Sajnálom, nincs információm erről."          │
  │                                                    │
  └────────────────────────────────────────────────────┘

  ┌──────────────── MEMÓRIÁVAL ──────────────────────┐
  │                                                    │
  │  Session 1:                                        │
  │  Fejlesztő: "A Redis timeout legyen 30 másodperc" │
  │  AI: "Rendben, beállítom 30s-re." ✓                │
  │  [Memória ment: "Redis timeout: 30s — döntés"]     │
  │                                                    │
  │  Session 2 (másnap):                               │
  │  Fejlesztő: "Mi a Redis timeout?"                  │
  │  [Memória betölt: korábbi döntés a Redisről]       │
  │  AI: "Korábbi döntés alapján: 30 másodperc.        │
  │       Ezt az 1-es session-ben állítottuk be."      │
  │                                                    │
  └────────────────────────────────────────────────────┘
```

## A három memória típus

A rendszer háromféle emléket különböztet meg:

```
  ┌─────────────────────────────────────────────────────┐
  │                                                     │
  │  DÖNTÉS (Decision)                                  │
  │  "A és B közül B-t választottuk, mert..."           │
  │  Példa: "SSE-t használunk WebSocket helyett,        │
  │          mert a Cloudflare Workers nem támogatja     │
  │          a tartós kapcsolatokat."                    │
  │                                                     │
  ├─────────────────────────────────────────────────────┤
  │                                                     │
  │  TANULSÁG (Learning)                                │
  │  "Ezt tapasztaltuk és ebből tanultunk."             │
  │  Példa: "A PySide6 QTimer-t csak a fő szálból      │
  │          szabad hívni, különben crash."             │
  │                                                     │
  ├─────────────────────────────────────────────────────┤
  │                                                     │
  │  KONTEXTUS (Context)                                │
  │  "Háttér információ a projektről."                  │
  │  Példa: "Ez egy monorepo pnpm workspace-szel,       │
  │          az API a packages/api/ könyvtárban van."    │
  │                                                     │
  └─────────────────────────────────────────────────────┘
```

**PM szemmel**: Gondolj rá úgy, mint három fiókra az irodában:
- **Döntések fiók**: Protokollok és megállapodások, amikre hivatkozni lehet
- **Tanulságok fiók**: Lessons learned, hogy ne kövessük el újra ugyanazt
- **Kontextus fiók**: Az „onboarding dokumentum", ami az új embernek kell

## Az 5 réteg — hogyan dolgozik a memória

A memóriát egy ötlépéses automatikus rendszer kezeli. Nem kell az ágensnek mondani, hogy „jegyezd meg" — a rendszer automatikusan működik:

```
  Session élete:

  ┌───── Session indul ─────┐
  │ 1. BETÖLTÉS             │  Betölti amit tud a projektről:
  │    (Session Start)      │  korábbi döntések, konvenciók,
  │                         │  ismert hibák, bevált módszerek
  └───────────┬─────────────┘
              │
              ▼
  ┌───── Munka közben ──────┐
  │ 2. FELIDÉZÉS            │  Minden kérdésnél megkeresi a
  │    (Kérdés beérkezik)   │  releváns emlékeket
  │                         │  "Volt már hasonló probléma?"
  │ 3. FELISMERÉS           │  Ha parancsot futtat, megnézi
  │    (Eszköz használat)   │  volt-e már hasonló helyzet
  │                         │
  │ 4. HIBAEMLÉK            │  Ha hiba történik, megkeresi
  │    (Hiba esetén)        │  a korábbi megoldásokat
  │                         │  "Ezt a hibát már láttuk,
  │                         │   a megoldás: ..."
  └───────────┬─────────────┘
              │
              ▼
  ┌───── Session véget ér ──┐
  │ 5. MENTÉS               │  Elmenti a fontos dolgokat:
  │    (Session End)        │  új döntéseket, tanulságokat,
  │                         │  felfedezett mintákat
  └─────────────────────────┘
```

**PM szemmel**: Úgy kell elképzelni, mint egy pályakezdőt akinek van egy jegyzetfüzete:
- Reggel megnézi a tegnapi jegyzeteit (1. betöltés)
- Munka közben ha kérdése van, visszalapoz (2-4. felidézés)
- Este leírja amit tanult (5. mentés)

A különbség: az AI ágens ezt automatikusan, következetesen, minden alkalommal megteszi. Ember ritkán ilyen fegyelmezett.

## Csapat memória — gépek között

A memória nem csak egyetlen gépen létezik. Ha több fejlesztő (vagy több gépen futó ágens) dolgozik ugyanazon a projekten, a memória **git-en keresztül szinkronizálódik**:

```
  ┌─────────┐                    ┌─────────┐
  │ Gép A   │     git sync       │ Gép B   │
  │         │ ◀────────────────▶ │         │
  │ Ágens 1 │                    │ Ágens 2 │
  │ Memória │                    │ Memória │
  └─────────┘                    └─────────┘
       │                              │
       └──────────── Közös ───────────┘
              memória adatbázis
```

Ha az Ágens 1 megtanulta, hogy „a deployment scriptben a `--force` flag kell", ez az információ megjelenik az Ágens 2-nél is.

**PM szemmel**: Mint egy közös tudásbázis (wiki), de ami automatikusan íródik és automatikusan használódik. Nem kell senkit emlékeztetned, hogy „írd be a wiki-be" — megtörténik.

## Valós példa: hogyan segít a memória

Egy projekt 3. hetében az AI ágens egy furcsa hibába futott:

```
  Session 15 (memória nélkül):
  AI futtatja: npm test
  Hiba: "ECONNREFUSED localhost:5432"
  AI: "Úgy tűnik, az adatbázis nem fut."
  AI: *15 percig debugol, mire rájön, hogy a teszt
      adatbázis külön Docker containerben fut*

  Session 15 (memóriával):
  AI futtatja: npm test
  Hiba: "ECONNREFUSED localhost:5432"
  [Memória betölt: "Teszt adatbázishoz kell:
   docker compose up test-db"]
  AI: "Ismert probléma — a teszt adatbázis nem fut.
       Indítom: docker compose up test-db"
  *30 másodperc és kész*
```

15 perc vs. 30 másodperc. Ez a memória értéke.

## Mi NEM memória

Fontos tisztázni: a memória nem mindenható.

| Ami memória | Ami NEM memória |
|-------------|-----------------|
| Projektszintű döntések | Titkos adatok (jelszavak, kulcsok) |
| Konvenciók és minták | A teljes kódbázis másolata |
| Korábbi hibák és megoldások | Minden egyes chat üzenet |
| Architectural Decision Records | Ideiglenes debug információ |

A memória szelektív — csak azt jegyzi meg, ami hosszú távon hasznos. Pont úgy, ahogy te sem jegyzed meg a mai ebédet, de emlékszel, hogy a csapatod agilis módszertant használ.

\begin{kulcsuzenat}
Az AI ágens memóriával nem felejt. Ami egyszer megtörtént — döntés, hiba, konvenció — azt emlékezik és használja. A PM-nek ez azért fontos, mert a korábbi döntésekre építhetünk anélkül, hogy újra meg kellene vitatni azokat. Mint egy tökéletes jegyzőkönyv, amit mindenki olvas.
\end{kulcsuzenat}
