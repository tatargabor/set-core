# Függelék

## A. Szószedet

| Angol kifejezés | Magyar jelentés | Rövid leírás |
|----------------|-----------------|--------------|
| **Agent / Ágens** | Ágens, ügynök | AI rendszer ami önállóan cselekszik: fájlokat olvas, kódot ír, parancsokat futtat |
| **Agentic Loop** | Ágentikus ciklus | Az AI gondolkodási ciklusa: tervez → cselekszik → ellenőriz → ismétli |
| **API** | Alkalmazás-programozási felület | Szabványos mód, ahogy szoftverek egymással kommunikálnak |
| **Artifact** | Műtermék, termék | Az OpenSpec-ben: egy dokumentum (proposal, spec, design, tasks) |
| **Branch** | Ág, elágazás | A kód egy párhuzamos verziója amiben valaki dolgozik |
| **CLI** | Parancssori felület | Szöveges felület ahol parancsokat írsz (terminál) |
| **Commit** | Mentési pont | Egy változtatáscsomag elmentése a verziókezelőbe |
| **Context Window** | Kontextus ablak | Az AI munkamemóriája — amennyit egyszerre kezelni tud |
| **DAG** | Irányított körmentes gráf | Függőségi térkép: mi függ mitől (orchestrációnál) |
| **Deploy** | Telepítés, élesítés | A kód feltöltése az éles szerverre |
| **Design** | Tervezési dokumentum | Technikai döntéseket rögzítő dokumentum |
| **Git** | Git verziókezelő | A legelterjedtebb kód-verziókövető rendszer |
| **Hallucination** | Hallucináció | Amikor az AI magabiztosan állít olyasmit, ami nem igaz |
| **Hook** | Kampó, automatizmus | Automatikus művelet ami egy eseményre reagál |
| **IDE** | Integrált fejlesztőkörnyezet | Szoftver amiben a fejlesztők dolgoznak (pl. VS Code) |
| **LLM** | Nagy nyelvi modell | Az AI motor ami a szöveget érti és generálja |
| **MCP** | Modell Kontextus Protokoll | Szabvány az AI és külső eszközök összekapcsolására |
| **Merge** | Beolvasztás, összefésülés | Két kódverzió egyesítése |
| **Orchestration** | Orchestráció, karmesterség | Több AI ágens koordinált, párhuzamos futtatása |
| **Pipeline** | Csővezeték, munkafolyamat | Lépések sorozata egy cél elérésére |
| **Production** | Éles környezet | A szoftver azon verziója amit a felhasználók használnak |
| **Prompt** | Utasítás, kérés | Az AI-nak adott szöveges utasítás |
| **Proposal** | Javaslat | „Mit és miért?" dokumentum az OpenSpec-ben |
| **PR / Pull Request** | Beolvasztási kérelem | Kérés hogy a változtatásaid kerüljenek be a fő kódba |
| **Ralph Loop** | Ralph ciklus | Autonóm munkaciklus ahol az AI ismétlődően dolgozik feladatokon |
| **Review** | Áttekintés, ellenőrzés | Kód vagy dokumentum felülvizsgálata |
| **Sandbox** | Homokozó | Elszigetelt környezet ahol az AI biztonságosan futtathat parancsokat |
| **Session** | Munkamenet | Egy beszélgetés/munkaszakasz az AI-val |
| **Spec / Specification** | Specifikáció | Pontos, mérhető követelményeket leíró dokumentum |
| **Spec-Driven** | Specifikáció-vezérelt | Fejlesztési megközelítés ahol minden a specifikációból indul |
| **Subagent** | Alágenes | Kisebb, specializált AI ami a fő ágens irányítása alatt dolgozik |
| **Task** | Feladat | Egy konkrét, elvégzendő munkadarab |
| **Token** | Token | Az AI szövegfeldolgozási egysége (~0.75 szó) |
| **Vibe Coding** | Hangulat-kódolás | AI-val való informális, tervezés nélküli kódolás |
| **Worktree** | Munkafa | A git egy funkciója: egy repo több példánya a lemezen |

## B. Linkgyűjtemény

### Anthropic és Claude Code

| Link | Leírás |
|------|--------|
| [code.claude.com/docs](https://code.claude.com/docs/en/overview) | Claude Code hivatalos dokumentáció |
| [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices) | Bevált gyakorlatok Claude Code használatához |
| [Claude Code Hooks](https://code.claude.com/docs/en/hooks-guide) | Hook rendszer útmutató |
| [Claude Code Sub-agents](https://code.claude.com/docs/en/sub-agents) | Subágensek használata |
| [CLAUDE.md dokumentáció](https://code.claude.com/docs/en/claude-md) | Projekt memória fájl |
| [claude.ai](https://claude.ai) | Claude AI webes felület |
| [anthropic.com](https://www.anthropic.com) | Anthropic cég honlapja |

### MCP (Model Context Protocol)

| Link | Leírás |
|------|--------|
| [modelcontextprotocol.io](https://modelcontextprotocol.io/introduction) | MCP bevezető — mi ez és miért fontos |
| [MCP dokumentáció](https://modelcontextprotocol.io/docs/learn/architecture) | Architektúra és működés |

### Kutatás és benchmarkok

| Link | Leírás |
|------|--------|
| [SWE-bench kutatás](https://www.anthropic.com/research/swe-bench-sonnet) | Claude teljesítménye valós hibák javításában |

### Iparági eszközök

| Link | Leírás |
|------|--------|
| [GitHub Copilot](https://github.com/features/copilot) | Microsoft/GitHub AI kódolási eszköz |
| [Cursor](https://cursor.com) | AI-natív kódszerkesztő |
| [Devin](https://devin.ai) | Cognition Labs autonóm AI fejlesztő |

## C. „Kipróbálom" — Quick Start

Ha szeretnéd kipróbálni a Claude Code-ot, íme a legegyszerűbb út:

### 1. lépés: Telepítés (2 perc)

Nyiss egy terminált (Mac: Terminal.app, Windows: PowerShell, Linux: bármilyen terminál) és futtasd:

**Mac / Linux:**
```
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows PowerShell:**
```
irm https://claude.ai/install.ps1 | iex
```

### 2. lépés: Bejelentkezés

```
claude
```

Az első indításnál a böngészőben bejelentkezel a Claude fiókodba. Fizetős előfizetés szükséges (Claude Pro, Team, vagy Enterprise).

### 3. lépés: Próbáld ki egy projekten

Navigálj egy meglévő projektbe és indítsd el:

```
cd a-te-projekted
claude
```

### 4. lépés: Első parancsok

Próbáld ki ezeket:

```
"Magyarázd el, mit csinál ez a projekt"

"Keress hibákat a kódban"

"Írj teszteket a fő funkcióhoz"

"Javítsd ki a legfontosabb hibát amit találtál"
```

### 5. lépés: Fedezd fel

- Nyomd meg a `Tab` billentyűt a kontextusváltáshoz (Plan Mode / Normal Mode)
- Írd be `/help` a parancsok listájáért
- Írd be `/init` egy CLAUDE.md fájl generálásához

### Tippek

- **Légy konkrét**: „Javítsd ki a login hibát az auth.py-ban" jobb, mint „javítsd ki a hibákat"
- **Adj kontextust**: „A tesztek pytest-tel futnak: `npm test`" segít az AI-nak
- **Engedd dolgozni**: Ne állítsd le azonnal — hagyd végigmenni a gondolkodási cikluson
- **Ellenőrizd**: Mindig nézd meg mit csinált mielőtt jóváhagynád
