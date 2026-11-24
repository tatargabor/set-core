## 1. Core rules and state (core, `lib/set_orch/fleet/relay_discord.py`)

- [ ] 1.1 Config readers: token file (`~/.config/set-core/relay-discord.token`, mode checked), `relay_discord.channel_id`, `relay_discord.allowed_users` (a JSON list or comma list of ids); `missing()` names what is absent. Tests. [REQ: only-allowed-users-answer]
- [ ] 1.2 `decide(post, reactions_by_user, replies, allowed)`: the pure answer rules (❌ defer, multi collect + ✅ close, single: last reply, "number + note", one reaction, two reactions = no answer; bot's own and strangers' reactions ignored). One test per spec scenario, plus a mutation of the "two reactions" and the allowed-user checks. [REQ: the-answer-is-decided-from-reactions-and-replies-by-fixed-rules]
- [ ] 1.3 Post records under `<relay state>/discord/posts/` (mode 600, atomic write): create, mark answered/closed, list open, prune after 7 days. Tests. [REQ: the-bridge-posts-each-relayed-question-to-the-channel]
- [ ] 1.4 `message_text(entry, kind)`: project · session from `source`, the kind label, the question, options 1–5 numbered, the rest as text; under Discord's 2000-char limit (the question cut, never the options). Tests. [REQ: the-bridge-posts-each-relayed-question-to-the-channel]

## 2. Discord transport (core)

- [ ] 2.1 A thin REST client on `urllib` (v10): post message, add reaction, list reaction users per emoji, list channel messages after an id, reply with `message_reference`, `GET /users/@me`, `GET /channels/<id>`; one retry on 429 after `retry_after`; errors raised with the HTTP status only. Tests against a fake opener. [REQ: the-bridge-posts-each-relayed-question-to-the-channel]
- [ ] 2.2 Log lines carry call id, key, HTTP status and outcome only; a test runs post + poll with a distinctive question text and asserts it is absent from the captured log. [REQ: logs-carry-ids-and-outcomes-never-text]

## 3. Commands (`bin/set-relay-discord`)

- [ ] 3.1 `post`: envelope from stdin → one message per question + reactions (numbers, ❌, ✅ for multi) → post record; exit 0 only if all posted; not configured → exit non-zero with the missing item. Tests with the fake transport, including a mid-envelope failure. [REQ: the-bridge-posts-each-relayed-question-to-the-channel]
- [ ] 3.2 `poll`: for each open post — answer file exists → mark answered, reply "answered elsewhere"; no waiting record with its id past the 2-minute grace → reply closed, mark closed (nothing closed when `waiting/` is unreadable); else gather allowed reactions + replies → `decide` → write `{"valasz": …}` (600, atomic, never over an existing file) → 🖥️ + reply naming the answer → mark answered. Tests for each branch. [REQ: a-written-answer-reaches-the-relay-and-is-acknowledged]
- [ ] 3.3 The close path as its own tests: terminal answer → closed after grace; inside the grace → left open; unreadable waiting dir → nothing closed. [REQ: a-post-whose-question-no-longer-waits-is-closed]
- [ ] 3.4 `setup --channel --allow … [--token-stdin] [--replace] [--remove]`: token file 600, config keys, `GET /users/@me` + channel check, wiring per D7 (auto-answer forward vs relay command; refuse a foreign command without `--replace`, print it; record the previous value for `--remove`), the user timer (`set-relay-discord.timer`, every minute, `poll`). `status` (config, token check, timer, open/answered counts, never the token) and `test` (probe post; reports an empty-content reply as the missing Message Content intent). Tests with a fake transport, a tmp config dir and a fake systemctl. [REQ: setup-wires-one-machine-and-says-what-it-checked]
- [ ] 3.5 Capability guide line in `.claude/rules/capability-guide.md`. [REQ: setup-wires-one-machine-and-says-what-it-checked]

## 4. Live

