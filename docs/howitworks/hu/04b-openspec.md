# OpenSpec — A Spec-Driven Workflow

## Mi az OpenSpec?

Az OpenSpec egy strukturált fejlesztési workflow, amely minden változtatást (change) fázisokon vezet végig, mielőtt az implementáció elkezdődne. A cél: az AI ágens ne "csak kódoljon", hanem *értse meg* a feladatot, és nyomon követhető döntéseket hozzon.

A fázisok:

```
Proposal (MIÉRT)  →  Design (HOGYAN)  →  Specs (MIT)  →  Tasks (CSINÁLD)  →  Implementáció
```

## Az artifact-ok

### Proposal

A *miért* dokumentum: motiváció, scope, sikerkritériumok. Az orchestrátor a plan-ből **előre generálja** a proposal-t a worktree-ben, a roadmap item és scope alapján — az ágens ezt kapja kiindulásként.

### Design

A *hogyan* dokumentum: technikai döntések ADR (Architecture Decision Record) formátumban, kockázatok, alternatívák. Az ágens generálja a proposal-ból.

### Specs

A *mit* dokumentum: részletes követelmények BDD (Given/When/Then) formátumban, delta műveletek (ADDED, MODIFIED, REMOVED). Minden követelmény tesztelhető szcenáriókkal.

### Tasks

A *csináld* lista: checkbox-os feladatlista, amit az ágens az implementáció során egyenként pipál. A `[?]` jelölés manuális (emberi) feladatot jelöl — API kulcs beszerzés, külső szolgáltatás beállítás.

```markdown
- [x] Add JWT middleware to /api/* routes
- [x] Create login endpoint with bcrypt
- [ ] Add refresh token rotation
- [?] Configure OAuth provider credentials
```

## Integráció az orchestrációval

### Dispatch fázis

A `dispatcher.sh` a worktree létrehozásakor:

1. Létrehozza a change könyvtárat (`openspec new change`)
2. **Előre generálja a proposal-t** a plan scope-jából
3. Bemásolja a spec kontextust (digest módban)
4. Hozzáfűzi a cross-cutting fájlok listáját, a szomszédos change-ek státuszát, és a memória kontextust

### Ralph loop integráció

A Ralph loop az OpenSpec artifact-ok állapota alapján dönt:

```
Ha nincs tasks.md → action: ff (fast-forward, minden artifact létrehozása)
Ha van tasks.md  → action: apply (implementáció)
Ha minden kész   → action: done
```

Az `ff` fázisban az ágens a `/opsx:ff` skillt futtatja: egyetlen session-ben létrehozza a design-t, specs-et és tasks-ot a proposal-ból. Az `apply` fázisban a `/opsx:apply` skillt futtatja: a tasks.md alapján implementálja a feladatokat.

### FF→Apply láncolás

Korábban az artifact-generálás (ff) és az implementáció (apply) két külön iterációban futott, és az iteráció-határ kontextusvesztést okozott. A jelenlegi verzió egyetlen iteráción belül láncolja: az ff befejezése után azonnal indul az apply, friss kontextussal.

## Interaktív vs. orchestrált használat

| Mód | Parancsok | Mikor |
|-----|-----------|-------|
| **Interaktív** | `/opsx:new` → `/opsx:continue` → `/opsx:apply` → `/opsx:verify` → `/opsx:archive` | Fejlesztő egyedül dolgozik, lépésenként |
| **Fast-forward** | `/opsx:ff` → `/opsx:apply` → `/opsx:archive` | Fejlesztő, de nincs idő lépésenkéntre |
| **Orchestrált** | Automatikus — a dispatcher és Ralph loop kezeli | `wt-orchestrate start` |

## Nyomkövethetőség

Az OpenSpec teljes nyomkövetési láncot biztosít:

```
Spec szekció (v3.md)
  → Requirement ID (REQ-042)
    → Change hozzárendelés (platform-dashboard)
      → Proposal: "Ez a change a REQ-042-t fedi le"
        → Tasks: "KPI kártyák hozzáadása"
          → Git commit: a REQ-042-t implementáló kód
```

A verify gate nem csak a kód minőségét, hanem a **követelmény-megfelelőséget** is ellenőrzi: a review prompt tartalmazza a hozzárendelt REQ-XXX azonosítókat.

\begin{fontos}
Az OpenSpec az orchestráció és a végrehajtás közötti szerződés. Az orchestrátor létrehozza a proposal-t; az ágens létrehozza a design-t, specs-et és tasks-ot; a verify gate ellenőrzi az implementációt. Ha bármelyik fázis hiányzik, a rendszer tudja, hol tart és mi a következő lépés.
\end{fontos}

## Limitációk

- **FF kudarcok**: Az `/opsx:ff` néha nem hozza létre a tasks.md-t (nagy spec, truncált LLM válasz). Ilyenkor a loop fallback tasks-ot generál a proposal-ból
- **Manuális feladatok**: A `[?]` jelölésű feladatok (API kulcsok, external setup) emberi beavatkozást igényelnek — az orchestráció ezeket nem tudja automatizálni
- **Nagy change-ek**: 14+ requirement egy change-ben → megbízhatatlan. A planner max 6 REQ/change szabályt alkalmaz
