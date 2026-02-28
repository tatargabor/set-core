# pm-guide-chapters Specification

## Purpose
TBD - created by archiving change pm-guide-agentic-development. Update Purpose after archive.
## Requirements
### Requirement: Chapter I — AI fordulópont (2024)
A dokumentum SKAL tartalmaznia egy bevezető fejezetet ami az AI fejlődés kronológiáját mutatja be (GPT-3 → Claude 3.5 → Claude 4.6), a 2024 őszi SWE-bench eredményeket, és az AI jelenlegi képességeit/korlátait. A fejezet célja a kontextus felépítése nem-technikai olvasó számára.

#### Scenario: PM olvassa a bevezető fejezetet
- **WHEN** az olvasó megnyitja a dokumentumot
- **THEN** a fejezet 6-8 oldalon elmagyarázza az AI kódolás forradalmát, hivatkozik az Anthropic SWE-bench kutatásra, és világossá teszi miért releváns ez egy PM számára

#### Scenario: Kronológia áttekinthetősége
- **WHEN** az olvasó a kronológiát nézi
- **THEN** idővonal vagy táblázat formátumban látja a főbb mérföldköveket 2022-től 2026-ig

### Requirement: Chapter II — Claude Code bemutatása
A dokumentum SKAL tartalmaznia egy fejezetet ami részletesen bemutatja a Claude Code eszközt: mi ez, hol fut (terminál, IDE, desktop, web), az agentic loop koncepciója, eszközök (Read, Edit, Bash, stb.), CLAUDE.md, hookrendszer, MCP, subágensek. Konkrét példával illusztrálva.

#### Scenario: Agentic loop megértése
- **WHEN** az olvasó a Claude Code fejezetet olvassa
- **THEN** ASCII diagram mutatja a Gondol → Cselekszik → Ellenőriz ciklust, és szöveges magyarázat kíséri

#### Scenario: MCP koncepció
- **WHEN** az olvasó az MCP-ről olvas
- **THEN** az "USB-C az AI-nak" analógia és hivatkozás a modelcontextprotocol.io-ra megjelenik

#### Scenario: Claude Code dokumentáció hivatkozások
- **WHEN** az olvasó többet szeretne tudni
- **THEN** minden alfejezetben megjelennek a releváns Anthropic dokumentáció linkek

### Requirement: Chapter III — Vibe Coding vs Spec-Driven Development
A dokumentum SKAL tartalmaznia egy fejezetet ami elmagyarázza a vibe coding fogalmát (Karpathy, 2025 feb), a kontextus/minőség/skálázás problémákat, és szembeállítja a spec-driven megközelítéssel összehasonlító táblázattal.

#### Scenario: Vibe coding definíció
- **WHEN** az olvasó a vibe coding fejezethez ér
- **THEN** Karpathy idézettel és egyszerű példával illusztrálva érti meg miről van szó

#### Scenario: Összehasonlító táblázat
- **WHEN** az olvasó a fejezet végéhez ér
- **THEN** táblázat hasonlítja össze a vibe coding-ot és spec-driven fejlesztést sebesség, minőség, nyomon követhetőség, PM rálátás és skálázhatóság szempontjából

#### Scenario: Kontextus ablak probléma
- **WHEN** az olvasó a technikai problémákról olvas
- **THEN** ASCII vizualizáció mutatja a kontextus ablak telítődését és hatását

### Requirement: Chapter IV — OpenSpec specifikáció-vezérelt fejlesztés
A dokumentum SKAL tartalmaznia egy fejezetet ami bemutatja az OpenSpec rendszert: Proposal → Specs → Design → Tasks → Implementation pipeline, artifact típusok, PM szerepe a workflow-ban.

#### Scenario: Pipeline vizualizáció
- **WHEN** az olvasó az OpenSpec fejezetet olvassa
- **THEN** ASCII diagram mutatja az artifact-ok láncolatát és mindegyik mellett rövid magyar leírás van

