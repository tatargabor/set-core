## Why

A wt-tools production bugok (sales-raketa tapasztalat) 90%-a a komponensek közti interakcióból ered — nem az izolált funkciókból. A jelenlegi tesztek (unit, orchestrator parse) nem fedik le a teljes flow-t: project bootstrap → spec → plan → dispatch → implement → smoke → merge → archive. Egy valódi, végig futtatható test projektre van szükség ahol a teljes pipeline-t teszteljük, és git checkpoint-okkal visszatérhetünk javítás után.

## What Changes

- Új test projekt scaffold: "MiniShop" — minimális Express.js API webshop, better-sqlite3 lokális DB-vel, Jest tesztekkel
- Üzleti spec dokumentum (`v1-minishop.md`) ami az orchestrator bemenetéül szolgál — 4 egymásra épülő change-dzsel (products CRUD → cart → orders → auth)
- E2E runner script (`tests/e2e/run.sh`) ami a scaffold-ot friss git repo-ba klónozza, `wt-project init --project-type web`-et futtat, és felkészíti a sentinel futtatásra
- Git tag-alapú checkpoint rendszer a runner-ben — minden fázis után tag, hogy javítás után visszatérhessünk
- A teszt a valódi wt-tools pipeline-t használja (sentinel → orchestrate → wt-loop), nincs mock — a valódi bugok valódian jönnek elő

## Capabilities

### New Capabilities
- `e2e-scaffold`: MiniShop Express API projekt scaffold — package.json, src/, tests/, docs/ — működő `npm test`-tel az első pillanattól
- `e2e-spec`: Üzleti specifikáció a MiniShop-hoz az orchestrator formátumában — 4 change dependency gráffal és cross-cutting auth-tal
- `e2e-runner`: Runner script és checkpoint infrastruktúra — scaffold klónozás, wt-project init, git tag-ek, checkpoint-ból folytatás

### Modified Capabilities

## Impact

- Új könyvtár: `tests/e2e/` (scaffold/, fixtures nem kellenek — valódi teszt)
- Függőség: Node.js + npm a test projekthez (már elérhető a dev gépen)
- Token költség futásonként: ~600K-1M token (~$6-15) — de production bug-ok megelőzése ennél nagyságrendekkel többe kerül
- Nem érinti a meglévő wt-tools kódot — tisztán additív
