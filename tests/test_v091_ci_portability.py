"""Regression checks for v0.9.1 cross-platform CI safeguards."""
from PIL import Image


def test_background_preview_jpeg_plugin_registered_before_workers():
    # Importing the module is the main-thread startup path, not a Qt worker.
    from yomunote import importers
    assert importers.Image is Image
    assert 'JPEG' in Image.SAVE


def test_sqlite_ci_fixtures_explicitly_close_connections():
    # sqlite3.Connection as a context manager commits/rolls back, but DOES NOT
    # close the underlying handle. Windows cannot replace open SQLite files.
    from pathlib import Path
    tests = Path(__file__).parent
    for name in ('test_safesave_session.py', 'test_safesave_overwrite_versions.py'):
        body = (tests / name).read_text(encoding='utf-8')
        assert 'with sqlite3.connect(' not in body
        assert 'with closing(sqlite3.connect(' in body
