# Shodh-Memory Integration Audit

**Date**: 2026-02-16
**Scope**: set-core ↔ shodh-memory v0.1.75 integration audit
**Method**: GitHub docs + local Python API + CLI introspection + memory data analysis

---

## Executive Summary

A shodh-memory-t **részlegesen** használjuk. Az alapvető remember/recall ciklus működik, de a rendszer legértékesebb kognitív képességei (tudásgráf, Hebbian tanulás, proaktív kontextus, strukturált döntés-rögzítés) **teljesen kihasználatlanok**. Az 56 memóriánk mögött egy üres tudásgráf áll (0 csomópont, 0 él), ami azt jelenti, hogy az asszociatív és kauzális recall módok puszta aliasok a szemantikus keresésre.

```
┌─────────────────────────────────────────────────────────────────┐
│                    CURRENT vs POTENTIAL                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  USED (35%)              │  UNUSED (65%)                       │
│  ────────────            │  ────────────                       │
│  ✓ remember (plain text) │  ✗ proactive_context                │
│  ✓ recall (semantic)     │  ✗ record_decision + DecisionContext│
│  ✓ context_summary       │  ✗ record_failure + root_cause      │
│  ✓ brain_state           │  ✗ find_similar_decisions            │
│  ✓ export/import         │  ✗ find_failures                    │
│  ✓ sync push/pull        │  ✗ reinforce (Hebbian feedback)     │
│  ✓ forget (by id)        │  ✗ recall_by_tags (1ms vs 50ms!)   │
│  ✓ health/repair         │  ✗ recall_by_date                   │
│  ✓ list/get              │  ✗ forget_by_importance              │
│                          │  ✗ Entity extraction / NER           │
│                          │  ✗ Knowledge graph traversal         │
│                          │  ✗ metadata structured fields        │
│                          │  ✗ is_failure / is_anomaly flags     │
│                          │  ✗ batch remember                    │
│                          │  ✗ consolidation monitoring          │
│                          │  ✗ MCP server (37 tools)             │
│                          │  ✗ GTD todo/project system            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. CRITICAL: Üres tudásgráf

### A probléma

```
graph_stats() → {
  "node_count": 0,
  "edge_count": 0,
  "avg_strength": 0.0,
  "potentiated_count": 0
}
```

56 memóriánk van, de a Knowledge Graph **teljesen üres**. Ez azt jelenti:

- **Entitás-kinyerés (NER) nem működik** — shodh rendelkezik TinyBERT NER modellel (15MB), ami embereket, szervezeteket, helyeket ismer fel. De a CLI wrapperünk egyszerű szöveget küld, ami lehet hogy nem triggereli az NER pipeline-t.
- **Hebbian tanulás nem történik** — nincs mit erősíteni, ha nincs gráf
- **Asszociatív recall = szemantikus recall** — gráf nélkül a spreading activation nem működik
- **Kauzális recall = szemantikus recall** — ok-okozati láncolás gráf nélkül lehetetlen

### Bizonyíték

```python
# Minden mód AZONOS eredményt ad, azonos sorrendben:
semantic     → ['2fbeac52', '07347602']
temporal     → ['2fbeac52', '07347602']
hybrid       → ['2fbeac52', '07347602']
causal       → ['2fbeac52', '07347602']
associative  → ['2fbeac52', '07347602']
```

### Hatás

A `--mode causal` és `--mode associative` paramétereink az explore és apply skill-ekben **nulla értéket adnak** — placebó effektus. Ugyanúgy viselkednek, mint a `--mode semantic`.

### Lehetséges ok

A `set-memory remember` CLI plaintext-ként küldi a tartalmat a Python API-nak, ami talán nem futtatja az NER-t automatikusan. A REST API-n és az MCP szerveren keresztül a `remember` endpoint más útvonalat járhat.

### Ajánlott vizsgálat

1. Tesztelni, hogy a Python API `m.remember(content, entities=[...])` explicit entitásokkal működik-e
2. Ellenőrizni, hogy a NER modell betöltődik-e lokális módban (nincs szerver)
3. Ha a NER nem fut automatikusan, explicit entitás-kinyerést implementálni a CLI wrapperben

---

## 2. CRITICAL: Memória-tier hierarchia nem működik

### A probléma

```python
get_stats() → {
  "working_memory_count": 0,
  "session_memory_count": 0,
  "long_term_memory_count": 56,
  "promotions_to_session": 0,
  "promotions_to_longterm": 0,
  "total_memories": 56
}
```

A Cowan-féle 3-szintű memória-hierarchia (Working → Session → Long-term) **nem működik**. Minden memória közvetlenül a long-term-be kerül, nincs promóció, nincs working/session szint.

### Valószínű ok

A CLI wrapper állapotmentes (stateless). Nincs session koncepció — minden parancs egy új Python `Memory()` objektumot hoz létre, használ, majd eldobja. A working/session tier valószínűleg a folyamatosan futó szerver módban vagy a Python API hosszú életű objektumánál működik.

### Hatás

- **Aktiváció-decay nem funkcionál** — nincs ami gyengüljön, minden azonnal long-term
- **Memory replay nem történik** — a konszoldáció üres
- **Importance-based promotion nem történik** — minden azonos szinten van

### Consolidation report bizonyíték

```python
consolidation_report() → {
  "stats": {
    "memories_strengthened": 0,
    "memories_decayed": 0,
    "edges_formed": 0,
    "edges_strengthened": 0,
    "facts_extracted": 0,
    "maintenance_cycles": 0
  }
}
```

---

## 3. HIGH: proactive_context — a legnagyobb kiaknázatlan lehetőség

### Mi ez?

A `proactive_context` nem explicit query-t kér, hanem **kontextust** (pl. ami éppen történik a beszélgetésben), és automatikusan felszínre hozza a releváns memóriákat. Visszaad `relevance_score` és `relevance_reason` értékeket.

### Teszt

```python
m.proactive_context(
    "working on benchmark analysis",
    max_results=2, auto_ingest=False
)
# → 2 releváns memória, relevance_score: 0.54 és 0.49
# → relevance_reason: "recent_and_relevant", "semantic_similarity"
```

### Miért fontos?

Jelenleg a recall minőségét az határozza meg, milyen jó query-t ír az agens:
```
# Jelenlegi mód (recall-dependent):
Agent → "Mire emlékezzek?" → recall("benchmark design") → eredmények

