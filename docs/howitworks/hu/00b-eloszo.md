# Előszó

A 2000-es évek elején Magyarországon dolgoztam egy Nokia alvállalkozói csapatban. SMS gateway-eket és hasonló telekommunikációs rendszereket fejlesztettünk — a korszak nagy infrastruktúra projektjeit, ahol a megbízhatóság nem opció volt, hanem alapkövetelmény. Millió felhasználó üzenetei mentek át a szervereinkenen, és minden perc kiesés mért költséget jelentett.

Abban a környezetben tanultam meg, mit jelent a *rendszerszintű gondolkodás*: nem elég, ha egy komponens működik — az egész pipeline-nak kell működnie, végig, éjjel-nappal, emberi beavatkozás nélkül. A Nokia mérnöki kultúrájában minden rendszernek volt monitoring-ja, watchdog-ja, és eszkalációs terve. Ha valami megállt, nem egy ember ment ránézni — a rendszer maga próbálta meg először javítani.

Ez a szemlélet húsz évvel később, egy teljesen más technológiai környezetben köszönt vissza.

---

A `wt-orchestrate` ugyanazt a problémát oldja meg, amit a Nokia infrastruktúráknál tanultam: hogyan futtassunk *autonóm, többlépéses pipeline-okat* úgy, hogy a rendszer magától kezelje a hibákat, magától eszkaláljon, és csak akkor kérjen embert, ha tényleg muszáj.

A különbség: itt nem SMS-ek mennek át a pipeline-on, hanem *szoftver-fejlesztési feladatok*. Az "ágens" nem egy hardveres node, hanem egy Claude Code session egy git worktree-ben. A "watchdog" nem hardveres heartbeat-et figyel, hanem a `loop-state.json` iterációs hash-ét. De a minta ugyanaz:

- **Dispatch** → **Monitor** → **Detect failure** → **Escalate** → **Recover or fail gracefully**

Ez a dokumentáció végigvezet ezen a pipeline-on, az inputtól a végső merge-ig.

\begin{fontos}
Ez nem egy elméleti dokumentum. Minden funkció, amit itt leírunk, éles projekteken lett tesztelve és fejlesztve — a wt-orchestrate naponta fut production kódbázisokon, autonóm módon, órákig, emberi beavatkozás nélkül.
\end{fontos}
