# A wt-tools ökoszisztéma

## Áttekintés

A `wt-orchestrate` nem egyedül áll — egy tágabb eszközkészlet része, amely a teljes AI-asszisztált fejlesztési workflow-t lefedi. A `wt-tools` csomag CLI eszközöket, hookokat, memória rendszert, és projekt sablonokat tartalmaz.

## A fő eszközök

### Worktree lifecycle

Ezek az eszközök a git worktree-k teljes életciklusát kezelik — a létrehozástól a merge-ig és a cleanup-ig. Minden ágens izolált worktree-ben dolgozik, saját branch-en, anélkül, hogy a fő ágat zavarná.

| Eszköz | Funkció |
|--------|---------|
| `wt-new` | Új worktree és branch létrehozása, .claude/ inicializálás |
| `wt-list` | Aktív worktree-k listázása, állapot összefoglaló |
| `wt-status` | Részletes ágens-állapot: PID, iteráció, token, modell |
| `wt-merge` | Worktree merge main-be, LLM conflict resolution |
| `wt-close` | Worktree cleanup (branch törlés, könyvtár eltávolítás) |
| `wt-focus` | Ágens-váltás: terminál fókusz a kiválasztott worktree-re |
| `wt-add` | Meglévő branch hozzáadása worktree-ként |

### Ágens futtatás

A Ralph loop a `wt-loop` által vezérelt iteratív fejlesztési ciklus. Az ágens minden iterációban kódot ír, teszteket futtat, és az eredmény alapján dönt a folytatásról. A loop automatikusan kezeli a context window limiteket, a token budgetet, és az API rate limiteket.

| Eszköz | Funkció |
|--------|---------|
| `wt-loop` | Ralph iteratív loop: max-turns, token budget, model routing |
| `wt-work` | Interaktív munka session worktree-ben |
| `wt-skill-start` | Skill-alapú session indítás worktree-ben |

### Orchestráció és felügyelet

Az orchestrációs réteg felelős a teljes pipeline koordinálásáért — a specifikáció feldolgozásától a végső merge-ig. A sentinel a felügyelő, amely az orchestrátort újraindítja crash esetén.

| Eszköz | Funkció |
|--------|---------|
| `wt-orchestrate` | Teljes orchestrációs pipeline (ez a dokumentum tárgya) |
| `wt-sentinel` | Orchestrátor felügyelő: crash recovery, checkpoint kezelés |
| `wt-manual` | Kézi orchestrációs beavatkozás (debug, state edit) |
| `wt-e2e-report` | E2E teszt eredmények összesítése és riportálás |

### Memória és kontextus

A memória rendszer biztosítja, hogy az ágensek tanuljanak a korábbi session-ökből. Minden projekt saját memória-adatbázissal rendelkezik, amely a fontos döntéseket, tanulságokat és kontextust tárolja. A hook rendszer automatikusan injektálja a releváns memóriákat az ágens kontextusába.

| Eszköz | Funkció |
|--------|---------|
| `wt-memory` | Memória CLI: remember, recall, forget, search, sync |
| `wt-hook-memory` | Automatikus memória injekció (SessionStart, PostTool) |
| `wt-hook-memory-warmstart` | Session indítás: releváns memóriák betöltése |
| `wt-hook-memory-recall` | Prompt-szintű téma-alapú memória visszahívás |
| `wt-hook-memory-posttool` | Eszköz-használat utáni kontextus kiegészítés |
| `wt-hook-memory-save` | Session végi memória mentés és extrakció |

### Projekt menedzsment

A `wt-project` rendszer biztosítja, hogy az új és meglévő projektek egyetlen paranccsal beállíthatók legyenek — hookak, parancsok, skill-ek telepítése, projekt regisztráció. Az `init` parancs idempotens: újrafuttatása frissíti a telepített fájlokat anélkül, hogy a konfigurációt felülírná.

| Eszköz | Funkció |
|--------|---------|
| `wt-project` | Projekt inicializálás, hook telepítés, regisztráció |
| `wt-config` | Globális és projekt-szintű konfiguráció kezelés |
| `wt-deploy-hooks` | Claude Code hookak telepítése projekthez |
| `wt-version` | Verziószám megjelenítés |
| `wt-usage` | Token használati statisztikák |

### Csapat szinkronizáció

