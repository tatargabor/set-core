## ADDED Requirements

### Requirement: Microphone toggle button
The voice input component SHALL display a microphone icon button next to the text input. Clicking the button SHALL start audio recording via the Soniox Web SDK. Clicking again SHALL stop recording. The button SHALL visually indicate recording state (idle: default, recording: red/pulsing).

#### Scenario: Start recording
- **WHEN** user clicks the microphone button while idle
- **THEN** the browser requests microphone permission (if not already granted), Soniox starts streaming audio, and the button changes to red/pulsing state

#### Scenario: Stop recording
- **WHEN** user clicks the microphone button while recording
- **THEN** Soniox stops recording, final transcript is placed in the text input, and the button returns to idle state

#### Scenario: Microphone permission denied
- **WHEN** user denies microphone permission
- **THEN** the button returns to idle state and a brief error message is shown

### Requirement: Real-time partial transcription
While recording, the Soniox SDK SHALL stream partial transcription results into the text input field in real-time. The user SHALL see words appearing as they speak.

#### Scenario: Partial results during speech
- **WHEN** user is speaking and Soniox returns partial tokens
- **THEN** the textarea shows the accumulated partial text, updating as new tokens arrive

#### Scenario: Final result on stop
- **WHEN** user stops recording
- **THEN** the textarea contains the final transcript, cursor is at the end, and the text is editable

### Requirement: Editable transcript
After recording stops, the transcribed text SHALL remain in the text input as editable text. The user SHALL be able to modify, append, or delete text before sending.

#### Scenario: Fix transcription error
- **WHEN** Soniox transcribes "rebase-t" as "rebase tea" and user stops recording
- **THEN** the user can click into the textarea, select "tea", and type "t" to correct it before sending

### Requirement: Language selector
The voice input component SHALL include a language selector dropdown with Hungarian (HU) and English (EN) options. The selected language SHALL be passed as `languageHints` to the Soniox SDK. The selection SHALL persist in localStorage.

#### Scenario: Switch language to English
- **WHEN** user selects "EN" from the language dropdown
- **THEN** the next recording session uses English language hints and the selection is saved to localStorage

#### Scenario: Default language
- **WHEN** user opens the chat for the first time (no localStorage entry)
- **THEN** the language selector defaults to Hungarian (HU)

### Requirement: Soniox API key retrieval
The voice input component SHALL fetch the Soniox API key from `GET /api/soniox-key` on mount. The key SHALL NOT be embedded in the JS bundle. If the endpoint returns 404 (key not configured), the component SHALL hide voice input controls.

#### Scenario: API key available
- **WHEN** the component mounts and `GET /api/soniox-key` returns a key
- **THEN** the microphone button and language selector are visible and functional

#### Scenario: API key not configured
- **WHEN** the component mounts and `GET /api/soniox-key` returns 404
- **THEN** only the text input and send button are visible — no microphone button, no language selector

### Requirement: Mobile and Tailscale compatibility
The voice input component SHALL use 44px minimum touch targets for the microphone button and language selector. On mobile viewports (<768px), the input controls SHALL be touch-friendly. Microphone access requires HTTPS on non-localhost origins; when `getUserMedia` fails due to insecure context, the component SHALL hide voice controls and fall back to text-only.

#### Scenario: Voice input on mobile over Tailscale HTTPS
- **WHEN** user opens the dashboard on mobile Chrome via Tailscale MagicDNS (HTTPS)
- **THEN** microphone button is visible with 44px tap target, recording works

#### Scenario: Voice input on non-HTTPS remote access
- **WHEN** user opens the dashboard via plain HTTP on a non-localhost address
- **THEN** `getUserMedia` is unavailable, mic button is hidden, text input works normally

### Requirement: Recording duration display
While recording, the component SHALL display the elapsed recording time next to the microphone button (e.g., "0:05").

#### Scenario: Recording timer
- **WHEN** user has been recording for 12 seconds
- **THEN** the display shows "0:12" next to the pulsing microphone button
