# Tasks: Issue Management Console

## 1. API Client & Types

- [ ] 1.1 Add TypeScript interfaces to `web/src/lib/api.ts`: Issue, IssueState, Diagnosis, IssueGroup, MutePattern, AuditEntry, IssueStats, ProjectStatus, TimelineEntry [REQ: project-cards]
- [ ] 1.2 Add API client functions for projects: getProjects, getProjectStatus, startSentinel, stopSentinel, restartSentinel, startOrchestration, stopOrchestration [REQ: process-control-buttons]
- [ ] 1.3 Add API client functions for issues: getIssues, getIssue, createIssue, getAllIssues, getIssueStats, getAllIssueStats [REQ: urgency-based-sections]
- [ ] 1.4 Add API client functions for issue actions: investigateIssue, fixIssue, dismissIssue, cancelIssue, skipIssue, muteIssue, extendTimeout, sendIssueMessage [REQ: action-api-calls]
- [ ] 1.5 Add API client functions for groups: getIssueGroups, createIssueGroup, fixGroup [REQ: multi-select-and-bulk-actions]
- [ ] 1.6 Add API client functions for mutes: getMutePatterns, addMutePattern, deleteMutePattern [REQ: mute-pattern-dialog]
- [ ] 1.7 Add API client functions for audit: getIssueAudit, getManagerStatus [REQ: timeline-construction]

## 2. Hooks

- [ ] 2.1 Create `web/src/hooks/useProjectOverview.ts`: polls getProjects every 5s [REQ: project-cards]
- [ ] 2.2 Create `web/src/hooks/useIssueData.ts`: polls getIssues + getIssueGroups + getIssueStats every 2s [REQ: urgency-based-sections]
- [ ] 2.3 Create `web/src/hooks/useIssueDetail.ts`: polls getIssue + getIssueAudit, builds unified timeline [REQ: timeline-construction]
- [ ] 2.4 Create `web/src/hooks/useIssueChat.ts`: WebSocket to /ws/{project}/issue-chat?issue_id=X [REQ: chat-input]

## 3. Shared Components

- [ ] 3.1 Create `web/src/components/issues/SeverityBadge.tsx`: colored badge for unknown/low/medium/high/critical [REQ: issue-row-display]
- [ ] 3.2 Create `web/src/components/issues/StateBadge.tsx`: colored badge with icon for all 13 states [REQ: issue-row-display]
- [ ] 3.3 Create `web/src/components/manager/ModeBadge.tsx`: E2E (blue) / PROD (red) / DEV (gray) [REQ: project-cards]
- [ ] 3.4 Create `web/src/components/issues/TimeoutCountdown.tsx`: live countdown timer + progress bar, updates every 1s [REQ: timeout-countdown-display]
- [ ] 3.5 Create `web/src/components/issues/IssueCountBadge.tsx`: summary badge with open count + nearest timeout [REQ: project-cards]
- [ ] 3.6 Create `web/src/components/shared/ChatInput.tsx`: text input + Send button, reusable [REQ: chat-input]

## 4. Projects Overview Page

- [ ] 4.1 Create `web/src/pages/Manager.tsx` page component at route `/manager` [REQ: project-cards]
- [ ] 4.2 Create `web/src/components/manager/ProjectCard.tsx`: project name, mode badge, process indicators, issue summary [REQ: project-cards]
- [ ] 4.3 Create `web/src/components/manager/ProcessControl.tsx`: green/red indicator + uptime + Start/Stop/Restart buttons [REQ: process-control-buttons]
- [ ] 4.4 Create `web/src/components/manager/ManagerStatus.tsx`: service health bar at bottom [REQ: service-health-display]
- [ ] 4.5 Wire ProcessControl buttons to API calls with optimistic updates [REQ: process-control-buttons]
- [ ] 4.6 Handle manager unreachable: show red banner with CLI instructions [REQ: service-health-display]

## 5. Issue List Page

- [ ] 5.1 Create `web/src/pages/ManagerIssues.tsx` page component at route `/manager/:project/issues` and `/manager/issues` [REQ: urgency-based-sections]
- [ ] 5.2 Create `web/src/components/issues/IssueList.tsx`: three collapsible sections by urgency [REQ: urgency-based-sections]
- [ ] 5.3 Create `web/src/components/issues/IssueRow.tsx`: checkbox, ID, severity, state, summary, source, timer, group [REQ: issue-row-display]
- [ ] 5.4 Create `web/src/components/issues/IssueFilter.tsx`: dropdown filters for state, severity, source [REQ: filters]
- [ ] 5.5 Implement client-side filtering logic [REQ: filters]
- [ ] 5.6 Create `web/src/components/issues/BulkActions.tsx`: multi-select action bar with "Group Selected" and "Dismiss Selected" [REQ: multi-select-and-bulk-actions]
- [ ] 5.7 Create group creation dialog: name + reason input [REQ: multi-select-and-bulk-actions]
- [ ] 5.8 Create `web/src/components/issues/GroupList.tsx` + `GroupRow.tsx`: active groups section [REQ: group-list]
- [ ] 5.9 Add environment column for cross-project view [REQ: issue-row-display]

