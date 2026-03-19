## 1. Skill Tracking Infrastructure

- [x] 1.1 Create bin/wt-skill-start helper script
- [x] 1.2 Update bin/wt-status to read skill from .set-core/current_skill
- [x] 1.3 Add skill name to wt-status JSON output (replace PID)
- [x] 1.4 Update status display in wt-status human-readable output

## 2. Editor Window Detection

- [x] 2.1 Create gui/control_center/mixins/editor_detection.py
- [x] 2.2 Implement detect_open_editors() using xdotool
- [x] 2.3 Add caching for editor detection results
- [x] 2.4 Add has_open_editor(wt_path) method

## 3. Active Filter UI

- [x] 3.1 Add filter toggle button to toolbar (next to refresh)
- [x] 3.2 Add filter_active state to main window
- [x] 3.3 Style active/inactive button states
- [x] 3.4 Add tooltip for filter button

## 4. Filtered Table Rendering

- [x] 4.1 Modify render_table() to check filter state
- [x] 4.2 Skip rows without open editor when filter active
- [x] 4.3 Hide project headers when no visible worktrees
- [x] 4.4 Invalidate editor cache on filter toggle/refresh

## 5. Update Skills

- [x] 5.1 Add skill registration to openspec-explore skill
- [x] 5.2 Add skill registration to openspec-apply-change skill
- [x] 5.3 Add skill registration to openspec-new-change skill
- [x] 5.4 Add skill registration to openspec-ff-change skill
- [x] 5.5 Add skill registration to openspec-archive-change skill
- [x] 5.6 Add skill registration to wt skill

## 6. Testing

- [x] 6.1 Test skill tracking with fresh skill start
- [x] 6.2 Test stale skill file handling (> 30 min)
- [x] 6.3 Test filter with multiple editors open
- [x] 6.4 Test filter with no editors open
- [x] 6.5 Test status display with skill name
