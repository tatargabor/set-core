## ADDED Requirements

### Requirement: A non-question blocking message is notified, never answered

While this machine's relay switch is on, a terminal-blocking message that is not a question — a permission request, the runtime's waiting-for-input notice, delivered by the runtime's notification event — SHALL be posted to the configured notify outbound as a one-way notification naming the project, the agent label, and the message. The notification SHALL have no answer path: the hook SHALL NOT wait, SHALL NOT produce tool-affecting output, and SHALL exit 0 promptly; the terminal remains the only place the message is acted on.

#### Scenario: Permission prompt relayed

- **WHEN** a session raises a permission request while the switch is on and a notify outbound is configured
- **THEN** the outbound receives one notification naming the project, the agent, and the request within seconds, and the terminal keeps showing the prompt unchanged

#### Scenario: Switch off

- **WHEN** `question_relay.enabled` is not true and a notification event fires
- **THEN** the hook exits 0 with no output and no process started, exactly as when the relay was absent

### Requirement: Notify configuration is reported, never completed by guess

The notify outbound SHALL be read from local configuration only: `question_relay.notify_command` (a command that reads the notification envelope on stdin and returns nothing), or `question_relay.webhook_url` when no notify command is set. If the switch is on and neither key is configured, the notification SHALL be dropped with the missing key named in the relay's log, and the fleet's readiness SHALL name it — the framework SHALL NOT supply a default.

#### Scenario: No notify outbound configured

- **WHEN** the switch is on, a notification fires, and neither `question_relay.notify_command` nor `question_relay.webhook_url` is set
- **THEN** nothing is sent, the relay's log names the missing key, and the session is unaffected

#### Scenario: Notify command fails

- **WHEN** the notify command is set but exits non-zero or cannot be started
- **THEN** one attempt is made, the failure is logged with its reason, and the terminal is unchanged — no retry, no blocking, no output into the session

### Requirement: The wire check counts the notification hook

A project whose hook configuration lacks the notification carrier SHALL be reported unwired by the same surface that already names projects whose question hook is missing, so a silent class of blocking messages is marked where the reader stands rather than discovered by a blocked session.

#### Scenario: Unwired project named in the header

- **WHEN** a project's hook configuration does not carry the notification carrier while the relay is on
- **THEN** the fleet's relay surface lists that project among the unwired, naming the missing hook
