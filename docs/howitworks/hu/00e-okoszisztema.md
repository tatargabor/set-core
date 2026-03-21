# A set-core ökoszisztéma

## Áttekintés

A `set-orchestrate` nem egyedül áll — egy tágabb eszközkészlet része, amely a teljes AI-asszisztált fejlesztési workflow-t lefedi. A `set-core` csomag CLI eszközöket, hookokat, memória rendszert, és projekt sablonokat tartalmaz.

## A fő eszközök

### Worktree lifecycle

Ezek az eszközök a git worktree-k teljes életciklusát kezelik — a létrehozástól a merge-ig és a cleanup-ig. Minden ágens izolált worktree-ben dolgozik, saját branch-en, anélkül, hogy a fő ágat zavarná.

| Eszköz | Funkció |
|--------|---------|
| `set-new` | Új worktree és branch létrehozása, .claude/ inicializálás |
| `set-list` | Aktív worktree-k listázása, állapot összefoglaló |
| `set-status` | Részletes ágens-állapot: PID, iteráció, token, modell |
| `set-merge` | Worktree merge main-be, LLM conflict resolution |
| `set-close` | Worktree cleanup (branch törlés, könyvtár eltávolítás) |
| `set-focus` | Ágens-váltás: terminál fókusz a kiválasztott worktree-re |
| `set-add` | Meglévő branch hozzáadása worktree-ként |

### Ágens futtatás

A Ralph loop a `set-loop` által vezérelt iteratív fejlesztési ciklus. Az ágens minden iterációban kódot ír, teszteket futtat, és az eredmény alapján dönt a folytatásról. A loop automatikusan kezeli a context window limiteket, a token budgetet, és az API rate limiteket.

| Eszköz | Funkció |
|--------|---------|
| `set-loop` | Ralph iteratív loop: max-turns, token budget, model routing |
| `set-work` | Interaktív munka session worktree-ben |
| `set-skill-start` | Skill-alapú session indítás worktree-ben |

### Orchestráció és felügyelet

Az orchestrációs réteg felelős a teljes pipeline koordinálásáért — a specifikáció feldolgozásától a végső merge-ig. A sentinel a felügyelő, amely az orchestrátort újraindítja crash esetén.

| Eszköz | Funkció |
|--------|---------|
| `set-orchestrate` | Teljes orchestrációs pipeline (ez a dokumentum tárgya) |
| `set-sentinel` | Orchestrátor felügyelő: crash recovery, checkpoint kezelés |
| `set-manual` | Kézi orchestrációs beavatkozás (debug, state edit) |
| `set-e2e-report` | E2E teszt eredmények összesítése és riportálás |

### Memória és kontextus

A memória rendszer biztosítja, hogy az ágensek tanuljanak a korábbi session-ökből. Minden projekt saját memória-adatbázissal rendelkezik, amely a fontos döntéseket, tanulságokat és kontextust tárolja. A hook rendszer automatikusan injektálja a releváns memóriákat az ágens kontextusába.

| Eszköz | Funkció |
|--------|---------|
| `set-memory` | Memória CLI: remember, recall, forget, search, sync |
| `set-hook-memory` | Automatikus memória injekció (SessionStart, PostTool) |
| `set-hook-memory-warmstart` | Session indítás: releváns memóriák betöltése |
| `set-hook-memory-recall` | Prompt-szintű téma-alapú memória visszahívás |
| `set-hook-memory-posttool` | Eszköz-használat utáni kontextus kiegészítés |
| `set-hook-memory-save` | Session végi memória mentés és extrakció |

### Projekt menedzsment

A `set-project` rendszer biztosítja, hogy az új és meglévő projektek egyetlen paranccsal beállíthatók legyenek — hookak, parancsok, skill-ek telepítése, projekt regisztráció. Az `init` parancs idempotens: újrafuttatása frissíti a telepített fájlokat anélkül, hogy a konfigurációt felülírná.

| Eszköz | Funkció |
|--------|---------|
| `set-project` | Projekt inicializálás, hook telepítés, regisztráció |
| `set-config` | Globális és projekt-szintű konfiguráció kezelés |
| `set-deploy-hooks` | Claude Code hookak telepítése projekthez |
| `set-version` | Verziószám megjelenítés |
| `set-usage` | Token használati statisztikák |

### Csapat szinkronizáció

A team sync lehetővé teszi több fejlesztő (vagy ágens) közötti kommunikációt — üzenetküldés, aktivitás megosztás, memória szinkronizáció. A `set-control` egy git orphan branch-et használ a kommunikációs csatornaként.