# Proaktív mód:
Agent → proactive_context("Change 4: user dashboard") → automatikus releváns emlékek
```

A `proactive_context` megoldja az "agent elfelejti mit keressen" problémát, mert nem kell query-t formulázni.

### Ajánlott integrációs pontok

| Hely | Jelenleg | Ajánlott |
|------|----------|----------|
| Skill indítás | `recall "<change-name>"` | `proactive_context "<change-name> + proposal tartalom>"` |
| CLAUDE.md ambient | `recall "<topic>"` | `proactive_context "<current task context>"` |
| set-hook-memory-recall | shell recall | proactive_context Python API |
| Session bootstrap | `context_summary` | `proactive_context` + `context_summary` kombinálva |

---

## 4. HIGH: Strukturált döntés-rögzítés (record_decision)

### Mi ez?

A `record_decision` strukturált formában rögzíti a döntéseket:

```python
from shodh_memory import DecisionContext, Outcome

context = DecisionContext(
    state={"task": "choose-database", "requirements": ["offline", "simple"]},
    action_params={"choice": "sqlite"},
    confidence=0.8,
    alternatives=["postgres", "redis"]
)

outcome = Outcome(
    outcome_type="success",
    details="SQLite worked well for offline use case",
    reward=0.9,
    prediction_accurate=True
)