- [ ] 4.1 End to end with a REAL bot token and channel: setup, a scratch fleet agent asks one question, the post appears, an allowed 1️⃣ answers it, the agent continues with option 1, the post carries 🖥️ and the reply; then a second question answered at the terminal is closed on Discord. Record in `measurements.md`. NEEDS the operator's test bot token and channel, or runs on the teammate's machine — stays open until one of them is done. [REQ: a-written-answer-reaches-the-relay-and-is-acknowledged]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN the relay pipes a one-question two-option envelope THEN one message with project, kind, question and options 1–2 is posted, with 1️⃣ 2️⃣ ❌, a post record, exit 0 [REQ: the-bridge-posts-each-relayed-question-to-the-channel, scenario: a-two-option-question-is-posted]
- [ ] AC-2: WHEN Discord is unreachable or refuses THEN exit non-zero, no record for that question, log with id and status only [REQ: the-bridge-posts-each-relayed-question-to-the-channel, scenario: discord-is-unreachable]
- [ ] AC-3: WHEN `post` runs without token, channel or allowed users THEN nothing is posted and the missing item is named [REQ: the-bridge-posts-each-relayed-question-to-the-channel, scenario: not-configured]
- [ ] AC-4: WHEN a user not on the allowed list reacts THEN no answer is written [REQ: only-allowed-users-answer, scenario: a-stranger-reacts]
- [ ] AC-5: WHEN an allowed 2️⃣ lands on a Yes/No post THEN "No" is written [REQ: the-answer-is-decided-from-reactions-and-replies-by-fixed-rules, scenario: one-reaction-answers-a-single-question]
- [ ] AC-6: WHEN the reply is "1, but only after the review" THEN "Yes — but only after the review" is written [REQ: the-answer-is-decided-from-reactions-and-replies-by-fixed-rules, scenario: a-numbered-reply-with-a-note]
- [ ] AC-7: WHEN the reply is free text THEN it is written verbatim [REQ: the-answer-is-decided-from-reactions-and-replies-by-fixed-rules, scenario: free-text]
- [ ] AC-8: WHEN a multi-select post has 1️⃣ 3️⃣ and no ✅ THEN nothing; after ✅ the two options joined [REQ: the-answer-is-decided-from-reactions-and-replies-by-fixed-rules, scenario: multi-select-waits-for-✅]
- [ ] AC-9: WHEN a single-select post has 1️⃣ and 2️⃣ and no reply THEN nothing is written [REQ: the-answer-is-decided-from-reactions-and-replies-by-fixed-rules, scenario: two-reactions-on-a-single-question]
- [ ] AC-10: WHEN the relay waits and an allowed 1️⃣ lands THEN within one poll the answer file holds option 1, the relay answers, the post has 🖥️ and a reply [REQ: a-written-answer-reaches-the-relay-and-is-acknowledged, scenario: the-answer-reaches-the-waiting-agent]
- [ ] AC-11: WHEN the answer file already exists THEN nothing is written, the post is marked answered with an "answered elsewhere" reply [REQ: a-written-answer-reaches-the-relay-and-is-acknowledged, scenario: the-fleet-answered-first]
- [ ] AC-12: WHEN the question is answered at the terminal THEN after the grace the post gets "closed" and no answer is written [REQ: a-post-whose-question-no-longer-waits-is-closed, scenario: answered-at-the-terminal]
- [ ] AC-13: WHEN the waiting records cannot be read THEN nothing is closed [REQ: a-post-whose-question-no-longer-waits-is-closed, scenario: the-waiting-folder-is-unreadable]
- [ ] AC-14: WHEN setup runs with a valid token, readable channel, one allowed user THEN token file 600, config set, relay wired, timer active, each check named [REQ: setup-wires-one-machine-and-says-what-it-checked, scenario: first-setup]
- [ ] AC-15: WHEN setup meets another bridge without `--replace` THEN nothing is rewired and the existing command and the flag are named [REQ: setup-wires-one-machine-and-says-what-it-checked, scenario: an-existing-bridge-is-configured]
- [ ] AC-16: WHEN a question is posted and answered THEN the logs name ids and outcomes and never the question text [REQ: logs-carry-ids-and-outcomes-never-text, scenario: a-posted-and-answered-question]