## 6. Issue Detail Panel

- [ ] 6.1 Create `web/src/components/issues/IssueDetail.tsx`: slide-out panel container (50-60% width) [REQ: slide-out-panel]
- [ ] 6.2 Implement panel open/close: click row to open, Escape/click-outside to close [REQ: slide-out-panel]
- [ ] 6.3 Create issue header: ID, severity, state, summary, environment, source, group, occurrence count [REQ: issue-header]
- [ ] 6.4 Create tab navigation: Timeline (default), Diagnosis, Error, Related [REQ: slide-out-panel]
- [ ] 6.5 Create `web/src/components/issues/IssueDiagnosis.tsx`: root cause, impact, confidence, fix scope, suggested fix, affected files, tags [REQ: diagnosis-tab]
- [ ] 6.6 Handle "no diagnosis" state with placeholder message [REQ: diagnosis-tab]
- [ ] 6.7 Create `web/src/components/issues/IssueError.tsx`: monospace error output + occurrence info [REQ: error-tab]
- [ ] 6.8 Create `web/src/components/issues/IssueRelated.tsx`: group member list + actions (fix together, remove from group) [REQ: related-tab]
- [ ] 6.9 Handle ungrouped issue with diagnosis group suggestion [REQ: related-tab]

## 7. Unified Timeline

- [ ] 7.1 Create `web/src/components/issues/IssueTimeline.tsx`: container with scroll, auto-scroll logic [REQ: auto-scroll]
- [ ] 7.2 Create `web/src/components/issues/TimelineEntry.tsx`: conditional rendering for system/user/agent types [REQ: system-event-styling]
- [ ] 7.3 Implement system event styling: centered, gray, small font, icon + action text [REQ: system-event-styling]
- [ ] 7.4 Implement user message styling: right-aligned, blue bubble, timestamp [REQ: chat-message-styling]
- [ ] 7.5 Implement agent message styling: left-aligned, gray bubble, robot icon, timestamp [REQ: chat-message-styling]
- [ ] 7.6 Implement `buildTimeline()`: merge audit entries + chat messages, sort by timestamp [REQ: timeline-construction]
- [ ] 7.7 Integrate ChatInput at bottom of timeline, wire to sendIssueMessage API [REQ: chat-input]
- [ ] 7.8 Implement auto-scroll pause on manual scroll-up, resume on scroll-to-bottom [REQ: auto-scroll]
- [ ] 7.9 Create audit icon mapping: AUDIT_ICONS record for all action types [REQ: system-event-styling]

## 8. Issue Actions

- [ ] 8.1 Create `web/src/components/issues/IssueActions.tsx`: state-aware button bar [REQ: state-aware-button-rendering]
- [ ] 8.2 Implement STATE_BUTTON_MAP: hardcoded button list per IssueState [REQ: state-aware-button-rendering]
- [ ] 8.3 Wire each button to corresponding API endpoint with optimistic update [REQ: action-api-calls]
- [ ] 8.4 Implement error toast on API failure (HTTP 409, etc.) [REQ: action-api-calls]
- [ ] 8.5 Create confirmation dialog component for Dismiss and Cancel actions [REQ: confirmation-dialogs]
- [ ] 8.6 Create mute pattern dialog: auto-generated pattern, editable reason, optional expiry [REQ: mute-pattern-dialog]
- [ ] 8.7 Create extend timeout dialog: minutes input [REQ: extend-timeout-dialog]
- [ ] 8.8 Integrate TimeoutCountdown into action bar for AWAITING_APPROVAL issues [REQ: timeout-countdown-display]

## 9. Mute Management Page

- [ ] 9.1 Create `web/src/pages/ManagerMutes.tsx` at route `/manager/:project/mutes` [REQ: mute-pattern-dialog]
- [ ] 9.2 Create `web/src/components/issues/MuteManager.tsx`: list patterns with match count, last matched, expiry [REQ: mute-pattern-dialog]
- [ ] 9.3 Add "Add Mute" button with creation dialog [REQ: mute-pattern-dialog]
- [ ] 9.4 Add Edit and Delete buttons per pattern [REQ: mute-pattern-dialog]

