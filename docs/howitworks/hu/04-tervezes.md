# Tervezés

## A dekompozíció célja

A tervezési fázis a specifikációt (vagy digest-et) **végrehajtható change-ekre** bontja. Minden change egy önálló, jól definiált fejlesztési feladat, amelyet egy AI ágens egy worktree-ben hajt végre.

![Dekompozíció és DAG generálás](diagrams/rendered/03-planning-dag.png){width=90%}

## Tervezési módszerek

Két tervezési módszer létezik, a `plan_method` direktíva vezérli:

### API mód (alapértelmezett)

Egyetlen Claude API hívás végzi a dekompozíciót:

```bash
set-orchestrate --spec docs/v3.md plan   # plan_method: api (default)
```

Előnyök:

- Gyors (1-2 perc)
- Kevés token használat
- Determinisztikus kimenet

### Agent mód

Egy dedikált worktree-ben egy Ralph loop végzi a tervezést, több iterációban:

```yaml
# orchestration.yaml
plan_method: agent
plan_token_budget: 500000
```

Ez a módszer akkor hasznos, ha:

- A specifikáció nagyon összetett
- A planner-nek kódot kell olvasnia a jó dekompozícióhoz
- A tesztelési infrastruktúra felderítése szükséges

## A Plan struktúra

A `cmd_plan()` eredménye az `orchestration-plan.json`:

```json
{
  "plan_version": 1,
  "brief_hash": "a1b2c3d4",
  "plan_phase": "phase-2",
  "plan_method": "api",
  "changes": [
    {
      "name": "auth-system",
      "scope": "JWT autentikáció implementálása a /api/* végpontokon",
      "complexity": "L",
      "change_type": "feature",
      "depends_on": [],
      "roadmap_item": "Auth rendszer",
      "requirements": ["REQ-001", "REQ-004"],
      "also_affects_reqs": ["REQ-012"],
      "model": null,
      "skip_review": false,
      "skip_test": false
    },
    {
      "name": "user-profile",
      "scope": "Profil szerkesztés és avatar feltöltés",
      "complexity": "M",
      "depends_on": ["auth-system"],
      "requirements": ["REQ-002", "REQ-003"]
    }
  ]
}
```

### Mezők magyarázata

| Mező | Leírás |
|------|--------|
| `name` | Egyedi azonosító (ez lesz a branch neve: `change/auth-system`) |
| `scope` | Részletes leírás az ágens számára |
| `complexity` | S (small), M (medium), L (large) — token limit meghatározáshoz |
| `change_type` | feature, fix, refactor, test, docs, config |
| `depends_on` | Függőségek (más change nevek) |
| `requirements` | Hozzárendelt REQ-XXX azonosítók |
| `also_affects_reqs` | Cross-cutting követelmények (figyelemfelhívás) |
| `model` | Change-specifikus model override (null = default) |
| `skip_review` | Review gate kihagyása (pl. config change-eknél) |
| `skip_test` | Test gate kihagyása (pl. docs change-eknél) |

## Topológiai rendezés (DAG)

A `topological_sort()` függvény a `depends_on` mezők alapján egy irányított aciklikus gráfot (DAG) épít, és topológiai sorrendben adja vissza a change-eket.

**Szabályok**:

1. Függőség nélküli change-ek párhuzamosan indulhatnak
2. Egy change csak akkor indulhat, ha minden függősége `merged` státuszban van
3. Körkörös függőség → hiba a plan generálásnál

**Példa**: Ha A ← B és A ← C, de D ← B,C:

```
T1: A (nincs függőség)
T2: B, C (párhuzamosan, A merged után)
T3: D (B és C merged után)
```

### Körkörös függőség detekció

```bash
# A self-test tartalmaz tesztet:
set-orchestrate self-test
# → PASS: circular dependency detected
```

Ha a planner körkörös függőséget generál, a rendszer hibát dob és a plan-t el kell vetni.

## Tesztelési infrastruktúra felderítés

A `detect_test_infra()` függvény a plan fázisban felméri a projekt tesztelési képességeit:

- **Framework**: vitest, jest, pytest, mocha
- **Config fájlok**: vitest.config.ts, jest.config.js, stb.
- **Teszt fájlok**: `*.test.*`, `*.spec.*`, `test_*.py`
- **Helper könyvtárak**: `src/test/`, `__tests__/`

Ez az információ bekerül a planner prompt-ba, hogy a change-ek scope-ja tartalmazza a tesztelést is.

## Spec összegzés nagy dokumentumokhoz

Ha a spec túl nagy (sok ezer token), a `summarize_spec()` egy haiku modellel összegzi az anyagot, mielőtt a planner megkapná:

1. Az összegző kivonja a fázis struktúrát
2. Azonosítja a kész és hiányzó részeket
3. A planner csak a releváns fázist kapja meg

\begin{fontos}
A plan mindig megtekinthető a generálás után: `set-orchestrate plan --show`. A `start` parancs kiadása előtt érdemes ellenőrizni, hogy a dekompozíció ésszerű-e.
\end{fontos}

## Plan validálás

A generált plan-t a rendszer automatikusan validálja:

- Minden change névnek egyedinek kell lennie
- A `depends_on` hivatkozásoknak létező change-ekre kell mutatniuk
- Körkörös függőség nem megengedett
- A `complexity` értéknek S, M vagy L-nek kell lennie

Ha a validálás sikertelen, a plan nem mentődik és hibaüzenetet kap a felhasználó.
