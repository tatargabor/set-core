## Why

MiniShop run10 bizonyította: a Figma MCP regisztrálva volt, a spec explicit kérte az agentek használatát, a design-snapshot.md teljes tartalommal a repoban volt — mégsem érvényesült a design. Az agentek shadcn default-okra építettek (fekete primary a kék helyett, kisebb betűméretek, hiányzó shadow-ok, eltérő layout-ok).

A gyökérok: a design-snapshot.md tartalma csak a **planner** prompt-ba jut el (aki scope szövegeket ír), de a planner "matching Figma X frame" szöveges hivatkozássá desztillálja. A **tényleges tokenek, hierarchiák és vizuális specifikációk** elvesznek a fordításban. Az agent egy opcionális `design_ref` stringet kap a proposal-ba, amit figyelmen kívül hagy.

## What Changes

- **Design context injection a dispatcher-ben**: A `dispatch_change()` a design-snapshot.md releváns részeit (tokenek + érintett frame hierarchia) közvetlenül az agent proposal.md-jébe injektálja, nem csak egy egysoros `design_ref`-et
- **Ralph loop design-awareness**: A Ralph loop detektálja a design-snapshot.md-t a project root-ban és CLAUDE.md-n keresztül emlékezteti az agentet a design token használatára
- **Verify gate design compliance check**: A review prompt-ba design token összehasonlítás kerül — a diff-ben használt szín/spacing/typography osztályokat ellenőrzi a design-snapshot.md token értékei ellen

## Capabilities

### New Capabilities
- `design-dispatch-injection`: Design snapshot tartalom injektálása a dispatch proposal-ba — az agent közvetlenül kapja a frame hierarchiát és token értékeket
- `design-verify-gate`: Design fidelity ellenőrzés a verify gate-ben — token/class összehasonlítás a design-snapshot.md ellen

### Modified Capabilities
- `design-snapshot`: A meglévő spec frissítése — snapshot tartalom nem csak a planner-nek, hanem az agent-nek is eljut
- `design-bridge`: A meglévő spec frissítése — rule erősítése passzívból aktívvá

## Impact

- `lib/orchestration/dispatcher.sh` — `dispatch_change()` design injection
- `lib/design/bridge.sh` — új `design_context_for_agent()` függvény (frame-szűrt snapshot rész)
- `lib/orchestration/verifier.sh` — `review_change()` design compliance section
- `.claude/rules/design-bridge.md` — erősebb, imperatív szabály
- `lib/set_orch/templates.py` — review template design section
