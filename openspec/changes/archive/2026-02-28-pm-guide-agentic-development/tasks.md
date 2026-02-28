## 1. Setup — Könyvtárstruktúra és build pipeline

- [x] 1.1 Létrehozni a `docs/pm-guide/` könyvtárat és a `docs/pm-guide/output/` alkönyvtárat
- [x] 1.2 Létrehozni a `docs/pm-guide/00-meta.md` fájlt pandoc YAML frontmatterrel (title, author, date, lang: hu, toc: true, documentclass, fontsize, geometry, mainfont, monofont, header-includes magyar babel + monospace beállítások)
- [x] 1.3 Létrehozni a `docs/pm-guide/build.sh` scriptet ami ellenőrzi pandoc/xelatex elérhetőségét, majd pandoc-kal PDF-et generál az összes fejezeti fájlból `docs/pm-guide/output/az-agensek-kora.pdf` kimenettel

## 2. I. fejezet — Mi történt 2024 végén?

- [x] 2.1 Megírni a `docs/pm-guide/01-ai-fordulopont.md` fejezetet: AI fejlődés kronológiája (GPT-3 → Claude 3.5 → Claude 4.6), idővonal táblázat 2022-2026, SWE-bench eredmények hivatkozással, az AI jelenlegi képességei és korlátai, PM-barát nyelvezet, "Kulcs üzenet PM-nek" box a végén

## 3. II. fejezet — Claude Code

- [x] 3.1 Megírni a `docs/pm-guide/02-claude-code.md` fejezetet: mi a Claude Code, futási környezetek (terminál/IDE/desktop/web), agentic loop ASCII diagram (Gondol→Cselekszik→Ellenőriz), eszközök bemutatása (Read, Edit, Bash, stb.), CLAUDE.md mint projektmemória, hookrendszer, MCP ("USB-C az AI-nak" analógia + hivatkozás), subágensek, konkrét bugfix példa, Anthropic doc hivatkozások minden alfejezetben

## 4. III. fejezet — Vibe Coding vs Spec-Driven

- [x] 4.1 Megírni a `docs/pm-guide/03-vibe-vs-spec.md` fejezetet: Karpathy vibe coding fogalom (2025 feb, idézet), kontextus ablak probléma ASCII vizualizációval, minőség probléma (nincs spec → nincs mit ellenőrizni), skálázás probléma, mikor jó/rossz a vibe coding, összehasonlító táblázat (sebesség, minőség, nyomon követhetőség, PM rálátás, skálázhatóság)

## 5. IV. fejezet — OpenSpec

- [x] 5.1 Megírni a `docs/pm-guide/04-openspec.md` fejezetet: Proposal→Specs→Design→Tasks→Implementation pipeline ASCII diagrammal, minden artifact típus rövid (5-10 soros) példával, PM munkafolyamat konkrét példával (PM ír proposal → AI generál spec → PM review → AI implementál), a wt-tools projektből vett illusztrációk

## 6. V. fejezet — Orchestráció

- [x] 6.1 Megírni a `docs/pm-guide/05-orchestracio.md` fejezetet: git worktree koncepció PM-barát analógiával ("5 fejlesztő 5 mappában") + ASCII diagram, Ralph Loop autonomy loop, orchestrátor működése (spec→DAG→párhuzamos dispatch→merge) ASCII diagrammal, merge policy-k (eager/checkpoint/manual), GUI dashboard említése, valós számok (N change, M ágens, X óra)

## 7. VI. fejezet — Memória

- [x] 7.1 Megírni a `docs/pm-guide/06-memoria.md` fejezetet: "minden session nulláról indul" probléma, előtte/utána példa, memória típusok (Decision/Learning/Context) PM-barát magyarázattal, 5 rétegű hook rendszer 5 pontban egyszerűsítve, csapat szintű memória szinkronizáció

## 8. VII. fejezet — A szoftverfejlesztés jövője

- [x] 8.1 Megírni a `docs/pm-guide/07-jovo.md` fejezetet: rövid/közép/hosszú távú trend, PM szerep evolúciója vizualizáció (MA→HOLNAP→HOLNAPUTÁN), iparági összehasonlító táblázat (Claude Code, Copilot, Cursor, Devin), kockázatok (hallucináció, biztonság, vendor lock-in, EU AI Act), ami NEM tűnik el

## 9. Függelék

- [x] 9.1 Megírni a `docs/pm-guide/08-appendix.md` függeléket: szószedet (AI/ML fogalmak magyarul/angolul), linkgyűjtemény (Anthropic docs, MCP, SWE-bench, YouTube videók), "Kipróbálom" quick-start (3-5 lépés hogyan próbálja ki a Claude Code-ot)

## 10. Build és véglegesítés

- [x] 10.1 PDF build futtatása `build.sh`-val, ékezetes karakterek és ASCII diagramok ellenőrzése, tartalomjegyzék és oldalszámok verifikálása
- [x] 10.2 A generált PDF commitolása a repóba