m.record_decision(
    description="Chose SQLite over Postgres for offline-first requirement",
    action_type="design-decision",
    decision_context=context,
    outcome=outcome
)
```

### Miért fontos?

1. **find_similar_decisions** keresés: "Amikor legutóbb hasonló döntést hoztam, mi lett belőle?"
2. **Outcome tracking**: A döntés eredménye rögzítve van (success/failure/partial)
3. **Confidence + alternatives**: Tudod, mennyire voltál biztos, és mit fontoltál meg
4. **RL-style reward**: -1.0 és 1.0 közötti értékelés a döntés minőségéről

### Jelenlegi helyzet

```python
find_similar_decisions("design-decision", ...) → 0 results
```

Nulla strukturált döntés van rögzítve. Az összes döntés plain text `remember` hívásokkal van mentve.

### Ajánlott használat

Az OpenSpec design.md fázisban hozott döntéseket `record_decision`-nal kellene rögzíteni, nem plain text `remember`-rel. Ez lehetővé tenné:
- "Milyen hasonló design döntéseket hoztunk korábban?" → `find_similar_decisions`
- "Melyik döntéseink lettek sikertelenek?" → `find_failures` + outcome filtering

---

## 5. HIGH: Hebbian Reinforcement (reinforce)

### Mi ez?

Explicit visszajelzés a memória-rendszernek: "Ez a memória hasznos volt / nem volt hasznos".

### Miért fontos?

Jelenleg az `access_count` a legtöbb memóriánál 0 (vagy 1 a recall miatt). A Hebbian tanulás szabálya: 5+ ko-aktiváció → Long-Term Potentiation (10x lassabb decay). De ha nincs feedback loop, a rendszer nem tanul meg különbséget tenni a hasznos és haszontalan memóriák között.

### Ajánlott integrációs pont

Amikor az agens felhasznál egy memóriát (pl. recall eredménye befolyásolja a kódot), a `reinforce` API-val jelezni kellene a sikerességet. Ez különösen fontos az apply fázisban.

---

## 6. MEDIUM: Memória-minőség problémák

### Importance eloszlás

```
Importance < 0.3:  16 memories (29% — ZAJ!)
Importance 0.3-0.5: 34 memories (61%)
Importance > 0.5:   6 memories (11%)
```

A memóriák közel harmada alacsony fontosságú, jellemzően "implementation complete" típusú jegyzetek:
- `"memory-browse-upgrade: implementation complete — ..."`
- `"Benchmark v3 results documented"`
- `"test type check"`

### Forrás-eloszlás

```
source:agent:  45 (80%) — döntő többség agens-generált
source:user:    8 (14%) — kevés emberi döntés
nincs source:   3 (5%)
```

### Type eloszlás problémája

A `set-memory list` API-n a `memory_type` mező `"unknown"` értéket ad vissza, míg a `list_memories()` Python API helyesen `experience_type`-ot mutat. Ez egy bug a CLI wrapper és a Python API közötti mismatch-ben.

### Ajánlások

1. **Rendszeres cleanup**: `set-memory forget --pattern "^(memory-|bulk-archive|wire-memory)" --dry-run` tesztelése
2. **forget_by_importance**: Havi `forget_by_importance(threshold=0.2)` futtatása
3. **Deduplikáció**: 2 pár közel-duplikát van (bulk-archive-memory-hooks)

---

## 7. MEDIUM: recall_by_tags — gyors strukturált keresés

### Mi ez?

Tag-alapú keresés embedding nélkül — ~1ms vs ~50ms szemantikus.

### Miért fontos?

Amikor tudjuk, mit keresünk (pl. "minden döntés erről a change-ről"), a tag-alapú keresés sokkal gyorsabb és precízebb:

```python
# Lassú és bizonytalan:
recall("memory-save-reminder-hook design decisions", mode="semantic")

