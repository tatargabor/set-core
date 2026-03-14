## Context

A design bridge pipeline már létezik (`lib/design/bridge.sh`), és a planner (`lib/orchestration/planner.sh`) használja is: a `design_prompt_section()` a teljes design-snapshot.md-t injektálja a decompose prompt-ba. A planner LLM tehát **látja** a design tokeneket és frame hierarchiákat.

A probléma az, hogy a planner output-ja — a scope szöveg — csak szöveges hivatkozásokat tartalmaz ("matching Figma AdminLogin frame"), és a dispatcher (`lib/orchestration/dispatcher.sh`) csak egy opcionális `design_ref` stringet ír a proposal-ba ("Query the design tool for: `AdminLogin`"). Az agent tehát nem kapja meg:
1. A konkrét design tokeneket (színek, spacing, typography)
2. A frame-specifikus component hierarchiát
3. A vizuális specifikációkat

Az agent-nek van Figma MCP-je (`design-bridge.md` rule mondja, hogy használja), de a rule passzív ("if available... query"), és a verify gate nem ellenőrzi a design compliance-t.

**Érintett fájlok jelenlegi állapota:**
- `lib/orchestration/dispatcher.sh:421-428` — design_ref injection (1 sor)
- `lib/design/bridge.sh:84-138` — `design_prompt_section()` (planner-only)
- `lib/orchestration/verifier.sh:134-188` — `review_change()` (no design check)
- `.claude/rules/design-bridge.md` — passzív rule
- `lib/wt_orch/templates.py` — review template (no design section)

## Goals / Non-Goals

**Goals:**
- Design-snapshot tartalom eljut a dispatch proposal-ba (frame-szűrt részlet, nem a teljes snapshot)
- Design tokenek (primary color, radius, typography) bekerülnek a review prompt-ba és ellenőrizhetők
- A design-bridge rule imperatívvá válik (MUST query, not "if available")

**Non-Goals:**
- Visual regression testing (screenshot comparison) — az egy külön change
- Figma MCP hívás kényszerítése az agent-en (nem tudjuk megakadályozni, hogy kihagyja — de jobb kontextust adunk)
- Planner módosítása — a planner már jól működik, a design_context eljut hozzá

## Decisions

### D1: Frame-szűrt design context az agent proposal-ba

A `dispatch_change()` a `design-snapshot.md`-ből kiemeli a releváns frame-ek hierarchiáját és a design tokeneket, és a proposal.md-be injektálja — nem a teljes snapshot-ot (ami túl nagy), hanem:
1. **Design Tokens** szekciót (mindig — ez globális)
2. **Releváns frame hierarchiák** — a scope szövegben említett frame nevek alapján szűrve

Ehhez új function kell: `design_context_for_dispatch()` a `bridge.sh`-ban.

**Alternative considered:** Teljes snapshot beinjektálása → rejected mert az agent proposal 2x-3x megnő, és a legtöbb frame nem releváns egy change-hez.

**Alternative considered:** Agent-re bízni a snapshot olvasást (file a repo-ban van) → rejected mert a MiniShop run10 bizonyította: ha nem kapja meg az agent explicit, nem olvassa el.

### D2: Design compliance section a review prompt-ban

A `review_change()` prompt-ba kerül egy "Design Compliance" szekció:
- Ha van `design-snapshot.md`, kiemeli a design tokeneket (elsősorban colors, typography, radius)
- A reviewer-t instruálja: ellenőrizze, hogy a diff-ben használt Tailwind osztályok konzisztensek-e a design tokenekkel
- Nem CRITICAL ha eltérés van, hanem WARNING — a design eltérés nem blokkolja a merge-t, de jelzi

**Alternative considered:** CRITICAL severity a design eltérésekre → rejected mert túl sok false positive lenne (pl. az agent szándékosan más spacing-et használ mert a design nem fedi le azt az edge case-t).

### D3: Imperatív design-bridge rule

A `.claude/rules/design-bridge.md` frissül:
- "if available" → "MUST query before implementing"
- Explicit utasítás: "Read design-snapshot.md in the project root BEFORE implementing any UI component"
- Token-lista referencia: "Use the exact color/spacing/typography values from design tokens"

### D4: Design token checker a verifier prompt-ban

A review template (`templates.py`) kap egy `design_compliance` szekciót:
- Csak ha van design-snapshot.md a project root-ban
- Kiemeli a design tokeneket (colors, radius, fonts)
- Instruálja a reviewer-t specifikus pattern-ek keresésére:
  - `bg-blue-600` vs `bg-primary` (ha a primary != blue)
  - `text-3xl` vs `text-2xl` (typography eltérés)
  - `shadow-md` jelenlét/hiány
  - `rounded-full` vs `rounded` (badge pill style)

## Risks / Trade-offs

- **[Token lista elavulhat]** → Ha a Figma design változik de a snapshot nem frissül, az agent rossz tokeneket kap. Mitigation: a replan cycle force-re-fetch-el.
- **[Frame szűrés pontatlan]** → A scope szöveg nem mindig tartalmazza a frame nevet pontosan. Mitigation: fuzzy matching (case-insensitive, contains) + fallback a teljes tokens szekció.
- **[Review false positives]** → A design reviewer WARNING-ot adhat olyan eltérésre amit az agent szándékosan csinált. Mitigation: WARNING, nem CRITICAL — nem blokkolja a merge-t.
- **[Proposal méret növekedés]** → A frame hierarchia + tokenek ~50-100 sor extra. Mitigation: max 150 sor limit a design injection-re, utána truncate.