#### Scenario: PM munkafolyamat
- **WHEN** az olvasó a PM szerepéről olvas
- **THEN** konkrét példa mutatja hogyan ír a PM proposal-t, review-olja a specifikációt, és hogyan implementál az AI

#### Scenario: Artifact tartalom bemutatása
- **WHEN** az olvasó az artifact típusokról olvas
- **THEN** minden artifact típushoz van egy rövid (5-10 soros) példa ami mutatja milyen tartalom kerül bele

### Requirement: Chapter V — Párhuzamos AI ágensek és orchestráció
A dokumentum SKAL tartalmaznia egy fejezetet ami bemutatja a git worktree koncepcióját (PM-barát módon), a Ralph Loop-ot, az orchestrátor működését (spec → DAG → párhuzamos végrehajtás → merge), merge policy-kat, és a GUI dashboard-ot.

#### Scenario: Worktree koncepció PM-nek
- **WHEN** az olvasó a worktree-kről olvas
- **THEN** egyszerű analógia (pl. "mint amikor 5 fejlesztő 5 külön mappában dolgozik") és ASCII diagram mutatja a párhuzamos munkaterületeket

#### Scenario: Orchestrátor DAG vizualizáció
- **WHEN** az olvasó az orchestrátorról olvas
- **THEN** ASCII diagram mutatja egy konkrét példán hogyan bomlik fel egy spec dokumentum change-ekre és függőségi gráfra

#### Scenario: Valós számok
- **WHEN** az olvasó az eredményekről olvas
- **THEN** konkrét számok mutatják: N change, M párhuzamos ágens, X óra → ami hagyományosan Y napba kerülne

### Requirement: Chapter VI — Memória és tanulás
A dokumentum SKAL tartalmaznia egy fejezetet a Developer Memory rendszerről: a "minden session nulláról indul" probléma, memória típusok (Decision, Learning, Context), az 5 rétegű hook rendszer egyszerűsítve, és csapat szintű memória szinkronizáció.

#### Scenario: Memória probléma bemutatása
- **WHEN** az olvasó a memória fejezethez ér
- **THEN** előtte/utána példa mutatja hogyan viselkedik az AI memória nélkül vs. memóriával

#### Scenario: Hook rendszer egyszerűsítve
- **WHEN** az olvasó a hook rendszerről olvas
- **THEN** maximum 5 pont mutatja az 5 réteget PM-barát nyelven, technikai részletek nélkül

### Requirement: Chapter VII — A szoftverfejlesztés jövője
A dokumentum SKAL tartalmaznia egy záró fejezetet ami bemutatja a rövid/közép/hosszú távú trendet, a PM szerep átalakulását, az iparági szereplőket (Claude Code, Copilot, Cursor, Devin), kockázatokat, és ami NEM fog eltűnni.

#### Scenario: PM szerep evolúciója
- **WHEN** az olvasó a jövőről olvas
- **THEN** vizualizáció mutatja a MA → HOLNAP → HOLNAPUTÁN átmenetet a PM munkafolyamatban

#### Scenario: Iparági összehasonlítás
- **WHEN** az olvasó az eszközökről olvas
- **THEN** táblázat hasonlítja össze a főbb AI fejlesztői eszközöket (Claude Code, Copilot, Cursor, Devin) fő jellemzők mentén

### Requirement: Függelék
A dokumentum SKAL tartalmaznia egy függeléket szószedettel (AI/ML fogalmak magyarul), linkgyűjteménnyel (Anthropic docs, MCP, SWE-bench, videók), és egy "Kipróbálom" quick-start útmutatóval.

#### Scenario: Szószedet hasznossága
- **WHEN** az olvasó egy ismeretlen fogalommal találkozik a szövegben
- **THEN** a szószedetben megtalálja a magyar definíciót és rövid kontextust

#### Scenario: Linkgyűjtemény
- **WHEN** az olvasó mélyebben akar olvasni egy témáról
- **THEN** a linkgyűjteményben megtalálja a releváns Anthropic dokumentációt, MCP oldalt, és YouTube videókat

