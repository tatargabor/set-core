# Ruflo (ruvnet/ruflo) Kutatás — 2026-03-10

> Átfogó kutatás a ruflo (korábban claude-flow) orchestration platformról,
> kifejezetten a set-core-ba átvehető minták szemszögéből.

## Háttér

- **Repo:** https://github.com/ruvnet/ruflo (~20k star, MIT)
- **Nyelv:** TypeScript/Node.js monorepo (`v3/@claude-flow/`)
- **Valódi forráskód:** ~1,500 sor (`v3/src/`), a többi prompt template és wrapper
- **Fontos:** a README enterprise feature-öket ígér, de a kód sokszor stub:
  - Consensus = `Math.random()` (nem Raft/Byzantine)
  - SQLite backend = in-memory `Map` (nem SQLite)
  - Agent task execution = callback stub mesterséges delay-jel

## I. NEM átvehető minták

| Feature | Miért nem |
|---------|-----------|
| 60+ agent type | Prompt templatek, nem futtatható logika |
| Queen/Hive-mind metafora | Prompt engineering, zero tényleges koordináció |
| Swarm topológiák (mesh, ring, Byzantine) | Interface van, implementáció nincs |
| WASM "352x speedup" | Nincs benchmark kód |
| DDD over-abstraction | ICoordinator→ICoordinationManager→IOrchestrator boilerplate |
| TOML config migráció | A YAML approach jól működik |
| Spec digest | **Nincs** — agent olvassa a specet in-context, nincs pre-processing |

## II. Átvehető minták (prioritás szerint)

### P1: Work Stealing (claims modul)

A ruflo legerősebb modulja. Jól megtervezett domain model.

**Forrásfájl:** `v3/@claude-flow/claims/src/`

**Állapotgép:**
```
active → stealable → stolen (+ contest mechanizmus)
```

**Stealable okok:** `stale` (nincs aktivitás N percig), `blocked` (külső dep), `overloaded`, `timeout`

**Contest:** eredeti agent `contestSteal()` → queen/human dönt a winner-ről

**set-core alkalmazás:** Amikor Ralph loop 3+ iteráció nulla haladás → change `stealable`
→ sentinel új worktree-be re-dispatch-ol fresh context-tel.
Jelenleg ez manuális beavatkozás.

### P1: Task dependency gráf + blokkolás-érvényesítés

**Forrásfájl:** `v3/src/task-execution/domain/Task.ts`

```typescript
SubTask { id, dependencies: string[], requiredCapabilities[], recommendedDomain }
// + topologikus rendezés ciklus-detektálással
```

**set-core alkalmazás:** A planner `depends_on` mezőt generál, de a dispatcher
nem mindig tartja tiszteletben. Explicit `blockedBy` tracking + topologikus
rendezés a dispatch sorrendhez.

### P1: Agent scoring formula task assignment-hoz

**Forrásfájl:** `v3/@claude-flow/swarm/src/coordinators/queen-coordinator.ts`

```
totalScore = capability(0.30) + load(0.20) + performance(0.25)
           + health(0.15) + availability(0.10)
```

**set-core alkalmazás:** Jelenleg round-robin-szerű dispatch. Score-alapú
dispatch jobb lenne: magas error rate → alacsony score → kevesebb task.

### P2: Circuit Breaker + Exponential Backoff

**Forrásfájl:** `v3/@claude-flow/shared/src/resilience/`

- **Circuit breaker:** CLOSED→OPEN→HALF_OPEN, rolling window, volume threshold
- **Retry:** jitter + backoff multiplier + per-attempt timeout + retryableErrors filter
- **Bulkhead:** max concurrent executions + overflow queue

**set-core alkalmazás:**
- API hívásokra: N egymást követő fail → circuit open → ne pazarolj tokent
- Meglévő `set-loop` backoff generalizálása `retry_with_backoff()` függvénnyé
- Bulkhead = `max_parallel_changes` + queue, ami már részben létezik

### P2: Health Monitor (agent-szintű egészség)

**Forrásfájl:** `v3/@claude-flow/shared/src/core/orchestrator/health-monitor.ts`

```
errorRate = errors / (completed + failed)
→ healthy (<20%), degraded (20-50%), unhealthy (>50%)
```

**set-core alkalmazás a watchdog/sentinel-ben:**
- Rolling error rate worktree-nként
- 30s-onkénti health check: token consumption rate, iteráció/progress ráta
- Degraded worktree → alacsonyabb dispatch priority

### P2: Priority message queue

```
urgent > high > normal > low
```

Graceful degradation: overflow → lowest-priority drop.

**set-core alkalmazás:** Sentinel beavatkozás = urgent, task completion = normal,
heartbeat = low. A jelenlegi flat `send_message` nem priorizál.

### P3: Event correlation/causation ID-k

```typescript
DomainEvent { causationId, correlationId }
```

**set-core alkalmazás:** Run log post-mortem elemzéshez — planner_decision →
dispatch → agent_failure → replan lánc összekapcsolása.

### P3: ReasoningBank (korábbi megoldások újrafelhasználása)

Sikeres reasoning trajectory-k tárolása embedding-gel → hasonló feladatnál
retrieve past solution as context.

**set-core alkalmazás:** shodh-memory már support-olja, explicit integrálás
kell az orchestrator dispatch-be.

### P3: Confidence decay stale memóriákra

Régi, nem megerősített memóriák confidence-je csökken → automatikus
prioritás-csökkentés retrieval-nál.

### P4: Event Sourcing (state recovery) — long-term

Append-only event log + snapshot + replay. A state.yaml korrupció ellen véd.
Csak ha a korrupció ismétlődő probléma lesz.

## III. set-core előnyei ruflo-val szemben

| Szempont | set-core | ruflo |
|----------|----------|-------|
| Valódi multi-process | Claude Code worktree-kben | In-memory callback stub |
| Spec digest | `digest.sh` — domain decomposition | Nincs |
| State management | Git-alapú, tartós | In-memory Map |
| Verification | Valódi verifier pipeline | Nincs |
| Battle-tested | sales-raketa produkció | Nincs produkciós evidence |
| Requirement traceability | REQ-ID → change → coverage | Flat tasks |

## IV. Összesített prioritási mátrix

| Minta | Erőfeszítés | Hatás | Prioritás |
|-------|-------------|-------|-----------|
| Work Stealing (stale detect + re-dispatch) | Közepes | Magas | **P1** |
| Dependency gráf enforcement | Alacsony | Magas | **P1** |
| Agent scoring (dispatch) | Alacsony | Magas | **P1** |
| Circuit breaker (API) | Alacsony | Közepes | **P2** |
| Health classification (watchdog) | Közepes | Közepes | **P2** |
| Priority message queue | Közepes | Közepes | **P2** |
| Event correlation IDs | Alacsony | Alacsony | **P3** |
| ReasoningBank integration | Közepes | Közepes | **P3** |
| Confidence decay | Alacsony | Alacsony | **P3** |
| Event sourcing | Nagyon magas | Magas | **P4** |