## 10. Routing & Navigation

- [ ] 10.1 Add routes to app router: /manager, /manager/issues, /manager/:project/issues, /manager/:project/issues/:id, /manager/:project/mutes [REQ: project-cards]
- [ ] 10.2 Add "Manager" link to existing sidebar/navigation [REQ: project-cards]
- [ ] 10.3 Add issue count badge to sidebar navigation per project [REQ: urgency-based-sections]

## 11. Styling & Constants

- [ ] 11.1 Define STATE_STYLES constant: color + icon for all 13 states [REQ: state-aware-button-rendering]
- [ ] 11.2 Define SEVERITY_STYLES constant: color + label for unknown/low/medium/high/critical [REQ: issue-row-display]
- [ ] 11.3 Define MODE_STYLES constant: color + label for e2e/production/development [REQ: project-cards]
- [ ] 11.4 Define AUDIT_ICONS constant: icon mapping for all audit action types [REQ: system-event-styling]

## 12. Graceful Degradation

- [ ] 12.1 Handle manager API unreachable in all hooks: show fallback UI [REQ: service-health-display]
- [ ] 12.2 Handle issues not enabled for project: show "not enabled" message [REQ: service-health-display]
- [ ] 12.3 Handle empty states: no projects, no issues, no groups, no mutes [REQ: project-cards]

## 13. API Proxy

- [ ] 13.1 Add proxy rule in set-web server: /api/manager/* → set-manager:3112 [REQ: project-cards]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN overview loads with running project THEN green indicators show with uptime [REQ: project-cards, scenario: active-project-display]
- [ ] AC-2: WHEN user clicks Start sentinel THEN API is called and indicator updates [REQ: process-control-buttons, scenario: start-sentinel-from-ui]
- [ ] AC-3: WHEN manager is unreachable THEN red banner with CLI instructions shows [REQ: service-health-display, scenario: manager-unreachable]
- [ ] AC-4: WHEN issue list loads THEN issues grouped in correct urgency sections [REQ: urgency-based-sections, scenario: issues-grouped-by-urgency]
- [ ] AC-5: WHEN issue is AWAITING_APPROVAL THEN live countdown timer shows [REQ: issue-row-display, scenario: awaiting-issue-with-countdown]
- [ ] AC-6: WHEN user selects 3 issues and groups them THEN dialog asks for name, group created [REQ: multi-select-and-bulk-actions, scenario: group-selected-issues]
- [ ] AC-7: WHEN user clicks issue row THEN slide-out panel opens with Timeline tab [REQ: slide-out-panel, scenario: open-issue-detail]
- [ ] AC-8: WHEN user presses Escape THEN panel closes [REQ: slide-out-panel, scenario: close-panel]
- [ ] AC-9: WHEN diagnosis exists THEN all fields displayed with formatting [REQ: diagnosis-tab, scenario: diagnosis-available]
- [ ] AC-10: WHEN no diagnosis THEN placeholder message shown [REQ: diagnosis-tab, scenario: no-diagnosis]
- [ ] AC-11: WHEN timeline has audit + chat entries THEN they appear interleaved by timestamp [REQ: timeline-construction, scenario: interleaved-events]
- [ ] AC-12: WHEN system event rendered THEN it shows centered, gray, with icon [REQ: system-event-styling, scenario: system-event-display]
- [ ] AC-13: WHEN user sends chat message THEN it appears immediately (optimistic) [REQ: chat-input, scenario: send-chat-message]
- [ ] AC-14: WHEN user scrolls up and new entry arrives THEN no auto-scroll [REQ: auto-scroll, scenario: user-scrolled-up]
- [ ] AC-15: WHEN viewing DIAGNOSED issue THEN buttons: Fix Now, Investigate More, Dismiss, Mute, Skip [REQ: state-aware-button-rendering, scenario: diagnosed-state-buttons]
- [ ] AC-16: WHEN user clicks Fix Now THEN API called and state updates [REQ: action-api-calls, scenario: fix-now-clicked]
- [ ] AC-17: WHEN action API returns 409 THEN error toast appears [REQ: action-api-calls, scenario: api-error]
- [ ] AC-18: WHEN user clicks Dismiss THEN confirmation dialog shown first [REQ: confirmation-dialogs, scenario: dismiss-confirmation]
- [ ] AC-19: WHEN user clicks Mute THEN dialog shows with auto-generated pattern [REQ: mute-pattern-dialog, scenario: mute-dialog]
- [ ] AC-20: WHEN countdown reaches 0 THEN issue re-fetched (now FIXING) [REQ: timeout-countdown-display, scenario: countdown-reaches-zero]