| Eszköz | Funkció |
|--------|---------|
| `set-control` | Team sync: üzenetküldés, aktivitás, koordináció |
| `set-control-init` | Team sync inicializálás (orphan branch) |
| `set-control-sync` | Szinkronizáció: push/pull üzenetek és aktivitás |
| `set-control-chat` | Csevegés más ágensekkel / fejlesztőkkel |
| `set-control-gui` | Grafikus team dashboard |
| `set-hook-activity` | Automatikus aktivitás megosztás |

### OpenSpec és minőség

Az OpenSpec a strukturált fejlesztési workflow: a proposal-tól a design-on és a task-okon át az implementációig. Az audit és review eszközök biztosítják, hogy a minőségi kapuk ne csak az orchestrációban, hanem a kézi fejlesztésben is működjenek.

| Eszköz | Funkció |
|--------|---------|
| `set-openspec` | OpenSpec artifact kezelés (proposal, design, tasks) |
| `set-audit` | Kód audit: security, minőség, best practices |

## Projekt típusok és modulok

A `set-project` rendszer moduláris. Az alap profil (`CoreProfile`) a set-core magjába integrált, a projekt-specifikus típusok pedig a `modules/` könyvtárban vagy külső plugin-ként érhetők el.

### CoreProfile (set-core beépített)

Az alap profil, amely minden projekthez használható. A `lib/set_orch/profile_loader.py` (`CoreProfile`) és `lib/set_orch/profile_types.py` (ABC) tartalmazza:

- Claude Code hookak (memória, activity, skill dispatch)
- `/set:*` parancsok (orchestrate, decompose, help)
- OpenSpec skillek (fast-forward, apply, verify)
- Sentinel szabályok
- Alapértelmezett `.claude/` konfiguráció

### Web modul — `modules/web/` (Next.js)

A web alkalmazásokhoz készült modul, a `CoreProfile` kiterjesztése (`WebProjectType`). Helye: `modules/web/set_project_web/`. Tartalmazza:

- Next.js specifikus konfigurációk
- Tesztelési stratégia (Jest + Playwright)
- Adatbázis kezelés (Prisma/Drizzle támogatás)
- `smoke_command` és `e2e_command` előkonfigurálás
- Fejlesztési szerver kezelés

### Példa modul — `modules/example/`

A Dungeon Builder példaprojekt, amely bemutatja hogyan készíthető egyedi projekt típus plugin.

### Külső plugin-ek

A modul rendszer szándékosan nyitott. A beépített modulokon túl bármilyen más technológiai stack támogatható külső plugin-ként (entry_points):

- **set-project-api** — REST/GraphQL API backend-ek
- **set-project-mobile** — React Native, Flutter alkalmazások
- **set-project-python** — Python/FastAPI/Django projektek
- **set-project-scraper** — Adatgyűjtő és feldolgozó projektek

Ezek a plugin-ek a `CoreProfile`-ra épülnének, és a projekt-specifikus konfigurációt, tesztelési stratégiát, és build pipeline-t adnák hozzá. A profil feloldás sorrendje: entry_points → közvetlen import → beépített modules/ → NullProfile.

## Az ökoszisztéma térképe

```
┌─────────────────────────────────────────────────────────┐
│                    set-core ökoszisztéma                 │
├──────────────┬──────────────┬───────────────────────────┤
│  Worktree    │  Orchestráció │  Memória & Kontextus     │
│  lifecycle   │  & felügyelet │                          │
│              │              │                           │
│  set-new      │  set-orchestr.│  set-memory               │
│  set-list     │  set-sentinel │  set-hook-memory-*        │
│  set-status   │  set-manual   │                          │
│  set-merge    │  set-e2e-rep. │                          │
│  set-close    │              │                          │
│  set-loop     │              │                          │
├──────────────┼──────────────┼───────────────────────────┤
│  Projekt     │  Team Sync   │  OpenSpec & Minőség      │
│  menedzsment │              │                          │
│              │  set-control  │  set-openspec             │
│  set-project  │  set-ctrl-*   │  set-audit               │
│  set-config   │  set-hook-act.│  /opsx:* skillek        │
│  set-deploy   │              │                          │
├──────────────┴──────────────┴───────────────────────────┤
│  Projekt típusok (monorepo)                              │
│  CoreProfile (beépített) │ modules/web/ │ modules/example/ │
└─────────────────────────────────────────────────────────┘
```

\begin{fontos}
Az ökoszisztéma moduláris: nem kötelező mindent használni. A legegyszerűbb belépési pont a set-new + set-loop (egyetlen ágens, egyetlen worktree). Az orchestráció és a memória rendszer fokozatosan, szükség szerint kapcsolható be.
\end{fontos}
