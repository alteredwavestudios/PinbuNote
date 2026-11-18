"""Offline Qt host. The web page can only address its bound demo library."""
import json
import sys
from pathlib import Path

from PySide6.QtCore import QDir, QObject, QResource, Qt, QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from .model import BoardLibrary

ENTRY = QUrl("qrc:/pinbu-playable/index.html")
SOURCE_ROOT = Path(__file__).resolve().parents[2]


def _resource_candidates() -> list[Path]:
    """Find the resource beside source files and in a frozen app bundle."""
    candidates = [
        SOURCE_ROOT / "frontend/pinbuboard/board.rcc",
        Path(getattr(sys, "_MEIPASS", "")) / "frontend/pinbuboard/board.rcc",
        Path(getattr(sys, "_MEIPASS", "")) / "board.rcc",
        Path(sys.executable).resolve().parent / "frontend/pinbuboard/board.rcc",
        Path(sys.executable).resolve().parent / "board.rcc",
    ]
    return list(dict.fromkeys(path for path in candidates if str(path) and path.is_file()))


def _load_resources() -> bool:
    if QDir(":/pinbu-playable").exists():
        return True
    for path in _resource_candidates():
        if QResource.registerResource(str(path)) and QDir(":/pinbu-playable").exists():
            return True
    # The generated Python module uses Qt's in-process resource registration
    # API, which avoids binary RCC version differences across Qt 6 patch levels.
    for root in (SOURCE_ROOT / "frontend/pinbuboard", Path(getattr(sys, "_MEIPASS", ""))):
        module = root / "board_resources.py"
        if module.is_file():
            import importlib.util
            spec = importlib.util.spec_from_file_location("pinbuboard_board_resources", module)
            if spec and spec.loader:
                loaded = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(loaded)
                if QDir(":/pinbu-playable").exists():
                    return True
    return False


class Assets(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent):
        super().__init__(parent)
        self.paths = {ENTRY.path(), "/qtwebchannel/qwebchannel.js"}
        for name in QDir(":/pinbu-playable/assets").entryList(QDir.Filter.Files):
            self.paths.add("/pinbu-playable/assets/" + name)

    def interceptRequest(self, request):
        url = request.requestUrl()
        valid = (request.requestMethod() == b"GET" and url.scheme() == "qrc"
                 and not url.authority() and not url.hasQuery() and url.path() in self.paths)
        request.block(not valid)


class Page(QWebEnginePage):
    def acceptNavigationRequest(self, url, kind, is_main_frame):
        return is_main_frame and url == ENTRY

    def createWindow(self, kind):
        return None

    def chooseFiles(self, mode, previous, accepted_types):
        return []


class Bridge(QObject):
    def __init__(self, library, parent):
        super().__init__(parent)
        self.library = library

    @Slot(str, result=str)
    def request(self, raw):
        try:
            if len(raw.encode()) > 512 * 1024:
                raise ValueError("Command is too large.")
            data = self.library.handle(json.loads(raw))
            return json.dumps({"ok": True, "data": data})
        except OSError:
            return json.dumps({"ok": False, "error": "Could not read or save the demo file. Check folder access."})
        except (ValueError, KeyError, TypeError, RecursionError) as exc:
            message = str(exc) if type(exc) is ValueError else "Invalid board data."
            return json.dumps({"ok": False, "error": message})


class BoardView(QWebEngineView):
    def __init__(self, root, notebook_id, parent):
        if not _load_resources():
            raise ValueError("The bundled board.rcc could not be loaded.")
        library = BoardLibrary(root / "boards" / (notebook_id + ".json"), notebook_id)
        # Place the profile after the view in the workspace child list. On close
        # the demo releases the page and view before deleting the profile.
        super().__init__(parent)
        profile = QWebEngineProfile(parent)
        self.board_profile = profile
        self.policy = Assets(profile)
        profile.setUrlRequestInterceptor(self.policy)
        profile.downloadRequested.connect(lambda request: request.cancel())
        page = Page(profile, self)
        self.board_page = page
        self.setPage(page)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setAcceptDrops(False)
        for name in ("LocalContentCanAccessFileUrls", "LocalContentCanAccessRemoteUrls",
                     "LocalStorageEnabled", "JavascriptCanOpenWindows", "PluginsEnabled",
                     "PdfViewerEnabled", "JavascriptCanAccessClipboard", "NavigateOnDropEnabled"):
            page.settings().setAttribute(getattr(QWebEngineSettings.WebAttribute, name), False)
        self.channel = QWebChannel(page)
        self.bridge = Bridge(library, self.channel)
        self.channel.registerObject("board", self.bridge)
        page.setWebChannel(self.channel)
        self.load(ENTRY)
