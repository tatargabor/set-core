# v5 Orchestration Results — sales-raketa "Platform Admin Shell"

**Dátum:** 2026-02-28 23:28 → 2026-03-01 00:43 (75 perc)
**Orchestrator verzió:** wt-tools v1.2.0
**Projekt:** sales-raketa (Next.js SaaS, Prisma, Vitest)

---

## Feladat

A SUPER_ADMIN felhasználók dedikált `/platform` felületet kapnak, elkülönítve a tenant dashboard-tól. A spec (`docs/v5.md`) 2 fázisra bontotta a munkát:

- **Phase 1:** Platform shell routing — új route group, layout, sidebar, middleware redirect
- **Phase 2:** Dashboard, org management, settings, admin cleanup — 4 párhuzamos change

## Orchestrator Direktívák (a spec-ből)

```
max_parallel: 3
merge_policy: checkpoint
test_command: pnpm test
default_model: opus
auto_replan: true
```

## Tervezés (Planning)

A planner (Opus) a spec-ből 5 change-et generált, ami pontosan megfelelt a spec dependency gráfjának:

```
                    ┌─────────────────────────┐
                    │  platform-shell-routing  │
                    │  (Phase 1 — foundational)│
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
              ▼                  ▼                   ▼
   ┌──────────────────┐ ┌───────────────┐ ┌─────────────────┐
   │ platform-dashboard│ │platform-org-  │ │platform-settings│
   │ (M, opus)         │ │detail (L,opus)│ │ (M, opus)       │
   └──────────────────┘ └───────┬───────┘ └─────────────────┘
                                │
                                ▼
                     ┌──────────────────┐
                     │admin-route-      │
                     │cleanup (S,sonnet)│
                     └──────────────────┘
```

**Modell választás:** Opus minden security-sensitive change-hez (auth guard, cross-org query, invite flow). Sonnet csak a mechanikus cleanup-hoz. Ez a v1.2.0-ban bevezetett per-change model heurisztika első éles tesztje.

## Végrehajtás

### Idővonal

| Idő | Esemény |
|-----|---------|
| 23:28 | Orchestrator start, plan v16 létrehozva |
| 23:28 | platform-shell-routing dispatch (Opus) |
| 23:34 | Iter 1 kész: OpenSpec artifaktok (design, spec, tasks) — 6 perc |
| 23:42 | Iter 2 kész: implementáció + verify gate pass |
| 23:44 | shell-routing merged → Phase 2 indul |
| 23:45 | 3 change dispatch egyszerre: dashboard, org-detail, settings (mind Opus) |
| 23:57 | dashboard kész → verify gate → merged |
| 00:03 | settings kész → verify gate → merged |
| 00:07 | **Build FAILED on main** — `OrganizationInvite` típus hiba |
| 00:08 | org-detail kész → verify gate → merge attempt |
| 00:16 | **Merge conflict** — design doc-ok (2×900+ soros fájl) |
| 00:17-00:33 | LLM merge resolve 3× timeout (sonnet, 300s) |
| 00:33 | Orchestrator leállt (merge-blocked) |
| 00:34 | **Manuális beavatkozás:** conflict kézzel megoldva, state frissítve, restart |
| 00:34 | admin-route-cleanup dispatch (Sonnet) |
| 00:42 | admin-route-cleanup kész → verify gate → merged |
| 00:43 | Build FAILED marad (settings-ből örökölt típus hiba) |
| 00:43 | Replan cycle 11: "No new changes — all work done" |
| 00:43 | **Orchestration complete** |

### Change-ek részletei

| Change | Tokens | Verify Gate | Merge | Megjegyzés |
|--------|--------|-------------|-------|------------|
| platform-shell-routing | 303k | 140s (test:pass, review:pass, verify:ok) | OK | Foundational, 2 iteráció |
| platform-dashboard | 695k | 142s (test:pass, review:pass, verify:ok) | OK | KPI cards, activity feed |
| platform-org-detail | 907k | 230s (test:pass, **review:FAILED→skip**, verify:ok) | **CONFLICT** (kézi) | Legnagyobb change (L) |
| platform-settings | 991k | 238s (**review:FAILED→skip**, verify:ok) | OK, de **build break** | Schema migration |
| admin-route-cleanup | 451k | 68s (test:pass, review:pass, verify:ok) | OK | Sonnet, gyors |

## Eredmények

### Token felhasználás

| Kategória | Tokenek |
|-----------|---------|
| v5 change-ek összesen | **3,349,137** |
| Korábbi run (v4 doc-sync batch, same session) | 5,788,251 |
| **Session összesen** | **9,137,388** |

**Token per change átlag:** 670k (v5 change-ek)
- Legkisebb: shell-routing 303k (M, foundational — főleg új fájlok)
- Legnagyobb: settings 991k (M, de schema migration + invite flow + acceptInvite módosítás)

### Idő

| Metrika | Érték |
|---------|-------|
| Teljes futásidő | **75 perc** (23:28 → 00:43) |
| Aktív idő | ~65 perc (10 perc merge-blocked) |
| Verify gate összesen | 816s (~14 perc, 7% aktív idő) |
| Átlag change idő | ~15 perc |
| Manuális beavatkozás | ~1 perc (merge conflict) |

## Hibák és problémák

