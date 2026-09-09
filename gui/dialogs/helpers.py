"""
Always-on-top dialog helpers for macOS compatibility.

The Control Center uses NSStatusWindowLevel (25) via native API.
Qt's WindowStaysOnTopHint only sets NSFloatingWindowLevel (~3-8),
which is BELOW the CC. Dialogs must be raised to level 26 via
native NSWindow API so they appear above the CC and receive input.

Usage:
    from gui.dialogs.helpers import show_warning, show_question, get_text
    show_warning(self, "Error", "Something went wrong")
"""

import logging
import sys
from PySide6.QtWidgets import QMessageBox, QInputDialog, QFileDialog
from PySide6.QtCore import Qt

logger = logging.getLogger("set-control.dialogs")


def _raise_above_cc(widget):
    """Set native NSWindow level to 26 (above CC's 25) on macOS.

    winId() is a pointer to the widget's NSView, NOT an NSWindow number, so it
    must be resolved through the view — the same way main_window._get_ns_window
    does it. Comparing it against NSApp.windows()[i].windowNumber() never
    matches, and the failure is silent: the dialog stays at Qt's floating level
    (~8), below the CC's 25, where an application-modal dialog is invisible and
    blocks every click on the CC.
    """
    if sys.platform != "darwin":
        return False
    try:
        from ctypes import c_void_p
        import objc

        win_id = int(widget.winId())
        if not win_id:
            logger.warning("dialog raise: winId() is 0, cannot resolve NSWindow")
            return False

        ns_view = objc.objc_object(c_void_p=c_void_p(win_id))
        ns_window = ns_view.window() if hasattr(ns_view, "window") else None
        if ns_window is None:
            logger.warning("dialog raise: NSView %#x has no window", win_id)
            return False

        old_level = ns_window.level()
        ns_window.setLevel_(26)
        logger.debug(
            "dialog raise: window %d level %d -> %d",
            ns_window.windowNumber(), old_level, ns_window.level(),
        )
        return True
    except Exception as e:
        logger.warning("dialog raise failed: %s: %s", type(e).__name__, e)
        return False


def _exec_above_cc(widget):
    """Show widget, raise above CC, then exec modally.

    The raise is not cosmetic. These dialogs are application-modal, so one that
    ends up below the CC's window level blocks all input while being invisible —
    the app looks frozen. If the raise fails, say so rather than exec a dialog
    nobody can see.
    """
    widget.setWindowFlags(widget.windowFlags() | Qt.WindowStaysOnTopHint)
    widget.show()
    if not _raise_above_cc(widget):
        logger.warning(
            "dialog %r shown WITHOUT a native level raise — it may sit below the "
            "Control Center and block input while invisible",
            widget.windowTitle(),
        )
    widget.raise_()
    widget.activateWindow()
    return widget.exec()


def show_warning(parent, title, text):
    """QMessageBox.warning() above Control Center."""
    box = QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Ok, parent)
    return _exec_above_cc(box)


def show_information(parent, title, text):
    """QMessageBox.information() above Control Center."""
    box = QMessageBox(QMessageBox.Information, title, text, QMessageBox.Ok, parent)
    return _exec_above_cc(box)


def show_question(parent, title, text, buttons=None, default=None):
    """QMessageBox.question() above Control Center."""
    if buttons is None:
        buttons = QMessageBox.Yes | QMessageBox.No
    box = QMessageBox(QMessageBox.Question, title, text, buttons, parent)
    if default is not None:
        box.setDefaultButton(default)
    return _exec_above_cc(box)


def get_text(parent, title, label, **kwargs):
    """QInputDialog.getText() above Control Center.

    Returns (text, ok) tuple like the original.
    """
    dlg = QInputDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setLabelText(label)
    if kwargs.get('text'):
        dlg.setTextValue(kwargs['text'])
    if kwargs.get('echo'):
        dlg.setTextEchoMode(kwargs['echo'])
    ok = _exec_above_cc(dlg) == QInputDialog.Accepted
    return dlg.textValue(), ok


def get_item(parent, title, label, items, current=0, editable=False):
    """QInputDialog.getItem() above Control Center.

    Returns (item, ok) tuple like the original.
    """
    dlg = QInputDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setLabelText(label)
    dlg.setComboBoxItems(items)
    dlg.setComboBoxEditable(editable)
    if 0 <= current < len(items):
        dlg.setTextValue(items[current])
    ok = _exec_above_cc(dlg) == QInputDialog.Accepted
    return dlg.textValue(), ok


def get_existing_directory(parent, caption="", directory="", options=None):
    """QFileDialog.getExistingDirectory() above Control Center."""
    dlg = QFileDialog(parent, caption, directory)
    dlg.setFileMode(QFileDialog.Directory)
    if options is not None:
        dlg.setOptions(options)
    if _exec_above_cc(dlg) == QFileDialog.Accepted:
        dirs = dlg.selectedFiles()
        return dirs[0] if dirs else ""
    return ""


def get_open_filename(parent, caption="", directory="", filter=""):
    """QFileDialog.getOpenFileName() above Control Center.

    Returns (filename, selected_filter) tuple like the original.
    """
    dlg = QFileDialog(parent, caption, directory, filter)
    dlg.setFileMode(QFileDialog.ExistingFile)
    if _exec_above_cc(dlg) == QFileDialog.Accepted:
        files = dlg.selectedFiles()
        return (files[0] if files else "", dlg.selectedNameFilter())
    return ("", "")
