## 1. Dependencies & Config Schema

- [x] 1.1 Add `discord.py` to project dependencies [REQ: bot-connection-lifecycle]
- [x] 1.2 Add `discord:` config section schema to orchestration config loader [REQ: project-level-discord-configuration]
- [x] 1.3 Add `SET_DISCORD_TOKEN` env var reading to config resolution [REQ: bot-token-via-environment]

## 2. Bot Core

- [x] 2.1 Create `lib/set_orch/discord/__init__.py` with `DiscordBot` class (connect, disconnect, background task) [REQ: bot-connection-lifecycle]
- [x] 2.2 Implement `ChannelResolver` in `lib/set_orch/discord/channel.py` — find or create `#<project-name>` channel [REQ: channel-resolution]
- [x] 2.3 Implement `ThreadManager` in `lib/set_orch/discord/threads.py` — create thread per run, reuse on restart [REQ: thread-management]
- [x] 2.4 Implement `EmbedThrottle` in `lib/set_orch/discord/throttle.py` — 30-second batched embed edits [REQ: rate-limit-compliance]

## 3. Embed Builders

- [x] 3.1 Create `lib/set_orch/discord/embeds.py` — run status embed builder (per-change rows, progress bars, token count) [REQ: live-status-embed]
- [x] 3.2 Implement summary embed builder for run completion [REQ: event-to-discord-mapping]
- [x] 3.3 Implement error embed builder with @mention support [REQ: event-to-discord-mapping]

## 4. Event Handler

- [x] 4.1 Create `lib/set_orch/discord/events.py` — subscribe to event bus, route events to Discord actions [REQ: event-to-discord-mapping]
- [x] 4.2 Implement run start → main channel message + thread creation [REQ: event-to-discord-mapping]
- [x] 4.3 Implement STATE_CHANGE → thread embed in-place update [REQ: event-to-discord-mapping]
- [x] 4.4 Implement MERGE_ATTEMPT success → thread update + main channel one-liner [REQ: event-to-discord-mapping]
- [x] 4.5 Implement crash/stuck → main channel alert with @mention [REQ: event-to-discord-mapping]
- [x] 4.6 Implement run complete → thread summary embed + main channel summary [REQ: event-to-discord-mapping]

## 5. Notification Channel Integration

- [x] 5.1 Add `_send_discord()` handler to `notifications.py` [REQ: multi-channel-notification-dispatch]
- [x] 5.2 Register `"discord"` in the channel dispatch map [REQ: multi-channel-notification-dispatch]
- [x] 5.3 Handle bot-not-connected case (skip silently with debug log) [REQ: multi-channel-notification-dispatch]

## 6. Member Mapping & Mentions

- [x] 6.1 Implement member_map lookup in config (set-core member ID → Discord user ID) [REQ: member-to-discord-mapping]
- [x] 6.2 Implement mention_on_error fallback for unmapped members [REQ: member-to-discord-mapping]

## 7. Event Filtering

- [x] 7.1 Implement `notify_on` config filtering — only configured event types post to main channel [REQ: event-filtering]
- [x] 7.2 Ensure filtered events still update thread embeds (filter applies to main channel only) [REQ: event-filtering]

## 8. Lifecycle Integration

- [x] 8.1 Start Discord bot as background task in uvicorn startup hook [REQ: bot-connection-lifecycle]
- [x] 8.2 Stop Discord bot in uvicorn shutdown hook (flush pending edits, disconnect) [REQ: bot-connection-lifecycle]
- [x] 8.3 Implement supervisor wrapper — catch bot exceptions without crashing API server [REQ: bot-connection-lifecycle]

## 9. Documentation

- [x] 9.1 Add Discord setup instructions to docs (create bot, get token, configure guild_id) [REQ: project-level-discord-configuration]
- [x] 9.2 Add `discord:` section example to orchestration.yaml template [REQ: project-level-discord-configuration]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN orchestration starts and discord.enabled is true THEN bot connects and sets presence [REQ: bot-connection-lifecycle, scenario: bot-connects-on-orchestration-start]
- [x] AC-2: WHEN discord.enabled is false or SET_DISCORD_TOKEN unset THEN no connection attempted [REQ: bot-connection-lifecycle, scenario: bot-skipped-when-not-configured]
- [x] AC-3: WHEN bot connects and #project-name channel exists THEN bot uses that channel [REQ: channel-resolution, scenario: existing-channel-found]
- [x] AC-4: WHEN bot connects and no channel exists and has permission THEN bot creates channel [REQ: channel-resolution, scenario: channel-auto-created]
- [x] AC-5: WHEN orchestration starts a new run THEN thread created with status embed [REQ: thread-management, scenario: thread-created-on-run-start]
- [x] AC-6: WHEN orchestrator restarts for same run THEN existing thread is reused [REQ: thread-management, scenario: existing-thread-reused-on-restart]
- [x] AC-7: WHEN STATE_CHANGE event emitted THEN thread embed is edited in-place [REQ: event-to-discord-mapping, scenario: change-status-update]
- [x] AC-8: WHEN merge succeeds THEN thread updated + main channel one-liner [REQ: event-to-discord-mapping, scenario: merge-success]
- [x] AC-9: WHEN crash/stuck detected THEN main channel alert with @mention [REQ: event-to-discord-mapping, scenario: agent-stuck-or-crash]
- [x] AC-10: WHEN run completes THEN summary embed + main channel summary [REQ: event-to-discord-mapping, scenario: run-complete]
- [x] AC-11: WHEN activity changes THEN embed updates at most once per 30 seconds [REQ: rate-limit-compliance, scenario: embed-edit-throttling]
- [x] AC-12: WHEN channel includes "discord" and bot connected THEN message posted [REQ: multi-channel-notification-dispatch, scenario: discord-notification]
- [x] AC-13: WHEN channel includes "discord" but bot not connected THEN skipped silently [REQ: multi-channel-notification-dispatch, scenario: discord-bot-not-connected]
- [x] AC-14: WHEN error for mapped member THEN @mention that Discord user [REQ: member-to-discord-mapping, scenario: mapped-member-gets-mentioned]
- [x] AC-15: WHEN notify_on is filtered THEN only listed events post to main channel [REQ: event-filtering, scenario: filtered-events]
