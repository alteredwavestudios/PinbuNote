"""GUI integration checks. Run with QT_QPA_PLATFORM=offscreen if available."""
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QMessageBox
from yomunote import window as window_module
from yomunote.notebook import Notebook
from yomunote.window import MainWindow


@pytest.fixture
def window(tmp_path, monkeypatch, close_test_window):
    """Use a disposable notebook and INI settings, including on Windows.

    On Windows, QSettings defaults to the registry: HOME and XDG_CONFIG_HOME
    alone do not isolate the user's last-opened study notebook. Never let
    these destructive tab/Undo tests run against a real notebook.
    """
    app = QApplication.instance() or QApplication([])
    # tests/conftest.py already replaces the MainWindow QSettings factory
    # with an INI-backed store, even on Windows. Do NOT wrap it a second time:
    # the fixture is a callable, not the QSettings type (no .Format enum).
    notebook = Notebook.create(tmp_path / 'notebooks', 'GUI Test Notebook')
    notebook_path = notebook.path
    notebook.close()
    settings = window_module.QSettings('Yomu Note', 'Yomu Note')
    settings.setValue('preferencesMigrated', True)
    settings.setValue('openProjects', [str(notebook_path)])
    settings.sync()

    widget = MainWindow()
    # SafeSave stages the original into an independent local working copy.
    # The original path must remain the *display/publish* destination.
    if widget.notebook.display_path != notebook_path:
        widget.show_notebook(Notebook.open_session(notebook_path))
    assert widget.notebook.display_path == notebook_path
    assert widget.notebook.path != notebook_path
    assert widget.notebook.path.is_file()
    assert widget.tabs.count() == 1
    widget.show()
    app.processEvents()
    try:
        yield widget
    finally:
        close_test_window(widget)
        app.processEvents()


def test_tab_rename_trash_hover_delete_undo(window, monkeypatch):
    tabid = window.notebook.add_tab('Chapter B')
    window._resync_notebook_tabs()
    assert window.tabs.count() == 2
    assert not hasattr(window, '_pinned_paths')
    window._show_tab_trash_on_hover(1)
    trash = window.tabs.tabBar().tabButton(1, window.tabs.tabBar().ButtonPosition.RightSide)
    assert trash.isEnabled()
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)
    window.delete_tab_by_id(tabid)
    assert window.tabs.count() == 1
    window.undo_tab_deletion()
    assert window.tabs.count() == 2
    window.redo_tab_deletion()
    assert window.tabs.count() == 1


def test_tab_switch_clears_inactive_page_pixmaps(window):
    tabid = window.notebook.add_tab('Reading')
    window._resync_notebook_tabs()
    window.tabs.setCurrentIndex(0)
    first = window.tabs.currentWidget()
    window.tabs.setCurrentIndex(1)
    assert not first._active
    assert not first._loaded_thumb_rows
    assert not first._thumb_pending
