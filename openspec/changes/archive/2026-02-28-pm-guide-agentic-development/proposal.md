## Why

Egy PM barátnak szükséges egy átfogó, magyar nyelvű dokumentáció, ami elmagyarázza az agentic szoftverfejlesztés forradalmát — Claude Code-tól az orchestrációig. A célközönség ChatGPT szinten van (ismeri az AI-t mint chat eszközt, de nem fejlesztő), és projekt menedzserként szeretné megérteni, mire képesek ezek az eszközök, miért nem "vibe coding", és hogyan változik meg a szoftverfejlesztés. Ilyen összefoglaló magyar nyelven nem létezik.

## What Changes

- Új `docs/pm-guide/` könyvtár létrehozása a teljes dokumentációnak
- 7 fejezet Markdown formátumban, fejezeti fájlokra bontva
- `docs/pm-guide/build.sh` script ami pandoc+LaTeX-el PDF-et generál
- ASCII diagramok minden fejezetben
- Külső hivatkozások (Anthropic docs, MCP, SWE-bench, stb.)
- Magyar nyelvű szószedet a függelékben
- ~60-75 oldal terjedelmű könyv-jellegű dokumentum

## Capabilities

### New Capabilities
- `pm-guide-chapters`: A 7 fejezet tartalma — I. AI fordulópont (2024), II. Claude Code, III. Vibe Coding vs Spec-Driven, IV. OpenSpec, V. Orchestráció, VI. Memória, VII. Jövőkép
- `pm-guide-build`: PDF build pipeline (Markdown → pandoc → LaTeX → PDF) és a szükséges template/config

### Modified Capabilities

## Impact

- Új fájlok a `docs/pm-guide/` alatt (~7 markdown fejezet + build script + LaTeX template)
- Nincs kód módosítás, nincs API változás, nincs dependency változás
- A set-core projekt dokumentációját bővíti külső (PM) célközönség számára
