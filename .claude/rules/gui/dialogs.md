---
paths:
  - "gui/**"
---

# macOS Always-On-Top Dialog Rule

The Control Center uses NSStatusWindowLevel (25) to stay above normal apps. Menus and dialogs with `WindowStaysOnTopHint` naturally appear above it — no timer or pause/resume needed.

When creating ANY dialog in the GUI (QDialog, QMessageBox, QInputDialog, QFileDialog):

1. **System dialogs** (QMessageBox, QInputDialog, QFileDialog): Use the wrapper helpers from `gui/dialogs/helpers.py` instead of the Qt static methods. These automatically set `WindowStaysOnTopHint`.
   ```python
   from gui.dialogs.helpers import show_warning, show_question, get_text, get_item, get_existing_directory, get_open_filename
   show_warning(self, "Error", "Something went wrong")
   ```

2. **Custom/ad-hoc QDialogs**: Set `WindowStaysOnTopHint` explicitly:
   ```python
   dialog = QDialog(self)
   dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
   dialog.exec()
   ```

3. **Custom dialog subclasses** (e.g. SettingsDialog): These already have `WindowStaysOnTopHint` in their `__init__`. Just call `.exec()` directly.
