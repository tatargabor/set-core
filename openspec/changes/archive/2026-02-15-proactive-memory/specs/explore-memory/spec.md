## ADDED Requirements

### Requirement: Recall at explore start
The `/opsx:explore` skill SHALL check `set-memory health` at the beginning of an explore session. If healthy, it SHALL run `set-memory recall` with the user's topic as query and use relevant memories to inform the exploration. If health fails, it SHALL skip silently.

#### Scenario: Explore with relevant past memories
- **WHEN** user starts `/opsx:explore redis caching options` and memories exist about Redis
- **THEN** the agent runs `set-memory recall "redis caching options" --limit 5` and incorporates relevant results (e.g., "Note: Past memory found — Redis was too slow for per-request caching in this project")

#### Scenario: Explore with no relevant memories
- **WHEN** user starts `/opsx:explore` and no relevant memories match
- **THEN** the agent proceeds normally without mentioning memory

#### Scenario: Memory service unavailable
- **WHEN** user starts `/opsx:explore` and `set-memory health` fails
- **THEN** the agent skips recall silently and proceeds normally

### Requirement: Remember during exploration
During an explore session, the agent SHALL recognize when the user shares knowledge worth preserving and save it using `set-memory remember`. Recognition SHALL be language-independent — based on semantic intent, not keyword matching. The agent SHALL briefly confirm what was saved (one line) and continue the conversation.

#### Scenario: User shares negative experience (any language)
- **WHEN** user says something expressing "we tried X and it didn't work" (in any language, e.g., "ezt már kipróbáltuk és nem volt jó", "we tried this and it was bad", "das haben wir probiert, hat nicht funktioniert")
- **THEN** the agent saves an Observation memory with the what and why, tags it with the topic, and says e.g., "Saved to memory: Redis caching was too slow for per-request use"

#### Scenario: User shares a decision or preference
- **WHEN** user says something expressing a decision or constraint (e.g., "mindig --force-ot használjunk", "always use TypeScript not JavaScript", "soha ne commitolj automatikusan")
- **THEN** the agent saves a Decision memory, tags it with the topic

#### Scenario: User shares a technical learning
- **WHEN** user says something expressing a discovered pattern or gotcha (e.g., "az openspec update felülírja a SKILL.md-t", "the API returns 500 on empty arrays")
- **THEN** the agent saves a Learning memory, tags it with the topic

#### Scenario: Trivial or obvious statements are NOT saved
- **WHEN** user says something that is general knowledge, conversational filler, or a question (e.g., "hmm interesting", "what do you think?", "let's see")
- **THEN** the agent does NOT save anything — only genuinely valuable insights are saved

#### Scenario: Agent confirms briefly, doesn't interrupt flow
- **WHEN** the agent saves a memory during exploration
- **THEN** it shows a single brief confirmation line (e.g., "Saved: [Observation] Redis caching too slow") and continues the conversation without breaking the exploration flow
