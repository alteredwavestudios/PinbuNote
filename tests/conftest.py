"""Protect real study notebooks and preferences during MainWindow GUI tests.

Every test that imports MainWindow gets a disposable home and an INI-backed
QSettings store, including on Windows (where QSettings normally uses registry).
This also makes `python -m pytest` safe without the optional audit runner.
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest


@pytest.fixture(autouse=True)
def isolate_mainwindow_user_state(request):
    """Avoid opening or modifying a user's real notebook in GUI smoke tests."""
    namespace = vars(request.module)
    mainwindow_test = any(
        (getattr(value, '__name__', None) == 'MainWindow'
         and getattr(value, '__module__', None) == 'yomunote.window')
        or getattr(value, '__name__', None) == 'yomunote.window'
        for value in namespace.values()
    )
    if not mainwindow_test:
        return

    # Import only for tests that already imported the Qt MainWindow. Pure
    # Python tests must remain runnable without PySide6 installed.
    from PySide6.QtCore import QSettings
    from yomunote import window as window_module

    tmp_path = request.getfixturevalue('tmp_path')
    monkeypatch = request.getfixturevalue('monkeypatch')
    home = tmp_path / 'test-home'
    home.mkdir(exist_ok=True)
    prefs = tmp_path / 'test-preferences'
    prefs.mkdir(exist_ok=True)

    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('USERPROFILE', str(home))
    monkeypatch.setenv('APPDATA', str(tmp_path / 'appdata'))
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'localappdata'))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(prefs))
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))

    def private_qsettings(*args, **kwargs):
        if len(args) == 2 and not kwargs and all(isinstance(x, str) for x in args):
            name = '--'.join(re.sub(r'[^A-Za-z0-9_-]', '_', x) for x in args)
            return QSettings(str(prefs / f'{name}.ini'), QSettings.Format.IniFormat)
        return QSettings(*args, **kwargs)

    monkeypatch.setattr(window_module, 'QSettings', private_qsettings)


@pytest.fixture
def close_test_window():
    """Close a disposable test notebook via the REAL SafeSave close dialog.

    Production never auto-dismisses this dialog. The CI test schedules a
    user-like click on Close Without Saving inside Qt's nested event loop;
    silently disabling the dialog would weaken the tested safety contract.
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    def close(window):
        import sys

        if sys.platform == 'darwin':
            # Qt's native macOS message-box event loop can starve the Qt timer
            # used by the original GUI cleanup. Keep the REAL production
            # closeEvent and real QMessageBox/buttons, but make that one box
            # non-native in this offscreen macOS TEST only.
            from yomunote import window as window_module

            class MacCIMessageBox(QMessageBox):
                @staticmethod
                def critical(parent, title, message, *args, **kwargs):
                    # Diagnostic ONLY: Qt's blocking critical() dialog masks
                    # the exception that caused MainWindow.closeEvent to fail.
                    # Raise into pytest so the true error appears in logs.
                    raise RuntimeError(
                        'MAC_CI_SHUTDOWN_EXCEPTION: ' + str(title) + '\n'
                        + str(message))

                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.setOption(QMessageBox.Option.DontUseNativeDialog, True)

                def exec(self):
                    if self.windowTitle() != 'Unsaved changes':
                        raise AssertionError(
                            f'Unexpected modal dialog during Mac CI shutdown: '
                            f'{self.windowTitle()!r}: {self.text()!r}')
                    buttons = [button for button in self.buttons()
                               if button.text().replace('&', '').strip()
                               == 'Close Without Saving']
                    if len(buttons) != 1:
                        raise AssertionError(
                            'Mac CI shutdown requires exactly one '
                            'Close Without Saving button.')
                    # Qt macOS offscreen cannot reliably service timers in
                    # a nested QMessageBox.exec() event loop. Use a real,
                    # non-native Qt dialog opened ASYNCHRONOUSLY, then click
                    # the real button synchronously. QApplication remains
                    # responsive, production closeEvent still checks the
                    # clicked button, and no app safety logic is patched.
                    button = buttons[0]
                    self.open()
                    button.click()
                    if self.clickedButton() is not button:
                        raise AssertionError(
                            'Qt did not record the Close Without Saving click '
                            'during macOS headless test cleanup.')
                    print('macOS CI SafeSave test cleanup: real discard button clicked.',
                          flush=True)
                    return self.result()

            original_messagebox = window_module.QMessageBox
            window_module.QMessageBox = MacCIMessageBox
            try:
                window.close()
            finally:
                window_module.QMessageBox = original_messagebox
        else:
            # PROVEN Windows/Linux path: intentionally unchanged.
            def choose_close_without_saving():
                for widget in QApplication.topLevelWidgets():
                    if not isinstance(widget, QMessageBox) or not widget.isVisible():
                        continue
                    if widget.windowTitle() != 'Unsaved changes':
                        continue
                    for button in widget.buttons():
                        if button.text().replace('&', '') == 'Close Without Saving':
                            button.click()
                            return
            QTimer.singleShot(0, choose_close_without_saving)
            window.close()

        app = QApplication.instance()
        if app is not None:
            app.processEvents()
    return close