# Gyors és pontos:
recall_by_tags(["change:memory-save-reminder-hook", "decision"])
```

### Jelenlegi helyzet

A `recall_by_tags` soha nincs használva a skill-ekben vagy a CLAUDE.md-ben. Minden recall szemantikus.

### Ajánlott használat

- Skill induláskor: `recall_by_tags(["change:<name>"])` — az adott change összes memóriája
- Design fázisban: `recall_by_tags(["decision"])` — összes döntés

---

## 8. MEDIUM: metadata mező kihasználása

### Jelenlegi helyzet

56 memóriából 53-nak `metadata: {}` (üres), 3-nak `metadata: {"original_id": "..."}` (importált).

### Mit lehetne tárolni?

```python
metadata = {
    "change_name": "add-dark-mode",          # OpenSpec change
    "artifact": "design.md",                  # Melyik artifact-hoz kapcsolódik
    "git_sha": "abc123",                      # Milyen commit állapotban született
    "file_paths": ["gui/theme.py"],           # Érintett fájlok
    "openspec_phase": "design",               # Melyik fázisban
    "skill": "opsx:explore",                  # Melyik skill hívta
    "session_id": "abc-def",                  # Claude session ID
}
```

### Miért fontos?

1. **Traceability**: Honnan jött ez a memória, milyen kontextusban
2. **Filtered recall**: A metadata mezők alapján szűrni (a Python API támogatja)
3. **Debug**: Ha egy memória rossz, visszakövetni az eredetét

---

## 9. LOW: Consolidation és maintenance

### Jelenlegi helyzet

A konszoldáció teljesen inaktív:
```
consolidation_report → event_count: 0, zero everything
```

### Lehetséges ok

A konszoldáció valószínűleg a szerver módban (folyamatosan futó process) történik, nem a CLI wrapper-en keresztül. A CLI wrapper minden híváskor létrehoz egy Memory objektumot és megsemmisíti.

### Ajánlás

Periodikus maintenance script, amely:
1. Betölti a Memory objektumot
2. Futtat consolidation cycle-t
3. Ellenőrzi az index health-et
4. Takarítja az alacsony fontosságú memóriákat

---

## 10. LOW: MCP szerver mód és GTD

### Mi ez?

A shodh-memory MCP szerverként 37 tool-t kínál, beleértve egy komplett GTD (Getting Things Done) task management rendszert:
- Projektek (create, list, archive, delete)
- Todo-k (create, update, complete, reorder, subtasks)
- Ismétlődő feladatok
- Kontextusok (@computer, @phone, stb.)
- Emlékeztetők

### Relevanciánk

Az MCP szerver mód és a GTD rendszer **nem releváns** a jelenlegi CLI-alapú integrációnkhoz. A `set-memory` CLI wrapper a Python library-t használja közvetlenül, nem MCP-n keresztül. Ez helyes megközelítés — az MCP szerver mód overhead-et adna a lokális használathoz.

A GTD rendszer duplikálná az OpenSpec task management-et (`tasks.md`), tehát nem ajánlott bevezetni.

---

## Összefoglaló: Prioritizált akcióterv

### P0 — Azonnal vizsgálandó

| # | Probléma | Hatás | Művelet |
|---|----------|-------|---------|
| 1 | Üres Knowledge Graph | asszociatív/kauzális recall nem működik | Vizsgálni, miért nincs NER; explicit entitás-kinyerés tesztelése |
| 2 | Tier hierarchia nem működik | konszoldáció, decay, promóció inaktív | Vizsgálni szerver mód vs library mód különbségét |

### P1 — Következő iteráció

| # | Lehetőség | Hatás | Művelet |
|---|-----------|-------|---------|
| 3 | proactive_context | Jobb recall, kevesebb félretett memória | set-memory CLI-be + skill hooks-ba integrálni |
| 4 | record_decision | Strukturált döntés-keresés | set-memory CLI `decide` parancs + design skill hook |
| 5 | reinforce API | Hebbian tanulás beindítása | set-memory CLI `reinforce` parancs + apply skill hook |
| 6 | recall_by_tags | 50x gyorsabb strukturált keresés | set-memory CLI `recall --tags-only` flag |

### P2 — Minőségjavítás

| # | Lehetőség | Hatás | Művelet |
|---|-----------|-------|---------|
| 7 | forget_by_importance | Zaj csökkentése | Periodikus cleanup script vagy set-memory subcommand |
| 8 | metadata gazdagítás | Traceability, szűrés | set-memory remember --metadata flag |
| 9 | is_failure flag | Hiba-minta felismerés | set-memory remember --failure flag |
| 10 | recall_by_date | Temporális keresés | set-memory recall --date-range flag |

### P3 — Karbantartás

| # | Lehetőség | Hatás | Művelet |
|---|-----------|-------|---------|
| 11 | Konszoldáció trigger | Memória-evolúció | Periodikus maintenance script |
| 12 | Duplikátum-takarítás | Kevesebb zaj | Egyszeri cleanup |
| 13 | Recall mód audit | Helyes dokumentáció | --mode causal/associative eltávolítása amíg graph nem működik |

---

## Függelék: Teljes API felszín

### Használt API metódusok (set-memory CLI-n keresztül)

| API | CLI parancs | Hol használjuk |
|-----|------------|----------------|
| `remember()` | `set-memory remember` | CLAUDE.md, SKILL.md hooks, Stop hook, transcript extraction |
| `recall()` | `set-memory recall` | CLAUDE.md, SKILL.md hooks, explore, apply, ff skills |
| `context_summary()` | `set-memory context` | Session bootstrap |
| `brain_state()` | `set-memory brain` | GUI, debug |
| `list_memories()` | `set-memory list` | GUI browse dialog, analysis |
| `get_memory()` | `set-memory get` | GUI card detail |
| `forget()` | `set-memory forget` | GUI, manual cleanup |
| `forget_by_age()` | `set-memory forget --older-than` | Manual cleanup |
| `forget_by_tags()` | `set-memory forget --tags` | Manual cleanup |
| `forget_by_pattern()` | `set-memory forget --pattern` | Manual cleanup |
| `forget_all()` | `set-memory forget --all` | Reset |
| `index_health()` | `set-memory health --index` | Monitoring |
| `verify_index()` | `set-memory health --index` | Monitoring |
| `repair_index()` | `set-memory repair` | Maintenance |

### Nem használt API metódusok

| API | Leírás | Prioritás |
|-----|--------|-----------|
| `proactive_context()` | Kontextus-alapú automatikus recall | **P1** |
| `record_decision()` | Strukturált döntés-rögzítés | **P1** |
| `record_failure()` | Strukturált hiba-rögzítés | **P1** |
| `find_similar_decisions()` | Hasonló döntések keresése | **P1** |
| `find_failures()` | Hiba-minta keresés | **P1** |
| `recall_by_tags()` | Tag-alapú gyors keresés | **P1** |
| `recall_by_date()` | Dátum-tartomány keresés | **P2** |
| `forget_by_importance()` | Importancia-alapú takarítás | **P2** |
| `forget_by_date()` | Dátum-tartomány takarítás | **P3** |
| `graph_stats()` | Tudásgráf monitorozás | **P2** |
| `consolidation_report()` | Konszoldáció monitorozás | **P3** |
| `consolidation_events()` | Konszoldáció részletek | **P3** |
| `record_anomaly()` | Anomália rögzítés | N/A (robotika) |
| `record_sensor()` | Szenzor-adat rögzítés | N/A (robotika) |
| `record_obstacle()` | Akadály rögzítés | N/A (robotika) |
| `record_waypoint()` | Waypoint rögzítés | N/A (robotika) |
| `start_mission()` / `end_mission()` | Mission lifecycle | N/A (robotika) |

### Shodh architektúra referencia

```
┌─────────────────────────────────────────────────────────────┐
│                      SHODH-MEMORY                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐      │
│  │ Working  │───▶│ Session  │───▶│   Long-Term      │      │
│  │ Memory   │    │ Memory   │    │   Memory         │      │
│  │ 100 LRU  │    │ 500MB    │    │   (RocksDB+LZ4)  │      │
│  │ <1ms     │    │ <10ms    │    │   <100ms          │      │
│  └──────────┘    └──────────┘    └──────────────────┘      │
│       ↕               ↕                ↕                    │
│  ┌──────────────────────────────────────────────────┐      │
│  │              Knowledge Graph                      │      │
│  │  ┌────────┐  ┌────────┐  ┌────────────────┐     │      │
│  │  │Entities│──│ Edges  │──│ Hebbian        │     │      │
│  │  │ (NER)  │  │(causal)│  │ Learning       │     │      │
│  │  └────────┘  └────────┘  └────────────────┘     │      │
│  └──────────────────────────────────────────────────┘      │
│       ↕                                                     │
│  ┌──────────────────────────────────────────────────┐      │
│  │              Search Layer                         │      │
│  │  ┌─────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │      │
│  │  │Semantic │ │Temporal│ │ Causal │ │Assoc.  │  │      │
│  │  │(Vamana) │ │(decay) │ │(graph) │ │(spread)│  │      │
│  │  │384d emb.│ │        │ │        │ │        │  │      │
│  │  └─────────┘ └────────┘ └────────┘ └────────┘  │      │
│  └──────────────────────────────────────────────────┘      │
│                                                             │
│  ┌──────────────────────────────────────────────────┐      │
│  │              Storage                              │      │
│  │  RocksDB + Vamana HNSW + BM25 + TinyBERT NER    │      │
│  └──────────────────────────────────────────────────┘      │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Current set-core usage path:
  CLI → remember() → Long-Term (bypasses Working/Session)
  CLI → recall()   → Semantic only (no graph = no associative/causal)

Optimal usage path:
  CLI → remember() with entities → All tiers + Graph
  CLI → proactive_context() → Smart retrieval with scores
  CLI → record_decision() → Structured + find_similar
  CLI → reinforce() → Hebbian learning feedback loop
```
