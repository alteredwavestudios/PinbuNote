"""The experiment launcher owns one generated notebook and one lazy board view."""
from pathlib import Path

import shiboken6

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget, QToolButton

from ..notebook import Notebook
from ..window import MainWindow


class DemoWindow(MainWindow):
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.demo_path = root / "Study desk.pinbunote"
        if not self.demo_path.exists():
            created = Notebook.create(root, "Study desk", extension=".pinbunote")
            created.close()
        self.board_view = None
        super().__init__(initial_path=self.demo_path, demo_root=root)
        self.setWindowTitle("Pinbu Note · Experimental v1.1")
        self.board_button = QPushButton("PinbuBoard", self.header)
        self.board_button.setToolTip("Open PinbuBoard · Experimental v1.1")
        self.board_button.clicked.connect(self.toggle_board)
        self.header.layout().insertWidget(1, self.board_button)
        # WebEngine creates private QObjects on Chromium callbacks. Global Python
        # filters can try to wrap these objects before their construction finishes.
        app = QApplication.instance()
        app.removeEventFilter(self)
        app.removeEventFilter(self.button_motion)
        self._watch_study(self.header)
        self._watch_study(self.tabs)

    def _watch_study(self, root):
        for widget in [root, *root.findChildren(QWidget)]:
            widget.installEventFilter(self)
            if isinstance(widget, (QPushButton, QToolButton)):
                widget.installEventFilter(self.button_motion)

    def toggle_board(self):
        if self.board_view is not None and not self.board_view.isHidden():
            self.board_view.hide()
            self.tabs.show()
            self.quick_actions.show()
            self.menuBar().setEnabled(True)
            self.statusBar().show()
            self.board_button.setText("PinbuBoard")
            focus = self.study_focus
            if focus is not None and shiboken6.isValid(focus) and focus.isVisible():
                focus.setFocus()
            else:
                self.tabs.setFocus()
            return
        if not self.notebook or self.notebook.display_path != self.demo_path:
            QMessageBox.information(self, "PinbuBoard", "Open the generated Study desk notebook to use this demo.")
            return
        if self.board_view is not None and self.board_view.bridge.library.notebook != self.notebook.identifier:
            self.board_view.deleteLater()
            self.board_view = None
        if self.board_view is None:
            try:
                from .web import BoardView
                self.board_view = BoardView(self.demo_root, self.notebook.identifier, self.root)
                self.root_layout.addWidget(self.board_view, 1)
            except (ImportError, OSError, ValueError, RuntimeError) as exc:
                QMessageBox.warning(self, "PinbuBoard could not open", str(exc))
                return
        self.study_focus = self.tabs.focusWidget()
        self.tabs.hide()
        self.quick_actions.hide()
        self.menuBar().setEnabled(False)
        self.statusBar().hide()
        self.board_button.setText("Study workspace")
        self.board_view.show()
        self.board_view.setFocus()

    def closeEvent(self, event):
        super().closeEvent(event)
        if event.isAccepted() and self.board_view is not None:
            view = self.board_view
            self.board_view = None
            profile = view.board_profile
            view.page().setWebChannel(None)
            shiboken6.delete(view)
            shiboken6.delete(profile)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.ChildPolished and hasattr(self, 'board_button'):
            if watched is self.header or self.header.isAncestorOf(watched) or (
                    watched is self.tabs or self.tabs.isAncestorOf(watched)):
                child = event.child()
                if isinstance(child, QWidget):
                    self._watch_study(child)
        return super().eventFilter(watched, event)
