---
name: glm
description: Run Claude Code against the z.ai GLM models with the measured, working parameters — one-shot `-p` calls, batch loops, or an interactive session. Use when the user asks to run something on GLM, on a non-Anthropic model, or to compare models on the same task (an A/B run), and when a GLM run behaves strangely — silent stalls, "Prompt is too long", or a 400 on the model name. Carries the three failure modes measured in production so they do not have to be rediscovered.
---

# GLM futtatás — `set-glm`

**Nem a modell váltása a nehéz, hanem a context-ablak.** A Claude Code CLI nem ismeri a
GLM ablakát, ezért egy konzervatív értékre (~200k) vág — és a hosszú prompt vagy hangosan
elhasal, vagy némán compact-hurokba fut. Ez a skill azért létezik, hogy ezt ne kelljen
újra kimérni.

⚠ **A váltás mindig FELHASZNÁLÓI döntés.** Nincs automatika és nincs csendes fallback:
hiányzó konfigra a futtató megáll, nem esik vissza Claude-ra. Egy csendes visszaesés
azért a legrosszabb kimenet, mert a futás lefutna — csak a másik keretből, és semmi nem
jelezné, melyikből.

## Használat

```bash
set-glm --check                     # konfiguráció + ÉLŐ próbahívás — ezzel kezdj
set-glm -p "prompt"                 # egyszeri hívás
set-glm -p "…" --output-format json # strukturált kimenet (a token- és költség-mezőkkel)
set-glm                             # interaktív session GLM-en
set-glm --print-env                 # mit állít be (a token maszkolva)
```

Minden további flag változatlanul megy tovább a `claude`-nak (`--allowedTools`,
`--json-schema`, `--append-system-prompt`, …). A `--model` és az `--autocompact` csak
akkor kerül hozzá, ha a hívó nem adta meg.

### Konfiguráció — első találat nyer

| # | hely | mikor |
|---|---|---|
| 1 | a folyamat env-je | egyszeri felülírás |
| 2 | `./.env` a repóban (`GLM_*` sorok) | projekt-szintű |
| 3 | `~/.config/set-core/glm.env` | **gépszintű — ez a hordozható hely** |

```bash
printf 'GLM_TOKEN=%s\nGLM_MODEL=glm-5.3-flash\n' "$KULCS" > ~/.config/set-core/glm.env
```

Csak a `GLM_` prefixű sorokat olvassa be — szándékosan. Egy `source .env` az
`ANTHROPIC_API_KEY`-t is behozná, vagyis pont azt a kulcsot, ami a hívást csendben a
platform-számlára irányítaná át.

## A mért paraméterek (2026-08-29) — ne mérd ki újra

| mit | érték | env |
|---|---|---|
| endpoint | `https://api.z.ai/api/anthropic` | `GLM_BASE_URL` |
| modell | `glm-5.3-flash` — **prefix nélkül** | `GLM_MODEL` |
| context-ablak | **900000** (`CLAUDE_CODE_MAX_CONTEXT_TOKENS`) | `GLM_CONTEXT_TOKENS` |
| auto-compact | **700k** | `GLM_AUTOCOMPACT` |

Mért képességek: **800 016 input token elfogadva** (1,05M-nál `model_context_window_exceeded`,
tehát az ablak ~1M) · max output **≥131 072** · a **prompt cache működik** `cache_control`
nélkül is (2. azonos hívás: `input=16`, `cache_read=120 000`) · a `--json-schema`, az
`--allowedTools` és a Write/Edit tool mind megy. 200-at ad: `glm-4.6`, `glm-5.3`,
`glm-5.3-flash`, `glm-4.5`, `glm-4.5-air`.

## Három csapda — mindegyik MÉRT bukásból

1. ⚠ **A modellnév nem hordozhat gateway-prefixet.** A `zai/glm-5.3-flash` alakra
   `[1214][modelCode: does not exist]` 400 a válasz — az OpenRouter/LiteLLM formátum. A
   futtató ezért indulás ELŐTT elutasítja a `/`-t tartalmazó nevet: különben egy éjszakai
   loop az első hívásnál bukna el.

2. ⚠⚠ **A `--autocompact` önmagában kevés.** A CLI a küszöböt levágja arra az ablakra,
   amit az ismeretlen modellhez feltételez. Ugyanaz a ~250k tokenes prompt, négy változatban:

   | beállítás | eredmény |
   |---|---|
   | csak `--autocompact 700k` | `Prompt is too long`, input=0 |
   | `MAX_CONTEXT_TOKENS` + `DISABLE_…_ENFORCEMENT` | OK, `input_tokens=524 731` |
   | **csak `CLAUDE_CODE_MAX_CONTEXT_TOKENS`** | **OK — szükséges ÉS elégséges** |
   | csak `…_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT` | `Prompt is too long` |

   A második env-et ezért nem állítjuk be: a fölös env csak elfedi, mi hat.

   **A compact NEM hibaüzenet — kívülről „lassú modell"-nek látszik.** A mért bukás:
   180 174 tokennél compact (227 mp), fél perc múlva újra, végül a CLI saját üzenete —
   *„Autocompact is thrashing: the context refilled to the limit within 3 turns of the
   previous compact, 3 times in a row"* —, **9,5 perc alatt nulla megírt sorral**.
   Ha egy GLM-futás gyanúsan hosszan hallgat, a `--output-format stream-json` naplójában
   a **`compact_boundary`** és a `status: compacting` eseményt keresd; a tool-események
   közt semmi nem látszik belőle.

