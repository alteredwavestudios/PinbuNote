"""Exercise the shipped board bundle in the real application with synthetic data."""
import json
import time
import sys

import pytest

pytest.importorskip("PySide6.QtWebEngineWidgets")
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from yomunote.pinbuboard.window import DemoWindow

PRIMARY = Qt.KeyboardModifier.MetaModifier if sys.platform == "darwin" else Qt.KeyboardModifier.ControlModifier


def until(check, description):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if check():
            return
        QTest.qWait(20)
    pytest.fail("Timed out waiting for " + description)


class Canvas:
    def __init__(self, view):
        self.view = view

    def js(self, code):
        result = []
        self.view.page().runJavaScript(code, 0, result.append)
        until(lambda: result, "browser reply")
        return result[0]

    def point(self, selector):
        coords = self.js("JSON.stringify((()=>{const r=document.querySelector(" +
                         json.dumps(selector) + ").getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2]})())")
        return QPoint(*(round(x) for x in json.loads(coords)))

    def button(self, text):
        key = json.dumps(text)
        assert self.js(f"Array.from(document.querySelectorAll('button')).some(b=>{{if(b.textContent.trim()==={key} && !b.disabled){{b.click();return true}}return false}})"), text

    def wait_nodes(self, n):
        until(lambda: self.js("document.querySelectorAll('.react-flow__node').length") == n, f"{n} rendered patches")

    def drag(self, start, end, during=None):
        window = self.view.window()
        target = window.windowHandle()
        start = window.mapFromGlobal(self.view.mapToGlobal(start))
        end = window.mapFromGlobal(self.view.mapToGlobal(end))
        QTest.mousePress(target, Qt.MouseButton.LeftButton, pos=start)
        for step in range(1, 7):
            QTest.mouseMove(target, start + (end-start)*step/6, delay=5)
            QTest.qWait(40)
        if during:
            during()
        QTest.mouseRelease(target, Qt.MouseButton.LeftButton, pos=end)


