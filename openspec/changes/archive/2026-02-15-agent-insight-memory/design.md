## Context

A `set-memory` CLI wrapper jelenleg a shodh-memory alapvető API-ját használja: `remember()`, `recall()`, `list_memories()`, `get_stats()`. A shodh-memory v0.1.75 ennél sokkal többet tud — proactive context retrieval, recall modes, tag-based filtering, forget operations — de ezek nincsenek exponálva a CLI-ben.

Az OpenSpec SKILL.md fájlok memory hookjai:
- **Recall**: egyszerű keyword-alapú `recall "change-name keywords"` — nem használja a tag filterezést vagy recall mode-okat
- **Remember**: user-shared knowledge mentése mid-flow-ban (continue/ff/explore/apply), agent saját meglátásai csak apply Step 7-ben és archive-nál
- **Hiányzik**: verify-change, sync-specs, onboard nem használják a memóriát; agent self-reflection nincs a continue/ff/explore végén

## Goals / Non-Goals

**Goals:**
- `set-memory` CLI bővítése az összes hasznos shodh-memory v0.1.75 képességgel
- Agent self-reflection step minden releváns OpenSpec skill végéhez
- Enhanced recall (tag filter, mode) használata a SKILL.md hookokban
- Egységes tagging strategy (`source:agent`/`source:user`, `change:<name>`, `phase:<skill>`)
- Verify és sync-specs skillek memory-integrációja
- Invalid type-ok (`Observation`/`Event`) javítása a SKILL.md fájlokban

**Non-Goals:**
- GUI integráció az új CLI képességekhez (külön change)
- shodh-memory HTTP/Client API használata (maradunk a native Rust/PyO3-nál)
- Meglévő memóriák migrációja vagy retag-elése
- A `set-memory-hooks` automatikus install tool módosítása (a hook template-ek változnak, az install mechanizmus nem)

## Decisions

### D1: CLI command struktúra — flat commands, briefing alapján

A `shodh-upgrade-briefing.md` pontos CLI interfészt definiál. Ezt követjük:

```
set-memory forget <id>                     # single delete
set-memory forget --all --confirm          # delete all (confirmation required)
set-memory forget --older-than <days>      # age-based
set-memory forget --tags <t1,t2>           # tag-based
set-memory forget --pattern <regex>        # pattern-based
set-memory recall "query" --tags t1,t2 --mode hybrid  # enhanced recall
set-memory list --type Decision --limit 20             # filtered list
set-memory context [topic]                 # context_summary
set-memory brain                           # brain_state
set-memory get <id>                        # single memory by ID
set-memory health --index                  # index health
set-memory repair                          # repair index
```

**Rationale**: A briefing alapos kutatás eredménye, a flat command struktúra konzisztens a meglévő CLI felülettel. Az `inspect` alias-t kihagyjuk — felesleges indirection.

### D2: Agent self-reflection — session-végi összegzés, nem folyamatos

Az agent self-reflection egy explicit step a session végén (nem inline mentés minden egyes gondolatnál):

```
Skill vége előtt (continue/ff/explore):
1. Az agent visszanézi a session-t
2. Összegyűjti a saját meglátásait:
   - Döntési indoklások (miért X és nem Y)
   - Felfedezett patternek (ami a codebase-ből derült ki)
   - Meglepetések / gotcha-k
3. Minden releváns meglátást egyenként lement:
   echo "<insight>" | set-memory remember --type <Learning|Decision> \
     --tags change:<name>,phase:<skill>,source:agent
4. Rövid összegzés: "[Agent insights saved: N items]"
```

**Rationale**: Session-végi reflekció jobb mint inline, mert:
- Nem töri meg a flow-t
- Az agent visszanézve jobban tudja szűrni mi volt tényleg értékes
- Nem duplikál a mid-flow user-save-vel
- Konzisztens az apply Step 7 mintával (ami már így működik)

**Alternatives considered:**
- Folyamatos inline save → túl zajos, megszakítja a gondolkodást
- Csak a legfontosabb 1 insight → túl szűk, értékes meglátások veszhetnek el

### D3: Tagging strategy — structured tags, kereshetőség

```
Jelenlegi:   --tags repo,<change-name>,error
Új:          --tags change:<name>,phase:<skill>,source:<agent|user>,<topic>
```

Tag struktúra:
- `change:<name>` — melyik change-hez tartozik (replace: repo,change-name)
- `phase:<skill>` — melyik skill fázisban született (explore/continue/ff/apply/verify/archive)
- `source:agent` vagy `source:user` — ki látta meg (agent self-reflection vs user-shared)
- `<topic>` — szabad topic tag (error, pattern, decision, architecture, etc.)

**Rationale**: A strukturált tag-ek lehetővé teszik a `recall --tags change:add-auth,phase:apply` típusú célzott keresést. A `source:` tag megkülönbözteti az agent és user meglátásokat — a recall-nál mindkettőt visszakapjuk, de a source meta-info segít a kontextus megértésében.

**Backwards compatibility**: Meglévő `repo,change-name` tag-ű memóriák továbbra is visszajönnek szabad-szöveges recall-nál. Az új tag-ek additívak.

