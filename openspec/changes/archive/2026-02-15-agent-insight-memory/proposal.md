## Why

Az OpenSpec agent értékes felismeréseket (pattern-ek, döntési indoklások, architekturális meglátások) termel az artifact-készítés és explore fázisokban, de ezek elvesznek. Jelenleg a memory hookök csak a **user által kimondott** tudást mentik mid-flow-ban, és az agent saját meglátásait csak az apply (Step 7) és archive fázisoknál. Az explore teljesen memory-mentes a recall-on kívül, a continue/ff pedig nem reflektál a session végén. Emellett a verify és sync-specs skillek sem használják a memóriát.

Eközben a shodh-memory v0.1.75 jelentős új képességeket kínál (proactive_context, enhanced recall modes, tag-based filtering, forget operations), amiket a `set-memory` CLI még nem expoze-ol — pedig ezek közvetlenül javítanák a memory hookök hatékonyságát.

## What Changes

### set-memory CLI upgrade (shodh-memory v0.1.75 képességek)
- **Forget operations**: `forget <id>`, `forget --all`, `forget --older-than`, `forget --tags`, `forget --pattern`
- **Enhanced recall**: `--tags` filter, `--mode` (semantic/temporal/hybrid/causal/associative)
- **Introspection**: `context` (condensed summary), `brain` (3-tier visualization), `get`/`inspect` (single memory)
- **Maintenance**: `health --index`, `repair`
- **Enhanced list**: `--type` és `--limit` filterek

### OpenSpec SKILL.md memory hook fejlesztések
- **Agent self-reflection step** hozzáadása a continue, ff és explore skillek végéhez — az agent visszanézi a session-ben született saját meglátásait és lementi őket
- **Explore remember** bővítése: az agent saját felismerései is menthetők (jelenleg csak user-shared knowledge van)
- **Verify-change** memory hookök: recall a verifikáció előtt, remember a talált problémákból/tanulságokból
- **Sync-specs** memory hookök: döntések mentése a spec merge során
- **Enhanced recall** használata a hookökban: `--mode hybrid --tags change:<name>` a pontosabb recall-ért
- **Tagging strategy** egységesítése: `change:<name>`, `phase:<skill>`, `source:agent` vs `source:user` megkülönböztetés
- **Invalid type fix**: a meglévő `Observation` és `Event` típusok lecserélése `Learning`/`Context`-re

## Capabilities

### New Capabilities
- `agent-self-reflection`: Agent session-végi self-reflection step a continue, ff és explore skillekben — az agent összegyűjti és lementi a session közben született saját meglátásait (döntési indoklások, felfedezett pattern-ek, architekturális felismerések)
- `shodh-cli-upgrade`: A `set-memory` CLI bővítése a shodh-memory v0.1.75 új képességeivel (forget, enhanced recall, introspection, maintenance)

### Modified Capabilities
- `skill-hook-automation`: Memory hookök kiterjesztése a verify-change és sync-specs skillekre, enhanced recall használata, agent-source meglátások mentése, invalid type-ok javítása

## Impact

- **Érintett fájlok**: `bin/set-memory` (CLI bővítés), 6 SKILL.md fájl (explore, continue, ff, verify, sync-specs, apply)
- **Kódváltozás**: `bin/set-memory` bash script — új commands, enhanced existing commands
- **Nincs breaking change**: meglévő CLI felület változatlan, új funkciók additívak
- **Docs**: `docs/developer-memory.md`, `docs/readme-guide.md`, `README.md` frissítés
- **Backwards compatible**: meglévő memóriák zavartalanul működnek, új tag-ek additívak
