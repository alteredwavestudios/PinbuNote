"""v0.95 regressions: safe manifest reads and version compatibility.

Small test-size limits deliberately replace the production 32 MiB limit so
these tests run quickly in CI without allocating hundreds of megabytes.
"""
import json
import sqlite3
from pathlib import Path
from contextlib import closing

import pytest

from yomunote import __version__
from yomunote import notebook as notebook_mod
from yomunote.notebook import Notebook, _version_sortkey, read_bounded_manifest
from yomunote.backup_migration import _manifest as inspect_legacy
from yomunote.safe_overwrite import read_destination_info
from yomunote.safe_backup import create_snapshot, BackupFormatError
from yomunote.tab_exchange import _manifest as shared_manifest


def fixture_sqlite(path, manifest):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute('CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)')
        conn.execute('INSERT INTO meta(key,value) VALUES (?,?)', ('manifest', manifest))
        conn.commit()
    return path


def test_version_095_is_newer_than_092b_and_keeps_future_guard():
    assert __version__ == '1.0'
    assert _version_sortkey('0.95') > _version_sortkey('0.9.2b')
    assert _version_sortkey('1.0') > _version_sortkey('0.95')
    assert _version_sortkey('0.95a') < _version_sortkey('0.95')
    assert _version_sortkey('nonsense') is None


def test_bounded_loader_handles_valid_data_and_rejects_bad_types(tmp_path, monkeypatch):
    monkeypatch.setattr(notebook_mod, 'MAX_MANIFEST_BYTES', 512)
    path=fixture_sqlite(tmp_path/'simple.pinbunote', '{"id":"hello"}')
    with closing(sqlite3.connect(path)) as conn:
        assert read_bounded_manifest(conn) == {'id':'hello'}
        conn.execute('UPDATE meta SET value=?', ('x' * 513,))
        with pytest.raises(ValueError, match='too large'):
            read_bounded_manifest(conn)
        conn.execute('UPDATE meta SET value=?', ('[]',))
        with pytest.raises(ValueError, match='object'):
            read_bounded_manifest(conn)
        conn.execute('UPDATE meta SET value=?', ('not JSON',))
        with pytest.raises(ValueError, match='JSON'):
            read_bounded_manifest(conn)


def test_byte_limit_rejects_multibyte_text(tmp_path, monkeypatch):
    monkeypatch.setattr(notebook_mod,'MAX_MANIFEST_BYTES',20)
    path=fixture_sqlite(tmp_path/'unicode.pinbunote', '{"x":"' + '🌸'*8 + '"}')
    with closing(sqlite3.connect(path)) as conn:
        # SQLite length(text) sees about a dozen characters, but UTF-8
        # consumes >20 bytes. The limit must mean BYTES, not codepoints.
        assert conn.execute("SELECT length(value) FROM meta").fetchone()[0] < 20
        with pytest.raises(ValueError,match='too large'):
            read_bounded_manifest(conn)


def test_all_external_paths_reject_oversized_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(notebook_mod,'MAX_MANIFEST_BYTES',256)
    bad=fixture_sqlite(tmp_path/'oversized.pinbunote', '{"excess":"' + 'x'*1024 + '"}')
    with pytest.raises(ValueError):
        Notebook.load(bad)
    with pytest.raises(ValueError):
        Notebook.open_session(bad, tmp_path/'work')
    copy=tmp_path/'not-created.pinbunote'
    with pytest.raises(ValueError):
        Notebook.restore_copy(bad, copy)
    assert not copy.exists()
    with pytest.raises(ValueError):
        Notebook.create_clean_share_copy(bad, copy)
    assert not copy.exists()
    with pytest.raises(BackupFormatError):
        inspect_legacy(bad)
    with pytest.raises(ValueError):
        read_destination_info(bad)
    with pytest.raises(BackupFormatError):
        create_snapshot(bad,tmp_path/'archive')
    with closing(sqlite3.connect(bad)) as conn:
        with pytest.raises(ValueError):
            shared_manifest(conn)


def test_published_prior_version_remains_readable(tmp_path):
    notebook=Notebook.create(tmp_path,'Legacy example',extension='.pinbunote')
    path=notebook.path
    notebook.close()
    with closing(sqlite3.connect(path)) as conn:
        raw=conn.execute('SELECT value FROM meta WHERE key=?',('manifest',)).fetchone()[0]
        meta=json.loads(raw)
        meta['app_version']='0.9.2b'
        conn.execute('UPDATE meta SET value=? WHERE key=?', (json.dumps(meta),'manifest'))
        conn.commit()
    reopened=Notebook.load(path)
    try:
        assert reopened.identifier == meta['id']
    finally:
        reopened.close()


def test_future_app_version_still_blocks_loading(tmp_path):
    nb=Notebook.create(tmp_path, 'Future guard', extension='.pinbunote')
    path=nb.path
    nb.close()
    with closing(sqlite3.connect(path)) as conn:
        raw=conn.execute('SELECT value FROM meta WHERE key=?', ('manifest',)).fetchone()[0]
        meta=json.loads(raw)
        meta['app_version']='1.01'
        conn.execute('UPDATE meta SET value=? WHERE key=?',(json.dumps(meta),'manifest'))
        conn.commit()
    from yomunote.notebook import NotebookNewerVersionError
    with pytest.raises(NotebookNewerVersionError):
        Notebook.load(path)