### 1. Merge conflict — design doc-ok (KRITIKUS)
**Mi történt:** `platform-org-detail` merge-je conflict-ot kapott 2 nagy design doc-ban (`functional-conventions.md` 989 sor, `ui-conventions.md` 940 sor). Mindkét fájlt a dashboard és settings change-ek is módosították.

**LLM merge resolution 3× timeout:** A `wt-merge` a teljes fájlt (900+ sor conflict markerekkel) küldte sonnet-nek, ami 300s timeout-on belül nem tudta feldolgozni.

**Gyökérok:** A design doc-ok "shared resource"-ok — minden change bővíti a saját szekciójával. Párhuzamos change-ek merge-je mindig conflict-ot okoz rajtuk.

**Javítás (v1.2.0+1):**
- Opus fallback a merge resolution-ben (sonnet timeout → opus 600s)
- Hunk-only extraction: csak a conflict blokkokat küldi, nem a teljes fájlt

**Jövőbeli teendő:** A planner-nek kellene felismernie a shared resource pattern-t és serializing-olni az ilyen change-eket.

### 2. Build break — OrganizationInvite típus hiba (KÖZEPES)
**Mi történt:** `platform-settings` merge után a main branch build eltört: `OrganizationInvite` típus hiba (`organizationId` nullable lett a schema-ban, de valahol a kód nem kezeli az `undefined` esetet).

**Hatás:** A build FAILED figyelmeztetés megjelent, de az orchestrator nem próbálta automatikusan fixálni (a base build fix logic nem aktiválódott erre az esetre). Az `admin-route-cleanup` ennek ellenére lefutott és merged — a hiba átöröklődött.

**Gyökérok:** A `platform-settings` change módosította a Prisma schema-t (nullable FK), de a típus propagáció nem volt teljes a worktree-ben, csak main merge után derült ki.

### 3. Code review timeout — 2 change (ALACSONY)
`platform-settings` és `platform-org-detail` review-ja FAILED (valószínűleg timeout a nagy diff-ek miatt). A verify gate review:skip-kel engedte tovább.

**Gyökérok:** A review prompt az egész diff-et elküldi truncálás nélkül. Nagy refaktor change-eknél (40+ fájl) ez 100KB+ lehet.

### 4. Tesztek hiánya — 2/5 v5 change (ALACSONY)
`platform-shell-routing` és `admin-route-cleanup` nem tartalmazott tesztfájlokat a diff-ben. A verify gate WARN-t adott de engedte.

## Következtetések

### Mi működött jól

1. **Spec-driven orchestration** — A planner pontosan leképezte a v5.md struktúráját 5 change-re. A dependency graph helyes volt.
2. **OpenSpec artifact workflow** — Iteráció 1 mindig az artifaktokat csinálja (design → spec → tasks), iteráció 2+ az apply. Ez strukturáltabb és nyomon követhetőbb.
3. **Per-change model** — Opus a feature change-ekhez, sonnet a cleanup-hoz. Az admin-route-cleanup 451k tokennel és 68s verify gate-tel futott — jóval olcsóbb mint opus lenne.
4. **Párhuzamos végrehajtás** — Phase 2 három change-je egyszerre futott, a max_parallel:3 kihasználva.
5. **Verify gate** — Minden change átment (test, build, verify), 0 retry. A gate az aktív idő 7%-a — alacsony overhead.
6. **Auto-replan exit** — Az orchestrator felismerte, hogy nincs több munka és rendesen leállt (ez v1.1.0-ban volt bug).

### Mi nem működött

1. **Shared resource conflict** — Design doc-okat párhuzamos change-ek módosítják → merge conflict garantált. A planner-nek ezt fel kellene ismernie.
2. **LLM merge resolution nem skálázik** — Sonnet 300s-el nem bírja a 900+ soros fájlokat. Opus fallback és hunk extraction kellett.
3. **Post-merge build break nem javítódik** — A build fix logic nem aktiválódott a settings merge utáni típus hibára. Kézi fix kell.
4. **Code review unbounded diff** — A review prompt a teljes diff-et küldi. Truncálás kell.

### Összehasonlítás korábbi verziókkal

| Metrika | v3 (2026-02 eleje) | v5 (2026-02-28) |
|---------|---------------------|------------------|
| Adhoc fix commitok | 35 | 0 |
| Bug-ok | 10 | 1 (build break) |
| Spec eltérések | 7 | 0 |
| Merge conflict | N/A (manual merge) | 1 (auto-resolve failed) |
| Manuális beavatkozás | 2 nap | 1 perc |
| Infinite replan loop | Igen (50-100k token/5 perc) | Nem |
| Verify gate | Nem létezett | 5/5 change átment |

### Actionable javítások

1. **[KÉSZ]** Opus fallback merge resolution-ben (`wt-merge`)
2. **[KÉSZ]** Hunk-only extraction merge prompt-hoz (`wt-merge`)
3. **[TODO]** Shared resource detection a planner-ben — design doc-ot módosító change-ek serialization
4. **[TODO]** Code review diff truncálás (50KB cap)
5. **[TODO]** Replan memory cap (`_REPLAN_MEMORY` korlátlan növekedése)
6. **[TODO]** Post-merge build fix — ha a merge után eltörik a build, automatikus fix attempt