3. ⚠ **A `.env` gyakran git-követett.** Worktree-ben egy `git reset --hard` elviszi a
   `GLM_*` sorokat, és a futás „hiányzik a GLM_TOKEN"-nel áll meg. Ezért van a gépszintű
   `~/.config/set-core/glm.env` — az egyik repó takarítása nem viszi el a többiét.

## Subagent GLM-en — a provider a SZÜLŐTŐL jön, nem az agent-definícióból

Mérve 2026-08-29, három kísérlettel. **A subagent a szülő session ENDPOINTJÁT örökli** (a
`spawn` a szülő env-jét viszi tovább); az agent-definíció `model:` mezője csak azon az
endpointon belül választ.

| szülő | az agent `model:` mezője | mi történik |
|---|---|---|
| Anthropic | `glm-5.3-flash` | ⛔ **`model_not_found` (HTTP 404)** — a subagent elindul, majd elhasal |
| GLM (z.ai env) | `glm-5.3-flash` | ✅ működik, `modelUsage` = csak `glm-5.3-flash` |
| GLM (z.ai env) | `sonnet` | ⚠ **lefut**, de a hívás a **z.ai-ra** megy, és `claude-sonnet-5`-ként számolódik el |

**A recept tehát: a szülőt kell GLM-en indítani.** Nincs mód agentenként providert váltani —
`set-glm` a szülő session, és a subagentjei magukkal viszik.

⚠ **A harmadik sor a csapda, és ezt ki kell mondani.** GLM-szülő alatt egy `model: sonnet`
agent nem hasal el — a z.ai elfogadja a nevet —, a `modelUsage` pedig **két sort** mutat:
`glm-5.3-flash` (`costBasis: unknown`) és `claude-sonnet-5` (`costBasis: list`, `ctx=200000`).
Vagyis a képernyőn Anthropic modellnév áll, a számla viszont a z.ai-é, és az env-ben nincs is
Anthropic auth. Ez a *„más számla, azonos kinézet"* hibaosztály — ugyanaz, amit a ledger
provider-mezője zár le a másik oldalról.

**Ezért:** ha egy agent-definíciót GLM-szülő alatt akarsz futtatni, vagy **hagyd el a `model:`
mezőt** (akkor a szülő modelljét örökli, és nincs mit félreérteni), vagy írj bele **GLM-modellt**.
A `model: sonnet` GLM-szülő alatt félrevezető: azt ígéri, amit nem tart be.

### Melyik GLM-modell review-ra — mérve, öt eseten

Öt kód-review eset (sorszám-race · ÁFA-kerekítés · dátum-UTC · cron-idempotencia · egy
**szándékosan tiszta** kód a hamis pozitív méréséhez):

| modell | találat | átlag idő | átlag output |
|---|---|---|---|
| `glm-5.3-flash` | **5/5** | 12,7 mp | 222 token |
| `sonnet` (összevetésül) | **5/5** | 5,4 mp | 74 token |
| `glm-4.6` | 2/2 (rövid próbán) | 15,7 mp | 604 token |
| `glm-4.5-air` | ⛔ **0/2** | 11,0 mp | 878 token |

A **`glm-4.5-air` kizárva**: kétszer, két különböző hibaosztályon fogott mellé — egyszer
„NINCS HIBA"-t mondott valódi hibára —, és 8× annyi tokent égetett rá, mint a flash. Egy
review-agentnél ez a legrosszabb kimenet: a hallgatás megnyugtatóan hangzik.

A **`glm-5.3-flash` alkalmas** — a tiszta kódra is helyesen mondott „NINCS HIBA"-t (nem gyárt
hamis pozitívot). Cserébe 2,4× lassabb és 3× bőbeszédűbb a sonnetnél.

⚠ A minta **könnyű volt**: öt önhordó, 5–8 soros, tankönyvi hiba. Egy valódi review nehezebb —
nagy fájl, projekt-kontextus, egymásnak feszülő szabályok —, és arról ez a mérés semmit nem mond.

## Amit a költség-mező HAZUDIK

A `--output-format json` `total_cost_usd` mezője **Anthropic-árazással** számol, tehát
GLM-futásnál nem valós számla. Két modell összevetésére a **wall-clock** és a
**token-szám** való, a dollár nem — és ha egy ledgerbe írod, mondd ki mellette, hogy
ár-ekvivalens.

## Ha egy ciklust futtatsz vele (A/B, éjszakai loop)

- **Ugyanaz a prompt, ugyanaz a feladat** — különben nem mérés, hanem anekdota.
- **A kapusor a mérés része.** A mért GLM-futás munkája jó volt, de a commitot egy lint-kapu
  elutasította, mert a modell egy **nem létező** ignore-direktívával próbálta elnémítani a
  szabályt a repó saját precedense helyett. Ezt csak a kapu fogta meg — a teszt zöld volt.
  Aki modellt hasonlít össze, a **kapun átment** commitot számolja, ne a megírt sorokat.
- **Naplózz eseményt, ne csak kimenetet** (`--output-format stream-json`): a compact
  különben láthatatlan, és a lassulást a modellre fogod.

## Kapcsolódó

- `bin/set-glm` — a futtató; a mért indoklás a fájl fejlécében, kommentben
- `bin/claude-local` — ugyanez lokális Ollama modellre (a testvér-eset)
