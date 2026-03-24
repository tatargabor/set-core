# Input és Konfiguráció

## Input módok

Az orchestrátor háromféle bemenetet fogad el. Ezek kölcsönösen kizárják egymást.

![Input módok és konfiguráció feloldás](diagrams/rendered/01-input-modes.png){width=90%}

### 1. Specifikáció mód (`--spec`)

A legtöbb projekt specifikációs dokumentumokkal dolgozik:

```bash
set-orchestrate --spec docs/v3.md plan
set-orchestrate --spec v12 plan          # rövidnév: set/orchestration/specs/v12.md
set-orchestrate --spec docs/ plan         # egész könyvtár
```

A `--spec` egy fájlra vagy könyvtárra mutathat. Könyvtár esetén a rendszer az összes `.md` fájlt feldolgozza, és a `scan_spec_directory()` függvény felépíti a teljes képet.

**Fázis szűrés**: A `--phase` opcióval egy adott fázisra lehet szűkíteni:

```bash
set-orchestrate --spec docs/v3.md --phase 2 plan    # csak a 2. fázis
set-orchestrate --spec docs/v3.md --phase "Security" plan  # szöveges szűrés
```

### 2. Brief mód (`--brief`)

A korábbi, egyszerűbb formátum egy `### Next` szekciót használ a roadmap elemek felsorolásához:

```markdown
## Feature Roadmap
### Next
- Auth rendszer: JWT alapú autentikáció
- User profil: Profil szerkesztés és avatar
### Later
- Admin panel: Felhasználó kezelés
```

### 3. Auto-detect

Ha sem `--spec`, sem `--brief` nincs megadva, a rendszer automatikusan keres:

1. `openspec/project-brief.md` — ha van benne `### Next` elem
2. `openspec/project.md` — fallback
3. Hiba, ha egyik sem található

## Konfiguráció

A viselkedést három szinten lehet konfigurálni. A magasabb szint felülírja az alacsonyabbat:

```
CLI flag  >  orchestration.yaml  >  dokumentum direktívák  >  alapértelmezés
```

### orchestration.yaml

A fő konfigurációs fájl a `.claude/orchestration.yaml` (vagy `wt/orchestration.yaml`):

```yaml
# Végrehajtás
max_parallel: 3               # max párhuzamos change
merge_policy: checkpoint       # eager | checkpoint | manual
checkpoint_every: 3            # checkpoint N change után

# Tesztelés
test_command: "pnpm test"      # tesztelő parancs
test_timeout: 300              # teszt timeout (mp)
smoke_command: "pnpm build"    # smoke test parancs
smoke_blocking: true           # smoke fail blokkolja-e a merge-t

# Modellek
default_model: opus            # implementációs model
review_model: sonnet           # review model
summarize_model: haiku         # összegzéshez használt model

# Review
review_before_merge: true      # LLM review a merge előtt
max_verify_retries: 2          # verify retry limit

# Automatizálás
auto_replan: true              # auto-plan a következő fázisra
context_pruning: true          # context window optimalizálás
model_routing: "off"           # model routing stratégia

# Biztonság
token_budget: 5000000          # soft limit (figyelmeztetés)
token_hard_limit: 20000000     # hard limit (emberi jóváhagyás)
time_limit: "5h"               # futási idő limit

# Hookak
post_merge_command: "pnpm db:generate"
hook_pre_dispatch: ""
hook_post_verify: ""
hook_pre_merge: ""
hook_post_merge: ""
hook_on_fail: ""
```

### Dokumentum direktívák

A specifikáción belül is megadhatók direktívák:

```markdown
## Orchestrator Directives
- max_parallel: 4
- merge_policy: eager
- token_budget: 100000
```

A rendszer a `parse_directives()` függvénnyel olvassa ki ezeket az értékeket.

\begin{fontos}
A CLI flag mindig nyer. Ha `--max-parallel 5` van a parancssorban, az felülírja mind a YAML, mind a dokumentum direktívákat.
\end{fontos}

## Direktíva referencia

| Direktíva | Típus | Alapértelmezés | Leírás |
|-----------|-------|---------------|--------|
| `max_parallel` | szám | 3 | Max párhuzamos worktree |
| `merge_policy` | enum | checkpoint | eager/checkpoint/manual |
| `checkpoint_every` | szám | 3 | Checkpoint gyakoriság |
| `test_command` | string | "" | Tesztelő parancs |
| `test_timeout` | szám | 300 | Teszt timeout (mp) |
| `smoke_command` | string | "" | Smoke test parancs |
| `smoke_blocking` | bool | true | Smoke fail blokkolja-e a merge-t |
| `smoke_fix_max_retries` | szám | 3 | Smoke fix retry limit |
| `e2e_command` | string | "" | E2E teszt parancs |
| `e2e_mode` | enum | per_change | per_change/phase_end |
| `default_model` | string | opus | Implementációs model |
| `review_model` | string | sonnet | Review model |
| `review_before_merge` | bool | false | LLM review engedélyezése |
| `max_verify_retries` | szám | 2 | Verify retry limit |
| `auto_replan` | bool | false | Auto-replan a fázis végén |
| `token_budget` | szám | 0 | Soft token limit |
| `token_hard_limit` | szám | 20M | Hard token limit |
| `time_limit` | string | 5h | Futási idő limit |
| `watchdog_timeout` | szám | 600 | Watchdog timeout (mp) |
| `context_pruning` | bool | true | Context optimalizálás |
| `model_routing` | string | off | Model routing stratégia |
| `post_merge_command` | string | "" | Merge utáni parancs |