def test_playable_round_trip_and_workspace_switch(tmp_path, monkeypatch, close_test_window):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "local"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    win = DemoWindow(tmp_path / "demo")
    win.resize(1300, 820)
    win.show()
    QTest.qWait(100)
    notebook = win.notebook
    original = notebook.display_path.read_bytes()
    study = win.active()
    try:
        assert win.board_view is None and win.tabs.isVisible()
        win.board_button.click()
        canvas = Canvas(win.board_view)
        canvas.wait_nodes(5)
        assert not win.tabs.isVisible()
        lib = win.board_view.bridge.library

        def card(key):
            return next(n for n in lib.boards[lib.active]["nodes"] if n["id"] == key)

        # A real pointer gesture, with exactly one committed message on release.
        until(lambda: canvas.js("document.querySelectorAll('.react-flow__edge-path').length") == 4,
              "initial graph geometry")
        source = canvas.point('[data-id="claim"] h2')
        before = lib.revision
        canvas.drag(source, source + QPoint(35, 28), lambda: require_equal(lib.revision, before))
        until(lambda: lib.revision == before + 1, "one committed drag")
        assert card("claim")["x"] != 340
        start = canvas.point('[data-id="claim"] .react-flow__resize-control.bottom.right.handle')
        canvas.drag(start, start + QPoint(38, 30))
        until(lambda: card("claim")["w"] > 244, "resized patch")

        canvas.button("↶ Undo")
        until(lambda: card("claim")["w"] == 244, "undo resize")
        canvas.button("↷ Redo")
        until(lambda: card("claim")["w"] > 244, "redo resize")

        # Draw an additional directional edge using React Flow ports.
        canvas.drag(canvas.point('[data-id="claim"] .source'), canvas.point('[data-id="outline"] .target'))
        until(lambda: len(lib.boards["first"]["edges"]) == 5, "directed connection")
        assert any(e["source"] == "claim" and e["target"] == "outline" for e in lib.boards["first"]["edges"])

        canvas.button("¶Text note")
        canvas.wait_nodes(6)
        until(lambda: canvas.js("document.querySelectorAll('.react-flow__node.selected').length") == 1, "new selection")
        canvas.button("Edit")
        until(lambda: canvas.js("!!document.querySelector('dialog[open] input')"), "open patch editor")
        QTest.keyClick(win.board_view.focusProxy(), Qt.Key.Key_A, PRIMARY)
        QTest.keyClicks(win.board_view.focusProxy(), "Study finding")
        until(lambda: canvas.js("document.querySelector('dialog input').value") == "Study finding", "title input")
        canvas.js("document.querySelector('dialog textarea').focus()")
        QTest.keyClicks(win.board_view.focusProxy(), "My example")
        until(lambda: canvas.js("document.querySelector('dialog textarea').value") == "My example", "content input")
        canvas.button("Apply")
        until(lambda: any(n["title"] == "Study finding" for n in lib.boards["first"]["nodes"]), "edited title")

        # These keystrokes pass through Qt's window-level shortcut routing.
        target = win.board_view.focusProxy()
        QTest.keyClick(target, Qt.Key.Key_D, PRIMARY)
        canvas.wait_nodes(7)
        QTest.keyClick(target, Qt.Key.Key_Delete)
        canvas.wait_nodes(6)
        QTest.keyClick(target, Qt.Key.Key_Z, PRIMARY)
        canvas.wait_nodes(7)
        QTest.keyClick(target, Qt.Key.Key_A, PRIMARY)
        until(lambda: canvas.js("document.querySelectorAll('.react-flow__node.selected').length") == 7, "multiple selection")
        canvas.button("Align top")
        until(lambda: len({n["y"] for n in lib.boards["first"]["nodes"]}) == 1, "top alignment")
        canvas.button("↶ Undo")
        until(lambda: len({n["y"] for n in lib.boards["first"]["nodes"]}) > 1, "undo alignment")
        canvas.button("Snap")
        canvas.button("Overview")
        until(lambda: canvas.js("!!document.querySelector('.react-flow__minimap')"), "overview")
        initial_zoom = canvas.js("document.querySelector('output').textContent")
        canvas.button("＋")
        until(lambda: canvas.js("document.querySelector('output').textContent") != initial_zoom, "zoom")
        canvas.button("Fit")
        QTest.qWait(220)
        viewport = canvas.js("document.querySelector('.react-flow__viewport').style.transform")
        win.board_button.click()
        assert win.tabs.isVisible() and win.active() is study
        win.board_button.click()
        canvas.wait_nodes(7)
        assert canvas.js("document.querySelector('.react-flow__viewport').style.transform") == viewport

        canvas.button("＋ Board")
        until(lambda: canvas.js("!!document.querySelector('dialog[open] input')"), "new board name")
        QTest.keyClicks(target, "Essay plan")
        until(lambda: canvas.js("document.querySelector('dialog input').value") == "Essay plan", "board name")
        canvas.button("Create board")
        canvas.wait_nodes(0)
        new_id = lib.active
        assert lib.boards[new_id]["name"] == "Essay plan"
        canvas.button("Save")
        until(lambda: canvas.js("document.querySelector('.save-state').textContent")=="Saved to demo file", "save")
        canvas.button("Reload")
        until(lambda: canvas.js("document.querySelector('.save-state').textContent")=="Reloaded from file", "reload")
        assert len(lib.boards["first"]["nodes"]) == 7
        canvas.js("const select=document.querySelector('select'); select.value='first'; select.dispatchEvent(new Event('change',{bubbles:true}));")
        canvas.wait_nodes(7)
        assert lib.active == "first"
        QTest.keyClick(target, Qt.Key.Key_S, PRIMARY)
        until(lambda: canvas.js("document.querySelector('.save-state').textContent")=="Saved to demo file", "board save shortcut")
        assert notebook.display_path.read_bytes() == original
    finally:
        close_test_window(win)
        notebook.close()
        win.deleteLater()
        app.processEvents()


def require_equal(actual, expected):
    assert actual == expected
