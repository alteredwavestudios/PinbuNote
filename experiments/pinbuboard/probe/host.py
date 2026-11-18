"""Open two synthetic nodes, verify a WebChannel round trip and exit."""
from pathlib import Path
import secrets
import sys
from time import monotonic

from PySide6.QtCore import QDir, QObject, QResource, QTimer, QUrl, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineProfile, QWebEngineSettings,
    QWebEngineUrlRequestInterceptor, qWebEngineChromiumVersion,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication
import shiboken6

ENTRY = QUrl("qrc:/pinbuboard/index.html")


class LocalAssets(QWebEngineUrlRequestInterceptor):
    def __init__(self, profile):
        super().__init__(profile)
        assets = QDir(":/pinbuboard/assets").entryList(QDir.Filter.Files)
        self.allowed = {ENTRY.path(), "/qtwebchannel/qwebchannel.js"}
        self.allowed.update("/pinbuboard/assets/" + name for name in assets)

    def interceptRequest(self, info):
        url = info.requestUrl()
        permitted = (
            info.requestMethod() == b"GET" and url.scheme() == "qrc"
            and not url.authority() and not url.hasQuery()
            and url.path() in self.allowed
        )
        info.block(not permitted)


class ProbePage(QWebEnginePage):
    def acceptNavigationRequest(self, url, kind, is_main_frame):
        return is_main_frame and url == ENTRY

    def createWindow(self, kind):
        return None


class Probe(QObject):
    def __init__(self, channel, finish):
        super().__init__(channel)
        self.label = secrets.token_hex(8)
        self.finish = finish

    @Slot(result=str)
    def fixture(self):
        return self.label

    @Slot(str)
    def rendered(self, label):
        self.finish(label == self.label)


def main():
    app = QApplication([sys.argv[0]])
    bundle = Path(__file__).with_name("probe.rcc")
    if not QResource.registerResource(str(bundle)):
        raise SystemExit("Build the local probe.rcc resource first.")

    started = monotonic()
    profile = QWebEngineProfile()  # Unnamed profiles are off the record.
    guard = LocalAssets(profile)
    profile.setUrlRequestInterceptor(guard)
    profile.downloadRequested.connect(lambda request: request.cancel())
    view = QWebEngineView()
    page = ProbePage(profile, view)
    view.setPage(page)
    for attribute in (
        "LocalContentCanAccessFileUrls", "LocalContentCanAccessRemoteUrls",
        "LocalStorageEnabled", "JavascriptCanOpenWindows", "PluginsEnabled",
        "PdfViewerEnabled",
    ):
        page.settings().setAttribute(getattr(QWebEngineSettings.WebAttribute, attribute), False)

    def finish(success):
        if success:
            print(f"PASS: graph geometry and channel reply in {monotonic() - started:.2f}s "
                  f"(Chromium {qWebEngineChromiumVersion()})", flush=True)
        else:
            print("FAIL: missing graph geometry or incorrect bridge reply.", file=sys.stderr)
        app.exit(0 if success else 1)

    channel = QWebChannel(page)
    bridge = Probe(channel, finish)
    channel.registerObject("probe", bridge)
    page.setWebChannel(channel)
    timer = QTimer(view)
    timer.setSingleShot(True)
    timer.timeout.connect(lambda: finish(False))
    timer.start(15000)
    view.resize(800, 600)
    view.show()
    page.load(ENTRY)
    status = app.exec()
    page.setWebChannel(None)
    # WebEngine requires the profile to outlive every page that uses it.
    shiboken6.delete(view)
    shiboken6.delete(profile)
    return status


if __name__ == "__main__":
    sys.exit(main())
