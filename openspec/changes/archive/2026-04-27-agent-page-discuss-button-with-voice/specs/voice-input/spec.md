## MODIFIED Requirements

### Requirement: Language selector
The voice input component SHALL include a language selector dropdown with Hungarian (HU) and English (EN) options. The selected language SHALL be passed as `languageHints` to the Soniox SDK. The selection SHALL persist in localStorage under key `set-voice-lang`.

#### Scenario: Switch language to Hungarian
- **WHEN** user selects "HU" from the language dropdown
- **THEN** the next recording session uses Hungarian language hints and the selection is saved to localStorage

#### Scenario: Default language for new users
- **WHEN** user opens the chat for the first time (no `set-voice-lang` entry in localStorage)
- **THEN** the language selector defaults to English (EN)

#### Scenario: Returning user preference preserved
- **WHEN** user previously selected Hungarian and reloads the page (localStorage has `set-voice-lang=hu`)
- **THEN** the language selector shows Hungarian (HU) — the existing preference is not overwritten by the new English default

## ADDED Requirements

### Requirement: Agent tab splash screen with DISCUSS WITH AGENT button
The Agent tab SHALL display a centered splash screen whenever the chat has no messages and the agent is idle. The splash SHALL contain a large primary button labeled "DISCUSS WITH AGENT". Clicking the button SHALL send `{"type": "start"}` over the chat WebSocket, causing the server to spawn the greeting subprocess. The splash SHALL disappear once any messages exist or the agent status becomes `thinking`/`responding`.

#### Scenario: Splash on empty session
- **WHEN** the Agent tab mounts and the WebSocket reports `history_replay` with zero messages
- **THEN** a centered splash is rendered with a large "DISCUSS WITH AGENT" button
- **AND** the text input and send button are NOT shown

#### Scenario: Splash hidden when history exists
- **WHEN** the Agent tab mounts and the WebSocket reports `history_replay` with one or more messages
- **THEN** the splash is NOT rendered — the existing chat messages and input area are shown instead

#### Scenario: Click starts the session
- **WHEN** the user clicks "DISCUSS WITH AGENT"
- **THEN** the client sends `{"type": "start"}` over the WebSocket
- **AND** the splash disappears and the normal chat view is shown
- **AND** the agent greets the user in English

#### Scenario: Splash returns after New Session
- **WHEN** the user clicks "New Session" and the server broadcasts `session_cleared`
- **THEN** the splash is rendered again (messages are empty and status is idle)
- **AND** no greeting is spawned until the user clicks "DISCUSS WITH AGENT" or types a message

### Requirement: Agent tab placement in dashboard tab bar
The dashboard tab bar SHALL place the `agent` tab as the second-to-last visible tab, immediately before the `battle` tab. This applies regardless of which optional tabs (`digest`, `audit`, `plan`) are hidden.

#### Scenario: Default tab order with all optional tabs visible
- **WHEN** the dashboard renders with `hasDigest`, `hasAudit`, and `hasPlans` all true
- **THEN** the rightmost two tabs in order are `agent` then `battle`
- **AND** no other tab appears between `agent` and `battle`

#### Scenario: Tab order with optional tabs hidden
- **WHEN** the dashboard renders with all optional tabs hidden
- **THEN** the rightmost two visible tabs in order are still `agent` then `battle`

### Requirement: Voice entry button on splash screen
When a Soniox API key is available (the Agent tab has successfully fetched `/api/soniox-key`) and `navigator.mediaDevices.getUserMedia` is supported, the splash screen SHALL render a secondary voice entry button next to or below the primary "DISCUSS WITH AGENT" button. Clicking the voice button SHALL begin voice recording immediately. When the user stops recording, the transcribed text SHALL be sent as a normal user `message` — this becomes the opening utterance and the agent responds directly to it (no server-side greeting is spawned for the voice path).

#### Scenario: Voice button visible when Soniox configured
- **WHEN** the splash is rendered and `/api/soniox-key` returned a valid key
- **AND** `navigator.mediaDevices.getUserMedia` is supported
- **THEN** a voice entry button (microphone icon) is rendered alongside the "DISCUSS WITH AGENT" button

#### Scenario: Voice button hidden when Soniox missing
- **WHEN** the splash is rendered and `/api/soniox-key` returned 404
- **THEN** only the "DISCUSS WITH AGENT" button is shown — no voice entry button

#### Scenario: Voice button hidden when mic unavailable
- **WHEN** the splash is rendered on plain HTTP and `navigator.mediaDevices.getUserMedia` is undefined
- **THEN** only the "DISCUSS WITH AGENT" button is shown — no voice entry button

#### Scenario: Voice entry starts recording
- **WHEN** the user clicks the voice entry button on the splash
- **THEN** the Soniox recorder begins capturing audio immediately (no `start` message is sent)
- **AND** when the user stops recording, the transcribed text is sent as a user `{"type": "message", "content": ...}` over the WebSocket
- **AND** the agent responds directly to that message (no separate English greeting is spawned)