A team sync lehetővé teszi több fejlesztő (vagy ágens) közötti kommunikációt — üzenetküldés, aktivitás megosztás, memória szinkronizáció. A `wt-control` egy git orphan branch-et használ a kommunikációs csatornaként.

| Eszköz | Funkció |
|--------|---------|
| `wt-control` | Team sync: üzenetküldés, aktivitás, koordináció |
| `wt-control-init` | Team sync inicializálás (orphan branch) |
| `wt-control-sync` | Szinkronizáció: push/pull üzenetek és aktivitás |
| `wt-control-chat` | Csevegés más ágensekkel / fejlesztőkkel |
| `wt-control-gui` | Grafikus team dashboard |
| `wt-hook-activity` | Automatikus aktivitás megosztás |

### OpenSpec és minőség

Az OpenSpec a strukturált fejlesztési workflow: a proposal-tól a design-on és a task-okon át az implementációig. Az audit és review eszközök biztosítják, hogy a minőségi kapuk ne csak az orchestrációban, hanem a kézi fejlesztésben is működjenek.

| Eszköz | Funkció |
|--------|---------|
| `wt-openspec` | OpenSpec artifact kezelés (proposal, design, tasks) |
| `wt-audit` | Kód audit: security, minőség, best practices |

## Projekt sablonok

A `wt-project` rendszer sablon-alapú. Jelenleg két sablon érhető el, de a rendszer nyitott bármilyen technológiai stack-re:

### wt-project-base

Az alap sablon, amely minden projekthez használható. Tartalmazza:

- Claude Code hookak (memória, activity, skill dispatch)
- `/wt:*` parancsok (orchestrate, decompose, help)
- OpenSpec skillek (fast-forward, apply, verify)
- Sentinel szabályok
- Alapértelmezett `.claude/` konfiguráció

### wt-project-web (Next.js)

A web alkalmazásokhoz készült sablon, a `wt-project-base` kiterjesztése. Tartalmazza:

- Next.js specifikus konfigurációk
- Tesztelési stratégia (Jest + Playwright)
- Adatbázis kezelés (Prisma/Drizzle támogatás)
- `smoke_command` és `e2e_command` előkonfigurálás
- Fejlesztési szerver kezelés

### Más irányok

A sablon rendszer szándékosan nyitott. A `wt-project-web` a Next.js irányt mutatja, de bármilyen más technológiai stack támogatható saját sablonnal:

- **wt-project-api** — REST/GraphQL API backend-ek
- **wt-project-mobile** — React Native, Flutter alkalmazások
- **wt-project-python** — Python/FastAPI/Django projektek
- **wt-project-scraper** — Adatgyűjtő és feldolgozó projektek

Ezek a sablonok a `wt-project-base`-re épülnének, és a projekt-specifikus konfigurációt, tesztelési stratégiát, és build pipeline-t adnák hozzá.

## Az ökoszisztéma térképe

```
┌─────────────────────────────────────────────────────────┐
│                    wt-tools ökoszisztéma                 │
├──────────────┬──────────────┬───────────────────────────┤
│  Worktree    │  Orchestráció │  Memória & Kontextus     │
│  lifecycle   │  & felügyelet │                          │
│              │              │                           │
│  wt-new      │  wt-orchestr.│  wt-memory               │
│  wt-list     │  wt-sentinel │  wt-hook-memory-*        │
│  wt-status   │  wt-manual   │                          │
│  wt-merge    │  wt-e2e-rep. │                          │
│  wt-close    │              │                          │
│  wt-loop     │              │                          │
├──────────────┼──────────────┼───────────────────────────┤
│  Projekt     │  Team Sync   │  OpenSpec & Minőség      │
│  menedzsment │              │                          │
│              │  wt-control  │  wt-openspec             │
│  wt-project  │  wt-ctrl-*   │  wt-audit               │
│  wt-config   │  wt-hook-act.│  /opsx:* skillek        │
│  wt-deploy   │              │                          │
├──────────────┴──────────────┴───────────────────────────┤
│  Projekt sablonok                                       │
│  wt-project-base │ wt-project-web │ wt-project-...     │
└─────────────────────────────────────────────────────────┘
```

\begin{fontos}
Az ökoszisztéma moduláris: nem kötelező mindent használni. A legegyszerűbb belépési pont a wt-new + wt-loop (egyetlen ágens, egyetlen worktree). Az orchestráció és a memória rendszer fokozatosan, szükség szerint kapcsolható be.
\end{fontos}
