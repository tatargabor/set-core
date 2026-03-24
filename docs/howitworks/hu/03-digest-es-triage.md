# Digest és Triage

## Mi a Digest?

A digest a specifikáció strukturált kivonatja. Egy több ezer soros spec dokumentumot gépileg feldolgozható JSON formátumra bont, amelyben minden követelmény egyedi azonosítót kap (REQ-001, REQ-002, stb.).

Ez teszi lehetővé, hogy az orchestrátor:

- **Nyomon kövesse**, melyik követelményt melyik change implementálja
- **Ellenőrizze**, hogy minden követelmény le van-e fedve
- **Felismerje** a kétértelmű pontokat, mielőtt a fejlesztés elindul

![A digest generálás teljes folyamata](diagrams/rendered/02-digest-flow.png){width=90%}

## A Digest generálás lépései

### 1. Spec szkennelés (`scan_spec_directory`)

A rendszer feltérképezi a bemenetként kapott fájlt vagy könyvtárat:

```bash
set-orchestrate --spec docs/specs/ digest
```

A szkennelés eredménye:

- **file_count**: hány fájl került feldolgozásra
- **source_hash**: az összes fájl tartalmából képzett hash (frissesség ellenőrzés)
- **master_file**: ha van `index.md` vagy hasonló, az a fő fájl

### 2. Prompt összeállítás (`build_digest_prompt`)

A rendszer egy strukturált promptot épít a Claude API-nak, amely tartalmazza az összes spec fájlt és az elvárt kimeneti formátumot.

### 3. API hívás és parsing

A Claude feldolgozza a specifikációt és strukturált JSON kimenetet ad:

```json
{
  "requirements": [
    {
      "id": "REQ-001",
      "title": "JWT autentikáció",
      "brief": "Token alapú auth a /api/* végpontokon",
      "priority": "high",
      "source_file": "docs/v3-security.md",
      "section": "2.1 Authentication"
    }
  ],
  "phases": [...],
  "ambiguities": [...]
}
```

### 4. ID stabilizálás (`stabilize_ids`)

Ha már létezik korábbi digest, a rendszer megtartja a meglévő REQ-XXX azonosítókat, hogy a követelmény-nyomkövetés ne törjön el frissítés után.

## A digest kimeneti fájljai

A digest a `set/orchestration/digest/` könyvtárba ír:

| Fájl | Tartalom |
|------|---------|
| `requirements.json` | Összes követelmény REQ-XXX azonosítóval |
| `phases.json` | Fázis struktúra (melyik fázisban mi van) |
| `digest-meta.json` | Hash, dátum, fájl számok |
| `ambiguities.json` | Kétértelmű vagy hiányos pontok |

## Frissesség ellenőrzés

A `source_hash` mező lehetővé teszi a gyors frissesség-ellenőrzést:

```bash
# Ha a hash nem változott, a digest naprakész
if [[ "$current_hash" == "$stored_hash" ]]; then
    echo "Digest naprakész, kihagyva"
fi
```

Ez megakadályozza a felesleges újragenerálást, ha a spec nem változott.

## Ambiguity Triage

A digest generálás automatikusan azonosítja a specifikáció kétértelmű pontjait. Ezek kezelése a **triage** folyamatban történik.

### Triage generálás

A rendszer egy `triage.md` fájlt generál, amely felsorolja a kétértelmű pontokat és döntési opciókat kínál:

```markdown
## AMB-001: Nem egyértelmű session kezelés

**Kontextus**: A spec "session timeout" -ot említ, de nem definiálja az értéket.

**Opciók**:
- [ ] A: 30 perc (web standard)
- [ ] B: 60 perc (hosszabb munkamenet)
- [ ] C: Konfigurálható (runtime beállítás)

**Döntés**: ___
```

### Emberi döntés

A triage fájlt egy ember (vagy a sentinel) kitölti. A döntés visszaíródik az `ambiguities.json`-be, és a planner figyelembe veszi a dekompozíciónál.

### Automatikus triage mergelés

A `merge_triage_to_ambiguities()` és `merge_planner_resolutions()` függvények biztosítják, hogy:

- Az emberi döntések bekerüljenek a digest-be
- A planner által hozott döntések szintén megmaradjanak
- Ellentmondás esetén az emberi döntés nyer

\begin{fontos}
A triage gate az egyetlen pont, ahol az orchestrátor megáll és emberi beavatkozást kér. Minden más döntést autonóm módon hoz. Ha nincs kétértelmű pont, a triage lépés automatikusan kimarad.
\end{fontos}

## Requirement Coverage

A digest lehetővé teszi a követelmény-lefedettség nyomon követését az egész pipeline-on keresztül:

```bash
set-orchestrate coverage
```

Kimenet:

```
Requirement Coverage: 12/15 (80%)
  ✓ REQ-001: JWT autentikáció          → change/auth-system (merged)
  ✓ REQ-002: User profil               → change/user-profile (running)
  ✗ REQ-003: Admin panel                → (not assigned)
  ...
```

A `update_coverage_status()` függvény automatikusan frissíti a lefedettséget, amikor egy change státusza változik (merged, failed, stb.).