### D4: Enhanced recall használata a hookokban

A jelenlegi recall pattern:
```bash
set-memory recall "<change-name> <keywords>" --limit 5
```

Lecserélni erre ahol releváns:
```bash
set-memory recall "<change-name> <context>" --limit 5 --mode hybrid --tags change:<name>
```

- `--mode hybrid` — kombinált semantic + temporal keresés, a legrelevánsabb találatokat adja
- `--tags change:<name>` — szűkíti a keresést az adott change-hez kapcsolódó memóriákra
- Ha a `--tags` nem talál elég eredményt, a hybrid mode a szemantikus keresés révén tágabb kontextusból is hozhat

**Skill-specifikus recall finomhangolás:**

| Skill | Recall query | Mode | Tags filter |
|-------|-------------|------|-------------|
| explore | `"<user-topic>"` | hybrid | — (szabad keresés) |
| continue | `"<change-name> <proposal-keywords>"` | hybrid | `change:<name>` |
| ff | `"<change-name> <description>"` | hybrid | `change:<name>` |
| apply | `"<change-name> implementation errors"` | hybrid | `change:<name>` |
| verify | `"<change-name> verification issues"` | hybrid | `change:<name>` |
| sync-specs | `"<change-name> spec decisions"` | hybrid | `change:<name>` |

### D5: Verify-change memory integration — problémák és tanulságok

A verify skill jelenleg teljesen memory-mentes. Kiegészítjük:

**Recall (step elején):**
```bash
set-memory recall "<change-name> verification issues bugs" --limit 5 --mode hybrid --tags change:<name>
```

**Remember (step végén):**
- Ha a verifikáció problémákat talált → save each as Learning:
  ```bash
  echo "<issue description and root cause>" | set-memory remember \
    --type Learning --tags change:<name>,phase:verify,source:agent,issue
  ```
- Ha a verifikáció sikeres és van tanulság → save as Learning:
  ```bash
  echo "<what was verified and why it passed>" | set-memory remember \
    --type Learning --tags change:<name>,phase:verify,source:agent,pattern
  ```

### D6: Sync-specs memory integration — döntések mentése

A sync-specs skill jelenleg nem ment memóriát. Kiegészítjük:

**Remember (merge döntéseknél):**
- Ha a spec merge során döntés születik (conflict resolution, spec refinement):
  ```bash
  echo "<spec merge decision and rationale>" | set-memory remember \
    --type Decision --tags change:<name>,phase:sync-specs,source:agent,spec-merge
  ```

### D7: Invalid type cleanup — Learning és Context everywhere

A SKILL.md fájlokban még előforduló `--type Observation` → `--type Learning`, `--type Event` → `--type Context` csere. Ez egyszerű find-and-replace az érintett fájlokban:

- `openspec-apply-change/SKILL.md`: Step 7 — `Observation` → `Learning`, `Event` → `Context`
- `openspec-archive-change/SKILL.md`: Step 7 — `Event` → `Context`
- `openspec-explore/SKILL.md`: type options — remove `Observation` from alternatives
- `openspec-continue-change/SKILL.md`: mid-flow — remove `Observation` from alternatives
- `openspec-ff-change/SKILL.md`: mid-flow — remove `Observation` from alternatives

### D8: CLI implementation follows existing patterns

Minden új CLI command követi a meglévő mintát:
1. Args parsing a case statement-ben
2. `cmd_health` check — silent no-op ha shodh-memory nincs telepítve
3. `get_storage_path` + `mkdir -p`
4. `run_with_lock run_shodh_python -c "..."` (env vars data passing)
5. JSON stdout, errors to log file
6. Graceful degradation: `[]` vagy `{}` on failure

A destructive `forget --all` **MUST** require `--confirm` flag — nincs interactive prompt.

## Risks / Trade-offs

**[Tag verbosity]** → Az új tag struktúra (`change:X,phase:Y,source:agent,topic`) hosszabb mint a régi (`repo,X,error`). Trade-off: jobb kereshetőség vs több karakternyi tag per memory. Elfogadható — a tag-ek nem jelennek meg a user-nek.

**[Over-saving]** → Az agent self-reflection minden skill végén extra memóriákat termel. Mitigation: explicit threshold — "only save if a future agent in a different session would benefit". Ha a session-ben nem volt érdemi meglátás, ne mentsünk semmit. Az összegzés `[Agent insights saved: 0 items]` legyen ha nincs mit menteni.

**[Recall noise]** → A `--tags change:<name>` filter szűkít, de ha egy change-nek sok memóriája van, zajos lehet. Mitigation: `--limit 5` megmarad, és a `--mode hybrid` a temporal relevancia alapján is rangsorol.

**[shodh-memory version dependency]** → Az új CLI commands a v0.1.75 API-t használják. Ha régebbi verzió van telepítve, ezek a commands fail-elhetnek. Mitigation: minden command-ban try/except a Python kódban, graceful degradation error message-el. A `health` command megmarad backwards compatible.

**[Forget safety]** → A forget operations destructive-ok. Mitigation: `forget --all` requires `--confirm`; egyéb forget commands explicit target-et kérnek (id, tags, pattern). Nincs "oops" path.
