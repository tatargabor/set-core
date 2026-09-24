"""
Test dialog helpers - verify always-on-top wrappers set WindowStaysOnTopHint.
"""

from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QInputDialog, QFileDialog

from gui.dialogs.helpers import (
    show_warning, show_information, show_question,
    get_text, get_item, get_existing_directory, get_open_filename,
)


class TestShowWarning:
    def test_sets_window_stays_on_top(self):
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Ok):
            with patch.object(QMessageBox, 'setWindowFlags') as mock_flags:
                show_warning(None, "Title", "Text")

        assert mock_flags.called
        flags_arg = mock_flags.call_args[0][0]
        assert flags_arg & Qt.WindowStaysOnTopHint

    def test_returns_exec_result(self):
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Ok):
            result = show_warning(None, "Title", "Text")
        assert result == QMessageBox.Ok


class TestShowInformation:
    def test_sets_window_stays_on_top(self):
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Ok):
            with patch.object(QMessageBox, 'setWindowFlags') as mock_flags:
                show_information(None, "Title", "Text")

        assert mock_flags.called
        flags_arg = mock_flags.call_args[0][0]
        assert flags_arg & Qt.WindowStaysOnTopHint


class TestShowQuestion:
    def test_sets_window_stays_on_top(self):
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.Yes):
            with patch.object(QMessageBox, 'setWindowFlags') as mock_flags:
                show_question(None, "Title", "Question?")

        assert mock_flags.called
        flags_arg = mock_flags.call_args[0][0]
        assert flags_arg & Qt.WindowStaysOnTopHint

    def test_passes_buttons_and_default(self):
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.No):
            with patch.object(QMessageBox, 'setDefaultButton') as mock_default:
                show_question(
                    None, "Title", "Q?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
        assert mock_default.called


class TestGetText:
    def test_returns_tuple(self):
        with patch.object(QInputDialog, 'exec', return_value=QInputDialog.Accepted):
            with patch.object(QInputDialog, 'textValue', return_value="hello"):
                text, ok = get_text(None, "Title", "Label")
        assert ok is True
        assert text == "hello"

    def test_sets_window_stays_on_top(self):
        with patch.object(QInputDialog, 'exec', return_value=QInputDialog.Accepted):
            with patch.object(QInputDialog, 'textValue', return_value=""):
                with patch.object(QInputDialog, 'setWindowFlags') as mock_flags:
                    get_text(None, "Title", "Label")

        assert mock_flags.called
        flags_arg = mock_flags.call_args[0][0]
        assert flags_arg & Qt.WindowStaysOnTopHint


class TestGetItem:
    def test_returns_tuple(self):
        with patch.object(QInputDialog, 'exec', return_value=QInputDialog.Rejected):
            with patch.object(QInputDialog, 'textValue', return_value=""):
                item, ok = get_item(None, "Title", "Label", ["a", "b"])
        assert ok is False

    def test_sets_window_stays_on_top(self):
        with patch.object(QInputDialog, 'exec', return_value=QInputDialog.Accepted):
            with patch.object(QInputDialog, 'textValue', return_value="item1"):
                with patch.object(QInputDialog, 'setWindowFlags') as mock_flags:
                    get_item(None, "Title", "Label", ["item1", "item2"])

        assert mock_flags.called
        flags_arg = mock_flags.call_args[0][0]
        assert flags_arg & Qt.WindowStaysOnTopHint


class TestGetExistingDirectory:
    def test_returns_empty_on_reject(self):
        with patch.object(QFileDialog, 'exec', return_value=QFileDialog.Rejected):
            result = get_existing_directory(None, "Select")
        assert result == ""


class TestGetOpenFilename:
    def test_returns_empty_on_reject(self):
        with patch.object(QFileDialog, 'exec', return_value=QFileDialog.Rejected):
            filename, filter_ = get_open_filename(None, "Open")
        assert filename == ""
        assert filter_ == ""


@pytest.fixture(scope="module")
def app():
    """A QApplication that does not depend on pytest-qt being installed.

    The rest of this file's tests reach one only because some other module in a
    full-suite run created it first, which is why they abort when this file runs
    alone — measured at HEAD, unrelated to these tests.
    """
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class TestRaiseAboveCC:
    """The native level raise — asserted on the RESULT, not on the mechanism.

    Every test above asserts that WindowStaysOnTopHint was set. That flag is
    exactly what produces NSFloatingWindowLevel (~8), which is BELOW the Control
    Center's NSStatusWindowLevel (25) — so those tests pass on precisely the
    broken state this class exists to catch: an application-modal dialog living
    under the CC, invisible, blocking every click, and the app reading as frozen.
    """

    def test_winid_is_not_a_window_number(self, app):
        """The wrong pattern, held in a test so it cannot come back.

        winId() is a pointer to the widget's NSView. The original lookup compared
        it against NSApp.windows()[i].windowNumber() — a small monotonic counter —
        so the loop never matched and the raise silently did nothing.
        """
        import sys
        if sys.platform != "darwin":
            pytest.skip("macOS window levels only")
        from AppKit import NSApp

        box = QMessageBox(QMessageBox.Information, "t", "t")
        box.show()
        try:
            win_id = int(box.winId())
            numbers = [w.windowNumber() for w in NSApp.windows()]
            assert win_id not in numbers, (
                "winId() matched a windowNumber — the old lookup's premise. If this "
                "ever holds, re-check _raise_above_cc's resolution."
            )
        finally:
            box.hide()
            box.deleteLater()
            app.processEvents()

    def test_raise_actually_reaches_level_26(self, app):
        """The result: the dialog's NSWindow ends up above the CC's level 25."""
        import sys
        if sys.platform != "darwin":
            pytest.skip("macOS window levels only")
        from ctypes import c_void_p
        import objc

        from gui.dialogs.helpers import _raise_above_cc

        box = QMessageBox(QMessageBox.Information, "t", "t")
        box.setWindowFlags(box.windowFlags() | Qt.WindowStaysOnTopHint)
        box.show()
        try:
            ns_window = objc.objc_object(c_void_p=c_void_p(int(box.winId()))).window()
            before = ns_window.level()
            assert before < 25, (
                f"precondition: WindowStaysOnTopHint alone must leave the dialog "
                f"below the CC, got level {before}"
            )

            assert _raise_above_cc(box) is True
            assert ns_window.level() == 26
        finally:
            box.hide()
            box.deleteLater()
            app.processEvents()
